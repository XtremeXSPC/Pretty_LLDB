# ----------------------------------------------------------------------- #
# FILE: linear.py
#
# DESCRIPTION:
# This module provides the summary formatter for linear, pointer-based
# data structures such as singly-linked lists, stacks, and queues.
#
# It follows the new architecture by:
#   1. Using a 'register_summary' decorator to announce its capability.
#   2. Delegating structure discovery and traversal to the shared
#      extraction layer.
#   3. Formatting the extracted nodes into a final, user-facing
#      summary string.
# ----------------------------------------------------------------------- #

from .abi_layouts import resolve_vector_storage_layout
from .extraction import extract_linear_structure
from .helpers import (
    Colors,
    SUMMARY_CYCLE_MARKER,
    SUMMARY_TRUNCATION_MARKER,
    _safe_get_node_from_pointer,
    g_config,
    get_raw_pointer,
    get_value_summary,
    should_use_colors,
)
from .registry import register_summary, register_synthetic
from .schema_adapters import get_resolved_child, resolve_linear_container_schema, resolve_linear_node_schema
from .synthetic_support import create_synthetic_child, parse_synthetic_child_index


@register_synthetic(r"^(Custom|My)?(Linked)?List<.*>$")
@register_synthetic(r"^(Custom|My)?Stack<.*>$")
@register_synthetic(r"^(Custom|My)?Queue<.*>$")
class LinearProvider:
    def __init__(self, valobj, internal_dict):
        self.valobj = valobj
        self.children = []

    def update(self):
        self.children = []

        current_ptr = resolve_linear_container_schema(self.valobj).head_ptr
        if not current_ptr or get_raw_pointer(current_ptr) == 0:
            return

        first_node = _safe_get_node_from_pointer(current_ptr)
        if not first_node or not first_node.IsValid():
            return

        next_field = resolve_linear_node_schema(first_node).next_field
        if not next_field:
            return

        visited_addrs = set()
        while current_ptr and get_raw_pointer(current_ptr) != 0:
            if len(self.children) >= g_config.synthetic_max_children:
                break

            node_addr = get_raw_pointer(current_ptr)
            if node_addr in visited_addrs:
                break
            visited_addrs.add(node_addr)

            node = _safe_get_node_from_pointer(current_ptr)
            if not node or not node.IsValid():
                break

            child = create_synthetic_child(self.valobj, f"[{len(self.children)}]", node_addr, node)
            if child:
                self.children.append(child)

            next_child = get_resolved_child(node, next_field)
            if not next_child:
                break
            current_ptr = next_child

    def num_children(self):
        self.update()
        return len(self.children)

    def get_child_at_index(self, index):
        self.update()
        if 0 <= index < len(self.children):
            return self.children[index]
        return None

    def get_child_index(self, name):
        return parse_synthetic_child_index(name)


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
    use_colors = should_use_colors()
    extraction = extract_linear_structure(valobj, max_items=g_config.summary_max_items)
    diagnostics_suffix = (
        extraction.diagnostics.compact_summary() if g_config.diagnostics_enabled else ""
    )

    if extraction.error_message:
        return f"{extraction.error_message}{diagnostics_suffix}"

    if extraction.is_empty:
        return f"size = 0, []{diagnostics_suffix}"

    # ----- Format the output string ----- #
    C_GREEN = Colors.GREEN if use_colors else ""
    C_RESET = Colors.RESET if use_colors else ""
    C_YELLOW = Colors.YELLOW if use_colors else ""
    C_BOLD_CYAN = Colors.BOLD_CYAN if use_colors else ""
    C_RED = Colors.RED if use_colors else ""

    values = [node.value for node in extraction.nodes]
    size_str = f"size = {extraction.size}" if extraction.size is not None else ""

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
        if extraction.is_doubly_linked
        else f" {C_BOLD_CYAN}->{C_RESET} "
    )

    summary_str = separator.join(colored_values)

    if extraction.cycle_detected:
        cycle_label = f"{C_RED}{SUMMARY_CYCLE_MARKER}{C_RESET}"
        if summary_str:
            summary_str = f"{summary_str}{separator}{cycle_label}"
        else:
            summary_str = cycle_label

    if extraction.truncated:
        summary_str += f" {separator.strip()} {SUMMARY_TRUNCATION_MARKER}"

    return f"{C_GREEN}{size_str}{C_RESET}, [{summary_str}]{diagnostics_suffix}"


@register_summary(r"^std::__1::vector<.*>$")
@register_summary(r"^std::vector<.*>$")
def vector_summary_provider(valobj, internal_dict):
    """
    Summary provider for std::vector across common libc++ and libstdc++ layouts.
    Displays size, capacity, data pointer, and a preview of elements.
    """
    use_colors = should_use_colors()
    C_GREEN = Colors.GREEN if use_colors else ""
    C_RESET = Colors.RESET if use_colors else ""
    C_YELLOW = Colors.YELLOW if use_colors else ""
    C_RED = Colors.RED if use_colors else ""

    storage = resolve_vector_storage_layout(valobj)
    begin_ptr = storage.begin_ptr
    end_ptr = storage.end_ptr
    end_cap_raw = storage.end_cap_ptr

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
    end_cap_addr = get_raw_pointer(end_cap_raw) if end_cap_raw else 0
    if end_cap_addr:
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
                element_val = valobj.CreateValueFromAddress(f"[{i}]", element_addr, elem_type)
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
        elements_str = (
            f"{elements_str}, {SUMMARY_TRUNCATION_MARKER}"
            if elements_str
            else SUMMARY_TRUNCATION_MARKER
        )

    size_str = f"size = {size}"
    capacity_str = f"capacity = {capacity}" if capacity is not None else "capacity = ?"
    data_str = f"data = 0x{begin_addr:x}" if begin_addr else "data = null"

    return (
        f"{C_GREEN}{size_str}{C_RESET}, {C_GREEN}{capacity_str}{C_RESET}, "
        f"{C_GREEN}{data_str}{C_RESET}, [{elements_str}]"
    )
