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
  - Barn: `git archive` of barn master `(master, 2026-11-11)` built to
    `/root/fastwaits/barn` (Linux). Server command and profile as in barn
    CLAUDE.md (`outbound-on.conf`, `barn-linux-testdb-outbound-on`).
  - Toast: `/root/src/toaststunt/build-release/moo` at `(local release build)` with
    `{db} {db}.new -p {port}` and `profiles/toast/stock-wsl-testdb.json`, as in
    barn's `make conformance-toast`. CI builds Toast `(CI's pinned build)` with
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
| base | base commit | Barn (master, 2026-11-11) | 13487 passed, 318 skipped | 689.4 s | 16.76 -> 10.46 |
| base + probe | base commit | Barn (master, 2026-11-11) | 13487 passed, 318 skipped | 674.0 s | (not logged) -> 9.41 |
| Part 1 + probe | Part 1 commit | Barn (master, 2026-11-11) | 13487 passed, 318 skipped | 537.6 s | (not logged; run script edited mid-run) |

| Part 2 + probe | Part 2 commit | Barn (master, 2026-11-11) | 13487 passed, 318 skipped | 379.0 s | 14.76 (just before) -> 5.26 |
| Part 3b (final) + probe | Part 3b commit | Barn (master, 2026-11-11) | 13487 passed, 318 skipped | 319.1 s | 14.40 (just before) -> 9.43 |
| base + probe | base commit | WSL Toast (local release build), `-k "not multiple_inheritance_hardening"` | 7 failed, 13748 passed, 43 skipped, 7 deselected | 808.1 s | (not logged) -> 8.07 |

Final Barn attribution (probe, sum of per-test wall 310.5 s): raw reads with
nothing arriving 79.1 s (unchanged, no expectation), runner sleeps 57.4 s
(remaining fixed waits plus 50 ms poll intervals, 443 calls), port poll
15.5 s, raw reads with data 11.0 s (was 7.3 s: expected reads now wait for
their output), process stop 9.5 s + 10.9 s subprocess waits, assert_file
polling 5.1 s, the one down_ms Barn runs 6.0 s, login 1.7 s. Note that 53
fork-feature tests (incl. task_scheduling_toast_oracle and task_local) are
skipped on Barn's profile, so Barn does not exercise those conversions.

| Part 3b (final) + probe | Part 3b commit | WSL Toast (local release build), same `-k` | 6 failed, 13749 passed, 43 skipped, 7 deselected | 388.1 s | (not logged) -> 19.02 |

Per-test status, base vs final: Barn 13805 cases, 0 differ. Toast 13798
cases, 1 differs: `server/signals_children.yaml::exec_and_checkpoint_children_complete_independently`
failed at base (assert_file never saw `SIGNAL-CHILD-CHECKPOINT-1`) and passed
at final; that YAML is unchanged, cause unknown ((local release build), load ~8-19).

Duration bands (sum of junit times), base -> final:
- Barn: 0.1-0.2 s band 354 tests / 52.9 s -> 97 / 14.2 s; 0.2-0.3 s 169 /
  42.7 s -> 40 / 9.5 s; 1-5 s 187 / 421.6 s -> 76 / 133.8 s; >= 5 s 7 /
  62.0 s -> 7 / 46.3 s; total 675.4 s -> 303.1 s. New 0.05 s cluster (397
  tests, 19.9 s): one 50 ms port poll per server start.
- Toast: 0.1-0.2 s 389 / 56.6 s -> 90 / 11.9 s; 0.2-0.3 s 185 / 46.2 s -> 52
  / 13.5 s; 1-5 s 219 / 472.3 s -> 94 / 164.5 s; >= 5 s 15 / 134.4 s -> 11 /
  76.0 s; total 792.1 s -> 371.4 s.

Final Toast attribution (probe, 381.1 s): runner sleeps 81.6 s (remaining
fixed waits incl. the task_scheduling ones Barn skips, plus poll intervals),
raw reads with nothing arriving 80.6 s, port poll 36.1 s (723 polls over 353
starts: Toast takes ~2 polls to open its port), down_ms 19.0 s, raw reads
with data 11.7 s, assert_file polling 8.4 s, stop 13.3 s, login 0.7 s.

Toast runs use the documented oracle binary
`/root/src/toaststunt/build-release/moo` ((local release build)) with CI's flags
(`--log {log} --no-ipv6 --ipv4 127.0.0.1 --outbound --exec-dir
{server_dir}/executables {db} {db}.new {port}`) and a profile copying CI's
feature set (scratch `toast-profile.json`). CI builds Toast (CI's pinned build) with
`BACKGROUND_TEST`. Two consequences: (1) without the `-k`, (local release build) panics on
`objects/multiple_inheritance_hardening.yaml::renumbering_a_parent...`
(SIGABRT); the harness latches the lifecycle failure and aborts the session
after ~13150 cases, skipping server/, vm/, fork/; (2) seven tests fail at the
base commit on (local release build), all semantic differences (not timing):
object_hierarchy next_recycled_object, map_authority int keys, object_authority
comparator, limits map_literal E_QUOTA, object_dump_persistence (object
identity map), restart_task_semantics indefinitely_suspended ((local release build) resumes
it with 0), signals_children. Two of these are files Part 3 changes, so they
are verified on Barn only locally.

Part 2 effect (probe, Barn): `_wait_for_port` 148.7 s -> 15.0 s over the same
297 starts (still one 50 ms sleep per start); sum of per-test wall
530.4 s -> 373.2 s.

Part 1 effect (probe, Barn): login drain 160.7 s -> 2.0 s over the same 1587
logins; sum of per-test wall 667.7 s -> 530.4 s; the [0.13, 0.17) cluster
went from 350 tests / 51.7 s to 59 tests / 8.4 s. Raw-read sites unchanged
(79.1 s empty, 7.3 s data), as designed: no YAML `wait:` before an expected
read has been removed yet.

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

## Classification of `wait:`, `wait_ms`, `down_ms` (Part 3)

Classes: CKPT = wait for a requested checkpoint before restart, replaced by
`restart_server.checkpoint_timeout_ms: 10000`. LOADED = post-restart pause
before a check that reads only state loaded from the checkpoint; Toast loads
the database (server.cc `db_load`) before it starts listeners and runs
`server_started` before its main loop reads input, so there is nothing to
wait for; removed. POLL = sleep then a read-only check of state an
asynchronous event sets once and that nothing later in the scenario changes;
replaced by the check with `poll_ms`. LOG = sleep then `assert_log contains`,
replaced by `assert_log.timeout_ms`. FILE = sleep before an `assert_file`
that already has its own `timeout_ms`; removed. READ = sleep before a raw
read that has an output expectation; removed, the read now waits for it.
BEHAVIOUR = the elapsed time is what the test checks (a timeout or delay that
must pass, a "not yet"/absence window, a downtime); left alone. ACT = sleep
then a side-effecting step with no read-only event to wait on; left alone.

| File | Test | ms | Class | Change / reason |
|---|---|---|---|---|
| server/boolean_dump_persistence | boolean_type_and_values_survive_dump_and_restart | 1500 + wait_ms 300 | CKPT + LOADED | checkpoint_timeout_ms; next step reads `#1` properties |
| server/dump_persistence | inherited_override_survives_dump_and_restart | 1500 + 300 | CKPT + LOADED | same |
| server/dump_persistence | adjacent_floats_survive_dump_and_restart | 1500 + 300 | CKPT + LOADED | same |
| server/error_dump_persistence | all_named_errors_survive_dump_and_restart | 1500 + 300 | CKPT + LOADED | same |
| server/float_boundary_dump_persistence | maximum_normal_and_subnormal_values_survive_dump_and_restart | 1500 + 300 | CKPT + LOADED | same |
| server/integer_dump_persistence | full_range_integers_survive_dump_and_restart | 1500 + 300 | CKPT + LOADED | same |
| server/list_dump_persistence | nested_heterogeneous_lists_survive_dump_and_restart | 1500 + 300 | CKPT + LOADED | same |
| server/map_dump_persistence | ordering_spelling_bytes_and_non_total_topology_round_trip | 1500 + 300 | CKPT + LOADED | same |
| server/object_dump_persistence | boundary_and_invalid_object_references_survive_dump_and_restart | 1500 + 300 | CKPT + LOADED | same |
| server/string_dump_persistence | raw_bytes_identity_and_copy_survive_dump_and_restart | 1500 + 300 | CKPT + LOADED | same |
| server/waif_dump_persistence | waif_backreference_identity_survives_dump_and_restart | 1500 + 300 | CKPT + LOADED | same |
| server/verb_alias_dump_persistence | add_verb_aliases_survive_dump_and_restart | 1500 + 300 | CKPT + LOADED | next step reads verbs |
| server/verb_alias_dump_persistence | set_verb_info_aliases_survive_dump_and_restart | 1500 + 300 | CKPT + LOADED | same |
| server/persistent_walking_skeleton | boot_login_eval_checkpoint_restart_eval | 1500 + 300 | CKPT + LOADED | next step is `40 + 2` |
| server/empty_fork_checkpoint_restart | empty_fork_survives_two_checkpoint_restarts (x2) | 2 x (1500 + 300) | CKPT + LOADED | next step reads restored `queued_tasks()` |
| server/fork_variable_checkpoint_restart | fork_variable_holds_own_task_id_after_checkpoint_restart | 1500 + 300 | CKPT + LOADED | next step checks the 6 s fork is still queued and has not run; it now runs earlier after the fork, so further from the 6 s boundary |
| same | same | 6000 | POLL 15000 | waits for the 6 s fork to set `fork_var_result`; before that `result[1]` raises, so the check cannot pass early; one task, set once |
| server/fork_trailing_block_checkpoint_restart | trailing_block_forks_run_after_checkpoint_restart | 1500 + 300 | CKPT + LOADED | as above |
| same | same | 7000 | POLL 15000 | four 6 s forks plus one nested fork(0) append one entry each; `length == 5` is only reached when all have run, and no further task exists |
| server/fork_try_computed_codes_checkpoint_restart | try_computed_codes_forks_run_after_checkpoint_restart | 1500 + 300 | CKPT + LOADED | as above |
| same | same | 7000 | POLL 15000 | two 6 s forks append exactly one entry each ("unexpected" replaces "body" in the same task), so `length == 2` means both finished |
| server/restart_task_semantics | indefinitely_suspended_task_across_checkpoint_restart | 1500 | CKPT | checkpoint_timeout_ms |
| same | same | wait_ms 300 + 1000 | BEHAVIOUR | the check asserts the task has NOT resumed; the 1.3 s after restart is the window in which it must stay suspended |
| same | restored_overdue_fork_runs_after_server_started_returns | 1500 | CKPT | checkpoint_timeout_ms |
| same | same | down_ms 6000 | BEHAVIOUR | the fork (5) must become overdue while the process is down; restart now happens at >= fork+6 s, still overdue |
| same | same | wait_ms 300 + 1000 | POLL 10000 | `restore_order == ["started","task"]`; before the overdue task runs it is `["started"]`; a wrong order never becomes equal |
| audit/task_scheduling_toast_oracle | audit_background_task_id_stable_across_suspend_and_fork | 500 | POLL 10000 | `audit_heartbeat_result` starts `{}` and is set once at the end of the heartbeat task |
| same | audit_suspended_task_survives_restart | 1500 / wait_ms 500 / 4500 | CKPT / POLL 15000 | value goes `before` -> `after` when the fork (4) runs after restart |
| same | audit_pending_forked_task_survives_genuine_offline_restart | 1500 | CKPT | checkpoint_timeout_ms |
| same | same | down_ms 8000 | BEHAVIOUR | genuine offline downtime past the fork (3) deadline |
| same | audit_delayed_fork_preserves_identity_locals_and_schedule_across_restart | 1500 + wait_ms 300 | CKPT + LOADED | next check reads the restored queue entry (incl. "not yet run": `queued[2] > time()`, now checked earlier, further from the 8 s deadline) |
| same | same | 7000 | POLL 15000 | `result[1]` raises until the fork (8) runs; then set once and the task leaves the queue |
| same | audit_suspended_vm_preserves_frames_locals_continuations_and_resume_value | 1500 + wait_ms 300 | CKPT + POLL 10000 | the resumed task runs after restart and sets `audit_result` once; `result[9]` raises before |
| same | audit_suspended_vm_remaining_wake_time_survives_restart | 1500 + wait_ms 300 | CKPT + LOADED | next check is "still pending, deadline in the future", now checked earlier (further from the 8 s wake) |
| same | same | down_ms 1000 | BEHAVIOUR | genuine process-down restart |
| same | same | 7000 | POLL 20000 | set once at wake; `result[3] >= result[2] + 7` uses the task's own clock, not the poll time |
| same | audit_suspended_vm_overdue_during_process_down_runs_after_restart | 1500 | CKPT | stop now ~1.5 s earlier; suspend(3) deadline still passes during the unchanged 4 s downtime |
| same | same | down_ms 4000 | BEHAVIOUR | the wake deadline must pass while the process is down |
| same | same | wait_ms 300 + 500 | POLL 10000 | set once when the overdue task runs |
| same | audit_anonymous_values_in_suspended_vm_survive_restart | 1500 / 300 | CKPT / POLL 10000 | resumed task sets `audit_result` once after restart |
| same | audit_waif_values_in_suspended_vm_survive_restart | 1500 / 300 | CKPT / POLL 10000 | same |
| same | audit_blocked_read_resumes_with_interrupted_after_restart | 1500 / 300 | CKPT / POLL 10000 | restored read() task resumes with E_INTRPT once |
| same | audit_blocked_read_http_resumes_with_interrupted_after_restart | 1500 / 500 | CKPT / POLL 10000 | same for read_http() |
| same | audit_waiting_exec_resumes_with_interrupted_after_restart | 1500 / 500 | CKPT / POLL 10000 | same for exec() |
| same | audit_long_suspended_background_task_can_yield_after_wake | 3500 | POLL 10000 | progress `before` -> `after-long-suspend` -> `after-yield`; only the final value matches |
| audit/connection_lifecycle_toast_oracle | audit_listener_handler_do_login_command | 500 | POLL 10000 | the connect-time empty call sets `{handler, {}, ""}`, which does not match; the login line sets the expected value once |
| same | audit_listener_handler_do_command | 500 (after login send) | ACT | next step sends a post-login command; no read-only event in the test proves login finished |
| same | same | 500 | POLL 10000 | `audit_command_seen` starts `{}` |
| same | audit_listener_handler_do_blank_command | 500 | POLL 10000 | `audit_blank_seen` starts `{}`; the handler has no do_login_command, so connecting sets nothing |
| same | audit_proxy_command_clears_login_input | 500 | left | the connect-time empty do_login_command already sets the expected `{{}, ""}`, so a poll would pass before the PROXY line is processed |
| same | audit_user_connected_hook_on_first_login | 500 | POLL 10000 | hook value starts `{}` |
| same | audit_user_connected_continues_after_zero_delay_fork | 500 | POLL 10000 | final `order == {"parent","child"}` and marker; stable |
| same | audit_user_connected_dynamic_handler_continues | 500 | POLL 10000 | values start `{}` |
| same | audit_user_connected_confunc_calls_continue_after_fork_and_setting_task_perms | 500 | POLL 10000 | values start `{}`; final order list stable |
| same | audit_user_client_disconnected_hook | 500 (after login send) | ACT | the close must follow a completed login; no read-only event |
| same | same | 500 | left | the test is designed to catch a second call ("exactly once"); a poll could pass on the first entry before a duplicate lands |
| same | audit_user_reconnected_cross_listener_hooks | 500 (after first login) | ACT | sequencing before the second login |
| same | same | 500 | left | the check includes an absence (`audit_cross_new_reconnected == {}`); a poll could pass before a wrong hook call lands |
| same | audit_checkpointed_connections_disconnect_before_server_started | 1500 / 500 | CKPT / POLL 10000 | events are recorded during startup; poll tolerates any startup lag |
| same | audit_connect_timeout_server_option | 1500, 2500 | BEHAVIOUR | "not yet" checks: the timeout must not have fired, and must have been reset by the probe |
| same | same | 2000 | left | the test is designed to catch a second user_disconnected call; this check plus the next 500 ms one form its duplicate window, which a poll would shorten |
| same | same | 500 | BEHAVIOUR | "still exactly one" after a further window |
| same | audit_flush_command_flushes_pending_input | 500 (after login) | ACT | next step sets connection options for the logged-in player |
| same | same | 500 before `.FlUsH` | READ | the `.FlUsH` send now waits for its exact expected output; the two held lines were sent >= 0.5 s earlier each (their own silence windows are unchanged) |
| same | same | 500, 500 | ACT | sleep then set option / send; left |
| same | same | 500 | POLL 10000 | `audit_flush_seen` starts `{}` and becomes `[""]`; if the flush failed the held lines would be appended first, so `[""]` is never seen |
| same | audit_boot_player_messages | 500 (after login) | ACT | boot must follow a completed login |
| same | same | 500 | READ | read_connection now waits for `*** Disconnected ***` |
| same | audit_recycle_active_player_message | 500 (after login) | ACT | same |
| same | same | 500 | READ | read waits for `*** Recycled ***` |
| same | audit_login_timeout_message | 2500 | READ | read waits for the timeout message (connect_timeout 1 s, later than the 0.5 s connect read window) |
| same | audit_redirect_messages | 500, 500 | ACT / left | sequencing, then reads that only capture (no expectation); a later `run` compares the captures |
| same | audit_user_created_hook_for_new_login_object | 500 | POLL 10000 | values start `{}` (typeof LIST) |
| audit/divergence_command_connection_lifecycle | cmd_out_of_band_prefix_dispatches_pre_login | 500 | left | expects `dcc_login` to stay at its connect-time `[[], ""]`; a misroute that also called do_login_command after do_out_of_band_command would pass a poll in between |
| same | cmd_out_of_band_quote_prefix_unquotes_to_inband | 500 | POLL 10000 | connect-time value `{{}, ""}` differs; a wrong unquote never equals |
| same | cmd_prefix_suffix_frame_command_output | 300 | ACT | after the login send; protects the next exact read from late login output |
| same | cmd_hold_input_defers_commands_until_released | 300 | ACT | sleep then set hold-input |
| same | same | 500 | BEHAVIOUR | asserts the held command has NOT run, and releases the hold in the same eval |
| same | same | 500 | POLL 10000 | `dch_log` goes `[]` -> `["ping"]` after release |
| same | cmd_multiple_commands_one_packet_preserve_order | 700 | POLL 10000 | only the complete ordered list matches |
| same | cmd_say_and_emote_shortcuts_expand | 300 | ACT | after login |
| same | same | 500 | POLL 10000 | log starts `{}` |
| same | cmd_program_intrinsic_sets_verb_code | 300 | ACT | after login |
| same | same | 700 | POLL 10000 | verb code starts empty |
| audit/gap_followups_toast_oracle | audit_telnet_iac_stripped_from_login_input | 500 | POLL 10000 | connect-time `{{}, ""}` differs; only correct stripping matches |
| same | audit_crlf_split_across_reads_dispatches_blank_lf | 500 | left | the test counts blank-line dispatches; the state after the text line but before the LF is already `["packet-boundary", 1]`, so a poll could pass before a wrong extra blank dispatch |
| same | audit_telnet_escaped_iac_stripped_from_login_input | 500 | POLL 10000 | as above |
| same | audit_telnet_two_byte_command_delivered_across_reads | 500 | POLL 10000 | only the reassembled command matches |
| same | audit_telnet_iac_delivered_as_oob_command | 100 | BEHAVIOUR | the gap makes the two byte groups arrive in separate reads |
| same | same | 500 | POLL 10000 | as above |
| same | audit_telnet_subnegotiation_delivered_across_reads | 500 | POLL 10000 | as above |
| same | audit_gmcp_subnegotiation_delivered_across_reads | 500 | POLL 10000 | as above |
| same | audit_output_order_disconnect | 500, 500 | ACT | after login; before close |
| audit/divergence_input_lifecycle_decompile | read_in_command_task_consumes_next_line | 300, 300 | ACT | after login; `read()` must be waiting before the answer line is sent |
| same | same | 500 | POLL 10000 | wrong path logs "ran-as-command" and never matches |
| same | do_login_command_suspend_discards_login_result | 700 | ACT | the suspended login must resolve before the next line |
| same | same | 500 | POLL 10000 | only the complete three-entry list matches |
| audit/connection_hook_frames_toast_oracle | initial_empty_do_login_command_has_server_origin_frame | 500 | POLL 10000 | `seen` starts `{}` |
| same | new_login_object_calls_user_created_only | 500 | left | designed to catch extra hook calls ("only") |
| same | same_listener_reconnect_calls_user_reconnected | 500, 500 | ACT / left | sequencing; the expected list also excludes a client-disconnected event that a wrong server could append after the reconnect |
| audit/world_metadata_toast_oracle | audit_last_move_survives_checkpoint_restart | 1500 / 500 | CKPT / LOADED | next step reads loaded `last_move` |
| audit/checkpoint_lifecycle_toast_oracle | audit_checkpoint_hooks_order_status_and_boundary | 1500 | POLL 10000 | events go `[]` -> `[["started"]]` -> `[["started"], ["finished", 1]]`; only the final state matches |
| same | same | 500 | LOADED | after restart the check reads the loaded `[["started"]]` |
| server/connection_callback_context | all 16 cases | 16 x 100 | left | after new_connection; the next step either resets state (side effect) or is a check that already polls inside MOO for up to 1 s; at most 1.6 s in total |
| server/input_callback_context | input_{kind}_{outcome}_context_and_fallback, trusted_blank_{allow}_... (x2), huh_... | 4 x 100 | left | ACT after new_connection (next step resets state or sends); the trusted_blank check is built to catch an extra login fallthrough event |
| server/input_task_completion | native_command_suffix_once_and_last_input_identity_survives_oob | 300 | ACT | after login |
| same | same | 2500 | READ | read waits for `after` (task suspends 2 s); the suffix this test guards against would come from the same task end, inside the 0.1 s trailing drain |
| same | same | 1500 | READ | read waits for `oob-done` (fork suspends 1 s) |
| server/max_line_bytes | unterminated_line_at_limit_closes_connection | 500 | LOG | `assert_log.timeout_ms: 10000` |
| same | telnet_subnegotiation_at_limit_closes_connection | 500 | LOG | same |
| server/proxy_delayed_prelude | proxy_prelude_after_delay_reaches_read_login | 2000 | BEHAVIOUR | the delay before the PROXY prelude is the scenario |
| server/startup_repair_broken1..5 | (one test each) | 5 x 500 | LOG | every `assert_log contains` gets `timeout_ms: 10000`; the repair messages are written while the server loads the canned database |
| server/startup_repair_anon1..5, anon7 | (one test each) | 6 x 750 | FILE | the next `assert_file` already has `timeout_ms: 5000`, and checkpoints are published by rename, so it cannot see a partial file |
| server/signals_timers | sigalrm_during_blocked_outbound_connect_fires_connect_timeout_not_checkpoint | 1000 | BEHAVIOUR | gives the task time to block inside the outbound connect before SIGALRM; no observable event |
| same | same | 1000 | BEHAVIOUR | absence window before `assert_log not_contains` |
| server/dump_database | dump_database_logs_checkpoint | 1000 | LOG | `assert_log.timeout_ms: 10000` |
| server/database_disk_size_selection | chooses_input_before_dump_and_checkpoint_after_dump | 1500 | left | waits for the checkpoint before overwriting `.new`; the only existing step that waits for that file is `assert_file`, which would add an assertion the test does not make |
| server/database_disk_size_failed_dump | failed_dump_selects_existing_output | 1500 | left | the expected size already holds before the failed dump finishes, so a poll would not wait for it |
| server/error_callback_context | timeout_{resource}_frame_and_payload (x2 rows) | 2500 | left | the check asserts `length(cb_events) == 1`; a poll could pass before a duplicate handler call |
| builtins/background_threads | threads_reports_active_background_test_handle | 1500 | POLL 10000 | `unset` -> `done` |
| builtins/move_hooks_suspend_toast_oracle | do_command_dispatch_completes_after_enterfunc_suspend | 500 | ACT | the next step moves the player (side effect) |
| builtins/network_matrix | open_network_connection_loopback_... | 200 | left | after open_network_connection; the next check has no event to wait for (the connection exists when the call returns) |
| same | same | 200 | POLL 10000 | after boot_player, membership in `connected_players(1)` goes 1 -> 0 |
| builtins/notify_semantics | no_flush_notify_returns_zero_when_unread_output_queue_is_full | 500 | ACT | next step changes server options and notifies |
| builtins/server_admin | boot_player_disconnects_open_connection | 100 | POLL 10000 | membership goes 1 -> 0 |
| builtins/server_log | server_log_basic, server_log_with_level | 2 x 200 | LOG | `assert_log.timeout_ms: 10000` |
| builtins/set_thread_mode_activation_scope | forked_task_starts_threaded | 500 | POLL 10000 | `-1` -> `1` |
| builtins/task_local | suspend_between_verb_calls | 7000 | POLL 20000 | `task_local_done` `0` -> `1`, set last by the verb; the next step reads the result once |
| fork/fork_timing | fork_zero_delay_executes | 500 | POLL 10000 | `0` -> `42` |
| same | fork_killed_does_not_execute | 3000 | BEHAVIOUR | the killed 2 s fork must not run during the window |
| same | fork_zero_delay_child_observes_rest_of_forking_slice | 500 | POLL 10000 | `saw` `-1` -> `1`; a wrong slice order gives `0` |
| language/error_traceback | uncaught_forked_call_function_error_reaches_server_handler | 500 | LOG | both `assert_log` steps get `timeout_ms: 10000` |
| same | uncaught_forked_handler_stack_frames_are_complete | 500 | POLL 10000 | `audit_uncaught_args` starts `{}` (indexing raises) |
| same | uncaught_forked_handler_preserves_custom_message_and_value | 500 | POLL 10000 | same |

Counts. `wait:` steps: 173 (177.6 s) before, 65 (36.6 s) after. Of the 108
removed: CKPT 34, POLL 49, LOG 11, FILE 6, READ 6, LOADED 2. Of the 65 kept:
BEHAVIOUR 10, ACT 42 (16 of them the 100 ms waits in
connection_callback_context), and 13 left because a poll is unsafe or there
is no event to wait for. `restart_server.wait_ms`: 26 (8.0 s) before, 1
(0.3 s, BEHAVIOUR) after; the 25 removed were LOADED or folded into a POLL.
`down_ms`: all 4 (19 s) kept as BEHAVIOUR. New fields in use: 50 `poll_ms`,
34 added `checkpoint_timeout_ms`, 35 `assert_log.timeout_ms`.

Note on CKPT: `checkpoint_timeout_ms` also fails the restart if no fresh
checkpoint appears within 10 s. Before, a missing checkpoint made the restart
adopt an older output, and every converted test then checks restored state
that only the fresh checkpoint contains, so it failed anyway. The docs
already recommend this field over a fixed sleep.

POLL safety rule used for every conversion: a poll is used only when no
wrong outcome the test is designed to detect passes through a state that
satisfies the expectation. Checks built to catch an extra or duplicate event
("exactly once", "only", an explicit `== {}` absence) are left alone, as are
checks whose expected value already holds before the event.

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

Commits on this branch: Part 1 (raw reads + login), Part 2 (port poll),
Part 3a (poll_ms, assert_log timeout_ms: controller), Part 3b (YAML: data).
CI's change_boundary.py rejects a PR that mixes controller and data paths,
so 3b must be its own PR after the controller PR (Parts 1, 2, 3a) merges.
Measured and recorded above: Barn 689.4 s -> 319.1 s, Toast (local
(local release build), MI-hardening deselected) 808.1 s -> 388.1 s, no pass/fail change on
Barn and none attributable on Toast.

Unverified: CI's Toast (CI's pinned build) build; the four MI-hardening tests on any
Toast (deselected locally because (local release build) aborts on them; none of them is
touched by this branch); the converted task_scheduling and task_local cases
on Barn (Barn's profile skips fork-feature tests); object_dump_persistence and
restart_task_semantics::indefinitely_suspended on Toast (fail on (local release build) at
base for semantic reasons). CI on the PRs is the remaining check.

Harness-owned time still left: raw reads with no expectation that see
nothing (~80 s per engine; left because nothing says what they wait for and
not reading changes close semantics) and one 50 ms port poll per start.
