# Portable exec coverage report

## Summary

Implemented portable managed-server exec fixtures and converted the existing skipped exec coverage into runnable deterministic tests. The exec suite now covers:

- wizard permission and path/security rejections, preserving existing coverage
- process stdin/stdout/stderr I/O through `test_io`
- argument passing through `test_args`
- exit status through `test_exit_status`
- delayed process output through `test_with_sleep`
- invalid binary stdin rejection
- suspended exec visibility in `queued_tasks()`
- `kill_task()` success and repeated-kill failure
- `resume()` rejection for an exec-suspended task, with cleanup
- `task_stack()` parity between ordinary suspended tasks and exec-suspended tasks
- multiple simultaneous exec tasks, including selective kill behavior

## Files changed

- `pyproject.toml`
- `src/moo_conformance/server.py`
- `src/moo_conformance/_exec_fixtures/echo`
- `src/moo_conformance/_exec_fixtures/sleep`
- `src/moo_conformance/_exec_fixtures/test_args`
- `src/moo_conformance/_exec_fixtures/test_exit_status`
- `src/moo_conformance/_exec_fixtures/test_io`
- `src/moo_conformance/_exec_fixtures/test_with_sleep`
- `src/moo_conformance/_exec_fixtures/true`
- `src/moo_conformance/_tests/server/exec.yaml`
- `tests/test_managed_server.py`
- `reports/coverage-exec-portable-report.md`

## Commands run

- `uv run pytest tests/test_managed_server.py -q`
  - Outcome: `10 passed in 0.19s`
- `uv run moo-conformance --collect-only -q -k "exec::"`
  - Outcome: `23/11461 tests collected (11438 deselected) in 2.64s`
- `wsl sh -lc 'cd /mnt/c/Users/Q/code/moo-conformance-tests && UV_PROJECT_ENVIRONMENT=.venv-wsl uv run moo-conformance --server-command="/root/src/toaststunt/build-release/moo {db} {db}.out -p {port}" -q -k "exec::"'`
  - Outcome: `23 passed, 11438 deselected in 7.37s`
- `git diff --check`
  - Outcome: passed with no output

## Commit

- Commit hash: `4742603d2efd74f67ff87b7aa45c16335cb75cb7`

## Deferred behavior

- No exec behaviors from the prompt are intentionally deferred.
- Native Windows executable semantics remain outside this slice because the Toast oracle for this repo is WSL Toast, and Toast `exec()` uses POSIX `execve()` semantics. The fixture installer still copies fixtures in managed-server mode on all platforms and applies executable bits where the filesystem honors them.
