# ============================================================================ #
"""
Formatter registration support for Pretty LLDB.

This module implements the lightweight registry used by the package to collect
summary and synthetic providers before LLDB initialization runs. Formatters add
themselves through decorators, which keeps the package entry point free from
hard-coded formatter lists.

Author: XtremeXSPC
Version: 0.5.0.dev0
"""
# ============================================================================ #

# This global list stores registration information for all formatters.
# The '__lldb_init_module' function will iterate over this list to
# register everything with LLDB.
FORMATTER_REGISTRY = []


def _register_formatter(entry):
    """Append one formatter registration unless an identical entry already exists."""

    for existing in FORMATTER_REGISTRY:
        if existing == entry:
            return
    FORMATTER_REGISTRY.append(entry)


def register_summary(type_regex):
    """
    Register a function as the summary provider for matching type names.

    The decorator records the fully-qualified Python path expected by LLDB so
    the package entry point can register the provider later without importing
    implementation details a second time.
    """

    def decorator(summary_function):
        # Get the full Python path to the function (e.g., 'LLDB_Formatters.tree.tree_summary_provider')
        # This is required by LLDB to find the function.
        function_path = f"{summary_function.__module__}.{summary_function.__name__}"

        _register_formatter(
            {
                "type": "summary",
                "regex": type_regex,
                "function_path": function_path,
                "description": f"Summary for types matching '{type_regex}'",
            }
        )
        return summary_function

    return decorator


def register_synthetic(type_regex):
    """
    Register a class as the synthetic children provider for matching types.

    The stored class path is later consumed by `__lldb_init_module`, which uses
    it to register the provider with the active LLDB formatter category.
    """

    def decorator(synthetic_class):
        # Get the full Python path to the class (e.g., 'LLDB_Formatters.graph.GraphProvider')
        class_path = f"{synthetic_class.__module__}.{synthetic_class.__name__}"

        _register_formatter(
            {
                "type": "synthetic",
                "regex": type_regex,
                "class_path": class_path,
                "description": f"Synthetic children for types matching '{type_regex}'",
            }
        )
        return synthetic_class

    return decorator
