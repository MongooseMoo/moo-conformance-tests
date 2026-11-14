# Publish numeric-preposition conformance coverage

## Goal

Catch the Mongoose initializer defect in the shared MOO conformance suite.
Q authorized publishing/merging the tests and said "Make it so!" on October 21.
Smallest change: reuse the two existing YAML fixtures, 96 lines, and this handoff;
no controller, workflow, profile, or harness change.

## State

- Branch `test/numeric-prepositions-integration`, based on current suite main `6e55e6c9a8bb2db188d94627ec92b66f6deafacb`.
- PR: https://github.com/MongooseMoo/moo-conformance-tests/pull/134, paired with Barn #484. CI for `a885465` passed all three Toast profiles and the full-suite/quality checks. The handoff-only update still requires current-head PR CI before merge; fixture bytes remain identical to `441c0bfe`.
- Cherry-pick `6d4f12e` contains only fixture commit `441c0bfe`; its unrelated unknown-builtin parent is excluded.
- Range fixture checks canonical readbacks for 0..14 and E_INVARG for 15..32, leaving refused argument specs unchanged.
- Lexical fixture checks 18 inputs, including leading zeros, signs, whitespace, overflow, names and empty strings.
- Both use explicit test-owned driver receivers, bounded probes, restoration and recycling.
- Existing October 18 canonical and repaired Barn receipts are historical. The PR's existing Toast CI establishes the current result; no local CI steps are rerun.

## Decisions and why

The fixtures belong in the shared suite. Barn CI already checks out suite main,
so publishing them there gives the existing job this regression coverage.
The separate Barn integration branch contains the implementation repair.

## Surprises

Barn previously accepted every bounded numeric probe through 32; canonical Toast
stopped at 15. The real initializer depended on that native error for termination.
The tests assert native outcomes and readbacks rather than relying on a timeout.

## Next step

Follow the existing current-head Toast checks and merge PR #134 only if valid.
Ensure final Barn PR #484 CI consumes suite main containing these fixtures.
On a failed step, preserve raw output and stop for Q; do not fix CI or rerun around it.
