import tempfile
import unittest
from pathlib import Path

from LLDB_Formatters.tests.lldb_integration import (
    RUNTIME_ROOT,
    build_fixture,
    run_lldb_batch,
    strip_ansi,
)


class TestLLDBIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            cls.binary_path = build_fixture("lldb_smoke.cpp")
        except FileNotFoundError as error:
            raise unittest.SkipTest(f"LLDB integration fixture setup failed: {error}")
        except RuntimeError as error:
            raise unittest.SkipTest(str(error))

    def _run_commands(self, commands):
        result = run_lldb_batch(self.binary_path, commands)
        combined_output = strip_ansi(f"{result.stdout}\n{result.stderr}")
        if (
            result.returncode != 0
            and "error: process exited with status -1 (no such process)" in combined_output
        ):
            raise unittest.SkipTest(
                "LLDB process launch is blocked in the current execution environment."
            )
        self.assertEqual(
            result.returncode,
            0,
            msg=f"LLDB batch command failed.\nOutput:\n{combined_output}",
        )
        self.assertNotIn(
            "error: unable to find type",
            combined_output.lower(),
            msg=f"Formatter import or summary registration failed.\nOutput:\n{combined_output}",
        )
        return combined_output

    def test_import_and_linear_summary(self):
        output = self._run_commands(["frame variable my_list"])

        self.assertIn("my_list = size = 3", output)
        self.assertIn("[10 -> 20 -> 30]", output)

    def test_tree_summary_uses_real_lldb_values(self):
        output = self._run_commands(["frame variable my_tree"])

        self.assertIn("my_tree = size = 3", output)
        self.assertIn("[2 -> 1 -> 3] (preorder)", output)

    def test_formatter_config_can_enable_diagnostics(self):
        output = self._run_commands(
            [
                "formatter_config diagnostics_enabled true",
                "frame variable my_list",
            ]
        )

        self.assertIn("Set diagnostics_enabled -> True", output)
        self.assertIn("diag:", output)
        self.assertIn("container_head=head", output)
        self.assertIn("node_next=next", output)

    def test_formatter_explain_reports_real_tree_resolution(self):
        output = self._run_commands(["formatter_explain my_tree"])

        self.assertIn("Detected kind: tree", output)
        self.assertIn("container_root -> root", output)
        self.assertIn("node_left -> left", output)
        self.assertIn("node_right -> right", output)
        self.assertIn("Extracted nodes: 3", output)

    def test_export_graph_command_creates_dot_output(self):
        output_file = Path(
            tempfile.mkdtemp(prefix="graph-export-", dir=RUNTIME_ROOT)
        ) / "graph.dot"
        output = self._run_commands([f"export_graph my_graph {output_file}"])

        self.assertIn("Successfully exported graph", output)
        self.assertTrue(output_file.exists(), "Expected graph.dot to be created.")

        dot_content = output_file.read_text(encoding="utf-8")
        self.assertIn('label="10"', dot_content)
        self.assertIn('label="20"', dot_content)
        self.assertIn('label="30"', dot_content)
        self.assertIn("->", dot_content)


if __name__ == "__main__":
    unittest.main()
