# Portable failed-dump fixture data

## Goal

Fix the existing failed-dump fixture without weakening its assertion. Q approved
the upstream correction after Banteng PR82 reached one remaining fixture failure.

## State

Local commit506e4a4 on branch fix/portable-dump-fixture, worktree
C:/Users/Q/code/moo-conformance-portable-dump-fixture. Based on controller
commit38d9686 (PR157), not yet trusted main. Do not publish the data PR against
main until the controller lands; CI rejects mixed controller/data candidates.

## Decisions and why

Smallest data change (~12 changed lines): remove Toast/Barn temp-name blockers,
deny directory writes with chmod500 after the initial input-size assertion,
then retain dump/wait/output-size assertion. Cleanup always restores700 before
server shutdown. ManagedServer uses tempfile.mkdtemp, whose POSIX mode is700.
Require unprivileged_posix because root bypasses permissions and native Windows
does not enforce these POSIX directory modes. No new assertion or test gate.

Toast CI authority is eaaa1972f0993a1247f787dbf2dd5a01702ef442;
db_file.cc:1128-1142 chooses a temp name then opens it, and1285-1294 selects
existing output after an attempted dump. The expectation remains5, not the
size of a successfully rewritten database.

## Surprises

Banteng previously rethrew a checkpoint IOException after committing the task.
Source comparison with Toast server.cc:2618-2627 confirmed that ordinary dump
failure must not raise into that task. Banteng0ae2c84 now logs ordinary failures
and keeps checkpoint_finished(false), preserving shutdown's throwing path.
Its CI40378241127 completed against unchanged suite main: Java and other checks
passed; only the old failed-dump fixture fails. This corrected fixture has not
yet executed against Banteng.

## Next step

PR157 head38d9686 passed all authoritative/candidate Toast profiles and both
required exact-head checks in CI40377666217. Reporter attempt2 passed after a
GitHub HTTP502. Q corrected the unnecessary retry-permission request; the shared
rule in C:/Users/Q/.codex/AGENTS.md:93 was clarified before retrying.
The separate question requesting normal merges for controller157 and then this
fixture after green CI is still pending. Once Q gives that go-ahead and the
controller is trusted on main, publish this data slice, inspect its full Toast
profiles, then validate Banteng against the resulting latest main.
