# Additional semantic tests, September 26

- User clarified this means 1,000 NEW tests beyond the old PR #82; do not count that campaign. Baseline `76f3d226`: 13,080 cases / 530 YAML files.
- Isolated worktree `C:/Users/Q/code/moo-conformance-semantic-edges`, branch `tests/semantic-edges-20260926`; new generator plus four YAML files total 1,095 tests (324 scatter, 432 nested range writes, 264 lazy effects, 75 finally transfers).
- All four focused managed WSL Toast runs passed with zero skips/failures, following fresh canonical admission. Native copy `/tmp/moo-semantic-edges-20260926`, evidence under `evidence/`; runner in worktree `.tmp/run-oracle.sh`.
- No blocker. User authorizes schema/new primitive improvements if needed. Current cases use existing statement/expect support.
- Next: inventory/coverage ledger, exact duplicate and identity audit, generator formatting/static checks, full managed Toast suite, final review. Nothing committed or published yet; original workspace preserved.

- All 1,095 new bodies are unique and absent from both committed baseline (13,080 cases) and original workspace including untracked YAML (13,103 cases / 539 files).
- Strengthened the 75 finally cases to observe a temporary object's post-call trace as well as returned snapshots; all 75 pass again. Other focused families remain 324/432/264 passing, no skips.
- Quality: 530 harness tests pass / 1 platform skip; generator unit rerun passes; Ruff/MyPy/drift/duplicate baseline pass. Controller-only local commit `210377d` contains generator and its unit test; data/docs still uncommitted.
- Full run hit 8 existing-case failures and a Toast panic, aborting at 13,464 pass / 410 skip. Baseline-only replay (session 70888) is live; do not claim baseline reproduction until it finishes. All evidence in native `/tmp/moo-semantic-edges-20260926/evidence` and worktree `.tmp/evidence`.
- Next: finish control replay, summarize baseline limitations truthfully, refresh identity audit and evidence, commit only four new YAMLs plus coverage doc, complete goal if all new-case requirements remain proven. No pushes/PRs requested.

- Baseline replay completed: 12,369 passed / 410 skipped / same 8 failures and panic; both broad runs leave 293 baseline cases unexecuted. Exact failure identities compared in `.tmp/evidence/full-baseline-comparison.json`.
- Final strengthened 75-case run passes; all four delivered YAML hashes match focused JUnit identity audit, totaling 1,095 current new passes with zero skips/errors/failures.
- Local data/docs commit `8773f1c` follows controller commit `210377d`; pre-commit duplicate and profile-contract guards passed. Branch `tests/semantic-edges-20260926`; no push or PR.
- Seven added tracked paths only; scratch evidence is untracked under isolated worktree `.tmp/`. Original repository tracked files remain unchanged.
- Completion audit: at least 1,000 additional useful tests, inventory of committed and untracked existing coverage, unique new bodies, current Toast proof, and coverage/verification documentation are satisfied. Existing full-suite failures remain explicitly reported; no all-green full-suite claim.

- User rejected the completion claim: ZERO FAILURES ARE EXPECTED. Goal reopened; earlier acceptance of eight failures is invalid.
- Root cause verified: local oracle was `aecc51e9`, but CI pins `eaaa1972f0993a1247f787dbf2dd5a01702ef442`. Baseline CI run `36292503398` is green on exact `76f3d226`; profile pass counts 13050/13033/13028, no failures.
- Built clean pinned source in `/tmp/semantic-edges-ci-toast`, with CI's Ninja/Release/Jemalloc/BACKGROUND_TEST/SAVE_FINISHED_TASKS flags, builds `/tmp/semantic-edges-ci-build64` and `...build32`. Both builds exited 0.
- Full pinned-profile runs now live: 64bit-on session 34829, 64bit-off 21367, 32bit-on 78306. Runner: worktree `.tmp/run-ci-profile.sh`; logs/evidence: native `evidence/ci-<profile>/`.
- Next: wait for all full runs, resolve any failure without waivers, run paired_inventory/execution_ledger exact union, correct report and commit documentation. Do not complete until zero failures on all CI profiles is proven.

- First correct-pin full runs: 64bit-on 14,145 passed / 30 declared skips, 64bit-off 14,128 / 47; both zero failures. 32bit-on has exactly 12 new-case failures (negative lower bound on string ranges), 14,111 passes / 52 skips.
- Source diagnosis: `EOP_RANGESET` compares `Num from` to `memo_strlen()+1`; cached length is `uint32_t`. With ONLY_32_BITS, negative Num converts to unsigned and raises E_RANGE; int64 comparison preserves the negative and clamps. List lengths remain signed on both profiles.
- Next fix: for those 12 cases, select exact source-derived expectations via advertised `server_version("options.ONLY_32_BITS")`, fail on unknown metadata, keep all cases active, then rerun all full profiles and exact ledger. Do not accept either result indiscriminately or skip cases.

- Correct native metadata API verified from `version.cc`: `server_version("options/ONLY_32_BITS")` returns `{0}` when defined and `#-1` when undefined. Generator rejects anything else and asserts each width's exact outcome; count stays 1,095 and no skips added.
- Smoke runs cover all 24 negative-start list/string cases: 24/24 passed on pinned 64-bit and 24/24 on pinned 32-bit, with zero skips/failures.
- Fresh final full runs active: 64bit-on session 22607; 64bit-off 92615; 32bit-on 85947. Output roots are now `evidence/ci-full-<profile>/`, preserving earlier failed attempts separately.
- Quality/inventory refresh session 3401; final auditor script worktree `.tmp/audit_ci.py` asserts 14,175 exact identities per profile, zero failures/errors, 1,095 new passes in each, and fresh admission. Run execution_ledger against all three final JUnits afterward.
- Generator, range YAML and report have uncommitted corrections. Finish full zero-failure gate, update audited hashes/evidence/report, commit corrections, then complete goal. Old local oracle runs cannot satisfy acceptance.

- Corrected generator committed locally as `34dc5ff`. Final full reruns completed with every new case passing, but one failure on each profile: existing `audit_anonymous_values_in_suspended_vm_survive_restart`, E_INVIND when reading its class after restart. Full counts 14144/14127/14122 passed, skips 30/47/52, one failure each; NOT accepted.
- That exact test passed alone (1/1) on pinned 64-bit Toast; no production/test changes have been made to address it yet. Hypothesis is stale checkpoint adoption; must verify, not waive.
- Read-only diagnostic plugin `.tmp/diagnostic_plugin.py` captures managed server log and DB files on failure. Audit-prefix diagnostic is session 32102; preceding-overdue-restart + anonymous pair is session 43588. Output dirs native `evidence/ci-prefix-64bit-outbound-on` and `ci-pair-64bit-outbound-on`.
- Next: inspect captured checkpoint evidence/failure, establish and fix cause, then full three-profile rerun plus exact ledger. Goal stays active with zero failures required.

- Concurrent audit prefixes passed on all three profiles; exact capability-provider plus audit prefix also passed 326/326 on 64-bit. No deterministic preceding-state failure reproduced.
- Prior error context is truncated entire run-step text, not proof of the precise failing MOO statement. E_INVIND location remains unproven.
- Preserve failed full evidence as ci-failed-*; repeat full profiles with read-only diagnostic plugin capturing managed log and DB at anonymous case.
- No baseline assertions or harness changed. Investigate actual full failure evidence before selecting a fix; zero failures required.
- Native root /tmp/moo-semantic-edges-20260926; runner worktree .tmp/run-ci-profile.sh now captures full-run diagnostics.

- Full diagnostic reruns launched: 64-bit outbound-on session 40166, outbound-off 1137, 32-bit outbound-on 60771.
- Reports reuse ci-full-* after copying failed evidence to ci-failed-*.
- Exact provider-prefix result: 326 passed, 13850 deselected, zero failures.
- Current task is identifying intermittent restart failure without waivers or speculative timing changes.
- Next inspect full-run diagnostic snapshots, then fix confirmed cause or validate all-profile completion and ledger.

- Anonymous restart case passed in all three full diagnostic reruns; log proves checkpoint finished before shutdown and reloaded regular plus anonymous objects. Prior failure cause remains unknown, not fixed or accepted.
- Full runs now near completion, sessions 40166/1137/60771; no reported failure yet. All assertions and baseline files unchanged.
- Corrected range YAML committed as 8dcee75; duplicate baseline and profile-contract precommit checks passed.
- Final audit script worktree .tmp/final-audit.sh runs canonical paired inventory, exact profile ledger, strict 1095-new-case audit, baseline body audit, and delivered/runtime byte match.
- Finish runs, execute audit, copy evidence, update report with actual counts and intermittent-failure limitation, commit report. Do not publish; goal still active.

- Final pinned full profiles all passed: 64-on 14145/30 skips, 64-off 14128/47 skips, 32-on 14123/52 skips; zero failures/errors and all 1095 additions pass without skips in each.
- Canonical paired inventory and ledger passed 14175/14175; strict audits confirm all 530 baseline YAML unchanged, 1095 unique new bodies, and delivered/runtime byte equality.
- Complete evidence copied to worktree .tmp/evidence, including ci-failed-* and final ci-full-* diagnostic snapshots. Earlier intermittent anonymous restart cause remains unresolved; no fix claimed.
- Report updated and committed as 49d41d4. Local branch tests/semantic-edges-20260926; no push or PR. Only .tmp and investigations remain untracked in isolated worktree.
- Objective achieved by current full zero-failure runs; report explicitly distinguishes local CI-equivalent verification from hosted CI and records prior intermittent failure limitation.

- User rejected unexplained failure/PR readiness; new active goal is root-cause investigation and correction, followed by full zero-failure profiles. No publication authorized.
- Diagnostic repeat plugin .tmp/restart_probe.py captured pre-restart DBs and pre-cleanup state. Unchanged anonymous case passed 50 iterations; shell wrapper exit was corrupted by editing its file while running, so use iteration markers/XML only for that diagnostic result.
- Controlled LD_PRELOAD fsync delay in checkpoint child reproduces missing completed checkpoint at restart; isolated case then hit BrokenPipe, not yet original E_INVIND. No production change made.
- Next controlled run preserves preceding overdue-restart checkpoint and delays only anonymous-case writer using a marker file. Session launched by ci-delayed-pair-red; inspect captured probes for exact missing object and E_INVIND.
- Original 1.5s wait plus silent fallback to input DB is a confirmed synchronization hazard; must connect reproduction to original symptom and then replace timing assumption with checkpoint evidence, without weakening semantic assertions.

- SHA audit confirms clean Toast eaaa1972, both exact binary hashes match failed reports; current remote conformance HEAD 1418def changes only unrelated threaded-builtins YAML since baseline.
- Controlled slow checkpointer (3s fsync delay) plus 2s scheduling gap after old checkpoint selection reproduces exact E_INVIND: class #15 invalid and property read fails. Probe evidence ci-delayed-gap-red-64bit-outbound-on. Earlier no-gap delays exposed inherited-listener bind failures, same premature-stop hazard.
- Added restart_server.checkpoint_timeout_ms optional schema/harness support: await fresh completed known output since test/launch boundary before adoption and stop, reject stale/partial output, fail deadline without stopping. Anonymous case uses 5000ms deadline instead of 1500ms sleep. Controlled identical green experiment passed 2/2.
- New regression tests first failed 3 tests, then 67 focused tests passed; full harness session 35524 pending. YAML/schema/harness/docs changes uncommitted, no publication.
- Full corrected profiles running 5563/31645/89857; 20 delayed-checkpoint repetitions 27027. Do not edit run-ci-profile.sh while these run. Next full results, audits (allow only explicit baseline test sync change), code review, docs, local commit.

- Identical controlled red/green proved stale adoption: old code E_INVIND with invalid class, new checkpoint deadline passes. Twenty repeated 3s delayed checkpoints passed, session 27027 exit0; no semantic assertions changed.
- Linux harness 538 passed/1 platform skip (eight new checkpoint regression cases). Ruff, MyPy, generator --check passed; evidence checkpoint-*.log.
- Harness/schema/docs/tests committed f2c2fdb. Anonymous YAML synchronization-only commit in progress session80975 with normal duplicate/profile-contract hook.
- Full profiles sessions5563/31645/89857 around40%; still pending. Audit script allows only exact intended two-line baseline synchronization change and enforces other529 baseline YAML unchanged.
- SHA evidence and controlled scheduling limitation recorded in investigation/report. Finish allfull zero-failure gate, canonical ledger, source/input hash matching, evidence copy, final report commit; no push/PR authorized.

- Corrected full profiles completed zero failures/errors: 14145/14128/14123 passes with30/47/52 declared skips. All1095 additions passed on allprofiles.
- Canonical ledger passed14175/14175; strict baseline audit permits only the exact anonymous restart wait-to-deadline change, verifies remaining529 YAML unchanged. Source/regression/YAML runtime byte matches passed.
- Local commits f2c2fdb harness/schema/tests,99f8205 anonymous test correction,5b95027 final report. Nothing pushed; only local .tmp and investigations untracked.
- Evidence copied into worktree .tmp/evidence, including controlled E_INVIND red/green and20 delayed-checkpoint passes. Original historical scheduling unavailable, but the same error is deterministically reproduced via stale checkpoint adoption and corrected by publication wait.
- Root cause investigation and full verification complete. No confirmed Toast restoration bug; SHA and binary hashes match CI pin and original failing reports.

- User authorized PR creation. CI explicitly rejects mixed controller/data changes, so split current combined work onto latest main1418def into controller and stacked data PRs.
- Controller PR116 ready: https://github.com/MongooseMoo/moo-conformance-tests/pull/116 head34f9cc8, branchfix/checkpoint-publication-controller, worktree moo-conformance-checkpoint-pr. Focused9tests pass; hosted classifier passed and CI running.
- Data PR117 draft: https://github.com/MongooseMoo/moo-conformance-tests/pull/117 head0acd10d, branchtests/semantic-interactions-data, basethecontrollerbranch, worktree moo-conformance-semantic-pr. Depends116 landing onmain before retarget/ready/merge.
- Data boundary independently passed controller0/data5/neutral1; generation1095 and duplicate/profile-contract hook pass. Currentmain removes14 unrelated threaded cases; descriptions distinguish prior local campaign counts from pending exact-head hosted CI.
- Both branches pushed, neither merged or auto-merge enabled. Finish reciprocal PR links and verify actual PR heads/bases/draft statuses, then give user links and CI-pending status.
