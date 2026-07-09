# Coverage Final Verifier Report

Verdict: MERGE

## Branch and Commit Graph

- Current branch: `main`.
- Tracking state: `main...origin/main [ahead 11]`.
- Ahead/behind: `git rev-list --left-right --count main...origin/main` reported `11 0`.
- `origin/master` does not exist in this checkout; `git rev-parse HEAD origin/main origin/master` failed only for the missing `origin/master` ref.
- HEAD: `a5b815059c8ebef23482fbf855bb0a6f35c5f282` (`Record coverage records commit report`).
- Worktree before writing this report had no tracked modifications, but many unrelated untracked files were already present.

Commits ahead of `origin/main`:

```text
a5b8150 Record coverage records commit report
5e8bc79 Record coverage coordination artifacts
bf71595 Report read_stdin coverage work
1e1a8ba Add read_stdin conformance coverage
98a366a Record portable exec coverage report
4742603 Add portable exec conformance coverage
8e98bac Add network matrix coverage report
28767f2 Document optional extension coverage slice
30cf56d Add optional extension builtin behavior coverage
fb10d43 Add network matrix conformance coverage
02570f0 Add background thread runtime coverage
```

All required commit ids resolved as commit objects and are ancestors of `HEAD`.

## Required Slice Assessment

- #1 background/thread runtime behavior: complete. Commit `02570f0822d6c262a40804016e7efcac9ab944c6` adds `src/moo_conformance/_tests/builtins/background_threads.yaml`. It covers `set_thread_mode`, `thread_pool`, `threads`, and `background_test` behavior with state restoration and cleanup. Report `reports/coverage-background-threads-report.md` is present, added by coordination commit `5e8bc7946690c6e71d4d5284e11e10c1a82af711`.
- #2 console/stdin behavior: complete with residual environment skip risk. Commit `1e1a8ba1806f31857748082c95c4e56b486e6925` adds `write_stdin` schema/runner/managed-server support plus `read_stdin` behavior tests. Report commit `bf7159599c09bce2b64bbb73cada810a48f343e1` is present. The tests are behavioral, but the current WSL Toast binary skipped them because `read_stdin` is unavailable.
- #3 optional extension builtins: complete. Commit `30cf56dd4065f26fba5a65f303bf868f5e97ef2e` adds behavior coverage for spellcheck, simplex noise, malloc stats, and URL/cURL edge cases. Report commit `28767f24a18ea7d3b8e7252697fcf3cefaa8e1c7` is present.
- #4 outbound/listener/network matrix: complete. Commit `fb10d43576487ce51c690021f99dc0840c592f9c` adds listener, connection info, outbound connection, buffered output, lookup, boot, and disabled-option behavior. Report commit `8e98bac2083e41b198aed3eece6a47c88da176af` is present.
- #6 platform-dependent exec behavior: complete. Commit `4742603d2efd74f67ff87b7aa45c16335cb75cb7` adds packaged exec fixtures, fixture installation, and portable exec behavior tests. Report commit `98a366a2159658a441ce9cabaa97fc72a5a0df0d` is present.
- Coordination records: complete. Commit `5e8bc7946690c6e71d4d5284e11e10c1a82af711` adds coordination artifacts and the background report. Report commit `a5b815059c8ebef23482fbf855bb0a6f35c5f282` is present.

The added coverage is not just presence checks: the suites exercise permissions, argument validation, state mutation/restoration, process stdin, listener lifecycle, outbound connection state, exec task suspension, kill/resume behavior, and packaged executable handling.

## Commands and Outcomes

- `git status --short --branch`
  - Passed. Reported `## main...origin/main [ahead 11]` and only untracked files.
- `git branch --show-current`
  - Passed. Output: `main`.
- `git rev-list --left-right --count main...origin/main`
  - Passed. Output: `11 0`.
- `git rev-parse HEAD origin/main origin/master`
  - Failed for missing `origin/master`; confirmed `HEAD=a5b815059c8ebef23482fbf855bb0a6f35c5f282` and `origin/main=2fc2a9e0f6d9ab56dde41b1111664f3ae9b189fd`.
- `git cat-file --batch-check` for all required commit ids
  - Passed. Every required id resolved to a commit object.
- `git merge-base --is-ancestor ... HEAD` for all required commit ids
  - Passed. Every required commit is reachable from `HEAD`.
- `git diff --check`
  - Passed with no output.
- `uv run pytest tests/test_schema.py tests/test_managed_server.py`
  - Passed: `22 passed in 0.16s`.
- `uv run moo-conformance --collect-only -q`
  - Passed: `11461 tests collected in 2.72s`.
- `wsl --cd /mnt/c/Users/Q/code/moo-conformance-tests --exec bash -lc 'UV_PROJECT_ENVIRONMENT=.venv-wsl uv run moo-conformance --server-command="/root/src/toaststunt/build-release/moo {db} {db}.out -p {port}" -q -k background_threads'`
  - Passed: `9 passed, 3 skipped, 11449 deselected in 9.21s`.
- `wsl --cd /mnt/c/Users/Q/code/moo-conformance-tests --exec bash -lc 'UV_PROJECT_ENVIRONMENT=.venv-wsl uv run moo-conformance --server-command="/root/src/toaststunt/build-release/moo {db} {db}.out -p {port}" -q -k read_stdin'`
  - Passed by skip: `5 skipped, 11456 deselected in 8.02s`.
- `wsl --cd /mnt/c/Users/Q/code/moo-conformance-tests --exec bash -lc 'UV_PROJECT_ENVIRONMENT=.venv-wsl uv run moo-conformance --server-command="/root/src/toaststunt/build-release/moo {db} {db}.out -p {port}" -q -k optional_extensions'`
  - Passed: `7 passed, 2 skipped, 11452 deselected in 8.07s`.
- `wsl --cd /mnt/c/Users/Q/code/moo-conformance-tests --exec bash -lc 'UV_PROJECT_ENVIRONMENT=.venv-wsl uv run moo-conformance --server-command="/root/src/toaststunt/build-release/moo {db} {db}.out -p {port}" -q -k network_matrix'`
  - Passed: `3 passed, 2 skipped, 11456 deselected in 8.35s`.
- `wsl --cd /mnt/c/Users/Q/code/moo-conformance-tests --exec bash -lc 'UV_PROJECT_ENVIRONMENT=.venv-wsl uv run moo-conformance --server-command="/root/src/toaststunt/build-release/moo {db} {db}.out -p {port}" -q -k "exec::"'`
  - Passed: `23 passed, 11438 deselected in 9.34s`.

## Residual Risks and Skipped Behavior

- `read_stdin` coverage collected but skipped entirely on the current WSL Toast binary because the builtin is unavailable.
- Optional-extension and network-matrix runs include expected profile-dependent skips for unavailable optional builtins or mutually exclusive outbound-network profile states.
- This verifier did not push and did not modify production or test files.

## Push Acceptability

It is acceptable to push `main` to `origin/main` for the committed coverage work. The current branch is `main`, is ahead of `origin/main` by exactly the 11 required commits, is behind by 0, and all required verifier gates passed. This report file itself is uncommitted and should not be assumed to be part of that push.
