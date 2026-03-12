SUMMARY_UNSUPPORTED_LAYOUT_MARKER = "[unsupported layout]"
SUMMARY_INCOMPLETE_MARKER = "[incomplete]"

_STRUCTURE_LABELS = {
    "linear": "Linear structure",
    "tree": "Tree",
    "graph": "Graph",
    "list": "List",
}


def structure_label(structure_kind):
    return _STRUCTURE_LABELS.get(structure_kind, "Structure")


def unsupported_layout_summary(structure_kind, diagnostics_suffix=""):
    return f"{structure_label(structure_kind)} {SUMMARY_UNSUPPORTED_LAYOUT_MARKER}{diagnostics_suffix}"


def hidden_warning_codes(extraction, visible_warning_codes=()):
    if not extraction or not getattr(extraction, "diagnostics", None):
        return []

    visible = set(visible_warning_codes)
    return [
        warning.code
        for warning in extraction.diagnostics.warnings
        if warning.code not in visible
    ]


def append_incomplete_marker(summary, extraction, visible_warning_codes=()):
    if hidden_warning_codes(extraction, visible_warning_codes):
        return f"{summary} {SUMMARY_INCOMPLETE_MARKER}"
    return summary
