import unittest
from unittest.mock import Mock

from LLDB_Formatters.config import formatter_config_command
from LLDB_Formatters.diagnostics import formatter_explain_command
from LLDB_Formatters.graph import export_graph_command
from LLDB_Formatters.tests.mock_lldb import MockSBValue, MockSBValueContainer
from LLDB_Formatters.tree import export_tree_command, pptree_preorder_command
from LLDB_Formatters.web_visualizer import (
    export_graph_web_command,
    export_list_web_command,
    export_tree_web_command,
)


class MockResult:
    def __init__(self):
        self.messages = []
        self.error = None

    def AppendMessage(self, message):
        self.messages.append(message)

    def SetError(self, error):
        self.error = error


def _make_debugger(
    frame_valid=True, values=None, target_valid=True, process_valid=True, thread_valid=True
):
    if values is None:
        values = {}

    frame = Mock()
    frame.IsValid.return_value = frame_valid
    frame.FindVariable.side_effect = lambda variable_name: values.get(variable_name)

    thread = Mock()
    thread.IsValid.return_value = thread_valid
    thread.GetSelectedFrame.return_value = frame

    process = Mock()
    process.IsValid.return_value = process_valid
    process.GetSelectedThread.return_value = thread

    target = Mock()
    target.IsValid.return_value = target_valid
    target.GetProcess.return_value = process

    debugger = Mock()
    debugger.GetSelectedTarget.return_value = target
    return debugger


class TestCommandUX(unittest.TestCase):
    def test_formatter_explain_usage_is_specific(self):
        result = MockResult()

        formatter_explain_command(_make_debugger(), "", result, {})

        self.assertEqual(result.error, "Usage: formatter_explain <variable>")

    def test_export_graph_usage_is_specific(self):
        result = MockResult()

        export_graph_command(_make_debugger(), "", result, {})

        self.assertEqual(result.error, "Usage: export_graph <variable> [file.dot] [directed|undirected]")

    def test_webgraph_usage_is_specific(self):
        result = MockResult()

        export_graph_web_command(_make_debugger(), "", result, {})

        self.assertEqual(result.error, "Usage: webgraph <variable> [directed|undirected]")

    def test_webtree_usage_is_specific(self):
        result = MockResult()

        export_tree_web_command(_make_debugger(), "", result, {})

        self.assertEqual(result.error, "Usage: webtree <variable> [preorder|inorder|postorder]")

    def test_graph_commands_validate_mode_argument(self):
        graph_value = MockSBValue(
            children={
                "nodes": MockSBValueContainer([]),
                "num_nodes": MockSBValue(0),
                "num_edges": MockSBValue(0),
            },
            name="my_graph",
            type_name="MyGraph<int>",
        )
        debugger = _make_debugger(values={"my_graph": graph_value})

        for command_fn, command_text in [
            (export_graph_command, "my_graph graph.dot sideways"),
            (export_graph_web_command, "my_graph sideways"),
        ]:
            with self.subTest(command=command_fn.__name__):
                result = MockResult()
                command_fn(debugger, command_text, result, {})
                self.assertIn("Invalid graph mode 'sideways'.", result.error)

    def test_webtree_validates_traversal_argument(self):
        tree_value = MockSBValue(
            children={"root": MockSBValue(0, is_pointer=True), "size": MockSBValue(0)},
            name="my_tree",
            type_name="MyBinaryTree<int>",
        )
        debugger = _make_debugger(values={"my_tree": tree_value})
        result = MockResult()

        export_tree_web_command(debugger, "my_tree sideways", result, {})

        self.assertIn("Invalid tree traversal 'sideways'.", result.error)

    def test_formatter_config_usage_is_normalized(self):
        result = MockResult()

        formatter_config_command(None, "summary_max_items 10 extra", result, {})

        self.assertEqual(result.error, "Usage: formatter_config [<setting_name> [<value>]]")

    def test_formatter_config_can_inspect_single_setting(self):
        result = MockResult()

        formatter_config_command(None, "summary_max_items", result, {})

        rendered = "\n".join(result.messages)
        self.assertIn("summary_max_items = 30", rendered)
        self.assertIn("Type: integer", rendered)
        self.assertIn("Usage: formatter_config summary_max_items <integer>", rendered)

    def test_formatter_config_can_reset_defaults(self):
        set_result = MockResult()
        formatter_config_command(None, "summary_max_items 12", set_result, {})

        reset_result = MockResult()
        formatter_config_command(None, "reset", reset_result, {})

        inspect_result = MockResult()
        formatter_config_command(None, "summary_max_items", inspect_result, {})

        self.assertEqual(set_result.messages, ["Set summary_max_items -> 12"])
        self.assertEqual(reset_result.messages, ["Reset formatter settings to defaults."])
        self.assertIn("summary_max_items = 30", "\n".join(inspect_result.messages))

    def test_invalid_execution_context_is_shared_across_commands(self):
        debugger = _make_debugger(target_valid=False)
        commands = [
            (formatter_explain_command, "formatter_explain my_tree"),
            (pptree_preorder_command, "my_tree"),
            (export_tree_command, "my_tree tree.dot"),
            (export_graph_command, "my_graph graph.dot"),
            (export_tree_web_command, "my_tree"),
        ]

        for command_fn, command_text in commands:
            with self.subTest(command=command_fn.__name__):
                result = MockResult()
                command_fn(debugger, command_text, result, {})
                self.assertEqual(result.error, "Cannot execute command: no selected frame.")

    def test_missing_variable_message_is_shared_across_commands(self):
        debugger = _make_debugger(values={})
        commands = [
            (formatter_explain_command, "missing"),
            (pptree_preorder_command, "missing"),
            (export_tree_command, "missing out.dot"),
            (export_graph_command, "missing out.dot"),
            (export_list_web_command, "missing"),
        ]

        for command_fn, command_text in commands:
            with self.subTest(command=command_fn.__name__):
                result = MockResult()
                command_fn(debugger, command_text, result, {})
                self.assertEqual(result.error, "Could not find variable 'missing'.")

    def test_commands_support_quoted_variable_names(self):
        tree_value = MockSBValue(
            children={"root": MockSBValue(0, is_pointer=True), "size": MockSBValue(0)},
            name="quoted tree",
            type_name="MyBinaryTree<int>",
        )
        debugger = _make_debugger(values={"quoted tree": tree_value})
        result = MockResult()

        formatter_explain_command(debugger, '"quoted tree"', result, {})

        self.assertIsNone(result.error)
        self.assertTrue(result.messages)
        self.assertIn("Formatter explanation for 'quoted tree'", result.messages[0])

    def test_tree_commands_report_empty_tree_consistently(self):
        tree_value = MockSBValue(
            children={"root": MockSBValue(0, is_pointer=True), "size": MockSBValue(0)},
            name="empty_tree",
            type_name="MyBinaryTree<int>",
        )
        debugger = _make_debugger(values={"empty_tree": tree_value})

        for command_fn, command_text in [
            (pptree_preorder_command, "empty_tree"),
            (export_tree_command, "empty_tree tree.dot"),
        ]:
            with self.subTest(command=command_fn.__name__):
                result = MockResult()
                command_fn(debugger, command_text, result, {})
                self.assertEqual(result.messages, ["Tree is empty."])
                self.assertIsNone(result.error)

    def test_tree_commands_report_unsupported_layout_consistently(self):
        tree_value = MockSBValue(
            children={"size": MockSBValue(0)},
            name="broken_tree",
            type_name="MyBinaryTree<int>",
        )
        debugger = _make_debugger(values={"broken_tree": tree_value})

        for command_fn, command_text in [
            (pptree_preorder_command, "broken_tree"),
            (export_tree_command, "broken_tree tree.dot"),
            (export_tree_web_command, "broken_tree"),
        ]:
            with self.subTest(command=command_fn.__name__):
                result = MockResult()
                command_fn(debugger, command_text, result, {})
                self.assertEqual(result.error, "Tree layout is unsupported.")

    def test_export_graph_reports_empty_graph_consistently(self):
        graph_value = MockSBValue(
            children={
                "nodes": MockSBValueContainer([]),
                "num_nodes": MockSBValue(0),
                "num_edges": MockSBValue(0),
            },
            name="empty_graph",
            type_name="MyGraph<int>",
        )
        debugger = _make_debugger(values={"empty_graph": graph_value})
        result = MockResult()

        export_graph_command(debugger, "empty_graph graph.dot", result, {})

        self.assertEqual(result.messages, ["Graph is empty."])
        self.assertIsNone(result.error)

    def test_graph_commands_report_unsupported_layout_consistently(self):
        graph_value = MockSBValue(
            children={"num_nodes": MockSBValue(0)},
            name="broken_graph",
            type_name="MyGraph<int>",
        )
        debugger = _make_debugger(values={"broken_graph": graph_value})

        for command_fn, command_text in [
            (export_graph_command, "broken_graph graph.dot"),
            (export_graph_web_command, "broken_graph"),
        ]:
            with self.subTest(command=command_fn.__name__):
                result = MockResult()
                command_fn(debugger, command_text, result, {})
                self.assertEqual(result.error, "Graph layout is unsupported.")


if __name__ == "__main__":
    unittest.main()
