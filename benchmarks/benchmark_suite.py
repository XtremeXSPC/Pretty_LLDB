#!/usr/bin/env python3

import argparse
import os
import statistics
import sys
import time
from contextlib import contextmanager

from LLDB_Formatters.config import g_config
from LLDB_Formatters.extraction import (
    extract_graph_structure,
    extract_linear_structure,
    extract_tree_structure,
)
from LLDB_Formatters.graph import GraphProvider
from LLDB_Formatters.linear import LinearProvider, linear_container_summary_provider
from LLDB_Formatters.renderers import (
    build_graph_renderer_payload,
    build_list_renderer_payload,
    build_tree_renderer_payload,
    render_graph_dot,
    render_tree_dot,
)
from LLDB_Formatters.tests.mock_lldb import MockSBValue, MockSBValueContainer
from LLDB_Formatters.tree import TreeProvider, tree_summary_provider
from LLDB_Formatters.web_visualizer import (
    generate_graph_visualization_html,
    generate_list_visualization_html,
    generate_tree_visualization_html,
)

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)


def _null_pointer(name):
    return MockSBValue(0, is_pointer=True, name=name, address=0)


def make_linear_fixture(length):
    current = _null_pointer("next")
    address_map = {}
    for index in range(length, 0, -1):
        node = MockSBValue(
            children={"value": MockSBValue(index), "next": current},
            name=f"node_{index}",
            address=0x1000 + (index * 0x10),
            type_name="Node<int>",
        )
        address_map[node.GetAddress().GetFileAddress()] = node
        current = node

    return MockSBValue(
        children={"head": current, "size": MockSBValue(length)},
        name="bench_list",
        type_name="MyList<int>",
        address_map=address_map,
    )


def make_deep_tree_fixture(depth):
    current = _null_pointer("left")
    address_map = {}
    for index in range(depth, 0, -1):
        node = MockSBValue(
            children={
                "left": current,
                "right": _null_pointer("right"),
                "value": MockSBValue(index),
            },
            name=f"node_{index}",
            address=0x5000 + (index * 0x10),
            type_name="TreeNode<int>",
        )
        address_map[node.GetAddress().GetFileAddress()] = node
        current = node

    return MockSBValue(
        children={"root": current, "size": MockSBValue(depth)},
        name="bench_tree",
        type_name="MyBinaryTree<int>",
        address_map=address_map,
    )


def make_dense_graph_fixture(node_count, degree):
    nodes = []
    for index in range(node_count):
        node = MockSBValue(
            children={"value": MockSBValue(index), "neighbors": MockSBValueContainer([])},
            name=f"node_{index}",
            address=0x9000 + (index * 0x10),
            type_name="MyGraphNode<int>",
        )
        nodes.append(node)

    for index, node in enumerate(nodes):
        neighbors = []
        for offset in range(1, min(degree, node_count - 1) + 1):
            neighbors.append(nodes[(index + offset) % node_count])
        node._children["neighbors"] = MockSBValueContainer(neighbors)

    return MockSBValue(
        children={
            "nodes": MockSBValueContainer(nodes),
            "num_nodes": MockSBValue(node_count),
            "num_edges": MockSBValue(node_count * min(degree, max(node_count - 1, 0))),
        },
        name="bench_graph",
        type_name="MyGraph<int>",
    )


@contextmanager
def temporary_config(
    summary_max_items, synthetic_max_children, graph_max_neighbors, tree_max_depth
):
    original = (
        g_config.summary_max_items,
        g_config.synthetic_max_children,
        g_config.graph_max_neighbors,
        g_config.tree_max_depth,
    )
    g_config.summary_max_items = summary_max_items
    g_config.synthetic_max_children = synthetic_max_children
    g_config.graph_max_neighbors = graph_max_neighbors
    g_config.tree_max_depth = tree_max_depth
    try:
        yield
    finally:
        (
            g_config.summary_max_items,
            g_config.synthetic_max_children,
            g_config.graph_max_neighbors,
            g_config.tree_max_depth,
        ) = original


def benchmark_case(operation_name, fn, iterations):
    samples_ms = []
    for _ in range(iterations):
        start = time.perf_counter()
        fn()
        elapsed_ms = (time.perf_counter() - start) * 1000
        samples_ms.append(elapsed_ms)
    return {
        "operation": operation_name,
        "median_ms": statistics.median(samples_ms),
        "min_ms": min(samples_ms),
        "max_ms": max(samples_ms),
    }


def run_list_benchmarks(list_size, iterations):
    fixture = make_linear_fixture(list_size)
    extraction = extract_linear_structure(fixture)
    return [
        benchmark_case(
            "list summary",
            lambda: linear_container_summary_provider(fixture, {}),
            iterations,
        ),
        benchmark_case(
            "list synthetic initial expansion",
            lambda: LinearProvider(fixture, {}).num_children(),
            iterations,
        ),
        benchmark_case(
            "list renderer payload",
            lambda: build_list_renderer_payload(extraction),
            iterations,
        ),
        benchmark_case(
            "list web html",
            lambda: generate_list_visualization_html(fixture),
            iterations,
        ),
    ]


def run_tree_benchmarks(tree_depth, iterations):
    fixture = make_deep_tree_fixture(tree_depth)
    extraction = extract_tree_structure(fixture)
    return [
        benchmark_case(
            "tree summary",
            lambda: tree_summary_provider(fixture, {}),
            iterations,
        ),
        benchmark_case(
            "tree synthetic initial expansion",
            lambda: TreeProvider(fixture, {}).num_children(),
            iterations,
        ),
        benchmark_case(
            "tree dot export",
            lambda: render_tree_dot(extraction),
            iterations,
        ),
        benchmark_case(
            "tree web html",
            lambda: generate_tree_visualization_html(fixture, traversal_name="preorder"),
            iterations,
        ),
        benchmark_case(
            "tree renderer payload",
            lambda: build_tree_renderer_payload(extraction),
            iterations,
        ),
    ]


def run_graph_benchmarks(graph_nodes, graph_degree, iterations):
    fixture = make_dense_graph_fixture(graph_nodes, graph_degree)
    extraction = extract_graph_structure(fixture)
    return [
        benchmark_case(
            "graph summary",
            lambda: GraphProvider(fixture, {}).get_summary(),
            iterations,
        ),
        benchmark_case(
            "graph synthetic initial expansion",
            lambda: GraphProvider(fixture, {}).num_children(),
            iterations,
        ),
        benchmark_case(
            "graph dot export",
            lambda: render_graph_dot(extraction, directed=True),
            iterations,
        ),
        benchmark_case(
            "graph web html",
            lambda: generate_graph_visualization_html(fixture, directed=True),
            iterations,
        ),
        benchmark_case(
            "graph renderer payload",
            lambda: build_graph_renderer_payload(extraction, directed=True),
            iterations,
        ),
    ]


def print_results(title, rows):
    print(title)
    print("-" * len(title))
    for row in rows:
        print(
            f"{row['operation']:<32} "
            f"median={row['median_ms']:>8.3f} ms  "
            f"min={row['min_ms']:>8.3f} ms  "
            f"max={row['max_ms']:>8.3f} ms"
        )
    print()


def parse_args():
    parser = argparse.ArgumentParser(description="Pretty LLDB local benchmark suite.")
    parser.add_argument("--list-size", type=int, default=5000)
    parser.add_argument("--tree-depth", type=int, default=256)
    parser.add_argument("--graph-nodes", type=int, default=400)
    parser.add_argument("--graph-degree", type=int, default=12)
    parser.add_argument("--iterations", type=int, default=7)
    parser.add_argument("--summary-max-items", type=int, default=g_config.summary_max_items)
    parser.add_argument(
        "--synthetic-max-children",
        type=int,
        default=g_config.synthetic_max_children,
    )
    parser.add_argument("--graph-max-neighbors", type=int, default=g_config.graph_max_neighbors)
    parser.add_argument("--tree-max-depth", type=int, default=g_config.tree_max_depth)
    return parser.parse_args()


def main():
    args = parse_args()
    with temporary_config(
        summary_max_items=args.summary_max_items,
        synthetic_max_children=args.synthetic_max_children,
        graph_max_neighbors=args.graph_max_neighbors,
        tree_max_depth=args.tree_max_depth,
    ):
        list_rows = run_list_benchmarks(args.list_size, args.iterations)
        tree_rows = run_tree_benchmarks(args.tree_depth, args.iterations)
        graph_rows = run_graph_benchmarks(
            args.graph_nodes,
            args.graph_degree,
            args.iterations,
        )

    print("Pretty LLDB Benchmark Suite")
    print("===========================")
    print(
        "Config:"
        f" list_size={args.list_size},"
        f" tree_depth={args.tree_depth},"
        f" graph_nodes={args.graph_nodes},"
        f" graph_degree={args.graph_degree},"
        f" iterations={args.iterations},"
        f" summary_max_items={args.summary_max_items},"
        f" synthetic_max_children={args.synthetic_max_children},"
        f" graph_max_neighbors={args.graph_max_neighbors}"
        f", tree_max_depth={args.tree_max_depth}"
    )
    print()

    print_results("Large List", list_rows)
    print_results("Deep Tree", tree_rows)
    print_results("Dense Graph", graph_rows)


if __name__ == "__main__":
    main()
