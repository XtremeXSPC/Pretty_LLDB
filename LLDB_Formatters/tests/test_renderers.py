import unittest

from LLDB_Formatters.extraction import (
    ExtractedGraphStructure,
    ExtractedLinearStructure,
    ExtractedTreeStructure,
    GraphEdge,
    GraphNode,
    LinearNode,
    TreeEdge,
    TreeNode,
)
from LLDB_Formatters.renderers import (
    build_graph_renderer_payload,
    build_list_renderer_payload,
    build_tree_renderer_payload,
    render_graph_dot,
    render_tree_dot,
)


class TestRenderers(unittest.TestCase):
    def test_build_list_renderer_payload_marks_cycle_edges(self):
        extracted_list = ExtractedLinearStructure(
            size=3,
            is_doubly_linked=False,
            cycle_detected=True,
            nodes=[
                LinearNode(address=0x10, value="10", next_address=0x20),
                LinearNode(address=0x20, value="20", next_address=0x30),
                LinearNode(address=0x30, value="30", next_address=0x20),
            ],
        )

        payload = build_list_renderer_payload(extracted_list)

        self.assertEqual(payload["traversal_order"], ["0x10", "0x20", "0x30"])
        self.assertEqual(
            [edge["is_cycle_edge"] for edge in payload["edges_data"]],
            [False, False, True],
        )
        self.assertEqual(
            [edge["kind"] for edge in payload["edges_data"]],
            ["next", "next", "cycle"],
        )

    def test_build_list_renderer_payload_adds_backward_edges_for_doubly_linked_lists(self):
        extracted_list = ExtractedLinearStructure(
            size=3,
            is_doubly_linked=True,
            nodes=[
                LinearNode(address=0x10, value="10", next_address=0x20),
                LinearNode(address=0x20, value="20", next_address=0x30),
                LinearNode(address=0x30, value="30", next_address=0),
            ],
        )

        payload = build_list_renderer_payload(extracted_list)

        self.assertEqual(
            [edge["kind"] for edge in payload["edges_data"]],
            ["next", "next", "prev", "prev"],
        )
        self.assertEqual(
            payload["edges_data"][-1],
            {
                "from": "0x30",
                "to": "0x20",
                "arrows": "to",
                "kind": "prev",
                "is_cycle_edge": False,
            },
        )

    def test_build_tree_renderer_payload_is_deterministic(self):
        extracted_tree = ExtractedTreeStructure(
            size=3,
            root_address=0x20,
            child_mode="binary",
            nodes=[
                TreeNode(address=0x20, value="root", children=[0x10, 0x30]),
                TreeNode(address=0x30, value="right"),
                TreeNode(address=0x10, value="left"),
            ],
            edges=[
                TreeEdge(source=0x20, target=0x30),
                TreeEdge(source=0x20, target=0x10),
            ],
        )

        payload = build_tree_renderer_payload(extracted_tree, traversal_order=[0x20, 0x10, 0x30])

        self.assertEqual(
            [node["address"] for node in payload["nodes_data"]],
            ["0x10", "0x20", "0x30"],
        )
        self.assertEqual(
            [node["label"] for node in payload["nodes_data"]],
            ["2: left", "1: root", "3: right"],
        )
        self.assertEqual(
            payload["edges_data"],
            [{"from": "0x20", "to": "0x10"}, {"from": "0x20", "to": "0x30"}],
        )

    def test_build_graph_renderer_payload_can_be_undirected(self):
        extracted_graph = ExtractedGraphStructure(
            num_nodes=2,
            num_edges=2,
            nodes=[
                GraphNode(address=0x20, value="b"),
                GraphNode(address=0x10, value="a"),
            ],
            edges=[
                GraphEdge(source=0x20, target=0x10),
                GraphEdge(source=0x10, target=0x20),
            ],
        )

        payload = build_graph_renderer_payload(extracted_graph, directed=False)

        self.assertFalse(payload["directed"])
        self.assertEqual(
            [node["address"] for node in payload["nodes_data"]],
            ["0x10", "0x20"],
        )
        self.assertEqual(payload["num_edges"], 1)
        self.assertEqual(len(payload["edges_data"]), 1)
        self.assertNotIn("arrows", payload["edges_data"][0])

    def test_render_graph_dot_escapes_labels_and_sorts_output(self):
        extracted_graph = ExtractedGraphStructure(
            num_nodes=2,
            num_edges=1,
            nodes=[
                GraphNode(address=0x20, value='b "quoted"'),
                GraphNode(address=0x10, value="a\\path\nline"),
            ],
            edges=[GraphEdge(source=0x20, target=0x10)],
        )

        dot = render_graph_dot(extracted_graph, directed=True)

        self.assertIn('digraph Graph {', dot)
        self.assertIn('Node_0x10 [label="a\\\\path\\nline"];', dot)
        self.assertIn('Node_0x20 [label="b \\"quoted\\""];', dot)
        self.assertLess(dot.index('Node_0x10 [label="a\\\\path\\nline"];'), dot.index('Node_0x20 [label="b \\"quoted\\""];'))
        self.assertIn("Node_0x20 -> Node_0x10;", dot)

    def test_render_graph_dot_uses_undirected_edges_when_requested(self):
        extracted_graph = ExtractedGraphStructure(
            num_nodes=2,
            num_edges=2,
            nodes=[
                GraphNode(address=0x20, value="b"),
                GraphNode(address=0x10, value="a"),
            ],
            edges=[
                GraphEdge(source=0x20, target=0x10),
                GraphEdge(source=0x10, target=0x20),
            ],
        )

        dot = render_graph_dot(extracted_graph, directed=False)

        self.assertIn("graph Graph {", dot)
        self.assertIn("Node_0x10 -- Node_0x20;", dot)
        self.assertNotIn("->", dot)

    def test_render_tree_dot_annotates_traversal_order(self):
        extracted_tree = ExtractedTreeStructure(
            size=3,
            root_address=0x20,
            child_mode="binary",
            nodes=[
                TreeNode(address=0x20, value="root", children=[0x10, 0x30]),
                TreeNode(address=0x10, value="left"),
                TreeNode(address=0x30, value="right"),
            ],
            edges=[
                TreeEdge(source=0x20, target=0x30),
                TreeEdge(source=0x20, target=0x10),
            ],
        )

        dot = render_tree_dot(extracted_tree, traversal_order=[0x20, 0x10, 0x30])

        self.assertIn('Node_0x20 [label="1: root"];', dot)
        self.assertIn('Node_0x10 [label="2: left"];', dot)
        self.assertIn('Node_0x30 [label="3: right"];', dot)
        self.assertLess(dot.index("Node_0x20 -> Node_0x10;"), dot.index("Node_0x20 -> Node_0x30;"))


if __name__ == "__main__":
    unittest.main()
