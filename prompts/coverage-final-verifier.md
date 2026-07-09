You are a verifier subagent working in C:\Users\Q\code\moo-conformance-tests.

Task: audit the completed coverage work against the objective:
"For each of these except #5, launch a subagent to plan and implement the tests. don't stop until they're all covered. Use foreman protocol. Get it all merged to the main/master branch when done."

Required covered slices:
- #1 background/thread runtime behavior
- #2 console/stdin behavior
- #3 optional extension builtins
- #4 outbound/listener/network matrix
- #6 platform-dependent exec behavior

Excluded slice:
- #5 non-native DB backend and roundtrip behavior

Verifier requirements:
1. Verify current branch and commit graph. Confirm the work is on main or master and identify ahead/behind state.
2. Verify there is a committed implementation/report for each required slice:
   - background/thread: `02570f0822d6c262a40804016e7efcac9ab944c6`, report `reports/coverage-background-threads-report.md`
   - read_stdin: `1e1a8ba1806f31857748082c95c4e56b486e6925`, report commit `bf7159599c09bce2b64bbb73cada810a48f343e1`
   - optional extensions: `30cf56d`, report commit `28767f2`
   - network matrix: `fb10d43576487ce51c690021f99dc0840c592f9c`, report commit `8e98bac2083e41b198aed3eece6a47c88da176af`
   - exec portability: `4742603d2efd74f67ff87b7aa45c16335cb75cb7`, report commit `98a366a2159658a441ce9cabaa97fc72a5a0df0d`
   - coordination records: `5e8bc7946690c6e71d4d5284e11e10c1a82af711`, report commit `a5b815059c8ebef23482fbf855bb0a6f35c5f282`
3. Inspect the changed tests/harness enough to decide whether each required slice has meaningful behavioral coverage, not just presence checks.
4. Run verification gates:
   - `git diff --check`
   - relevant unit/schema tests for changed harness code
   - full collect-only if feasible
   - focused WSL Toast runs for the new suites if feasible, using `UV_PROJECT_ENVIRONMENT=.venv-wsl` and `/root/src/toaststunt/build-release/moo`
5. Do not modify production/test files. If you need a report file, write only `reports/coverage-final-verifier-report.md`.
6. Return a clear verdict: `MERGE` or `NO-MERGE`.

Write `reports/coverage-final-verifier-report.md` with:
- verdict
- exact commands and outcomes
- per-slice completion assessment
- residual risks or skipped behavior
- whether it is acceptable to push `main` to `origin/main`

Do not ask questions. Do not push.
