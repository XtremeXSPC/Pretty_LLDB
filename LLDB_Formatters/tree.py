# ============================================================================ #
"""
Tree-formatting entry points for Pretty LLDB.

This module gathers the LLDB-facing features for supported tree containers:
summary generation, synthetic children, console traversal commands, and
Graphviz export. Traversal semantics are delegated to the shared strategy and
extraction layers so the user-facing commands stay consistent.

Author: XtremeXSPC
Version: 0.5.0.dev0
"""
# ============================================================================ #

from .command_helpers import (
    empty_structure_message,
    find_variable,
    normalize_output_path,
    resolve_command_arguments,
    resolve_command_variable,
    unsupported_layout_message,
)
from .extraction import extract_tree_structure
from .helpers import (
    SUMMARY_CYCLE_MARKER,
    SUMMARY_TRUNCATION_MARKER,
    Colors,
    _safe_get_node_from_pointer,
    g_config,
    get_raw_pointer,
    get_value_summary,
    should_use_colors,
)
from .registry import register_summary, register_synthetic
from .renderers import render_tree_dot
from .schema_adapters import (
    get_resolved_child,
    get_tree_children,
    resolve_tree_container_schema,
    resolve_tree_node_schema,
)
from .strategies import InOrderTreeStrategy, PostOrderTreeStrategy, PreOrderTreeStrategy
from .summary_contract import append_incomplete_marker, unsupported_layout_summary
from .synthetic_support import create_synthetic_child, parse_synthetic_child_index
from .visualization_options import create_tree_traversal_strategy


def _collect_tree_nodes_by_address(root_ptr, wanted_addresses=None):
    """
    Traverse a tree and map node addresses to concrete LLDB node values.

    When `wanted_addresses` is provided, the traversal stops as soon as all
    requested addresses have been resolved. This keeps the synthetic provider
    from materializing more nodes than the selected traversal order requires.
    """

    nodes_by_address = {}
    visited_addrs = set()
    wanted = set(wanted_addresses) if wanted_addresses else None
    stack = [root_ptr]

    while stack:
        node_ptr = stack.pop()
        node_addr = get_raw_pointer(node_ptr)
        if node_addr == 0 or node_addr in visited_addrs:
            continue
        visited_addrs.add(node_addr)

        node = _safe_get_node_from_pointer(node_ptr)
        if not node or not node.IsValid():
            continue

        if wanted is None or node_addr in wanted:
            nodes_by_address[node_addr] = node
            if wanted is not None and len(nodes_by_address) >= len(wanted):
                break

        schema = resolve_tree_node_schema(node)
        children = get_tree_children(node, schema)
        for child_ptr in reversed(children):
            stack.append(child_ptr)

    return nodes_by_address


@register_synthetic(r"^(Custom|My)?(Binary)?Tree<.*>$")
class TreeProvider:
    """Expose tree nodes as ordered synthetic children in the variable view."""

    def __init__(self, valobj, internal_dict):
        self.valobj = valobj
        self.children = []
        self._loaded = False

    def update(self):
        """Rebuild the synthetic children using the configured traversal order."""

        self.children = []
        self._loaded = True

        root_ptr = resolve_tree_container_schema(self.valobj).root_ptr
        if not root_ptr or get_raw_pointer(root_ptr) == 0:
            return

        strategy, _ = create_tree_traversal_strategy(default_mode=g_config.tree_traversal_strategy)
        ordered_addresses = strategy.ordered_addresses(root_ptr, g_config.synthetic_max_children)
        nodes_by_address = _collect_tree_nodes_by_address(
            root_ptr,
            wanted_addresses=ordered_addresses,
        )

        for index, address in enumerate(ordered_addresses):
            node = nodes_by_address.get(address)
            child = create_synthetic_child(self.valobj, f"[{index}]", address, node)
            if child:
                self.children.append(child)

    def _ensure_updated(self):
        """Populate synthetic children lazily on the first LLDB access."""

        if not self._loaded:
            self.update()

    def num_children(self):
        """Return the number of synthetic tree nodes available for expansion."""

        self._ensure_updated()
        return len(self.children)

    def get_child_at_index(self, index):
        """Return the synthetic child at `index`, or `None` if unavailable."""

        self._ensure_updated()
        if 0 <= index < len(self.children):
            return self.children[index]
        return None

    def get_child_index(self, name):
        """Translate an LLDB synthetic child label into its numeric index."""

        return parse_synthetic_child_index(name)


@register_summary(r"^(Custom|My)?(Binary)?Tree<.*>$")
def tree_summary_provider(valobj, internal_dict):
    """
    Build the one-line summary for supported tree containers.

    The provider validates the layout, selects the active traversal strategy,
    formats the visited values, and appends any incomplete-state markers that
    should remain visible to the user.
    """
    use_colors = should_use_colors()

    C_GREEN = Colors.GREEN if use_colors else ""
    C_YELLOW = Colors.YELLOW if use_colors else ""
    C_CYAN = Colors.BOLD_CYAN if use_colors else ""
    C_RESET = Colors.RESET if use_colors else ""
    C_RED = Colors.RED if use_colors else ""
    diagnostics_suffix = ""

    extraction = extract_tree_structure(valobj)
    if g_config.diagnostics_enabled:
        diagnostics_suffix = extraction.diagnostics.compact_summary()
    if extraction.error_message:
        return unsupported_layout_summary("tree", diagnostics_suffix)
    if extraction.is_empty:
        return f"Tree is empty{diagnostics_suffix}"

    root_node_ptr = extraction.root_ptr
    if not root_node_ptr or get_raw_pointer(root_node_ptr) == 0:
        return f"Tree is empty{diagnostics_suffix}"

    strategy, strategy_name = create_tree_traversal_strategy(
        default_mode=g_config.tree_traversal_strategy
    )
    values, metadata = strategy.traverse(root_node_ptr, g_config.summary_max_items)

    colored_values = []
    for v in values:
        if v.startswith("["):
            colored_values.append(f"{C_RED}{v}{C_RESET}")
        else:
            colored_values.append(f"{C_YELLOW}{v}{C_RESET}")

    separator = f" {C_CYAN}->{C_RESET} "
    summary_str = separator.join(colored_values)

    if metadata.get("truncated", False):
        summary_str += f" {SUMMARY_TRUNCATION_MARKER}"

    size_str = ""
    if extraction.size is not None:
        size_str = f"{C_GREEN}size = {extraction.size}{C_RESET}, "

    summary = f"{size_str}[{summary_str}] ({strategy_name})"
    summary = append_incomplete_marker(
        summary,
        extraction,
        visible_warning_codes=("cycle_detected",),
    )
    return f"{summary}{diagnostics_suffix}"


def _recursive_preorder_print(node_ptr, prefix, is_last, result, visited_addrs=None, depth=0):
    """
    Render a tree branch as an ASCII diagram using pre-order traversal.

    The helper keeps track of visited addresses to avoid infinite recursion on
    malformed cyclic structures and enforces the configured maximum depth.
    """

    if visited_addrs is None:
        visited_addrs = set()

    if not node_ptr or get_raw_pointer(node_ptr) == 0:
        return
    if depth > g_config.tree_max_depth:
        result.AppendMessage(
            f"{prefix}{'└── ' if is_last else '├── '}{Colors.RED}[depth limit]{Colors.RESET}"
        )
        return

    node_addr = get_raw_pointer(node_ptr)
    if node_addr in visited_addrs:
        result.AppendMessage(
            f"{prefix}{'└── ' if is_last else '├── '}{Colors.RED}{SUMMARY_CYCLE_MARKER}{Colors.RESET}"
        )
        return
    visited_addrs.add(node_addr)

    node = _safe_get_node_from_pointer(node_ptr)
    if not node or not node.IsValid():
        return

    schema = resolve_tree_node_schema(node)
    value = get_resolved_child(node, schema.value_field)
    value_summary = get_value_summary(value)

    result.AppendMessage(
        f"{prefix}{'└── ' if is_last else '├── '}{Colors.YELLOW}{value_summary}{Colors.RESET}"
    )

    children = get_tree_children(node, schema)
    for i, child in enumerate(children):
        new_prefix = f"{prefix}{'    ' if is_last else '│   '}"
        _recursive_preorder_print(
            child,
            new_prefix,
            i == len(children) - 1,
            result,
            visited_addrs,
            depth + 1,
        )


def _pptree_command_dispatcher(debugger, command, result, internal_dict, order):
    """
    Dispatch the `pptree_*` commands through a shared validation pipeline.

    `order` selects the traversal mode. Pre-order produces a drawn tree,
    while the other modes render a linearized visitation sequence.
    """
    _, _, tree_val = resolve_command_variable(
        debugger,
        command,
        result,
        f"pptree_{order}",
    )
    if not tree_val:
        return

    extraction = extract_tree_structure(tree_val)
    if extraction.error_message:
        result.SetError(unsupported_layout_message("tree"))
        return
    if extraction.is_empty:
        result.AppendMessage(empty_structure_message("tree"))
        return

    root_node_ptr = extraction.root_ptr

    result.AppendMessage(
        f"{tree_val.GetTypeName()} at {tree_val.GetAddress()} ({order.capitalize()}):"
    )

    # For 'preorder', we draw the tree visually.
    if order == "preorder":
        _recursive_preorder_print(root_node_ptr, "", True, result)
        return

    # For other orders, we use the corresponding strategy to get a sequential list.
    if order == "inorder":
        strategy = InOrderTreeStrategy()
    elif order == "postorder":
        strategy = PostOrderTreeStrategy()
    else:
        result.SetError(f"Internal error: Unknown order '{order}'")
        return

    # Use a large number for max_items to get the full list for printing.
    values, metadata = strategy.traverse(root_node_ptr, max_items=g_config.summary_max_items)

    if not values:
        result.AppendMessage("[]")
        return

    summary_parts = [f"{Colors.YELLOW}{v}{Colors.RESET}" for v in values]
    summary = f"[{' -> '.join(summary_parts)}]"
    if metadata.get("truncated"):
        summary += f" {SUMMARY_TRUNCATION_MARKER}"
    result.AppendMessage(summary)


def pptree_preorder_command(debugger, command, result, internal_dict):
    """Render the selected tree as an ASCII diagram in pre-order."""

    _pptree_command_dispatcher(debugger, command, result, internal_dict, "preorder")


def pptree_inorder_command(debugger, command, result, internal_dict):
    """Print the selected tree values in in-order traversal order."""

    _pptree_command_dispatcher(debugger, command, result, internal_dict, "inorder")


def pptree_postorder_command(debugger, command, result, internal_dict):
    """Print the selected tree values in post-order traversal order."""

    _pptree_command_dispatcher(debugger, command, result, internal_dict, "postorder")


def export_tree_command(debugger, command, result, internal_dict):
    """
    Export a supported tree container to a Graphviz `.dot` file.

    When the caller requests a known traversal order, the exported graph is
    annotated with that visit sequence; otherwise the command falls back to the
    default pre-order rendering without traversal annotations.
    """
    args, frame = resolve_command_arguments(
        debugger,
        command,
        result,
        "export_tree",
        "<variable> [file.dot] [order]",
        min_args=1,
    )
    if not args or not frame:
        return

    var_name = args[0]
    output_filename = args[1] if len(args) > 1 else "tree.dot"
    traversal_order = args[2].lower() if len(args) > 2 else None

    try:
        output_path = normalize_output_path(output_filename)
    except ValueError as error:
        result.SetError(str(error))
        return

    tree_val = find_variable(frame, var_name, result)
    if not tree_val:
        return

    extraction = extract_tree_structure(tree_val)
    if extraction.error_message:
        result.SetError(unsupported_layout_message("tree"))
        return
    if extraction.is_empty:
        result.AppendMessage(empty_structure_message("tree"))
        return

    # Define available strategies.
    strategy_map = {
        "preorder": PreOrderTreeStrategy(),
        "inorder": InOrderTreeStrategy(),
        "postorder": PostOrderTreeStrategy(),
    }

    # Determine the strategy and whether to annotate the graph.
    # If an invalid order is given, we default to preorder without annotation.
    if traversal_order in strategy_map:
        strategy = strategy_map[traversal_order]
        should_annotate = True
    else:
        strategy = PreOrderTreeStrategy()
        should_annotate = False

    traversal_addresses = None
    root_node_ptr = extraction.root_ptr
    if should_annotate:
        traversal_addresses = strategy.ordered_addresses(root_node_ptr)

    dot_content = render_tree_dot(extraction, traversal_order=traversal_addresses)

    try:
        with open(output_path, "w") as f:
            f.write(dot_content)
        result.AppendMessage(f"Successfully exported tree to '{output_path}'.")
        result.AppendMessage(
            f"To generate the image, run: dot -Tpng -Gdpi=300 {output_path} -o tree.png"
        )
    except IOError as e:
        result.SetError(f"Failed to write to file '{output_path}': {e}")
