# fix/restart-wait-port-free

## Goal
Managed restart must not launch the new server while a process forked by the
old server (ToastStunt's checkpointer child) still holds the listening port.

## State
`ManagedServer.restart()` (src/moo_conformance/server.py) now calls
`_wait_for_port_release(timeout=30.0)` after `stop()`. The probe is a wildcard
bind with SO_REUSEADDR (as Toast binds); a lingering listener fails the bind,
TIME_WAIT connections do not. Bounded: raises ManagedServerLifecycleError
naming the port. Two unit tests in tests/test_managed_server.py; both fail
without the server.py change and pass with it (Linux/WSL).

## Evidence (why)
moo-conformance-tests PR #129 run 43630611828, job 132556528263
(64bit-outbound-off): `server/dump_database_hook_order.yaml` calls
`dump_database()`, Toast forks a checkpointer (`db_file.cc` dump_database ->
`fork_server`, a bare fork() in `server.cc`), the test restarts immediately,
and the relaunched Toast logged `Error binding listening socket: Address
already in use` / `Can't create initial connection point!` and exited 1. The
child's `CHECKPOINTING ... finished` appears after that. Rerun passed.

## Decisions
- Bind probe, POSIX only. On Windows, a wildcard bind succeeds beside a
  127.0.0.1 listener and SO_REUSEADDR can take over a live port (local run
  showed both new tests failing that way); a connect probe there waits ~2 s per
  refusal on loopback and broke existing restart tests. Windows servers do not
  fork listener-inheriting children, so the wait is skipped there.

## Next step
None once the PR merges.
