# Multiple-inheritance contract implementation checkpoint
- Key finding: upstream commit 02f6040 supplies seven portable MOO-level regression shapes matching the saved plan.
- Current state: isolated branch is clean and the upstream Ruby cases have been recovered from the managed Debian ToastStunt checkout.
- Blocker: none; the required YAML suite has not yet been written.
- Next action: encode the seven cases with local cleanup, then collect, lint, and run latest/old Toast evidence.

## Differential execution checkpoint
- Key finding: all seven contracts pass current upstream ToastStunt at eaaa197; the membership assertions now correctly normalize MOO list positions.
- Current state: exact old revision 297523b builds after generating its omitted version_options.h in the build directory.
- Blocker: the first per-case old commands selected out capability admission, so they executed no contract case and are not behavioral evidence.
- Next action: rerun each old case with admission selected, then finish repository gates and commit only the YAML suite.

## Final-gate checkpoint
- Key finding: all seven cases fail independently on old Toast 297523b and pass together on latest Toast eaaa197.
- Current state: collection reports 11,809 tests and the controller suite passes 524 of 524.
- Blocker: repository duplicate lint has pre-existing failures; the new suite has not appeared in any duplicate group.
- Next action: measure the duplicate baseline, run ruff/mypy/diff checks, and commit only the new YAML file.

## Review checkpoint
- Key finding: the implementation handoff is one committed, data-only YAML suite at 08366e89f2d520eeaca29be864ea88a57e34c6cc.
- Current state: detached Codex review is running against immutable base b3eea0df95b7654b2a7e73841c9ac99784a9fc4c.
- Blocker: none; the review process has not exited yet.
- Next action: read the completed review result, apply the bounded response if needed, then run root final verification.

## Detached-review cleanup guard
- Key finding: `git worktree remove --force` can unregister a review worktree yet leave its directory when reviewer artifacts remain.
- Durable guard: verify the exact absolute path is unregistered and inside `C:\Users\Q\code`, then remove that literal leftover and assert it is absent before continuing.
- Safety fallback: if recursive removal is policy-blocked, move the exact unregistered directory to a validated task-specific temp quarantine and report its recoverable location.

## Root final-verification checkpoint
- Key finding: review repair head is `2aeb0b3e711f2db1ad640cd7acbc1ba241b26f1e`, still based on current `origin/main` `b3eea0df95b7654b2a7e73841c9ac99784a9fc4c`.
- Current state: exact cached Toast sources are latest `eaaa1972f0993a1247f787dbf2dd5a01702ef442` and old `297523b2ae1e26e389c926be1c8a39891032b2e4`.
- Blocker: none.
- Next action: run root-owned focused differential, ordinary gates, and full latest-Toast conformance.

## Cross-OS verification guard
- Key finding: concurrent Windows and WSL `uv run` commands corrupted the shared `.venv`, producing missing `pytest`/`mypy.binder` and a WSL permission error.
- Immediate repair: stop the affected gate and discard all results from that concurrent run.
- Durable guard: set distinct task-specific `UV_PROJECT_ENVIRONMENT` paths for Windows and WSL, and never run cross-OS `uv` commands against one environment.
- Next action: prove both isolated environments independently, then restart the final gate from the beginning.

## CI oracle dependency checkpoint
- Key finding: the full unprofiled latest run is not CI-equivalent, and repository CI pins pre-hardening Toast `aecc51e9449c6e7c95272f0f044b5ba38948459e`.
- Current state: focused latest is green and all seven old cases are red, but a data-only PR would run those tests against the pinned old oracle.
- Blocker: passing exact-head PR CI requires a separate trusted-workflow oracle-pin change, which the approved plan explicitly excluded.
- Next action: stop publication and request authority to deliver the prerequisite workflow PR before the data PR.

## In-flight prerequisite ledger guard
- Key finding: the delivery ledger rejects adding dependencies after an outcome has left `QUEUED`.
- Immediate repair: retain `mi-contract` as blocked on the CI-pin merge and track the authorized `ci-pin` outcome separately.
- Durable guard: encode dependencies before dispatch; for an already blocked in-flight outcome, preserve the blocker until the prerequisite reaches its terminal state.

## CI-pin review checkpoint
- Key finding: prerequisite commit `f57abb2cf2953e5af0119ebf286f8c70c6f70888` updates the oracle pin and couples checkout/admission provenance by test.
- Current state: detached Codex review against base `b3eea0df95b7654b2a7e73841c9ac99784a9fc4c` exited zero; final review text is not yet read.
- Blocker: `mi-contract` remains blocked until this workflow-only prerequisite is normally merged.
- Next action: read the completed review, run root final verification, publish, watch CI, and merge the prerequisite.

## Root-owned pytest-cache cleanup guard
- Key finding: detached reviews can create root-owned `.pytest_cache` content that defeats both `git clean` and `git worktree remove` on Windows.
- Immediate repair: the exact unregistered CI-pin review directory was moved to recoverable temp quarantine `codex-orphaned-ci-pin-review-20260830`.
- Durable guard: launch future detached reviews with `PYTEST_ADDOPTS=-p no:cacheprovider` and retain the validated quarantine fallback.

## Local CI-generator guard
- Key finding: local WSL lacks Ninja although GitHub CI installs it, so the literal CI generator failed before compilation.
- Immediate repair: a fresh Makefiles build with identical semantic flags completed and produced the exact latest 64-bit Toast binary.
- Durable guard: preflight `ninja`; when absent locally, use a fresh default-generator directory while preserving all profile and compiler definitions.

## Process-poll guard
- Key finding: the first CI-equivalent admission poll was issued without the immediately preceding delivery-ledger `wait-safe` check.
- Immediate repair: `wait-safe` now reports no actionable outcomes while admission remains active.
- Durable guard: run and read `wait-safe` directly before every `write_stdin` process poll, including root-owned final gates.

## Review-response checkpoint
- Key finding: the multiple-inheritance suite calls `length()` but does not declare `length` in `requires.builtins`.
- Current state: the implementation commit exists; only the missing capability declaration is authorized for repair.
- Blocker: none.
- Next action: add `length`, run scoped admission/collection/profile and latest-Toast checks, then commit the repair locally.
2026-08-30 staged CI pin repair checkpoint
Key finding: latest Toast fails five existing base-data contracts, so the pin must be selected by controller/data mode.
Current state: workflow-only repair is assigned in moo-conformance-ci-pin-eaaa197; no YAML conformance data or Barn changes are authorized.
Blocker: unconditional latest-Toast selection cannot pass the controller-mode final gate.
Next action: select aecc51e for controller mode and eaaa197 for data mode, couple provenance/profile evidence to that ref, test, lint, and commit.

## Delivery-ledger command guard
- Key finding: the ledger CLI has `show`, not `status`; an attempted `status` invocation failed at argument parsing.
- Immediate repair: rerun the inspection with `issue_delivery_state.py show` and use that output as the authoritative ledger snapshot.
- Durable guard: before invoking the ledger CLI, use only the subcommands listed by its help output: `init`, `add`, `depend`, `transition`, `block`, `resume`, `attach-agent`, `show`, `git-safe`, `wait-safe`, and `publish-safe`.

## Staged CI pin final-verification checkpoint
- Key finding: controller/neutral mode must retain `aecc51e`, while data mode can select hardened Toast `eaaa197` without invalidating existing base data.
- Current state: exact head `1efd7ee` changes only the Toast workflow and workflow-contract tests; 526 tests, Ruff, and mypy pass locally.
- Blocker: none for publishing the staged controller PR.
- Next action: mark the ledger outcome verified, run the publication guard, push, open a ready PR, and monitor its exact-head checks through normal merge.

## CI pin PR merge checkpoint
- Key finding: PR #87 is clean and mergeable at exact head `1efd7ee`; all 14 checks passed and the watcher surfaced no review feedback.
- Current state: final audit confirms only the Toast workflow and its workflow-contract test, with the intended two commits and no closing phrase.
- Blocker: none.
- Next action: transition the ledger to merge-ready, execute `gh pr merge 87 --merge`, verify the two-parent merge, then prepare the required latest-oracle data compatibility PR.

## Windows ripgrep path guard
- Key finding: passing `C:\...\Temp\*` as an `rg` path is invalid on Windows because `rg` does not expand that wildcard as a directory operand.
- Immediate repair: rerun against the literal temp directory with `-g` file filters; the corrected search completed and found no saved matching log.
- Durable guard: give `rg` literal directory roots on Windows and express file selection only through `-g`; never append shell wildcards to a directory operand.

## Paired candidate-root guard
- Key finding: a custom `--moo-suite-root` is rejected unless the same invocation supplies the independently admitted `--candidate-root`.
- Immediate repair: rerun the focused latest-Toast diagnostic with both roots pointing at the isolated compatibility worktree.
- Durable guard: treat `--candidate-root` and `--moo-suite-root` as an inseparable pair in every local CI-equivalent conformance command.

## Focused conformance admission-evidence guard
- Key finding: selecting packaged conformance node IDs still requires either an admission case in-session or both the admission evidence file and its exact context.
- Immediate repair: rerun the five latest-Toast cases with the already-passed admission JSON and its matching immutable-oracle context.
- Durable guard: every focused packaged-conformance invocation must include `--admission-evidence-input` and `--admission-evidence-context` together unless admission tests are selected in the same session.

## Pytest node-selection guard
- Key finding: combining `--pyargs moo_conformance` with explicit filesystem node IDs caused pytest to select the full 11,801-case conformance suite.
- Immediate repair: interrupt the unintended run before it progressed beyond the initial cases and rerun without `--pyargs`.
- Durable guard: use either package discovery or explicit filesystem node IDs, never both; confirm the collected selected count before allowing server execution to continue.

## Detached review output guard reinforcement
- Key finding: launching `codex review` in a unified live-output session allowed an intermediate poll to expose reviewer working output.
- Immediate repair: stop polling that session and track the active review only by its recorded process ID `62548` until exit.
- Durable guard: all future Codex reviews must use a hidden `Start-Process` with separate redirected stdout/stderr files and a recorded PID; never launch a review through a live-output session.

## Fresh-worktree dev dependency guard
- Key finding: `uv run` in a fresh worktree had the runtime environment but could not spawn `mypy` because optional development dependencies were not installed.
- Immediate repair: run `uv sync --frozen --all-extras`, then rerun Ruff and mypy successfully.
- Durable guard: before a fresh-worktree quality gate, synchronize the locked environment with `--all-extras`; never infer tool availability from another worktree's `.venv`.

## Review-artifact quarantine and worktree-cwd guard
- Key finding: the review left an ACL-inaccessible `.pytest-review-temp`; Windows, WSL root, and ownership repair could not move it, and the first fresh-worktree audit accidentally remained in the original cwd.
- Immediate repair: abandon the contaminated worktree for publication and verify a fresh detached worktree at exact commit `fa70951` from its own cwd.
- Durable guard: run reviews only in disposable detached worktrees; after `git worktree add`, start a new command with that path as `workdir` before making any status, head, or cleanliness claim.

## CI repair worker and identity-boundary guard
- Key finding: PR #88 failed because four renamed YAML identities looked like deletions, and `CI_REPAIR_RUNNING` rejected a transition without a live canonical worker handle.
- Immediate repair: reactivate `/root/ci_pin_stage_repair`, record that handle, and restore only the four stable IDs while retaining corrected semantics.
- Durable guard: run paired-inventory deletion checks before publishing any data PR, and attach a live canonical agent on every transition into `CI_REPAIR_RUNNING`.

## CI-repair state-path guard
- Key finding: the ledger rejects `CI_REPAIR_RUNNING -> READY_FOR_FINAL_VERIFY`; its only allowed successor is `WATCHING`.
- Immediate repair: keep the issue repair-running while root verifies the repair, then use the existing-PR publication guard and return directly to watching after the push.
- Durable guard: do not reuse initial-delivery final-verification transitions for CI repairs; verify in-place and follow the ledger's direct `CI_REPAIR_RUNNING -> WATCHING` path.

## Latest-Toast data compatibility merge checkpoint
- Key finding: stable YAML identities had to remain unchanged, while their portable behavior contracts now assert full-width map keys, persistence, map literal quota enforcement, and deterministic recycled-max handling.
- Current state: PR #88 passed 13 exact-head checks and normally merged as two-parent commit `92ed729`.
- Blocker: none for making the latest Toast pin universal.
- Next action: land the controller cleanup that removes staged mode selection, then update and publish the original multiple-inheritance data branch against that base.

## Universal Toast pin publication checkpoint
- Key finding: after compatibility data landed, the mode conditional can be removed and all CI paths can use exact Toast `eaaa197`.
- Current state: exact head `20cbafb` passed 526 tests, Ruff, mypy, and one no-findings review; PR #89 is open.
- Blocker: exact-head CI is pending.
- Next action: watch PR #89 through normal merge, then integrate its base into the multiple-inheritance branch and publish that final data-only PR.
CI pin failure checkpoint (2026-08-30): PR #89 exact head 20cbafb ran latest Toast but four hardened-semantics cases still carried their old expected values.
Branch ancestry is correct: PR #89 is based on merged PR #88 at 92ed729, and origin/main contains fa70951 plus the stable-name follow-up 83bd326.
The failing cases are next_recycled_object, full-width integer/object map keys, map-literal quota, and dump persistence.
Current blocker: determine why fa70951 did not leave the hardened expectations in the merged tree despite its stated contract-update scope.
Next action: inspect fa70951 and PR #88 commit content, then repair the data contract separately before retrying the universal pin.
Ledger guard repair (2026-08-30): `depend` is legal only while the dependent issue is `QUEUED`; the rejected late dependency made no ledger change.
Durable rule: once an artifact has advanced, represent a newly discovered prerequisite as its own issue and finish it before manually resuming the blocked repair; never attempt to retrofit its dependency list.
Worker-transition guard repair (2026-08-30): `WORKER_RUNNING` must receive the exact worktree path and canonical agent in the same transition call.
Verified repair: `toast-data-rollback` is now `WORKER_RUNNING` at `C:\Users\Q\code\moo-conformance-toast-data-rollback` under `/root`.
Local-gate repair (2026-08-30): fresh worktrees must run `uv sync --frozen --all-extras`; the ordinary unit gate is `uv run pytest tests`, not bare pytest, which invokes the live packaged suite.
Verified corrected rollback gate: 526 unit tests passed, Ruff passed, and mypy reported no issues in 25 source files.
Wait-guard repair (2026-08-30): before waiting on any background review, dispatch every ledger-advertised actionable outcome; `READY_FOR_CI_REPAIR` must have a live canonical repair owner.
Verified repair: `/root/ci_pin_stage_repair` owns PR #89 and `ci-pin-finalize` is `CI_REPAIR_RUNNING` while the separate rollback prerequisite proceeds.
Delivery checkpoint (2026-08-30): trusted base workflows make the staged data-then-controller Toast migration deadlock; PR #89 ran old `aecc51e`, not its proposed universal pin.
The exact PR #88 rollback was committed as `c0d595f`, but its one Codex review correctly found that a data-only rollback would fail latest-Toast CI.
Current state: `toast-data-rollback` is `REPAIR_RUNNING`; PR #89 remains open at `20cbafb` and the completed MI contract remains unpublished.
Blocker: establish a temporary old/new-compatible data bridge so the controller-only universal pin can land green.
Next action: implement and verify that bridge, merge it normally, repair and merge PR #89, restore strict latest data, then publish the MI contract PR.
Recovery guard (2026-08-30): never weaken conformance contracts to bridge a circular trusted-workflow migration.
When Q explicitly authorizes the unavoidable one-time override, preserve a normal two-parent merge, disable only `enforce_admins`, push the audited merge, and restore `enforce_admins` in `finally`.
PR #89 was integrated as merge `0200f67` with parents `92ed729` and `20cbafb`; branch-protection admin enforcement was restored immediately.
Final publication checkpoint (2026-08-30): PR #89 merged as `0200f67` and exact-main run `33340751837` passed all three latest-Toast profiles and the full suite.
The MI branch was merged with that exact main; its final diff is only `multiple_inheritance_hardening.yaml`.
Local final evidence: 526 unit tests, Ruff, mypy, and seven selected latest-Toast MI cases passed.
PR #90 is open at exact head `7fabb88b583e5f975d4c360ca113898cca77bbf3`.
Next action: wait for PR #90 exact-head CI to finish green; do not merge it or change Barn.
Completion checkpoint (2026-08-30): PR #89 merged as normal two-parent merge `0200f67`; exact-main run `33340751837` passed all latest-Toast profiles.
PR #90 is open at exact head `7fabb88b583e5f975d4c360ca113898cca77bbf3`, clean and mergeable.
Its complete diff is the single new `objects/multiple_inheritance_hardening.yaml` contract file.
Exact-head CI passed all three Toast profiles, the full suite, controller validation, and quality gates.
Stopping point reached: leave PR #90 open; do not merge it or change Barn.
