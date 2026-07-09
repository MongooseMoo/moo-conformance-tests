You are a coding subagent working in C:\Users\Q\code\moo-conformance-tests.

Task: plan and implement conformance coverage for optional extension builtin behavior, corresponding to gap #3 from the foreman objective.

You are not alone in this codebase. Other workers may be changing unrelated files. Do not revert or modify work you did not make. Keep your changes scoped to this slice.

Primary write scope:
- Prefer focused YAML additions under src/moo_conformance/_tests/builtins/ for curl, url_encode, url_decode, spellcheck, simplex_noise, malloc_stats, and any other optional extension surfaces you prove are only presence/signature-covered.
- Do not edit DB backend, read_stdin, background/thread, network matrix, or exec-specific suites.

Requirements:
1. Inspect the current tracked tests and ToastStunt source/tests yourself. Do not rely on chat summaries.
2. Identify which optional extension builtins still have only presence/signature coverage.
3. Add meaningful deterministic behavior tests, not only existence or arity checks.
4. For curl, cover real behavior only when deterministic in the harness; otherwise cover concrete error maps, protocol restriction behavior, timeout/header flag semantics, and option validation proven from Toast.
5. For URL helpers, cover more than a single reserved-character roundtrip: malformed percent encodings, plus/space behavior, high-byte/binary-string behavior where Toast defines it.
6. For spellcheck/simplex/malloc_stats or similar optional builtins, gate tests with skip_if or requires so servers without the feature skip cleanly.
7. Keep behavior Toast-backed where feasible. Avoid network calls to uncontrolled public services.

Expected verification:
- Run focused collection for your new/changed tests with uv.
- Run focused execution against the Toast oracle when feasible. Use the WSL Toast oracle pattern documented in the repo/memory: /root/src/toaststunt/build-release/moo in WSL, with uv run moo-conformance --server-command="/root/src/toaststunt/build-release/moo {db} {db}.out -p {port}".
- Run relevant unit/schema tests if you change harness/schema code.
- Run git diff --check.

Commit and report:
- Stage only the files you changed.
- Commit your slice with a descriptive message.
- Write reports/coverage-optional-extensions-report.md with:
  - summary of behaviors covered
  - files changed
  - commands run and exact outcomes
  - commit hash
  - any intentionally deferred behavior with the exact reason and evidence

Do not ask questions. Make conservative decisions from the current repo.
