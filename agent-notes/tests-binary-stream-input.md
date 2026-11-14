# Binary stream input conformance repair

## Goal

Preserve the existing binary dispatch assertion without assuming TCP read/write
boundaries match. Change only its test fixture and observation.

## State

The existing case uses the planned raw-byte observer, exact unsplit payload,
asserted setup/mode and bounded completion value. Managed Toast and preserved
Barn each pass the focused two-test selection, including admission, and the
complete eighteen-test surrounding gap suite. Raw XML/admission evidence lives
in the checkpoint worktree .tmp/{toast,barn}-binary-stream-{repair,gap-repair}
files. All four XML captures report zero failures, errors and skips. No
publication or merge occurred. Final diff checking returns zero.

## Decisions and why

Keep the original unsplit eight-byte payload, capture test-player raw command
chunks in do_command, and assert their concatenation. Assert setup/login/mode
before input and observe a bounded completion value. Restore hook metadata,
code and existence on cleanup. Use no new runtime layer or dependency.

## Surprises

Canonical Toast reproduces the original failed assertion when the valid TCP
producer splits the payload. That does not establish original CI packetization.

## Next step

The bounded change and reports are ready for independent review and exact-head
complete CI. Parent owns publication and merge. No checkpoint or runtime
implementation change is justified by the test's demonstrated boundary defect.
