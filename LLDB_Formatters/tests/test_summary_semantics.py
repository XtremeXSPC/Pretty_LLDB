import unittest

from LLDB_Formatters.graph import GraphProvider
from LLDB_Formatters.linear import linear_container_summary_provider
from LLDB_Formatters.tests.mock_lldb import MockSBValue, MockSBValueContainer
from LLDB_Formatters.tree import tree_summary_provider


def _invalid_value(name):
    return MockSBValue(name=name, valid=False)


class TestSummarySemantics(unittest.TestCase):
    def test_linear_summary_reports_unsupported_layout(self):
        list_value = MockSBValue(
            children={"size": MockSBValue(0)},
            name="broken_list",
            type_name="MyList<int>",
        )

        summary = linear_container_summary_provider(list_value, {})

        self.assertEqual(summary, "Linear structure [unsupported layout]")

    def test_linear_summary_marks_partial_rendering_as_incomplete(self):
        node = MockSBValue(
            children={"value": MockSBValue(10), "next": _invalid_value("next")},
            name="node1",
            address=0x1000,
            type_name="Node<int>",
        )
        list_value = MockSBValue(
            children={"head": node, "size": MockSBValue(1)},
            name="partial_list",
            type_name="MyList<int>",
        )

        summary = linear_container_summary_provider(list_value, {})

        self.assertIn("size = 1", summary)
        self.assertIn("[10]", summary)
        self.assertTrue(summary.endswith("[incomplete]"))

    def test_tree_summary_reports_unsupported_layout(self):
        tree_value = MockSBValue(
            children={"size": MockSBValue(0)},
            name="broken_tree",
            type_name="MyBinaryTree<int>",
        )

        summary = tree_summary_provider(tree_value, {})

        self.assertEqual(summary, "Tree [unsupported layout]")

    def test_graph_summary_reports_unsupported_layout(self):
        graph_value = MockSBValue(
            children={"num_nodes": MockSBValue(0)},
            name="broken_graph",
            type_name="MyGraph<int>",
        )

        summary = GraphProvider(graph_value, {}).get_summary()

        self.assertEqual(summary, "Graph [unsupported layout]")

    def test_graph_summary_marks_partial_rendering_as_incomplete(self):
        node = MockSBValue(
            children={
                "value": MockSBValue(10),
                "neighbors": MockSBValueContainer([_invalid_value("neighbor")]),
            },
            name="node_a",
            type_name="MyGraphNode<int>",
        )
        graph_value = MockSBValue(
            children={
                "nodes": MockSBValueContainer([node]),
                "num_nodes": MockSBValue(1),
                "num_edges": MockSBValue(0),
            },
            name="partial_graph",
            type_name="MyGraph<int>",
        )

        summary = GraphProvider(graph_value, {}).get_summary()

        self.assertEqual(summary, "Graph | V = 1 | E = 0 [incomplete]")


if __name__ == "__main__":
    unittest.main()
