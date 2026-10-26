# Portable failed-dump fixture data

## Goal

Fix the existing failed-dump fixture without weakening its assertion. Q approved
the upstream correction after Banteng PR82 reached one remaining fixture failure.

## State

Local branch fix/portable-dump-fixture, worktree
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

Current Banteng handles a checkpoint IOException by throwing after committing
the task. This new actual failure may expose another runtime mismatch; inspect
its source against Toast's asynchronous dump behavior before claiming acceptance.

## Next step

Read PR157 CI. Once its controller is trusted on main, publish this data slice
and inspect full Toast profiles, then Banteng's latest-main conformance CI.
