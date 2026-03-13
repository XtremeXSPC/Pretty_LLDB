# ---------------------------------------------------------------------- #
# FILE: tests/test_tree_strategies.py
#
# DESCRIPTION:
# This file contains the unit tests for the tree traversal strategies.
# It uses Python's standard 'unittest' framework. The key to this test
# suite is a more faithful mock of the lldb.SBValue API, which allows
# the real helper functions to be tested directly with mock data,
# removing the need for complex patching.
# ---------------------------------------------------------------------- #

import unittest

from LLDB_Formatters.config import g_config
from LLDB_Formatters.strategies import (
    InOrderTreeStrategy,
    PostOrderTreeStrategy,
    PreOrderTreeStrategy,
)
from LLDB_Formatters.tests.mock_lldb import MockSBValue


def _make_right_skewed_tree(depth):
    current = None
    for value in range(depth, 0, -1):
        current = MockSBValue(
            value,
            {"left": None, "right": current, "value": MockSBValue(value)},
        )
    return current


# ----- Test Cases for Tree Traversal Strategies ----- #
class TestTreeStrategies(unittest.TestCase):
    """
    A test suite for our tree traversal strategies.
    It builds a complex mock tree once and runs all traversal
    strategies against it, including edge cases.
    """

    @classmethod
    def setUpClass(cls):
        """
        This method is run once before all tests.
        We build our test tree here using the mock objects.
        This tree is an exact representation of the one in the image.
        All nodes, including leaves, realistically have a 'value' child member.
        """
        # ----- Build Nodes (from the bottom up) ----- #
        # Leaves
        node0 = MockSBValue(0, {"value": MockSBValue(0)})
        node2 = MockSBValue(2, {"value": MockSBValue(2)})
        node5 = MockSBValue(5, {"value": MockSBValue(5)})
        node7 = MockSBValue(7, {"value": MockSBValue(7)})
        node9 = MockSBValue(9, {"value": MockSBValue(9)})
        node11 = MockSBValue(11, {"value": MockSBValue(11)})
        node18 = MockSBValue(18, {"value": MockSBValue(18)})

        # Internal Nodes
        node1 = MockSBValue(1, {"left": node0, "right": node2, "value": MockSBValue(1)})
        node4 = MockSBValue(4, {"left": None, "right": node5, "value": MockSBValue(4)})
        node12 = MockSBValue(12, {"left": node11, "right": None, "value": MockSBValue(12)})
        node17 = MockSBValue(17, {"left": None, "right": node18, "value": MockSBValue(17)})

        node6 = MockSBValue(6, {"left": node4, "right": node7, "value": MockSBValue(6)})
        node13 = MockSBValue(13, {"left": node12, "right": None, "value": MockSBValue(13)})
        node16 = MockSBValue(16, {"left": None, "right": node17, "value": MockSBValue(16)})

        node3 = MockSBValue(3, {"left": node1, "right": node6, "value": MockSBValue(3)})
        node15 = MockSBValue(15, {"left": None, "right": node16, "value": MockSBValue(15)})

        node14 = MockSBValue(14, {"left": node13, "right": node15, "value": MockSBValue(14)})

        node10 = MockSBValue(10, {"left": node9, "right": node14, "value": MockSBValue(10)})

        # Root
        cls.root = MockSBValue(8, {"left": node3, "right": node10, "value": MockSBValue(8)})

    def test_preorder_traversal(self):
        """Verify that the PreOrder strategy produces the correct sequence."""
        strategy = PreOrderTreeStrategy()
        values, _ = strategy.traverse(self.root, max_items=100)

        # fmt: off
        expected = [
            "8", "3", "1", "0", "2", "6", "4", "5", "7",
            "10", "9", "14", "13", "12", "11", "15", "16", "17", "18",
        ]
        # fmt: on

        self.assertEqual(values, expected, "PreOrder traversal is incorrect")

    def test_inorder_traversal(self):
        """Verify that the InOrder strategy produces the correct sequence."""
        strategy = InOrderTreeStrategy()
        values, _ = strategy.traverse(self.root, max_items=100)

        # fmt: off
        expected = [
            "0", "1", "2", "3", "4", "5", "6", "7", "8", "9",
            "10", "11", "12", "13", "14", "15", "16", "17", "18",
        ]
        # fmt: on

        self.assertEqual(values, expected, "InOrder traversal is incorrect")

    def test_postorder_traversal(self):
        """Verify that the PostOrder strategy produces the correct sequence."""
        strategy = PostOrderTreeStrategy()
        values, _ = strategy.traverse(self.root, max_items=100)

        # fmt: off
        expected = [
            "0", "2", "1", "5", "4", "7", "6", "3", "9", "11",
            "12", "13", "18", "17", "16", "15", "14", "10", "8",
        ]
        # fmt: on

        self.assertEqual(values, expected, "PostOrder traversal is incorrect")

    def test_empty_tree(self):
        """Verify that strategies correctly handle an empty tree (root=None)."""
        root = None

        strategy_inorder = InOrderTreeStrategy()
        values, _ = strategy_inorder.traverse(root, max_items=100)
        self.assertEqual(values, [], "InOrder failed on empty tree")

    def test_root_only_tree(self):
        """Verify that strategies work with a single-node tree."""
        root = MockSBValue(42, {"left": None, "right": None, "value": MockSBValue(42)})
        expected_values = ["42"]

        preorder_vals, _ = PreOrderTreeStrategy().traverse(root, 100)
        inorder_vals, _ = InOrderTreeStrategy().traverse(root, 100)
        postorder_vals, _ = PostOrderTreeStrategy().traverse(root, 100)

        self.assertEqual(preorder_vals, expected_values, "PreOrder failed on root-only tree")
        self.assertEqual(inorder_vals, expected_values, "InOrder failed on root-only tree")
        self.assertEqual(postorder_vals, expected_values, "PostOrder failed on root-only tree")

    def test_right_skewed_tree(self):
        """Verify a degenerate tree (like a right-linked list)."""
        # Structure: 1 -> 2 -> 3
        node3 = MockSBValue(3, {"value": MockSBValue(3)})
        node2 = MockSBValue(2, {"left": None, "right": node3, "value": MockSBValue(2)})
        root = MockSBValue(1, {"left": None, "right": node2, "value": MockSBValue(1)})

        pre_vals, _ = PreOrderTreeStrategy().traverse(root, 100)
        self.assertEqual(pre_vals, ["1", "2", "3"])

        in_vals, _ = InOrderTreeStrategy().traverse(root, 100)
        self.assertEqual(in_vals, ["1", "2", "3"])

        post_vals, _ = PostOrderTreeStrategy().traverse(root, 100)
        self.assertEqual(post_vals, ["3", "2", "1"])

    def test_truncation(self):
        """Verify that truncation with max_items works correctly."""
        strategy = InOrderTreeStrategy()
        max_items = 5

        values, metadata = strategy.traverse(self.root, max_items)

        self.assertEqual(len(values), max_items, "Incorrect number of items after truncation")
        self.assertEqual(values, ["0", "1", "2", "3", "4"], "Incorrect values after truncation")
        self.assertTrue(metadata.get("truncated", False), "Truncated flag was not set correctly")

    def test_preorder_traversal_respects_tree_depth_limit(self):
        original_depth_limit = g_config.tree_max_depth
        g_config.tree_max_depth = 2
        try:
            root = _make_right_skewed_tree(6)
            values, metadata = PreOrderTreeStrategy().traverse(root, max_items=100)
        finally:
            g_config.tree_max_depth = original_depth_limit

        self.assertEqual(values, ["1", "2", "3"])
        self.assertTrue(metadata.get("depth_limited"))
        self.assertTrue(metadata.get("truncated"))

    def test_iterative_strategies_handle_very_deep_trees_without_recursion_errors(self):
        depth = 1100
        original_depth_limit = g_config.tree_max_depth
        g_config.tree_max_depth = depth + 4
        try:
            root = _make_right_skewed_tree(depth)
            preorder, pre_meta = PreOrderTreeStrategy().traverse(root, max_items=depth + 10)
            inorder, in_meta = InOrderTreeStrategy().traverse(root, max_items=depth + 10)
            postorder, post_meta = PostOrderTreeStrategy().traverse(root, max_items=depth + 10)
        finally:
            g_config.tree_max_depth = original_depth_limit

        self.assertEqual(len(preorder), depth)
        self.assertEqual(preorder[:3], ["1", "2", "3"])
        self.assertEqual(inorder[:3], ["1", "2", "3"])
        self.assertEqual(postorder[:3], [str(depth), str(depth - 1), str(depth - 2)])
        self.assertFalse(pre_meta.get("depth_limited"))
        self.assertFalse(in_meta.get("depth_limited"))
        self.assertFalse(post_meta.get("depth_limited"))

    def test_traverse_for_dot_escapes_quotes_in_labels(self):
        root = MockSBValue(
            'say "hi"',
            {"left": None, "right": None, "value": MockSBValue('say "hi"')},
        )

        dot_lines, _ = PreOrderTreeStrategy().traverse_for_dot(root)
        dot = "\n".join(dot_lines)

        self.assertIn('\\"hi\\"', dot)

    def test_traverse_for_dot_reports_depth_limit(self):
        original_depth_limit = g_config.tree_max_depth
        g_config.tree_max_depth = 1
        try:
            root = _make_right_skewed_tree(4)
            _, metadata = PreOrderTreeStrategy().traverse_for_dot(root)
        finally:
            g_config.tree_max_depth = original_depth_limit

        self.assertTrue(metadata.get("depth_limited"))
        self.assertTrue(metadata.get("truncated"))


# This allows running the test file directly.
if __name__ == "__main__":
    unittest.main()
