# MOO output capacity, byte accounting and file scans

## Goal

Resolve I/O contracts for Q's approved Barn system-layering plan using the
canonical managed WSL Toast oracle before changing Barn behavior.

## State

Four candidate cases record notify acceptance and same-task output-byte deltas:
CRLF framing, no-newline framing, accumulation and decoded binary output.
Expected values are derived from the inspected stock Toast enqueue_output and
buffered-output-length source. The first managed session passed admission but
skipped all four cases because the suite's optional prerequisite incorrectly
named Barn's singular connection_option getter. This establishes no behavioral
verdict. The corrected candidate uses canonical connection_options and has no
optional-builtin prerequisite that could hide a misspelled core name as skips.
The failed observation remains in the Barn worktree's toast-byte.xml.
The corrected managed stock oracle run completed with five passes and zero
failures/errors/skips, including admission. The same suite on Barn completed
with admission passing and all four behavior cases failing: it returns counts
of notifications rather than the required byte deltas. Raw results remain in
the Barn worktree's .tmp/system-layering/toast-byte-v2.xml and
barn-byte-before.xml, with their admission JSON evidence.
After the byte correction, the same managed Barn cases passed with admission
and zero skips. Barn PR #636 merged on November 7 after full PR CI and review;
the generic byte suite can now publish independently against main.

Three additional acceptance/capacity cases plus admission passed on stock
Toast. They establish live max_queued_output reload, positive minimum 2048,
preservation of zero/negative limits, invalid-type default 65536, and real
no_flush rejection after existing queued output. The first two failed on the
frozen Barn candidate: capacity remains 65536 and notify returns 1 instead of
0. Raw evidence is in the Barn worktree's toast-acceptance-v2.xml and
barn-acceptance-before.xml with matching admission evidence. The no_flush refusal case remains local because its Barn implementation is not
repaired. Capacity and file scans have verified corrections in Barn PR #639;
the companion PR may run CI but must not merge before that dependency.

## Decisions and why

The same MOO task observes before/after values so network-loop draining cannot
make the delta depend on peer timing. No full-queue or slow-socket claim is made
by these byte-accounting cases. Binary mode is restored in finally. A final
empty text notification terminates a no-newline payload only after the measured
delta is saved, preserving the eval transport's line framing. The escaped
binary payload decodes to ASCII bytes so this byte-count test does not feed
invalid UTF-8 into the existing text result parser.

Generic MOO behavior belongs in this companion repository; Barn regressions
will follow only after the oracle result. Keep the suite independent of Barn
implementation details and include capability_admission in each managed run.

## Surprises

The singular getter is not a registered stock Toast builtin. Stock server.cc
registers connection_options; the existing companion call-shape suite uses it.
The initial requires guard turned that wrong input name into four skips.

## Next step

Byte suite PR #177 merged after multi-profile Toast CI and final review, then
the local checkout fast-forwarded to main. Publish the verified capacity and
file-scan suites as a separate dependent PR; hold its merge until Barn PR #639
is merged. Keep no_flush refusal and the stock-64-only width probe local;
neither belongs in this generic change.
The first candidate file_scan_cursor run passed admission but all three scan
cases observed an empty file. This is a failed fixture observation, not a cursor
behavior verdict. Preserve toast-file-scan.xml and inspect the actual setup
execution and stock file-mode source before correcting or rerunning it.
Source confirmed suite setup splits physical lines and ignores each failure.
The corrected one-program setup passed all scan cases plus admission on stock
Toast. Barn's same managed cases pass count/all-match but first-match grep raises
E_FILE when the next file_readline should return omega. Preserve
barn-file-scan-before.xml: this is a confirmed cursor correctness defect.
An additional managed stock case confirmed 65536-byte lines are accepted by
count and grep, including the exact first-match cursor and following line.
toast-file-scan-v3.xml reports five passes including admission. Do not preserve
Barn's accidental Scanner token-size limit as a language contract.
