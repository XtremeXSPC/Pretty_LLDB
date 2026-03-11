import unittest

from LLDB_Formatters.helpers import get_value_summary
from LLDB_Formatters.linear import linear_container_summary_provider
from LLDB_Formatters.tests.mock_lldb import MockSBValue


def strip_ansi(text):
    return (
        text.replace("\x1b[33m", "")
        .replace("\x1b[32m", "")
        .replace("\x1b[31m", "")
        .replace("\x1b[1;36m", "")
        .replace("\x1b[0m", "")
    )


class TestValueRendering(unittest.TestCase):
    def test_string_summary_strips_outer_quotes(self):
        value = MockSBValue('"hello"', type_name="std::__1::string")

        self.assertEqual(get_value_summary(value), "hello")

    def test_pair_fallback_renders_first_and_second(self):
        pair_value = MockSBValue(
            children={"first": MockSBValue(1), "second": MockSBValue(2)},
            type_name="std::pair<int, int>",
        )

        self.assertEqual(get_value_summary(pair_value), "(1, 2)")

    def test_optional_fallback_renders_libcxx_engaged_value(self):
        optional_value = MockSBValue(
            children={"__engaged_": MockSBValue(1), "__val_": MockSBValue(42)},
            type_name="std::__1::optional<int>",
        )

        self.assertEqual(get_value_summary(optional_value), "42")

    def test_optional_fallback_renders_libstdcxx_disengaged_value(self):
        optional_value = MockSBValue(
            children={
                "_M_payload": MockSBValue(
                    children={"_M_engaged": MockSBValue(0), "_M_value": MockSBValue(7)}
                )
            },
            type_name="std::optional<int>",
        )

        self.assertEqual(get_value_summary(optional_value), "nullopt")

    def test_tuple_fallback_uses_indexed_children(self):
        tuple_value = MockSBValue(
            children={"[0]": MockSBValue(1, name="[0]"), "[1]": MockSBValue(2, name="[1]")},
            type_name="std::tuple<int, int>",
        )

        self.assertEqual(get_value_summary(tuple_value), "(1, 2)")

    def test_linear_summary_renders_pair_payloads(self):
        node2 = MockSBValue(
            0,
            {
                "value": MockSBValue(
                    children={"first": MockSBValue(2), "second": MockSBValue(20)},
                    type_name="std::pair<int, int>",
                ),
                "next": None,
            },
            type_name="MyListNode<std::pair<int, int>>",
        )
        list_value = MockSBValue(
            children={"head": node2, "size": MockSBValue(1)},
            type_name="MyList<std::pair<int, int>>",
        )

        summary = strip_ansi(linear_container_summary_provider(list_value, {}))

        self.assertIn("size = 1", summary)
        self.assertIn("[(2, 20)]", summary)


if __name__ == "__main__":
    unittest.main()
