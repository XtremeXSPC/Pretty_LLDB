# ---------------------------------------------------------------------- #
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
# ---------------------------------------------------------------------- #

from .helpers import (
    Colors,
    get_child_member_by_names,
    get_value_summary,
    g_config,
)
from .extraction import extract_graph_structure
from .registry import register_summary, register_synthetic
import shlex

# ----- Formatter for Graphs (Synthetic Children) ----- #


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
        if not self.nodes_container:
            self.nodes_container = get_child_member_by_names(
                self.valobj, ["nodes", "m_nodes", "adj", "adjacency_list"]
            )

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

    def get_summary(self):
        """
        Returns a concise one-line text summary for the entire graph object.
        This summary is typically displayed next to the variable name.
        """
        num_nodes_member = get_child_member_by_names(
            self.valobj, ["num_nodes", "V", "node_count"]
        )
        num_edges_member = get_child_member_by_names(
            self.valobj, ["num_edges", "E", "edge_count"]
        )

        # Summaries in GUI panels should be colorless.
        summary = "Graph"
        if num_nodes_member:
            summary += f" | V = {num_nodes_member.GetValueAsUnsigned()}"
        if num_edges_member:
            summary += f" | E = {num_edges_member.GetValueAsUnsigned()}"
        return summary


# ----- Summary Formatter for Graph Nodes ----- #


@register_summary(r"^(Custom|My)?(Graph)?Node<.*>$")
def graph_node_summary_provider(valobj, internal_dict):
    """
    Provides a summary for a single Graph Node, showing its value and
    a list of its immediate neighbors.
    """
    node_value = get_child_member_by_names(valobj, ["value", "val", "data", "key"])
    neighbors = get_child_member_by_names(valobj, ["neighbors", "adj", "edges"])

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
                neighbor_val = get_child_member_by_names(
                    neighbor_node, ["value", "val", "data", "key"]
                )
                neighbor_summaries.append(get_value_summary(neighbor_val))

        if neighbor_summaries:
            summary += f" -> [{', '.join(neighbor_summaries)}]"
        if num_neighbors > max_neighbors:
            summary += " ..."

    return summary


# ----- Custom LLDB command 'export_graph' ----- #


def export_graph_command(debugger, command, result, internal_dict):
    """
    Implements the 'export_graph' command. It traverses a graph structure
    and writes a Graphviz .dot file to disk.
    Usage: (lldb) export_graph <variable_name> [output_file.dot]
    """
    args = shlex.split(command)
    if not args:
        result.SetError("Usage: export_graph <variable_name> [output_file.dot]")
        return

    var_name = args[0]
    output_filename = args[1] if len(args) > 1 else "graph.dot"

    frame = (
        debugger.GetSelectedTarget().GetProcess().GetSelectedThread().GetSelectedFrame()
    )
    if not frame.IsValid():
        result.SetError("Cannot execute: invalid execution context.")
        return

    graph_val = frame.FindVariable(var_name)
    if not graph_val or not graph_val.IsValid():
        result.SetError(f"Could not find a variable named '{var_name}'.")
        return

    nodes_container = get_child_member_by_names(
        graph_val, ["nodes", "m_nodes", "adj", "adjacency_list"]
    )
    if not nodes_container or not nodes_container.IsValid():
        result.AppendMessage("Graph is empty or nodes container not found.")
        return

    extracted_graph = extract_graph_structure(graph_val)
    if extracted_graph.is_empty:
        result.AppendMessage("Graph is empty or nodes container not found.")
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
