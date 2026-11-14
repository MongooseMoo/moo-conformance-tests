# Portable failed-dump fixture controller

## Goal

Q authorized fixing the conformance fixture upstream ("yeax fix in conformance
tests") after Banteng PR82 reached one remaining fixture failure. Keep the
existing failed-dump assertion: output selection must use the stale five-byte
output after an actual failed dump attempt. Do not skip a Banteng failure.

## State

Isolated worktree C:/Users/Q/code/moo-conformance-banteng-latest, branch
fix/portable-dump-controller from suite main3d51b08. Original checkout preserved.
Banteng PR82 implementation a8f2390 passes Java CI and all conformance except
this fixture (CI40289133756). Q explicitly authorized normal merges of this
controller PR157 and its dependent fixture after required CI passes. Controller
38d9686 passed all checks; main advanced to db38a71, now merged into this branch
for strict current-base CI before merging. Banteng code head is now0ae2c84.

## Decisions and why

Smallest complete repair: replace implementation-specific temporary-path
blockers with permission denial on the managed directory. Controller slice
(roughly100 lines including docs): a confined chmod step with three-digit octal
mode, available in ordinary steps and cleanup; unprivileged_posix config for
permission-denial cases. Windows loads the schema but skips POSIX execution.
No new test or validation gate. Use existing PR CI, never local CI reruns.
Publish controller separately from dependent conformance data, per repository
trusted-controller/candidate-data boundary. Data slice follows after controller.

Authority: CI pins Toast eaaa1972f0993a1247f787dbf2dd5a01702ef442, exactly the
local Toast source revision. src/db_file.cc:1128-1142 chooses a temporary filename
before fopen;1285-1294 chooses existing output after a dump attempt. Banteng's
LambdaMooV17Codec.writeAtomic uses a PID-qualified temporary name, so current
Toast/Barn blockers never deny its write. ManagedServer.start creates its
private directory via tempfile.mkdtemp (server.py:228), so restoring0700 in
fixture cleanup preserves its original POSIX mode.

## Surprises

The controller's cleanup loop currently accepts only MOO run steps; chmod must
run directly there before requiring any transport. Root bypasses permission
denial, so the fixture must require an unprivileged POSIX process explicitly.

## Next step

Controller implementation is72 changed lines plus this note. It reuses
require_confined_path rather than a new path resolver. Publish controller PR
and read CI. No local tests, typecheck, lint, or builds have been run.
Next: push the current-base merge, read required checks, normal-merge PR157,
then publish the dependent fixture. No renewed merge permission is needed.
