# MCT 180 required Toast profile failure investigation

## Goal and state

Investigate required run 42388897437 without changing tests or production code.
The required 64bit-outbound-on profile failed; two other required profiles and
all three informational candidate-controller profiles passed. Cause unknown.

## Facts

- The completed run has a retained toast-conformance-64bit-outbound-on artifact.
- Quality gates passed. Failure is not yet attributed to CLI code or timing.

Raw required profile summary:

```text
3 failed, 13746 passed, 30 skipped, 1 deselected in 733.44s
admission schema_version=2; all four probes passed
```

All three failures are in builtins/move_hooks_toast_oracle.yaml:

- move_calls_accept_exitfunc_enterfunc_with_post_move_state: socket recv timeout;
  server log since test start empty; testcase duration 8.582 seconds.
- move_same_location_and_reorder_skip_lifecycle_callbacks: E_VARNF; 0.002s.
- move_exitfunc_relocation_skips_original_destination_enterfunc: E_VARNF; 0.002s.

The previous case is the command-dispatch/suspending-enterfunc case in
move_hooks_suspend_toast_oracle.yaml. It passed in 0.744 seconds. Its cleanup
removes the do_command hook and player test verbs, then recycles its room.
The following ordinary move-invalid-argument cases resumed passing.

The required lane runs the base trusted controller through pytest directly,
so the changed candidate cli.py is not executed in this lane. Candidate data is
unchanged by this PR. This rules out the new option-token code as the direct
producer of the required failure, but does not establish a transient cause.

## Theories

1. A predecessor leaves command lifecycle or response framing unsettled.
2. A host/socket delay times out the first case; shared framing then misattributes
   its late output to the next two cases.
3. A deterministic move fixture defect depends on prior shared world state.

No theory is established by the retained XML alone. The original artifact does
not include wire bytes or server process logs, only the timeout log excerpt.

## Probe result

Run both consecutive move-hook suites plus capability admission through the
managed canonical Debian Toast command. Output paths are .tmp/pr180-move-focused
XML and matching admission JSON. No production or test change is selected.

```text
collected 9 items
9 passed, 1 warning in 17.21s
XML: tests=9 failures=0 errors=0 skipped=0
```

The first formerly failed move case took 0.042 seconds, the next two 0.040 and
0.049 seconds. Its immediate predecessor took 0.784 seconds. Four admission
probes passed. This disproves a deterministic failure for this focused sequence
on the local canonical build, not a broader history-dependent failure.

The same-profile informational candidate-controller CI log says:

```text
13749 passed, 30 skipped, 1 deselected in 710.75s
```

Both CI lanes select pinned Toast revision eaaa1972f0993a1247f787dbf2dd5a01702ef442.
The candidate's data, transport.py and runner.py have no diff from the base.
The local canonical profile identifies a different build revision, so its pass
does not establish exact CI binary equivalence.

## Primary-source limits

Python's socket documentation explains timeout as an operation not completing
within the socket's interval; it does not prove command loss, server stall or
absence of late response:
https://docs.python.org/3/library/socket.html#notes-on-socket-timeouts

Toast's changelog includes historical DNS stalls and delayed TLS input, but no
retained evidence connects those incidents to this plain-socket case:
https://github.com/lisdude/toaststunt/blob/master/docs/ChangeLog.md

The current harness keeps the same socket after a timeout and runs teardown
through execute in finally (runner.py 499-510). Response parsing uses no request
identity and starts a fresh local receive buffer per execute (transport.py
521-563). This supports possible late-frame misattribution, but missing original
wire bytes prevent establishing it as the cause of the two E_VARNF outcomes.

## Preserved evidence

Original artifact directory: .tmp/pr180-failed-64on (all 16 files retained).

```text
toast-conformance.xml SHA256 B4044B48038B4CDD126609458A1D0FF40383217A7F6B73FAD29B99E419024543
admission.json SHA256 3ECB936132EB8390E9BF50069DA56D4F7FBE047E89889A1D4F208316D6A286B4
```

The focused XML/admission files remain private under .tmp/pr180-move-focused*.

## Next step

Actual required failure cause remains unknown. No test weakening, timeout
increase or implementation repair is earned. A targeted failed-job repeat could
measure recurrence at the exact CI profile, but would be another experiment,
not a diagnosed transient recovery or proof that the failure is fixed. Parent
has this distinction and selected a controlled recurrence probe:
`gh run rerun 42388897437 --repo MongooseMoo/moo-conformance-tests --failed`.
Root owns invoking and evaluating that probe. Its output must use a separately
named directory, preserving the original .tmp/pr180-failed-64on capture. A pass
will establish nonrecurrence in that run, not identify the original cause.
No source/test change or publication performed by this investigator.
