# ---------------------------------------------------------------------- #
# FILE: linear.py
#
# DESCRIPTION:
# This module provides the summary formatter for linear, pointer-based
# data structures such as singly-linked lists, stacks, and queues.
#
# It follows the new architecture by:
#   1. Using a 'register_summary' decorator to announce its capability.
#   2. Employing the 'LinearTraversalStrategy' to decouple the traversal
#      logic from the presentation logic.
#   3. Formatting the results from the strategy into a final, user-
#      facing summary string.
# ---------------------------------------------------------------------- #

from .helpers import (
    Colors,
    get_child_member_by_names,
    get_raw_pointer,
    get_value_summary,
    should_use_colors,
    g_config,
)
from .registry import register_summary
from .strategies import LinearTraversalStrategy


@register_summary(r"^(Custom|My)?(Linked)?List<.*>$")
@register_summary(r"^(Custom|My)?Stack<.*>$")
@register_summary(r"^(Custom|My)?Queue<.*>$")
def linear_container_summary_provider(valobj, internal_dict):
    """
    This is the registered summary provider for all linear containers.
    It orchestrates fetching data using a strategy and formatting the
    final summary string.

    Args:
        valobj: The SBValue object representing the list/stack/queue.
        internal_dict: The LLDB internal dictionary.

    Returns:
        A formatted one-line summary string.
    """
    # Use the appropriate strategy to traverse the data structure.
    strategy = LinearTraversalStrategy()
    use_colors = should_use_colors()

    # Find the head pointer of the container.
    head_ptr = get_child_member_by_names(valobj, ["head", "m_head", "_head", "top"])
    if not head_ptr:
        return "Error: Could not find head pointer member."

    if get_raw_pointer(head_ptr) == 0:
        return "size = 0, []"

    # The strategy returns the list of values and metadata about the traversal.
    values, metadata = strategy.traverse(head_ptr, g_config.summary_max_items)

    # --- Format the output string ---
    C_GREEN = Colors.GREEN if use_colors else ""
    C_RESET = Colors.RESET if use_colors else ""
    C_YELLOW = Colors.YELLOW if use_colors else ""
    C_BOLD_CYAN = Colors.BOLD_CYAN if use_colors else ""
    C_RED = Colors.RED if use_colors else ""

    # Format the size information.
    size_member = get_child_member_by_names(
        valobj, ["count", "size", "m_size", "_size"]
    )
    size_str = f"size = {size_member.GetValueAsUnsigned()}" if size_member else ""

    # Colorize values. Red for errors, yellow for data.
    colored_values = []
    for v in values:
        if v.startswith("["):  # Error or cycle
            colored_values.append(f"{C_RED}{v}{C_RESET}")
        else:
            colored_values.append(f"{C_YELLOW}{v}{C_RESET}")

    # Choose the appropriate separator based on linked list type.
    separator = (
        f" {C_BOLD_CYAN}<->{C_RESET} "
        if metadata.get("doubly_linked", False)
        else f" {C_BOLD_CYAN}->{C_RESET} "
    )

    summary_str = separator.join(colored_values)

    if metadata.get("truncated", False):
        summary_str += f" {separator.strip()} ..."

    return f"{C_GREEN}{size_str}{C_RESET}, [{summary_str}]"

# ------------------ Summary Provider for std::vector ------------------- #

def _extract_vector_end_cap_pointer(end_cap_value):
    if not end_cap_value or not end_cap_value.IsValid():
        return None

    if end_cap_value.GetType().IsPointerType():
        return end_cap_value

    for name in ["__value_", "__first_", "first", "__value", "__first"]:
        child = end_cap_value.GetChildMemberWithName(name)
        if child and child.IsValid():
            if child.GetType().IsPointerType():
                return child
            nested = get_child_member_by_names(
                child, ["__value_", "__first_", "first", "__value", "__first"]
            )
            if nested and nested.IsValid() and nested.GetType().IsPointerType():
                return nested

    for i in range(end_cap_value.GetNumChildren()):
        child = end_cap_value.GetChildAtIndex(i)
        if child and child.IsValid() and child.GetType().IsPointerType():
            return child

    return None


@register_summary(r"^std::__1::vector<.*>$")
@register_summary(r"^std::vector<.*>$")
def vector_summary_provider(valobj, internal_dict):
    """
    Summary provider for libc++ std::vector.
    Displays size, capacity, data pointer, and a preview of elements.
    """
    use_colors = should_use_colors()
    C_GREEN = Colors.GREEN if use_colors else ""
    C_RESET = Colors.RESET if use_colors else ""
    C_YELLOW = Colors.YELLOW if use_colors else ""
    C_RED = Colors.RED if use_colors else ""

    begin_ptr = get_child_member_by_names(valobj, ["__begin_", "__begin"])
    end_ptr = get_child_member_by_names(valobj, ["__end_", "__end"])
    end_cap_raw = get_child_member_by_names(valobj, ["__end_cap_", "__end_cap"])
    end_cap_ptr = _extract_vector_end_cap_pointer(end_cap_raw)

    if not begin_ptr or not end_ptr:
        return "Error: Could not locate vector storage pointers."

    begin_addr = get_raw_pointer(begin_ptr)
    end_addr = get_raw_pointer(end_ptr)

    elem_type = None
    element_size = 0
    if begin_ptr.GetType().IsPointerType():
        elem_type = begin_ptr.GetType().GetPointeeType()
        if elem_type:
            element_size = elem_type.GetByteSize()

    size = 0
    if begin_addr and end_addr and element_size > 0 and end_addr >= begin_addr:
        size = (end_addr - begin_addr) // element_size

    capacity = None
    if end_cap_ptr:
        end_cap_addr = get_raw_pointer(end_cap_ptr)
        if end_cap_addr and element_size > 0 and end_cap_addr >= begin_addr:
            capacity = (end_cap_addr - begin_addr) // element_size

    values = []
    truncated = False
    if size > 0 and element_size > 0 and elem_type:
        max_items = g_config.summary_max_items
        show_count = min(size, max_items)
        for i in range(show_count):
            element_addr = begin_addr + (i * element_size)
            try:
                element_val = valobj.CreateValueFromAddress(
                    f"[{i}]", element_addr, elem_type
                )
            except Exception:
                element_val = None
            values.append(get_value_summary(element_val))
        truncated = size > max_items

    colored_values = []
    for value in values:
        if value and value.startswith("["):
            colored_values.append(f"{C_RED}{value}{C_RESET}")
        else:
            colored_values.append(f"{C_YELLOW}{value}{C_RESET}")

    if size == 0:
        elements_str = ""
    elif values:
        elements_str = ", ".join(colored_values)
    else:
        elements_str = f"{C_RED}[unavailable]{C_RESET}"

    if truncated:
        elements_str = f"{elements_str}, ..." if elements_str else "..."

    size_str = f"size = {size}"
    capacity_str = f"capacity = {capacity}" if capacity is not None else "capacity = ?"
    data_str = f"data = 0x{begin_addr:x}" if begin_addr else "data = null"

    return (
        f"{C_GREEN}{size_str}{C_RESET}, {C_GREEN}{capacity_str}{C_RESET}, "
        f"{C_GREEN}{data_str}{C_RESET}, [{elements_str}]"
    )
