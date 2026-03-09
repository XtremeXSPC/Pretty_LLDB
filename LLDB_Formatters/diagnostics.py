import shlex
from typing import Tuple

from .extraction import (
    ExtractedGraphStructure,
    ExtractedLinearStructure,
    ExtractedTreeStructure,
    detect_structure_kind,
    extract_supported_structure,
)


def _get_frame(debugger, result):
    frame = debugger.GetSelectedTarget().GetProcess().GetSelectedThread().GetSelectedFrame()
    if not frame.IsValid():
        result.SetError("Cannot execute command: invalid execution context.")
        return None
    return frame


def _get_variable_from_command(debugger, command, result):
    args = shlex.split(command)
    if not args:
        result.SetError("Usage: formatter_explain <variable_name>")
        return None, None

    frame = _get_frame(debugger, result)
    if not frame:
        return None, None

    var_name = args[0]
    valobj = frame.FindVariable(var_name)
    if not valobj or not valobj.IsValid():
        result.SetError(f"Could not find variable '{var_name}'.")
        return None, None

    return var_name, valobj


def _append_resolution_lines(lines, extraction):
    lines.append("Resolved fields:")
    for resolution in extraction.diagnostics.field_resolutions:
        matched = resolution.matched if resolution.matched else "<unresolved>"
        lines.append(f"  - {resolution.role} -> {matched}")


def _append_warning_lines(lines, extraction):
    if not extraction.diagnostics.warnings:
        lines.append("Warnings:")
        lines.append("  - none")
        return

    lines.append("Warnings:")
    for warning in extraction.diagnostics.warnings:
        lines.append(f"  - {warning.code}: {warning.message}")


def format_extraction_report(var_name: str, valobj, structure_kind: str, extraction) -> str:
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
    var_name, valobj = _get_variable_from_command(debugger, command, result)
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
