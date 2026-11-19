# test/fork-debug-flag

## Goal

Pin, as Toast-verified conformance tests, when a forked task takes its verb's
`d` (debug) flag: at the fork statement or when the child starts, and whether
the flag survives a checkpoint and restart while the fork is still queued.
Then report whether Barn's master agrees. No Barn change, no expectation
changed to suit Barn.

## State

`src/moo_conformance/_tests/server/fork_debug_flag.yaml`, 8 cases, on branch
`test/fork-debug-flag` (from `origin/main`). Not pushed, no PR.

- Stock WSL Toast oracle: `9 passed in 33.57s` (8 cases plus admission).
- Barn built from `origin/master` (the merge of Barn PR 945):
  `2 failed, 7 passed in 62.29s`. Failing:
  - `queued_fork_from_non_debug_verb_raises_after_checkpoint_restart`
  - `queued_fork_from_non_debug_verb_raises_after_flag_set_and_checkpoint_restart`

  Both: expected `["raised", "E_TYPE"]`, Barn returned `["value", "E_TYPE"]`.

What Toast does:

| Case | Verb at fork | Changed to | Restart | Forked body |
|---|---|---|---|---|
| `fork_from_debug_verb_raises_in_forked_body` | d | | no | raises |
| `fork_from_non_debug_verb_gets_error_value_in_forked_body` | not d | | no | value |
| `fork_keeps_debug_flag_cleared_after_fork_statement` | d | not d | no | raises |
| `fork_keeps_non_debug_flag_set_after_fork_statement` | not d | d | no | value |
| `queued_fork_from_debug_verb_raises_after_checkpoint_restart` | d | | yes | raises |
| `queued_fork_from_non_debug_verb_raises_after_checkpoint_restart` | not d | | yes | raises |
| `queued_fork_from_debug_verb_raises_after_flag_cleared_and_checkpoint_restart` | d | not d | yes | raises |
| `queued_fork_from_non_debug_verb_raises_after_flag_set_and_checkpoint_restart` | not d | d | yes | raises |

So, for the two behaviours Barn PR 945 changed from source reading alone:

1. "A fork from a verb without d, checkpointed while queued and loaded after a
   restart, runs with debug off" is false on Toast. It runs with debug on
   (`queued_fork_from_non_debug_verb_raises_after_checkpoint_restart`).
2. "A fork takes the d flag when the fork statement executes, not when the
   child starts" is true on Toast while the server keeps running
   (`fork_keeps_debug_flag_cleared_after_fork_statement`,
   `fork_keeps_non_debug_flag_set_after_fork_statement`). Across a checkpoint
   restart the flag at the fork statement is not kept: every reloaded fork
   ran with debug on.

### Run record

- Fixture: `src/moo_conformance/_db/Test.db`, 2035 bytes, SHA-256
  `1a3f23ebb549e02ccf5341668425118fcdc935b977096add87bc2a8ef29d408e`
  (equals `database_checksum` in Barn's `profiles/toast/stock-wsl-testdb.json`).
- Toast: `/root/src/toaststunt/build-release/moo` in WSL distro `Debian`,
  SHA-256 `61dd1799d82f75e33cb9c42fe48bd1966199ad83fda2f6298e3a7f872cc613dd`;
  its source checkout's HEAD equals `implementation_ref` in Barn's
  `profiles/toast/stock-wsl-testdb.json`.
- Barn: scratch worktree `C:/Users/Q/code/barn-fork-debug-scratch` detached at
  `origin/master` (the merge of Barn PR 945), built in WSL
  with go1.27.1 by `make conformance`; `bin/barn` SHA-256
  `20c119c5a53a14770df105b1ade6139c2a0aa0059c18942b86610215760c811b`.
  Worktree removed afterwards.
- `/mnt/c` worked; no copies under the Linux home were needed.

Toast command (PowerShell or Git Bash on the workstation):

```
wsl -d Debian -u root --exec bash -lc 'set -euo pipefail; cd /mnt/c/Users/Q/code/barn-fork-debug-scratch; make conformance-toast CONFORMANCE_SUITE=/mnt/c/Users/Q/code/moo-conformance-tests-fork-debug CONFORMANCE_ENV=/root/.cache/fork-debug-flag-conformance CONFORMANCE_PATHS=/mnt/c/Users/Q/code/moo-conformance-tests-fork-debug/src/moo_conformance/_tests/server/fork_debug_flag.yaml K=fork_debug_flag CONFORMANCE_ARGS="-v --tb=short"'
```

Barn command: the same with `make conformance` in place of
`make conformance-toast`, and `export GOFLAGS=-buildvcs=false;` before `make`
(see Surprises).

## Decisions and why

- The body does `1 + "a"` inside try/except and records `{"raised", code}` or
  `{"value", code}` so one property tells debug on from debug off.
- Without a restart, the fork statement (delay 0) and `set_verb_info()` run in
  one eval task, so the forked task cannot start before the flag changes. No
  timing is involved.
- With a restart, the fork delay is 6 seconds and the step after the restart
  asserts the task is still queued, the result still empty, and the verb's
  flags as left before the checkpoint: the same pattern as
  `fork_line_numbers_checkpoint_restart.yaml`.
- In the restart cases the flag is changed before the checkpoint, in the same
  task as the fork statement.
- Error codes are compared as `toliteral()` strings.
- The first draft expected "value" for the two non-d restart cases, from
  reading Toast source. Toast returned "raised" for both, so the expectations
  and the test names were changed to what Toast returned.

## Surprises

- Toast runs every reloaded queued fork with debug on, although
  `write_activ_as_pi` (WSL `/root/src/toaststunt/src/execute.cc:3859`) looks
  as if it saves `a.debug`. My reading of why, not checked against a
  checkpoint file: that `dbio_printf` passes `a.vloc`, a 16-byte `Var`
  (`structures.h:164`, value union then `type`), to a single `%PRIdN`
  conversion, so the final `%d` prints the second half of the `Var` (its
  `type`, `TYPE_OBJ` = 1 for a verb defined on an ordinary object) and
  `a.debug` is never printed. `read_activ_as_pi` (`execute.cc:3894`) then
  reads that 1 into `a->debug`. If that is the cause, the saved number is the
  type of the verb's definer, not the flag.
- Git inside WSL cannot open a worktree made by Windows git (its `.git` file
  holds a `C:/` path), so `go build` there needs `GOFLAGS=-buildvcs=false`.

## Unverified

- The explanation above of why Toast loads debug as on. The behaviour is
  verified; the cause is source reading only.
- Suspended (not forked) tasks use the same `write_activ_as_pi`
  (`execute.cc:4019`); whether a suspended non-d verb resumes with debug on
  after a restart is not tested here.
- A verb defined on an anonymous object (a different `vloc` type) is not
  tested.
- Changing the flag after the restart, before the reloaded task starts, is not
  tested.

## Next step

Team lead pushes and opens the PR. It is Toast-green and Barn-red on purpose:
merging it before Barn loads a queued fork with debug on turns Barn CI red.
