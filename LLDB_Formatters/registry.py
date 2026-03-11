# ----------------------------------------------------------------------- #
# FILE: registry.py
#
# DESCRIPTION:
# This module implements the Registry Pattern for the LLDB formatters.
# It provides a central list, 'FORMATTER_REGISTRY', and a set of
# decorators ('register_summary', 'register_synthetic') that allow
# formatters to be registered for specific data types automatically.
#
# This approach decouples the formatters from the main '__init__.py'
# file. To add a new formatter, one only needs to define it in its
# module and decorate it, without modifying the initialization script.
# ----------------------------------------------------------------------- #

# This global list stores registration information for all formatters.
# The '__lldb_init_module' function will iterate over this list to
# register everything with LLDB.
FORMATTER_REGISTRY = []


def register_summary(type_regex):
    """
    A decorator that registers a function as a Summary Provider for a given type.

    Args:
        type_regex: A regular expression that matches the C++ type name.
    """

    def decorator(summary_function):
        # Get the full Python path to the function (e.g., 'LLDB_Formatters.tree.tree_summary_provider')
        # This is required by LLDB to find the function.
        function_path = f"{summary_function.__module__}.{summary_function.__name__}"

        FORMATTER_REGISTRY.append(
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
    A decorator that registers a class as a Synthetic Children Provider.

    Args:
        type_regex: A regular expression that matches the C++ type name.
    """

    def decorator(synthetic_class):
        # Get the full Python path to the class (e.g., 'LLDB_Formatters.graph.GraphProvider')
        class_path = f"{synthetic_class.__module__}.{synthetic_class.__name__}"

        FORMATTER_REGISTRY.append(
            {
                "type": "synthetic",
                "regex": type_regex,
                "class_path": class_path,
                "description": f"Synthetic children for types matching '{type_regex}'",
            }
        )
        return synthetic_class

    return decorator
