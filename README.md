# Pretty LLDB

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Language](https://img.shields.io/badge/Language-Python-blue.svg)]()
[![Debugger](https://img.shields.io/badge/Debugger-LLDB-orange.svg)]()

`Pretty_LLDB` is a Python-based formatter package for LLDB that improves the
inspection of C++ data structures during interactive debugging. The project is
designed around three complementary goals:

1. produce concise and readable one-line summaries in the variables view;
2. expose stable synthetic children for structured expansion inside LLDB;
3. provide richer inspection workflows through console commands, Graphviz
   export, and interactive HTML visualizers.

The current `0.5.x` development line is centered on an adapter-driven
extraction layer and ABI-aware probing, replacing earlier heuristic-heavy
behavior with a more explicit and extensible internal contract.

![Showcase Example](Assets/Example.webp)

## Project Status

The repository currently includes:

- an adapter-based schema resolution layer for linear structures, trees, and
  adjacency-list graphs;
- ABI-aware support for `std::vector` layouts used by common libc++ and
  libstdc++ variants;
- configurable tree traversal semantics and depth safeguards;
- console commands for diagnostics, tree printing, Graphviz export, and web
  visualization;
- packaged HTML/CSS/JavaScript assets for interactive list, tree, and graph
  renderers;
- release-engineering assets, including packaging metadata, a compatibility
  matrix, a benchmark suite, and CI workflow files.

The project remains pre-`1.0`. Public command names are stable enough for daily
use, but output details and compatibility claims should still be treated as part
of an evolving development line.

## Core Capabilities

### LLDB summaries and synthetic children

The package registers LLDB summary providers and synthetic providers for the
supported structure families. During debugger startup, synthetic providers are
loaded before summaries so the registration log remains easier to inspect.

### Interactive HTML visualizers

The `weblist`, `webtree`, and `webgraph` commands generate self-contained HTML
documents backed by bundled `vis.js` assets. When the debugger environment
supports direct HTML display, the visualizers can open inside the IDE; when it
does not, the package falls back to a temporary-file workflow and launches the
system browser.

### Graphviz export

Trees and graphs can be exported to `.dot` files through `export_tree` and
`export_graph`. This path is useful when the debugging session needs a durable
artifact for documentation, offline analysis, or rendering through Graphviz.

### Diagnostic introspection

The `formatter_explain` command reports how a variable was recognized, which
semantic roles were matched, and which warnings were emitted during extraction.
This command is particularly useful when integrating the formatter with custom
containers whose layout only partially matches the adapter catalog.

### Runtime configuration

Behavior that affects truncation, traversal, diagnostics, and debug logging is
controlled through `formatter_config`, without requiring code edits or module
reloads.

## Supported Structure Families

The project is intentionally generic within a bounded domain. It does not
hard-code support for one user-defined type; instead, it recognizes common
container and node layouts through regex-based registration plus semantic field
adapters.

### Linear structures

Supported families include custom linked lists, stacks, and queues matching the
registered type-name patterns:

- `LinkedList<T>`
- `List<T>`
- `Stack<T>`
- `Queue<T>`
- `My...` and `Custom...` variants that satisfy the same regex family

Typical semantic roles include:

- container head fields such as `head`, `first`, `front`, `begin`, `top`;
- node value fields such as `value`, `val`, `data`, `payload`;
- linkage fields such as `next`, `link`, `m_next`, `previous`, `prev`.

### STL vector support

`std::vector` summaries are supported through ABI-aware storage probing rather
than naive child enumeration. The package includes logic for the common pointer
layouts exposed by libc++ and libstdc++, and it also avoids leaking debug-vector
wrapper internals when iterating logical elements.

### Trees

Supported tree families include binary and n-ary layouts that expose a root
member and either:

- classic binary children such as `left` and `right`; or
- a children container such as `children`, `kids`, or analogous semantic roles.

Tree traversal can be configured globally or requested per command using
`preorder`, `inorder`, or `postorder`. Extraction and traversal both respect
the configured depth limit.

### Graphs

Graph support targets adjacency-list style containers that expose:

- a node collection such as `nodes`, `vertices`, `adjacency_list`;
- optional stored counts such as `num_nodes`, `V`, `num_edges`, `E`;
- graph node payload fields such as `value`, `payload`, `data`;
- neighbor containers such as `neighbors`, `adj`, `connections`, `links`.

The package currently focuses on graph containers and node summaries rather than
on every possible graph API surface. It is best suited to explicit node objects
with visible adjacency collections.

## Installation

### Repository import

Clone the repository to any stable local path:

```sh
git clone https://github.com/XtremeXSPC/Pretty_LLDB.git /absolute/path/to/Pretty_LLDB
```

Then import the package from LLDB:

```lldb
command script import /absolute/path/to/Pretty_LLDB
```

For a persistent installation, add the same command to `~/.lldbinit`.

### VS Code / CodeLLDB

When using CodeLLDB, the import can also be attached to a project launch
configuration:

```json
{
  "name": "Debug C++",
  "type": "lldb",
  "request": "launch",
  "program": "${workspaceFolder}/bin/your_binary",
  "initCommands": [
    "command script import /absolute/path/to/Pretty_LLDB"
  ]
}
```

### Python package metadata

The repository contains a `pyproject.toml` with package metadata and bundled
template assets. At present, the canonical workflow remains repository import
from LLDB rather than a published package installation flow.

## Command Surface

The package installs the following custom commands and aliases.

| Command                                                     | Alias             | Purpose                                                                   |
| :---------------------------------------------------------- | :---------------- | :------------------------------------------------------------------------ |
| `formatter_help`                                            | `fhelp`           | Show the built-in command reference.                                      |
| `formatter_config`                                          | -                 | Inspect, change, or reset formatter settings.                             |
| `formatter_explain <variable>`                              | `fexplain`        | Report extraction decisions, resolved fields, and warnings.               |
| `pptree <variable>`                                         | `pptree_preorder` | Render a tree as an ASCII diagram using pre-order traversal.              |
| `pptree_inorder <variable>`                                 | -                 | Print the in-order traversal sequence.                                    |
| `pptree_postorder <variable>`                               | -                 | Print the post-order traversal sequence.                                  |
| `export_tree <variable> [file.dot] [order]`                 | -                 | Export a tree to Graphviz DOT, optionally annotated with traversal order. |
| `export_graph <variable> [file.dot] [directed\|undirected]` | -                 | Export a graph to Graphviz DOT.                                           |
| `weblist <variable>`                                        | -                 | Open the list visualizer.                                                 |
| `webtree <variable> [preorder\|inorder\|postorder]`         | `webt`            | Open the tree visualizer.                                                 |
| `webgraph <variable> [directed\|undirected]`                | `webg`            | Open the graph visualizer.                                                |

## Runtime Configuration

The current formatter settings are:

| Setting                   | Default    | Meaning                                                            |
| :------------------------ | :--------- | :----------------------------------------------------------------- |
| `summary_max_items`       | `30`       | Maximum number of items shown in one-line summaries.               |
| `synthetic_max_children`  | `30`       | Maximum number of synthetic children exposed in LLDB expansion.    |
| `graph_max_neighbors`     | `10`       | Maximum number of neighbors previewed in graph node summaries.     |
| `tree_max_depth`          | `512`      | Maximum tree depth explored during extraction and traversal.       |
| `tree_traversal_strategy` | `preorder` | Default traversal mode for tree summaries and synthetic providers. |
| `diagnostics_enabled`     | `False`    | Append compact diagnostic suffixes to formatter output.            |
| `debug_enabled`           | `False`    | Emit verbose debug logs to the LLDB console.                       |

Examples:

```lldb
formatter_config
formatter_config tree_traversal_strategy inorder
formatter_config summary_max_items 50
formatter_config diagnostics_enabled true
formatter_config reset
```

## Internal Architecture

The project is organized around a layered formatter pipeline.

### Registration layer

The package entry point imports formatter modules and consumes a shared registry
populated by decorators. This keeps LLDB initialization declarative and avoids
manual duplication of provider lists.

### Schema and extraction layer

The central runtime behavior lives in:

- `schema_adapters.py` for semantic role resolution;
- `pointers.py` for pointer-like and smart-pointer resolution;
- `extraction.py` for normalized linear, tree, and graph extraction models;
- `abi_layouts.py` for STL and ABI-sensitive probing.

This layer is the principal boundary between raw `SBValue` inspection and
formatter presentation.

### Presentation layer

User-facing output is produced by:

- `linear.py`, `tree.py`, and `graph.py` for LLDB summaries and commands;
- `renderers.py` for deterministic payload and DOT generation;
- `web_visualizer.py` plus the bundled templates for HTML rendering.

### Traversal semantics

Tree traversal behavior is isolated in `strategies.py`, which allows summaries,
synthetic providers, exports, and web visualizers to share the same conceptual
visit order without duplicating traversal logic in each feature module.

## Validation, Compatibility, and Release Operations

This repository includes operational artifacts that describe the supported
environments and release expectations more precisely than a top-level overview
can.

- Compatibility matrix: [COMPATIBILITY.md](COMPATIBILITY.md)
- Changelog: [CHANGELOG.md](CHANGELOG.md)
- Release checklist: [RELEASE_CHECKLIST.md](RELEASE_CHECKLIST.md)
- Benchmark suite: `python3 benchmarks/benchmark_suite.py`

For the current `0.5.x` line, compatibility claims are intentionally
conservative and tied to directly validated environments rather than informal
assumptions.

## Development Notes

The most productive workflow when extending the project is:

1. add or refine a semantic adapter in `schema_adapters.py`;
2. validate the resulting extraction model with `formatter_explain`;
3. update the relevant summary, synthetic provider, or renderer behavior;
4. add focused tests for both the extraction path and the LLDB-facing surface.

Because LLDB formatting involves both debugger behavior and ABI details, changes
should be evaluated not only by unit tests but also, when possible, by direct
LLDB integration runs in a validated local environment.

## License

This project is licensed under the **MIT License**. See [LICENSE](LICENSE) for
details.
