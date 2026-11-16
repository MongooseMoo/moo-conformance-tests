# harness-timeout-resync

## Goal
A command that times out must not leave its late reply on the connection for
the next command (and therefore the next test) to read.

## State
`SocketTransport.execute` (src/moo_conformance/transport.py) sends through the
new `SocketTransport._exchange`. If the send or the framed read raises
(normally `socket.timeout` from `sock.recv`), `_exchange` closes the socket
and re-raises. `YamlTestRunner._ensure_transport_connected`
(src/moo_conformance/runner.py) already reconnects when `transport.sock` is
None, so the next command runs on a fresh connection. `_ensure_standard_properties`
uses `_exchange` too. Unit test:
`tests/test_transport.py::test_a_reply_that_arrives_after_a_timeout_is_never_returned_to_the_next_request`
(failed `111 != 111` before the change).

A test's declared `timeout_ms` is now honoured. It was parsed (schema.py,
default 5000) and never read, while every command waited a fixed 3 s
(`settimeout(3)` in `connect`/`switch_user`). Now `MooTestCase.timeout_ms`
is None unless declared; `SocketTransport.command_timeout` (default
`COMMAND_TIMEOUT = 3.0`) is applied by `_exchange` before each command;
`YamlTestRunner.run_test` sets it from a declared `timeout_ms` for that test
and restores it afterwards. Undeclared tests keep 3 s. Tests:
`test_each_command_waits_for_the_command_timeout`,
`test_a_declared_test_timeout_applies_to_the_test_commands_only`,
`test_a_test_without_a_declared_timeout_keeps_the_transport_timeout`,
`test_test_timeout_is_absent_unless_declared`.

## Evidence (why)
A full managed Toast run: `vm/wide_control_flow.yaml` tests hit
`TimeoutError: timed out` (runner.py `run_test`), the same socket was reused,
and 19 later tests read the previous command's framed reply (for example
`sqlite_info_invalid_handle` got the string 'E_INVARG'; `fork_delayed_appears_in_queue`
got a task id). Toast `tasks.cc` (do_command path) emits PREFIX, the result
and SUFFIX with `notify(tq->player, ...)` within one command, so for a busy,
non-suspending task the whole late frame goes to the old connection before
Toast reads the new login; closing that socket discards it.

Managed WSL Toast run with a temporary, uncommitted probe suite sorted ahead
of sqlite and fork (a 6 s busy eval with no `timeout_ms`, then `return 777`,
then a 5 s busy eval declaring `timeout_ms: 15000`): the first timed out, the
second got 777, the third passed, and every sqlite, fork_timing and
fork_observation test passed (1 failed, 103 passed, 19 skipped for
`queued_tasks` having no provider).

## Surprises
- Test.db `#0:do_login_command` creates a new player object on every
  `connect wizard|programmer|player`. A reconnect after a timeout therefore
  gets a new `player`; state a suite's setup put on the old `player` is gone,
  so later tests in the same suite fail cleanly (wide_control_flow got
  E_VERBNF). `switch_user` already behaves this way.
- `vm/wide_control_flow.yaml` is not on main; it was an untracked file in
  another checkout.
- `_receive_lines` (raw `send_command`) still swallows `socket.timeout` and
  returns partial lines without dropping the socket; not changed here.

## Next step
None once the PR merges.
