from typing import Iterable, Optional


def _hex_address(address):
    return f"0x{address:x}"


def _escape_dot_label(text):
    return str(text).replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


def _sorted_tree_nodes(extracted_tree):
    return sorted(extracted_tree.nodes, key=lambda node: node.address)


def _sorted_tree_edges(extracted_tree):
    return sorted(extracted_tree.edges, key=lambda edge: (edge.source, edge.target))


def _sorted_graph_nodes(extracted_graph):
    return sorted(extracted_graph.nodes, key=lambda node: node.address)


def _sorted_graph_edges(extracted_graph):
    return sorted(extracted_graph.edges, key=lambda edge: (edge.source, edge.target))


def build_list_renderer_payload(extracted_list):
    node_addresses = {node.address for node in extracted_list.nodes}
    seen_addresses = set()
    nodes_data = []
    edges_data = []

    for index, node in enumerate(extracted_list.nodes):
        node_id = _hex_address(node.address)
        nodes_data.append(
            {
                "id": node_id,
                "label": node.value,
                "value": node.value,
                "address": node_id,
                "index": index,
            }
        )

        if node.next_address != 0:
            target_id = _hex_address(node.next_address)
            edges_data.append(
                {
                    "from": node_id,
                    "to": target_id,
                    "arrows": "to",
                    "kind": "next",
                    "is_cycle_edge": node.next_address in seen_addresses,
                    "is_visible_target": node.next_address in node_addresses,
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
    order_map = {}
    if traversal_order:
        order_map = {address: index for index, address in enumerate(traversal_order, 1)}

    nodes_data = []
    for node in _sorted_tree_nodes(extracted_tree):
        label = node.value
        if node.address in order_map:
            label = f"{order_map[node.address]}: {label}"

        node_id = _hex_address(node.address)
        nodes_data.append(
            {
                "id": node_id,
                "label": label,
                "value": node.value,
                "title": f"Value: {node.value}\nAddress: {node_id}",
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
        "root_address": _hex_address(extracted_tree.root_address) if extracted_tree.root_address else None,
        "tree_size": extracted_tree.size if extracted_tree.size is not None else "N/A",
        "child_mode": extracted_tree.child_mode,
    }


def build_graph_renderer_payload(extracted_graph, directed=True):
    nodes_data = []
    for node in _sorted_graph_nodes(extracted_graph):
        node_id = _hex_address(node.address)
        nodes_data.append(
            {
                "id": node_id,
                "label": node.value,
                "title": f"Value: {node.value}",
                "address": node_id,
            }
        )

    edges_data = []
    for edge in _sorted_graph_edges(extracted_graph):
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
        "num_edges": extracted_graph.num_edges,
        "directed": directed,
    }


def render_tree_dot(extracted_tree, traversal_order: Optional[Iterable[int]] = None):
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
