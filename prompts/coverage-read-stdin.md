You are a coding subagent working in C:\Users\Q\code\moo-conformance-tests.

Task: plan and implement conformance coverage for console/stdin behavior, corresponding to gap #2 from the foreman objective.

You are not alone in this codebase. Other workers may be changing unrelated files. Do not revert or modify work you did not make. Keep your changes scoped to this slice.

Primary write scope:
- Prefer a new YAML suite under src/moo_conformance/_tests/builtins/ for read_stdin behavior.
- If the harness needs a narrow managed-server stdin primitive to test read_stdin, you may edit the minimal runner/server/transport/schema files required for that primitive.
- Do not edit DB backend, background/thread, curl/spellcheck/simplex, network matrix, or exec-specific suites.

Requirements:
1. Inspect the current tracked tests, harness capabilities, and ToastStunt read_stdin implementation yourself.
2. Determine whether read_stdin can be tested in the current managed-server architecture.
3. If it can be tested, add behavioral coverage for real stdin blocking/resume behavior and error/permission/arity behavior where applicable.
4. If a small harness primitive is required, implement it as a general test step only as far as needed for read_stdin and document the schema.
5. If live stdin behavior is impossible to test safely in this harness, add the strongest deterministic coverage possible and report the exact blocker, with evidence from source/harness behavior.
6. Gate optional or compile-time-dependent behavior with existing suite mechanisms when appropriate.

Expected verification:
- Run focused collection for your new/changed tests with uv.
- Run focused execution against the Toast oracle when feasible. Use the WSL Toast oracle pattern documented in the repo/memory: /root/src/toaststunt/build-release/moo in WSL, with uv run moo-conformance --server-command="/root/src/toaststunt/build-release/moo {db} {db}.out -p {port}".
- Run relevant unit/schema tests if you change harness/schema code.
- Run git diff --check.

Commit and report:
- Stage only the files you changed.
- Commit your slice with a descriptive message.
- Write reports/coverage-read-stdin-report.md with:
  - summary of behaviors covered
  - files changed
  - commands run and exact outcomes
  - commit hash
  - any intentionally deferred behavior with the exact reason and evidence

Do not ask questions. Make conservative decisions from the current repo.
