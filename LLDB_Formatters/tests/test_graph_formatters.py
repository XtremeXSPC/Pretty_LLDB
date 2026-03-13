# ---------------------------------------------------------------------- #
# FILE: tests/test_graph_formatters.py
#
# DESCRIPTION:
# This file contains the unit tests for the GraphProvider and the
# graph_node_summary_provider. It tests the synthetic children logic
# and the node summary generation, including truncation.
# ---------------------------------------------------------------------- #

import unittest
from unittest.mock import patch

from LLDB_Formatters.config import g_config
from LLDB_Formatters.graph import GraphProvider, graph_node_summary_provider
from LLDB_Formatters.tests.mock_lldb import MockSBValue, MockSBValueContainer


# ----- Test Cases for Graph Formatters ----- #
class TestGraphFormatters(unittest.TestCase):
    """A test suite for graph formatters."""

    @classmethod
    def setUpClass(cls):
        """Build a mock graph structure to be used by all tests."""
        # Node D (leaf)
        cls.node_d = MockSBValue(
            40, {"value": MockSBValue(40), "neighbors": MockSBValueContainer([])}
        )

        # Node C (points to D)
        cls.node_c = MockSBValue(
            30,
            {"value": MockSBValue(30), "neighbors": MockSBValueContainer([cls.node_d])},
        )

        # Node B (points to C)
        cls.node_b = MockSBValue(
            20,
            {"value": MockSBValue(20), "neighbors": MockSBValueContainer([cls.node_c])},
        )

        # Node A (points to B and C)
        cls.node_a = MockSBValue(
            10,
            {
                "value": MockSBValue(10),
                "neighbors": MockSBValueContainer([cls.node_b, cls.node_c]),
            },
        )

        # Create the main graph object mock
        nodes_list = [cls.node_a, cls.node_b, cls.node_c, cls.node_d]
        cls.graph_obj = MockSBValue(
            children={
                "nodes": MockSBValueContainer(nodes_list),
                "num_nodes": MockSBValue(4),
                "num_edges": MockSBValue(3),
            }
        )

    def test_graph_provider_summary(self):
        """Verify the one-line summary of the entire graph object."""
        provider = GraphProvider(self.graph_obj, {})
        summary = provider.get_summary()
        self.assertEqual(summary, "Graph | V = 4 | E = 3")

    def test_graph_provider_children(self):
        """Verify the synthetic children logic of the GraphProvider."""
        provider = GraphProvider(self.graph_obj, {})

        # Check child count
        self.assertEqual(provider.num_children(), 4)

        # Check if it returns the correct node at a specific index
        child_at_1 = provider.get_child_at_index(1)
        # We compare the value, as the mock objects will be different
        self.assertIsNotNone(child_at_1)
        self.assertEqual(child_at_1.GetSummary(), "20")  # type: ignore
        self.assertIs(child_at_1, self.node_b)  # Should be the exact same object

    def test_graph_node_summary_simple(self):
        """Verify the summary for a node with one neighbor."""
        # Test summary for Node C -> D
        summary = graph_node_summary_provider(self.node_c, {})
        # Remove ANSI color codes for stable comparison
        plain_summary = summary.replace("\x1b[33m", "").replace("\x1b[0m", "")
        self.assertEqual(plain_summary, "30 -> [40]")

    def test_graph_node_summary_multiple_neighbors(self):
        """Verify the summary for a node with multiple neighbors."""
        # Test summary for Node A -> B, C
        summary = graph_node_summary_provider(self.node_a, {})
        plain_summary = summary.replace("\x1b[33m", "").replace("\x1b[0m", "")
        self.assertEqual(plain_summary, "10 -> [20, 30]")

    def test_graph_node_summary_truncation(self):
        """Verify that neighbor list is truncated according to g_config."""
        # Temporarily set the global limit to 1
        original_max = g_config.graph_max_neighbors
        g_config.graph_max_neighbors = 1

        # Test summary for Node A (should now be truncated)
        summary = graph_node_summary_provider(self.node_a, {})
        plain_summary = summary.replace("\x1b[33m", "").replace("\x1b[0m", "")

        self.assertEqual(plain_summary, "10 -> [20] ...")

        # Restore global config to not affect other tests
        g_config.graph_max_neighbors = original_max

    def test_graph_node_summary_no_neighbors(self):
        """Verify the summary for a node with no neighbors."""
        # Test summary for Node D
        summary = graph_node_summary_provider(self.node_d, {})
        plain_summary = summary.replace("\x1b[33m", "").replace("\x1b[0m", "")
        self.assertEqual(plain_summary, "40")

    def test_graph_node_summary_requests_only_one_extra_neighbor_for_truncation(self):
        original_max = g_config.graph_max_neighbors
        g_config.graph_max_neighbors = 1
        try:
            neighbors = self.node_a.GetChildMemberWithName("neighbors")
            with patch(
                "LLDB_Formatters.graph.iter_container_values",
                return_value=[self.node_b, self.node_c],
            ) as iter_mock:
                plain_summary = graph_node_summary_provider(self.node_a, {}).replace(
                    "\x1b[33m", ""
                ).replace("\x1b[0m", "")
        finally:
            g_config.graph_max_neighbors = original_max

        iter_mock.assert_called_once_with(neighbors, max_items=2)
        self.assertEqual(plain_summary, "10 -> [20] ...")


if __name__ == "__main__":
    unittest.main()
