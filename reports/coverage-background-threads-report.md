# Coverage Background Threads Report

## Summary

Added `src/moo_conformance/_tests/builtins/background_threads.yaml` with behavioral
coverage for Toast background/thread runtime builtins:

- `set_thread_mode()` round-trips current activation state, follows MOO integer
  truthiness, and does not leak a mode change into a later eval task.
- `thread_pool()` enforces wizard permission, rejects unknown pool/function names,
  rejects negative MAIN sizes, and accepts `INIT` with zero/positive sizes for
  disable-and-restore behavior.
- `threads()` enforces wizard permission and, when `background_test()` is compiled
  in, reports an active background helper handle while the task is suspended.
- `background_test()` behavior is covered when compiled in: zero-delay echo return
  and synchronous callback execution when `set_thread_mode(0)` disables threading.

The `background_test()` cases use `skip_if: "missing builtin.background_test"`
because Toast registers that builtin only under the `BACKGROUND_TEST` compile-time
option. The current WSL Toast oracle build does not expose it, so those cases were
collected and skipped rather than converted into failing compile-time references.

## Files Changed

- `src/moo_conformance/_tests/builtins/background_threads.yaml`

## Commands Run

- `git status --short --branch`
  - Outcome: branch `main...origin/main`; no tracked-file changes at start, many
    pre-existing untracked files outside this slice.

- `uv run pytest --pyargs moo_conformance --collect-only -q -k background_threads`
  - Outcome: passed collection; `12/11431 tests collected (11419 deselected)` in
    `3.80s`.

- `wsl --cd /mnt/c/Users/Q/code/moo-conformance-tests --exec bash -lc 'uv run moo-conformance --server-command="/root/src/toaststunt/build-release/moo {db} {db}.out -p {port}" -k background_threads -q'`
  - Outcome: failed before tests; WSL `uv` tried to remove the Windows `.venv`
    path and hit `Permission denied`.

- `wsl --cd /mnt/c/Users/Q/code/moo-conformance-tests --exec bash -lc 'UV_PROJECT_ENVIRONMENT=.venv-wsl uv run moo-conformance --server-command="/root/src/toaststunt/build-release/moo {db} {db}.out -p {port}" -k background_threads -q'`
  - Outcome: passed focused Toast oracle execution; `9 passed, 3 skipped, 11424
    deselected in 9.99s`. The three skips were the `background_test()` optional
    compile-time cases.

- `uv run pytest --pyargs moo_conformance --collect-only -q`
  - Outcome: passed full collection; `11436 tests collected in 5.76s`.

- `git diff --check -- src/moo_conformance/_tests/builtins/background_threads.yaml`
  - Outcome: passed with no whitespace errors.

- `git diff --cached --check`
  - Outcome: passed with no whitespace errors before committing the YAML slice.

## Commit Hash

- Coverage commit: `02570f0822d6c262a40804016e7efcac9ab944c6`

## Intentionally Deferred Behavior

- No harness/schema changes were made. Existing YAML mechanisms were sufficient:
  multi-step tests, `wait`, `timeout_ms`, `permission`, and `skip_if`.
- `background_test()` live behavior could not be executed against the current WSL
  Toast oracle because that build does not compile/register `background_test`.
  The tests are present and gated so they will run on a Toast build with the
  optional builtin enabled.
