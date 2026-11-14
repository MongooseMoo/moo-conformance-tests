# Goal

## Current merge delivery

Q explicitly requested merging the Barn and MCT campaign PRs after the prior
stop. MCT 180 is open. Required quality and two Toast profiles passed; the
required 64-bit outbound-on profile failed three move-hook cases: a timeout
followed by two E_VARNF results. The corresponding candidate-controller profile
passed. Cause is being investigated from the retained raw CI artifact, not
assumed transient. The required lane invokes unchanged base-controller pytest,
so the new CLI option guard is not executed there. Candidate data, transport and
runner are unchanged. A managed canonical focused run of both consecutive
move-hook suites plus admission completed nine passed in 17.21 seconds. That
does not identify the original cause, and the local oracle differs from the CI
pinned build. No source/test repair or timeout increase is selected.

Root selected a failed-job rerun as a controlled recurrence probe, not as a
diagnosed transient fix. Original raw artifacts remain in .tmp/pr180-failed-64on;
new attempt evidence will be kept separately. The full facts, competing theories,
source citations and primary-documentation limits are in
reports/cli-option-ci-investigation.md.

Next step: resolve the actual failing producer, obtain required exact-head
checks and independent final verification, then normal merge and local main
integration. Preserve the original failure and unrelated checkout files.

Keep option tokens containing `_tests` intact when the CLI extracts bare suite selectors.

# State

Isolated worktree created from current origin/main. Regression reproduced the actual option being replaced by `--moo-suite-path=.` on both POSIX and Windows path spellings. Minimal production fix applied. Focused unit result: `4 passed, 32 deselected in 0.07s`. Diff inspected; `git diff --check` produced no output. No publication performed.

# Decisions and why

The actual `--moo-suite-root=/mnt/c/Users/Q/code/moo-conformance-tests/src/moo_conformance/_tests` argument was interpreted as the bare selector `.`. Preserve option tokens before pathname normalization; retain existing bare-path handling.

# Surprises

Bare absolute POSIX and Windows file selectors already pass; they must remain supported.

# Next step

The controlled required-profile repeat passed: 13779 tests, no failures/errors,
30 declared skips; all three originally failing move cases passed without skips,
and admission passed all four probes. Original timeout cause remains unknown.
The final verifier confirmed both required head checks and raw profile/quality
evidence, but strict protection then reported the branch behind current main.

Current main's independently merged checkpoint-hook test was integrated without
conflict. No CLI implementation or regression changed during integration.
Publish this combined head, obtain fresh required checks and final verification,
then normal merge and local main integration. Preserve original and repeat raw
captures separately; a passing repeat is not a diagnosis of the old timeout.
