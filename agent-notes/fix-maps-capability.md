# Maps capability classification

## Goal
Fix the verified active maps capability classifier so real maps support executes
the existing map suite while unsupported syntax and probe failures stay distinct.
Root owns publication and CI; this worker commits only.

## State
The bounded classifier and regressions are implemented. The documented managed
pinned Toast run executed all 127 map cases plus canonical capability admission.
No local Barn tests. Existing map expectations and suite marker remain unchanged.
Prior actual Barn CI collected 127 map suite cases and skipped all 127 for
Requires feature: maps while seven independent map-authority cases executed.
Pinned Toast likewise skipped the original RHS probe's maps requirement but
executed the exact expressions with actual map builtins required instead.

## Decisions and why
Fix the existing capability owner, preserve explicit profile feature.maps values,
and reuse the existing semantic probe rather than create another framework.

## Findings
- The active `_has_feature` uses an explicit boolean profile override first,
  then falls back to server feature-name membership for ordinary features. Bare
  maps is not advertised by the supporting engines used in the recorded runs.
- The fresh default branch has no targets.py semantic probe. That file existed
  only in the older checkout's uncommitted work, so it is not reused or copied.
- Reuse active `_dynamic_feature` for the constant `eval("return [1 -> 2];")[1]`
  probe. It preserves wizard identity, statement mode, integer 0/1 validation,
  successful-result caching, and transport/native failures as probe errors.
- Primary Toast `src/verbs.cc` bf_eval parses the supplied program: compilation
  rejection returns `{0, diagnostics}`; completed execution returns `{1, value}`.
  Permission and stack failures are native errors rather than unsupported syntax.
- Regressions exercise the actual map suite requirement, semantic unsupported
  result, cache behavior, failed-result retry, malformed values and transport
  exceptions. Existing explicit true/false/nonboolean profile-override tests stay.
  Generic advertised-feature checks now use optional_feature rather than maps.

## Surprises
No tracked AGENTS.md exists in this fresh worktree; the root agent supplied the
administration instruction from the main checkout. The required gh api probe
returned allow_auto_merge true. No workflow changes are included.

## Next step
Root publishes this independent PR and runs required repository CI. Inspect the
exact-head results before normal merge. No passing full repository CI is claimed.

## Verification evidence
The documented managed CLI ran from this worktree under Debian, using the pinned
`/root/src/toaststunt/build-release/moo` oracle, bundled Test.db, and Barn's stock
Toast profile as both oracle and target profile. Selection:
`_tests/builtins/map.yaml -k "capability_admission or map.yaml"`, port 17950,
`--fail-on-unexpected-skip --strict-markers`, with a Linux-only uv environment
outside the checkout. Admission context: maps-capability-pinned-toast.

Raw terminal output: `collected 128 items` and
`128 passed, 1 warning in 15.10s`. The warning concerns pytest's JUnit family.
XML query: `MapCases=127, Skipped=0, Failed=0, Errors=0`.
Raw JUnit and admission evidence remains in `.tmp/maps-oracle/`.

The exact requirements test file written in this task ran via
`uv run --frozen pytest tests/test_requirements.py --strict-markers -q`:
`91 passed in 0.46s`. Other repository quality gates remain for PR CI.
