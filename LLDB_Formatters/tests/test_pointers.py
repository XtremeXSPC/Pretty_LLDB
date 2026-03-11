import unittest

from LLDB_Formatters.extraction import extract_linear_structure, extract_tree_structure
from LLDB_Formatters.helpers import _safe_get_node_from_pointer, get_raw_pointer
from LLDB_Formatters.pointers import resolve_pointer_like
from LLDB_Formatters.tests.mock_lldb import MockSBValue


def make_raw_pointer(pointee, name="ptr"):
    if pointee is None:
        return MockSBValue(value=0, is_pointer=True, name=name)
    return MockSBValue(value=id(pointee), is_pointer=True, name=name, pointee=pointee)


def make_libstdcxx_shared_ptr(pointee, name="shared_ptr"):
    return MockSBValue(
        children={"_M_ptr": make_raw_pointer(pointee, name="_M_ptr")},
        name=name,
        type_name="std::shared_ptr<int>",
    )


def make_libcxx_unique_ptr(pointee, name="unique_ptr"):
    return MockSBValue(
        children={
            "__ptr_": MockSBValue(
                children={"__value_": make_raw_pointer(pointee, name="__value_")},
                name="__ptr_",
            )
        },
        name=name,
        type_name="std::__1::unique_ptr<int>",
    )


class TestPointerResolution(unittest.TestCase):
    def test_resolve_raw_pointer(self):
        node = MockSBValue(42, {"value": MockSBValue(42)}, name="node")
        ptr = make_raw_pointer(node)

        resolution = resolve_pointer_like(ptr)

        self.assertEqual(resolution.kind, "raw_pointer")
        self.assertEqual(resolution.address, id(node))
        self.assertIs(resolution.pointee, node)

    def test_resolve_libstdcxx_shared_ptr_storage(self):
        node = MockSBValue(42, {"value": MockSBValue(42)}, name="node")
        shared_ptr = make_libstdcxx_shared_ptr(node)

        resolution = resolve_pointer_like(shared_ptr)

        self.assertEqual(resolution.kind, "wrapped_pointer")
        self.assertEqual(resolution.address, id(node))
        self.assertEqual(resolution.matched_path, ("_M_ptr",))
        self.assertIs(_safe_get_node_from_pointer(shared_ptr), node)

    def test_resolve_libcxx_unique_ptr_nested_storage(self):
        node = MockSBValue(99, {"value": MockSBValue(99)}, name="node")
        unique_ptr = make_libcxx_unique_ptr(node)

        resolution = resolve_pointer_like(unique_ptr)

        self.assertEqual(resolution.kind, "wrapped_pointer")
        self.assertEqual(resolution.address, id(node))
        self.assertEqual(resolution.matched_path, ("__ptr_", "__value_"))
        self.assertIs(_safe_get_node_from_pointer(unique_ptr), node)

    def test_extract_linear_structure_with_unique_ptr_head_and_next(self):
        node3 = MockSBValue(
            30,
            {
                "value": MockSBValue(30),
                "next": make_libcxx_unique_ptr(None, name="next"),
            },
            name="node3",
        )
        node2 = MockSBValue(
            20,
            {
                "value": MockSBValue(20),
                "next": make_libcxx_unique_ptr(node3, name="next"),
            },
            name="node2",
        )
        linear = MockSBValue(
            children={"head": make_libcxx_unique_ptr(node2, name="head"), "size": MockSBValue(2)},
            type_name="MyLinkedList<int>",
        )

        extraction = extract_linear_structure(linear, max_items=10)

        self.assertEqual([node.value for node in extraction.nodes], ["20", "30"])
        self.assertEqual(extraction.size, 2)
        self.assertFalse(extraction.is_empty)

    def test_extract_tree_structure_with_unique_ptr_root_and_children(self):
        left = MockSBValue(
            1,
            {
                "value": MockSBValue(1),
                "left": make_libcxx_unique_ptr(None, name="left"),
                "right": make_libcxx_unique_ptr(None, name="right"),
            },
            name="left",
        )
        right = MockSBValue(
            3,
            {
                "value": MockSBValue(3),
                "left": make_libcxx_unique_ptr(None, name="left"),
                "right": make_libcxx_unique_ptr(None, name="right"),
            },
            name="right",
        )
        root = MockSBValue(
            2,
            {
                "value": MockSBValue(2),
                "left": make_libcxx_unique_ptr(left, name="left"),
                "right": make_libcxx_unique_ptr(right, name="right"),
            },
            name="root",
        )
        tree = MockSBValue(
            children={"root": make_libcxx_unique_ptr(root, name="root"), "size": MockSBValue(3)},
            type_name="MyTree<int>",
        )

        extraction = extract_tree_structure(tree)

        self.assertEqual(sorted(node.value for node in extraction.nodes), ["1", "2", "3"])
        self.assertEqual(len(extraction.edges), 2)
        self.assertEqual(extraction.child_mode, "binary")

    def test_vector_capacity_can_read_nested_pointer_storage(self):
        pointee = MockSBValue(7, name="buffer")
        end_cap = MockSBValue(
            children={"__value_": make_raw_pointer(pointee, name="__value_")},
            name="__end_cap_",
        )

        self.assertEqual(get_raw_pointer(end_cap), id(pointee))


if __name__ == "__main__":
    unittest.main()
