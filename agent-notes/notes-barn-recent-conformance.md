# Recent Barn conformance capture checkpoint

## Objective

Capture externally visible Barn behavior repaired during roughly 2026-08-04 through 2026-08-10 as portable conformance tests, accepting only cases proven against managed WSL Toast.

## Current state

- Working branch is `main` at `71e2ba2`; the checkout already contains a large set of unrelated untracked notes, logs, prompts, reports, and scratch files. No tracked changes were present at inventory time.
- Barn `origin/master` contains a dense recent repair campaign. Existing conformance coverage already includes nested `try`/`finally`, parser nesting liveness, bcrypt prefix/high-byte semantics, shutdown/anonymous GC fixtures, optional `finished_tasks()` permissions, integer literal overflow, and several scheduler/connection oracle cases.
- High-value, externally observable candidates not yet found as literal focused coverage include:
  - `rmatch()` rightmost/overlapping/empty/capture semantics (#55)
  - `unique()` equality semantics, including case folding, signed zero, nested collections, and distinct NaNs (#56)
  - `random(min,max)` across overflow-width integer ranges (#15)
  - `exec()` documented three-argument stdin and isolated environment behavior (#47/#53), profile permitting
  - caught `E_MAXREC` activation-frame cleanup (#17)
  - large (>64 KiB bytecode) `try`/`except`, `try`/`finally`, loops, and fork bodies (#69/#70)
  - object-bounded `for` ranges (#21)
  - built-in property write permission enforcement (#13)
  - `mapdelete()` map-limit rather than list-limit enforcement (#49), if dynamic limits can be expressed portably
  - `decode_binary()` and hash/HMAC result-limit enforcement (#71/#73), if dynamic limits can be expressed portably
  - FIFO handoff among multiple `read()` tasks (#76), likely requiring multi-connection orchestration
- Current tracked/untracked deliverable edits now include focused cases for:
  - `rmatch()` rightmost, overlap, empty, capture-offset, anchor, and alternation semantics
  - wide `random(min,max)` ranges
  - object-bounded and scalar-ceiling `for` ranges
  - multibyte string iteration assembled from raw bytes
  - three-argument `exec()` stdin and environment behavior using managed fixtures
  - regular-object built-in privilege flag write protection
  - caught-`E_MAXREC` activation-frame cleanup
  - static property/verb names beyond constant index 255
  - hash/HMAC exemption from `max_string_concat`
  - concurrent immutable-list frontier appends from forked tasks
  - >64 KiB try/except, try/finally, while-loop, and fork address/range behavior
  - FIFO input handoff between multiple tasks blocked in `read()` (under oracle revision)
- Internal-only or non-semantic changes (module/package renames, caches, locks, snapshot implementation, fd backoff, fsync mechanics) should not receive superficial MOO rows unless an actual observable contract can be isolated.

## Observations

- Barn unit tests are the best source for regression shapes; Toast remains the semantic authority.
- Managed Toast must run through WSL `/root/src/toaststunt/build-release/moo` and focused packaged selections must include `capability_admission`.
- `uv` on Windows currently errors while trying to remove `.venv/lib64`; run the oracle command inside WSL as documented instead of treating that Windows environment failure as semantic evidence.
- The current conformance checkout has a very noisy untracked worktree, so all edits and any eventual staging must use exact paths.
- Existing coverage is broader than filename-level searches first suggested:
  - `match_rmatch.yaml` covers basic reverse matching but not the repaired overlapping, empty, suffix-anchor, alternation, and capture-offset cases.
  - `looping.yaml` covers ASCII string iteration but not multibyte byte iteration.
  - `limits.yaml` already has both grouped and fully-numeric `decode_binary()` list-limit cases, so #71 does not need a duplicate row.
  - anonymous-object built-in flag permissions are covered, but regular-object built-in property write protection still merits a direct case for #13.
  - existing scheduler audit coverage includes `read()` lifecycle behavior but no obvious two-reader FIFO handoff row for #76.
- A material conflict needs Toast adjudication: `server/limits.yaml::mapdelete_uses_list_not_map_max_value_bytes` expects `E_QUOTA` when only the list byte limit is low, while Barn #49 deliberately changed `mapdelete()` to enforce the map limit independently. The existing row predates that repair and cannot be treated as authority merely because it exists.
- Hash/HMAC #73 was resolved by documenting and preserving Toast's exemption from `max_string_concat`, not by enforcing that limit. Focused conformance should assert the exemption if it is not already covered.
- `exec.yaml` has two-argument stdin coverage but not the documented three-argument stdin path or custom environment isolation. Managed executable fixtures make both observable and portable.
- The static-name constant-255 defect (#39) can be observed by generating a verb containing 255/256 distinct static property/verb names and executing the boundary operation; the existing suite has no such row.
- Managed Toast adjudication is now conclusive for `mapdelete()`: the existing list-limit row passed with capability admission, so Barn #49 is a real Toast incompatibility rather than a policy divergence.
- First new-case Toast run: 14 passed, 2 failed, 8 capability-skipped, 11,609 deselected.
  - Rightmost repeated/overlapping/capture/empty/alternation `rmatch`, all three wide-random cases, and all five object-range cases passed.
  - Toast returned `[1, 1, ...]` for `rmatch("abc", "^.")`, not Barn's new regression test expectation `[3, 3, ...]`. Barn's optimized `rmatch()` preserved a Barn-only suffix-relative anchor behavior and is currently incompatible with Toast on this case. The conformance expectation has been corrected to Toast.
  - A raw Unicode source literal produced `[0, 0]` through the Toast command parser. The portable test now constructs UTF-8 bytes with `tostr(chr(195), chr(169))` before comparing `length()` with iteration count.
  - Stock Toast has no `unique()` builtin in source, so `unique()` rows were removed rather than counting requirement skips as proof.
  - Toast source does register `exec()` but the old `server/exec.yaml` suite is hidden behind stale broad feature requirements. The two recent exec cases were moved to a focused managed-server suite requiring only the actual builtin and managed fixture support.
- Second Toast run passed all 11 selected cases: corrected rmatch anchor, byte-built multibyte iteration, two regular-object privilege writes, caught-E_MAXREC frame cleanup, both exec regressions, and three static-name boundary operations.
- Third Toast run passed capability admission plus hash/HMAC limit exemption and 20 synchronized shared-list frontier append attempts (3/3).
- Fourth Toast run passed capability admission plus all four >64 KiB bytecode cases (5/5).
- The FIFO handoff probe also timed out against Toast when moved to a separate negative connection, so it was removed rather than accepted without oracle proof.
- A current-tree Barn managed run selected 31 cases: 16 passed and 15 failed. Three failures are confirmed semantic incompatibilities: anchored `rmatch()` returns the suffix-relative `[3, 3]` instead of Toast's subject-relative `[1, 1]`; multibyte iteration reports one character rather than Toast's two UTF-8 bytes; and `mapdelete()` ignores Toast's list-value byte limit. The 64-bit cases were skipped because that first command did not emit a managed profile manifest, while the seven compiler-boundary failures returned `E_QUOTA` because the focused fixtures had not declared a sufficient list-value budget.
- `static_name_boundaries.yaml` now declares foreground tick/time and list-value budgets; `wide_control_flow.yaml` now also declares a list-value budget. Managed WSL Toast re-accepted capability admission plus all seven adjusted compiler-boundary rows: 8/8 passed in 151.45 seconds.
- A manifest-backed Barn rerun executed 44 broadly matched cases: 29 passed, 5 capability-skipped, and 10 failed. The expected anchored-`rmatch`, multibyte-iteration, and existing `mapdelete` incompatibilities remained. The seven later `E_QUOTA` results were contamination: because Barn's `mapdelete` unexpectedly succeeded, its low list-limit mutation committed; Toast's expected exception rolls that task back. A fresh Barn run excluding that known-failing row passed capability admission plus all seven compiler-boundary cases (8/8 in 190.12 seconds). The 64-bit random/range rows also executed successfully once Barn emitted its profile manifest.
- Final static authority is green in WSL: 95/95 schema, duplicate-linter, and builtin-coverage tests; the checked-in duplicate baseline matched exactly (503 YAML files, 4,571 tests; 45 name groups and 28 content groups); `git diff --check` is clean.
- The first broad Toast attempt selected all conformance but correctly failed closed because admission was excluded. The next attempt included admission and reached 84% with 9,693 passes before exposing an incorrect `--server-db-dir` pointing at Toast source fixtures. With the canonical packaged startup fixture directory, the complete managed WSL Toast gate passed: 11,209 passed, 431 declared skips, zero failures in 455.77 seconds.
- The first FIFO `read()` probe against the active authenticated harness connection failed Toast with E_INVARG. It was not accepted. The revised probe uses a separate live negative connection, matching already-proven `read(connection)` and `force_input(connection, ...)` suite patterns, and its oracle rerun is active.
- Static authority tests are green: 95/95 across schema, duplicate-linter unit tests, and builtin coverage tests. Direct whole-tree duplicate lint reports 45 name groups and 28 content groups already present in the baseline; the authoritative command needs `--baseline ci/duplicate-baseline.json` before judging the new delta.
- Barn checkout state changed externally during this task to branch `agent/issue-27-concurrent-list-append` at `97f05d0`; it has no tracked dirt. Before target verification, compare its tree to `origin/master` and avoid overwriting the user's existing `barn.exe` (dated 2026-08-08).

## Blocker

No external blocker. Final worktree/scope audit remains; the three confirmed current Barn incompatibilities should be reported without changing Barn in this repository task.

## Next action

Audit the exact changed paths against the user's requested conformance-only scope, confirm no unrelated dirt is staged or modified, then hand off the accepted tests and the three current Barn incompatibilities.
