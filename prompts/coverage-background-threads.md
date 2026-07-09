You are a coding subagent working in C:\Users\Q\code\moo-conformance-tests.

Task: plan and implement conformance coverage for background/thread runtime behavior, corresponding to gap #1 from the foreman objective.

You are not alone in this codebase. Other workers may be changing unrelated files. Do not revert or modify work you did not make. Keep your changes scoped to this slice.

Primary write scope:
- Prefer a new YAML suite under src/moo_conformance/_tests/builtins/ for background/thread behavior.
- You may edit tests/schema/runner code only if the existing harness cannot express a required Toast behavior, but keep that change narrowly tied to this slice.
- Do not edit DB backend, read_stdin, curl/spellcheck/simplex, network matrix, or exec-specific suites.

Requirements:
1. Inspect the current tracked tests and ToastStunt source/tests yourself. Do not rely on chat summaries.
2. Identify the actual undercovered background/thread runtime behaviors for background_test, thread_pool, threads, and set_thread_mode.
3. Add meaningful behavioral conformance tests, not only presence or arity checks.
4. Gate optional or compile-time-dependent behavior with the existing suite mechanisms when appropriate.
5. Prefer Toast-observed behavior. If you add a test that should pass only with a feature enabled, make the skip/assumption explicit in YAML.
6. Keep the tests deterministic and suitable for managed-server mode.

Expected verification:
- Run focused collection for your new/changed tests with uv.
- Run focused execution against the Toast oracle when feasible. Use the WSL Toast oracle pattern documented in the repo/memory: /root/src/toaststunt/build-release/moo in WSL, with uv run moo-conformance --server-command="/root/src/toaststunt/build-release/moo {db} {db}.out -p {port}".
- Run the relevant local unit/schema checks if you changed harness/schema code.
- At minimum run collect-only for the full conformance test surface you affected.

Commit and report:
- Run precommit-equivalent checks available in the repo, at minimum git diff --check and focused uv tests.
- Stage only the files you changed.
- Commit your slice with a descriptive message.
- Write reports/coverage-background-threads-report.md with:
  - summary of behaviors covered
  - files changed
  - commands run and exact outcomes
  - commit hash
  - any intentionally deferred behavior with the reason

Do not ask questions. Make conservative decisions from the current repo.
