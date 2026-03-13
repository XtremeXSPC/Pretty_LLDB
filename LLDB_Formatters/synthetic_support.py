# ============================================================================ #
"""
Synthetic-child support helpers for Pretty LLDB.

This module contains the small utility functions shared by synthetic providers
to create stable child entries and to translate LLDB child names back into the
indices used by the synthetic expansion APIs.

Author: XtremeXSPC
Version: 0.5.0.dev0
"""
# ============================================================================ #


def create_synthetic_child(container_valobj, child_name, child_address, child_value):
    """
    Create one synthetic child entry for a formatter provider.

    When the current LLDB runtime exposes `CreateValueFromAddress`, the helper
    uses it to create a child with a stable index-based display name. If that
    facility is unavailable, or if LLDB refuses the synthetic creation, the
    already-resolved child value is returned as a safe fallback.
    """
    if not child_value or not child_value.IsValid():
        return None

    create_value = getattr(container_valobj, "CreateValueFromAddress", None)
    if callable(create_value):
        try:
            synthetic_child = create_value(child_name, child_address, child_value.GetType())
            if synthetic_child and synthetic_child.IsValid():
                return synthetic_child
        except Exception:
            pass

    return child_value


def parse_synthetic_child_index(name):
    """Translate an LLDB synthetic child name like `[3]` into an integer index."""

    if not name:
        return -1

    token = name.strip()
    if token.startswith("[") and token.endswith("]"):
        token = token[1:-1]

    if not token.isdigit():
        return -1
    return int(token)
