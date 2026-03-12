import tempfile
import unittest
from pathlib import Path

from LLDB_Formatters.tests.lldb_integration import (
    RUNTIME_ROOT,
    available_compiler_variants,
    build_fixture,
    classify_vector_abi_from_output,
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
        return self._run_commands_for_binary(self.binary_path, commands)

    def _run_commands_for_binary(self, binary_path, commands):
        result = run_lldb_batch(binary_path, commands)
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

    def test_linear_synthetic_children_are_available_in_real_lldb(self):
        output = self._run_commands(
            [
                (
                    "script frame = lldb.debugger.GetSelectedTarget().GetProcess()."
                    "GetSelectedThread().GetSelectedFrame(); "
                    'value = frame.FindVariable("my_list").GetSyntheticValue(); '
                    "child0 = value.GetChildAtIndex(0); child1 = value.GetChildAtIndex(1); "
                    'print("SYN_LIST_CHILDREN", value.GetNumChildren()); '
                    'print("SYN_LIST_CHILD0", child0.GetName(), child0.GetChildMemberWithName("value").GetValue()); '
                    'print("SYN_LIST_CHILD1", child1.GetName(), child1.GetChildMemberWithName("value").GetValue())'
                )
            ]
        )

        self.assertIn("SYN_LIST_CHILDREN 3", output)
        self.assertIn("SYN_LIST_CHILD0 [0] 10", output)
        self.assertIn("SYN_LIST_CHILD1 [1] 20", output)

    def test_tree_synthetic_children_follow_configured_traversal_in_real_lldb(self):
        output = self._run_commands(
            [
                "formatter_config tree_traversal_strategy inorder",
                (
                    "script frame = lldb.debugger.GetSelectedTarget().GetProcess()."
                    "GetSelectedThread().GetSelectedFrame(); "
                    'value = frame.FindVariable("my_tree").GetSyntheticValue(); '
                    "child0 = value.GetChildAtIndex(0); child1 = value.GetChildAtIndex(1); child2 = value.GetChildAtIndex(2); "
                    'print("SYN_TREE_CHILDREN", value.GetNumChildren()); '
                    'print("SYN_TREE_VALUES", '
                    'child0.GetChildMemberWithName("value").GetValue(), '
                    'child1.GetChildMemberWithName("value").GetValue(), '
                    'child2.GetChildMemberWithName("value").GetValue())'
                ),
            ]
        )

        self.assertIn("Set tree_traversal_strategy -> 'inorder'", output)
        self.assertIn("SYN_TREE_CHILDREN 3", output)
        self.assertIn("SYN_TREE_VALUES 1 2 3", output)

    def test_string_payload_list_summary_uses_real_lldb_values(self):
        output = self._run_commands(["frame variable my_string_list"])

        self.assertIn("my_string_list = size = 3", output)
        self.assertIn("[alpha -> beta -> gamma]", output)

    def test_optional_payload_list_summary_uses_real_lldb_values(self):
        output = self._run_commands(["frame variable my_optional_list"])

        self.assertIn("my_optional_list = size = 3", output)
        self.assertIn("[10 -> nullopt -> 30]", output)

    def test_pair_payload_tree_summary_uses_real_lldb_values(self):
        output = self._run_commands(["frame variable my_pair_tree"])

        self.assertIn("my_pair_tree = size = 3", output)
        self.assertIn("(2, 20)", output)
        self.assertIn("(1, 10)", output)
        self.assertIn("(3, 30)", output)

    def test_vector_summary_uses_real_lldb_values(self):
        output = self._run_commands(["frame variable my_vector"])

        self.assertIn("my_vector = size = 4", output)
        self.assertIn("[1, 2, 3, 4]", output)

    def test_string_vector_summary_uses_real_lldb_values(self):
        output = self._run_commands(["frame variable my_string_vector"])

        self.assertIn("my_string_vector = size = 3", output)
        self.assertIn("[red, green, blue]", output)

    def test_available_vector_abi_variants_report_supported_layouts(self):
        variants = available_compiler_variants()
        if not variants:
            raise unittest.SkipTest("No compiler variants available for ABI probing.")

        exercised = 0
        observed_abis = set()
        for variant in variants:
            try:
                binary_path = build_fixture("lldb_smoke.cpp", compiler_variant=variant)
            except RuntimeError:
                continue

            with self.subTest(variant=variant.name):
                output = self._run_commands_for_binary(
                    binary_path,
                    ["frame variable my_vector", "frame variable --raw my_vector"],
                )
                self.assertIn("my_vector = size = 4", output)
                self.assertIn("[1, 2, 3, 4]", output)

                abi_family = classify_vector_abi_from_output(output)
                self.assertIn(
                    abi_family,
                    {"libcxx", "libstdcxx"},
                    msg=f"Could not classify std::vector ABI for variant '{variant.name}'.",
                )
                if variant.expected_abi:
                    self.assertEqual(
                        abi_family,
                        variant.expected_abi,
                        msg=f"Expected ABI '{variant.expected_abi}' for variant '{variant.name}'.",
                    )

                observed_abis.add(abi_family)
                exercised += 1

        if exercised == 0:
            raise unittest.SkipTest("No ABI-specific compiler variants could be built.")

        self.assertTrue(observed_abis)

    def test_smart_list_summary_uses_real_lldb_values(self):
        output = self._run_commands(["frame variable my_smart_list"])

        self.assertIn("my_smart_list = size = 3", output)
        self.assertIn("[10 -> 20 -> 30]", output)

    def test_smart_tree_summary_uses_real_lldb_values(self):
        output = self._run_commands(["frame variable my_smart_tree"])

        self.assertIn("my_smart_tree = size = 3", output)
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
        output_file = Path(tempfile.mkdtemp(prefix="graph-export-", dir=RUNTIME_ROOT)) / "graph.dot"
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
