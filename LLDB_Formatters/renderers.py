# ============================================================================ #
"""
Renderer payload and DOT generation helpers for Pretty LLDB.

This module converts extracted list, tree, and graph structures into stable
payloads consumed by the web visualizers and into deterministic DOT output used
for export commands and regression tests.

Author: XtremeXSPC
Version: 0.5.0.dev0
"""
# ============================================================================ #

import re
from typing import Iterable, Optional


_ANSI_ESCAPE_RE = re.compile(r"\x1b\[[0-9;]*m")


def _hex_address(address):
    """Format a numeric address using the hexadecimal style shown in LLDB."""

    return f"0x{address:x}"


def _escape_dot_label(text):
    """Escape label text so it remains valid inside Graphviz DOT strings."""

    return str(text).replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


def _strip_ansi(text):
    """Remove ANSI color sequences so web and DOT renderers receive plain text."""

    return _ANSI_ESCAPE_RE.sub("", str(text))


def _sorted_tree_nodes(extracted_tree):
    """Return tree nodes in deterministic address order for stable rendering."""

    return sorted(extracted_tree.nodes, key=lambda node: node.address)


def _sorted_tree_edges(extracted_tree):
    """Return tree edges in deterministic source/target order."""

    return sorted(extracted_tree.edges, key=lambda edge: (edge.source, edge.target))


def _sorted_graph_nodes(extracted_graph):
    """Return graph nodes in deterministic address order for tests and exports."""

    return sorted(extracted_graph.nodes, key=lambda node: node.address)


def _sorted_graph_edges(extracted_graph):
    """Return graph edges in deterministic source/target order."""

    return sorted(extracted_graph.edges, key=lambda edge: (edge.source, edge.target))


def build_list_renderer_payload(extracted_list):
    """Translate an extracted linear structure into web-renderer payload data."""

    seen_addresses = set()
    nodes_data = []
    edges_data = []

    for index, node in enumerate(extracted_list.nodes):
        node_id = _hex_address(node.address)
        nodes_data.append(
            {
                "id": node_id,
                "label": _strip_ansi(node.value),
                "value": _strip_ansi(node.value),
                "address": node_id,
                "index": index,
            }
        )

        if node.next_address != 0:
            target_id = _hex_address(node.next_address)
            is_cycle_edge = node.next_address in seen_addresses
            edges_data.append(
                {
                    "from": node_id,
                    "to": target_id,
                    "arrows": "to",
                    "kind": "cycle" if is_cycle_edge else "next",
                    "is_cycle_edge": is_cycle_edge,
                }
            )

        if extracted_list.is_doubly_linked and index > 0:
            prev_node = extracted_list.nodes[index - 1]
            edges_data.append(
                {
                    "from": node_id,
                    "to": _hex_address(prev_node.address),
                    "arrows": "to",
                    "kind": "prev",
                    "is_cycle_edge": False,
                }
            )

        seen_addresses.add(node.address)

    return {
        "nodes_data": nodes_data,
        "edges_data": edges_data,
        "traversal_order": extracted_list.traversal_order,
        "list_size": extracted_list.size if extracted_list.size is not None else 0,
        "is_doubly_linked": extracted_list.is_doubly_linked,
        "cycle_detected": extracted_list.cycle_detected,
        "truncated": extracted_list.truncated,
    }


def build_tree_renderer_payload(extracted_tree, traversal_order: Optional[Iterable[int]] = None):
    """Translate an extracted tree into deterministic node and edge payloads."""

    order_map = {}
    if traversal_order:
        order_map = {address: index for index, address in enumerate(traversal_order, 1)}

    nodes_data = []
    for node in _sorted_tree_nodes(extracted_tree):
        plain_value = _strip_ansi(node.value)
        label = plain_value
        if node.address in order_map:
            label = f"{order_map[node.address]}: {label}"

        node_id = _hex_address(node.address)
        nodes_data.append(
            {
                "id": node_id,
                "label": label,
                "value": plain_value,
                "title": f"Value: {plain_value}\nAddress: {node_id}",
                "address": node_id,
            }
        )

    edges_data = [
        {"from": _hex_address(edge.source), "to": _hex_address(edge.target)}
        for edge in _sorted_tree_edges(extracted_tree)
    ]

    return {
        "nodes_data": nodes_data,
        "edges_data": edges_data,
        "root_address": (
            _hex_address(extracted_tree.root_address) if extracted_tree.root_address else None
        ),
        "tree_size": extracted_tree.size if extracted_tree.size is not None else "N/A",
        "child_mode": extracted_tree.child_mode,
    }


def build_graph_renderer_payload(extracted_graph, directed=True):
    """Translate an extracted graph into payload data for web and DOT renderers."""

    nodes_data = []
    for node in _sorted_graph_nodes(extracted_graph):
        node_id = _hex_address(node.address)
        nodes_data.append(
            {
                "id": node_id,
                "label": _strip_ansi(node.value),
                "title": f"Value: {_strip_ansi(node.value)}",
                "address": node_id,
            }
        )

    edges_data = []
    seen_undirected_edges = set()
    for edge in _sorted_graph_edges(extracted_graph):
        if not directed:
            undirected_key = tuple(sorted((edge.source, edge.target)))
            if undirected_key in seen_undirected_edges:
                continue
            seen_undirected_edges.add(undirected_key)

        edge_data = {
            "from": _hex_address(edge.source),
            "to": _hex_address(edge.target),
            "directed": directed,
        }
        if directed:
            edge_data["arrows"] = "to"
        edges_data.append(edge_data)

    return {
        "nodes_data": nodes_data,
        "edges_data": edges_data,
        "num_nodes": extracted_graph.num_nodes,
        "num_edges": len(edges_data) if not directed else extracted_graph.num_edges,
        "directed": directed,
    }


def render_tree_dot(extracted_tree, traversal_order: Optional[Iterable[int]] = None):
    """Render an extracted tree as Graphviz DOT with deterministic ordering."""

    payload = build_tree_renderer_payload(extracted_tree, traversal_order=traversal_order)

    dot_lines = [
        "digraph Tree {",
        '  graph [rankdir="TD"];',
        "  node [shape=circle, style=filled, fillcolor=lightblue];",
        "  edge [arrowhead=vee];",
    ]

    for node in payload["nodes_data"]:
        label = _escape_dot_label(node["label"])
        dot_lines.append(f'  Node_{node["address"]} [label="{label}"];')

    for edge in payload["edges_data"]:
        dot_lines.append(f'  Node_{edge["from"]} -> Node_{edge["to"]};')

    dot_lines.append("}")
    return "\n".join(dot_lines)


def render_graph_dot(extracted_graph, directed=True):
    """Render an extracted graph as Graphviz DOT in directed or undirected mode."""

    payload = build_graph_renderer_payload(extracted_graph, directed=directed)
    graph_keyword = "digraph" if directed else "graph"
    edge_operator = "->" if directed else "--"

    dot_lines = [
        f"{graph_keyword} Graph {{",
        '  graph [rankdir="LR"];',
        "  node [shape=circle];",
    ]

    for node in payload["nodes_data"]:
        label = _escape_dot_label(node["label"])
        dot_lines.append(f'  Node_{node["address"]} [label="{label}"];')

    for edge in payload["edges_data"]:
        dot_lines.append(f'  Node_{edge["from"]} {edge_operator} Node_{edge["to"]};')

    dot_lines.append("}")
    return "\n".join(dot_lines)
