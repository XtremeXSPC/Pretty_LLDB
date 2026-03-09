# ---------------------------------------------------------------------- #
# FILE: helpers.py
#
# DESCRIPTION:
# This module provides a collection of shared utility functions, global
# configuration variables, and constants used across the entire
# 'LLDB_Formatters' package.
#
# It centralizes common logic to avoid code duplication and includes:
#   - Generic helper functions to interact with LLDB's SBValue and SBType.
#   - Access to the global configuration object 'g_config'.
#   - ANSI color code definitions for colored console output.
#   - A conditional debug printing utility.
# ---------------------------------------------------------------------- #

import os

from .config import g_config


# ----- ANSI Color Codes ----- #
# A simple class to hold ANSI escape sequences for colored console output.
class Colors:
    RESET = "\x1b[0m"
    BOLD_CYAN = "\x1b[1;36m"
    YELLOW = "\x1b[33m"
    GREEN = "\x1b[32m"
    MAGENTA = "\x1b[35m"
    RED = "\x1b[31m"


def debug_print(message):
    """Prints a message only if debugging is enabled."""
    if getattr(g_config, "debug_enabled", False):
        print(f"[Formatter Debug] {message}")


# -------------------------- Generic Helpers --------------------------- #


def should_use_colors():
    """
    Returns True if the script is likely running in a terminal that
    supports ANSI color codes (like CodeLLDB's debug console or a standard terminal).
    Checks for the 'TERM_PROGRAM' environment variable set by VS Code.
    """
    return os.environ.get("TERM_PROGRAM") == "vscode"


def type_has_field(type_obj, field_name):
    """
    Checks if an SBType has a data member with the given name by iterating
    through its fields. This is more reliable than GetChildMemberWithName.
    """
    for i in range(type_obj.GetNumberOfFields()):
        if type_obj.GetFieldAtIndex(i).GetName() == field_name:
            return True
    return False


def get_nonsynthetic_value(value):
    """
    Returns the non-synthetic backing value when LLDB exposes a synthetic
    provider for the object. Falls back to the original value otherwise.
    """
    if not value or not value.IsValid():
        return value

    try:
        nonsynthetic = value.GetNonSyntheticValue()
        if nonsynthetic and nonsynthetic.IsValid():
            return nonsynthetic
    except Exception:
        pass

    return value


def get_child_member_by_names(value, names):
    """
    Attempts to find and return the first valid child member from a list of
    possible common names (e.g., ["_head", "m_head", "head"]).
    """
    base_value = get_nonsynthetic_value(value)
    if not base_value or not base_value.IsValid():
        return None
    for name in names:
        child = base_value.GetChildMemberWithName(name)
        if child and child.IsValid():
            return child
    return None


def get_raw_pointer(value):
    """
    Extracts the raw memory address from an SBValue, correctly handling
    raw pointers, smart pointers (unique_ptr, shared_ptr), and other objects.
    """
    if not value or not value.IsValid():
        return 0

    # If it's already a pointer type, get its value.
    if value.GetType().IsPointerType():
        return value.GetValueAsUnsigned()

    # For smart pointers, find the internal raw pointer member.
    # Common names are '_M_ptr' (libstdc++), '__ptr_' (libc++), 'pointer'.
    ptr_member = get_child_member_by_names(value, ["_M_ptr", "__ptr_", "pointer"])
    if ptr_member and ptr_member.IsValid():
        return ptr_member.GetValueAsUnsigned()

    # As a fallback for other types, return the address of the object itself.
    return value.GetAddress().GetFileAddress()


def get_value_summary(value_child):
    """
    Extracts a displayable string from a value SBValue. It prefers the
    type's summary (e.g., for std::string) but falls back to its raw value.
    """
    if not value_child or not value_child.IsValid():
        return f"{Colors.RED}[invalid]{Colors.RESET}"

    # GetSummary() often provides a better representation (e.g., for strings)
    # and we strip quotes for cleaner display inside our own formatting.
    summary = value_child.GetSummary()
    if summary:
        return summary.strip('"')

    # Fallback to GetValue() if no summary is available.
    return value_child.GetValue()


# ---------------- Tree-specific Helpers (Centralized) ----------------- #


def _safe_get_node_from_pointer(node_ptr):
    """
    Safely gets the underlying TreeNode struct from an SBValue that can be
    a raw pointer or a smart pointer, returning the SBValue for the struct.
    """
    if not node_ptr or not node_ptr.IsValid():
        return None

    # Try to handle it as a smart pointer first by looking for an internal pointer.
    internal_ptr = get_child_member_by_names(node_ptr, ["_M_ptr", "__ptr_", "pointer"])
    if internal_ptr and internal_ptr.IsValid():
        debug_print("   - Smart pointer detected, dereferencing internal ptr.")
        return internal_ptr.Dereference()

    # Fallback for raw pointers, which can be dereferenced directly.
    debug_print("   - Assuming raw pointer, dereferencing directly.")
    return node_ptr.Dereference()


def _get_node_children(node_struct):
    """
    Gets a list of children for a given tree node SBValue. This function is
    adaptive and handles both n-ary trees (which have a 'children' container member)
    and binary trees (which have 'left' and 'right' members).

    Args:
        node_struct: The SBValue of the dereferenced node struct.

    Returns:
        A list of SBValue objects, where each is a pointer/smart_ptr to a child node.
    """
    children = []

    # First, attempt to find an n-ary style 'children' container (e.g., std::vector).
    children_container = get_child_member_by_names(node_struct, ["children", "m_children"])
    if (
        children_container
        and children_container.IsValid()
        and children_container.MightHaveChildren()
    ):
        for i in range(children_container.GetNumChildren()):
            child = children_container.GetChildAtIndex(i)
            # Ensure the child is a valid pointer before adding.
            if child and get_raw_pointer(child) != 0:
                children.append(child)
        return children

    # If no 'children' container is found, fall back to binary tree style.
    left = get_child_member_by_names(node_struct, ["left", "m_left", "_left"])
    if left and get_raw_pointer(left) != 0:
        children.append(left)

    right = get_child_member_by_names(node_struct, ["right", "m_right", "_right"])
    if right and get_raw_pointer(right) != 0:
        children.append(right)

    return children
