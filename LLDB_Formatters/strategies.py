# ============================================================================ #
"""
Traversal strategies for Pretty LLDB structure summaries and exports.

This module implements the strategy layer used to walk supported structures in
different orders. It keeps traversal semantics separate from formatter entry
points so summaries, synthetic providers, and exporters can share the same
ordered views of the extracted data.

Author: XtremeXSPC
Version: 0.5.0.dev0
"""
# ============================================================================ #

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Tuple

# The 'lldb' module is not available in a standard Python interpreter.
# We use this block to allow type hinting without causing an ImportError
# when running static analysis tools.
try:
    import lldb  # type: ignore
except ImportError:
    pass

from .helpers import (
    SUMMARY_CYCLE_MARKER,
    _safe_get_node_from_pointer,
    g_config,
    get_raw_pointer,
    get_value_summary,
)
from .renderers import _escape_dot_label
from .schema_adapters import (
    get_resolved_child,
    get_tree_children,
    resolve_linear_node_schema,
    resolve_tree_node_schema,
)


# -------------------- Traversal Strategy Base Class -------------------- #
class TraversalStrategy(ABC):
    """
    Define the common interface shared by all traversal strategy implementations.
    """

    @abstractmethod
    def traverse(
        self, root_ptr: "lldb.SBValue", max_items: int
    ) -> Tuple[List[str], Dict[str, Any]]:
        """
        Traverse a structure and return ordered value summaries plus metadata.
        """
        pass

    def traverse_for_dot(self, root_ptr: "lldb.SBValue") -> Tuple[List[str], Dict[str, Any]]:
        """
        Generate DOT-oriented traversal output for simple non-tree structures.

        Subclasses can override this when they need richer structural fidelity,
        as the tree strategies do for parent-child rendering.
        """
        # Default implementation for non-tree-like structures
        values, metadata = self.traverse(root_ptr, max_items=g_config.summary_max_items)
        dot_lines = ["digraph G {", '  rankdir="LR";', "  node [shape=box];"]
        for i, value in enumerate(values):
            dot_lines.append(f'  Node_{i} [label="{_escape_dot_label(value)}"];')
            if i > 0:
                dot_lines.append(f"  Node_{i-1} -> Node_{i};")
        dot_lines.append("}")
        return dot_lines, metadata


# -------------------- Concrete Traversal Strategies -------------------- #
class LinearTraversalStrategy(TraversalStrategy):
    """Traverse linear pointer-linked structures such as lists and queues."""

    def traverse(
        self, root_ptr: "lldb.SBValue", max_items: int
    ) -> Tuple[List[str], Dict[str, Any]]:
        """Traverse a linear chain while tracking truncation and cycle state."""

        if not root_ptr or get_raw_pointer(root_ptr) == 0:
            return [], {}

        # Introspect the first node to find member names dynamically.
        node_obj = _safe_get_node_from_pointer(root_ptr)
        if not node_obj or not node_obj.IsValid():
            return [], {}

        schema = resolve_linear_node_schema(node_obj)
        next_ptr_name = schema.next_field
        value_name = schema.value_field
        is_doubly_linked = schema.prev_field is not None

        if not next_ptr_name or not value_name:
            return ["Error: Could not determine node structure (val/next)"], {}

        values: List[str] = []
        visited_addrs = set()
        current_ptr = root_ptr
        truncated = False

        while get_raw_pointer(current_ptr) != 0:
            if len(values) >= max_items:
                truncated = True
                break

            node_addr = get_raw_pointer(current_ptr)
            if node_addr in visited_addrs:
                values.append(SUMMARY_CYCLE_MARKER)
                break
            visited_addrs.add(node_addr)

            node_struct = _safe_get_node_from_pointer(current_ptr)
            if not node_struct or not node_struct.IsValid():
                break

            value_child = get_resolved_child(node_struct, value_name)
            values.append(get_value_summary(value_child))

            current_ptr = get_resolved_child(node_struct, next_ptr_name)

        metadata: Dict[str, Any] = {
            "truncated": truncated,
            "doubly_linked": is_doubly_linked,
        }
        return values, metadata


# ----------------- Tree Traversal Strategy Base Class ------------------ #
def _result_limit_reached(results: List[object], max_items: Optional[int]) -> bool:
    """Return whether a traversal output list has reached its configured limit."""

    return max_items is not None and len(results) >= max_items


def _resolve_tree_visit_payload(node_ptr: "lldb.SBValue"):
    """Resolve the normalized visit payload needed by iterative tree traversals."""

    node = _safe_get_node_from_pointer(node_ptr)
    if not node or not node.IsValid():
        return None

    schema = resolve_tree_node_schema(node)
    value = get_resolved_child(node, schema.value_field)
    value_summary = get_value_summary(value)

    if schema.child_mode == "binary":
        left_child = get_resolved_child(node, schema.left_field)
        right_child = get_resolved_child(node, schema.right_field)
        ordered_children = []
        for child in (left_child, right_child):
            if child and get_raw_pointer(child) != 0:
                ordered_children.append(child)
        return {
            "node": node,
            "schema": schema,
            "value_summary": value_summary,
            "is_binary": True,
            "left_child": left_child,
            "right_child": right_child,
            "children": ordered_children,
        }

    return {
        "node": node,
        "schema": schema,
        "value_summary": value_summary,
        "is_binary": False,
        "left_child": None,
        "right_child": None,
        "children": get_tree_children(node, schema),
    }


def _schedule_tree_frames(order: str, payload: Dict[str, Any], node_ptr, depth: int):
    """Return the stack frames that execute one node in the requested order."""

    visit_frame = ("visit", None, depth, get_raw_pointer(node_ptr), payload["value_summary"])

    if order == "preorder":
        frames = [("enter", child, depth + 1, 0, None) for child in reversed(payload["children"])]
        frames.append(visit_frame)
        return frames

    if order == "postorder":
        frames = [visit_frame]
        frames.extend(
            ("enter", child, depth + 1, 0, None) for child in reversed(payload["children"])
        )
        return frames

    if payload["is_binary"]:
        frames = []
        right_child = payload["right_child"]
        left_child = payload["left_child"]
        if right_child and get_raw_pointer(right_child) != 0:
            frames.append(("enter", right_child, depth + 1, 0, None))
        frames.append(visit_frame)
        if left_child and get_raw_pointer(left_child) != 0:
            frames.append(("enter", left_child, depth + 1, 0, None))
        return frames

    frames = [
        ("enter", child, depth + 1, 0, None) for child in reversed(payload["children"][1:])
    ]
    frames.append(visit_frame)
    if payload["children"]:
        frames.append(("enter", payload["children"][0], depth + 1, 0, None))
    return frames


def _run_tree_traversal(
    root_ptr: "lldb.SBValue",
    order: str,
    max_items: Optional[int],
    include_cycle_markers: bool,
    collect_addresses: bool = False,
):
    """Run one iterative tree traversal and return ordered output plus metadata."""

    results: List[object] = []
    visited_addrs = set()
    depth_limited = False
    limit_reached = False
    stack = [("enter", root_ptr, 0, 0, None)]
    max_depth = g_config.tree_max_depth

    while stack:
        if _result_limit_reached(results, max_items):
            limit_reached = True
            break

        state, node_ptr, depth, node_addr, value_summary = stack.pop()
        if state == "visit":
            results.append(node_addr if collect_addresses else value_summary)
            continue

        if not node_ptr or get_raw_pointer(node_ptr) == 0:
            continue
        if depth > max_depth:
            depth_limited = True
            continue

        node_addr = get_raw_pointer(node_ptr)
        if node_addr in visited_addrs:
            if include_cycle_markers and not _result_limit_reached(results, max_items):
                results.append(SUMMARY_CYCLE_MARKER)
            continue
        visited_addrs.add(node_addr)

        payload = _resolve_tree_visit_payload(node_ptr)
        if payload is None:
            continue

        for frame in _schedule_tree_frames(order, payload, node_ptr, depth):
            stack.append(frame)

    metadata: Dict[str, Any] = {
        "truncated": limit_reached or depth_limited,
        "depth_limited": depth_limited,
    }
    return results, metadata


class TreeTraversalStrategy(TraversalStrategy):
    """
    Provide shared tree-specific traversal helpers for concrete tree strategies.

    In addition to the base traversal contract, this class knows how to
    generate DOT-friendly parent-child output and how to expose ordered node
    addresses for synthetic providers and traversal annotations.
    """

    traversal_order_name = "preorder"

    def traverse_for_dot(
        self, root_ptr: "lldb.SBValue", annotate: bool = False
    ) -> Tuple[List[str], Dict[str, Any]]:
        """
        Generate DOT body lines that preserve the real tree structure.
        """

        dot_lines = []
        visited_addrs = set()
        traversal_map = {}
        max_depth = g_config.tree_max_depth
        depth_limited = False
        stack = [(root_ptr, 0)]

        if annotate:
            ordered_addrs = self._get_ordered_addresses(root_ptr)
            traversal_map = {addr: index for index, addr in enumerate(ordered_addrs, 1)}

        while stack:
            node_ptr, depth = stack.pop()
            if not node_ptr or get_raw_pointer(node_ptr) == 0:
                continue
            if depth > max_depth:
                depth_limited = True
                continue

            node_addr = get_raw_pointer(node_ptr)
            if node_addr in visited_addrs:
                continue
            visited_addrs.add(node_addr)

            payload = _resolve_tree_visit_payload(node_ptr)
            if payload is None:
                continue

            label = payload["value_summary"]
            if traversal_map and node_addr in traversal_map:
                label = f"{traversal_map[node_addr]}: {label}"
            dot_lines.append(f'  Node_{node_addr} [label="{_escape_dot_label(label)}"];')

            next_children = []
            for child_ptr in payload["children"]:
                child_addr = get_raw_pointer(child_ptr)
                if child_addr == 0:
                    continue
                if depth + 1 > max_depth:
                    depth_limited = True
                    continue
                dot_lines.append(f"  Node_{node_addr} -> Node_{child_addr};")
                next_children.append((child_ptr, depth + 1))

            for child_item in reversed(next_children):
                stack.append(child_item)

        return dot_lines, {"depth_limited": depth_limited, "truncated": depth_limited}

    def ordered_addresses(
        self, root_ptr: "lldb.SBValue", max_items: Optional[int] = None
    ) -> List[int]:
        """Return node addresses in the concrete traversal order of the strategy."""

        return self._get_ordered_addresses(root_ptr, max_items=max_items)

    def _get_ordered_addresses(
        self, root_ptr: "lldb.SBValue", max_items: Optional[int] = None
    ) -> List[int]:
        """
        Return node addresses in the traversal order defined by the subclass.
        """

        results, _ = _run_tree_traversal(
            root_ptr,
            self.traversal_order_name,
            max_items=max_items,
            include_cycle_markers=False,
            collect_addresses=True,
        )
        return [address for address in results if isinstance(address, int)]


# ----------------- Concrete Tree Traversal Strategies ------------------ #
class PreOrderTreeStrategy(TreeTraversalStrategy):
    """Traverse trees in pre-order, visiting the root before its children."""

    traversal_order_name = "preorder"

    def traverse(
        self, root_ptr: "lldb.SBValue", max_items: int
    ) -> Tuple[List[str], Dict[str, Any]]:
        """Traverse a tree in pre-order with cycle and depth safeguards."""

        return _run_tree_traversal(
            root_ptr,
            self.traversal_order_name,
            max_items=max_items,
            include_cycle_markers=True,
        )


class InOrderTreeStrategy(TreeTraversalStrategy):
    """
    Traverse trees in in-order.

    Binary trees use the classic `(left, root, right)` rule, while n-ary trees
    use the formatter's generalized `(first child, root, remaining children)`
    convention.
    """

    traversal_order_name = "inorder"

    def traverse(
        self, root_ptr: "lldb.SBValue", max_items: int
    ) -> Tuple[List[str], Dict[str, Any]]:
        """Traverse a tree in in-order with cycle and depth safeguards."""

        return _run_tree_traversal(
            root_ptr,
            self.traversal_order_name,
            max_items=max_items,
            include_cycle_markers=True,
        )


class PostOrderTreeStrategy(TreeTraversalStrategy):
    """Traverse trees in post-order, visiting children before the root."""

    traversal_order_name = "postorder"

    def traverse(
        self, root_ptr: "lldb.SBValue", max_items: int
    ) -> Tuple[List[str], Dict[str, Any]]:
        """Traverse a tree in post-order with cycle and depth safeguards."""

        return _run_tree_traversal(
            root_ptr,
            self.traversal_order_name,
            max_items=max_items,
            include_cycle_markers=True,
        )
