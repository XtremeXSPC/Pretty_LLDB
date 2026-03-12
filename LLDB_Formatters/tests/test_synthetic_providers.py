import unittest

from LLDB_Formatters.config import formatter_config_command, g_config
from LLDB_Formatters.linear import LinearProvider
from LLDB_Formatters.tests.mock_lldb import MockSBValue
from LLDB_Formatters.tree import TreeProvider


class MockResult:
    def __init__(self):
        self.messages = []
        self.error = None

    def AppendMessage(self, message):
        self.messages.append(message)

    def SetError(self, error):
        self.error = error


def _null_pointer(name):
    return MockSBValue(0, is_pointer=True, name=name, address=0)


def _linear_fixture():
    node3 = MockSBValue(
        children={"value": MockSBValue(30), "next": _null_pointer("next")},
        name="node3",
        address=0x3000,
        type_name="Node<int>",
    )
    node2 = MockSBValue(
        children={"value": MockSBValue(20), "next": node3},
        name="node2",
        address=0x2000,
        type_name="Node<int>",
    )
    node1 = MockSBValue(
        children={"value": MockSBValue(10), "next": node2},
        name="node1",
        address=0x1000,
        type_name="Node<int>",
    )
    address_map = {
        0x1000: node1,
        0x2000: node2,
        0x3000: node3,
    }
    container = MockSBValue(
        children={"head": node1, "size": MockSBValue(3)},
        name="my_list",
        type_name="MyList<int>",
        address_map=address_map,
    )
    return container


def _tree_fixture():
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
    address_map = {
        0x1100: left,
        0x1200: root,
        0x1300: right,
    }
    container = MockSBValue(
        children={"root": root, "size": MockSBValue(3)},
        name="my_tree",
        type_name="MyBinaryTree<int>",
        address_map=address_map,
    )
    return container


class TestSyntheticProviders(unittest.TestCase):
    def test_formatter_config_lists_synthetic_max_children(self):
        result = MockResult()

        formatter_config_command(None, "", result, {})

        rendered = "\n".join(result.messages)
        self.assertIn("synthetic_max_children", rendered)

    def test_linear_provider_exposes_indexed_children_in_list_order(self):
        original_limit = g_config.synthetic_max_children
        g_config.synthetic_max_children = 8
        try:
            provider = LinearProvider(_linear_fixture(), {})

            self.assertEqual(provider.num_children(), 3)

            first = provider.get_child_at_index(0)
            second = provider.get_child_at_index(1)
            third = provider.get_child_at_index(2)

            self.assertEqual(first.GetName(), "[0]")
            self.assertEqual(second.GetName(), "[1]")
            self.assertEqual(third.GetName(), "[2]")
            self.assertEqual(first.GetChildMemberWithName("value").GetSummary(), "10")
            self.assertEqual(second.GetChildMemberWithName("value").GetSummary(), "20")
            self.assertEqual(third.GetChildMemberWithName("value").GetSummary(), "30")
        finally:
            g_config.synthetic_max_children = original_limit

    def test_linear_provider_respects_synthetic_child_limit(self):
        original_limit = g_config.synthetic_max_children
        g_config.synthetic_max_children = 2
        try:
            provider = LinearProvider(_linear_fixture(), {})

            self.assertEqual(provider.num_children(), 2)
            self.assertEqual(provider.get_child_at_index(1).GetName(), "[1]")
            self.assertIsNone(provider.get_child_at_index(2))
        finally:
            g_config.synthetic_max_children = original_limit

    def test_tree_provider_follows_selected_traversal_strategy(self):
        original_strategy = g_config.tree_traversal_strategy
        original_limit = g_config.synthetic_max_children
        g_config.synthetic_max_children = 8
        try:
            tree_value = _tree_fixture()

            g_config.tree_traversal_strategy = "preorder"
            preorder_provider = TreeProvider(tree_value, {})
            preorder_values = [
                preorder_provider.get_child_at_index(index)
                .GetChildMemberWithName("value")
                .GetSummary()
                for index in range(preorder_provider.num_children())
            ]
            self.assertEqual(preorder_values, ["2", "1", "3"])

            g_config.tree_traversal_strategy = "inorder"
            inorder_provider = TreeProvider(tree_value, {})
            inorder_values = [
                inorder_provider.get_child_at_index(index)
                .GetChildMemberWithName("value")
                .GetSummary()
                for index in range(inorder_provider.num_children())
            ]
            self.assertEqual(inorder_values, ["1", "2", "3"])
        finally:
            g_config.tree_traversal_strategy = original_strategy
            g_config.synthetic_max_children = original_limit


if __name__ == "__main__":
    unittest.main()
