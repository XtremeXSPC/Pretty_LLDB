# ---------------------------------------------------------------------- #
# FILE: tests/test_linear_strategy.py
#
# DESCRIPTION:
# This file contains the unit tests for the LinearTraversalStrategy.
# It verifies the correct traversal of singly and doubly linked lists,
# as well as edge cases like empty lists, truncation, and cycle detection.
# ---------------------------------------------------------------------- #

import unittest

from LLDB_Formatters.strategies import LinearTraversalStrategy
from LLDB_Formatters.tests.mock_lldb import MockSBValue


# ----- Test Cases for LinearTraversalStrategy ----- #
class TestLinearStrategy(unittest.TestCase):
    """A test suite for the LinearTraversalStrategy."""

    def test_empty_list(self):
        """Verify that the strategy correctly handles an empty list (head=None)."""
        strategy = LinearTraversalStrategy()
        values, metadata = strategy.traverse(root_ptr=None, max_items=100)
        self.assertEqual(values, [])
        self.assertEqual(metadata, {})

    def test_single_node_list(self):
        """Verify traversal of a list with only one node."""
        head = MockSBValue(10, {"value": MockSBValue(10), "next": None})
        strategy = LinearTraversalStrategy()
        values, _ = strategy.traverse(head, 100)
        self.assertEqual(values, ["10"])

    def test_singly_linked_list_traversal(self):
        """Verify correct traversal of a standard singly-linked list."""
        node3 = MockSBValue(30, {"value": MockSBValue(30), "next": None})
        node2 = MockSBValue(20, {"value": MockSBValue(20), "next": node3})
        head = MockSBValue(10, {"value": MockSBValue(10), "next": node2})

        strategy = LinearTraversalStrategy()
        values, metadata = strategy.traverse(head, 100)

        self.assertEqual(values, ["10", "20", "30"])
        self.assertFalse(metadata.get("doubly_linked", True))

    def test_doubly_linked_list_detection(self):
        """Verify that a doubly-linked list is correctly detected."""
        node3 = MockSBValue(
            30, {"value": MockSBValue(30), "next": None, "prev": None}
        )  # prev is set
        node2 = MockSBValue(20, {"value": MockSBValue(20), "next": node3, "prev": None})
        head = MockSBValue(10, {"value": MockSBValue(10), "next": node2, "prev": None})

        strategy = LinearTraversalStrategy()
        values, metadata = strategy.traverse(head, 100)

        self.assertEqual(values, ["10", "20", "30"])
        self.assertTrue(metadata.get("doubly_linked", False))

    def test_truncation(self):
        """Verify that the traversal is correctly truncated by max_items."""
        node3 = MockSBValue(30, {"value": MockSBValue(30), "next": None})
        node2 = MockSBValue(20, {"value": MockSBValue(20), "next": node3})
        head = MockSBValue(10, {"value": MockSBValue(10), "next": node2})

        strategy = LinearTraversalStrategy()
        values, metadata = strategy.traverse(head, max_items=2)

        self.assertEqual(len(values), 2)
        self.assertEqual(values, ["10", "20"])
        self.assertTrue(metadata.get("truncated", False))

    def test_cycle_detection(self):
        """Verify that a cycle in the list is detected and handled gracefully."""
        node3 = MockSBValue(30, {"value": MockSBValue(30)})
        node2 = MockSBValue(20, {"value": MockSBValue(20), "next": node3})
        head = MockSBValue(10, {"value": MockSBValue(10), "next": node2})
        # Create a cycle: node3 points back to node2
        node3._children["next"] = node2

        strategy = LinearTraversalStrategy()
        values, _ = strategy.traverse(head, max_items=100)

        self.assertEqual(values, ["10", "20", "30", "[CYCLE DETECTED]"])


if __name__ == "__main__":
    unittest.main()
