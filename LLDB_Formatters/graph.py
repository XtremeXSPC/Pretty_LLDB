# ----------------------------------------------------------------------- #
# FILE: graph.py
#
# DESCRIPTION:
# This module provides data formatters and commands for visualizing
# graph data structures.
#
# It contains:
#   - 'GraphProvider': A synthetic children provider, registered with a
#     decorator, that displays a graph's nodes as children.
#   - 'GraphNodeSummary': A summary provider for individual graph nodes.
#   - 'export_graph_command': A custom LLDB command to export a graph
#     to a Graphviz .dot file.
# ----------------------------------------------------------------------- #

from .command_helpers import (
    empty_structure_message,
    find_variable,
    resolve_command_arguments,
    unsupported_layout_message,
)
from .extraction import extract_graph_structure
from .helpers import (
    Colors,
    SUMMARY_TRUNCATION_MARKER,
    g_config,
    get_value_summary,
)
from .registry import register_summary, register_synthetic
from .schema_adapters import (
    get_resolved_child,
    resolve_graph_container_schema,
    resolve_graph_node_schema,
)
from .summary_contract import append_incomplete_marker, unsupported_layout_summary
from .synthetic_support import parse_synthetic_child_index

# -------------- Formatter for Graphs (Synthetic Children) -------------- #


@register_synthetic(r"^(Custom|My)?Graph<.*>$")
class GraphProvider:
    """
    Provides synthetic children for a Graph structure, allowing the user
    to expand the graph object in the debugger's variable view to see
    its nodes.
    """

    def __init__(self, valobj, internal_dict):
        self.valobj = valobj
        self.nodes_container = None
        # update() is called on-demand to ensure it has the latest state.

    def update(self):
        """Finds the container of nodes within the graph object."""
        self.nodes_container = resolve_graph_container_schema(self.valobj).nodes_container

    def num_children(self):
        """Returns the number of nodes to display as children."""
        self.update()
        if self.nodes_container and self.nodes_container.IsValid():
            return self.nodes_container.GetNumChildren()
        return 0

    def get_child_at_index(self, index):
        """Returns the i-th node from the nodes container."""
        self.update()
        if self.nodes_container:
            return self.nodes_container.GetChildAtIndex(index)
        return None

    def get_child_index(self, name):
        return parse_synthetic_child_index(name)

    def get_summary(self):
        """
        Returns a concise one-line text summary for the entire graph object.
        This summary is typically displayed next to the variable name.
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


# ------------------ Summary Formatter for Graph Nodes ------------------ #


@register_summary(r"^(Custom|My)?(Graph)?Node<.*>$")
def graph_node_summary_provider(valobj, internal_dict):
    """
    Provides a summary for a single Graph Node, showing its value and
    a list of its immediate neighbors.
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


# ----------------- Custom LLDB command 'export_graph' ------------------ #


def export_graph_command(debugger, command, result, internal_dict):
    """
    Implements the 'export_graph' command. It traverses a graph structure
    and writes a Graphviz .dot file to disk.
    Usage: (lldb) export_graph <variable_name> [output_file.dot]
    """
    args, frame = resolve_command_arguments(
        debugger,
        command,
        result,
        "export_graph",
        "<variable> [file.dot]",
        min_args=1,
    )
    if not args or not frame:
        return

    var_name = args[0]
    output_filename = args[1] if len(args) > 1 else "graph.dot"

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

    dot_lines = ["digraph G {", '  rankdir="LR";', "  node [shape=circle];"]
    for node in extracted_graph.nodes:
        val_summary = node.value.replace('"', '\\"')
        dot_lines.append(f'  Node_{node.address} [label="{val_summary}"];')

    for edge in extracted_graph.edges:
        dot_lines.append(f"  Node_{edge.source} -> Node_{edge.target};")
    dot_lines.append("}")

    try:
        with open(output_filename, "w") as f:
            f.write("\n".join(dot_lines))
        result.AppendMessage(f"Successfully exported graph to '{output_filename}'.")
        result.AppendMessage(f"Run: dot -Tpng {output_filename} -o graph.png")
    except IOError as e:
        result.SetError(f"Failed to write to file '{output_filename}': {e}")
