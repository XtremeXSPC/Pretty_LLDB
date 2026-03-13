# Changelog

All notable changes to this project will be documented in this file.

The format follows Keep a Changelog, and the release process follows the
pre-1.0 semantic-versioning expectations documented in `RELEASE_CHECKLIST.md`.

## [Unreleased]

### Added

- A local benchmark suite for large lists, deep trees, and dense graphs in
  `benchmarks/benchmark_suite.py`.
- Configurable tree traversal depth safeguards across extraction, summaries,
  synthetic providers, and console tree printing.
- A tracked compatibility matrix and a release checklist for Sprint 5.
- Initial CI workflow covering pure-Python tests, LLDB integration, and a
  benchmark smoke run.
- PEP 621 packaging metadata for reproducible builds and stable package data.

### Changed

- Synthetic providers now cache resolved children between repeated LLDB queries.
- Graph synthetic expansion now respects `synthetic_max_children`.
- Tree synthetic expansion resolves only the addresses needed for the selected
  traversal window.
