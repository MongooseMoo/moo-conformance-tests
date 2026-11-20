# test-suspended-debug-flag

## Goal

Toast-verified conformance tests for the debug flag of a SUSPENDED task across
a checkpoint restart (`src/moo_conformance/_tests/server/suspended_debug_flag.yaml`),
and a report of whether Barn's fix branch (`fix/reloaded-fork-debug-flag`,
Barn PR 947) and Barn master agree with Toast. No Barn change, no expectation
changed to suit Barn. The queued-fork half is `fork_debug_flag.yaml`
(`agent-notes/test-fork-debug-flag.md`).

## State

`src/moo_conformance/_tests/server/suspended_debug_flag.yaml`, 8 cases, a new
commit on branch `test/fork-debug-flag`. Not pushed by me.

- Stock WSL Toast oracle, first run, expectations unchanged since:
  `9 passed in 44.35s` (8 cases plus admission).
- Barn fix branch (worktree `C:/Users/Q/code/barn-reloaded-fork-debug`,
  nothing changed there): `9 passed in 42.65s`.
- Barn `origin/master` (the merge of Barn PR 928):
  `3 failed, 6 passed in 65.96s (0:01:05)`. Failing:
  - `suspended_non_debug_verb_raises_after_checkpoint_restart`: expected
    `["raised", "E_TYPE"]`, got `["value", "E_TYPE"]`
  - `suspended_non_debug_frame_under_debug_frame_both_raise_after_checkpoint_restart`:
    expected `[["raised", "E_TYPE"], ["raised", "E_TYPE"]]`, got
    `[["value", "E_TYPE"], ["raised", "E_TYPE"]]`
  - `suspended_debug_frame_under_non_debug_frame_both_raise_after_checkpoint_restart`:
    expected `[["raised", "E_TYPE"], ["raised", "E_TYPE"]]`, got
    `[["raised", "E_TYPE"], ["value", "E_TYPE"]]`
- Duplicate lint as CI runs it
  (`moo-lint-duplicates --tests-dir=src/moo_conformance/_tests --baseline=ci/duplicate-baseline.json`):
  `Duplicate lint passed.`

What Toast does (each frame does `1 + "a"` after `suspend()` returns):

| Case | Frames (outer to inner) | Restart | After resume |
|---|---|---|---|
| `suspended_debug_verb_raises_after_resume` | d | no | raises |
| `suspended_non_debug_verb_gets_error_value_after_resume` | not d | no | value |
| `suspended_debug_verb_raises_after_checkpoint_restart` | d | yes | raises |
| `suspended_non_debug_verb_raises_after_checkpoint_restart` | not d | yes | raises |
| `suspended_non_debug_frame_under_debug_frame_keeps_each_flag_after_resume` | d, not d | no | outer raises, inner value |
| `suspended_debug_frame_under_non_debug_frame_keeps_each_flag_after_resume` | not d, d | no | outer value, inner raises |
| `suspended_non_debug_frame_under_debug_frame_both_raise_after_checkpoint_restart` | d, not d | yes | both raise |
| `suspended_debug_frame_under_non_debug_frame_both_raise_after_checkpoint_restart` | not d, d | yes | both raise |

So on Toast a task suspended in a verb without `d`, checkpointed, and resumed
after a restart runs the rest of that verb with debug on, and so does every
other frame of that task. Without a restart each frame keeps its verb's flag.

### Run record

- Fixture: `src/moo_conformance/_db/Test.db`, 2035 bytes, SHA-256
  `1a3f23ebb549e02ccf5341668425118fcdc935b977096add87bc2a8ef29d408e`.
- Toast: `/root/src/toaststunt/build-release/moo` in WSL distro `Debian`,
  SHA-256 `61dd1799d82f75e33cb9c42fe48bd1966199ad83fda2f6298e3a7f872cc613dd`;
  its source checkout's HEAD equals `implementation_ref` in Barn's
  `profiles/toast/stock-wsl-testdb.json`.
- Barn fix branch: `bin/barn` built in WSL by `make conformance`, SHA-256
  `dce5b85f741ad9a8d0e5be013fb61401f7c6b483dbfdf690d899a289ed980901`.
- Barn master: scratch worktree `C:/Users/Q/code/barn-suspended-debug-scratch`
  detached at `origin/master`, `bin/barn` SHA-256
  `ea6d8f9e4e6a1f7191e3e9c6881897bf0d2c2ecc7f5346db39d310875b426576`.
  Worktree removed afterwards.
- `/mnt/c` worked; no copies under the Linux home were needed.
- WSL load average when the runs started: 29.85 (1 min).

Toast command (Git Bash on the workstation):

```
wsl -d Debian -u root --exec bash -lc 'set -euo pipefail; cd /mnt/c/Users/Q/code/barn-reloaded-fork-debug; make conformance-toast CONFORMANCE_SUITE=/mnt/c/Users/Q/code/moo-conformance-tests-fork-debug CONFORMANCE_ENV=/root/.cache/suspended-debug-flag-conformance CONFORMANCE_PATHS=/mnt/c/Users/Q/code/moo-conformance-tests-fork-debug/src/moo_conformance/_tests/server/suspended_debug_flag.yaml K=suspended_debug_flag CONFORMANCE_ARGS="-v --tb=short"'
```

Barn commands: the same with `make conformance` in place of
`make conformance-toast` and `export GOFLAGS=-buildvcs=false;` before `make`,
once with `cd /mnt/c/Users/Q/code/barn-reloaded-fork-debug` and once with
`cd /mnt/c/Users/Q/code/barn-suspended-debug-scratch`.

## Decisions and why

- The suspending code is the body of a zero-delay fork, so the eval that
  starts it returns the task id at once and the suspended task's outermost
  frame is the verb under test (one frame in the single-frame cases).
- Each frame does `1 + "a"` inside try/except after `suspend()` returns and
  records `{"raised", code}` or `{"value", code}` in its own property, so the
  two-frame cases show each frame separately (`inner_result`, `outer_result`).
- Before the checkpoint a polled step requires `stage == "suspending"` and the
  task in `queued_tasks()`, so the dump holds a suspended task and not a
  queued fork.
- The suspend is 8 seconds; the step after the restart asserts the results are
  still empty, the task still queued and the verb flags as created, the same
  pattern as `fork_debug_flag.yaml`.
- The two-frame cases without a restart were added as the baseline for the
  two-frame restart cases.

## Surprises

- None in behaviour: Toast returned what the reading of `write_activ_as_pi`
  and `read_activ_as_pi` in Barn's `agent-notes/fix-reloaded-fork-debug-flag.md`
  predicted, on the first run.
- `moo-lint-duplicates` with no arguments exits 1 on duplicates that are
  already in `ci/duplicate-baseline.json`; CI's form with `--baseline` is the
  one that counts.

## Unverified

- A verb defined on an anonymous object (a different definer type code) is not
  tested.
- A task suspended in `read()` or with no timeout is not tested; only
  `suspend(8)`.
- Cross-engine (one engine writes the checkpoint, the other resumes) was not
  run for this file.
- Each engine was run once.

## Next step

Team lead pushes the commit to PR 240. The file is Toast-green and Barn-master
red on purpose: it goes green on Barn with Barn PR 947.
