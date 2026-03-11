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

MAX_POINTER_RESOLUTION_DEPTH = 6


@dataclass
class PointerResolution:
    address: int = 0
    pointee: Optional[object] = None
    kind: str = "invalid"
    matched_path: Tuple[str, ...] = ()

    @property
    def is_null(self) -> bool:
        return self.address == 0


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


def _get_named_child(value, name):
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
    base_value = get_nonsynthetic_value(value)
    if not base_value or not base_value.IsValid():
        return 0

    try:
        return base_value.GetNumChildren()
    except Exception:
        return 0


def _safe_child_at_index(value, index):
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
    if not value or not value.IsValid():
        return None

    try:
        return value.GetName()
    except Exception:
        return None


def _safe_object_address(value) -> int:
    if not value or not value.IsValid():
        return 0

    try:
        return value.GetAddress().GetFileAddress()
    except Exception:
        return 0


def _safe_dereference(value):
    if not value or not value.IsValid():
        return None

    try:
        pointee = value.Dereference()
    except Exception:
        return None

    if pointee and pointee.IsValid():
        return pointee
    return None


def _resolve_pointer_impl(value, allow_object_address, depth, seen_ids):
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

    if allow_object_address:
        return PointerResolution(
            address=_safe_object_address(base_value),
            pointee=base_value,
            kind="object_address_fallback",
        )

    return PointerResolution()


def resolve_pointer_like(value, allow_object_address=True) -> PointerResolution:
    return _resolve_pointer_impl(
        value,
        allow_object_address=allow_object_address,
        depth=0,
        seen_ids=set(),
    )


def get_raw_pointer(value) -> int:
    return resolve_pointer_like(value).address


def dereference_pointer_like(value):
    resolution = resolve_pointer_like(value)
    if resolution.kind == "invalid" or resolution.is_null:
        return None
    return resolution.pointee
