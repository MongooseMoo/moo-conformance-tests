# perf/harness-fixed-waits

## Goal

Cut fixed waiting time out of the conformance harness without changing what any
test asserts. Three parts, one commit each:

1. Raw connection reads return when the awaited output has arrived (bounded by a
   deadline) instead of after a silence timer.
2. Port polling after server start uses a short interval.
3. Classify every YAML `wait:` and `down_ms` step; replace "sleep, then look"
   waits with a wait for the event; leave behaviour-under-test waits alone.

## State

- Read: worktree CLAUDE.md, barn AGENTS.md, the main checkout's untracked
  AGENTS.md, the convergence plan's oracle and Windows-to-WSL sections,
  transport.py, runner.py (step dispatch), server.py (start/stop/restart/
  `_wait_for_port`), schema.py step dataclasses, toast-conformance-core.yml.
- Measurement setup (all inside WSL Debian, 32 CPUs):
  - Barn: `git archive` of barn master `d890b124` built to
    `/root/fastwaits/barn` (Linux). Server command and profile as in barn
    CLAUDE.md (`outbound-on.conf`, `barn-linux-testdb-outbound-on`).
  - Toast: `/root/src/toaststunt/build-release/moo` at `aecc51e` with
    `{db} {db}.new -p {port}` and `profiles/toast/stock-wsl-testdb.json`, as in
    barn's `make conformance-toast`. CI builds Toast `eaaa1972` with
    `BACKGROUND_TEST`; the local binary is not that build, so local Toast
    pass/fail counts are not CI's.
  - Harness: a clone of this branch at the base commit in
    `/root/fastwaits/base`; uv env per checkout under `/root/fastwaits/`.
  - Driver: scratch `run_suite.sh` (managed `moo-conformance -m "admission or
    conformance" ... --junitxml`), logs `/proc/loadavg` before and after.
  - Attribution: scratch pytest plugin `waitprobe.py` wraps `time.sleep`,
    `TestConnection._receive_until_quiet`, `_consume_login_output`,
    `connect`, `switch_user`, `_wait_for_port`, server `start`/`stop`, and
    sums wall time per test node. Measurement only, no behaviour change.

## Inventory on this branch (survey of `_tests/**/*.yaml`)

- Raw connection steps: 86 `new_connection` (none has an expectation), 79
  `send` (64 no expectation, 1 capture, 7 exact, 4 exact-empty, 2 contains,
  1 match), 31 `send_bytes` (none has an expectation), 9 `read_connection`
  (5 exact, 2 contains, 2 capture).
- 173 `wait:` steps summing 177.6 s in 56 files; 154 `restart_server` steps,
  26 with `wait_ms` (sum 8.0 s), 4 with `down_ms` (sum 19.0 s).

## Measurements

All runs: managed suite, `-m "admission or conformance"`, inside WSL Debian
(32 CPUs). Self-hosted barn CI jobs (conformance and jepsen) were running on
the same machine during every run; load is recorded per run.

| Run | Harness | Engine | Result | pytest time | load before -> after |
|---|---|---|---|---|---|
| base | base commit | Barn d890b124 | 13487 passed, 318 skipped | 689.4 s | 16.76 -> 10.46 |
| base + probe | base commit | Barn d890b124 | 13487 passed, 318 skipped | 674.0 s | (not logged) -> 9.41 |

Baseline attribution (waitprobe, Barn, sum of per-test wall 667.7 s):

| Site | Seconds | Calls | Notes |
|---|---|---|---|
| `_consume_login_output` (login drain) | 160.7 | 1587 | 0.1 s trailing silence after `Connected` on every login and user switch |
| `_wait_for_port` sleep | 148.5 | 297 | exactly one 0.5 s sleep per server start: the first probe is always refused |
| YAML `wait:` steps | 132.0 | 168 | (fewer than 173: some suites skip on Barn) |
| raw read, nothing arrived (`quiet_read:empty`) | 79.1 | 160 | 0.5 s window, reads with no expectation |
| raw read, data arrived | 7.3 | 83 | |
| `restart_server.wait_ms` | 6.3 | 21 | |
| `restart_server.down_ms` | 6.0 | 1 | |
| `assert_file` polling | 4.7 | 94 | already event-based |
| process stop waits | 9.7 | 1452 | `subprocess.wait` inside stop |

The 0.15 s / 0.25 s / 0.55 s duration clusters are the login drain, not the
raw connection timers: the 350 tests in [0.13, 0.17) hold 51.7 s, of which
35.2 s is login drain; [0.23, 0.27) 157 tests, 31.8 of 39.5 s; [0.52, 0.57)
44 tests, 17.4 of 23.8 s. Tests switch user (wizard/programmer) and every
switch reconnects and logs in.

## Decisions and why

- Part 1, raw reads (`TestConnection`): only a step with an output
  expectation knows what it is waiting for. Such a read now waits until the
  expectation is satisfied (deadline 10 s), then keeps the existing 0.1 s
  trailing quiet drain so extra output still reaches an `exact` assertion.
  An expectation already satisfied by no output (`exact: []`) keeps the old
  0.5 s window, because it asserts that nothing arrives. Reads with no
  expectation (all 86 `new_connection`, 64 `send`, 31 `send_bytes`) keep the
  silence window: nothing tells the harness what they wait for, and skipping
  their reads would leave unread data at close (RST instead of FIN), which
  can change server-observed disconnect behaviour. Direct saving from this is
  small; its value is that a `wait:` before an expected read becomes
  removable (Part 3).
- Part 1, login (`_consume_login_output`): return as soon as the
  `Connected` marker arrives instead of draining 0.1 s of silence after it.
  The marker-framed readers (`_receive`, `_receive_lines`) already discard
  lines before the PREFIX marker, and output is ordered per connection, so
  any remaining login output is skipped by them. Test.db's
  `#0:do_login_command` (inspected with `barn -verb-code`) only creates the
  player and calls `switch_player`; `#0` has no `user_connected` or
  `user_reconnected` verb, so no asynchronous login output exists to race
  with the first framed response.
- Part 3 classes (working set): CKPT `dump_database(); wait; restart_server`
  -> `restart_server: {checkpoint_timeout_ms: 10000}` (existing field, used
  by 9 tests already; Toast and Barn both publish checkpoints by rename, so a
  fresh `{db}.new` is complete). POLL: wait then read-only `run` check ->
  needs a new `run` polling field. LOG: wait then `assert_log contains` ->
  needs a `timeout_ms` on `assert_log` (assert_file on server.log is not
  equivalent: it reads the whole file, not since test start). READ: wait
  then `read_connection` with an expectation -> removable after Part 1.
  BEHAVIOUR: a timeout that must elapse or a "not yet" check -> left alone.
  ACT: wait then a side-effecting step with no read-only event -> left
  alone.

## Surprises

- The brief's counts (179 waits, 186 s, 156 restarts,
  `server/checkpoint_operational.yaml` 17 s) do not match this branch: there
  is no `checkpoint_operational.yaml` here, and the survey finds 173 waits /
  177.6 s and 154 restarts. The brief's numbers likely came from a different
  tree; this note uses the branch's own counts.
- The brief inferred the 0.15/0.25/0.55 s clusters came from
  `TestConnection._receive_until_quiet`. Measured: they come from the login
  drain in `SocketTransport._consume_login_output` (see Measurements). The
  raw-connection timers cost 86 s in total, 79 s of it in reads that have no
  expectation.
- Every managed server start sleeps 0.5 s: the port probe runs right after
  `Popen`, is refused, and sleeps the full interval (297 of 297 starts).

## Next step

Baseline Barn run (running), then the waitprobe run, then baseline Toast.
