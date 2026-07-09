# read_stdin coverage report

## Summary

Implemented conformance coverage for the ToastStunt example `read_stdin()`
extension and added the narrow managed-server primitive needed to drive process
stdin safely.

Covered behaviors:

- `function_info("read_stdin")` signature for zero-argument registration.
- Argument rejection with `E_ARGS`.
- Real blocking/resume shape: a forked task calls `read_stdin()`, remains
  incomplete before process stdin is written, then resumes after `write_stdin`.
- Source-defined return transformation where a trailing newline is replaced
  with `X`.
- Source-defined `a*` input error branch returning `E_NACC`.

## Files changed

- `docs/YAML_SCHEMA.md`
- `src/moo_conformance/runner.py`
- `src/moo_conformance/schema.py`
- `src/moo_conformance/server.py`
- `src/moo_conformance/_tests/builtins/read_stdin.yaml`
- `tests/test_managed_server.py`
- `tests/test_schema.py`

## Commands run

- `uv run pytest tests/test_schema.py tests/test_managed_server.py -q`
  - Outcome: failed, with `tests/test_managed_server.py::test_managed_server_installs_exec_fixtures` asserting executable mode on Windows. This was unrelated exec-fixture coverage already present in the current tree; the stdin-specific tests in that file were not the failing tests.
- `uv run pytest tests/test_schema.py::test_write_stdin_step_accepts_scalar_text tests/test_schema.py::test_write_stdin_step_accepts_mapping_text tests/test_managed_server.py::test_managed_server_opens_process_stdin_pipe tests/test_managed_server.py::test_managed_server_write_stdin -q`
  - Outcome: `4 passed in 0.18s`.
- `uv run moo-conformance -k read_stdin --collect-only`
  - Outcome: `5/11451 tests collected (11446 deselected) in 2.80s`.
- `wsl bash -lc 'cd /mnt/c/Users/Q/code/moo-conformance-tests && command -v uv && test -x /root/src/toaststunt/build-release/moo && echo READY'`
  - Outcome: `/root/.local/bin/uv` and `READY`.
- `wsl bash -lc 'cd /mnt/c/Users/Q/code/moo-conformance-tests && uv run moo-conformance -k read_stdin --server-command="/root/src/toaststunt/build-release/moo {db} {db}.out -p {port}"'`
  - Outcome: failed before tests because WSL `uv` tried to remove the Windows `.venv/Scripts` directory and hit `Permission denied (os error 13)`.
- `wsl bash -lc 'cd /mnt/c/Users/Q/code/moo-conformance-tests && UV_PROJECT_ENVIRONMENT=.venv-wsl uv run moo-conformance -k read_stdin --server-command="/root/src/toaststunt/build-release/moo {db} {db}.out -p {port}"'`
  - Outcome: `5 skipped, 11455 deselected in 7.69s`. All focused tests skipped because the current WSL Toast build does not provide `read_stdin`.
- `git diff --cached --check`
  - Outcome before implementation commit: passed with no output.

## Commit

- Implementation commit: `1e1a8ba1806f31857748082c95c4e56b486e6925`

## Deferred behavior

- No runnable live `read_stdin()` behavior was observed on the current WSL Toast oracle because the checked ToastStunt source has `#define EXAMPLE 0` in `src/extensions.cc`, and `read_stdin` is registered only inside `#if EXAMPLE`.
- The suite keeps the behavioral coverage present and deterministic for builds that compile the example extension, using `skip_if: "missing builtin.read_stdin"` for ordinary builds where the builtin is absent.
