# ---------------------------------------------------------------------- #
# FILE: web_visualizer.py
#
# DESCRIPTION:
# This module implements advanced, interactive data structure
# visualizations by generating self-contained HTML files that use the
# 'vis.js' JavaScript library.
#
# It provides three main commands:
#   - 'export_list_web': Generates an interactive, linear view of a
#     linked list with traversal animation.
#   - 'export_tree_web': Generates an interactive, hierarchical view
#     of a tree structure.
#   - 'export_graph_web': Generates an interactive, physics-based
#     force-directed layout of a graph structure.
#
# The generated HTML file is automatically opened in the user's
# default web browser.
#
# NOTE: ON DESIGN
# This module intentionally does NOT use the TraversalStrategy classes.
# The strategies are designed to produce linear text summaries, while the
# web visualizer needs the full structural information of the data
# (nodes, edges, addresses) to render it graphically.
# ---------------------------------------------------------------------- #

import json
import os
import shlex
import tempfile
import webbrowser

from .extraction import (
    extract_graph_structure,
    extract_linear_structure,
    extract_tree_structure,
)
from .helpers import debug_print

# ---------------------------------------------------------------------- #
# SECTION 1: PRIVATE HELPER FUNCTIONS
# These functions are for internal use within this module.
# ---------------------------------------------------------------------- #


def _load_static_file(file_path):
    """
    Generic helper to load a static file from the templates/static directory.
    """
    try:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        full_path = os.path.join(script_dir, "templates/static", file_path)
        with open(full_path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        debug_print(f"Failed to load static file {file_path}: {e}")
        return f"/* FAILED TO LOAD {file_path} */"


def _load_visjs_library():
    """Loads the content of the vis-network.min.js library."""
    return _load_static_file("vis-network.min.js")


def _load_shared_css():
    """Loads the content of style.css."""
    return _load_static_file("style.css")


def _load_shared_js():
    """Loads the content of common.js."""
    return _load_static_file("common.js")


def _build_visjs_data_for_list(valobj):
    """
    Traverses a linked list SBValue and returns all data required for its
    vis.js visualization in a dictionary.
    Returns None if the list is empty or its structure cannot be determined.
    """
    extracted_list = extract_linear_structure(valobj)
    if extracted_list.error_message or extracted_list.is_empty:
        return None

    nodes_data = []
    edges_data = []
    for node in extracted_list.nodes:
        nodes_data.append(
            {
                "id": f"0x{node.address:x}",
                "value": node.value,
                "address": f"0x{node.address:x}",
            }
        )
        if node.next_address != 0:
            edges_data.append(
                {
                    "from": f"0x{node.address:x}",
                    "to": f"0x{node.next_address:x}",
                }
            )

    return {
        "nodes_data": nodes_data,
        "edges_data": edges_data,
        "traversal_order": extracted_list.traversal_order,
        "list_size": extracted_list.size if extracted_list.size is not None else 0,
        "is_doubly_linked": extracted_list.is_doubly_linked,
    }


def _build_visjs_data_for_graph(valobj):
    """
    Traverses a graph SBValue and returns all data needed for its
    vis.js visualization in a dictionary.
    Returns None if the graph is empty or its structure cannot be determined.
    """
    extracted_graph = extract_graph_structure(valobj)
    if extracted_graph.is_empty:
        return None

    nodes = []
    edges = []
    for node in extracted_graph.nodes:
        nodes.append(
            {
                "id": f"0x{node.address:x}",
                "label": node.value,
                "title": f"Value: {node.value}",
                "address": f"0x{node.address:x}",
            }
        )

    for edge in extracted_graph.edges:
        edges.append(
            {
                "from": f"0x{edge.source:x}",
                "to": f"0x{edge.target:x}",
                "arrows": "to",
            }
        )
    return {"nodes_data": nodes, "edges_data": edges}


# ---------------------------------------------------------------------- #
# SECTION 2: PUBLIC REUSABLE HTML GENERATORS
# These functions orchestrate the creation of the final HTML content.
# ---------------------------------------------------------------------- #


def _generate_html(template_name, template_data):
    """
    Generic private helper to load an HTML template, substitute placeholders
    with data, and return the final HTML string.
    """
    template_data["__VISJS_LIBRARY__"] = _load_visjs_library()
    template_data["__SHARED_CSS__"] = _load_shared_css()
    template_data["__SHARED_JS__"] = _load_shared_js()

    try:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        template_path = os.path.join(script_dir, "templates", template_name)
        with open(template_path, "r", encoding="utf-8") as f:
            final_html = f.read()
        # Replace all placeholders with their corresponding data
        for placeholder, value in template_data.items():
            final_html = final_html.replace(placeholder, str(value))
        return final_html
    except Exception as e:
        return f"<html><body>Error generating visualizer from template '{template_name}': {e}</body></html>"


def generate_list_visualization_html(valobj):
    """
    Takes a list SBValue and returns a complete, self-contained HTML string
    for its visualization. Returns None if data generation fails.
    """
    list_data = _build_visjs_data_for_list(valobj)
    if not list_data:
        return None

    # ----- UNIFIED INFO TABLE GENERATION ------ #
    info = {
        "Variable Name": valobj.GetName(),
        "Type Name": valobj.GetTypeName(),
        "Size": list_data["list_size"],
        "Is Doubly Linked": "Yes" if list_data["is_doubly_linked"] else "No",
    }
    info_html = "<h3>List Information</h3><table>"
    for key, value in info.items():
        info_html += f"<tr><th>{key}</th><td>{value}</td></tr>"
    info_html += "</table>"

    template_data = {
        "__NODES_DATA__": json.dumps(list_data["nodes_data"]),
        "__EDGES_DATA__": json.dumps(list_data["edges_data"]),
        "__TRAVERSAL_ORDER_DATA__": json.dumps(list_data["traversal_order"]),
        "__IS_DOUBLY_LINKED__": json.dumps(list_data["is_doubly_linked"]),
        "__TYPE_INFO_HTML__": info_html,
    }
    return _generate_html("list_visualizer.html", template_data)


def generate_tree_visualization_html(valobj):
    """
    Takes a tree SBValue and returns a complete, self-contained HTML string
    for its visualization. Returns None if the tree is empty.
    This function is designed to be imported by other modules (e.g., tree.py).
    """
    extracted_tree = extract_tree_structure(valobj)
    if extracted_tree.is_empty or extracted_tree.error_message:
        return None

    nodes_data = []
    edges_data = []
    for node in extracted_tree.nodes:
        nodes_data.append(
            {
                "id": f"0x{node.address:x}",
                "label": node.value,
                "title": f"Value: {node.value}\nAddress: 0x{node.address:x}",
                "address": f"0x{node.address:x}",
            }
        )
    for edge in extracted_tree.edges:
        edges_data.append({"from": f"0x{edge.source:x}", "to": f"0x{edge.target:x}"})

    # ----- UNIFIED INFO TABLE GENERATION ------ #
    info = {
        "Variable Name": valobj.GetName(),
        "Type Name": valobj.GetTypeName(),
        "Size": extracted_tree.size if extracted_tree.size is not None else "N/A",
        "Root Address": f"0x{extracted_tree.root_address:x}",
    }
    info_html = "<h3>Tree Information</h3><table>"
    for key, value in info.items():
        info_html += f"<tr><th>{key}</th><td>{value}</td></tr>"
    info_html += "</table>"

    template_data = {
        "__NODES_DATA__": json.dumps(nodes_data),
        "__EDGES_DATA__": json.dumps(edges_data),
        "__TYPE_INFO_HTML__": info_html,  # Pass the full HTML block
    }
    return _generate_html("tree_visualizer.html", template_data)


def generate_graph_visualization_html(valobj):
    """
    Takes a graph SBValue and returns a complete, self-contained HTML string
    for its visualization. Returns None if data generation fails.
    """
    extracted_graph = extract_graph_structure(valobj)
    if extracted_graph.is_empty or extracted_graph.error_message:
        return None

    graph_data = _build_visjs_data_for_graph(valobj)
    if not graph_data:
        return None

    # ----- UNIFIED INFO TABLE GENERATION ------ #
    info = {
        "Variable Name": valobj.GetName(),
        "Type Name": valobj.GetTypeName(),
        "Nodes (V)": extracted_graph.num_nodes,
        "Edges (E)": extracted_graph.num_edges,
    }
    info_html = "<h3>Graph Information</h3><table>"
    for key, value in info.items():
        info_html += f"<tr><th>{key}</th><td>{value}</td></tr>"
    info_html += "</table>"

    template_data = {
        "__NODES_DATA__": json.dumps(graph_data["nodes_data"]),
        "__EDGES_DATA__": json.dumps(graph_data["edges_data"]),
        "__TYPE_INFO_HTML__": info_html,  # Pass the full HTML block
    }
    return _generate_html("graph_visualizer.html", template_data)


# ---------------------------------------------------------------------- #
# SECTION 3: CUSTOM LLDB COMMANDS
# These functions are registered in __init__.py and are callable from LLDB.
# ---------------------------------------------------------------------- #


def _display_html_content(html_content, var_name, result):
    """
    Handles displaying the generated HTML. It attempts to use the direct
    CodeLLDB API first, and falls back to opening a file in the default
    web browser if the API is not available (e.g., in a standard terminal).
    """
    if not html_content:
        result.AppendMessage(
            f"Could not generate visualization for '{var_name}'. The variable might be empty or invalid."
        )
        return

    # Try to use the direct CodeLLDB API for in-IDE visualization
    display_html = None
    try:
        from debugger import display_html  # type: ignore
    except ImportError:
        display_html = None

    if display_html:
        try:
            display_html(html_content)
            result.AppendMessage(f"Displayed interactive visualizer for '{var_name}' in a new tab.")
            return
        except Exception as e:
            debug_print(f"Failed to use CodeLLDB display_html: {e}")

    # Fallback for standard terminals
    result.AppendMessage("CodeLLDB API not found. Falling back to a web browser.")
    try:
        with tempfile.NamedTemporaryFile("w", delete=False, suffix=".html", encoding="utf-8") as f:
            f.write(html_content)
            output_filename = f.name
        webbrowser.open(f"file://{os.path.realpath(output_filename)}")
        result.AppendMessage(f"Successfully exported visualizer to '{output_filename}'.")
    except Exception as e:
        result.SetError(f"Failed to create or open the HTML file: {e}")


def _get_variable_from_command(command, debugger, result):
    """
    A utility to parse the command arguments to get the variable name
    and retrieve the corresponding SBValue from the debugger frame.
    Handles common errors like missing arguments or invalid variables.
    """
    args = shlex.split(command)
    if not args:
        result.SetError("Usage: <command> <variable_name>")
        return None, None

    var_name = args[0]
    frame = debugger.GetSelectedTarget().GetProcess().GetSelectedThread().GetSelectedFrame()
    if not frame.IsValid():
        result.SetError("Cannot execute command: invalid execution context.")
        return None, None

    valobj = frame.FindVariable(var_name)
    if not valobj or not valobj.IsValid():
        result.SetError(f"Could not find a variable named '{var_name}'.")
        return None, None

    return var_name, valobj


def export_list_web_command(debugger, command, result, internal_dict):
    """Implements the 'weblist' command."""
    var_name, valobj = _get_variable_from_command(command, debugger, result)
    if not valobj:
        return
    html_content = generate_list_visualization_html(valobj)
    _display_html_content(html_content, var_name, result)


def export_tree_web_command(debugger, command, result, internal_dict):
    """Implements the 'webtree' command."""
    var_name, valobj = _get_variable_from_command(command, debugger, result)
    if not valobj:
        return
    html_content = generate_tree_visualization_html(valobj)
    _display_html_content(html_content, var_name, result)


def export_graph_web_command(debugger, command, result, internal_dict):
    """Implements the 'webgraph' command."""
    var_name, valobj = _get_variable_from_command(command, debugger, result)
    if not valobj:
        return
    html_content = generate_graph_visualization_html(valobj)
    _display_html_content(html_content, var_name, result)
