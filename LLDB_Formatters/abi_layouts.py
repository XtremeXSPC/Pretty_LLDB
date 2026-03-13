# ============================================================================ #
"""
ABI-specific layout helpers for Pretty LLDB.

This module isolates standard-library field layout probing that would otherwise
leak into formatter logic, starting with the storage layout resolution required
to summarize `std::vector` across common libc++ and libstdc++ implementations.

Author: XtremeXSPC
Version: 0.5.0.dev0
"""
# ============================================================================ #

from dataclasses import dataclass
from typing import Optional

from .helpers import _find_descendant_child_by_names, get_child_member_by_names
from .pointers import get_raw_pointer


@dataclass
class VectorStorageLayout:
    """Describe the resolved pointer fields for one `std::vector` layout."""

    abi_family: str = "unknown"
    begin_ptr: Optional[object] = None
    end_ptr: Optional[object] = None
    end_cap_ptr: Optional[object] = None


def _safe_type_name(value) -> str:
    """Return the LLDB type name for a value, or an empty string on failure."""

    if not value or not value.IsValid():
        return ""

    try:
        return value.GetTypeName() or ""
    except Exception:
        return ""


def _looks_like_vector_type(value) -> bool:
    """Return whether a value looks like a `std::vector`-style container."""

    return "vector<" in _safe_type_name(value).lower()


def _safe_num_children(value) -> int:
    """Return the visible child count for a value, or zero on LLDB failure."""

    if not value or not value.IsValid():
        return 0

    try:
        return value.GetNumChildren()
    except Exception:
        return 0


def _iter_visible_children(value, max_items=None):
    """Return the visible child values LLDB exposes directly on `value`."""

    child_count = _safe_num_children(value)
    if max_items is not None:
        child_count = min(child_count, max_items)

    children = []
    for index in range(child_count):
        try:
            child = value.GetChildAtIndex(index)
        except Exception:
            child = None
        if child and child.IsValid():
            children.append(child)
    return children


def resolve_vector_storage_layout(valobj) -> VectorStorageLayout:
    """Resolve vector storage pointers for common libc++ and libstdc++ layouts."""

    begin_ptr = get_child_member_by_names(valobj, ["__begin_", "__begin"])
    end_ptr = get_child_member_by_names(valobj, ["__end_", "__end"])
    end_cap_ptr = get_child_member_by_names(valobj, ["__end_cap_", "__end_cap"])
    if not begin_ptr or not end_ptr:
        begin_ptr = _find_descendant_child_by_names(valobj, ["__begin_", "__begin"])
        end_ptr = _find_descendant_child_by_names(valobj, ["__end_", "__end"])
        end_cap_ptr = _find_descendant_child_by_names(valobj, ["__end_cap_", "__end_cap"])
    if begin_ptr and end_ptr:
        return VectorStorageLayout(
            abi_family="libcxx",
            begin_ptr=begin_ptr,
            end_ptr=end_ptr,
            end_cap_ptr=end_cap_ptr,
        )

    impl = get_child_member_by_names(valobj, ["_M_impl"])
    if not impl:
        impl = _find_descendant_child_by_names(valobj, ["_M_impl"])
    if impl and impl.IsValid():
        begin_ptr = get_child_member_by_names(impl, ["_M_start"])
        end_ptr = get_child_member_by_names(impl, ["_M_finish"])
        end_cap_ptr = get_child_member_by_names(impl, ["_M_end_of_storage"])
        if begin_ptr and end_ptr:
            return VectorStorageLayout(
                abi_family="libstdcxx",
                begin_ptr=begin_ptr,
                end_ptr=end_ptr,
                end_cap_ptr=end_cap_ptr,
            )

    begin_ptr = get_child_member_by_names(valobj, ["_M_start"])
    end_ptr = get_child_member_by_names(valobj, ["_M_finish"])
    end_cap_ptr = get_child_member_by_names(valobj, ["_M_end_of_storage"])
    if not begin_ptr or not end_ptr:
        begin_ptr = _find_descendant_child_by_names(valobj, ["_M_start"])
        end_ptr = _find_descendant_child_by_names(valobj, ["_M_finish"])
        end_cap_ptr = _find_descendant_child_by_names(valobj, ["_M_end_of_storage"])
    return VectorStorageLayout(
        abi_family="unknown",
        begin_ptr=begin_ptr,
        end_ptr=end_ptr,
        end_cap_ptr=end_cap_ptr,
    )


def iter_vector_storage_values(valobj, max_items=None):
    """
    Materialize vector elements from resolved storage pointers.

    The helper returns `None` when the value does not expose a recognizable
    vector layout. Empty vectors are represented as an empty list.
    """

    storage = resolve_vector_storage_layout(valobj)
    if not storage.begin_ptr or not storage.end_ptr:
        return None

    try:
        begin_type = storage.begin_ptr.GetType()
    except Exception:
        begin_type = None
    if not begin_type or not begin_type.IsPointerType():
        return None

    try:
        elem_type = begin_type.GetPointeeType()
        element_size = elem_type.GetByteSize()
    except Exception:
        return None

    if not elem_type or element_size <= 0:
        return None

    begin_addr = get_raw_pointer(storage.begin_ptr)
    end_addr = get_raw_pointer(storage.end_ptr)
    if end_addr < begin_addr:
        return None

    element_count = (end_addr - begin_addr) // element_size
    if max_items is not None:
        element_count = min(element_count, max_items)

    values = []
    for index in range(element_count):
        element_addr = begin_addr + (index * element_size)
        try:
            element = valobj.CreateValueFromAddress(f"[{index}]", element_addr, elem_type)
        except Exception:
            element = None
        if element and element.IsValid():
            values.append(element)
    return values


def iter_container_values(valobj, max_items=None):
    """
    Return the logical elements of a container as LLDB values.

    `std::vector`-style containers are iterated through their storage pointers
    so debug-wrapper implementations do not leak internal bookkeeping nodes.
    All other containers fall back to LLDB-visible indexed children.
    """

    if _looks_like_vector_type(valobj):
        vector_values = iter_vector_storage_values(valobj, max_items=max_items)
        if vector_values is not None:
            return vector_values
    return _iter_visible_children(valobj, max_items=max_items)
