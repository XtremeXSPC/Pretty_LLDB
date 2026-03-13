# ============================================================================ #
"""
Shared command-handling helpers for Pretty LLDB.

This module provides the common parsing, validation, and messaging logic used
by LLDB command entry points so they can report usage errors, resolve the
selected frame, and find variables in a consistent way.

Author: XtremeXSPC
Version: 0.5.0.dev0
"""
# ============================================================================ #

import os
import shlex

INVALID_EXECUTION_CONTEXT_ERROR = "Cannot execute command: no selected frame."


def usage_message(command_name, arguments=""):
    """Build a normalized usage string for an LLDB command."""

    arguments = arguments.strip()
    if arguments:
        return f"Usage: {command_name} {arguments}"
    return f"Usage: {command_name}"


def set_usage_error(result, command_name, arguments=""):
    """Write a usage error to an LLDB command result object."""

    result.SetError(usage_message(command_name, arguments))


def set_argument_parse_error(result, command_name, error):
    """Write a consistent argument-parsing error for malformed shell-like input."""

    result.SetError(f"Invalid arguments for '{command_name}': {error}.")


def missing_variable_message(var_name):
    """Return the shared error message used when a variable lookup fails."""

    return f"Could not find variable '{var_name}'."


def empty_structure_message(structure_name):
    """Return the shared message used when a supported structure is empty."""

    return f"{structure_name.capitalize()} is empty."


def unsupported_layout_message(structure_name):
    """Return the shared message used for unsupported structure layouts."""

    return f"{structure_name.capitalize()} layout is unsupported."


def normalize_output_path(output_filename):
    """
    Normalize one user-supplied export path to an absolute filesystem path.

    The helper keeps the export commands flexible for interactive LLDB use
    while making the final write target explicit in command output and tests.
    """

    normalized = os.path.abspath(os.path.expanduser(output_filename))
    if os.path.isdir(normalized):
        raise ValueError(f"Output path '{normalized}' is a directory.")
    return normalized


def _is_valid_handle(handle):
    """Return whether an LLDB handle-like object is present and valid."""

    if not handle:
        return False

    is_valid = getattr(handle, "IsValid", None)
    if callable(is_valid):
        return bool(is_valid())
    return True


def parse_command_arguments(command, result, command_name, arguments="", min_args=1):
    """Split a raw LLDB command string and validate its minimum arity."""

    try:
        args = shlex.split(command)
    except ValueError as error:
        set_argument_parse_error(result, command_name, error)
        return None

    if len(args) < min_args:
        set_usage_error(result, command_name, arguments)
        return None
    return args


def resolve_selected_frame(debugger, result):
    """Resolve the currently selected frame, or report a shared context error."""

    if not debugger:
        result.SetError(INVALID_EXECUTION_CONTEXT_ERROR)
        return None

    target = debugger.GetSelectedTarget()
    if not _is_valid_handle(target):
        result.SetError(INVALID_EXECUTION_CONTEXT_ERROR)
        return None

    process = target.GetProcess()
    if not _is_valid_handle(process):
        result.SetError(INVALID_EXECUTION_CONTEXT_ERROR)
        return None

    thread = process.GetSelectedThread()
    if not _is_valid_handle(thread):
        result.SetError(INVALID_EXECUTION_CONTEXT_ERROR)
        return None

    frame = thread.GetSelectedFrame()
    if not _is_valid_handle(frame):
        result.SetError(INVALID_EXECUTION_CONTEXT_ERROR)
        return None

    return frame


def find_variable(frame, var_name, result):
    """Look up one variable in the current frame and report failures consistently."""

    valobj = frame.FindVariable(var_name)
    if not _is_valid_handle(valobj):
        result.SetError(missing_variable_message(var_name))
        return None
    return valobj


def resolve_command_arguments(debugger, command, result, command_name, arguments="", min_args=1):
    """Resolve parsed command arguments together with the currently selected frame."""

    args = parse_command_arguments(command, result, command_name, arguments, min_args=min_args)
    if args is None:
        return None, None

    frame = resolve_selected_frame(debugger, result)
    if not frame:
        return None, None

    return args, frame


def resolve_command_variable(debugger, command, result, command_name, arguments="<variable>"):
    """Resolve a command, its variable name, and the corresponding `SBValue`."""

    args, frame = resolve_command_arguments(
        debugger,
        command,
        result,
        command_name,
        arguments,
        min_args=1,
    )
    if not args or not frame:
        return None, None, None

    var_name = args[0]
    valobj = find_variable(frame, var_name, result)
    if not valobj:
        return None, None, None

    return args, var_name, valobj
