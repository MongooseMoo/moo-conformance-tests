# kill_task() removes the task from the caller's queued_tasks() at once

## Goal

Pin ToastStunt's behaviour that a task killed by kill_task() no longer appears in
queued_tasks() called later in the same task, for a forked task that has not
started and for a suspended task. Barn shows killed tasks until the killer's
transaction commits; the Barn fix is a separate PR.

## State

Two tests added to builtins/task_management.yaml. Managed WSL runs: ToastStunt
(CI server command) passes both; Barn master 36eba5f2 fails both.

## Decisions and why

The existing coverage was server/exec.yaml::multiple_simultaneous_execs_work,
which is gated on exec_support/forking/tasks and so skipped on Barn. These tests
need only fork, suspend, kill_task and queued_tasks, so every engine runs them.

## Surprises

None beyond the gating above.

## Next step

Merge after CI; Barn fix PR follows.
