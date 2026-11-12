# jepsen/toast-divergences

## Goal

Pin, as Toast-passing conformance tests, the five task/permission/signal behaviors that
Barn's source reading said diverge from Toast (Barn report
`reports/jepsen-toast-task-semantics.md`), as the prerequisite for Barn's Jepsen PR E.

## State

All eight new tests pass the managed WSL stock Toast oracle
(`/root/src/toaststunt/build-release/moo`, `make conformance-toast` from the Barn checkout
with `CONFORMANCE_SUITE` pointing here). On Barn master, seven fail and one passes.

| Test | Toast |
|---|---|
| `server/signals_timers.yaml::sigalrm_during_running_task_requests_checkpoint_without_aborting_task` | checkpoint runs, task completes |
| `server/signals_timers.yaml::sigalrm_during_blocked_outbound_connect_fires_connect_timeout_not_checkpoint` | connect fails at once with `{E_INVARG, "Connection failure"}`, no checkpoint |
| `server/restart_task_semantics.yaml::indefinitely_suspended_task_across_checkpoint_restart` | task stays suspended after load (CI oracle) |
| `server/restart_task_semantics.yaml::restored_overdue_fork_runs_after_server_started_returns` | `["started", "task"]` |
| `builtins/properties.yaml::delete_property_missing_on_unwritable_object_checks_permission_first` | `E_PERM` |
| `builtins/properties.yaml::clear_property_missing_for_nonowner_is_propnf` | `E_PROPNF` |
| `builtins/set_connection_option_call_shapes.yaml::set_connection_option_programmer_other_unconnected_is_perm` | `E_PERM` |
| `builtins/notify_semantics.yaml::no_flush_notify_returns_zero_when_unread_output_queue_is_full` | a later no_flush notify returns 0 |

## Decisions and why

- The blocked connect uses `192.0.2.1:9` (TEST-NET-1); a connect there hangs from WSL, so
  the connect timeout timer is pending when SIGALRM arrives. Toast's SIGALRM handler runs
  the head of its sorted real-time timer list (`timers.cc:67-79`).
- The pinned oracle is built without `IS_WSL`, so task seconds limits use SIGVTALRM; a
  SIGALRM during a running task is the checkpoint timer. Test 1a pins that.
- The notify overflow needs a peer that does not read: Toast pushes queued output to the
  socket before deciding (`network.cc:1347-1354`). The secondary `new_connection` socket
  only reads when asked.
- `restart_task_semantics.yaml` declares no `features: fork`: that capability needs its
  provider test in the same session, so a focused selection skipped both tests.

## Surprises

- After the first no_flush 0, a further no_flush notify returned 1 on Toast, so the test
  asserts only that a 0 occurs.
- The two Toast oracles disagree on the indefinite suspend. The WSL stock binary
  (source `aecc51e9`) writes `INTNUM_MAX` with `%d`, prints `-1`, and resumes the task
  with 0 after load. This repo's CI oracle, MongooseMoo/toaststunt `eaaa1972` (a
  descendant of `aecc51e9`), writes it with `PRIdN` and reads a negative start time as
  `INTNUM_MAX` ("Old 64-bit servers wrote an indefinite INTNUM_MAX timeout through a
  32-bit %d conversion, producing -1"), so the task stays suspended (`[[], 1]` on both
  64-bit CI profiles). The test pins the fixed behavior of the CI oracle.

## Next step

Merge; then Barn's `fix/toast-divergences` makes the seven failing tests pass.
