# Output byte conformance analyst review

## Scope and state

Reviewing actual open companion PR #177, Verify queued connection output byte
counts. Published changes are one four-case YAML suite and its task note.
The local HEAD matches the assigned published head. Untracked capacity and
file-scan suites are excluded and preserved. No source edits, local tests or
publication performed.

## Findings so far

No concrete defect found in the four published cases. They save a baseline and
measure deltas within one MOO statement program. The binary case restores the
prior connection option through finally. Unframed cases save the measurement
before issuing an empty text notification to complete result line framing.
No optional-builtin prerequisite can mask a misspelled core builtin as skips.

## Completed source and evidence inspection

`schema.py:527-561` selects statement mode and preserves the complete program.
`runner.py:475-497` builds that program and invokes transport.execute once per
case. `transport.py:389-408` flattens physical lines into one eval command;
these measurements are not separate requests with a network drain between
the baseline and observed values. The programs call no suspending primitive.

The unframed text and binary cases store observed before the final empty text
notification. Binary output uses decoded ASCII AB, and its prior option is
restored in finally before the text terminator. This is compatible with the
existing receive path's UTF-8 line decoding and final-result/notification split
(`transport.py:520-610`). The expected list checks run only for successful
results; a compile/runtime error cannot satisfy them (`runner.py:1450-1490`).
All four cases require wizard execution and use the canonical plural
connection_options getter. No skip or optional requirement is declared.

Read the managed XML artifacts directly from the Barn worktree. Each contains
capability_admission and these exact four test names:

```text
toast-byte-v2.xml: tests=5 failures=0 errors=0 skipped=0
barn-byte-before.xml: tests=5 failures=4 errors=0 skipped=0
barn-byte-after.xml: tests=5 failures=0 errors=0 skipped=0
```

The old-Barn failures have these expected/actual pairs:

```text
CRLF: [1,5] / [1,1]
no newline: [1,3] / [1,1]
accumulation: [1,1,3,7] / [1,1,1,2]
decoded binary: [1,2] / [1,1]
```

Thus the cases distinguish byte accounting from notification counts and have
observed oracle and corrected-Barn successes. They make no assertion about
queue refusal, capacity, physical write progress or a slow peer. The separate
untracked capacity/file-scan suites are not part of this published diff.

## Bounded verdict and remaining unknowns

No actionable defect found in the published suite. This is a source/evidence
analyst result, not merge approval. At the last live PR check snapshot:

```text
Trusted controller validation: pending
Classify trusted controller and candidate data boundary: pass (12s)
Report trusted conclusion on exact PR head: pass (4s)
Trusted PR head status probe: pass
Untrusted candidate controller suite/quality: skipping
```

The four measured cases themselves have zero skips in all three inspected
managed captures. Full PR CI remains pending at this snapshot. Commit-hook
results were supplied by the coordinator and were not rerun or independently
verified by this analyst.
