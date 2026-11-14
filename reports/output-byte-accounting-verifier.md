# Output byte accounting conformance final verification

## State

Final verification is complete for actual open moo-conformance-tests PR #177.
The assigned published head is the review target. Untracked capacity/file-scan
experiments and uncommitted task-note/report changes are excluded.

The verifier checked published YAML measurement/framing/restoration, analyst
findings, dependency merge, exact-head terminal CI and live review state.
No source edit, local broad test, publication or merge was performed.

## Source and dependency findings

No concrete defect found. Each case uses one statement program, and the runner
passes that complete program to transport.execute once. Socket transport flattens
it into one eval command. Baseline and observed values therefore occur in the
same task with no suspending primitive between them. The newline-free cases
save the result before sending their final empty notification. The binary case
uses decoded ASCII AB, restores the prior binary option through finally, then
terminates the output line. Its getter uses the canonical connection_options.
No optional requirement can hide a core builtin misspelling as a skip.

Expected results distinguish payload plus CRLF, unframed payload, accumulation
and decoded binary bytes. The analyst has no unresolved actionable finding.
Capacity/refusal and file-scan experiments are not in the published YAML diff.

Live dependency output:

```text
Barn PR #636 state: MERGED
mergedAt: 2026-11-07T09:50:03Z
```

## Terminal CI and review evidence

The live PR head matches the assigned review head. Relevant raw checks:

```text
Toast / 32bit-outbound-on: pass (13m13s)
Toast / 64bit-outbound-off: pass (13m24s)
Toast / 64bit-outbound-on: pass (13m4s)
Trusted controller validation: pass (1m11s)
Harness, schema, duplicates, types, and lint: pass
Full suite: pass
Report required checks on exact PR head: pass (4s)
mergeStateStatus: CLEAN
mergeable: MERGEABLE
reviews.nodes: []
reviewThreads.nodes: []
```

Both untrusted-controller branches are skipped while the trusted-controller
validation and all three actual Toast profiles succeeded. All checks are
terminal; no failure or pending check remains.

## Verdict: MERGE

The four cases exercise the confirmed observable contract through the existing
harness and preserve line framing and binary option cleanup. The Barn dependency
is merged. Exact-head controller, quality, three-profile full-suite and required
status reporting checks pass, with no unresolved review. This verdict applies
only to PR #177. No runtime performance claim is made.
