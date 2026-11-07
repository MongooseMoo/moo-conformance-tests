# Goal

Pin checkpoint_started ordering after the dump_database caller returns, in a
standalone conformance PR. Do not merge, comment, or create issues.

# State

Created isolated branch tests/checkpoint-hook-order from origin/main. Required
Barn and conformance instructions read; existing checkpoint failure callback
setup inspected. No Barn source changes belong to this task. The final string
loop passed five Toast repetitions and 20/20 fixed Barn runs; unfixed master
failed 20/20. Publication and PR CI are next.

# Decisions and why

Use bundled Test.db, managed server lifecycle, a test-owned checkpoint_started
hook recording order_probe into seen, a bounded busy loop in the requesting
task, and a bounded suspension wait. Expect dump_database to return zero and
the hook to record exactly {2}. No chmod or unprivileged_posix requirement.

Plan: establish several Toast passes, measure many pre-fix Barn master runs,
then require all fixed-branch repetitions to pass. Keep capability admission
in each managed selection. Record fixture and executable identities and commands.
Publish only this YAML and this note. Barn PR #623 must merge before this PR;
both merges remain outside this task's authorization.

# Surprises

The original main checkout is behind origin/main and contains unrelated
untracked work. The isolated worktree preserves it.

The first draft used 2,000 arithmetic iterations (i * i). Toast passed six
managed runs (one broad collection and five selected-file runs). Unfixed current
Barn master passed 20/20: no red evidence from that draft. The final draft keeps
2,000 iterations but scans a fixed 16 KiB string with strsub, to widen the overlap
without raising the number of loop iterations or yielding the requesting task.

The final draft's first unfixed Barn run returned zero from the caller but the
hook observed the old committed value: raw assertion `expected = [2], actual =
[0]`, followed by `1 failed, 1 passed in 9.03s`. The test detects early hook
execution even when the caller itself does not encounter a commit conflict.

# Verification environment

All measurements use the managed Linux harness in WSL Debian, as root. The
selected source fixture is this branch's src/moo_conformance/_db/Test.db,
2,035 bytes, SHA-256
`1a3f23ebb549e02ccf5341668425118fcdc935b977096add87bc2a8ef29d408e`.
The harness owns disposable copies, server startup, restarts, and shutdown.

Executable SHA-256 identities (freshly built Barn binaries):

- Stock oracle /root/src/toaststunt/build-release/moo:
  `72fb1cf96cb303647a8ee72808e7c1ff62a491ecf44f547e6757e71ba2402bde`.
- Unfixed origin/master, isolated barn-checkpoint-order-master/bin/barn:
  `45959346a5c494ff7501329ab8356f534deedada9c51404491a455ae35f50e59`.
- PR #623 fix/checkpoint-callback-flake, barn-checkpoint-flake/bin/barn:
  `8fb2991a9ac565f9512f813c69444cb9ebffd76bbd83393230c48d6249deecec`.

Barn binaries use Go 1.27.1, Linux amd64, default PGO and outbound-on.conf.
The stock-wsl-testdb.json oracle manifest supplies the strict Linux comparison.

Commands run from /mnt/c/Users/Q/code/mct-checkpoint-order through
`wsl -d Debian --exec bash -lc`, with `set -euo pipefail`. Each selected run:

```bash
UV_PROJECT_ENVIRONMENT=/root/.cache/checkpoint-order-conformance \
uv run --frozen moo-conformance \
  src/moo_conformance/_tests/server/dump_database_hook_order.yaml \
  -m "admission or conformance" \
  -k "capability_admission or checkpoint_started_observes_completed_dump_caller" \
  --server-command="$server_command" \
  --server-db=src/moo_conformance/_db/Test.db \
  --server-db-dir=src/moo_conformance/_db/startup \
  --moo-host=127.0.0.1 \
  --oracle-profile-manifest=/mnt/c/Users/Q/code/barn/profiles/toast/stock-wsl-testdb.json \
  --fail-on-unexpected-skip --strict-markers -q
```

Toast server_command:
`/root/src/toaststunt/build-release/moo {db} {db}.new {port}`.
Toast additionally uses the same manifest as --target-profile-manifest.
Barn server_command (replace TREE with barn-checkpoint-order-master or
barn-checkpoint-flake):
`/mnt/c/Users/Q/code/TREE/bin/barn --db {db} --listen tcp://127.0.0.1:{port} --config=/mnt/c/Users/Q/code/TREE/profiles/barn/outbound-on.conf --profile-id=barn-linux-testdb-outbound-on --profile-manifest={manifest}`.

Every selected invocation collects two items: capability admission and the new
conformance case. No skips occurred in the completed runs.

Final test repetition results:

| Engine | Passes | Failures |
| --- | ---: | ---: |
| Managed stock WSL Toast | 5 | 0 |
| Unfixed origin/master Barn | 0 | 20 |
| Barn PR #623 branch | 20 | 0 |

Terminal raw summaries:

```text
TOAST LONG repetition 5/5
2 passed in 9.24s
BARN MASTER LONG cumulative passes=0 failures=20
BARN FIXED cumulative passes=20 failures=0
```

Both Barn executable hashes and the fixture hash were rechecked after the runs
and matched their pre-run values. Barn #623's source checkout stayed clean.

Unverified: post-merge Barn behavior, other engines/platforms, and the merged
cross-repository gate. These measurements establish the ordering assertion;
they do not claim that this case reproduces the original uncatchable E_INVARG.

# Next step

Publish the independent conformance PR and watch its checks. Leave it unmerged.
