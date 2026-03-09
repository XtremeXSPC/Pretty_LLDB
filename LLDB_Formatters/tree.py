# ---------------------------------------------------------------------- #
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
# ---------------------------------------------------------------------- #

import shlex

from .extraction import extract_tree_structure
from .helpers import (
    Colors,
    _get_node_children,
    _safe_get_node_from_pointer,
    g_config,
    get_child_member_by_names,
    get_raw_pointer,
    get_value_summary,
    should_use_colors,
)
from .registry import register_summary
from .strategies import (
    InOrderTreeStrategy,
    PostOrderTreeStrategy,
    PreOrderTreeStrategy,
)

# ------------------ Summary Provider for Tree Root ------------------- #


@register_summary(r"^(Custom|My)?(Binary)?Tree<.*>$")
def tree_summary_provider(valobj, internal_dict):
    """
    This is the main summary provider for Tree structures. It uses the
    Strategy pattern to select a traversal method based on the global
    configuration ('g_config.tree_traversal_strategy').
    """
    use_colors = should_use_colors()

    # Color Definitions
    C_GREEN = Colors.GREEN if use_colors else ""
    C_YELLOW = Colors.YELLOW if use_colors else ""
    C_CYAN = Colors.BOLD_CYAN if use_colors else ""
    C_RESET = Colors.RESET if use_colors else ""
    C_RED = Colors.RED if use_colors else ""
    diagnostics_suffix = ""

    extraction = None
    if g_config.diagnostics_enabled:
        extraction = extract_tree_structure(valobj)
        diagnostics_suffix = extraction.diagnostics.compact_summary()
        if extraction.is_empty or extraction.error_message:
            return f"Tree is empty{diagnostics_suffix}"

    # Get Tree Root
    root_node_ptr = get_child_member_by_names(valobj, ["root", "m_root", "_root"])
    if not root_node_ptr or get_raw_pointer(root_node_ptr) == 0:
        return f"Tree is empty{diagnostics_suffix}"

    # Strategy Selection
    strategy_name = g_config.tree_traversal_strategy
    if strategy_name == "inorder":
        strategy = InOrderTreeStrategy()
    elif strategy_name == "postorder":
        strategy = PostOrderTreeStrategy()
    else:  # Default to pre-order
        strategy = PreOrderTreeStrategy()

    # Traversal
    values, metadata = strategy.traverse(root_node_ptr, g_config.summary_max_items)

    # Formatting
    colored_values = []
    for v in values:
        if v.startswith("["):  # Cycle
            colored_values.append(f"{C_RED}{v}{C_RESET}")
        else:
            colored_values.append(f"{C_YELLOW}{v}{C_RESET}")

    separator = f" {C_CYAN}->{C_RESET} "
    summary_str = separator.join(colored_values)

    if metadata.get("truncated", False):
        summary_str += " ..."

    size_member = get_child_member_by_names(valobj, ["size", "m_size", "count"])
    size_str = ""
    if extraction and extraction.size is not None:
        size_str = f"{C_GREEN}size = {extraction.size}{C_RESET}, "
    elif size_member:
        size_str = f"{C_GREEN}size = {size_member.GetValueAsUnsigned()}{C_RESET}, "

    return f"{size_str}[{summary_str}] ({strategy_name}){diagnostics_suffix}"


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
            f"{prefix}{'└── ' if is_last else '├── '}{Colors.RED}[CYCLE]{Colors.RESET}"
        )
        return
    visited_addrs.add(node_addr)

    node = _safe_get_node_from_pointer(node_ptr)
    if not node or not node.IsValid():
        return

    value = get_child_member_by_names(node, ["value", "val", "data", "key"])
    value_summary = get_value_summary(value)

    result.AppendMessage(
        f"{prefix}{'└── ' if is_last else '├── '}{Colors.YELLOW}{value_summary}{Colors.RESET}"
    )

    children = _get_node_children(node)
    for i, child in enumerate(children):
        new_prefix = f"{prefix}{'    ' if is_last else '│   '}"
        _recursive_preorder_print(child, new_prefix, i == len(children) - 1, result, visited_addrs)


# ------------ Central dispatcher for all 'pptree' commands ------------ #


def _pptree_command_dispatcher(debugger, command, result, internal_dict, order):
    """
    A single function to handle the logic for all traversal commands.
    'order' can be 'preorder', 'inorder', or 'postorder'.
    """
    args = shlex.split(command)
    if not args:
        result.SetError(f"Usage: pptree_{order} <variable_name>")
        return

    frame = debugger.GetSelectedTarget().GetProcess().GetSelectedThread().GetSelectedFrame()
    if not frame.IsValid():
        result.SetError("Cannot execute command: invalid execution context.")
        return

    tree_val = frame.FindVariable(args[0])
    if not tree_val or not tree_val.IsValid():
        result.SetError(f"Could not find variable '{args[0]}'.")
        return

    root_node_ptr = get_child_member_by_names(tree_val, ["root", "m_root", "_root"])
    if not root_node_ptr or get_raw_pointer(root_node_ptr) == 0:
        result.AppendMessage("Tree is empty.")
        return

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


# --------- LLDB Command to Export Tree as Graphviz .dot File ---------- #


def export_tree_command(debugger, command, result, internal_dict):
    """
    Implements the 'export_tree' command. Traverses a tree and writes
    a Graphviz .dot file. Now uses a unified strategy-based approach.
    """
    args = shlex.split(command)
    if not args:
        result.SetError("Usage: export_tree <variable> [file.dot] [order]")
        return

    var_name = args[0]
    output_filename = args[1] if len(args) > 1 else "tree.dot"
    traversal_order = args[2].lower() if len(args) > 2 else None

    frame = debugger.GetSelectedTarget().GetProcess().GetSelectedThread().GetSelectedFrame()
    if not frame.IsValid():
        result.SetError("Cannot execute: invalid execution context.")
        return

    tree_val = frame.FindVariable(var_name)
    if not tree_val or not tree_val.IsValid():
        result.SetError(f"Could not find variable '{var_name}'.")
        return

    root_node_ptr = get_child_member_by_names(tree_val, ["root", "m_root", "_root"])
    if not root_node_ptr or get_raw_pointer(root_node_ptr) == 0:
        result.AppendMessage("Tree is empty.")
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
