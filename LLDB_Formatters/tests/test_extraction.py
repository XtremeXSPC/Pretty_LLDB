import unittest

from LLDB_Formatters.extraction import (
    extract_graph_structure,
    extract_linear_structure,
    extract_tree_structure,
)
from LLDB_Formatters.tests.mock_lldb import MockSBValue, MockSBValueContainer


class TestExtractionLayer(unittest.TestCase):
    def test_extract_linear_structure_collects_nodes_and_diagnostics(self):
        node3 = MockSBValue(30, {"value": MockSBValue(30), "next": None, "prev": None})
        node2 = MockSBValue(
            20, {"value": MockSBValue(20), "next": node3, "prev": None}
        )
        head = MockSBValue(
            children={"head": node2, "size": MockSBValue(2)}
        )

        extraction = extract_linear_structure(head, max_items=10)

        self.assertEqual([node.value for node in extraction.nodes], ["20", "30"])
        self.assertEqual(extraction.size, 2)
        self.assertTrue(extraction.is_doubly_linked)
        self.assertEqual(extraction.head_field, "head")
        self.assertEqual(extraction.next_field, "next")
        self.assertEqual(extraction.value_field, "value")
        self.assertIn("container_head=head", extraction.diagnostics.compact_summary())

    def test_extract_linear_structure_reports_cycle(self):
        node3 = MockSBValue(30, {"value": MockSBValue(30)})
        node2 = MockSBValue(20, {"value": MockSBValue(20), "next": node3})
        head = MockSBValue(children={"head": node2})
        node3._children["next"] = node2

        extraction = extract_linear_structure(head, max_items=10)

        self.assertTrue(extraction.cycle_detected)
        self.assertEqual([warning.code for warning in extraction.diagnostics.warnings], ["cycle_detected"])

    def test_extract_tree_structure_builds_nodes_and_edges(self):
        left = MockSBValue(1, {"value": MockSBValue(1)})
        right = MockSBValue(3, {"value": MockSBValue(3)})
        root = MockSBValue(
            2, {"left": left, "right": right, "value": MockSBValue(2)}
        )
        tree = MockSBValue(children={"root": root, "size": MockSBValue(3)})

        extraction = extract_tree_structure(tree)

        self.assertEqual(extraction.root_field, "root")
        self.assertEqual(extraction.size, 3)
        self.assertEqual(sorted(node.value for node in extraction.nodes), ["1", "2", "3"])
        self.assertEqual(len(extraction.edges), 2)
        self.assertEqual(extraction.child_mode, "binary")

    def test_extract_graph_structure_builds_directional_edges(self):
        node_c = MockSBValue(
            30, {"value": MockSBValue(30), "neighbors": MockSBValueContainer([])}
        )
        node_b = MockSBValue(
            20, {"value": MockSBValue(20), "neighbors": MockSBValueContainer([node_c])}
        )
        node_a = MockSBValue(
            10,
            {
                "value": MockSBValue(10),
                "neighbors": MockSBValueContainer([node_b, node_c]),
            },
        )
        graph = MockSBValue(
            children={
                "nodes": MockSBValueContainer([node_a, node_b, node_c]),
                "num_nodes": MockSBValue(3),
            }
        )

        extraction = extract_graph_structure(graph)

        self.assertEqual(extraction.nodes_field, "nodes")
        self.assertEqual(extraction.num_nodes, 3)
        addresses_by_value = {
            node.value: node.address for node in extraction.nodes
        }
        self.assertEqual(
            sorted((edge.source, edge.target) for edge in extraction.edges),
            sorted(
                [
                    (addresses_by_value["10"], addresses_by_value["20"]),
                    (addresses_by_value["10"], addresses_by_value["30"]),
                    (addresses_by_value["20"], addresses_by_value["30"]),
                ]
            ),
        )
        self.assertEqual(extraction.neighbors_field, "neighbors")


if __name__ == "__main__":
    unittest.main()
