import re
from dataclasses import dataclass
from typing import Dict, Optional, Tuple

from .helpers import get_child_member_by_names, get_raw_pointer, type_has_field
from .pointers import get_nonsynthetic_value

COMMON_VALUE_FIELDS = (
    "value",
    "val",
    "data",
    "m_data",
    "key",
    "payload",
    "m_payload",
    "element",
    "item",
    "node_value",
)

COMMON_SIZE_FIELDS = (
    "size",
    "m_size",
    "_size",
    "count",
    "length",
    "len",
    "node_count",
)


@dataclass(frozen=True)
class AdapterDefinition:
    name: str
    roles: Dict[str, Tuple[str, ...]]
    required_roles: Tuple[str, ...] = ()
    type_name_patterns: Tuple[str, ...] = ()


@dataclass
class LinearContainerSchema:
    adapter_name: Optional[str] = None
    head_field: Optional[str] = None
    size_field: Optional[str] = None
    head_ptr: Optional[object] = None
    size_member: Optional[object] = None


@dataclass
class LinearNodeSchema:
    adapter_name: Optional[str] = None
    value_field: Optional[str] = None
    next_field: Optional[str] = None
    prev_field: Optional[str] = None


@dataclass
class TreeContainerSchema:
    adapter_name: Optional[str] = None
    root_field: Optional[str] = None
    size_field: Optional[str] = None
    root_ptr: Optional[object] = None
    size_member: Optional[object] = None


@dataclass
class TreeNodeSchema:
    adapter_name: Optional[str] = None
    value_field: Optional[str] = None
    left_field: Optional[str] = None
    right_field: Optional[str] = None
    children_field: Optional[str] = None

    @property
    def child_mode(self) -> Optional[str]:
        if self.children_field:
            return "nary"
        if self.left_field or self.right_field:
            return "binary"
        return None


@dataclass
class GraphContainerSchema:
    adapter_name: Optional[str] = None
    nodes_field: Optional[str] = None
    node_count_field: Optional[str] = None
    edge_count_field: Optional[str] = None
    nodes_container: Optional[object] = None
    node_count_member: Optional[object] = None
    edge_count_member: Optional[object] = None


@dataclass
class GraphNodeSchema:
    adapter_name: Optional[str] = None
    value_field: Optional[str] = None
    neighbors_field: Optional[str] = None


LINEAR_CONTAINER_ADAPTERS = (
    AdapterDefinition(
        name="linear_standard_container",
        roles={
            "head": ("head", "m_head", "_head", "top"),
            "size": COMMON_SIZE_FIELDS,
        },
        required_roles=("head",),
        type_name_patterns=(r"list", r"stack", r"queue"),
    ),
    AdapterDefinition(
        name="linear_first_container",
        roles={
            "head": ("first", "front", "begin", "begin_", "first_node"),
            "size": COMMON_SIZE_FIELDS,
        },
        required_roles=("head",),
        type_name_patterns=(r"list", r"queue"),
    ),
)

LINEAR_NODE_ADAPTERS = (
    AdapterDefinition(
        name="linear_standard_node",
        roles={
            "value": COMMON_VALUE_FIELDS,
            "next": ("next", "m_next", "_next", "pNext"),
            "prev": ("prev", "m_prev", "_prev", "pPrev", "previous"),
        },
        required_roles=("value", "next"),
        type_name_patterns=(r"list", r"node", r"stack", r"queue"),
    ),
    AdapterDefinition(
        name="linear_link_node",
        roles={
            "value": COMMON_VALUE_FIELDS,
            "next": ("link", "m_link", "_link", "node_next", "next_node", "next_"),
            "prev": ("back", "prev", "previous", "prev_link", "previous_link"),
        },
        required_roles=("value", "next"),
        type_name_patterns=(r"list", r"node"),
    ),
)

TREE_CONTAINER_ADAPTERS = (
    AdapterDefinition(
        name="tree_standard_container",
        roles={
            "root": ("root", "m_root", "_root"),
            "size": COMMON_SIZE_FIELDS,
        },
        required_roles=("root",),
        type_name_patterns=(r"tree",),
    ),
    AdapterDefinition(
        name="tree_alt_container",
        roles={
            "root": ("root_node", "origin", "entry"),
            "size": COMMON_SIZE_FIELDS,
        },
        required_roles=("root",),
        type_name_patterns=(r"tree",),
    ),
)

TREE_NODE_ADAPTERS = (
    AdapterDefinition(
        name="tree_binary_standard_node",
        roles={
            "value": COMMON_VALUE_FIELDS,
            "left": ("left", "m_left", "_left"),
            "right": ("right", "m_right", "_right"),
        },
        required_roles=("value",),
        type_name_patterns=(r"tree", r"node"),
    ),
    AdapterDefinition(
        name="tree_binary_alt_node",
        roles={
            "value": COMMON_VALUE_FIELDS,
            "left": ("lhs", "left_child", "child_left"),
            "right": ("rhs", "right_child", "child_right"),
        },
        required_roles=("value",),
        type_name_patterns=(r"tree", r"node"),
    ),
    AdapterDefinition(
        name="tree_nary_standard_node",
        roles={
            "value": COMMON_VALUE_FIELDS,
            "children": ("children", "m_children", "_children"),
        },
        required_roles=("value", "children"),
        type_name_patterns=(r"tree", r"node"),
    ),
    AdapterDefinition(
        name="tree_nary_alt_node",
        roles={
            "value": COMMON_VALUE_FIELDS,
            "children": ("kids", "child_nodes", "nodes", "descendants"),
        },
        required_roles=("value", "children"),
        type_name_patterns=(r"tree", r"node"),
    ),
)

GRAPH_CONTAINER_ADAPTERS = (
    AdapterDefinition(
        name="graph_standard_container",
        roles={
            "nodes": ("nodes", "m_nodes", "adj", "adjacency_list"),
            "node_count": ("num_nodes", "V", "node_count"),
            "edge_count": ("num_edges", "E", "edge_count"),
        },
        required_roles=("nodes",),
        type_name_patterns=(r"graph",),
    ),
    AdapterDefinition(
        name="graph_alt_container",
        roles={
            "nodes": ("vertices", "vertex_list", "graph_nodes"),
            "node_count": ("vertex_count", "vertices_count", "num_vertices"),
            "edge_count": ("edge_total", "edges_count", "num_edges"),
        },
        required_roles=("nodes",),
        type_name_patterns=(r"graph",),
    ),
)

GRAPH_NODE_ADAPTERS = (
    AdapterDefinition(
        name="graph_standard_node",
        roles={
            "value": COMMON_VALUE_FIELDS,
            "neighbors": ("neighbors", "adj", "edges", "adjacency"),
        },
        required_roles=("value", "neighbors"),
        type_name_patterns=(r"graph", r"vertex", r"node"),
    ),
    AdapterDefinition(
        name="graph_alt_node",
        roles={
            "value": COMMON_VALUE_FIELDS,
            "neighbors": ("connections", "links", "adjacent", "neighbors_"),
        },
        required_roles=("value", "neighbors"),
        type_name_patterns=(r"graph", r"vertex", r"node"),
    ),
)


def _type_name_matches(type_name: str, patterns: Tuple[str, ...]) -> bool:
    return any(re.search(pattern, type_name, flags=re.IGNORECASE) for pattern in patterns)


def _resolve_child_or_field(value, candidates: Tuple[str, ...]):
    base_value = get_nonsynthetic_value(value)
    if not base_value or not base_value.IsValid():
        return None, None

    for candidate in candidates:
        child = base_value.GetChildMemberWithName(candidate)
        if child and child.IsValid():
            return candidate, child

    type_obj = base_value.GetType()
    for candidate in candidates:
        if type_obj and type_has_field(type_obj, candidate):
            return candidate, None

    return None, None


def _resolve_type_field(type_obj, candidates: Tuple[str, ...]) -> Optional[str]:
    if not type_obj:
        return None

    for candidate in candidates:
        if type_has_field(type_obj, candidate):
            return candidate
    return None


def _select_value_adapter(value, adapters):
    base_value = get_nonsynthetic_value(value)
    type_name = ""
    if base_value and base_value.IsValid():
        type_name = base_value.GetTypeName() or ""

    best = None
    for adapter in adapters:
        matched_fields = {}
        matched_children = {}
        matched_roles = 0
        required_matches = 0
        for role, candidates in adapter.roles.items():
            matched_field, matched_child = _resolve_child_or_field(base_value, candidates)
            matched_fields[role] = matched_field
            matched_children[role] = matched_child
            if matched_field:
                matched_roles += 1
                if role in adapter.required_roles:
                    required_matches += 1
        required_ok = required_matches == len(adapter.required_roles)
        score = (
            1 if required_ok else 0,
            1 if _type_name_matches(type_name, adapter.type_name_patterns) else 0,
            required_matches,
            matched_roles,
        )
        if best is None or score > best["score"]:
            best = {
                "adapter": adapter,
                "matched_fields": matched_fields,
                "matched_children": matched_children,
                "score": score,
            }
    return best


def _select_type_adapter(value_or_type, adapters):
    type_obj = value_or_type.GetType() if hasattr(value_or_type, "GetType") else value_or_type
    type_name = ""
    if hasattr(value_or_type, "GetTypeName"):
        type_name = value_or_type.GetTypeName() or ""

    best = None
    for adapter in adapters:
        matched_fields = {}
        matched_roles = 0
        required_matches = 0
        for role, candidates in adapter.roles.items():
            matched_field = _resolve_type_field(type_obj, candidates)
            matched_fields[role] = matched_field
            if matched_field:
                matched_roles += 1
                if role in adapter.required_roles:
                    required_matches += 1
        required_ok = required_matches == len(adapter.required_roles)
        score = (
            1 if required_ok else 0,
            1 if _type_name_matches(type_name, adapter.type_name_patterns) else 0,
            required_matches,
            matched_roles,
        )
        if best is None or score > best["score"]:
            best = {
                "adapter": adapter,
                "matched_fields": matched_fields,
                "score": score,
            }
    return best


def _record_resolutions(diagnostics, adapter, matched_fields, role_names):
    if diagnostics is None or adapter is None:
        return

    for role, candidates in adapter.roles.items():
        diagnostics.record_resolution(
            role_names[role],
            list(candidates),
            matched_fields.get(role),
        )


def resolve_linear_container_schema(value, diagnostics=None) -> LinearContainerSchema:
    match = _select_value_adapter(value, LINEAR_CONTAINER_ADAPTERS)
    adapter = match["adapter"]
    _record_resolutions(
        diagnostics,
        adapter,
        match["matched_fields"],
        {"head": "container_head", "size": "container_size"},
    )
    return LinearContainerSchema(
        adapter_name=adapter.name if adapter else None,
        head_field=match["matched_fields"].get("head"),
        size_field=match["matched_fields"].get("size"),
        head_ptr=match["matched_children"].get("head"),
        size_member=match["matched_children"].get("size"),
    )


def resolve_linear_node_schema(value_or_type, diagnostics=None) -> LinearNodeSchema:
    match = _select_type_adapter(value_or_type, LINEAR_NODE_ADAPTERS)
    adapter = match["adapter"]
    _record_resolutions(
        diagnostics,
        adapter,
        match["matched_fields"],
        {"value": "node_value", "next": "node_next", "prev": "node_prev"},
    )
    return LinearNodeSchema(
        adapter_name=adapter.name if adapter else None,
        value_field=match["matched_fields"].get("value"),
        next_field=match["matched_fields"].get("next"),
        prev_field=match["matched_fields"].get("prev"),
    )


def resolve_tree_container_schema(value, diagnostics=None) -> TreeContainerSchema:
    match = _select_value_adapter(value, TREE_CONTAINER_ADAPTERS)
    adapter = match["adapter"]
    _record_resolutions(
        diagnostics,
        adapter,
        match["matched_fields"],
        {"root": "container_root", "size": "container_size"},
    )
    return TreeContainerSchema(
        adapter_name=adapter.name if adapter else None,
        root_field=match["matched_fields"].get("root"),
        size_field=match["matched_fields"].get("size"),
        root_ptr=match["matched_children"].get("root"),
        size_member=match["matched_children"].get("size"),
    )


def resolve_tree_node_schema(value_or_type, diagnostics=None) -> TreeNodeSchema:
    match = _select_type_adapter(value_or_type, TREE_NODE_ADAPTERS)
    adapter = match["adapter"]
    _record_resolutions(
        diagnostics,
        adapter,
        match["matched_fields"],
        {
            "value": "node_value",
            "left": "node_left",
            "right": "node_right",
            "children": "node_children",
        },
    )
    return TreeNodeSchema(
        adapter_name=adapter.name if adapter else None,
        value_field=match["matched_fields"].get("value"),
        left_field=match["matched_fields"].get("left"),
        right_field=match["matched_fields"].get("right"),
        children_field=match["matched_fields"].get("children"),
    )


def resolve_graph_container_schema(value, diagnostics=None) -> GraphContainerSchema:
    match = _select_value_adapter(value, GRAPH_CONTAINER_ADAPTERS)
    adapter = match["adapter"]
    _record_resolutions(
        diagnostics,
        adapter,
        match["matched_fields"],
        {
            "nodes": "container_nodes",
            "node_count": "container_node_count",
            "edge_count": "container_edge_count",
        },
    )
    return GraphContainerSchema(
        adapter_name=adapter.name if adapter else None,
        nodes_field=match["matched_fields"].get("nodes"),
        node_count_field=match["matched_fields"].get("node_count"),
        edge_count_field=match["matched_fields"].get("edge_count"),
        nodes_container=match["matched_children"].get("nodes"),
        node_count_member=match["matched_children"].get("node_count"),
        edge_count_member=match["matched_children"].get("edge_count"),
    )


def resolve_graph_node_schema(value_or_type, diagnostics=None) -> GraphNodeSchema:
    match = _select_type_adapter(value_or_type, GRAPH_NODE_ADAPTERS)
    adapter = match["adapter"]
    _record_resolutions(
        diagnostics,
        adapter,
        match["matched_fields"],
        {"value": "node_value", "neighbors": "node_neighbors"},
    )
    return GraphNodeSchema(
        adapter_name=adapter.name if adapter else None,
        value_field=match["matched_fields"].get("value"),
        neighbors_field=match["matched_fields"].get("neighbors"),
    )


def get_resolved_child(value, field_name):
    if not field_name:
        return None
    return get_child_member_by_names(value, [field_name])


def get_tree_children(node_struct, schema: Optional[TreeNodeSchema] = None):
    if schema is None:
        schema = resolve_tree_node_schema(node_struct)

    children = []
    if schema.children_field:
        children_container = get_resolved_child(node_struct, schema.children_field)
        if (
            children_container
            and children_container.IsValid()
            and children_container.MightHaveChildren()
        ):
            for index in range(children_container.GetNumChildren()):
                child = children_container.GetChildAtIndex(index)
                if child and get_raw_pointer(child) != 0:
                    children.append(child)
            return children

    for field_name in (schema.left_field, schema.right_field):
        child = get_resolved_child(node_struct, field_name)
        if child and get_raw_pointer(child) != 0:
            children.append(child)

    return children
