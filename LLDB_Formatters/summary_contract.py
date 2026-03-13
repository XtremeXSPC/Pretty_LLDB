# ============================================================================ #
"""
Shared summary-formatting contract helpers for Pretty LLDB.

This module centralizes the small pieces of summary policy that must stay
consistent across formatter families, such as unsupported-layout markers and
the logic used to append the `[incomplete]` marker when warnings are hidden
from the user-facing summary text.

Author: XtremeXSPC
Version: 0.5.0.dev0
"""
# ============================================================================ #

SUMMARY_UNSUPPORTED_LAYOUT_MARKER = "[unsupported layout]"
SUMMARY_INCOMPLETE_MARKER = "[incomplete]"

_STRUCTURE_LABELS = {
    "linear": "Linear structure",
    "tree": "Tree",
    "graph": "Graph",
    "list": "List",
}


def structure_label(structure_kind):
    """Return the user-facing label associated with a structure kind token."""

    return _STRUCTURE_LABELS.get(structure_kind, "Structure")


def unsupported_layout_summary(structure_kind, diagnostics_suffix=""):
    """Build the standardized summary used for unsupported structure layouts."""

    return (
        f"{structure_label(structure_kind)} {SUMMARY_UNSUPPORTED_LAYOUT_MARKER}{diagnostics_suffix}"
    )


def hidden_warning_codes(extraction, visible_warning_codes=()):
    """Return extraction warning codes that are not already surfaced elsewhere."""

    if not extraction or not getattr(extraction, "diagnostics", None):
        return []

    visible = set(visible_warning_codes)
    return [
        warning.code for warning in extraction.diagnostics.warnings if warning.code not in visible
    ]


def append_incomplete_marker(summary, extraction, visible_warning_codes=()):
    """Append `[incomplete]` when the extraction contains hidden warning states."""

    if hidden_warning_codes(extraction, visible_warning_codes):
        return f"{summary} {SUMMARY_INCOMPLETE_MARKER}"
    return summary
