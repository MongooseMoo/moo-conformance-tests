# Startup database object labels

## Goal
Conformance coverage for how Toast places numbered object records at load:
from DBV_NextGen (v5) on, ng_read_object ignores the `#N` label and takes the
next slot; v4_read_object rejects a label that is not last-used + 1 and the
server exits 1. Pairs with Barn PR #624 (Barn merges first).

## State
Worktree created from origin/main. Writing two startup fixtures
(V5MismatchedLabel.db, V4MismatchedLabel.db) and one suite.

## Decisions and why
- Toast source read: db_file.cc v4_read_object (line 231), ng_read_object
  (304-326), read_db_file caller (925-935), db_load (1248-1249),
  server.cc:2304-2305 exit(1); version.h DBV_NextGen is enum value 5.
- The loadable case runs #0:server_started, which server_logs what loaded and
  calls shutdown(), so the suite needs no transport (runner.py starts such
  suites with wait_for_port=False and wait_for_server_exit observes the exit).
- Fixtures are hand-written and minimal so the only defect is the label.

## Surprises

## Runs
Toast oracle run 1 (from barn-fuzz-db-reader: `make conformance-toast
CONFORMANCE_SUITE=/mnt/c/Users/Q/code/mct-db-object-labels
K=startup_object_label CONFORMANCE_ARGS=-v` in WSL Debian): 3 passed
(capability_admission + both suites), 279 s.
Toast oracle runs 2 and 3 (same command, -rA): 3 passed each (338 s, 244 s).
Barn master before PR #624 (origin/master 9970fadd, `make conformance-k
CONFORMANCE_SUITE=... K=startup_object_label`): v4 FAILED "Server did not exit
naturally within 5000 ms" (Barn loaded the bad label); v5 FAILED, probe line
absent from the log.
Barn test/fuzz-db-reader (PR #624 content, since merged): v5 PASSED; v4 FAILED
only on assert_log "READ_DB_FILE: Bad object #2." (wait_for_server_exit
exit_code 1 passed). Barn logs `Barn failed err="load database: ... object
record 2 has ID #9"` (cmd/barn/main.go). Toast's text is db_file.cc:920
`errlog("READ_DB_FILE: Bad object #%" PRIdN ".\n", i - 1)` in the v4 loop (926
ng loop, 945 anonymous loop). The suite stays as Toast passes it; Barn needs
that wording (pending coordinator).

Barn fix/db-v4-bad-object-wording (logs Toast's "READ_DB_FILE: Bad object
#%d." for a v4 label mismatch), same `make conformance-k` selection: 3 passed.
Toast oracle run 4 (`make conformance-toast`, same selection): 3 passed.

## State (2026-11-07)
Fixtures, manifest lines and both suites committed; PR open.

## Next step
Merge after the Barn PR for fix/db-v4-bad-object-wording merges.
