# README update and main pull

## Current state

- The user requested a README update and push, then explicitly directed that `main` be pulled first.
- `origin/main` was fetched successfully.
- Local `main` began 16 commits ahead and 113 commits behind `origin/main`.
- `git pull --no-rebase origin main` started a normal merge, preserving local commit history.
- The pull merged `src/moo_conformance/server.py` and `tests/test_managed_server.py` automatically.
- The normal pull merge was completed as commit `98cacda` with local and remote `main` as its two parents.
- `README.md` now documents managed checkpoint/restart coverage and the current Toast command shape.
- PR #64 is open and ready for review from `agent/checkpoint-roundtrip-conformance` into `main`.
- CI rejected PR #64 because its candidate tree mixes controller changes with conformance-data changes.
- A controller-only branch, `agent/checkpoint-restart-controller`, now starts at current `origin/main` and contains two cherry-picked commits: `2ae5357` and `3098b44`.
- The controller-only diff contains exactly `src/moo_conformance/server.py` and `tests/test_managed_server.py`.
- Unrelated untracked files remain untouched.

## Verification

- The conflict was resolved by preserving remote's `features: [fork]` classification and adding the local `resume` builtin requirement.
- Focused managed-server and schema verification passed: 79 tests.
- Full repository unit verification reported 459 passed and one environment-contamination failure because the existing ignored `build/lib/moo_conformance/test_conformance.py` duplicates the packaged execution owner.
- The unrelated ignored build artifact and stable test were not modified.
- GitHub Actions root cause: `change_boundary.py` classified controller paths (`server.py`, `test_managed_server.py`) and data paths (the audit/server YAML files) in the same candidate, then failed closed before Toast execution.
- The required quality and full-suite checks on PR #64 are downstream failures from that rejected admission; the Toast matrix did not run.

## Next action

- Run the controller branch's unit, Ruff, and mypy gates.
- Push the controller-only branch and open a ready-for-review controller PR into `main`.
- Leave PR #64 as the dependent data/README PR until the controller PR is explicitly authorized to merge and lands on `main`.
