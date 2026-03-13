# ============================================================================ #
"""
Diagnostic reporting helpers for Pretty LLDB.

This module turns extraction diagnostics into user-facing reports and exposes
the `formatter_explain` command used to inspect how the formatter recognized a
value during a real LLDB session.

Author: XtremeXSPC
Version: 0.5.0.dev0
"""
# ============================================================================ #

from .command_helpers import resolve_command_variable
from .extraction import (
    ExtractedGraphStructure,
    ExtractedLinearStructure,
    ExtractedTreeStructure,
    detect_structure_kind,
    extract_supported_structure,
)


def _append_resolution_lines(lines, extraction):
    """Append the resolved field-role mappings recorded during extraction."""

    lines.append("Resolved fields:")
    for resolution in extraction.diagnostics.field_resolutions:
        matched = resolution.matched if resolution.matched else "<unresolved>"
        lines.append(f"  - {resolution.role} -> {matched}")


def _append_warning_lines(lines, extraction):
    """Append extraction warnings, or an explicit `none` marker when absent."""

    if not extraction.diagnostics.warnings:
        lines.append("Warnings:")
        lines.append("  - none")
        return

    lines.append("Warnings:")
    for warning in extraction.diagnostics.warnings:
        lines.append(f"  - {warning.code}: {warning.message}")


def format_extraction_report(var_name: str, valobj, structure_kind: str, extraction) -> str:
    """Build a human-readable explanation report for one extracted structure."""

    lines = [
        f"Formatter explanation for '{var_name}'",
        f"Type: {valobj.GetTypeName()}",
        f"Detected kind: {structure_kind}",
    ]

    if isinstance(extraction, ExtractedLinearStructure):
        lines.extend(
            [
                f"Empty: {'yes' if extraction.is_empty else 'no'}",
                f"Reported size: {extraction.size if extraction.size is not None else 'N/A'}",
                f"Extracted nodes: {len(extraction.nodes)}",
                f"Doubly linked: {'yes' if extraction.is_doubly_linked else 'no'}",
                f"Cycle detected: {'yes' if extraction.cycle_detected else 'no'}",
                f"Truncated: {'yes' if extraction.truncated else 'no'}",
            ]
        )
    elif isinstance(extraction, ExtractedTreeStructure):
        lines.extend(
            [
                f"Empty: {'yes' if extraction.is_empty else 'no'}",
                f"Reported size: {extraction.size if extraction.size is not None else 'N/A'}",
                f"Root address: {f'0x{extraction.root_address:x}' if extraction.root_address else 'N/A'}",
                f"Extracted nodes: {len(extraction.nodes)}",
                f"Extracted edges: {len(extraction.edges)}",
                f"Child mode: {extraction.child_mode if extraction.child_mode else 'unknown'}",
            ]
        )
    elif isinstance(extraction, ExtractedGraphStructure):
        lines.extend(
            [
                f"Empty: {'yes' if extraction.is_empty else 'no'}",
                f"Reported node count: {extraction.num_nodes if extraction.num_nodes is not None else 'N/A'}",
                f"Reported edge count: {extraction.num_edges if extraction.num_edges is not None else 'N/A'}",
                f"Extracted nodes: {len(extraction.nodes)}",
                f"Extracted edges: {len(extraction.edges)}",
            ]
        )

    if extraction.error_message:
        lines.append(f"Error: {extraction.error_message}")

    _append_resolution_lines(lines, extraction)
    _append_warning_lines(lines, extraction)
    return "\n".join(lines)


def formatter_explain_command(debugger, command, result, internal_dict):
    """Implement the `formatter_explain` LLDB command for supported structures."""

    _, var_name, valobj = resolve_command_variable(
        debugger,
        command,
        result,
        "formatter_explain",
    )
    if not valobj:
        return

    structure_kind = detect_structure_kind(valobj)
    if not structure_kind:
        result.SetError(
            f"Could not infer a supported structure kind for '{var_name}'. Supported kinds: linear, tree, graph."
        )
        return

    _, extraction = extract_supported_structure(valobj)
    result.AppendMessage(format_extraction_report(var_name, valobj, structure_kind, extraction))
