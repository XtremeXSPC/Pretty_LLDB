# Advanced LLDB Formatters for C++ Data Structures

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Language](https://img.shields.io/badge/Language-Python-blue.svg)]()
[![Debugger](https://img.shields.io/badge/Debugger-LLDB-orange.svg)]()

A powerful, modern, and extensible Python-based formatter package for LLDB that provides rich, interactive visualizations and summaries for common C++ data structures. Designed to work seamlessly with IDEs like VS Code (via CodeLLDB), this package goes beyond simple text summaries, offering in-IDE web-based visualizers.

![Showcase Example](/Assets/Example.webp)

---

## Features

- **Clean & Informative Summaries:** Get concise, readable one-line summaries for your data structures directly in the debugger's variable panel.
- **Interactive Visualizers:** Go beyond text with rich, interactive visualizers for Lists, Trees, and Graphs that open directly inside VS Code.
- **Console Pretty-Printing:** Use custom commands like `pptree` to print a visual representation of your tree directly in the LLDB console.
- **Graphviz Export:** Export Trees and Graphs to `.dot` files for offline analysis and documentation using `export_tree` and `export_graph`.
- **Highly configurable:** Customize formatter behavior at runtime with the `formatter_config` command.
- **Extensible architecture:** Built with an advanced Strategy and Registry pattern, making it incredibly easy to add support for new data structures or visualization strategies.

## Supported Data Structures

The formatters are designed to be generic and will automatically detect and format classes with common member names.

- **Linear Containers:** `LinkedList`, `Stack`, `Queue` (and custom variants).
  - Recognizes members like `head`, `top`, `next`, `count`, `size`.
- **STL Containers:** `std::vector` (libc++ layout).
  - Shows size, capacity, data pointer, and values preview.
- **Trees:** Binary Search Trees and other node-based trees.
  - Recognizes `root`, `left`, `right`, `children`, `value`.
- **Graphs:** Adjacency-list based graphs.
  - Recognizes `nodes`, `adj`, `neighbors`, `value`.

---

## Installation

1. **Clone the Repository:**

   ```sh
   git clone https://github.com/XtremeXSPC/Pretty_LLDB.git /path/to/LLDB_Formatters
   ```

   A common location is `~/.lldb/`, but any path will work.

2. **Load the Formatters in LLDB:**
   Add the following command to your global LLDB initialization file (`~/.lldbinit`):

   ```
   command script import /path/to/LLDB_Formatters
   ```

   This ensures the formatters are loaded every time you start a debug session.

3. **(Optional) For VS Code users:**
   You can also load the formatters per-project by adding it to your `launch.json` configuration:

   ```json
   "configurations": [
       {
           "name": "Debug C++",
           "type": "lldb",
           "request": "launch",
           // ... your other settings ...
           "initCommands": [
               "command script import /path/to/LLDB_Formatters"
           ]
       }
   ]
   ```

---

## Usage

Once installed, the formatters work automatically. Simply inspect your variables in the debugger GUI or use `print` in the LLDB console.

### Custom Commands

This package adds several powerful commands to your LLDB console. Use `fhelp` to see them all.

| Command              | Alias   | Description                                                                     |
| :------------------- | :------ | :------------------------------------------------------------------------------ |
| `formatter_help`     | `fhelp` | Displays a detailed list of all custom commands.                                |
| `formatter_config`   | `fconf` | View or change global settings (e.g., `formatter_config summary_max_items 50`). |
| `weblist <var>`      | -       | Opens an interactive visualizer for a list.                                     |
| `webtree <var>`      | `webt`  | Opens an interactive visualizer for a tree.                                     |
| `webgraph <var>`     | `webg`  | Opens an interactive visualizer for a graph.                                    |
| `pptree <var>`       | -       | Pretty-prints a tree structure in the console.                                  |
| `export_tree <var>`  | -       | Exports a tree to a Graphviz `.dot` file.                                       |
| `export_graph <var>` | -       | Exports a graph to a Graphviz `.dot` file.                                      |

---

## Architecture Overview

This project uses an advanced software architecture to ensure it is robust and easy to extend.

- **Registry Pattern:** Formatters are automatically discovered using Python decorators. Adding support for a new data structure is as simple as creating a new class—no need to edit central initialization files.
- **Strategy Pattern:** The logic for traversing a data structure (e.g., "pre-order traversal" for a tree) is separated from the presentation logic. This makes it easy to add new traversal algorithms without changing the core formatter code.
- **Configuration Object:** All settings are managed in a single, clean configuration object, providing a centralized point of control.

## Contributing

Contributions are welcome! Whether it's adding a new visualizer, supporting a new data structure, or improving the documentation, your help is appreciated.

1. **Fork the repository.**
2. **Create a new branch** (`git checkout -b feature/your-feature-name`).
3. **Make your changes.** Follow the existing code style and architecture.
4. **Submit a Pull Request.**

---

## License

This project is licensed under the **MIT License**. See the [LICENSE](LICENSE) file for details.
