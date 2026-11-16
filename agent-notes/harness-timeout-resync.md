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

## Evidence (why)
A full managed Toast run: `vm/wide_control_flow.yaml` tests hit
`TimeoutError: timed out` (runner.py `run_test`), the same socket was reused,
and 19 later tests read the previous command's framed reply (for example
`sqlite_info_invalid_handle` got the string 'E_INVARG'; `fork_delayed_appears_in_queue`
got a task id). Toast `tasks.cc` (do_command path) emits PREFIX, the result
and SUFFIX with `notify(tq->player, ...)` within one command, so for a busy,
non-suspending task the whole late frame goes to the old connection before
Toast reads the new login; closing that socket discards it.

Managed WSL Toast run with a temporary, uncommitted probe suite (a 6 s busy
eval sorted ahead of sqlite and fork): the probe timed out, the probe's next
test got its own reply, and every sqlite, fork_timing and fork_observation
test passed.

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
