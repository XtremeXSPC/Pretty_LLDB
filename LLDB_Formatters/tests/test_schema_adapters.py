import unittest

from LLDB_Formatters.extraction import (
    extract_graph_structure,
    extract_linear_structure,
    extract_tree_structure,
)
from LLDB_Formatters.graph import GraphProvider, graph_node_summary_provider
from LLDB_Formatters.linear import linear_container_summary_provider
from LLDB_Formatters.schema_adapters import resolve_tree_container_schema
from LLDB_Formatters.strategies import (
    InOrderTreeStrategy,
    PostOrderTreeStrategy,
    PreOrderTreeStrategy,
)
from LLDB_Formatters.tests.mock_lldb import MockSBValue, MockSBValueContainer
from LLDB_Formatters.tree import tree_summary_provider


def strip_ansi(text):
    return (
        text.replace("\x1b[33m", "")
        .replace("\x1b[32m", "")
        .replace("\x1b[31m", "")
        .replace("\x1b[1;36m", "")
        .replace("\x1b[0m", "")
    )


class TestSchemaAdapters(unittest.TestCase):
    def test_linear_summary_supports_alternate_container_and_node_fields(self):
        node3 = MockSBValue(
            30,
            {"payload": MockSBValue(30), "link": None, "previous": None},
            name="node3",
            type_name="AltListNode<int>",
        )
        node2 = MockSBValue(
            20,
            {"payload": MockSBValue(20), "link": node3, "previous": None},
            name="node2",
            type_name="AltListNode<int>",
        )
        list_value = MockSBValue(
            children={"first": node2, "length": MockSBValue(2)},
            type_name="MyLinkedList<int>",
        )

        extraction = extract_linear_structure(list_value, max_items=10)
        summary = strip_ansi(linear_container_summary_provider(list_value, {}))

        self.assertEqual([node.value for node in extraction.nodes], ["20", "30"])
        self.assertEqual(extraction.head_field, "first")
        self.assertEqual(extraction.size_field, "length")
        self.assertEqual(extraction.value_field, "payload")
        self.assertEqual(extraction.next_field, "link")
        self.assertTrue(extraction.is_doubly_linked)
        self.assertIn("size = 2", summary)
        self.assertIn("[20 <-> 30]", summary)

    def test_tree_summary_supports_alternate_binary_fields(self):
        left = MockSBValue(
            1,
            {"payload": MockSBValue(1), "lhs": None, "rhs": None},
            type_name="AltTreeNode<int>",
        )
        right = MockSBValue(
            3,
            {"payload": MockSBValue(3), "lhs": None, "rhs": None},
            type_name="AltTreeNode<int>",
        )
        root = MockSBValue(
            2,
            {"payload": MockSBValue(2), "lhs": left, "rhs": right},
            type_name="AltTreeNode<int>",
        )
        tree_value = MockSBValue(
            children={"root_node": root, "node_count": MockSBValue(3)},
            type_name="MyTree<int>",
        )

        summary = strip_ansi(tree_summary_provider(tree_value, {}))
        preorder, _ = PreOrderTreeStrategy().traverse(root, max_items=100)
        inorder, _ = InOrderTreeStrategy().traverse(root, max_items=100)
        postorder, _ = PostOrderTreeStrategy().traverse(root, max_items=100)

        self.assertIn("size = 3", summary)
        self.assertIn("[2 -> 1 -> 3] (preorder)", summary)
        self.assertEqual(preorder, ["2", "1", "3"])
        self.assertEqual(inorder, ["1", "2", "3"])
        self.assertEqual(postorder, ["1", "3", "2"])

    def test_tree_strategies_support_alternate_nary_fields(self):
        child1 = MockSBValue(1, {"payload": MockSBValue(1)}, type_name="AltNaryNode<int>")
        child2 = MockSBValue(2, {"payload": MockSBValue(2)}, type_name="AltNaryNode<int>")
        root = MockSBValue(
            0,
            {
                "payload": MockSBValue(0),
                "kids": MockSBValueContainer([child1, child2]),
            },
            type_name="AltNaryNode<int>",
        )

        preorder, _ = PreOrderTreeStrategy().traverse(root, max_items=100)
        inorder, _ = InOrderTreeStrategy().traverse(root, max_items=100)
        postorder, _ = PostOrderTreeStrategy().traverse(root, max_items=100)

        self.assertEqual(preorder, ["0", "1", "2"])
        self.assertEqual(inorder, ["1", "0", "2"])
        self.assertEqual(postorder, ["1", "2", "0"])

    def test_graph_provider_supports_alternate_container_fields(self):
        node_c = MockSBValue(
            30,
            {"payload": MockSBValue(30), "connections": MockSBValueContainer([])},
            type_name="AltGraphNode<int>",
        )
        node_b = MockSBValue(
            20,
            {"payload": MockSBValue(20), "connections": MockSBValueContainer([node_c])},
            type_name="AltGraphNode<int>",
        )
        node_a = MockSBValue(
            10,
            {
                "payload": MockSBValue(10),
                "connections": MockSBValueContainer([node_b, node_c]),
            },
            type_name="AltGraphNode<int>",
        )
        graph_value = MockSBValue(
            children={
                "vertices": MockSBValueContainer([node_a, node_b, node_c]),
                "vertex_count": MockSBValue(3),
                "edge_total": MockSBValue(3),
            },
            type_name="MyGraph<int>",
        )

        provider = GraphProvider(graph_value, {})
        extraction = extract_graph_structure(graph_value)

        self.assertEqual(provider.get_summary(), "Graph | V = 3 | E = 3")
        self.assertEqual(extraction.nodes_field, "vertices")
        self.assertEqual(extraction.size_field, "vertex_count")
        self.assertEqual(extraction.edge_count_field, "edge_total")
        self.assertEqual(extraction.value_field, "payload")
        self.assertEqual(extraction.neighbors_field, "connections")

    def test_graph_node_summary_supports_alternate_node_fields(self):
        node_c = MockSBValue(
            30,
            {"payload": MockSBValue(30), "connections": MockSBValueContainer([])},
            type_name="AltGraphNode<int>",
        )
        node_b = MockSBValue(
            20,
            {"payload": MockSBValue(20), "connections": MockSBValueContainer([node_c])},
            type_name="AltGraphNode<int>",
        )
        node_a = MockSBValue(
            10,
            {
                "payload": MockSBValue(10),
                "connections": MockSBValueContainer([node_b, node_c]),
            },
            type_name="AltGraphNode<int>",
        )

        summary = strip_ansi(graph_node_summary_provider(node_a, {}))

        self.assertEqual(summary, "10 -> [20, 30]")

    def test_tree_extraction_preserves_resolved_root_pointer(self):
        root = MockSBValue(
            2,
            {"left": None, "right": None, "value": MockSBValue(2)},
            type_name="MyTreeNode<int>",
        )
        tree_value = MockSBValue(
            children={"root": root, "size": MockSBValue(1)},
            type_name="MyTree<int>",
        )

        extraction = extract_tree_structure(tree_value)

        self.assertIs(extraction.root_ptr, root)
        self.assertEqual(extraction.root_address, root.GetAddress().GetFileAddress())

    def test_unmatched_tree_container_schema_does_not_select_arbitrary_adapter(self):
        tree_value = MockSBValue(
            children={"mystery_root": MockSBValue(1)},
            type_name="MysteryTree<int>",
        )

        schema = resolve_tree_container_schema(tree_value)

        self.assertIsNone(schema.adapter_name)
        self.assertIsNone(schema.root_field)
        self.assertIsNone(schema.root_ptr)


if __name__ == "__main__":
    unittest.main()
