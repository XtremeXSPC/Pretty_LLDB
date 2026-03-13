# ============================================================================ #
"""
Pointer-resolution helpers for Pretty LLDB.

This module isolates the logic required to interpret raw pointers and common
pointer-like wrapper layouts exposed by LLDB, including smart-pointer internals
and defensive fallbacks used when the formatter must recover an object address
from non-pointer storage.

Author: XtremeXSPC
Version: 0.5.0.dev0
"""
# ============================================================================ #

from dataclasses import dataclass
from typing import Optional, Tuple

DIRECT_POINTER_FIELDS = (
    "_M_ptr",
    "__ptr_",
    "pointer",
    "__value_",
    "__first_",
    "first",
)

WRAPPER_FIELDS = (
    "_M_t",
    "__compressed_pair",
    "__compressed_pair_elem",
    "__value_",
    "__ptr_",
    "__base_",
    "__first_",
    "first",
    "_M_head_impl",
    "_M_storage",
)

POINTER_WRAPPER_TYPE_TOKENS = (
    "unique_ptr",
    "shared_ptr",
    "weak_ptr",
    "__uniq_ptr",
    "__shared_ptr",
    "_tuple_impl",
    "_head_base",
    "compressed_pair",
)

MAX_POINTER_RESOLUTION_DEPTH = 6


@dataclass
class PointerResolution:
    """Describe the result of resolving a raw or wrapped pointer-like value."""

    address: int = 0
    pointee: Optional[object] = None
    kind: str = "invalid"
    matched_path: Tuple[str, ...] = ()

    @property
    def is_null(self) -> bool:
        """Return whether the resolved pointer address is explicitly null."""

        return self.address == 0


def get_nonsynthetic_value(value):
    """
    Return the non-synthetic backing value behind an LLDB display object.

    When LLDB exposes synthetic children, the formatter often needs to inspect
    the underlying storage fields instead. This helper performs that fallback
    transparently and returns the original value when no non-synthetic view is
    available.
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


def _get_named_child(value, name):
    """Return one named child from the non-synthetic value when it exists."""

    base_value = get_nonsynthetic_value(value)
    if not base_value or not base_value.IsValid():
        return None

    try:
        child = base_value.GetChildMemberWithName(name)
    except Exception:
        return None

    if child and child.IsValid():
        return child
    return None


def _safe_num_children(value) -> int:
    """Return the child count of a value, falling back to zero on failure."""

    base_value = get_nonsynthetic_value(value)
    if not base_value or not base_value.IsValid():
        return 0

    try:
        return base_value.GetNumChildren()
    except Exception:
        return 0


def _safe_child_at_index(value, index):
    """Return one child by index, suppressing LLDB lookup failures."""

    base_value = get_nonsynthetic_value(value)
    if not base_value or not base_value.IsValid():
        return None

    try:
        child = base_value.GetChildAtIndex(index)
    except Exception:
        return None

    if child and child.IsValid():
        return child
    return None


def _safe_child_name(value) -> Optional[str]:
    """Return a child name if LLDB can provide it safely."""

    if not value or not value.IsValid():
        return None

    try:
        return value.GetName()
    except Exception:
        return None


def _safe_object_address(value) -> int:
    """Return the file address of an LLDB object, or zero if unavailable."""

    if not value or not value.IsValid():
        return 0

    try:
        return value.GetAddress().GetFileAddress()
    except Exception:
        return 0


def _safe_dereference(value):
    """Dereference a pointer-like value and return the pointee when valid."""

    if not value or not value.IsValid():
        return None

    try:
        pointee = value.Dereference()
    except Exception:
        return None

    if pointee and pointee.IsValid():
        return pointee
    return None


def _safe_type_name(value) -> str:
    """Return the LLDB type name for a value, or an empty string on failure."""

    if not value or not value.IsValid():
        return ""

    try:
        return value.GetTypeName() or ""
    except Exception:
        return ""


def _looks_like_pointer_wrapper_type(type_name: str) -> bool:
    """Return whether a type name appears to be part of a smart-pointer wrapper chain."""

    lowered = type_name.lower()
    return any(token in lowered for token in POINTER_WRAPPER_TYPE_TOKENS)


def _resolve_pointer_impl(value, allow_object_address, depth, seen_ids):
    """Recursively resolve raw pointers and wrapper fields into one pointee."""

    base_value = get_nonsynthetic_value(value)
    if not base_value or not base_value.IsValid():
        return PointerResolution()

    if depth > MAX_POINTER_RESOLUTION_DEPTH:
        return PointerResolution()

    base_id = id(base_value)
    if base_id in seen_ids:
        return PointerResolution()
    seen_ids = seen_ids | {base_id}

    try:
        if base_value.GetType().IsPointerType():
            address = base_value.GetValueAsUnsigned()
            pointee = _safe_dereference(base_value) if address else None
            return PointerResolution(
                address=address,
                pointee=pointee,
                kind="raw_pointer",
            )
    except Exception:
        pass

    type_name = _safe_type_name(base_value)

    for field_name in DIRECT_POINTER_FIELDS:
        child = _get_named_child(base_value, field_name)
        if not child:
            continue
        resolved = _resolve_pointer_impl(
            child,
            allow_object_address=False,
            depth=depth + 1,
            seen_ids=seen_ids,
        )
        if resolved.kind != "invalid":
            return PointerResolution(
                address=resolved.address,
                pointee=resolved.pointee,
                kind="wrapped_pointer",
                matched_path=(field_name,) + resolved.matched_path,
            )

    for field_name in WRAPPER_FIELDS:
        child = _get_named_child(base_value, field_name)
        if not child:
            continue
        resolved = _resolve_pointer_impl(
            child,
            allow_object_address=False,
            depth=depth + 1,
            seen_ids=seen_ids,
        )
        if resolved.kind != "invalid":
            return PointerResolution(
                address=resolved.address,
                pointee=resolved.pointee,
                kind="wrapped_pointer",
                matched_path=(field_name,) + resolved.matched_path,
            )

    candidate_names = set(DIRECT_POINTER_FIELDS + WRAPPER_FIELDS)
    for index in range(_safe_num_children(base_value)):
        child = _safe_child_at_index(base_value, index)
        if not child:
            continue
        child_name = _safe_child_name(child)
        if child_name not in candidate_names:
            continue
        resolved = _resolve_pointer_impl(
            child,
            allow_object_address=False,
            depth=depth + 1,
            seen_ids=seen_ids,
        )
        if resolved.kind != "invalid":
            matched_path = resolved.matched_path
            if child_name:
                matched_path = (child_name,) + matched_path
            return PointerResolution(
                address=resolved.address,
                pointee=resolved.pointee,
                kind="wrapped_pointer",
                matched_path=matched_path,
            )

    if _looks_like_pointer_wrapper_type(type_name) or not allow_object_address:
        for index in range(_safe_num_children(base_value)):
            child = _safe_child_at_index(base_value, index)
            if not child:
                continue
            resolved = _resolve_pointer_impl(
                child,
                allow_object_address=False,
                depth=depth + 1,
                seen_ids=seen_ids,
            )
            if resolved.kind != "invalid":
                child_name = _safe_child_name(child)
                matched_path = resolved.matched_path
                if child_name:
                    matched_path = (child_name,) + matched_path
                return PointerResolution(
                    address=resolved.address,
                    pointee=resolved.pointee,
                    kind="wrapped_pointer",
                    matched_path=matched_path,
                )

    if allow_object_address:
        return PointerResolution(
            address=_safe_object_address(base_value),
            pointee=base_value,
            kind="object_address_fallback",
        )

    return PointerResolution()


def resolve_pointer_like(value, allow_object_address=True) -> PointerResolution:
    """Resolve a pointer-like value into an address, pointee, and match metadata."""

    return _resolve_pointer_impl(
        value,
        allow_object_address=allow_object_address,
        depth=0,
        seen_ids=set(),
    )


def get_raw_pointer(value) -> int:
    """Return the raw address resolved from a pointer-like value."""

    return resolve_pointer_like(value).address


def dereference_pointer_like(value):
    """Return the resolved pointee object for a pointer-like value."""

    resolution = resolve_pointer_like(value)
    if resolution.kind == "invalid" or resolution.is_null:
        return None
    return resolution.pointee
