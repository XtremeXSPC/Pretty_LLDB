# ============================================================================ #
"""
Option parsing helpers for Pretty LLDB visualization commands.

This module centralizes the small parsing rules used by tree and graph export
commands so that command handlers can share one consistent interpretation of
render modes, traversal names, and default behaviors.

Author: XtremeXSPC
Version: 0.5.0.dev0
"""
# ============================================================================ #

from .strategies import InOrderTreeStrategy, PostOrderTreeStrategy, PreOrderTreeStrategy

GRAPH_RENDER_MODES = {
    "directed": True,
    "undirected": False,
}

TREE_TRAVERSAL_MODES = {
    "preorder": PreOrderTreeStrategy,
    "inorder": InOrderTreeStrategy,
    "postorder": PostOrderTreeStrategy,
}


def parse_graph_render_mode(mode_token):
    """Parse the graph render mode token and return the corresponding boolean flag."""

    if mode_token is None:
        return True

    normalized = mode_token.lower()
    if normalized not in GRAPH_RENDER_MODES:
        valid_modes = ", ".join(GRAPH_RENDER_MODES)
        raise ValueError(f"Invalid graph mode '{mode_token}'. Valid options are: {valid_modes}.")
    return GRAPH_RENDER_MODES[normalized]


def parse_graph_export_arguments(args):
    """Parse `export_graph` arguments into an output filename and render mode."""

    output_filename = "graph.dot"
    mode_token = None

    if len(args) >= 2:
        second = args[1]
        if second.lower() in GRAPH_RENDER_MODES:
            mode_token = second
        else:
            output_filename = second

    if len(args) >= 3:
        mode_token = args[2]

    directed = parse_graph_render_mode(mode_token)
    return output_filename, directed


def create_tree_traversal_strategy(mode_token=None, default_mode="preorder"):
    """Create the requested tree traversal strategy and return it with its name."""

    normalized = default_mode
    if mode_token is not None:
        normalized = mode_token.lower()

    if normalized not in TREE_TRAVERSAL_MODES:
        valid_modes = ", ".join(TREE_TRAVERSAL_MODES)
        raise ValueError(
            f"Invalid tree traversal '{mode_token}'. Valid options are: {valid_modes}."
        )

    return TREE_TRAVERSAL_MODES[normalized](), normalized
