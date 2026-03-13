# Compatibility Matrix

This file is the tracked compatibility contract for the `0.5.x` development
line. Only environments with direct validation should be marked as `Supported`.

## Status Legend

- `Supported`: directly validated by local runs or CI.
- `Partial`: implementation exists, but direct end-to-end validation is still limited.
- `Planned`: targeted by Sprint 5, but not yet validated.

## Development Line

- Package version: `0.5.0.dev0`
- Last updated: March 13, 2026

## Validated Environments

| Area                        | Environment                     | Status    | Evidence                                             | Notes                                                                                                                 |
| :-------------------------- | :------------------------------ | :-------- | :--------------------------------------------------- | :-------------------------------------------------------------------------------------------------------------------- |
| Pure Python formatter logic | Local development environment   | Supported | `88` pure-Python unit tests passed on March 13, 2026 | Covers traversal logic, extraction, schema adapters, renderer payloads, command UX, and synthetic-provider semantics. |
| Real LLDB integration       | macOS local environment         | Supported | `17` LLDB integration tests passed on March 13, 2026 | Executed outside the sandbox with the repository fixture harness.                                                     |
| Canonical LLDB runtime      | `lldb-1703.0.236.103`           | Supported | Local integration suite                              | Output formatting and command registration validated through batch-mode LLDB.                                         |
| Compiler / ABI probing      | `clang++-default`               | Supported | `available_compiler_variants()` local probe          | Canonical default compiler variant discovered by the integration harness.                                             |
| Compiler / ABI probing      | `clang++-libcxx`                | Supported | `available_compiler_variants()` local probe          | Explicit libc++ variant discovered and exercised by ABI-aware tests.                                                  |
| CodeLLDB HTML display path  | VS Code / CodeLLDB              | Partial   | Implementation + unit coverage                       | Automated end-to-end IDE validation is still missing.                                                                 |
| Terminal browser fallback   | Standard terminal LLDB          | Partial   | Implementation + unit coverage                       | Browser-open behavior is not yet asserted in automation.                                                              |
| Linux / Windows LLDB        | Non-macOS debugger environments | Planned   | No direct validation yet                             | Candidate future matrix expansion after the macOS canonical lane is stable.                                           |
| Multi-version CI            | GitHub Actions unit matrix      | Planned   | Workflow added in Sprint 5                           | Becomes `Supported` once the workflow has executed successfully.                                                      |

## Compatibility Notes

- Support claims are intentionally conservative and tied to direct evidence.
- Formatter output remains pre-1.0 and may still evolve between minor releases.
- Environments should only be promoted from `Partial` or `Planned` after a
  repeatable automated run exists.
