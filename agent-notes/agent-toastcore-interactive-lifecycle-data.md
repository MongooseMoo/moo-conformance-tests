# ToastCore lifecycle delivery

## Goal

Finish conformance #85 with its real pinned ToastCore submodule database and
require the five lifecycle cases to execute in the supported Toast CI lane.

## State

Preserved and published the existing fixture/suite edits. Refreshed in a clean
detached delivery worktree because the original worktree has unrelated
uncommitted instructions. Resolved the fixture manifest merge by retaining
both the new ancestor fixture and ToastCore entries.

## Decisions and why

Keep the existing pinned upstream fixture and verify its actual SHA-256
against the manifest. The suite selects toastcore/toastcore.db via server_db;
the existing controller supports the nested gitlink and capability lane.
No controller changes belong in this data PR.

## Surprises

The original worktree already held the missing fixture integration, but it
had not been committed or published. Its unrelated instruction edits remain
in that original checkout.

## Next step

Publish the current-base candidate, verify managed Toast and Barn behavior,
require the full Toast profile union and execution ledger, then merge #85
after the Toast 2.8 cutover. Historical skip-only evidence is insufficient.
