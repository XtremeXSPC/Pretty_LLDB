GRAPH_RENDER_MODES = {
    "directed": True,
    "undirected": False,
}


def parse_graph_render_mode(mode_token):
    if mode_token is None:
        return True

    normalized = mode_token.lower()
    if normalized not in GRAPH_RENDER_MODES:
        valid_modes = ", ".join(GRAPH_RENDER_MODES)
        raise ValueError(f"Invalid graph mode '{mode_token}'. Valid options are: {valid_modes}.")
    return GRAPH_RENDER_MODES[normalized]


def parse_graph_export_arguments(args):
    output_filename = "graph.dot"
    mode_token = None

    if len(args) >= 2:
        second = args[1]
        if second.lower() in GRAPH_RENDER_MODES:
            mode_token = second
        else:
            output_filename = second

    if len(args) >= 3:
        mode_token = args[2]

    directed = parse_graph_render_mode(mode_token)
    return output_filename, directed
