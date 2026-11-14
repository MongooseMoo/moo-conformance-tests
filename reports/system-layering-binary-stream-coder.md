# Binary input fixture repair

## Goal and state

Repair the existing newline-free binary-input conformance case so its assertion
does not require one TCP write to become one command input chunk. Preserve the
original eight input bytes and the real binary-dispatch contract.

The existing case now observes raw command bytes through the existing hook.
Focused managed Toast and Barn selections each pass two tests with admission;
each complete surrounding gap suite passes eighteen tests. All four XML captures
report zero failures, errors and skips. Parent owns publication. Other worktrees
and unrelated files are outside this worker's scope.

## Evidence in progress

Read the actual case, canonical controlled-split negative witness and passing
raw-command capture. Original CI packetization remains unknown. The old native
verb observer requires the name auditbin to arrive in one command chunk. The
new observer filters to its test player and concatenates the delivered argstr
chunks, preserving the exact eight-byte auditbin/no-newline assertion.

Setup now returns an asserted one. The secondary connection's welcome login
is observed through connected_players before enabling binary mode; membership
and the binary option are both asserted. Removed the redundant textual login
command and two fixed sleeps. Completion polls the test-owned received string
for at most one hundred suspension intervals, then asserts exact content.

One loop saves each do_login_command and do_command hook's metadata, argument
spec, code and existence before modifying that hook; cleanup restores each saved
record or deletes a previously absent verb. Existing best-effort cleanup resets
the temporary player's mode, boots/recycles it and removes the owned properties.
The harness runs test cleanup in its existing Python finally path.

Raw repair evidence is preserved in the checkpoint worktree:
.tmp/toast-binary-stream-repair.xml and .tmp/barn-binary-stream-repair.xml,
each with its separately named admission JSON. Both focused runs report two
passes, sixteen deselected and zero failures or skips. The complete surrounding
gap suite passes eighteen cases with zero skips on Toast in 34.56 seconds and
Barn in 36.32 seconds. Corresponding raw files are
.tmp/toast-binary-stream-gap-repair.xml and
.tmp/barn-binary-stream-gap-repair.xml, with separately named admission evidence.
The warning concerns record_property with xunit2, not a behavior failure.

All four commands use the verified Debian distribution, the platform-specific
Linux uv environment, uv run --project this independent checkout --frozen
moo-conformance, the packaged gap suite, bundled Test.db/startup, strict markers
and fail-on-unexpected-skip. Focused runs select capability_admission plus the
existing case; complete runs select admission or conformance without -k.
Toast uses the stock manifest as both oracle and target. Barn uses the preserved
checkpoint-verifier executable with outbound-on config and generated target
manifest. No manual server or direct pytest command ran.

Final diff is limited to this one existing YAML case, the living note and this
report. git diff --check returns zero. No broad Go tests or builds ran. Hook
restoration is source-audited and the surrounding suite passes; no separate
fault-injection assertion proves every partial-setup cleanup branch.

## Next step

The bounded change and evidence are ready for parent review/publication. No
commit, push, review, CI retry or merge ran. Original failed CI packetization
remains unknown; its invalid boundary assumption has a separate canonical
negative witness and is removed from the corrected observation.
