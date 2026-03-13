# ============================================================================ #
"""
Runtime configuration support for Pretty LLDB.

This module defines the formatter settings exposed to users, provides the
parsing and validation helpers behind the `formatter_config` command, and keeps
the shared configuration singleton used by the formatter package.

Author: XtremeXSPC
Version: 0.5.0.dev0
"""
# ============================================================================ #

import shlex
from dataclasses import dataclass

from .command_helpers import set_argument_parse_error, usage_message


@dataclass(frozen=True)
class FormatterSettingSpec:
    """Describe one user-facing formatter setting and its validation contract."""

    key: str
    default: object
    description: str
    value_kind: str
    choices: tuple[str, ...] = ()


SETTING_SPECS = (
    FormatterSettingSpec(
        key="summary_max_items",
        default=30,
        description="Max items for list/tree summaries.",
        value_kind="integer",
    ),
    FormatterSettingSpec(
        key="synthetic_max_children",
        default=30,
        description="Max synthetic children when expanding list/tree formatters.",
        value_kind="integer",
    ),
    FormatterSettingSpec(
        key="graph_max_neighbors",
        default=10,
        description="Max neighbors in graph node summaries.",
        value_kind="integer",
    ),
    FormatterSettingSpec(
        key="tree_max_depth",
        default=512,
        description="Max tree depth explored during extraction and traversal.",
        value_kind="integer",
    ),
    FormatterSettingSpec(
        key="tree_traversal_strategy",
        default="preorder",
        description="Traversal order for tree summaries.",
        value_kind="choice",
        choices=("preorder", "inorder", "postorder"),
    ),
    FormatterSettingSpec(
        key="diagnostics_enabled",
        default=False,
        description="Append compact extraction diagnostics to formatter output.",
        value_kind="boolean",
    ),
    FormatterSettingSpec(
        key="debug_enabled",
        default=False,
        description="Emit verbose formatter debug logs to the LLDB console.",
        value_kind="boolean",
    ),
)

SETTING_SPECS_BY_KEY = {spec.key: spec for spec in SETTING_SPECS}


def _parse_bool(value_str):
    """Parse a boolean command argument using the accepted LLDB-facing aliases."""

    normalized = value_str.strip().lower()
    truth_map = {
        "1": True,
        "true": True,
        "yes": True,
        "on": True,
        "0": False,
        "false": False,
        "no": False,
        "off": False,
    }
    if normalized not in truth_map:
        raise ValueError(
            f"Invalid value '{value_str}'. Valid boolean options are: true, false, on, off, yes, no, 1, 0."
        )
    return truth_map[normalized]


def _parse_non_negative_int(value_str):
    """Convert a setting value to a non-negative integer or raise a clear error."""

    try:
        value = int(value_str)
    except ValueError as error:
        raise ValueError(
            f"Invalid value '{value_str}'. Expected a non-negative integer."
        ) from error

    if value < 0:
        raise ValueError(f"Invalid value '{value_str}'. Expected a non-negative integer.")
    return value


def _parse_choice(value_str, spec):
    """Validate a choice-based setting against the options declared in `spec`."""

    normalized = value_str.lower()
    if normalized not in spec.choices:
        raise ValueError(
            f"Invalid value '{value_str}'. Valid options for {spec.key} are: {', '.join(spec.choices)}."
        )
    return normalized


def _parse_setting_value(spec, value_str):
    """Dispatch setting parsing based on the value kind declared by the spec."""

    if spec.value_kind == "integer":
        return _parse_non_negative_int(value_str)
    if spec.value_kind == "boolean":
        return _parse_bool(value_str)
    if spec.value_kind == "choice":
        return _parse_choice(value_str, spec)
    raise ValueError(f"Unsupported setting kind '{spec.value_kind}'.")


def _format_setting_value(value):
    """Render a setting value in the same style used by command output."""

    if isinstance(value, str):
        return f"'{value}'"
    return str(value)


def _setting_usage(spec):
    """Build the per-setting usage suffix displayed by `formatter_config`."""

    if spec.value_kind == "choice":
        return f"{spec.key} <{'|'.join(spec.choices)}>"
    if spec.value_kind == "boolean":
        return f"{spec.key} <true|false>"
    return f"{spec.key} <integer>"


class FormatterConfig:
    """
    Store the active runtime configuration shared by all formatter entry points.

    The object is intentionally lightweight: it only exposes the current setting
    values and offers a `reset()` helper that re-applies the defaults declared
    in `SETTING_SPECS`.
    """

    def __init__(self):
        self.reset()

    def reset(self):
        """Restore every formatter setting to its declared default value."""

        for spec in SETTING_SPECS:
            setattr(self, spec.key, spec.default)


# Create a single global instance of the configuration object.
g_config = FormatterConfig()


def _append_settings_overview(result):
    """Write the full setting table to an LLDB command result object."""

    result.AppendMessage("Current formatter settings:")
    for spec in SETTING_SPECS:
        current_value = getattr(g_config, spec.key)
        result.AppendMessage(
            f"  - {spec.key} = {_format_setting_value(current_value)} "
            f"(default: {_format_setting_value(spec.default)})"
        )
        result.AppendMessage(f"    {spec.description}")
        if spec.choices:
            result.AppendMessage(f"    Options: {', '.join(spec.choices)}")

    result.AppendMessage(
        "\nUse 'formatter_config <setting>' to inspect one setting, "
        "'formatter_config <setting> <value>' to update it, or "
        "'formatter_config reset' to restore defaults."
    )


def _append_setting_detail(result, spec):
    """Write a detailed description for a single formatter setting."""

    current_value = getattr(g_config, spec.key)
    result.AppendMessage(f"{spec.key} = {_format_setting_value(current_value)}")
    result.AppendMessage(f"Default: {_format_setting_value(spec.default)}")
    result.AppendMessage(f"Type: {spec.value_kind}")
    result.AppendMessage(f"Description: {spec.description}")
    if spec.choices:
        result.AppendMessage(f"Options: {', '.join(spec.choices)}")
    result.AppendMessage(f"Usage: formatter_config {_setting_usage(spec)}")


def formatter_config_command(debugger, command, result, internal_dict):
    """
    Implement the `formatter_config` LLDB command.

    The command supports three read paths: showing the full configuration,
    inspecting one setting, and resetting every setting to defaults. When a
    value is supplied, the command validates it using the metadata in
    `SETTING_SPECS` before updating the shared configuration object.
    """
    try:
        args = shlex.split(command)
    except ValueError as error:
        set_argument_parse_error(result, "formatter_config", error)
        return

    if len(args) == 0:
        _append_settings_overview(result)
        return

    if len(args) > 2:
        result.SetError(usage_message("formatter_config", "[<setting_name> [<value>]]"))
        return

    if len(args) == 1:
        key = args[0]
        if key == "reset":
            g_config.reset()
            result.AppendMessage("Reset formatter settings to defaults.")
            return

        spec = SETTING_SPECS_BY_KEY.get(key)
        if not spec:
            result.SetError(
                f"Unknown setting '{key}'. Available settings are: {', '.join(spec.key for spec in SETTING_SPECS)}."
            )
            return

        _append_setting_detail(result, spec)
        return

    key, value_str = args
    spec = SETTING_SPECS_BY_KEY.get(key)
    if not spec:
        result.SetError(
            f"Unknown setting '{key}'. Available settings are: {', '.join(spec.key for spec in SETTING_SPECS)}."
        )
        return

    try:
        value = _parse_setting_value(spec, value_str)
    except ValueError as error:
        result.SetError(str(error))
        return

    setattr(g_config, key, value)
    result.AppendMessage(f"Set {key} -> {_format_setting_value(value)}")
