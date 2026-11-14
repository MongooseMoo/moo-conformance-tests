# Toast signal handling

The inventory below comes from the actual Toast source at
`/root/src/toaststunt`, audited at `aecc51e9449c6e7c95272f0f044b5ba38948459e`.
The same handlers were checked in the CI oracle revision
`eaaa1972f0993a1247f787dbf2dd5a01702ef442`. Tests exercise server behavior by
delivering OS signals to a directly managed PID and observing MOO state,
logs, process status, and databases loaded after restart.

| Signal | Source behavior | Coverage |
| --- | --- | --- |
| SIGINT, SIGTERM | `server.cc:shutdown_signal` sets the shutdown flag/message; main-loop shutdown disconnects clients and `db_shutdown` dumps current state. | Each broadcasts the shutdown notice, exits cleanly, bypasses user/checkpoint hooks, and persists a marker through restart. |
| SIGHUP | `setup_signals` installs `panic_signal` unless HUP was already ignored at exec. | Recoverable panic dump and abort; repeated delivery to an inherited-ignore launch remains harmless. |
| SIGILL, SIGQUIT, SIGSEGV, SIGBUS | `panic_signal` calls `panic_moo`: backtrace/history, shutdown notice, network close, PANIC dump, then SIGABRT. SIGBUS is conditional on the platform defining it. | Each broadcasts the panic notice, aborts, writes the current marker to the PANIC database, and reloads that database successfully. |
| SIGFPE | `setup_signals` ignores it. | Repeated delivery leaves the server responsive and bypasses the user hook. |
| SIGPIPE | `network.cc:network_initialize` ignores it; network code handles write failures. | Repeated delivery leaves the server responsive and bypasses the user hook. |
| SIGUSR1 | `handle_user_defined_signal` invokes `#0:handle_signal("SIGUSR1")`. A completed false result requests named-log reopen; without a named log the fallback does nothing. | Missing/false hooks, repeated rotation, descriptor continuity, true/error/suspended suppression, hook argument and task context. The default responsiveness case also runs without `--log`. |
| SIGUSR2 | The same hook receives `"SIGUSR2"`; a completed false result requests a checkpoint. | Missing/false hooks, repeated requests, started/finished hooks and success status, pre/post-flush persistence, true/error/suspended suppression. |
| SIGCHLD | `child_completed_signal` drains `waitpid(-1, ..., WNOHANG)`, routes exec statuses to `exec_complete`, and schedules checkpoint notification for other children. It reinstalls itself and preserves errno. | Unsolicited CHLD, sequential exec statuses and I/O, concurrent exec/checkpoint children, repeated checkpoint completion. |
| SIGALRM | `timers.cc:wakeup_call` pops the first active real timer, rearms timers, and invokes its callback. | At idle with no outbound connect or active task, direct ALRM fires the checkpoint timer; a second cycle proves rearming. |
| SIGVTALRM | `virtual_wakeup_call` clears the virtual timer and invokes its callback when `ITIMER_VIRTUAL` is enabled. | Real seconds-limit expiry aborts a busy background task, calls `handle_task_timeout("seconds", ...)`, then fires again while the server stays usable. |

`timers.cc` disables virtual interval timers on WSL, Apple, and the specified
Mach platforms; `set_virtual_timer` then uses the SIGALRM timer queue. The same
task-timeout test covers this fallback on WSL and SIGVTALRM on native Linux.
An idle SIGVTALRM is not a valid task-limit test because its handler expects an
active virtual timer. Task timers are exercised through real expiry.

`panic_moo` has two additional fault paths: a panic inside a forked checkpointer
signals its parent with SIGINT and exits 1; a recursive panic aborts immediately.
The graceful SIGINT and abort behavior are covered, but these internal panic
conditions are not induced by the signal cases. Log-reopen failure keeps the
original log open; these cases cover successful reopen and deliberate hook
suppression, not filesystem failure injection. SIGKILL, SIGSTOP, and other
unhandled kernel/default signals are not Toast-installed handlers.

## Run the cases

Use the packaged Test.db fixture and a foreground server command that directly
executes Toast. A named log is necessary for rotation coverage:

```sh
uv run --frozen pytest src/moo_conformance/test_conformance.py \
  -k 'capability_admission or signals_' --strict-markers \
  --candidate-root="$PWD" \
  --moo-suite-root=src/moo_conformance/_tests/server \
  --oracle-profile-manifest=/path/to/profile.json \
  --target-profile-manifest=/path/to/profile.json \
  --server-command='/root/src/toaststunt/build-release/moo --log {log} --exec-dir {server_dir}/executables {db} {db}.new {port}'
```

The `.new` output name in this command is part of the signal suites' fixture
contract. Use a profile manifest for the actual build, as CI does: the exec
suite declares `exec_support`, `forking`, and `tasks`, which stock Toast does
not necessarily advertise under those conformance feature names. Missing
profile metadata can produce capability skips even when `exec()` is present.
Cases reset to the original fixture, use deadlines for positive log
and checkpoint observations, and recover from shutdown/panic before proceeding.
Log rotation assertions inspect both the old and new files rather than relying
on an offset into a replaced file. For the no-named-log branch, run
`capability_admission or signals_default_usr1` with `--log {log}` omitted.

## Windows

YAML signal names load identically on Windows. The suites require
`requires.config: [posix_signals, managed_server, ...]`; a native Windows host
reports an explicit POSIX configuration skip. Native Windows process termination
does not establish Toast's POSIX graceful-shutdown semantics. To execute these
cases from Windows, run the **Python harness and Toast together inside WSL**.
Running only Toast through a Windows `wsl.exe` wrapper would send the signal to
the wrapper PID and does not satisfy this contract.

The runner's schema, file operations, exit/restart handling, and Windows
admission checks are validated with native Windows pytest. Kernel delivery and
inherited-disposition unit tests require POSIX and skip on native Windows.

## Source entry points

- `src/server.cc`: `setup_signals`, `shutdown_signal`, `panic_signal`,
  `panic_moo`, `abort_server`, `handle_user_defined_signal`,
  `child_completed_signal`, `main_loop`, `set_checkpoint_timer`.
- `src/network.cc`: `network_initialize` and the SIGPIPE ignore installation.
- `src/exec.cc`: `BLOCK_SIGCHLD` / `UNBLOCK_SIGCHLD`, `exec_complete`,
  `deal_with_child_exit`; masking prevents premature child-completion handling.
- `src/timers.cc`: `stop_timers`, `restart_timers`, `wakeup_call`,
  `virtual_wakeup_call`, `set_virtual_timer`, `reenable_timers`.
- `src/execute.cc`: `setup_task_execution_limits`, `task_timeout`, `abort_task`.
- `src/db_file.cc`: `dump_database`, `db_flush`, `db_shutdown`.
