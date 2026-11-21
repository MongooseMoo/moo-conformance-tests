# finished_tasks forked flake

## Goal
Stop the intermittent failure of
`builtins/finished_tasks_records.yaml::forked_task_runs_are_background` in Barn CI without
changing what it asserts.

## Evidence
- Barn merge-queue run 44934592070, job "MOO conformance suite": 1 failed, 13828 passed, while the
  workstation's self-hosted runners were all busy. The step that starts `hits = {};` expected
  `[[0, 1], [0, 0]]` and got `[[0, 1]]`.
- `[0, 1]` is the forked task's first run (it ends in `suspend(0)`). `[0, 0]` is its resumed run.
  When the step read `finished_tasks()`, the resumed run had not yet finished and been recorded.

## The race
- Step 3 (`{obj}:ft_forker(); suspend(0); return 1;`) returns once the eval task resumes. The
  forked task's resumption is runnable at about the same moment. Nothing orders it before the
  harness's next command (step 4).
- Barn: the record is written at the end of each run (barn `engine/task_runtime.go:670`,
  `recordFinishedTask` in `engine/lag_callback.go:67`). A suspended task is re-queued by
  `handOffSuspended` (`engine/task_runtime.go:888`, `RequeueYield` about line 951) and resumes on
  any free worker, at the same time as step 4. Under CPU load step 4 reads the list first.
- Toast does not guarantee the order either. In `run_ready_tasks` (`src/tasks.cc`, about lines
  1629-1680), each task queue tries `dequeue_input_task` before `dequeue_bg_task`, so input that is
  already queued runs before a ready background task. Toast passes only because its single loop
  usually runs the resumption before the client's round trip completes. So the fix belongs in the
  test, not in Barn.

## Fix
Step 4 of `forked_task_runs_are_background` gets `poll_ms: 10000`. The harness reruns the read
until `[[0, 1], [0, 0]]` holds (runner.py `_execute_steps`). The expected value is unchanged. A
missing or extra record still fails: `[[0, 1]]` forever times out, and a third record never matches.

## Surprises
- Stock WSL Toast (`/root/src/toaststunt/build-release/moo`, 03af4fa) is built without
  `SAVE_FINISHED_TASKS` (`src/include/options.h:472` is commented out). The managed oracle skips
  the whole suite ("Requires builtin: finished_tasks"). No WSL Toast build had it enabled.
- To check Toast, I built a scratch copy in `/tmp/toast-ft15`: a detached worktree at 03af4fa whose
  only change is `#define SAVE_FINISHED_TASKS 15`, Release build. The oracle binary is untouched.

## Runs (2026-11-21, WSL load average 12-23 from busy CI runners)
Managed harness, CI's Barn server command, `-m "admission or conformance"`,
`--fail-on-unexpected-skip --strict-markers`, `-k "capability_admission or (<suite>)"`, with the
YAML file as the positional selector. Barn is `bin/barn-linux-amd64` built from barn origin/master
a41f6088. The repro file was a scratch suite (deleted, not committed) with 100 copies of the case,
each with its own verb name `ft_forkerNNN`. A shared name would mix records across copies. Each
run is one server and 101 tests (100 copies plus capability_admission).

Before the fix (no `poll_ms`):
- Barn: 5 runs of 100 copies: 1, 0, 3, 2 and 0 failed. That is 6 failures in 500. The first run's
  failure (`forked_rep_032`) was the CI symptom exactly: expected `[[0, 1], [0, 0]]`, got `[[0, 1]]`.
- Toast with SAVE_FINISHED_TASKS=15: 1 run of 100 copies, 101 passed. The unchanged suite file
  passed 7 of 7.
- Stock Toast: 1 passed, 100 skipped (builtin absent).

After the fix (`poll_ms: 10000`):
- Barn: 5 runs of 100 copies, 101 passed each time. 0 failures in 500.
- Toast with SAVE_FINISHED_TASKS=15: 1 run of 100 copies, 101 passed.
- `finished_tasks_records.yaml` itself: Barn 7 passed; Toast with SAVE_FINISHED_TASKS=15 7 passed;
  stock Toast 1 passed and 6 skipped (builtin absent, same as before).

## State
The test change and this note are committed on `fix/flake-finished-tasks-forked`. Not pushed.

## Next step
Publish (push and open a PR) when the lead decides. Separate open question: should the stock oracle
be built with SAVE_FINISHED_TASKS so that this suite is checked against Toast in CI?
