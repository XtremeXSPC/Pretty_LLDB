import unittest

from LLDB_Formatters.config import g_config
from LLDB_Formatters.tests.mock_lldb import MockSBValue, MockSBValueContainer
from LLDB_Formatters.web_visualizer import (
    generate_graph_visualization_html,
    generate_list_visualization_html,
    generate_tree_visualization_html,
)


def _null_pointer(name):
    return MockSBValue(0, is_pointer=True, name=name, address=0)


def _make_list_with_cycle_and_prev():
    node3 = MockSBValue(
        children={"value": MockSBValue(30), "next": None, "prev": None},
        name="node3",
        address=0x3000,
        type_name="Node<int>",
    )
    node2 = MockSBValue(
        children={"value": MockSBValue(20), "next": node3, "prev": None},
        name="node2",
        address=0x2000,
        type_name="Node<int>",
    )
    node1 = MockSBValue(
        children={"value": MockSBValue(10), "next": node2, "prev": None},
        name="node1",
        address=0x1000,
        type_name="Node<int>",
    )
    node3._children["next"] = node2
    node2._children["prev"] = node1
    node3._children["prev"] = node2
    return MockSBValue(
        children={"head": node1, "size": MockSBValue(3)},
        name="cycle_list",
        type_name="MyList<int>",
    )


def _make_tree():
    left = MockSBValue(
        children={
            "left": _null_pointer("left"),
            "right": _null_pointer("right"),
            "value": MockSBValue(1),
        },
        name="left",
        address=0x1100,
        type_name="TreeNode<int>",
    )
    right = MockSBValue(
        children={
            "left": _null_pointer("left"),
            "right": _null_pointer("right"),
            "value": MockSBValue(3),
        },
        name="right",
        address=0x1300,
        type_name="TreeNode<int>",
    )
    root = MockSBValue(
        children={"left": left, "right": right, "value": MockSBValue(2)},
        name="root",
        address=0x1200,
        type_name="TreeNode<int>",
    )
    return MockSBValue(
        children={"root": root, "size": MockSBValue(3)},
        name="my_tree",
        type_name="MyBinaryTree<int>",
    )


def _make_graph():
    node_b = MockSBValue(
        20,
        {"value": MockSBValue(20), "neighbors": MockSBValueContainer([])},
        address=0x2200,
        name="node_b",
        type_name="MyGraphNode<int>",
    )
    node_a = MockSBValue(
        10,
        {"value": MockSBValue(10), "neighbors": MockSBValueContainer([node_b])},
        address=0x2100,
        name="node_a",
        type_name="MyGraphNode<int>",
    )
    node_b._children["neighbors"] = MockSBValueContainer([node_a])
    return MockSBValue(
        children={
            "nodes": MockSBValueContainer([node_a, node_b]),
            "num_nodes": MockSBValue(2),
            "num_edges": MockSBValue(2),
        },
        name="my_graph",
        type_name="MyGraph<int>",
    )


class TestWebVisualizer(unittest.TestCase):
    def test_list_visualization_html_contains_cycle_and_backward_edge_metadata(self):
        html = generate_list_visualization_html(_make_list_with_cycle_and_prev())

        self.assertIsNotNone(html)
        self.assertIn('"kind": "cycle"', html)
        self.assertIn('"kind": "prev"', html)
        self.assertIn("const cycleDetected = true;", html)

    def test_tree_visualization_html_can_annotate_inorder_traversal(self):
        html = generate_tree_visualization_html(_make_tree(), traversal_name="inorder")

        self.assertIsNotNone(html)
        self.assertIn('"label": "1: 1"', html)
        self.assertIn('"label": "2: 2"', html)
        self.assertIn('"label": "3: 3"', html)
        self.assertIn("<th>Traversal</th><td>inorder</td>", html)

    def test_tree_visualization_html_uses_configured_default_traversal(self):
        original_strategy = g_config.tree_traversal_strategy
        g_config.tree_traversal_strategy = "postorder"
        try:
            html = generate_tree_visualization_html(_make_tree())
        finally:
            g_config.tree_traversal_strategy = original_strategy

        self.assertIsNotNone(html)
        self.assertIn("<th>Traversal</th><td>postorder</td>", html)
        self.assertIn('"label": "1: 1"', html)

    def test_graph_visualization_html_marks_undirected_mode(self):
        html = generate_graph_visualization_html(_make_graph(), directed=False)

        self.assertIsNotNone(html)
        self.assertIn("const isDirected = false;", html)
        self.assertIn("<th>Mode</th><td>Undirected</td>", html)


if __name__ == "__main__":
    unittest.main()
