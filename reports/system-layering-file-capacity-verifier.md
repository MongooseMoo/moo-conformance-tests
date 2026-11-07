# File cursor and output capacity final verification

## Goal and state

Final gate for the actual open PR 178. The live published head matches the
assigned head and the PR is ready for review. Default verdict remains NO-MERGE
while terminal checks and source evidence are inspected. No source changes,
local runs, posting or merge are authorized for this verifier.

The requested legacy gauntlet role entrypoint is absent. The installed gauntlet
skill was resolved from its advertised root and will supply the role protocol.
Existing modified phase note, analyst report and untracked no_flush/width probes
belong to the coordinator and are preserved.

## Initial live evidence

```text
PR 178: OPEN, isDraft=false, mergeable=MERGEABLE, mergeStateStatus=BLOCKED
reviews=[]
Barn 639: MERGED, mergedAt=2026-11-07T11:21:06Z
```

The Barn dependency hold is satisfied. Terminal profile evidence establishes a
fixture leak, so the verdict is NO-MERGE until repaired and reverified.

## Published source inspection

Read the actual open PR diff, analyst report, suite programs, schema, production
test dispatch and runner lifecycle. Capacity cases preserve property presence and
value in MOO finally blocks and reload after restoration. File cases retain their
intended cursor/count/match/long-line assertions and close acquired handles.
The file_open optional feature guard is legitimate. No unresolved no_flush or
stock-width research probe is included in the published diff. Older PR 177
reports were not re-reviewed as code changes.

## Terminal failure inventory and raw evidence

The exact-head watcher completed with required failures. Downloaded all three
original profile artifacts from run 42367140692 into
.tmp/pr178-failure/{profile}/. Each retains original XML, conformance log,
admission XML/JSON/log, profile, provenance and workflow context.

```text
Toast / 64bit-outbound-on: fail 13m15s
  tests13779 failures6 errors0 skipped30
Toast / 64bit-outbound-off: fail 12m58s
  tests13779 failures6 errors0 skipped45
Toast / 32bit-outbound-on: fail 13m00s
  tests13779 failures6 errors0 skipped52
Each profile's six new file/capacity cases: failures0 errors0 skipped0
Trusted controller validation: pass49s
Harness, schema, duplicates, types, and lint: pass3s
Full suite: fail
```

All three profiles have exactly the same six failures, all in the pre-existing
file_stat_call_shapes suite: file_list_detail_flag_type_float, obj, str, err,
list and map. Each expects an empty root directory. Actual values are either
['__file_scan_cursor.txt'] or [['__file_scan_cursor.txt','reg','644',19]].
There are no other failed cases or errors in any profile. The six new cases
themselves pass; this does not excuse their contamination of later tests.

CI provenance names the selected and actual Toast revision identically. That
revision differs from the earlier canonical WSL captures, so this report does
not claim they ran the same executable. The failure values themselves identify
the newly created file; a version-drift explanation is unnecessary and unproved.

## Proven fixture lifecycle defect

file_scan_cursor.yaml creates __file_scan_cursor.txt in suite setup and declares
suite teardown to remove it. runner.py:220-250 executes setup once and caches its
suite name. test_conformance.py:394-397 calls that setup and run_test only.
plugin.py:446-459 returns one session-scoped runner and registers no teardown
finalizer. A repository-wide Python search finds run_suite_teardown only at its
definition (runner.py:431) and one unit-test invocation. The production pytest
path never calls it. Therefore the suite cleanup declaration does not remove
the file before the following root-list assertions.

This is a real producer and exact raw input/output failure, not an inferred
flake. No CI retry or source edit was performed by this verifier.

## Smallest bounded correction

Remove the newly introduced suite-persistent fixture. Use existing per-test
setup and teardown on the first three cases, sharing each block once through
YAML anchors and aliases. Keep the one-physical-line file creation program and
its MOO finally close. Keep the existing scan statement finally close. The long
case already removes its own file in finally and needs no lifecycle change.

runner.py:475-491 combines test.setup.code_lines and statement into one execution;
runner.py:505-509 runs per-test teardown in Python finally even if assertions
fail, provided the server is alive. Thus the proposed anchors have a real cleanup
caller, unlike suite teardown. No harness redesign or weakening of the existing
empty-root file_list assertions is needed for this bounded correction.

Parent will apply and verify the correction using the exact new suites followed
by the existing file-stat cases, then new exact-head full profile CI. The current
head remains NO-MERGE. No local execution, publication or merge was performed.
