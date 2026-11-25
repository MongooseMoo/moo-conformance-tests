# Paired conformance startup fixtures

## Goal

Restore paired Barn and conformance verification by making the tracked startup fixture available to the trusted controller's existing tests.

## State

Paired run 45565105324 passed Toast admission. Its explicit pair job stopped during controller quality checks. `test_repository_startup_fixture_manifest_is_exact` reported `missing startup fixture files: toastcore/toastcore.db`. The paired job checked out the controller without submodules and checked out the candidate data with submodules.

The paired controller checkout now initializes its pinned submodules. The existing workflow contract test failed without that setting and passed with it. The workflow test file, Ruff, actionlint and `git diff --check` passed.

## Decisions and why

Keep the fixture test and both checkout revisions. Fetch the submodule in the checkout that actually runs the fixture test. It already exists as a tracked gitlink in that revision.

## Surprises

The regular Toast workflow initializes the submodule in its trusted checkout. Its success does not show that the separate paired-controller checkout contains the fixture.

## Next step

Merge the workflow fix through protected CI, then run the paired workflow against the two default-branch revisions and check its verdict artifact.
