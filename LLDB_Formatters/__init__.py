# ============================================================================ #
"""
LLDB package entry point for Pretty LLDB.

This module is imported by LLDB to register formatter categories, summary and
synthetic providers, and the custom commands exposed by the package. It also
provides the built-in help command shown to end users inside the debugger.

Author: XtremeXSPC
Version: 0.5.0.dev0
"""
# ============================================================================ #

try:
    import lldb  # type: ignore
except ImportError:
    lldb = None

# Import all modules that contain registered formatters or commands.
# This ensures that the decorators are run and the registry is populated.
from . import config, diagnostics, graph, linear, registry, tree, web_visualizer
from .helpers import Colors, should_use_colors


# ---------------------------- Help Command ----------------------------- #
def formatter_help_command(debugger, command, result, internal_dict):
    """
    Print the formatter command reference shown to LLDB users.

    The help text documents the supported commands, aliases, and the most
    important arguments so users can discover the package features directly
    from the debugger console.
    """
    use_colors = should_use_colors()
    C_CMD = Colors.BOLD_CYAN if use_colors else ""
    C_ARG = Colors.YELLOW if use_colors else ""
    C_RST = Colors.RESET if use_colors else ""
    C_TTL = Colors.GREEN if use_colors else ""

    help_message = f"""
{C_TTL}-----------------------------------------{C_RST}
{C_TTL}  Custom LLDB Formatters - Command List  {C_RST}
{C_TTL}-----------------------------------------{C_RST}

{C_CMD}Configuration:{C_RST}
  formatter_config [{C_ARG}<setting> [value]{C_RST}]
    - View, inspect, reset, or change global settings.
    - Example: `formatter_config tree_traversal_strategy inorder`

  formatter_explain [{C_ARG}<variable>{C_RST}] (alias: `fexplain`)
    - Shows how the formatter recognized the structure and which fields matched.

{C_CMD}Console Tree Printing:{C_RST}
  pptree [{C_ARG}<variable>{C_RST}] (alias: `pptree_preorder`)
  pptree_inorder [{C_ARG}<variable>{C_RST}]
  pptree_postorder [{C_ARG}<variable>{C_RST}]

{C_CMD}File Exporters (Graphviz .dot):{C_RST}
  export_tree [{C_ARG}<variable> [file.dot] [order]{C_RST}]
  export_graph [{C_ARG}<variable> [file.dot] [directed|undirected]{C_RST}]

{C_CMD}Interactive Web Visualizers:{C_RST}
  weblist [{C_ARG}<variable>{C_RST}]
    - Opens an interactive list visualization in your web browser.

  webtree [{C_ARG}<variable> [preorder|inorder|postorder]{C_RST}]
    - Opens an interactive tree visualization in your web browser.

  webgraph [{C_ARG}<variable> [directed|undirected]{C_RST}] (alias: `webg`)
    - Opens an interactive graph visualization in your web browser.

{C_CMD}Help:{C_RST}
  formatter_help (alias: `fhelp`)
    - Shows this help message.
"""
    result.AppendMessage(help_message)


def _formatter_load_order_key(item):
    """Return the registration priority used for debugger startup output."""

    if item["type"] == "synthetic":
        return 0
    if item["type"] == "summary":
        return 1
    return 2


def _iter_formatter_registry_in_load_order():
    """
    Return registry items in the order used during LLDB initialization.

    Synthetic providers are intentionally loaded and printed before summary
    providers so the debugger startup log remains easier to scan.
    """

    return sorted(registry.FORMATTER_REGISTRY, key=_formatter_load_order_key)


# --------------------- LLDB Module Initialization ---------------------- #
def __lldb_init_module(debugger, internal_dict):
    """
    Initialize the Pretty LLDB package inside the active LLDB session.

    The function creates the formatter category when needed, registers every
    provider collected in the shared registry, installs the custom commands and
    aliases, and prints a short confirmation banner for the user.
    """
    if lldb is None:
        print("LLDB module not available - Skipping formatter registration")
        return

    print("Loading custom formatters from 'LLDB_Formatters' package...")

    # ----- 1. Category Setup ----- #
    category_name = "CustomFormatters"
    category = debugger.GetCategory(category_name)
    if not category.IsValid():
        category = debugger.CreateCategory(category_name)
    category.SetEnabled(True)

    # ----- 2. Dynamic Formatter Registration ----- #
    # Iterate over the registry populated by the @register decorators.
    for item in _iter_formatter_registry_in_load_order():
        regex = item["regex"]

        if item["type"] == "summary":
            function_path = item["function_path"]
            # Register the summary provider function. LLDB needs the full path.
            category.AddTypeSummary(
                lldb.SBTypeNameSpecifier(regex, True),
                lldb.SBTypeSummary.CreateWithFunctionName(function_path),
            )
            print(
                f"  - Registered summary: {function_path} for '{Colors.YELLOW}{regex}{Colors.RESET}'"
            )

        elif item["type"] == "synthetic":
            class_path = item["class_path"]
            # Register the synthetic children provider class. LLDB needs the full path.
            category.AddTypeSynthetic(
                lldb.SBTypeNameSpecifier(regex, True),
                lldb.SBTypeSynthetic.CreateWithClassName(class_path),
            )
            print(
                f"  - Registered synthetic: {class_path} for '{Colors.YELLOW}{regex}{Colors.RESET}'"
            )

    # ----- 3. Register Custom LLDB Commands ----- #
    command_map = {
        # Help and Config
        "formatter_help": "LLDB_Formatters.formatter_help_command",
        "formatter_config": "LLDB_Formatters.config.formatter_config_command",
        "formatter_explain": "LLDB_Formatters.diagnostics.formatter_explain_command",
        # Console Tree
        "pptree_preorder": "LLDB_Formatters.tree.pptree_preorder_command",
        "pptree_inorder": "LLDB_Formatters.tree.pptree_inorder_command",
        "pptree_postorder": "LLDB_Formatters.tree.pptree_postorder_command",
        # File Exporters
        "export_tree": "LLDB_Formatters.tree.export_tree_command",
        "export_graph": "LLDB_Formatters.graph.export_graph_command",
        # Web Visualizers
        "weblist": "LLDB_Formatters.web_visualizer.export_list_web_command",
        "webtree": "LLDB_Formatters.web_visualizer.export_tree_web_command",
        "webgraph": "LLDB_Formatters.web_visualizer.export_graph_web_command",
    }
    for command, function_path in command_map.items():
        debugger.HandleCommand(f"command script add -f {function_path} {command}")

    # ----- 4. Register Command Aliases ----- #
    debugger.HandleCommand("command alias fhelp formatter_help")
    debugger.HandleCommand("command alias fexplain formatter_explain")
    debugger.HandleCommand("command alias pptree pptree_preorder")
    debugger.HandleCommand("command alias webt webtree")
    debugger.HandleCommand("command alias webg webgraph")

    # ----- 5. Final Output Message ----- #
    print(
        f"{Colors.GREEN}Formatters and commands registered in category '{category_name}'.{Colors.RESET}"
    )
    print(
        f"Type '{Colors.BOLD_CYAN}formatter_help{Colors.RESET}' or '{Colors.BOLD_CYAN}fhelp{Colors.RESET}' to see the list of new commands."
    )
