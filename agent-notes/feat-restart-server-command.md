# feat/restart-server-command

## Goal

Add a harness option (`--restart-server-command`) taking a second server command
template. First start and fresh-database restarts (`reset_db`) use
`--server-command`; a `restart_server` step that keeps the working database
starts the server with the second template, so engine B boots from the
checkpoint engine A wrote. Also: capability gating across both engines, a way
to select only tests with a kept-database `restart_server` step, unit tests,
and documentation next to `--server-command`.

Acceptance: Barn's `tests/mongoose-conformance/server/suspended_eval_checkpoint.yaml`
passes in both directions on current Barn master, and fails in both directions
(with the specific messages from the brief) on a Barn built from the commit
just before the PR 886 merge.

## State

Built, unit-tested, documented, acceptance check run. Committed locally on
`feat/restart-server-command`; not pushed, no pull request.

### What was built (file:line in this worktree)

- `src/moo_conformance/server.py`
  - `:127` `RestartCommandError`.
  - `:144` `ManagedServer(restart_command_template=)`, `:181`
    `on_restart_command`.
  - `:269-270`, `:292-296`, `:325` `start()` picks the template: restart
    command when one is set and the launch keeps the working database.
  - `:351-359` a restart-command launch that fails to come up raises
    `RestartCommandError` and does not latch the lifecycle failure.
  - `:453` `restart_command_exit()` describes a restart-command server that
    exited after opening its port.
- `src/moo_conformance/runner.py`
  - `:226` `restart_engine` attribute (capability probe target).
  - `:400-427` `_ensure_suite_server_db` leaves the restart command at test
    start: fresh database, `--server-command`, suite setups forgotten.
  - `:981-1003`, `:1015-1024` `_execute_restart_server` marks the server down
    on `RestartCommandError`, including a failed reconnect to a server that
    has exited.
- `src/moo_conformance/conditions.py:88` `keeps_database_across_restart(test)`.
- `src/moo_conformance/plugin.py`
  - `:178` `--restart-server-command`; `:329` passed to the managed server.
  - `:339-386` `RestartEngine` and the session `restart_engine` fixture.
  - `:522-533` the `runner` fixture attaches it.
  - `:680` `kept_db_restart` marker on parametrized cases; `:907` registered.
  - `:867-871` usage error without `--server-command`.
- `src/moo_conformance/test_conformance.py`
  - `:61-91` restart-engine probe caches (`_probing_restart_engine`).
  - `:433-442` second requirement check in `test_yaml_conformance`.
- `tests/test_restart_server_command.py`: 24 unit tests.
- Docs: `README.md` ("Restarting as Another Engine", options table),
  `docs/YAML_SCHEMA.md` (CLI options table, `restart_server` section).

### Checks run

- `uv run --frozen pytest tests/test_restart_server_command.py -q -p no:cacheprovider`
  (Windows, this worktree) -> `24 passed in 1.25s`.
- `uv run --frozen ruff check .` -> `All checks passed!`.
- `uv run --frozen --extra dev mypy src/moo_conformance` -> one error,
  `plugin.py:478: Module has no attribute "geteuid"`. That line is unchanged
  code and the error comes from type-checking on Windows (CI runs mypy on
  Linux). My changes add no mypy errors.
- No existing test file was run or edited. The full suite was not run.

### Acceptance check (final code, 2026-11-18, all results as the brief expects)

Setup, from Git Bash on the workstation:

- Detached Barn worktrees inside this worktree, both removed afterwards with
  `git worktree remove --force` + `git worktree prune`: `.tmp/barn-master` at
  Barn master's head, the PR 886 merge commit, and `.tmp/barn-pre886` at that
  merge's first parent (the PR 884 merge). `C:/Users/Q/code/barn` itself was
  not touched.
- Linux binaries, built in each worktree with
  `GOOS=linux GOARCH=amd64 CGO_ENABLED=0 go build -o <this worktree>/.tmp/bin/barn-<name> ./cmd/barn`
  (go1.27.1): `barn-master` SHA-256
  `ca3c9cfd87ab1116d56ea0cdd2e9fbcfd0a5cb872e5d5d9cc94c41d792526ef6`,
  `barn-pre886` SHA-256
  `71f7f9a39f9cc71914395d63854dad9a48067ab7b16e40449506324363b6a4a3`. Deleted
  after the runs.
- Toast: WSL Debian `/root/src/toaststunt/build-release/moo`, whose source
  checkout is at the stock commit pinned in Barn's
  `plans/barn-toast-mongoose-convergence-workstreams.md`; binary SHA-256
  `61dd1799d82f75e33cb9c42fe48bd1966199ad83fda2f6298e3a7f872cc613dd`.
- Fixture: this worktree's `src/moo_conformance/_db/Test.db`, SHA-256
  `1a3f23ebb549e02ccf5341668425118fcdc935b977096add87bc2a8ef29d408e`, copied to
  `.tmp/barn-master/.tmp/conformance/db/Test.db` (candidate mode needs it under
  the candidate root).
- Test: master's `tests/mongoose-conformance/server/suspended_eval_checkpoint.yaml`
  from `.tmp/barn-master`, unchanged, for all four runs.
- Driver: `.tmp/accept.sh <barn-first|toast-first> <barn-master|barn-pre886>`
  (untracked, still on disk), run as
  `MSYS_NO_PATHCONV=1 wsl -d Debian --exec bash -l /mnt/c/Users/Q/code/moo-conformance-tests-restart-command/.tmp/accept.sh <direction> <binary>`.
  Inside WSL, with `UV_PROJECT_ENVIRONMENT=$HOME/.cache/restart-command-conformance-linux`
  (removed afterwards), it runs:

  ```
  uv run --project $suite --frozen moo-conformance \
    -m 'admission or kept_db_restart' \
    --candidate-root=$repo --moo-suite-root=$repo/tests/mongoose-conformance \
    --moo-suite-path=server/suspended_eval_checkpoint.yaml \
    --server-db=$repo/.tmp/conformance/db/Test.db \
    --server-db-dir=$repo/.tmp/conformance/db/startup \
    --moo-host=127.0.0.1 \
    --oracle-profile-manifest=$repo/profiles/toast/stock-wsl-testdb.json \
    --fail-on-unexpected-skip --strict-markers -v -p no:cacheprovider \
    <engine options>
  ```

  `$suite` = this worktree, `$repo` = `$suite/.tmp/barn-master`.
  BARN = `$suite/.tmp/bin/<binary> serve --db {db} --listen tcp://127.0.0.1:{port} --config=$repo/profiles/barn/outbound-on.conf --profile-id=barn-linux-testdb-outbound-on --profile-manifest={manifest}`.
  TOAST = `/root/src/toaststunt/build-release/moo {db} {db}.new -p {port}`.
  barn-first: `--server-command=BARN --restart-server-command=TOAST`.
  toast-first: `--server-command=TOAST --restart-server-command=BARN --target-profile-manifest=$repo/profiles/toast/stock-wsl-testdb.json`.

Raw results (full logs: `.tmp/results/*.log`, untracked, still on disk):

1. master, Barn first then Toast: exit 0. `test_capability_admission PASSED`,
   `test_yaml_conformance[server/suspended_eval_checkpoint.yaml::suspended_eval_checkpoint_roundtrip] PASSED`,
   `2 passed in 37.56s`.
2. master, Toast first then Barn: exit 0. Same two `PASSED`, `2 passed in 38.72s`.
3. pre-886, Barn first then Toast: exit 1, `1 failed, 1 passed in 39.86s`:
   `moo_conformance.runner.AssertionError: Test 'step 'o = #1.conformance_suspended_e...'' expected value [1, 1, [1, 73], 1], but got [1, 1, 73, 1]`
4. pre-886, Toast first then Barn: exit 1, `1 failed, 1 passed in 26.62s`:
   `moo_conformance.server.RestartCommandError: Managed server exited before accepting connections`;
   the server log tail in the failure ends with
   `level=ERROR msg="Barn failed" err="load database: restore suspended tasks: suspended task 891098415: native frame 2: native builtin continuation requires conversion"`.
   The same log shows Toast (`STARTING: Version 2.8.0_7`) writing the
   checkpoint before Barn's boot lines, so the restart did change engines.

Two extra managed sessions, to see the between-tests behaviour with real
engines (suite root `.tmp/barn-master/.tmp/conformance/suites/server/` holding
byte copies `a_suspended_eval_checkpoint.yaml` and
`b_suspended_call_checkpoint.yaml` of master's two files, so a second
kept-restart test runs after the first; same command with
`--moo-suite-root=<that root> --moo-suite-path=server`):

5. pre-886, Toast first then Barn: exit 1, `1 failed, 2 passed in 48.00s`.
   Test a `FAILED` with
   `moo_conformance.server.RestartCommandError: Managed server exited after opening its port`
   and the same Barn `requires conversion` log line; test b then `PASSED`.
   So a failed boot of the restart engine did not stop the session, and the
   next test started again on Toast with a fresh database.
6. master, Toast first then Barn: exit 0, `3 passed in 56.50s`.

WSL load average during the runs was 20-25 on 32 CPUs; the test's fixed waits
still held.

## Decisions and why

1. **Which command a launch uses.** `ManagedServer.start()` uses the restart
   command exactly when one is configured and the launch keeps the working
   database (its existing fresh-copy condition is false). Every launch from a
   fresh copy (first start, `reset_db`, suite database switch, relaunch after
   `wait_for_server_exit`) uses `--server-command`. Why: that condition already
   is the harness's definition of "fresh database", and `start()` is the only
   place the template is formatted, so no caller has to choose.
2. **Later kept-database restarts in the same test** also use the restart
   command (A, B, B, ...). Why: it needs no per-test state, and the first
   restart is the one that crosses engines; alternating back would hand B's
   checkpoint to A inside a test whose expectations were written for one
   crossing.
3. **Getting back to engine A.** When a test begins and the managed server is
   on the restart command, the runner relaunches from a fresh copy of the
   suite database (so `--server-command`) and forgets which suite setups ran,
   so suite setup runs again on the fresh database. Why fresh, not kept: a
   kept restart would load B's database on A (a second crossing no test
   asserts on, whose failure would be reported against the wrong test), and a
   kept restart without a new checkpoint reloads the last adopted checkpoint,
   i.e. the state before the previous test's cleanup ran. Consequence: in a
   cross-engine session, database state does not carry from a kept-restart
   test into the next test.
4. **Capability gating.** A test with a kept-database restart must pass its
   `requires` and `skip_if` on both engines. Engine A is checked as before.
   Engine B is checked by asking B itself: the session starts a second server
   with the restart command on its own fresh copy and port, used only for
   capability probes, and runs the same enforcement functions against it with
   its own probe cache. Why not manifests alone: `requires.builtins` and
   `min_version` are never in a manifest (always live probes), and features
   absent from a manifest fall back to live probes, so only a live B can
   answer. Skip reasons are the existing declared ones, so
   `--fail-on-unexpected-skip` accepts them. If B's command writes
   `{manifest}` and `--oracle-profile-manifest` is given, B's manifest is
   validated against the oracle like the target's, and its `features` are
   used. Tests without a kept-database restart never reach B and are not
   gated on it.
5. **Selecting the tests.** A `kept_db_restart` pytest marker is attached at
   parametrization time (`pytest_generate_tests`), because `-m` filtering runs
   before this plugin's `trylast` `pytest_collection_modifyitems`.
6. **`named_log_file` config** is checked for B from the restart command's own
   `{log}` placeholder, through the same `requires.config` path, with no new
   config key.
7. **A restart command that does not come up fails that test, not the
   session.** `start()` raises `RestartCommandError` instead of the latched
   `ManagedServerLifecycleError`; the runner marks the server down so the
   test's cleanup is skipped and the next test relaunches fresh. Why:
   `plugin.py` `_record_managed_lifecycle_failure` stops the whole session on
   a lifecycle error, and "engine B cannot boot engine A's checkpoint" is the
   finding this feature exists to report (PR 886's Toast-to-Barn direction).
   A job that stopped at the first one could not run every restart test. A
   restart command that cannot be launched at all (bad executable) still
   aborts the session. This goes beyond the literal brief.

## Surprises

- Barn opens its listening port before it restores suspended tasks. In the
  Toast-to-pre-886-Barn run the harness's port poll therefore sometimes
  succeeded before Barn exited; the first version then reported
  `ConnectionRefusedError`/`BrokenPipeError` (reconnect, then cleanup against a
  dead server) instead of the boot failure. Seen in a two-test session, not in
  the first single-test run, so it is timing-dependent. Fixed by
  `ManagedServer.restart_command_exit()` and the reconnect handling in
  `_execute_restart_server`: both orderings now raise `RestartCommandError`
  with the server log (runs 4 and 5 show one each).
- `tests/test_requirements.py` calls `test_yaml_conformance(runner, case,
  moo_config, profile)` directly with four positional arguments, so the
  restart-engine probe target could not be a new fixture parameter without
  editing those tests. It is carried on the runner (`runner.restart_engine`).
- Existing unit tests use `Mock()` managed servers, whose every attribute is
  truthy; the runner tests the new server flag with `is True` and the
  `restart_command_exit()` result with `isinstance`.
- Git Bash rewrites a `/mnt/c/...` argument to `wsl` into a Windows path;
  `MSYS_NO_PATHCONV=1` stops it. `wsl --exec bash <script>` is not a login
  shell and has no `uv` on PATH; use `bash -l`.
- The ToastCore submodule is not initialized in this worktree. It was not
  needed: the acceptance test uses `Test.db`.

## Not verified

- The capability-skip path (B lacks a builtin/feature) is covered by unit
  tests with fake transports only; no real test in the acceptance selection
  is skipped for B.
- B's manifest validation against `--oracle-profile-manifest` ran for real
  only in the Toast-first runs (B = Barn writes `{manifest}`) and passed; its
  rejection path has no test.
- `restart_server` with `arguments` or `ignore_sighup` on the restart
  command, `wait_for_server_exit` followed by a kept restart, and suites with
  `server_db` were not exercised across engines.
- Which packaged kept-restart tests pass across engines is unknown; only
  Barn's two candidate files above were run.
- The full harness test suite and the full conformance suite were not run
  locally (CI does).
- Whether `function_info()`/`server_version()` probes without a manifest give
  the right answers on Toast for every feature name (for example `64bit`
  falling back to the `ONLY_32_BITS` option probe) was not checked; the
  acceptance tests require builtins only.

## Next step

Team lead pushes the branch and opens the pull request. Then the Barn-side CI
job: run `-m "admission or kept_db_restart"` twice, once per direction, with
the commands recorded above. Untracked `.tmp/accept.sh` and `.tmp/results/`
are left on disk for reference and can be deleted.
