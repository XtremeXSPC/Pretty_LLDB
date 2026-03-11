from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from .helpers import (
    _safe_get_node_from_pointer,
    debug_print,
    get_nonsynthetic_value,
    get_raw_pointer,
    get_value_summary,
    type_has_field,
)
from .schema_adapters import (
    get_resolved_child,
    get_tree_children,
    resolve_graph_container_schema,
    resolve_graph_node_schema,
    resolve_linear_container_schema,
    resolve_linear_node_schema,
    resolve_tree_container_schema,
    resolve_tree_node_schema,
)


@dataclass
class FieldResolution:
    role: str
    candidates: Tuple[str, ...]
    matched: Optional[str]


@dataclass
class ExtractionWarning:
    code: str
    message: str


@dataclass
class ExtractionDiagnostics:
    structure_kind: str
    field_resolutions: List[FieldResolution] = field(default_factory=list)
    warnings: List[ExtractionWarning] = field(default_factory=list)

    def record_resolution(self, role: str, candidates: List[str], matched: Optional[str]) -> None:
        debug_print(
            f"[{self.structure_kind}] resolve {role}: matched={matched or '<unresolved>'}, candidates={candidates}"
        )
        self.field_resolutions.append(
            FieldResolution(role=role, candidates=tuple(candidates), matched=matched)
        )

    def warn(self, code: str, message: str) -> None:
        debug_print(f"[{self.structure_kind}] warning {code}: {message}")
        self.warnings.append(ExtractionWarning(code=code, message=message))

    def compact_summary(self) -> str:
        parts = []

        matched_fields = [
            f"{resolution.role}={resolution.matched}"
            for resolution in self.field_resolutions
            if resolution.matched
        ]
        if matched_fields:
            parts.append(", ".join(matched_fields))

        if self.warnings:
            warning_codes = ", ".join(warning.code for warning in self.warnings)
            parts.append(f"warnings={warning_codes}")

        if not parts:
            return ""

        return f" {{diag: {'; '.join(parts)}}}"


@dataclass
class LinearNode:
    address: int
    value: str
    next_address: int = 0


@dataclass
class ExtractedLinearStructure:
    diagnostics: ExtractionDiagnostics = field(
        default_factory=lambda: ExtractionDiagnostics("linear")
    )
    size: Optional[int] = None
    head_field: Optional[str] = None
    size_field: Optional[str] = None
    next_field: Optional[str] = None
    value_field: Optional[str] = None
    is_empty: bool = False
    is_doubly_linked: bool = False
    cycle_detected: bool = False
    truncated: bool = False
    error_message: Optional[str] = None
    nodes: List[LinearNode] = field(default_factory=list)

    @property
    def traversal_order(self) -> List[str]:
        return [f"0x{node.address:x}" for node in self.nodes]


@dataclass
class TreeNode:
    address: int
    value: str
    children: List[int] = field(default_factory=list)


@dataclass
class TreeEdge:
    source: int
    target: int


@dataclass
class ExtractedTreeStructure:
    diagnostics: ExtractionDiagnostics = field(
        default_factory=lambda: ExtractionDiagnostics("tree")
    )
    size: Optional[int] = None
    root_field: Optional[str] = None
    size_field: Optional[str] = None
    value_field: Optional[str] = None
    child_mode: Optional[str] = None
    root_address: int = 0
    is_empty: bool = False
    error_message: Optional[str] = None
    nodes: List[TreeNode] = field(default_factory=list)
    edges: List[TreeEdge] = field(default_factory=list)


@dataclass
class GraphEdge:
    source: int
    target: int


@dataclass
class GraphNode:
    address: int
    value: str
    neighbors: List[int] = field(default_factory=list)


@dataclass
class ExtractedGraphStructure:
    diagnostics: ExtractionDiagnostics = field(
        default_factory=lambda: ExtractionDiagnostics("graph")
    )
    size_field: Optional[str] = None
    edge_count_field: Optional[str] = None
    nodes_field: Optional[str] = None
    value_field: Optional[str] = None
    neighbors_field: Optional[str] = None
    num_nodes: Optional[int] = None
    num_edges: Optional[int] = None
    is_empty: bool = False
    error_message: Optional[str] = None
    nodes: List[GraphNode] = field(default_factory=list)
    edges: List[GraphEdge] = field(default_factory=list)


def _resolve_child_field(value, role: str, candidates: List[str], diagnostics):
    matched_name = None
    matched_child = None

    base_value = get_nonsynthetic_value(value)
    if base_value and base_value.IsValid():
        for candidate in candidates:
            child = base_value.GetChildMemberWithName(candidate)
            if child and child.IsValid():
                matched_name = candidate
                matched_child = child
                break

    diagnostics.record_resolution(role, candidates, matched_name)
    return matched_name, matched_child


def _resolve_type_field_name(type_obj, role: str, candidates: List[str], diagnostics):
    matched_name = None

    if type_obj:
        for candidate in candidates:
            if type_has_field(type_obj, candidate):
                matched_name = candidate
                break

    diagnostics.record_resolution(role, candidates, matched_name)
    return matched_name


def _resolve_existing_child_name(value, role: str, candidates: List[str], diagnostics):
    matched_name = None

    base_value = get_nonsynthetic_value(value)
    if base_value and base_value.IsValid():
        for candidate in candidates:
            child = base_value.GetChildMemberWithName(candidate)
            if child and child.IsValid():
                matched_name = candidate
                break

    diagnostics.record_resolution(role, candidates, matched_name)
    return matched_name


def _safe_num_children(value) -> int:
    base_value = get_nonsynthetic_value(value)
    if not base_value or not base_value.IsValid():
        return 0
    try:
        return base_value.GetNumChildren()
    except Exception:
        return 0


def detect_structure_kind(valobj) -> Optional[str]:
    if resolve_linear_container_schema(valobj).head_field:
        return "linear"
    if resolve_tree_container_schema(valobj).root_field:
        return "tree"
    if resolve_graph_container_schema(valobj).nodes_field:
        return "graph"
    return None


def extract_supported_structure(valobj, max_items: Optional[int] = None):
    structure_kind = detect_structure_kind(valobj)
    if structure_kind == "linear":
        return structure_kind, extract_linear_structure(valobj, max_items=max_items)
    if structure_kind == "tree":
        return structure_kind, extract_tree_structure(valobj)
    if structure_kind == "graph":
        return structure_kind, extract_graph_structure(valobj)
    return None, None


def extract_linear_structure(valobj, max_items: Optional[int] = None) -> ExtractedLinearStructure:
    diagnostics = ExtractionDiagnostics("linear")
    container_schema = resolve_linear_container_schema(valobj, diagnostics)

    extraction = ExtractedLinearStructure(
        diagnostics=diagnostics,
        head_field=container_schema.head_field,
        size_field=container_schema.size_field,
    )
    if container_schema.size_member:
        extraction.size = container_schema.size_member.GetValueAsUnsigned()

    if not container_schema.head_ptr and not extraction.head_field:
        extraction.error_message = "Error: Could not find head pointer member."
        diagnostics.warn("missing_head", "Could not find a valid head/top member.")
        return extraction

    if not container_schema.head_ptr or get_raw_pointer(container_schema.head_ptr) == 0:
        extraction.is_empty = True
        if extraction.size is None:
            extraction.size = 0
        return extraction

    first_node = _safe_get_node_from_pointer(container_schema.head_ptr)
    if not first_node or not first_node.IsValid():
        extraction.error_message = "Error: Could not dereference head pointer."
        diagnostics.warn("invalid_head", "The resolved head pointer could not be dereferenced.")
        return extraction

    node_schema = resolve_linear_node_schema(first_node, diagnostics)
    extraction.next_field = node_schema.next_field
    extraction.value_field = node_schema.value_field
    extraction.is_doubly_linked = node_schema.prev_field is not None

    if not extraction.next_field or not extraction.value_field:
        extraction.error_message = "Error: Could not determine node structure (val/next)"
        diagnostics.warn(
            "missing_node_schema",
            "Could not determine the linear node value/next fields.",
        )
        return extraction

    visited_addrs = set()
    current_ptr = container_schema.head_ptr
    traversal_limit = max_items if max_items is not None else 1000000

    while get_raw_pointer(current_ptr) != 0:
        if len(extraction.nodes) >= traversal_limit:
            extraction.truncated = True
            diagnostics.warn(
                "truncated",
                f"Traversal stopped after reaching the limit of {traversal_limit} items.",
            )
            break

        node_addr = get_raw_pointer(current_ptr)
        if node_addr in visited_addrs:
            extraction.cycle_detected = True
            diagnostics.warn(
                "cycle_detected",
                f"Detected a cycle at node address 0x{node_addr:x}.",
            )
            break
        visited_addrs.add(node_addr)

        node_struct = _safe_get_node_from_pointer(current_ptr)
        if not node_struct or not node_struct.IsValid():
            diagnostics.warn(
                "invalid_node",
                f"Could not dereference node at address 0x{node_addr:x}.",
            )
            break

        value_child = get_resolved_child(node_struct, extraction.value_field)
        next_child = get_resolved_child(node_struct, extraction.next_field)
        extraction.nodes.append(
            LinearNode(
                address=node_addr,
                value=get_value_summary(value_child),
                next_address=get_raw_pointer(next_child),
            )
        )

        if not next_child:
            diagnostics.warn(
                "missing_next_member",
                f"Node at address 0x{node_addr:x} is missing its resolved next field.",
            )
            break
        current_ptr = next_child

    if extraction.size is None:
        extraction.size = len(extraction.nodes)

    return extraction


def extract_tree_structure(valobj) -> ExtractedTreeStructure:
    diagnostics = ExtractionDiagnostics("tree")
    container_schema = resolve_tree_container_schema(valobj, diagnostics)

    extraction = ExtractedTreeStructure(
        diagnostics=diagnostics,
        root_field=container_schema.root_field,
        size_field=container_schema.size_field,
    )
    if container_schema.size_member:
        extraction.size = container_schema.size_member.GetValueAsUnsigned()

    if not container_schema.root_ptr and not extraction.root_field:
        extraction.error_message = "Tree is empty or root member not found."
        diagnostics.warn("missing_root", "Could not find a valid root member.")
        return extraction

    extraction.root_address = get_raw_pointer(container_schema.root_ptr)
    if extraction.root_address == 0:
        extraction.is_empty = True
        return extraction

    visited_addrs = set()

    def _visit(node_ptr):
        node_addr = get_raw_pointer(node_ptr)
        if node_addr == 0:
            return

        if node_addr in visited_addrs:
            diagnostics.warn(
                "cycle_detected",
                f"Detected a cycle at tree node address 0x{node_addr:x}.",
            )
            return
        visited_addrs.add(node_addr)

        node_struct = _safe_get_node_from_pointer(node_ptr)
        if not node_struct or not node_struct.IsValid():
            diagnostics.warn(
                "invalid_node",
                f"Could not dereference tree node at address 0x{node_addr:x}.",
            )
            return

        node_schema = resolve_tree_node_schema(node_struct, diagnostics)
        if extraction.value_field is None:
            extraction.value_field = node_schema.value_field
        if extraction.child_mode is None:
            extraction.child_mode = node_schema.child_mode

        value = get_resolved_child(node_struct, node_schema.value_field)
        children_ptrs = get_tree_children(node_struct, node_schema)
        child_addresses = []
        for child_ptr in children_ptrs:
            child_addr = get_raw_pointer(child_ptr)
            if child_addr != 0:
                child_addresses.append(child_addr)
                extraction.edges.append(TreeEdge(source=node_addr, target=child_addr))

        extraction.nodes.append(
            TreeNode(
                address=node_addr,
                value=get_value_summary(value),
                children=child_addresses,
            )
        )

        for child_ptr in children_ptrs:
            _visit(child_ptr)

    _visit(container_schema.root_ptr)

    if extraction.size is None and extraction.nodes:
        extraction.size = len(extraction.nodes)

    return extraction


def extract_graph_structure(valobj) -> ExtractedGraphStructure:
    diagnostics = ExtractionDiagnostics("graph")
    container_schema = resolve_graph_container_schema(valobj, diagnostics)

    extraction = ExtractedGraphStructure(
        diagnostics=diagnostics,
        nodes_field=container_schema.nodes_field,
        size_field=container_schema.node_count_field,
        edge_count_field=container_schema.edge_count_field,
    )
    if container_schema.node_count_member:
        extraction.num_nodes = container_schema.node_count_member.GetValueAsUnsigned()
    if container_schema.edge_count_member:
        extraction.num_edges = container_schema.edge_count_member.GetValueAsUnsigned()

    if not container_schema.nodes_container and not extraction.nodes_field:
        extraction.error_message = "Graph is empty or nodes container not found."
        extraction.is_empty = True
        diagnostics.warn("missing_nodes", "Could not find a valid graph nodes container.")
        return extraction

    nodes_container = container_schema.nodes_container
    if not nodes_container or not nodes_container.IsValid():
        extraction.error_message = "Graph is empty or nodes container not found."
        extraction.is_empty = True
        diagnostics.warn("missing_nodes", "Could not resolve the graph nodes container value.")
        return extraction

    node_map: Dict[int, GraphNode] = {}
    edge_set = set()
    for index in range(_safe_num_children(nodes_container)):
        node = nodes_container.GetChildAtIndex(index)
        if node and node.GetType().IsPointerType():
            node = node.Dereference()
        if not node or not node.IsValid():
            diagnostics.warn(
                "invalid_node",
                f"Encountered an invalid graph node entry at index {index}.",
            )
            continue

        node_addr = get_raw_pointer(node)
        if node_addr == 0:
            diagnostics.warn(
                "null_node",
                f"Encountered a null graph node entry at index {index}.",
            )
            continue

        node_schema = resolve_graph_node_schema(node, diagnostics)
        if extraction.value_field is None:
            extraction.value_field = node_schema.value_field
        if extraction.neighbors_field is None:
            extraction.neighbors_field = node_schema.neighbors_field

        if node_addr not in node_map:
            node_map[node_addr] = GraphNode(
                address=node_addr,
                value=get_value_summary(get_resolved_child(node, node_schema.value_field)),
            )

        neighbors = get_resolved_child(node, node_schema.neighbors_field)
        if neighbors and neighbors.IsValid():
            for neighbor_index in range(_safe_num_children(neighbors)):
                neighbor = neighbors.GetChildAtIndex(neighbor_index)
                if neighbor and neighbor.GetType().IsPointerType():
                    neighbor = neighbor.Dereference()
                if not neighbor or not neighbor.IsValid():
                    diagnostics.warn(
                        "invalid_neighbor",
                        f"Node 0x{node_addr:x} has an invalid neighbor entry at index {neighbor_index}.",
                    )
                    continue

                neighbor_addr = get_raw_pointer(neighbor)
                if neighbor_addr == 0:
                    continue

                node_map[node_addr].neighbors.append(neighbor_addr)
                edge = (node_addr, neighbor_addr)
                if edge not in edge_set:
                    edge_set.add(edge)
                    extraction.edges.append(GraphEdge(source=node_addr, target=neighbor_addr))

    extraction.nodes = list(node_map.values())

    if extraction.num_nodes is None:
        extraction.num_nodes = len(extraction.nodes)
    if extraction.num_edges is None:
        extraction.num_edges = len(extraction.edges)
    extraction.is_empty = len(extraction.nodes) == 0

    return extraction
