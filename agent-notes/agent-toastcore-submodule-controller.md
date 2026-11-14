# ToastCore submodule controller support

## Goal

Let PR #85 supply the ToastCore database as a git submodule of
lisdude/toastcore (Q, 2026-11-14: submodule, not a copied DB; "Loosen checks
for submodule", narrowest version).

## State

This controller PR, which must land before #85:

- (Follow-up controller PR) `.gitmodules` names the one submodule,
  `src/moo_conformance/_db/startup/toastcore` ->
  `https://github.com/lisdude/toastcore.git`. It is a controller path, so a
  data PR cannot change the URL.
- `change_boundary.py` admits git mode 160000 only at that path, and
  classifies the gitlink as data (the pinned commit is data).
- `startup_fixtures.py` admits the one `toastcore` directory and treats only
  `toastcore/toastcore.db` inside it as a fixture, checked by a manifest line
  like any flat file. Other nested paths and manifest names are still
  rejected; an unfetched submodule fails as a missing fixture.
- Every workflow checkout that runs tests, validates fixtures or runs the
  suite fetches submodules (`toast-conformance-core.yml` quality, full-suite,
  ledger, both candidate-controller lanes; `paired-candidates.yml` candidate
  data). The classifier checkouts do not need it.
- `runner.py` is unchanged: `server_db: toastcore/toastcore.db` already
  resolves inside `--server-db-dir` (`_resolve_suite_server_db`).
- `package-data` is unchanged: startup fixtures are not in the wheel.

## Decisions and why

- `.gitmodules` before the gitlink: `.gitmodules` is controller and the
  gitlink is data, and `change_boundary.py` rejects a PR mixing them.
- `.gitmodules` in its own follow-up PR: the classify job runs the base
  branch's `change_boundary.py`, which classed `.gitmodules` as unknown, so
  this PR's first run failed with "unclassified semantic paths: .gitmodules".
  Order: this PR (classifier, validator, checkouts), then `.gitmodules`, then
  #85.

## Next step

After merge: #85 adds the gitlink at
1887eacd591d97fdc55d258a76e2167899b1951d, the manifest line, and
`server_db: toastcore/toastcore.db`. Barn's CI checkout of the suite needs
`submodules: true` before #85 merges (Barn loads the suite DB before the
feature skip).
