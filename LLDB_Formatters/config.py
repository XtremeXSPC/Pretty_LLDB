# ---------------------------------------------------------------------- #
# FILE: config.py
#
# DESCRIPTION:
# This module implements the user-facing configuration command for the
# formatters. It centralizes all global settings into a single
# configuration object, 'g_config', making them easy to manage.
#
# It contains the implementation for the 'formatter_config' command,
# which provides a runtime interface to inspect and modify these settings
# directly from the LLDB console.
# ---------------------------------------------------------------------- #


class FormatterConfig:
    """
    A centralized class to hold all global configuration settings for the formatters.
    An instance of this class is created as a global singleton 'g_config'.
    """

    def __init__(self):
        # The maximum number of items to display in a summary for linear
        # containers and trees.
        self.summary_max_items = 30

        # The maximum number of neighbors to display in a graph node's summary.
        self.graph_max_neighbors = 10

        # The default traversal strategy for tree summaries.
        # Can be changed at runtime to 'inorder', 'postorder', etc.
        self.tree_traversal_strategy = "preorder"

        # Enables compact diagnostics appended to formatter output.
        self.diagnostics_enabled = False

        # Enables verbose debug prints in the LLDB console.
        self.debug_enabled = False


# Create a single global instance of the configuration object.
# This instance is imported and used by other modules to access settings.
g_config = FormatterConfig()


def formatter_config_command(debugger, command, result, internal_dict):
    """
    Implements the 'formatter_config' command to view and change global settings.
    Usage:
      formatter_config                # View current settings and their descriptions.
      formatter_config <key> <value>  # Set a new value for a setting.
    """
    args = command.split()

    def _parse_bool(value_str):
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
            raise ValueError
        return truth_map[normalized]

    # Case 1: No arguments
    # Print current settings and their descriptions.
    if len(args) == 0:
        result.AppendMessage("Current Formatter Settings:")
        result.AppendMessage(
            f"  - summary_max_items: {g_config.summary_max_items} "
            "(Max items for list/tree summaries)"
        )
        result.AppendMessage(
            f"  - graph_max_neighbors: {g_config.graph_max_neighbors} "
            "(Max neighbors in graph node summaries)"
        )
        result.AppendMessage(
            f"  - tree_traversal_strategy: '{g_config.tree_traversal_strategy}' "
            "(Traversal order for tree summaries. Options: preorder, inorder, postorder)"
        )
        result.AppendMessage(
            f"  - diagnostics_enabled: {g_config.diagnostics_enabled} "
            "(Append compact extraction diagnostics to formatter output)"
        )
        result.AppendMessage(
            f"  - debug_enabled: {g_config.debug_enabled} "
            "(Emit verbose formatter debug logs to the LLDB console)"
        )
        result.AppendMessage("\nUse 'formatter_config <key> <value>' to change a setting.")
        return

    # Case 2: Wrong number of arguments
    if len(args) != 2:
        result.SetError("Usage: formatter_config <setting_name> <value>")
        return

    # Case 3: Set a value
    key = args[0]
    value_str = args[1]

    # Handle integer-based settings
    if key in ["summary_max_items", "graph_max_neighbors"]:
        try:
            value = int(value_str)
            setattr(g_config, key, value)
            result.AppendMessage(f"Set {key} -> {value}")
        except ValueError:
            result.SetError(f"Invalid value. '{value_str}' is not a valid integer for '{key}'.")
        except AttributeError:
            result.SetError(f"Unknown setting '{key}'.")

    # Handle string-based settings
    elif key == "tree_traversal_strategy":
        valid_strategies = ["preorder", "inorder", "postorder"]
        if value_str.lower() in valid_strategies:
            g_config.tree_traversal_strategy = value_str.lower()
            result.AppendMessage(
                f"Set tree_traversal_strategy -> '{g_config.tree_traversal_strategy}'"
            )
        else:
            result.SetError(
                f"Invalid value '{value_str}'. Valid options for tree_traversal_strategy are: {', '.join(valid_strategies)}"
            )

    elif key in ["diagnostics_enabled", "debug_enabled"]:
        try:
            value = _parse_bool(value_str)
            setattr(g_config, key, value)
            result.AppendMessage(f"Set {key} -> {value}")
        except ValueError:
            result.SetError(
                f"Invalid value '{value_str}'. Valid boolean options are: true, false, on, off, yes, no, 1, 0."
            )

    # Handle unknown settings
    else:
        available_settings = [k for k in dir(g_config) if not k.startswith("__")]
        result.SetError(
            f"Unknown setting '{key}'.\nAvailable settings are: {', '.join(available_settings)}"
        )
