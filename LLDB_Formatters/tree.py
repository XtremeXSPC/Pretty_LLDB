# ----------------------------------------------------------------------- #
# FILE: tree.py
#
# DESCRIPTION:
# This module contains all logic for formatting and visualizing tree
# data structures.
#
# It has been refactored to use the Strategy pattern, where the traversal
# logic (pre-order, in-order, etc.) is encapsulated in strategy classes.
# This allows for runtime selection of the traversal method and cleans up
# the code for commands and summaries.
#
# Features include:
#   - A summary provider that dynamically chooses a traversal strategy.
#   - A suite of 'pptree' commands for console visualization.
#   - An 'export_tree' command to generate Graphviz .dot files.
# ----------------------------------------------------------------------- #

from .command_helpers import (
    empty_structure_message,
    find_variable,
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
from .schema_adapters import (
    get_resolved_child,
    get_tree_children,
    resolve_tree_container_schema,
    resolve_tree_node_schema,
)
from .strategies import InOrderTreeStrategy, PostOrderTreeStrategy, PreOrderTreeStrategy
from .summary_contract import append_incomplete_marker, unsupported_layout_summary
from .synthetic_support import create_synthetic_child, parse_synthetic_child_index


def _get_tree_strategy(strategy_name=None):
    resolved_name = strategy_name or g_config.tree_traversal_strategy
    if resolved_name == "inorder":
        return InOrderTreeStrategy(), "inorder"
    if resolved_name == "postorder":
        return PostOrderTreeStrategy(), "postorder"
    return PreOrderTreeStrategy(), "preorder"


def _collect_tree_nodes_by_address(root_ptr):
    nodes_by_address = {}
    visited_addrs = set()

    def _visit(node_ptr):
        node_addr = get_raw_pointer(node_ptr)
        if node_addr == 0 or node_addr in visited_addrs:
            return
        visited_addrs.add(node_addr)

        node = _safe_get_node_from_pointer(node_ptr)
        if not node or not node.IsValid():
            return

        nodes_by_address[node_addr] = node
        schema = resolve_tree_node_schema(node)
        for child_ptr in get_tree_children(node, schema):
            _visit(child_ptr)

    _visit(root_ptr)
    return nodes_by_address


@register_synthetic(r"^(Custom|My)?(Binary)?Tree<.*>$")
class TreeProvider:
    def __init__(self, valobj, internal_dict):
        self.valobj = valobj
        self.children = []

    def update(self):
        self.children = []

        root_ptr = resolve_tree_container_schema(self.valobj).root_ptr
        if not root_ptr or get_raw_pointer(root_ptr) == 0:
            return

        strategy, _ = _get_tree_strategy()
        ordered_addresses = strategy.ordered_addresses(root_ptr, g_config.synthetic_max_children)
        nodes_by_address = _collect_tree_nodes_by_address(root_ptr)

        for index, address in enumerate(ordered_addresses):
            node = nodes_by_address.get(address)
            child = create_synthetic_child(self.valobj, f"[{index}]", address, node)
            if child:
                self.children.append(child)

    def num_children(self):
        self.update()
        return len(self.children)

    def get_child_at_index(self, index):
        self.update()
        if 0 <= index < len(self.children):
            return self.children[index]
        return None

    def get_child_index(self, name):
        return parse_synthetic_child_index(name)


# ------------------- Summary Provider for Tree Root ------------------- #


@register_summary(r"^(Custom|My)?(Binary)?Tree<.*>$")
def tree_summary_provider(valobj, internal_dict):
    """
    This is the main summary provider for Tree structures. It uses the
    Strategy pattern to select a traversal method based on the global
    configuration ('g_config.tree_traversal_strategy').
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

    container_schema = resolve_tree_container_schema(valobj)
    root_node_ptr = container_schema.root_ptr
    if not root_node_ptr or get_raw_pointer(root_node_ptr) == 0:
        return f"Tree is empty{diagnostics_suffix}"

    strategy, strategy_name = _get_tree_strategy()
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
    if extraction and extraction.size is not None:
        size_str = f"{C_GREEN}size = {extraction.size}{C_RESET}, "
    elif container_schema.size_member:
        size_str = f"{C_GREEN}size = {container_schema.size_member.GetValueAsUnsigned()}{C_RESET}, "

    summary = f"{size_str}[{summary_str}] ({strategy_name})"
    summary = append_incomplete_marker(
        summary,
        extraction,
        visible_warning_codes=("cycle_detected",),
    )
    return f"{summary}{diagnostics_suffix}"


# ------- Helper to recursively "draw" the tree for 'pptree' commands ------- #


def _recursive_preorder_print(node_ptr, prefix, is_last, result, visited_addrs=None):
    """Helper function to recursively "draw" the tree in Pre-Order."""
    if visited_addrs is None:
        visited_addrs = set()

    if not node_ptr or get_raw_pointer(node_ptr) == 0:
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
        _recursive_preorder_print(child, new_prefix, i == len(children) - 1, result, visited_addrs)


# ------------ Central dispatcher for all 'pptree' commands ------------- #


def _pptree_command_dispatcher(debugger, command, result, internal_dict, order):
    """
    A single function to handle the logic for all traversal commands.
    'order' can be 'preorder', 'inorder', or 'postorder'.
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

    root_node_ptr = resolve_tree_container_schema(tree_val).root_ptr

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
    values, _ = strategy.traverse(root_node_ptr, max_items=1000)

    if not values:
        result.AppendMessage("[]")
        return

    summary_parts = [f"{Colors.YELLOW}{v}{Colors.RESET}" for v in values]
    result.AppendMessage(f"[{' -> '.join(summary_parts)}]")


# ------------------- User-facing command functions -------------------- #


def pptree_preorder_command(debugger, command, result, internal_dict):
    """Implements the 'pptree_preorder' command."""
    _pptree_command_dispatcher(debugger, command, result, internal_dict, "preorder")


def pptree_inorder_command(debugger, command, result, internal_dict):
    """Implements the 'pptree_inorder' command."""
    _pptree_command_dispatcher(debugger, command, result, internal_dict, "inorder")


def pptree_postorder_command(debugger, command, result, internal_dict):
    """Implements the 'pptree_postorder' command."""
    _pptree_command_dispatcher(debugger, command, result, internal_dict, "postorder")


# ---------- LLDB Command to Export Tree as Graphviz .dot File ---------- #


def export_tree_command(debugger, command, result, internal_dict):
    """
    Implements the 'export_tree' command. Traverses a tree and writes
    a Graphviz .dot file. Now uses a unified strategy-based approach.
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

    root_node_ptr = resolve_tree_container_schema(tree_val).root_ptr

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

    # Generate the main body of the .dot file using the selected strategy.
    dot_body, _ = strategy.traverse_for_dot(root_node_ptr, annotate=should_annotate)

    # Assemble the full .dot file content.
    dot_lines = [
        "digraph Tree {",
        '  graph [rankdir="TD"];',
        "  node [shape=circle, style=filled, fillcolor=lightblue];",
        "  edge [arrowhead=vee];",
        *dot_body,
        "}",
    ]
    dot_content = "\n".join(dot_lines)

    try:
        with open(output_filename, "w") as f:
            f.write(dot_content)
        result.AppendMessage(f"Successfully exported tree to '{output_filename}'.")
        result.AppendMessage(
            f"To generate the image, run: dot -Tpng -Gdpi=300 {output_filename} -o tree.png"
        )
    except IOError as e:
        result.SetError(f"Failed to write to file '{output_filename}': {e}")
