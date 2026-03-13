import unittest
from unittest.mock import Mock

from LLDB_Formatters.config import g_config
from LLDB_Formatters.extraction import (
    extract_graph_structure,
    extract_linear_structure,
    extract_tree_structure,
)
from LLDB_Formatters.tests.mock_lldb import MockSBValue, MockSBValueContainer


def _make_raw_pointer(pointee, name="ptr", type_name="MockNode*"):
    if pointee is None:
        return MockSBValue(value=0, is_pointer=True, name=name, type_name=type_name)
    return MockSBValue(
        value=id(pointee),
        is_pointer=True,
        name=name,
        type_name=type_name,
        pointee=pointee,
    )


def _make_debug_vector(items, type_name="std::__debug::vector<MockNode*>"):
    elem_type = Mock()
    elem_type.GetByteSize.return_value = 8

    begin_addr = 0x1000
    address_map = {}
    for index, item in enumerate(items):
        address_map[begin_addr + (index * 8)] = _make_raw_pointer(item, name=f"[{index}]")

    begin_ptr = MockSBValue(begin_addr, is_pointer=True, name="_M_start", type_name="MockNode**")
    begin_ptr.GetType().GetPointeeType.return_value = elem_type
    end_ptr = MockSBValue(
        begin_addr + (len(items) * 8),
        is_pointer=True,
        name="_M_finish",
        type_name="MockNode**",
    )
    end_cap_ptr = MockSBValue(
        begin_addr + (len(items) * 8),
        is_pointer=True,
        name="_M_end_of_storage",
        type_name="MockNode**",
    )

    return MockSBValue(
        children={
            "safe": MockSBValue(name="safe", type_name="__gnu_debug::_Safe_container"),
            "base": MockSBValue(
                children={
                    "_M_impl": MockSBValue(
                        children={
                            "_M_start": begin_ptr,
                            "_M_finish": end_ptr,
                            "_M_end_of_storage": end_cap_ptr,
                        },
                        name="_M_impl",
                        type_name="_Vector_impl",
                    )
                },
                name="std::__cxx1998::vector<MockNode*>",
                type_name="std::__cxx1998::vector<MockNode*>",
            ),
            "cap": MockSBValue(name="cap", type_name="__gnu_debug::_Safe_vector"),
        },
        type_name=type_name,
        address_map=address_map,
    )


def _make_right_skewed_tree(depth):
    current = None
    for value in range(depth, 0, -1):
        current = MockSBValue(
            value,
            {"left": None, "right": current, "value": MockSBValue(value)},
        )
    return current


class TestExtractionLayer(unittest.TestCase):
    def test_extract_linear_structure_collects_nodes_and_diagnostics(self):
        node3 = MockSBValue(30, {"value": MockSBValue(30), "next": None, "prev": None})
        node2 = MockSBValue(20, {"value": MockSBValue(20), "next": node3, "prev": None})
        head = MockSBValue(children={"head": node2, "size": MockSBValue(2)})

        extraction = extract_linear_structure(head, max_items=10)

        self.assertEqual([node.value for node in extraction.nodes], ["20", "30"])
        self.assertEqual(extraction.size, 2)
        self.assertTrue(extraction.is_doubly_linked)
        self.assertEqual(extraction.head_field, "head")
        self.assertEqual(extraction.next_field, "next")
        self.assertEqual(extraction.value_field, "value")
        self.assertIn("container_head=head", extraction.diagnostics.compact_summary())

    def test_extract_linear_structure_reports_cycle(self):
        node3 = MockSBValue(30, {"value": MockSBValue(30)})
        node2 = MockSBValue(20, {"value": MockSBValue(20), "next": node3})
        head = MockSBValue(children={"head": node2})
        node3._children["next"] = node2

        extraction = extract_linear_structure(head, max_items=10)

        self.assertTrue(extraction.cycle_detected)
        self.assertEqual(
            [warning.code for warning in extraction.diagnostics.warnings], ["cycle_detected"]
        )

    def test_extract_tree_structure_builds_nodes_and_edges(self):
        left = MockSBValue(1, {"value": MockSBValue(1)})
        right = MockSBValue(3, {"value": MockSBValue(3)})
        root = MockSBValue(2, {"left": left, "right": right, "value": MockSBValue(2)})
        tree = MockSBValue(children={"root": root, "size": MockSBValue(3)})

        extraction = extract_tree_structure(tree)

        self.assertEqual(extraction.root_field, "root")
        self.assertEqual(extraction.size, 3)
        self.assertEqual(sorted(node.value for node in extraction.nodes), ["1", "2", "3"])
        self.assertEqual(len(extraction.edges), 2)
        self.assertEqual(extraction.child_mode, "binary")

    def test_extract_tree_structure_respects_depth_limit(self):
        original_depth_limit = g_config.tree_max_depth
        g_config.tree_max_depth = 2
        try:
            tree = MockSBValue(
                children={"root": _make_right_skewed_tree(6), "size": MockSBValue(6)}
            )
            extraction = extract_tree_structure(tree)
        finally:
            g_config.tree_max_depth = original_depth_limit

        self.assertEqual([node.value for node in extraction.nodes], ["1", "2", "3"])
        self.assertEqual([warning.code for warning in extraction.diagnostics.warnings], ["depth_limit_reached"])

    def test_extract_graph_structure_builds_directional_edges(self):
        node_c = MockSBValue(30, {"value": MockSBValue(30), "neighbors": MockSBValueContainer([])})
        node_b = MockSBValue(
            20, {"value": MockSBValue(20), "neighbors": MockSBValueContainer([node_c])}
        )
        node_a = MockSBValue(
            10,
            {
                "value": MockSBValue(10),
                "neighbors": MockSBValueContainer([node_b, node_c]),
            },
        )
        graph = MockSBValue(
            children={
                "nodes": MockSBValueContainer([node_a, node_b, node_c]),
                "num_nodes": MockSBValue(3),
            }
        )

        extraction = extract_graph_structure(graph)

        self.assertEqual(extraction.nodes_field, "nodes")
        self.assertEqual(extraction.num_nodes, 3)
        addresses_by_value = {node.value: node.address for node in extraction.nodes}
        self.assertEqual(
            sorted((edge.source, edge.target) for edge in extraction.edges),
            sorted(
                [
                    (addresses_by_value["10"], addresses_by_value["20"]),
                    (addresses_by_value["10"], addresses_by_value["30"]),
                    (addresses_by_value["20"], addresses_by_value["30"]),
                ]
            ),
        )
        self.assertEqual(extraction.neighbors_field, "neighbors")

    def test_extract_graph_structure_supports_debug_vector_storage(self):
        node_c = MockSBValue(
            30,
            {
                "value": MockSBValue(30),
                "neighbors": _make_debug_vector([], type_name="std::__debug::vector<TestGraphNode<int>*>"),
            },
            type_name="TestGraphNode<int>",
        )
        node_b = MockSBValue(
            20,
            {
                "value": MockSBValue(20),
                "neighbors": _make_debug_vector([node_c], type_name="std::__debug::vector<TestGraphNode<int>*>"),
            },
            type_name="TestGraphNode<int>",
        )
        node_a = MockSBValue(
            10,
            {
                "value": MockSBValue(10),
                "neighbors": _make_debug_vector([node_b, node_c], type_name="std::__debug::vector<TestGraphNode<int>*>"),
            },
            type_name="TestGraphNode<int>",
        )
        graph = MockSBValue(
            children={
                "nodes": _make_debug_vector(
                    [node_a, node_b, node_c],
                    type_name="std::__debug::vector<TestGraphNode<int>*>",
                ),
                "num_nodes": MockSBValue(3),
            },
            type_name="MyGraph<int>",
        )

        extraction = extract_graph_structure(graph)

        self.assertEqual(sorted(node.value for node in extraction.nodes), ["10", "20", "30"])
        addresses_by_value = {node.value: node.address for node in extraction.nodes}
        self.assertEqual(
            sorted((edge.source, edge.target) for edge in extraction.edges),
            sorted(
                [
                    (addresses_by_value["10"], addresses_by_value["20"]),
                    (addresses_by_value["10"], addresses_by_value["30"]),
                    (addresses_by_value["20"], addresses_by_value["30"]),
                ]
            ),
        )
        self.assertEqual(extraction.neighbors_field, "neighbors")


if __name__ == "__main__":
    unittest.main()
