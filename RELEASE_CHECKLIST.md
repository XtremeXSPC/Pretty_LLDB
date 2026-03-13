# Release Checklist

This checklist is the release gate for the `0.y.z` development line.

## Semantic Versioning Expectations

- `0.MINOR.0`: may introduce new formatter capabilities, compatibility claims,
  command additions, and deliberate output-shape changes.
- `0.y.PATCH`: bug fixes, guard rails, test-only updates, and documentation or
  packaging corrections without intentional command-surface breaks.
- `1.0.0`: reserved for the point where the adapter surface, packaging story,
  and operational support contract are considered stable.

## Release Steps

1. Update `CHANGELOG.md` and move release-ready items out of `Unreleased`.
2. Update `COMPATIBILITY.md` with the environments directly validated for the release.
3. Run the pure-Python unit suite:
   `python3 -m unittest -q LLDB_Formatters.tests.test_command_ux LLDB_Formatters.tests.test_diagnostics LLDB_Formatters.tests.test_extraction LLDB_Formatters.tests.test_graph_formatters LLDB_Formatters.tests.test_linear_formatters LLDB_Formatters.tests.test_linear_strategy LLDB_Formatters.tests.test_pointers LLDB_Formatters.tests.test_renderers LLDB_Formatters.tests.test_schema_adapters LLDB_Formatters.tests.test_summary_semantics LLDB_Formatters.tests.test_synthetic_providers LLDB_Formatters.tests.test_tree_strategies LLDB_Formatters.tests.test_value_rendering LLDB_Formatters.tests.test_web_visualizer`
4. Run the LLDB integration suite on the canonical macOS environment:
   `python3 -m unittest -q LLDB_Formatters.tests.test_lldb_integration`
5. Run the benchmark suite and archive the results with the release notes:
   `python3 benchmarks/benchmark_suite.py --iterations 3 --list-size 2000 --tree-depth 128 --graph-nodes 200 --graph-degree 8 --tree-max-depth 128`
6. Sanity-check package contents:
   `python3 -m compileall LLDB_Formatters benchmarks`
7. Verify repository import still works from LLDB:
   `lldb -b -Q -o "command script import /absolute/path/to/Pretty_LLDB" -o quit`
8. Tag the release as `vX.Y.Z` only after all gates above are green.

## Minimum Release Artifacts

- Updated `CHANGELOG.md`
- Updated `COMPATIBILITY.md`
- Green unit and integration runs
- Benchmark output attached to the release notes
- Tag and short release summary
