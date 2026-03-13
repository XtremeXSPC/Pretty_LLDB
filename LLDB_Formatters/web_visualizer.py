# ============================================================================ #
"""
Interactive HTML visualizers for Pretty LLDB structures.

This module turns extracted list, tree, and graph data into self-contained
HTML pages backed by the bundled `vis.js` assets. It also provides the LLDB
commands that validate a structure, generate the HTML, and display it either
through CodeLLDB or a fallback browser workflow.

Author: XtremeXSPC
Version: 0.5.0.dev0
"""
# ============================================================================ #

import json
import os
import tempfile
import webbrowser

from .command_helpers import (
    empty_structure_message,
    resolve_command_variable,
    unsupported_layout_message,
)
from .extraction import (
    extract_graph_structure,
    extract_linear_structure,
    extract_tree_structure,
)
from .helpers import debug_print, g_config
from .renderers import (
    build_graph_renderer_payload,
    build_list_renderer_payload,
    build_tree_renderer_payload,
)
from .schema_adapters import resolve_tree_container_schema
from .visualization_options import create_tree_traversal_strategy, parse_graph_render_mode

# ----------------------------------------------------------------------- #
# SECTION 1: PRIVATE HELPER FUNCTIONS
# These functions are for internal use within this module.
# ----------------------------------------------------------------------- #


def _load_static_file(file_path):
    """Load one bundled static asset used by the HTML visualizer templates."""

    try:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        full_path = os.path.join(script_dir, "templates/static", file_path)
        with open(full_path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        debug_print(f"Failed to load static file {file_path}: {e}")
        return f"/* FAILED TO LOAD {file_path} */"


def _load_visjs_library():
    """Return the bundled `vis-network.min.js` payload."""

    return _load_static_file("vis-network.min.js")


def _load_shared_css():
    """Return the shared stylesheet injected into visualizer pages."""

    return _load_static_file("style.css")


def _load_shared_js():
    """Return the shared JavaScript helpers injected into visualizer pages."""

    return _load_static_file("common.js")


def _build_visjs_data_for_list(valobj):
    """
    Extract and convert a list value into the payload expected by the renderer.

    The helper returns `None` when the structure is empty or unsupported, which
    allows the caller to reuse a single validation path for LLDB commands.
    """
    extracted_list = extract_linear_structure(valobj)
    if extracted_list.error_message or extracted_list.is_empty:
        return None
    return build_list_renderer_payload(extracted_list)


def _build_visjs_data_for_graph(valobj, directed=True):
    """
    Extract and convert a graph value into the payload expected by the renderer.

    The `directed` flag only affects the rendered edge semantics; extraction
    still operates on the same normalized graph model.
    """
    extracted_graph = extract_graph_structure(valobj)
    if extracted_graph.is_empty or extracted_graph.error_message:
        return None
    return build_graph_renderer_payload(extracted_graph, directed=directed)


# ----------------------------------------------------------------------- #
# SECTION 2: PUBLIC REUSABLE HTML GENERATORS
# These functions orchestrate the creation of the final HTML content.
# ----------------------------------------------------------------------- #


def _generate_html(template_name, template_data):
    """
    Materialize one HTML visualizer template with the provided payload data.

    Shared CSS, JavaScript, and the embedded vis.js library are injected here
    so the generated output remains fully self-contained.
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
    Generate the full HTML document used to visualize a linear container.

    The returned document contains both the vis.js payload and a compact table
    with the most relevant metadata about the selected list variable.
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
        "__CYCLE_DETECTED__": json.dumps(list_data["cycle_detected"]),
        "__TYPE_INFO_HTML__": info_html,
    }
    return _generate_html("list_visualizer.html", template_data)


def generate_tree_visualization_html(valobj, traversal_name=None):
    """
    Generate the full HTML document used to visualize a tree container.

    When a traversal name is supplied, the corresponding strategy is resolved
    and its visit order is embedded so the page can annotate that sequence.
    """
    extracted_tree = extract_tree_structure(valobj)
    if extracted_tree.is_empty or extracted_tree.error_message:
        return None

    root_ptr = resolve_tree_container_schema(valobj).root_ptr
    traversal_addresses = None
    resolved_traversal_name = None
    if root_ptr:
        strategy, resolved_traversal_name = create_tree_traversal_strategy(
            traversal_name,
            default_mode=g_config.tree_traversal_strategy,
        )
        traversal_addresses = strategy.ordered_addresses(root_ptr)

    tree_data = build_tree_renderer_payload(
        extracted_tree,
        traversal_order=traversal_addresses,
    )

    # ----- UNIFIED INFO TABLE GENERATION ------ #
    info = {
        "Variable Name": valobj.GetName(),
        "Type Name": valobj.GetTypeName(),
        "Size": tree_data["tree_size"],
        "Root Address": tree_data["root_address"],
        "Traversal": resolved_traversal_name or "n/a",
    }
    info_html = "<h3>Tree Information</h3><table>"
    for key, value in info.items():
        info_html += f"<tr><th>{key}</th><td>{value}</td></tr>"
    info_html += "</table>"

    template_data = {
        "__NODES_DATA__": json.dumps(tree_data["nodes_data"]),
        "__EDGES_DATA__": json.dumps(tree_data["edges_data"]),
        "__TYPE_INFO_HTML__": info_html,  # Pass the full HTML block
    }
    return _generate_html("tree_visualizer.html", template_data)


def generate_graph_visualization_html(valobj, directed=True):
    """
    Generate the full HTML document used to visualize a graph container.

    The resulting page includes graph metadata and the node/edge payload needed
    by the interactive front-end renderer.
    """
    extracted_graph = extract_graph_structure(valobj)
    if extracted_graph.is_empty or extracted_graph.error_message:
        return None

    graph_data = _build_visjs_data_for_graph(valobj, directed=directed)
    if not graph_data:
        return None

    # ----- UNIFIED INFO TABLE GENERATION ------ #
    info = {
        "Variable Name": valobj.GetName(),
        "Type Name": valobj.GetTypeName(),
        "Nodes (V)": extracted_graph.num_nodes,
        "Edges (E)": graph_data["num_edges"],
        "Mode": "Directed" if graph_data["directed"] else "Undirected",
    }
    info_html = "<h3>Graph Information</h3><table>"
    for key, value in info.items():
        info_html += f"<tr><th>{key}</th><td>{value}</td></tr>"
    info_html += "</table>"

    template_data = {
        "__NODES_DATA__": json.dumps(graph_data["nodes_data"]),
        "__EDGES_DATA__": json.dumps(graph_data["edges_data"]),
        "__GRAPH_DIRECTED__": json.dumps(graph_data["directed"]),
        "__TYPE_INFO_HTML__": info_html,  # Pass the full HTML block
    }
    return _generate_html("graph_visualizer.html", template_data)


# ----------------------------------------------------------------------- #
# SECTION 3: CUSTOM LLDB COMMANDS
# These functions are registered in __init__.py and are callable from LLDB.
# ----------------------------------------------------------------------- #


def _display_html_content(html_content, var_name, result):
    """
    Display generated HTML through CodeLLDB or a browser-based fallback.

    This helper centralizes the environment-dependent display logic so the
    export commands only need to focus on validation and payload generation.
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


def _validate_visualizable_structure(result, structure_name, extraction):
    """Validate that a structure is supported and non-empty before rendering."""

    if extraction.error_message:
        result.SetError(unsupported_layout_message(structure_name))
        return False
    if extraction.is_empty:
        result.AppendMessage(empty_structure_message(structure_name))
        return False
    return True


def export_list_web_command(debugger, command, result, internal_dict):
    """Generate and display the interactive HTML visualizer for a list."""

    _, var_name, valobj = resolve_command_variable(
        debugger,
        command,
        result,
        "weblist",
    )
    if not valobj:
        return
    extraction = extract_linear_structure(valobj)
    if not _validate_visualizable_structure(result, "list", extraction):
        return
    html_content = generate_list_visualization_html(valobj)
    _display_html_content(html_content, var_name, result)


def export_tree_web_command(debugger, command, result, internal_dict):
    """Generate and display the interactive HTML visualizer for a tree."""

    args, var_name, valobj = resolve_command_variable(
        debugger,
        command,
        result,
        "webtree",
        "<variable> [preorder|inorder|postorder]",
    )
    if not valobj:
        return
    traversal_name = args[1] if len(args) > 1 else None
    try:
        _, resolved_traversal_name = create_tree_traversal_strategy(
            traversal_name,
            default_mode=g_config.tree_traversal_strategy,
        )
    except ValueError as error:
        result.SetError(str(error))
        return
    extraction = extract_tree_structure(valobj)
    if not _validate_visualizable_structure(result, "tree", extraction):
        return
    html_content = generate_tree_visualization_html(valobj, traversal_name=resolved_traversal_name)
    _display_html_content(html_content, var_name, result)


def export_graph_web_command(debugger, command, result, internal_dict):
    """Generate and display the interactive HTML visualizer for a graph."""

    args, var_name, valobj = resolve_command_variable(
        debugger,
        command,
        result,
        "webgraph",
        "<variable> [directed|undirected]",
    )
    if not valobj:
        return
    mode_token = args[1] if len(args) > 1 else None
    try:
        directed = parse_graph_render_mode(mode_token)
    except ValueError as error:
        result.SetError(str(error))
        return
    extraction = extract_graph_structure(valobj)
    if not _validate_visualizable_structure(result, "graph", extraction):
        return
    html_content = generate_graph_visualization_html(valobj, directed=directed)
    _display_html_content(html_content, var_name, result)
