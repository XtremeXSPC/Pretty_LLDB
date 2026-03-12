# ----------------------------------------------------------------------- #
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
# ----------------------------------------------------------------------- #

import os

from .config import g_config
from .pointers import (
    dereference_pointer_like,
    get_nonsynthetic_value,
    get_raw_pointer,
    resolve_pointer_like,
)


# ----- ANSI Color Codes ----- #
# A simple class to hold ANSI escape sequences for colored console output.
class Colors:
    RESET = "\x1b[0m"
    BOLD_CYAN = "\x1b[1;36m"
    YELLOW = "\x1b[33m"
    GREEN = "\x1b[32m"
    MAGENTA = "\x1b[35m"
    RED = "\x1b[31m"


SUMMARY_CYCLE_MARKER = "[CYCLE]"
SUMMARY_TRUNCATION_MARKER = "..."


def debug_print(message):
    """Prints a message only if debugging is enabled."""
    if getattr(g_config, "debug_enabled", False):
        print(f"[Formatter Debug] {message}")


# --------------------------- Generic Helpers --------------------------- #


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


def _get_display_child_by_names(value, names):
    if not value or not value.IsValid():
        return None

    for name in names:
        child = value.GetChildMemberWithName(name)
        if child and child.IsValid():
            return child

    return get_child_member_by_names(value, names)


def _normalize_summary_text(summary):
    if summary is None:
        return None

    normalized = summary.strip()
    if len(normalized) >= 2 and normalized[0] == normalized[-1] == '"':
        return normalized[1:-1]
    return normalized


def _safe_type_name(value_child):
    try:
        return value_child.GetTypeName() or ""
    except Exception:
        return ""


def _safe_value_text(value_child):
    try:
        return value_child.GetValue()
    except Exception:
        return None


def _safe_num_children(value_child):
    try:
        return value_child.GetNumChildren()
    except Exception:
        return 0


def _safe_child_name(value_child):
    try:
        return value_child.GetName()
    except Exception:
        return None


def _safe_child_at_index(value_child, index):
    try:
        return value_child.GetChildAtIndex(index)
    except Exception:
        return None


def _looks_like_std_type(type_name, token):
    return token in type_name.lower()


def _get_nested_child_by_paths(value_child, paths):
    for path in paths:
        current = value_child
        for field_name in path:
            current = _get_display_child_by_names(current, [field_name])
            if not current:
                break
        if current and current.IsValid():
            return current
    return None


def _find_descendant_child_by_names(value_child, names, max_depth=6, seen_ids=None):
    if max_depth < 0 or not value_child or not value_child.IsValid():
        return None

    if seen_ids is None:
        seen_ids = set()

    value_id = id(value_child)
    if value_id in seen_ids:
        return None
    seen_ids = seen_ids | {value_id}

    direct = _get_display_child_by_names(value_child, names)
    if direct:
        return direct

    for index in range(_safe_num_children(value_child)):
        child = _safe_child_at_index(value_child, index)
        if not child or not child.IsValid():
            continue
        found = _find_descendant_child_by_names(
            child,
            names,
            max_depth=max_depth - 1,
            seen_ids=seen_ids,
        )
        if found:
            return found

    return None


def _parse_bool_like(child):
    if not child or not child.IsValid():
        return None

    raw_text = _safe_value_text(child)
    if raw_text is None or raw_text == "":
        raw_text = child.GetSummary()
    if raw_text is None or raw_text == "":
        return None

    normalized = _normalize_summary_text(str(raw_text)).lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    return None


def _render_optional_like(value_child):
    engaged_child = _get_nested_child_by_paths(
        value_child,
        [
            ("__engaged_",),
            ("__has_value_",),
            ("has_value",),
            ("_M_engaged",),
            ("_M_payload", "_M_engaged"),
            ("_M_payload", "_M_payload", "_M_engaged"),
        ],
    )
    if not engaged_child:
        engaged_child = _find_descendant_child_by_names(
            value_child,
            ["__engaged_", "__has_value_", "has_value", "_M_engaged"],
        )
    engaged = _parse_bool_like(engaged_child)
    if engaged is False:
        return "nullopt"

    value_member = _get_nested_child_by_paths(
        value_child,
        [
            ("__val_",),
            ("__value_",),
            ("Value",),
            ("_M_value",),
            ("value",),
            ("_M_payload", "_M_value"),
            ("_M_payload", "__value_"),
            ("_M_payload", "_M_payload", "_M_value"),
        ],
    )
    if not value_member:
        value_member = _find_descendant_child_by_names(
            value_child,
            ["__val_", "__value_", "Value", "_M_value", "value"],
        )
    if value_member and value_member.IsValid():
        return get_value_summary(value_member)

    return None


def _render_pair_like(value_child):
    first = _get_display_child_by_names(value_child, ["first"])
    second = _get_display_child_by_names(value_child, ["second"])
    if not first and not second:
        return None

    first_summary = get_value_summary(first) if first else "?"
    second_summary = get_value_summary(second) if second else "?"
    return f"({first_summary}, {second_summary})"


def _render_tuple_like(value_child):
    items = []
    for index in range(_safe_num_children(value_child)):
        child = value_child.GetChildAtIndex(index)
        if not child or not child.IsValid():
            continue
        child_name = _safe_child_name(child)
        if child_name and (child_name.startswith("[") or child_name.isdigit()):
            items.append(get_value_summary(child))

    if items:
        return f"({', '.join(items)})"
    return None


def _render_string_view_like(value_child):
    size_member = _get_display_child_by_names(
        value_child,
        ["__size_", "_M_len", "size", "_M_size"],
    )
    if not size_member:
        return None

    try:
        size_value = size_member.GetValueAsUnsigned()
    except Exception:
        size_value = None

    if size_value is None:
        return None
    return f"string_view(size={size_value})"


def get_value_summary(value_child):
    """
    Extracts a displayable string from a value SBValue. It prefers the
    type's summary (e.g., for std::string) but falls back to its raw value.
    """
    if not value_child or not value_child.IsValid():
        return f"{Colors.RED}[invalid]{Colors.RESET}"

    type_name = _safe_type_name(value_child)

    if _looks_like_std_type(type_name, "optional<"):
        optional_summary = _render_optional_like(value_child)
        if optional_summary is not None:
            return optional_summary

    if _looks_like_std_type(type_name, "pair<"):
        pair_summary = _render_pair_like(value_child)
        if pair_summary is not None:
            return pair_summary

    if _looks_like_std_type(type_name, "tuple<"):
        tuple_summary = _render_tuple_like(value_child)
        if tuple_summary is not None:
            return tuple_summary

    # GetSummary() often provides a better representation (e.g., for strings)
    # and we normalize quotes for cleaner display inside our own formatting.
    summary = value_child.GetSummary()
    if summary:
        return _normalize_summary_text(summary)

    if _looks_like_std_type(type_name, "string_view"):
        string_view_summary = _render_string_view_like(value_child)
        if string_view_summary is not None:
            return string_view_summary

    # Fallback to GetValue() if no summary is available.
    raw_value = _safe_value_text(value_child)
    if raw_value not in (None, ""):
        return raw_value

    return f"{Colors.RED}[unavailable]{Colors.RESET}"


# ----------------- Tree-specific Helpers (Centralized) ----------------- #


def _safe_get_node_from_pointer(node_ptr):
    """
    Safely gets the underlying TreeNode struct from an SBValue that can be
    a raw pointer or a smart pointer, returning the SBValue for the struct.
    """
    if not node_ptr or not node_ptr.IsValid():
        return None

    resolution = resolve_pointer_like(node_ptr)
    if resolution.kind == "invalid" or resolution.is_null:
        return None

    if resolution.kind == "object_address_fallback":
        debug_print("   - Using object-address fallback for non-pointer node storage.")
    elif resolution.matched_path:
        debug_print(
            f"   - Pointer resolver matched {'/'.join(resolution.matched_path)} "
            f"({resolution.kind})."
        )
    else:
        debug_print(f"   - Pointer resolver matched {resolution.kind}.")

    return dereference_pointer_like(node_ptr)


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
