# ToastCore fixture profile lane

## Goal

Run the ToastCore suites (`requires: features: [toastcore_fixture]`, first one
is `server/toastcore_interactive_lifecycle.yaml` in PR #85) on Toast in CI, so
the execution ledger counts them as executed (Q, 2026-11-14: "Build ToastCore
profile").

## State

This controller PR adds `feature.toastcore_fixture` to the Toast lane
profile.json in `toast-conformance-core.yml`: true on `64bit-outbound-on`,
false on the other two lanes. Both the authoritative and the informational
candidate lanes write the same profile.

PR #85 (data only) then adds `_db/startup/toastcore.db` with its
`startup-fixtures.sha256` line and `server_db: toastcore.db` in the suite.

## Decisions and why

- Separate PRs: `change_boundary.py` rejects a PR mixing controller paths
  (`.github/`) and data paths (`_tests/*.yaml`, `_db/*.db`), and
  `toast-conformance.yml` runs on `pull_request_target`, so a lane added in a
  data PR never runs.
- Fixture via suite `server_db` from `_db/startup/` (existing mechanism,
  `runner.py` `_resolve_suite_server_db`), not a separate `--server-db` lane:
  the ledger requires every profile report to carry the full case surface, so a
  ToastCore-primary lane would run every Test.db case on ToastCore.
- One lane only: the cases were verified on 64-bit outbound-on Toast; the
  ledger needs one executing profile.
- Engines whose profile lacks the feature (Barn's) skip with
  "Requires feature: toastcore_fixture", a declared reason
  (`conditions.py` `declared_runtime_skip_reasons`), so
  `--fail-on-unexpected-skip` accepts it.

## Next step

Merge this PR, then re-run PR #85's checks.
