import unittest
from unittest.mock import Mock, patch

from LLDB_Formatters.config import g_config
from LLDB_Formatters.diagnostics import formatter_explain_command
from LLDB_Formatters.extraction import ExtractedLinearStructure
from LLDB_Formatters.tests.mock_lldb import MockSBValue
from LLDB_Formatters.tree import tree_summary_provider


class MockResult:
    def __init__(self):
        self.messages = []
        self.error = None

    def AppendMessage(self, message):
        self.messages.append(message)

    def SetError(self, error):
        self.error = error


def _make_debugger_for_value(name, value):
    frame = Mock()
    frame.IsValid.return_value = True
    frame.FindVariable.side_effect = lambda variable_name: value if variable_name == name else None

    thread = Mock()
    thread.GetSelectedFrame.return_value = frame

    process = Mock()
    process.GetSelectedThread.return_value = thread

    target = Mock()
    target.GetProcess.return_value = process

    debugger = Mock()
    debugger.GetSelectedTarget.return_value = target
    return debugger


class TestDiagnostics(unittest.TestCase):
    def test_formatter_explain_command_reports_linear_matches(self):
        node3 = MockSBValue(30, {"value": MockSBValue(30), "next": None}, name="node3")
        node2 = MockSBValue(20, {"value": MockSBValue(20), "next": node3}, name="node2")
        list_value = MockSBValue(
            children={"head": node2, "size": MockSBValue(2)},
            name="my_list",
            type_name="MyList<int>",
        )
        debugger = _make_debugger_for_value("my_list", list_value)
        result = MockResult()

        formatter_explain_command(debugger, "my_list", result, {})

        self.assertIsNone(result.error)
        rendered = "\n".join(result.messages)
        self.assertIn("Detected kind: linear", rendered)
        self.assertIn("container_head -> head", rendered)
        self.assertIn("node_next -> next", rendered)
        self.assertIn("Extracted nodes: 2", rendered)

    def test_tree_summary_appends_diagnostics_when_enabled(self):
        original_diagnostics_enabled = g_config.diagnostics_enabled
        g_config.diagnostics_enabled = True
        try:
            left = MockSBValue(1, {"value": MockSBValue(1)}, name="left")
            right = MockSBValue(3, {"value": MockSBValue(3)}, name="right")
            root = MockSBValue(
                2,
                {"left": left, "right": right, "value": MockSBValue(2)},
                name="root",
            )
            tree_value = MockSBValue(
                children={"root": root, "size": MockSBValue(3)},
                name="my_tree",
                type_name="MyBinaryTree<int>",
            )

            summary = tree_summary_provider(tree_value, {})

            self.assertIn("diag:", summary)
            self.assertIn("container_root=root", summary)
            self.assertIn("node_left=left", summary)
            self.assertIn("node_right=right", summary)
        finally:
            g_config.diagnostics_enabled = original_diagnostics_enabled

    def test_formatter_explain_reuses_detected_structure_kind(self):
        value = MockSBValue(
            children={"head": MockSBValue(0, is_pointer=True), "size": MockSBValue(0)},
            name="my_list",
            type_name="MyList<int>",
        )
        debugger = _make_debugger_for_value("my_list", value)
        result = MockResult()

        with patch("LLDB_Formatters.diagnostics.detect_structure_kind", return_value="linear"):
            with patch(
                "LLDB_Formatters.diagnostics.extract_supported_structure",
                return_value=("linear", ExtractedLinearStructure()),
            ) as extract_mock:
                formatter_explain_command(debugger, "my_list", result, {})

        self.assertIsNone(result.error)
        extract_mock.assert_called_once_with(value, structure_kind="linear")


if __name__ == "__main__":
    unittest.main()
