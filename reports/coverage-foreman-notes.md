# Coverage Foreman Notes

Objective: for each identified gap except DB backend gap #5, launch a subagent to plan and implement tests, then merge the completed work to main/master.

Scope:
- #1 background/thread runtime behavior
- #2 console/stdin behavior
- #3 optional extension builtins
- #4 outbound/listener/network matrix
- #6 platform-dependent exec behavior

Excluded:
- #5 non-native DB backend and roundtrip behavior

Status:
- 2026-07-09: Foreman protocol activated with `ward set foreman`.
- 2026-07-09: Prompt files created under `prompts/coverage-*.md`.
- 2026-07-09: Background/thread worker completed code commit `02570f0822d6c262a40804016e7efcac9ab944c6` (`Add background thread runtime coverage`). Added `src/moo_conformance/_tests/builtins/background_threads.yaml`. Verification reported: focused collect `12/11431` selected passed, WSL Toast focused run `9 passed, 3 skipped`, full collect `11436 tests collected`, and diff checks passed. Report written to `reports/coverage-background-threads-report.md` but not committed by the worker because unrelated staged files were present from other active work.
- 2026-07-09: Optional-extension worker completed commits `30cf56d` (`Add optional extension builtin behavior coverage`) and `28767f2` (`Document optional extension coverage slice`). Changed `src/moo_conformance/_tests/builtins/url_curl.yaml`, added `src/moo_conformance/_tests/builtins/optional_extensions.yaml`, and committed `reports/coverage-optional-extensions-report.md`. Verification reported: collect-only `31 selected, 11430 deselected`, WSL Toast focused run `29 passed, 2 skipped, 11430 deselected`, and `git diff --check` passed.
- 2026-07-09: Network-matrix worker completed commits `fb10d43576487ce51c690021f99dc0840c592f9c` (`Add network matrix conformance coverage`) and `8e98bac2083e41b198aed3eece6a47c88da176af` (`Add network matrix coverage report`). Added `src/moo_conformance/_tests/builtins/network_matrix.yaml` and committed `reports/coverage-network-matrix-report.md`. Verification reported: focused collect `5/11460 tests collected`, WSL Toast focused run `3 passed, 2 skipped`, and `git diff --check` passed.
- 2026-07-09: Exec-portability worker completed commits `4742603d2efd74f67ff87b7aa45c16335cb75cb7` (`Add portable exec conformance coverage`) and `98a366a2159658a441ce9cabaa97fc72a5a0df0d` (`Record portable exec coverage report`). Added portable exec fixtures and updated `src/moo_conformance/_tests/server/exec.yaml`; committed `reports/coverage-exec-portable-report.md`. Verification reported: `uv run pytest tests/test_managed_server.py -q` as `10 passed`, collect-only `23/11461 selected`, WSL Toast managed run `23 passed`, and `git diff --check` passed.
- 2026-07-09: Read-stdin worker completed commits `1e1a8ba1806f31857748082c95c4e56b486e6925` (implementation) and `bf7159599c09bce2b64bbb73cada810a48f343e1` (report). Added managed-server stdin support and `src/moo_conformance/_tests/builtins/read_stdin.yaml`; committed `reports/coverage-read-stdin-report.md`. Verification reported: stdin-specific unit/schema tests `4 passed`, collect-only `5/11451 tests collected`, WSL Toast focused run `5 skipped` because current Toast has `read_stdin` absent (`EXAMPLE 0`), and `git diff --cached --check` passed.
