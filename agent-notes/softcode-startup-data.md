# Startup and checkpoint failure callback data

## Goal

Complete the startup and checkpoint failure portion of Q's approved Toast
server-to-softcode inventory, including complete invocation contexts.

## State

The two YAML suites are authored and passed focused exploratory Toast runs using
the controller implementation in PR #161. The local WSL binary differs from the
CI pin, so those runs are not pinned-oracle acceptance. This data branch contains
no controller modifications and requires #161 merged into main for trusted CI.
Q authorized PR publication and babysitting through CI, but not merging.

## Decisions and why

Use real launch arguments for --start-line and --start-script; assert argument
line preservation, both option orders, startup ordering, absent/nonexecutable
hooks, return/error/suspension and every server-frame field.

Use the existing exec installer with #161's confined checkpoint_fault fixture
for actual checked-write and publication failures. Assert status zero, the
branch-specific log diagnostic, full callback context, then successful recovery.
Open-failure coverage uses existing chmod in the independent callback data PR.

## Surprises

Toast ignores final fflush failure. The fixture DB must exceed stdio buffering
to force /dev/full to fail during checked serialization writes. A nonempty output
directory separately exercises rename/publication failure.

## Next step

Commit and publish this data separately. Before claiming acceptance, obtain the
controller merge decision from Q, rebase this data onto main containing #161,
and follow its trusted CI. Never mix controller code into this data branch.
