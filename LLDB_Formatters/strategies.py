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
        values, metadata = self.traverse(root_ptr, max_items=1000)
        dot_lines = ["digraph G {", '  rankdir="LR";', "  node [shape=box];"]
        for i, value in enumerate(values):
            dot_lines.append(f'  Node_{i} [label="{value}"];')
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
class TreeTraversalStrategy(TraversalStrategy):
    """
    Provide shared tree-specific traversal helpers for concrete tree strategies.

    In addition to the base traversal contract, this class knows how to
    generate DOT-friendly parent-child output and how to expose ordered node
    addresses for synthetic providers and traversal annotations.
    """

    def traverse_for_dot(
        self, root_ptr: "lldb.SBValue", annotate: bool = False
    ) -> Tuple[List[str], Dict[str, Any]]:
        """
        Generate DOT body lines that preserve the real tree structure.
        """
        dot_lines = []
        visited_addrs = set()
        traversal_map = {}

        if annotate:
            # To annotate, we need to perform the specific traversal (pre, in, post)
            # and store the order of each node's address.
            ordered_addrs = self._get_ordered_addresses(root_ptr)
            traversal_map = {addr: i for i, addr in enumerate(ordered_addrs, 1)}

        self._build_dot_recursive(root_ptr, dot_lines, visited_addrs, traversal_map)

        # The first two lines are added by the caller, so we just return the body.
        return dot_lines, {}

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
        raise NotImplementedError

    def _build_dot_recursive(
        self,
        node_ptr: "lldb.SBValue",
        dot_lines: List[str],
        visited_addrs: set,
        traversal_map: Dict[int, int],
    ):
        """Append DOT nodes and edges for one tree subtree."""

        node_addr = get_raw_pointer(node_ptr)
        if node_addr == 0 or node_addr in visited_addrs:
            return
        visited_addrs.add(node_addr)

        node_struct = _safe_get_node_from_pointer(node_ptr)
        if not node_struct or not node_struct.IsValid():
            return

        schema = resolve_tree_node_schema(node_struct)
        value = get_resolved_child(node_struct, schema.value_field)
        val_summary = get_value_summary(value).replace('"', '"')

        label = val_summary
        if traversal_map and node_addr in traversal_map:
            order_index = traversal_map[node_addr]
            label = f'"{order_index}: {val_summary}"'
        else:
            label = f'"{val_summary}"'

        dot_lines.append(f"  Node_{node_addr} [label={label}];")

        children = get_tree_children(node_struct, schema)
        for child_ptr in children:
            child_addr = get_raw_pointer(child_ptr)
            if child_addr != 0:
                dot_lines.append(f"  Node_{node_addr} -> Node_{child_addr};")
                self._build_dot_recursive(child_ptr, dot_lines, visited_addrs, traversal_map)


# ----------------- Concrete Tree Traversal Strategies ------------------ #
class PreOrderTreeStrategy(TreeTraversalStrategy):
    """Traverse trees in pre-order, visiting the root before its children."""

    def traverse(
        self, root_ptr: "lldb.SBValue", max_items: int
    ) -> Tuple[List[str], Dict[str, Any]]:
        """Traverse a tree in pre-order with cycle and depth safeguards."""

        values: List[str] = []
        visited_addrs = set()
        max_depth = g_config.tree_max_depth
        depth_limited = False

        def _recursive_traverse(node_ptr, depth):
            nonlocal depth_limited
            if not node_ptr or get_raw_pointer(node_ptr) == 0 or len(values) >= max_items:
                return
            if depth > max_depth:
                depth_limited = True
                return

            node_addr = get_raw_pointer(node_ptr)
            if node_addr in visited_addrs:
                values.append(SUMMARY_CYCLE_MARKER)
                return
            visited_addrs.add(node_addr)

            node = _safe_get_node_from_pointer(node_ptr)
            if not node or not node.IsValid():
                return

            # 1. Visit Root
            schema = resolve_tree_node_schema(node)
            value = get_resolved_child(node, schema.value_field)
            values.append(get_value_summary(value))

            # 2. Recurse on children
            if len(values) < max_items:
                children = get_tree_children(node, schema)
                for child in children:
                    _recursive_traverse(child, depth + 1)

        _recursive_traverse(root_ptr, 0)
        metadata: Dict[str, Any] = {
            "truncated": len(values) >= max_items or depth_limited,
            "depth_limited": depth_limited,
        }
        return values, metadata

    def _get_ordered_addresses(
        self, root_ptr: "lldb.SBValue", max_items: Optional[int] = None
    ) -> List[int]:
        """Return visited node addresses in pre-order."""

        addresses: List[int] = []
        visited_addrs = set()
        max_depth = g_config.tree_max_depth

        def _recursive_traverse_addr(node_ptr, depth):
            if not node_ptr or get_raw_pointer(node_ptr) == 0:
                return
            if max_items is not None and len(addresses) >= max_items:
                return
            if depth > max_depth:
                return

            node_addr = get_raw_pointer(node_ptr)
            if node_addr in visited_addrs:
                return
            visited_addrs.add(node_addr)

            # 1. Visit Root (add address)
            addresses.append(node_addr)

            # 2. Recurse on children
            node = _safe_get_node_from_pointer(node_ptr)
            if node and node.IsValid():
                children = get_tree_children(node, resolve_tree_node_schema(node))
                for child in children:
                    _recursive_traverse_addr(child, depth + 1)

        _recursive_traverse_addr(root_ptr, 0)
        return addresses


class InOrderTreeStrategy(TreeTraversalStrategy):
    """
    Traverse trees in in-order.

    Binary trees use the classic `(left, root, right)` rule, while n-ary trees
    use the formatter's generalized `(first child, root, remaining children)`
    convention.
    """

    def traverse(
        self, root_ptr: "lldb.SBValue", max_items: int
    ) -> Tuple[List[str], Dict[str, Any]]:
        """Traverse a tree in in-order with cycle and depth safeguards."""

        values: List[str] = []
        visited_addrs = set()
        max_depth = g_config.tree_max_depth
        depth_limited = False

        def _recursive_traverse(node_ptr, depth):
            nonlocal depth_limited
            if not node_ptr or get_raw_pointer(node_ptr) == 0 or len(values) >= max_items:
                return
            if depth > max_depth:
                depth_limited = True
                return

            node_addr = get_raw_pointer(node_ptr)
            if node_addr in visited_addrs:
                values.append(SUMMARY_CYCLE_MARKER)
                return
            visited_addrs.add(node_addr)

            node = _safe_get_node_from_pointer(node_ptr)
            if not node or not node.IsValid():
                return

            schema = resolve_tree_node_schema(node)
            value = get_resolved_child(node, schema.value_field)
            left = get_resolved_child(node, schema.left_field)
            right = get_resolved_child(node, schema.right_field)
            is_binary = schema.child_mode == "binary"

            if is_binary:
                # 1. Recurse on Left Subtree
                if left and get_raw_pointer(left) != 0:
                    _recursive_traverse(left, depth + 1)

                if len(values) >= max_items:
                    return

                # 2. Visit Root
                values.append(get_value_summary(value))

                if len(values) >= max_items:
                    return

                # 3. Recurse on Right Subtree
                if right and get_raw_pointer(right) != 0:
                    _recursive_traverse(right, depth + 1)
            else:
                # Fallback to the n-ary tree generalization:
                # (First Child, Root, Other Children)
                children = get_tree_children(node, schema)

                # 1. Recurse on first child's subtree
                if children:
                    _recursive_traverse(children[0], depth + 1)

                if len(values) >= max_items:
                    return

                # 2. Visit Root
                values.append(get_value_summary(value))

                if len(values) >= max_items:
                    return

                # 3. Recurse on the rest of the children's subtrees
                for i in range(1, len(children)):
                    _recursive_traverse(children[i], depth + 1)

        _recursive_traverse(root_ptr, 0)
        metadata: Dict[str, Any] = {
            "truncated": len(values) >= max_items or depth_limited,
            "depth_limited": depth_limited,
        }
        return values, metadata

    def _get_ordered_addresses(
        self, root_ptr: "lldb.SBValue", max_items: Optional[int] = None
    ) -> List[int]:
        """Return visited node addresses in in-order."""

        addresses: List[int] = []
        visited_addrs = set()
        max_depth = g_config.tree_max_depth

        def _recursive_traverse_addr(node_ptr, depth):
            if not node_ptr or get_raw_pointer(node_ptr) == 0:
                return
            if max_items is not None and len(addresses) >= max_items:
                return
            if depth > max_depth:
                return

            node_addr = get_raw_pointer(node_ptr)
            if node_addr in visited_addrs:
                return
            visited_addrs.add(node_addr)

            node = _safe_get_node_from_pointer(node_ptr)
            if not node or not node.IsValid():
                return

            schema = resolve_tree_node_schema(node)
            left = get_resolved_child(node, schema.left_field)
            right = get_resolved_child(node, schema.right_field)
            is_binary = schema.child_mode == "binary"

            if is_binary:
                if left and get_raw_pointer(left) != 0:
                    _recursive_traverse_addr(left, depth + 1)
                if max_items is not None and len(addresses) >= max_items:
                    return
                addresses.append(node_addr)
                if max_items is not None and len(addresses) >= max_items:
                    return
                if right and get_raw_pointer(right) != 0:
                    _recursive_traverse_addr(right, depth + 1)
            else:
                children = get_tree_children(node, schema)
                if children:
                    _recursive_traverse_addr(children[0], depth + 1)
                if max_items is not None and len(addresses) >= max_items:
                    return
                addresses.append(node_addr)
                if max_items is not None and len(addresses) >= max_items:
                    return
                for i in range(1, len(children)):
                    _recursive_traverse_addr(children[i], depth + 1)

        _recursive_traverse_addr(root_ptr, 0)
        return addresses


class PostOrderTreeStrategy(TreeTraversalStrategy):
    """Traverse trees in post-order, visiting children before the root."""

    def traverse(
        self, root_ptr: "lldb.SBValue", max_items: int
    ) -> Tuple[List[str], Dict[str, Any]]:
        """Traverse a tree in post-order with cycle and depth safeguards."""

        values: List[str] = []
        visited_addrs = set()
        max_depth = g_config.tree_max_depth
        depth_limited = False

        def _recursive_traverse(node_ptr, depth):
            nonlocal depth_limited
            if not node_ptr or get_raw_pointer(node_ptr) == 0 or len(values) >= max_items:
                return
            if depth > max_depth:
                depth_limited = True
                return

            node_addr = get_raw_pointer(node_ptr)
            if node_addr in visited_addrs:
                # In post-order, a cycle can fill the list, so we check before appending.
                if len(values) < max_items:
                    values.append(SUMMARY_CYCLE_MARKER)
                return
            visited_addrs.add(node_addr)

            node = _safe_get_node_from_pointer(node_ptr)
            if not node or not node.IsValid():
                return

            # 1. Recurse on all children
            schema = resolve_tree_node_schema(node)
            children = get_tree_children(node, schema)
            for child in children:
                _recursive_traverse(child, depth + 1)

            if len(values) >= max_items:
                return

            # 2. Visit Root
            value = get_resolved_child(node, schema.value_field)
            values.append(get_value_summary(value))

        _recursive_traverse(root_ptr, 0)
        metadata: Dict[str, Any] = {
            "truncated": len(values) >= max_items or depth_limited,
            "depth_limited": depth_limited,
        }
        return values, metadata

    def _get_ordered_addresses(
        self, root_ptr: "lldb.SBValue", max_items: Optional[int] = None
    ) -> List[int]:
        """Return visited node addresses in post-order."""

        addresses: List[int] = []
        visited_addrs = set()
        max_depth = g_config.tree_max_depth

        def _recursive_traverse_addr(node_ptr, depth):
            if not node_ptr or get_raw_pointer(node_ptr) == 0:
                return
            if max_items is not None and len(addresses) >= max_items:
                return
            if depth > max_depth:
                return

            node_addr = get_raw_pointer(node_ptr)
            if node_addr in visited_addrs:
                return
            visited_addrs.add(node_addr)

            node = _safe_get_node_from_pointer(node_ptr)
            if node and node.IsValid():
                children = get_tree_children(node, resolve_tree_node_schema(node))
                for child in children:
                    _recursive_traverse_addr(child, depth + 1)
                    if max_items is not None and len(addresses) >= max_items:
                        return

            if max_items is not None and len(addresses) >= max_items:
                return
            addresses.append(node_addr)

        _recursive_traverse_addr(root_ptr, 0)
        return addresses
