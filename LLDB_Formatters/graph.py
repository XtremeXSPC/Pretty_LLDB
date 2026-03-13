# ============================================================================ #
"""
Graph-formatting entry points for Pretty LLDB.

This module hosts the LLDB-facing graph providers used by the project:
synthetic children for graph containers, summaries for graph nodes, and the
command that exports extracted graphs to Graphviz format.

Author: XtremeXSPC
Version: 0.5.0.dev0
"""
# ============================================================================ #

from .command_helpers import (
    empty_structure_message,
    find_variable,
    resolve_command_arguments,
    unsupported_layout_message,
)
from .extraction import extract_graph_structure
from .helpers import (
    SUMMARY_TRUNCATION_MARKER,
    Colors,
    g_config,
    get_value_summary,
)
from .registry import register_summary, register_synthetic
from .renderers import render_graph_dot
from .schema_adapters import (
    get_resolved_child,
    resolve_graph_container_schema,
    resolve_graph_node_schema,
)
from .summary_contract import append_incomplete_marker, unsupported_layout_summary
from .synthetic_support import parse_synthetic_child_index
from .visualization_options import parse_graph_export_arguments


@register_synthetic(r"^(Custom|My)?Graph<.*>$")
class GraphProvider:
    """Expose the graph node container as synthetic LLDB children."""

    def __init__(self, valobj, internal_dict):
        self.valobj = valobj
        self.nodes_container = None
        self._loaded = False
        # update() is called on-demand to ensure it has the latest state.

    def update(self):
        """Resolve and cache the graph field that stores the node collection."""

        self.nodes_container = resolve_graph_container_schema(self.valobj).nodes_container
        self._loaded = True

    def _ensure_updated(self):
        """Populate the cached node container before synthetic access."""

        if not self._loaded:
            self.update()

    def num_children(self):
        """Return how many graph nodes LLDB should expose as children."""

        self._ensure_updated()
        if self.nodes_container and self.nodes_container.IsValid():
            return min(self.nodes_container.GetNumChildren(), g_config.synthetic_max_children)
        return 0

    def get_child_at_index(self, index):
        """Return the node child at `index`, or `None` when it is unavailable."""

        self._ensure_updated()
        if self.nodes_container and 0 <= index < self.num_children():
            return self.nodes_container.GetChildAtIndex(index)
        return None

    def get_child_index(self, name):
        """Translate an LLDB synthetic child label into its numeric index."""

        return parse_synthetic_child_index(name)

    def get_summary(self):
        """
        Build the container-level summary shown next to the graph variable.

        The summary reports the extracted vertex and edge counts when they can
        be determined and preserves incomplete-layout diagnostics consistently
        with the rest of the formatter family.
        """
        extraction = extract_graph_structure(self.valobj)
        diagnostics_suffix = (
            extraction.diagnostics.compact_summary() if g_config.diagnostics_enabled else ""
        )
        if extraction.error_message:
            return unsupported_layout_summary("graph", diagnostics_suffix)
        if extraction.is_empty:
            return f"Graph is empty{diagnostics_suffix}"

        summary = "Graph"
        if extraction.num_nodes is not None:
            summary += f" | V = {extraction.num_nodes}"
        if extraction.num_edges is not None:
            summary += f" | E = {extraction.num_edges}"
        summary = append_incomplete_marker(summary, extraction)
        summary += diagnostics_suffix
        return summary


@register_summary(r"^(Custom|My)?(Graph)?Node<.*>$")
def graph_node_summary_provider(valobj, internal_dict):
    """
    Summarize one graph node and preview its immediate neighbors.

    The provider resolves the node payload and neighbor container through the
    schema layer, then emits a bounded adjacency preview suitable for the LLDB
    variables pane.
    """
    schema = resolve_graph_node_schema(valobj)
    if not schema.value_field or not schema.neighbors_field:
        return unsupported_layout_summary("graph")

    node_value = get_resolved_child(valobj, schema.value_field)
    neighbors = get_resolved_child(valobj, schema.neighbors_field)

    val_str = get_value_summary(node_value)
    summary = f"{Colors.YELLOW}{val_str}{Colors.RESET}"

    if neighbors and neighbors.IsValid() and neighbors.MightHaveChildren():
        neighbor_summaries = []
        # Use max_neighbors from the global config object.
        max_neighbors = g_config.graph_max_neighbors
        num_neighbors = neighbors.GetNumChildren()

        for i in range(min(num_neighbors, max_neighbors)):
            neighbor_node = neighbors.GetChildAtIndex(i)
            if neighbor_node.GetType().IsPointerType():
                neighbor_node = neighbor_node.Dereference()

            if neighbor_node and neighbor_node.IsValid():
                neighbor_schema = resolve_graph_node_schema(neighbor_node)
                neighbor_val = get_resolved_child(neighbor_node, neighbor_schema.value_field)
                neighbor_summary = get_value_summary(neighbor_val)
                if neighbor_summary:
                    neighbor_summaries.append(neighbor_summary)

        if neighbor_summaries:
            summary += f" -> [{', '.join(neighbor_summaries)}]"
        if num_neighbors > max_neighbors:
            summary += f" {SUMMARY_TRUNCATION_MARKER}"

    return summary


def export_graph_command(debugger, command, result, internal_dict):
    """
    Export a supported graph container to a Graphviz `.dot` file.

    The command validates the structure, resolves the requested directed or
    undirected rendering mode, and writes the renderer output to disk.
    """
    args, frame = resolve_command_arguments(
        debugger,
        command,
        result,
        "export_graph",
        "<variable> [file.dot] [directed|undirected]",
        min_args=1,
    )
    if not args or not frame:
        return

    var_name = args[0]
    try:
        output_filename, directed = parse_graph_export_arguments(args)
    except ValueError as error:
        result.SetError(str(error))
        return

    graph_val = find_variable(frame, var_name, result)
    if not graph_val:
        return

    extracted_graph = extract_graph_structure(graph_val)
    if extracted_graph.error_message:
        result.SetError(unsupported_layout_message("graph"))
        return
    if extracted_graph.is_empty:
        result.AppendMessage(empty_structure_message("graph"))
        return

    dot_content = render_graph_dot(extracted_graph, directed=directed)
    mode_label = "directed" if directed else "undirected"

    try:
        with open(output_filename, "w") as f:
            f.write(dot_content)
        result.AppendMessage(f"Successfully exported {mode_label} graph to '{output_filename}'.")
        result.AppendMessage(f"Run: dot -Tpng {output_filename} -o graph.png")
    except IOError as e:
        result.SetError(f"Failed to write to file '{output_filename}': {e}")
