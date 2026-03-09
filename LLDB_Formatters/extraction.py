from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from .helpers import (
    _get_node_children,
    _safe_get_node_from_pointer,
    get_child_member_by_names,
    get_raw_pointer,
    get_value_summary,
    type_has_field,
)


LINEAR_HEAD_FIELDS = ["head", "m_head", "_head", "top"]
LINEAR_SIZE_FIELDS = ["count", "size", "m_size", "_size"]
LINEAR_NEXT_FIELDS = ["next", "m_next", "_next", "pNext"]
LINEAR_PREV_FIELDS = ["prev", "m_prev", "_prev", "pPrev"]
VALUE_FIELDS = ["value", "val", "data", "m_data", "key"]

TREE_ROOT_FIELDS = ["root", "m_root", "_root"]
TREE_SIZE_FIELDS = ["size", "m_size", "count"]
TREE_CHILDREN_FIELDS = ["children", "m_children"]
TREE_LEFT_FIELDS = ["left", "m_left", "_left"]
TREE_RIGHT_FIELDS = ["right", "m_right", "_right"]

GRAPH_NODE_CONTAINER_FIELDS = ["nodes", "m_nodes", "adj", "adjacency_list"]
GRAPH_NEIGHBOR_FIELDS = ["neighbors", "adj", "edges"]
GRAPH_NODE_COUNT_FIELDS = ["num_nodes", "V", "node_count"]
GRAPH_EDGE_COUNT_FIELDS = ["num_edges", "E", "edge_count"]


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

    def record_resolution(
        self, role: str, candidates: List[str], matched: Optional[str]
    ) -> None:
        self.field_resolutions.append(
            FieldResolution(role=role, candidates=tuple(candidates), matched=matched)
        )

    def warn(self, code: str, message: str) -> None:
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

    if value and value.IsValid():
        for candidate in candidates:
            child = value.GetChildMemberWithName(candidate)
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

    if value and value.IsValid():
        for candidate in candidates:
            child = value.GetChildMemberWithName(candidate)
            if child and child.IsValid():
                matched_name = candidate
                break

    diagnostics.record_resolution(role, candidates, matched_name)
    return matched_name


def _safe_num_children(value) -> int:
    if not value or not value.IsValid():
        return 0
    try:
        return value.GetNumChildren()
    except Exception:
        return 0


def extract_linear_structure(
    valobj, max_items: Optional[int] = None
) -> ExtractedLinearStructure:
    diagnostics = ExtractionDiagnostics("linear")
    size_field, size_member = _resolve_child_field(
        valobj, "container_size", LINEAR_SIZE_FIELDS, diagnostics
    )
    head_field, head_ptr = _resolve_child_field(
        valobj, "container_head", LINEAR_HEAD_FIELDS, diagnostics
    )

    extraction = ExtractedLinearStructure(
        diagnostics=diagnostics, head_field=head_field, size_field=size_field
    )
    if size_member:
        extraction.size = size_member.GetValueAsUnsigned()

    if not head_ptr:
        extraction.error_message = "Error: Could not find head pointer member."
        diagnostics.warn("missing_head", "Could not find a valid head/top member.")
        return extraction

    if get_raw_pointer(head_ptr) == 0:
        extraction.is_empty = True
        if extraction.size is None:
            extraction.size = 0
        return extraction

    first_node = _safe_get_node_from_pointer(head_ptr)
    if not first_node or not first_node.IsValid():
        extraction.error_message = "Error: Could not dereference head pointer."
        diagnostics.warn(
            "invalid_head", "The resolved head pointer could not be dereferenced."
        )
        return extraction

    node_type = first_node.GetType()
    extraction.next_field = _resolve_type_field_name(
        node_type, "node_next", LINEAR_NEXT_FIELDS, diagnostics
    )
    extraction.value_field = _resolve_type_field_name(
        node_type, "node_value", VALUE_FIELDS, diagnostics
    )
    prev_field = _resolve_type_field_name(
        node_type, "node_prev", LINEAR_PREV_FIELDS, diagnostics
    )
    extraction.is_doubly_linked = prev_field is not None

    if not extraction.next_field or not extraction.value_field:
        extraction.error_message = "Error: Could not determine node structure (val/next)"
        diagnostics.warn(
            "missing_node_schema",
            "Could not determine the linear node value/next fields.",
        )
        return extraction

    visited_addrs = set()
    current_ptr = head_ptr
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

        value_child = node_struct.GetChildMemberWithName(extraction.value_field)
        next_child = node_struct.GetChildMemberWithName(extraction.next_field)
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
    size_field, size_member = _resolve_child_field(
        valobj, "container_size", TREE_SIZE_FIELDS, diagnostics
    )
    root_field, root_ptr = _resolve_child_field(
        valobj, "container_root", TREE_ROOT_FIELDS, diagnostics
    )

    extraction = ExtractedTreeStructure(
        diagnostics=diagnostics, root_field=root_field, size_field=size_field
    )
    if size_member:
        extraction.size = size_member.GetValueAsUnsigned()

    if not root_ptr:
        extraction.error_message = "Tree is empty or root member not found."
        diagnostics.warn("missing_root", "Could not find a valid root member.")
        return extraction

    extraction.root_address = get_raw_pointer(root_ptr)
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

        if extraction.value_field is None:
            extraction.value_field = _resolve_existing_child_name(
                node_struct, "node_value", VALUE_FIELDS, diagnostics
            )

        if extraction.child_mode is None:
            children_field = _resolve_existing_child_name(
                node_struct, "node_children", TREE_CHILDREN_FIELDS, diagnostics
            )
            if children_field:
                extraction.child_mode = "nary"
            else:
                left_field = _resolve_existing_child_name(
                    node_struct, "node_left", TREE_LEFT_FIELDS, diagnostics
                )
                right_field = _resolve_existing_child_name(
                    node_struct, "node_right", TREE_RIGHT_FIELDS, diagnostics
                )
                if left_field or right_field:
                    extraction.child_mode = "binary"

        value = get_child_member_by_names(node_struct, VALUE_FIELDS)
        children_ptrs = _get_node_children(node_struct)
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

    _visit(root_ptr)

    if extraction.size is None and extraction.nodes:
        extraction.size = len(extraction.nodes)

    return extraction


def extract_graph_structure(valobj) -> ExtractedGraphStructure:
    diagnostics = ExtractionDiagnostics("graph")
    nodes_field, nodes_container = _resolve_child_field(
        valobj, "container_nodes", GRAPH_NODE_CONTAINER_FIELDS, diagnostics
    )
    size_field, size_member = _resolve_child_field(
        valobj, "container_node_count", GRAPH_NODE_COUNT_FIELDS, diagnostics
    )
    edge_count_field, edge_count_member = _resolve_child_field(
        valobj, "container_edge_count", GRAPH_EDGE_COUNT_FIELDS, diagnostics
    )

    extraction = ExtractedGraphStructure(
        diagnostics=diagnostics,
        nodes_field=nodes_field,
        size_field=size_field,
        edge_count_field=edge_count_field,
    )
    if size_member:
        extraction.num_nodes = size_member.GetValueAsUnsigned()
    if edge_count_member:
        extraction.num_edges = edge_count_member.GetValueAsUnsigned()

    if not nodes_container or not nodes_container.IsValid():
        extraction.error_message = "Graph is empty or nodes container not found."
        extraction.is_empty = True
        diagnostics.warn("missing_nodes", "Could not find a valid graph nodes container.")
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

        if extraction.value_field is None:
            extraction.value_field = _resolve_existing_child_name(
                node, "node_value", VALUE_FIELDS, diagnostics
            )
        if extraction.neighbors_field is None:
            extraction.neighbors_field = _resolve_existing_child_name(
                node, "node_neighbors", GRAPH_NEIGHBOR_FIELDS, diagnostics
            )

        if node_addr not in node_map:
            node_map[node_addr] = GraphNode(
                address=node_addr,
                value=get_value_summary(get_child_member_by_names(node, VALUE_FIELDS)),
            )

        neighbors = get_child_member_by_names(node, GRAPH_NEIGHBOR_FIELDS)
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

