# Goal

Keep option tokens containing `_tests` intact when the CLI extracts bare suite selectors.

# State

Isolated worktree created from current origin/main. Regression reproduced the actual option being replaced by `--moo-suite-path=.` on both POSIX and Windows path spellings. Minimal production fix applied. Focused unit result: `4 passed, 32 deselected in 0.07s`. Diff inspected; `git diff --check` produced no output. No publication performed.

# Decisions and why

The actual `--moo-suite-root=/mnt/c/Users/Q/code/moo-conformance-tests/src/moo_conformance/_tests` argument was interpreted as the bare selector `.`. Preserve option tokens before pathname normalization; retain existing bare-path handling.

# Surprises

Bare absolute POSIX and Windows file selectors already pass; they must remain supported.

# Next step

Parent inspected the source, four regression instances and raw RED/GREEN output.
Publish the bounded fix for required PR quality/conformance checks, then obtain
an independent final verdict before a normal merge. The focused canonical Toast
HTTP run used the existing packaged-root path and completed 26 passed, one
deselected; it does not substitute for this fix's PR checks.
