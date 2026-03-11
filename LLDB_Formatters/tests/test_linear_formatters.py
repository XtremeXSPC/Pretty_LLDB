import unittest
from unittest.mock import Mock

from LLDB_Formatters.config import g_config
from LLDB_Formatters.linear import (
    linear_container_summary_provider,
    vector_summary_provider,
)
from LLDB_Formatters.tests.mock_lldb import MockSBValue


class MockVectorSBValue(MockSBValue):
    def __init__(self, children, address_map):
        super().__init__(children=children, type_name="std::vector<int>")
        self._address_map = address_map

    def CreateValueFromAddress(self, name, address, elem_type):
        return self._address_map.get(address)


class TestLinearFormatters(unittest.TestCase):
    def test_linear_summary_appends_diagnostics_when_enabled(self):
        original_diagnostics_enabled = g_config.diagnostics_enabled
        g_config.diagnostics_enabled = True
        try:
            node3 = MockSBValue(30, {"value": MockSBValue(30), "next": None}, name="node3")
            node2 = MockSBValue(20, {"value": MockSBValue(20), "next": node3}, name="node2")
            list_value = MockSBValue(
                children={"head": node2, "size": MockSBValue(2)},
                name="my_list",
                type_name="MyList<int>",
            )

            summary = linear_container_summary_provider(list_value, {})

            self.assertIn("size = 2", summary)
            self.assertIn("[20 -> 30]", summary)
            self.assertIn("diag:", summary)
            self.assertIn("container_head=head", summary)
            self.assertIn("node_next=next", summary)
        finally:
            g_config.diagnostics_enabled = original_diagnostics_enabled

    def test_vector_summary_uses_global_summary_limit(self):
        original_summary_max_items = g_config.summary_max_items
        g_config.summary_max_items = 2
        try:
            elem_type = Mock()
            elem_type.GetByteSize.return_value = 8

            begin_ptr = MockSBValue(0x1000, is_pointer=True, name="__begin_")
            begin_ptr.GetType().GetPointeeType.return_value = elem_type
            end_ptr = MockSBValue(0x1018, is_pointer=True, name="__end_")
            end_cap_ptr = MockSBValue(0x1020, is_pointer=True, name="__end_cap_")

            address_map = {
                0x1000: MockSBValue(10, name="[0]"),
                0x1008: MockSBValue(20, name="[1]"),
                0x1010: MockSBValue(30, name="[2]"),
            }
            vector_value = MockVectorSBValue(
                children={
                    "__begin_": begin_ptr,
                    "__end_": end_ptr,
                    "__end_cap_": end_cap_ptr,
                },
                address_map=address_map,
            )

            summary = vector_summary_provider(vector_value, {})

            self.assertIn("size = 3", summary)
            self.assertIn("capacity = 4", summary)
            self.assertIn("data = 0x1000", summary)
            self.assertIn("[10, 20, ...]", summary)
        finally:
            g_config.summary_max_items = original_summary_max_items


if __name__ == "__main__":
    unittest.main()
