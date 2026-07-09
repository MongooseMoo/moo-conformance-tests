You are a coding subagent working in C:\Users\Q\code\moo-conformance-tests.

Task: plan and implement conformance coverage for the real outbound/listener/network matrix, corresponding to gap #4 from the foreman objective.

You are not alone in this codebase. Other workers may be changing unrelated files. Do not revert or modify work you did not make. Keep your changes scoped to this slice.

Primary write scope:
- Prefer new or existing YAML under src/moo_conformance/_tests/builtins/ or src/moo_conformance/_tests/audit/ for open_network_connection, listen, unlisten, listeners, listener options, IPv4/IPv6 option behavior, connection_name_lookup, connection_info, and buffered_output_length.
- You may add small harness support only if the current step vocabulary cannot express a Toast-observed network behavior.
- Do not edit DB backend, background/thread, read_stdin, curl/spellcheck/simplex, or exec-specific suites.

Requirements:
1. Inspect the current tracked tests and ToastStunt network/server source/tests yourself.
2. Add meaningful stateful tests beyond signature and one simple loopback case.
3. Cover deterministic local behavior only. Avoid public internet dependency.
4. Include both enabled and disabled outbound-network profiles where the existing profile/skip mechanisms support that.
5. Exercise listener option permutations and connection state transitions where deterministic.
6. Gate optional or environment-dependent behavior with existing suite mechanisms.

Expected verification:
- Run focused collection for your new/changed tests with uv.
- Run focused execution against the Toast oracle when feasible. Use the WSL Toast oracle pattern documented in the repo/memory: /root/src/toaststunt/build-release/moo in WSL, with uv run moo-conformance --server-command="/root/src/toaststunt/build-release/moo {db} {db}.out -p {port}".
- Run relevant unit/schema tests if you change harness/schema code.
- Run git diff --check.

Commit and report:
- Stage only the files you changed.
- Commit your slice with a descriptive message.
- Write reports/coverage-network-matrix-report.md with:
  - summary of behaviors covered
  - files changed
  - commands run and exact outcomes
  - commit hash
  - any intentionally deferred behavior with the exact reason

Do not ask questions. Make conservative decisions from the current repo.
