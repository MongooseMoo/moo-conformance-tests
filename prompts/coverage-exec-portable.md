You are a coding subagent working in C:\Users\Q\code\moo-conformance-tests.

Task: plan and implement conformance coverage for platform-dependent exec behavior, corresponding to gap #6 from the foreman objective.

You are not alone in this codebase. Other workers may be changing unrelated files. Do not revert or modify work you did not make. Keep your changes scoped to this slice.

Primary write scope:
- Prefer src/moo_conformance/_tests/server/exec*.yaml and any narrowly required test fixture files under a repo-appropriate fixture directory.
- You may edit harness/schema code only if needed for portable executable fixture handling.
- Do not edit DB backend, background/thread, read_stdin, curl/spellcheck/simplex, or network matrix suites.

Requirements:
1. Inspect the current tracked exec tests, skipped cases, harness support, and ToastStunt exec behavior yourself.
2. Replace or supplement Windows-skipped executable cases with portable deterministic coverage where possible.
3. Cover process I/O, arguments, exit status, suspended exec task visibility, kill_task interaction, resume behavior, and multiple simultaneous execs where deterministic.
4. If fixture executables/scripts are required, make the fixture path portable or gate clearly by platform/config.
5. Preserve existing security/path rejection coverage.
6. Keep tests suitable for managed-server mode.

Expected verification:
- Run focused collection for your new/changed tests with uv.
- Run focused execution against the Toast oracle when feasible. Use the WSL Toast oracle pattern documented in the repo/memory: /root/src/toaststunt/build-release/moo in WSL, with uv run moo-conformance --server-command="/root/src/toaststunt/build-release/moo {db} {db}.out -p {port}".
- Run relevant unit/schema tests if you change harness/schema code.
- Run git diff --check.

Commit and report:
- Stage only the files you changed.
- Commit your slice with a descriptive message.
- Write reports/coverage-exec-portable-report.md with:
  - summary of behaviors covered
  - files changed
  - commands run and exact outcomes
  - commit hash
  - any intentionally deferred behavior with the exact reason

Do not ask questions. Make conservative decisions from the current repo.
