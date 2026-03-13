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

from .helpers import get_child_member_by_names


@dataclass
class VectorStorageLayout:
    """Describe the resolved pointer fields for one `std::vector` layout."""

    abi_family: str = "unknown"
    begin_ptr: Optional[object] = None
    end_ptr: Optional[object] = None
    end_cap_ptr: Optional[object] = None


def resolve_vector_storage_layout(valobj) -> VectorStorageLayout:
    """Resolve vector storage pointers for common libc++ and libstdc++ layouts."""

    begin_ptr = get_child_member_by_names(valobj, ["__begin_", "__begin"])
    end_ptr = get_child_member_by_names(valobj, ["__end_", "__end"])
    end_cap_ptr = get_child_member_by_names(valobj, ["__end_cap_", "__end_cap"])
    if begin_ptr and end_ptr:
        return VectorStorageLayout(
            abi_family="libcxx",
            begin_ptr=begin_ptr,
            end_ptr=end_ptr,
            end_cap_ptr=end_cap_ptr,
        )

    impl = get_child_member_by_names(valobj, ["_M_impl"])
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
    return VectorStorageLayout(
        abi_family="unknown",
        begin_ptr=begin_ptr,
        end_ptr=end_ptr,
        end_cap_ptr=end_cap_ptr,
    )
