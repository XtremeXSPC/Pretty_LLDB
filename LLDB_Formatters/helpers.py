# ============================================================================ #
"""
Shared low-level helpers for Pretty LLDB.

This module collects the utility functions used across the formatter package:
LLDB value inspection helpers, debug logging support, ANSI color constants, and
display-oriented rendering helpers for common STL-like payloads.

Author: XtremeXSPC
Version: 0.5.0.dev0
"""
# ============================================================================ #

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
    """ANSI escape sequences used by console-oriented formatter output."""

    RESET = "\x1b[0m"
    BOLD_CYAN = "\x1b[1;36m"
    YELLOW = "\x1b[33m"
    GREEN = "\x1b[32m"
    MAGENTA = "\x1b[35m"
    RED = "\x1b[31m"


SUMMARY_CYCLE_MARKER = "[CYCLE]"
SUMMARY_TRUNCATION_MARKER = "..."
_TYPE_FIELD_NAME_CACHE = {}


def debug_print(message):
    """Emit a formatter debug message only when debug logging is enabled."""

    if getattr(g_config, "debug_enabled", False):
        print(f"[Formatter Debug] {message}")


# --------------------------- Generic Helpers --------------------------- #


def should_use_colors():
    """
    Return whether console output should include ANSI color codes.

    The formatter currently treats the VS Code terminal environment as the
    primary signal that colored console output is appropriate.
    """
    if os.environ.get("NO_COLOR") is not None:
        return False

    if (os.environ.get("TERM") or "").lower() == "dumb":
        return False

    return os.environ.get("TERM_PROGRAM") == "vscode"


def type_has_field(type_obj, field_name):
    """
    Check whether an `SBType` exposes a field with the requested name.

    The helper inspects the type metadata directly instead of relying on child
    lookup, which can be less predictable for synthetic or display-oriented
    values.
    """
    if not type_obj:
        return False

    try:
        hash(type_obj)
        cache_key = type_obj
    except Exception:
        cache_key = id(type_obj)
    field_names = _TYPE_FIELD_NAME_CACHE.get(cache_key)
    if field_names is None:
        names = set()
        try:
            field_count = type_obj.GetNumberOfFields()
        except Exception:
            field_count = 0

        for index in range(field_count):
            try:
                field = type_obj.GetFieldAtIndex(index)
                name = field.GetName() if field else None
            except Exception:
                name = None
            if name:
                names.add(name)

        field_names = frozenset(names)
        _TYPE_FIELD_NAME_CACHE[cache_key] = field_names

    return field_name in field_names


def get_child_member_by_names(value, names):
    """
    Return the first valid child matching one of the provided candidate names.

    The lookup is performed on the non-synthetic view of the value so the
    formatter can inspect the real storage fields rather than presentation-only
    children.
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
    """Resolve a child from the display value first, then fall back to raw lookup."""

    if not value or not value.IsValid():
        return None

    for name in names:
        child = value.GetChildMemberWithName(name)
        if child and child.IsValid():
            return child

    return get_child_member_by_names(value, names)


def _normalize_summary_text(summary):
    """Normalize LLDB summary text by trimming whitespace and outer quotes."""

    if summary is None:
        return None

    normalized = summary.strip()
    if len(normalized) >= 2 and normalized[0] == normalized[-1] == '"':
        return normalized[1:-1]
    return normalized


def _safe_type_name(value_child):
    """Read a value type name without propagating LLDB access failures."""

    try:
        return value_child.GetTypeName() or ""
    except Exception:
        return ""


def _safe_value_text(value_child):
    """Read the raw value text from an `SBValue` while swallowing LLDB errors."""

    try:
        return value_child.GetValue()
    except Exception:
        return None


def _safe_num_children(value_child):
    """Read the child count of an `SBValue` with a defensive fallback to zero."""

    try:
        return value_child.GetNumChildren()
    except Exception:
        return 0


def _safe_child_name(value_child):
    """Read a child name while tolerating LLDB exceptions."""

    try:
        return value_child.GetName()
    except Exception:
        return None


def _safe_child_at_index(value_child, index):
    """Read one child by index while tolerating LLDB exceptions."""

    try:
        return value_child.GetChildAtIndex(index)
    except Exception:
        return None


def _looks_like_std_type(type_name, token):
    """Return whether a type name appears to contain the requested STL token."""

    return token in type_name.lower()


def _get_nested_child_by_paths(value_child, paths):
    """Follow candidate field paths and return the first valid nested child found."""

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
    """Search descendants recursively for one child matching any candidate name."""

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
    """Interpret a value or summary text as a boolean-like flag when possible."""

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
    """Render an optional-like STL wrapper using its engaged flag and payload."""

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
    """Render a pair-like object as `(first, second)` when its fields are visible."""

    first = _get_display_child_by_names(value_child, ["first"])
    second = _get_display_child_by_names(value_child, ["second"])
    if not first and not second:
        return None

    first_summary = get_value_summary(first) if first else "?"
    second_summary = get_value_summary(second) if second else "?"
    return f"({first_summary}, {second_summary})"


def _render_tuple_like(value_child):
    """Render tuple-like children in index order when LLDB exposes them directly."""

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
    """Render a string-view-like object using its visible size metadata."""

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
    Return the best display string available for one `SBValue`.

    The helper prefers high-level LLDB summaries, but it also contains targeted
    handling for optional-like, pair-like, tuple-like, and string-view-like
    standard-library values so user-facing formatter output avoids leaking
    internal implementation details whenever possible.
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
    Resolve a pointer-like node reference and dereference it safely.

    The helper accepts raw pointers, smart pointers, and pointer-like wrappers
    handled by the pointer-resolution layer, while also emitting debug details
    that explain how the dereference was resolved.
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
    Return child node references from either n-ary or binary tree layouts.

    The helper first looks for a container-style `children` member and, when it
    is absent, falls back to the classic `left` / `right` binary-tree fields.
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
