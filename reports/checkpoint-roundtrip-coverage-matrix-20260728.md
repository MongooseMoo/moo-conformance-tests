# Toast checkpoint round-trip coverage matrix

Date: 2026-07-28

## Authority and managed invocation

The behavioral authority is stock ToastStunt commit
`aecc51e9449c6e7c95272f0f044b5ba38948459e` at
`/root/src/toaststunt`. The executable is
`/root/src/toaststunt/build-release/moo`.

The tracked conformance checkout resolves inside WSL to:

```text
/mnt/c/Users/Q/code/moo-conformance-tests
```

The managed WSL command shape is:

```bash
UV_PROJECT_ENVIRONMENT=/tmp/barn-checkpoint-conformance-uv \
uv run moo-conformance \
  --server-command \
  "/root/src/toaststunt/build-release/moo {db} {db}.out -p {port}" \
  -k "<selector>" -v -rs
```

This is managed-server mode. `ManagedServer` copies the bundled database into a
temporary directory, launches the command itself, stops the process for
`restart_server`, adopts the checkpoint output back into the managed input
path, restarts, reconnects, and removes the managed directory at session end.
It is not a manual Toast launch.

Current oracle proof:

- existing delayed-fork restart rows: 2 passed, 11,564 deselected in 28.09s;
- existing `dump_persistence` rows: 11 passed, 11,555 deselected in 37.05s.

## Toast source contract

The following is grounded in the named functions in the stock source checkout.

- `tasks.cc::write_forked_task()` writes rounded start time, task id,
  activation identity, the runtime environment in program-variable order, and
  the fork program. `read_task_queue()` restores the saved id and schedule.
- `tasks.cc::write_suspended_task()` writes rounded wake time, task id, a typed
  resume value, and the complete VM. `read_task_queue()` restores all four.
- `eval_vm.cc::write_vm()` writes task-local state, activation-stack topology,
  root vector, function id, maximum stack size, and every activation.
- `execute.cc::write_activ()` writes the program, ordered locals, operand stack,
  typed receiver and verb location, player, programmer, invoked and stored verb
  names, debug/thread mode, temporary value, PC, builtin PC, error PC, and any
  registered builtin continuation data.
- Every registered external queue is written as interrupted VM state. In this
  checkout the registered production queues are `exec.cc`'s exec waiter and
  `background.cc`'s worker pool. The optional example extension registers
  `read_stdin`; it is not a stock production target.
- Idle tasks blocked in either `read()` or `read_http()` are also written as
  interrupted VM state. On load, every interrupted VM becomes a suspended task
  whose resume value is `E_INTRPT`.
- `server.cc::write_active_connections()` writes every player/listener pair.
  At startup, `read_active_connections()` feeds those pairs to
  `user_disconnected` before `server_started`.
- `db_file.cc::ng_write_object()` writes each object's typed `last_move`
  immediately after location. `db_objects.cc::db_change_location()` records a
  map containing `time` and the prior location under `source`.
- The server runs `checkpoint_started` before the database flush. It runs
  `checkpoint_finished` after completion, with success/failure status. State
  mutated only by `checkpoint_finished` is therefore later than the completed
  checkpoint and is not part of that checkpoint.

## Harness capability audit

| Capability | Current support | Consequence |
|---|---|---|
| Disposable database | `ManagedServer.start()` copies the selected fixture into a temporary directory | Every row can mutate and checkpoint without touching the bundled fixture |
| Genuine process-down restart | `restart_server.down_ms` stops the process before waiting and starting it again | Delayed and overdue task behavior can be distinguished |
| Checkpoint adoption | `_sync_checkpoint_output()` recognizes `.out`, `.new`, `.out.db`, and `.new.db` | Toast's separate output database becomes the next input database |
| Reconnection | The primary transport reconnects as its prior user after restart | Post-restart MOO state is directly observable |
| Additional connections | `new_connection`, `send`, `send_bytes`, `read_connection`, and `close_connection` | Active-connection and blocked-read states can be induced before restart |
| Runtime observation | MOO expressions, raw commands, captured values, logs, and files | Task results, hooks, metadata, errors, and ordering can be asserted |
| Timing | `wait`, restart `wait_ms`, and process-down `down_ms` | Remaining versus overdue wake behavior can be bounded coarsely |
| Managed requirement | Restart rows skip when pytest lacks `--server-command` | Barn's wrapper must pass a managed command instead of launching Barn outside pytest |
| Arbitrary host process inspection | Not exposed as a YAML step | Internal bytes are tested in Go; cross-engine rows must assert MOO-visible behavior or durable managed files |
| Preserve secondary sockets across process death | Impossible by network semantics | Former connections are observed through startup hooks, not by reusing dead sockets |

No new schema primitive is required for the named MOO-observable rows below.
The first harness change is invocation wiring so those rows execute for Barn.
Only add a new general step if a concrete Toast-first row proves this matrix
wrong.

## Observable coverage matrix

| State or field | Inducible and observable behavior | Existing durable coverage | Required managed coverage |
|---|---|---|---|
| Delayed queued fork | Fork with future delay, checkpoint, process-down restart, then observe exact task id and captured locals when it runs | Two rows prove eventual execution, including an overdue fork | Strengthen with task id, owner/programmer/receiver/verb location, ordered locals, and a not-before timing bound |
| Suspended VM | Enter a nested verb chain, set locals and task-local state, call indefinite `suspend()`, resume with a typed value, checkpoint before the ready task runs, restart, and observe its continuation | None | Add a row covering nested frames, local values, task-local value, typed resume value, stable id, and frame identity |
| Remaining suspended timing | Suspend for a future duration, checkpoint, use a known process-down interval, and observe whether continuation is still pending or overdue | Delayed fork only; no suspended VM timing row | Add separate remaining-time and overdue suspended-task assertions |
| Operand stack, temporary value, PC, and error PC | Expressions and nested try/except around the suspend point make continuation correctness observable after restart | None | Exercise arithmetic/collection operands and exception continuation after the suspend point |
| Builtin continuation | Suspend within a builtin that has registered persistence data | None | Add only for a builtin whose exact Toast induction and observable result pass first; `call_function` is the first source-backed candidate |
| Anonymous value in task state | Store a valid anonymous object in a suspended local/task-local/resume value and inspect type, validity, identity, and property after restart | ANON task introspection exists without restart | Add to the suspended-VM row or a focused ANON task-state row |
| WAIF value in task state | Store a WAIF in a suspended local/task-local/resume value and inspect class, property, and aliasing after restart | WAIF world-property persistence exists without task state | Add a focused WAIF task-state row |
| Task identity fields | Inspect `task_id()`, `callers(1)`, `task_stack()`, `task_perms()`, and values written by the resumed task | Individual runtime tests exist; no checkpoint identity row | Assert player/owner, programmer, receiver/`this`, caller, invoked verb, defining location, positive line, and stable task id after restart |
| Debug/thread identity | Trigger caught error/trace behavior after the continuation point or inspect an exposed thread-mode result | Runtime debug/thread coverage exists separately | Add only where MOO-visible behavior distinguishes a lost bit; do not assert dump bytes from YAML |
| Blocking `read()` | A background task blocks on a connected player, checkpoint/restart converts it to `E_INTRPT`, and its catch block records the error | Ordinary blocking/nonblocking read coverage exists; no restart row | Add a source-mandated `E_INTRPT` restart row |
| Blocking `read_http()` | A task blocks in `read_http()`, checkpoint/restart converts it to `E_INTRPT` | Call-shape coverage only | Add if the bundled fixture and managed transport can induce the wait on Toast without external services |
| Waiting `exec()` | Start the packaged sleeping executable, checkpoint while waiting, restart, and observe `E_INTRPT` in the task | Portable exec fixtures exist; no restart row | Add a source-mandated `E_INTRPT` restart row |
| Background worker wait | Start a registered background-pool operation, checkpoint while waiting, restart, and observe interruption | No durable wait-state row | First prove a deterministic stock builtin and result on Toast; otherwise record the exact induction gap |
| Network wait | No registered task queue was found for generic outbound networking in the audited source | Network behavior exists separately | Do not invent a checkpoint row until a specific source path proves a persisted waiting VM |
| Active/former connection | Log in a secondary connection, checkpoint while connected, restart, and query a durable `user_disconnected` record containing player/listener before `server_started` | Connection hooks exist without restart | Add a former-connection startup-order row |
| Connection input queue/options | Hold input or block in read before checkpoint | Hold/OOB behavior exists without restart | Cover only state Toast actually persists; active-connection records contain player/listener, not arbitrary socket buffers/options |
| `last_move` | Create two locations, move an object, capture `time` and `source`, checkpoint/restart, and compare exact map entries | Fresh/read-only semantics only | Add a world-metadata restart row |
| Other object metadata | Owner, flags, location, contents, parents/children, verbs, property definitions/values, and programs are MOO-visible after restart | Value families plus inherited property and WAIF aliasing cover much, but not one complete object | Strengthen object persistence only for a concrete uncovered field; avoid duplicating already passing value-family rows |
| Pending finalizations | Create/recycle anonymous or WAIF state that queues finalization and observe startup behavior | WAIF/ANON value tests, but no finalization restart row | Add only if deterministic MOO-visible finalization can be induced in the bundled fixture |
| `checkpoint_started`/`checkpoint_finished` | Hooks append markers; before restart observe both, after restart observe that only pre-flush state was checkpointed | Checkpoint log text only | Add exact hook order and checkpoint-boundary row |
| Checkpoint success/failure status | `checkpoint_finished` receives status after the flush | No row | Assert the Toast-observed argument for a successful managed checkpoint; failure requires a safe deterministic managed-file capability before adding a row |
| Genuine checkpoint adoption | Write to `{db}.out`, stop fully, adopt it, restart, and query mutated state | Every managed persistence row depends on it | Keep as a mandatory execution condition; fail instead of skip when a selected restart row lacks managed mode |

## Ordered implementation targets

1. Make the documented Barn wrapper invoke pytest with `--server-command`, so
   selected restart rows execute rather than skip.
2. Strengthen delayed queued-fork round-trip identity and local-state coverage.
3. Add the complete suspended-VM row, followed by focused timing, ANON, WAIF,
   and builtin-continuation rows where the first row does not already prove the
   field.
4. Add `read()` and packaged `exec()` interrupted-restart rows. Attempt
   `read_http()` and a background worker only through deterministic
   Toast-first induction.
5. Add former-connection startup ordering, `last_move`, and checkpoint hook
   ordering/status rows.
6. Use every Toast-green row unchanged against pre-fix Barn. Each Barn change
   must be the smallest red-first atomic slice that closes that row.

