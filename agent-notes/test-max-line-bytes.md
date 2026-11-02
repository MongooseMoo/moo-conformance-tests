# MAX_LINE_BYTES connection close

## Goal
Pin ToastStunt's per-connection input limit: a connection whose unterminated
line, or telnet subnegotiation, reaches MAX_LINE_BYTES (5242880,
include/options.h:247) is closed and logged (network.cc:395, 476). Found while
planning Barn fuzzing: Barn's TCP reader has no such cap.

## State
Test `server/max_line_bytes.yaml` passes on the stock WSL Toast oracle
(`make conformance-toast K=max_line_bytes` from Barn, 3 passed including
admission) and fails on Barn master (both cases: log text absent).

## Decisions and why
- `send_bytes.repeat` (positive int, default 1): 5 MiB as hex in YAML is not
  usable. The decoded bytes are repeated and sent in one write.
- `_receive_until_quiet` treats ConnectionResetError as end of data: Toast
  closes with the final byte unread, so the client sees a reset, not EOF.
- A final one-byte send forces the server to read again after the pending
  input reaches the limit; Toast checks before each read (pull_input) and before
  each telnet byte. The telnet case sends `IAC SB` first, so its bulk is 2 bytes
  shorter.
- Assertions use the stable substring of Toast's log line, not the connection
  name or counts.

## Surprises
- CI's change-boundary classifier rejects a PR mixing controller files
  (runner/schema/transport/tests) with conformance data (YAML). This PR is now
  controller-only; `server/max_line_bytes.yaml` lands in a second PR from main
  after this one merges. Its content is in this branch's history.

## Next step
Merge this controller PR. Then: Barn PR 568 (the fix), then the data PR adding
server/max_line_bytes.yaml, in that order, since Barn CI runs this repo's main.
