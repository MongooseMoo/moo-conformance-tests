# Toast 1000 useful conformance tests campaign

## Current state

- Branch: `agent/toast-conformance-1000-useful`, created from `origin/main` at `71e2ba2`.
- The checkout had substantial pre-existing dirty and untracked material before this campaign. In particular, the tracked edits to `match_rmatch.yaml`, `math.yaml`, `control_flow.yaml`, and `looping.yaml` are user-owned and must not be staged or rewritten.
- Current working-tree collection before campaign-owned test files: 11,640 tests. The prior exact-main authority count was 11,591; the 49-row difference is consistent with pre-existing local edits/untracked tests and is not campaign credit.
- Managed authority: WSL Toast binary `/root/src/toaststunt/build-release/moo` at Toast source commit `aecc51e`.
- Windows `uv` must use `UV_PROJECT_ENVIRONMENT=.venv-win`; the shared `.venv/lib64` removal fails with access denied after WSL use.

## Toast source observations

- `src/utils.cc:408-492` defines comparison/equality: ordinary `==` is case-insensitive recursively for strings/lists/maps; `equal()` is case-sensitive; booleans compare equal to integer 0/1 only; floats do not coerce to integers.
- `src/execute.cc:1295-1407` implements equality, relational operators, and `in`. Relational operators permit same-type scalar comparisons, reject list/map and mixed types, and numeric comparisons remain strict about int versus float.
- `src/list.cc:659-795` defines set/list insertion/deletion/set boundaries and `equal()`.
- `src/list.cc:1047-1158` defines `strsub`, `strcmp`, `index`, and `rindex`, including case flags and asymmetric offset rules.
- `src/collection.cc:31-95` shows membership is equality-driven, list membership returns first position, map membership scans values, while `is_member()` defaults to case-sensitive behavior.
- `src/map.cc:678-788` constrains map keys and recursively compares map keys/values.
- Toast's Ruby `test_equality.rb` only samples a small set of equal/unequal pairs, so a source-derived pairwise semantic matrix adds real coverage rather than transcribing an already exhaustive upstream suite.

## Working design

- Add deterministic table-driven matrices whose rows are independently collected tests.
- First matrix: ordered-pair equality corpus across scalar and recursive collection classes, asserting both case-insensitive `==`/`!=` and case-sensitive `equal()`.
- Second matrix: ordered-pair relational corpus, asserting all four operators and exact `E_TYPE` boundaries using catch expressions.
- Target at least 1,152 campaign-owned rows (24 x 24 x two operator families), with source anchors and a reviewable coverage ledger. Expand further into membership/string/list boundaries if the pairwise corpus cannot make every row semantically distinct and defensible.

## Blockers / risks

- No external blocker. The principal risk is inflating count with redundant cross-type rows. The corpus and plan must classify every row by a distinct ordered pair and operator contract, and duplicate lint must remain clean.
- Full verification must include `capability_admission`, strict unexpected-skip handling, packaged startup fixtures, and the managed WSL Toast binary. A Windows-only or admission-free run is diagnostic, not completion evidence.

## Next action

1. Finalize the corpus and expected-result model directly from the cited Toast branches.
2. Add the campaign plan, deterministic generator, and generated YAML via `apply_patch`/mechanical generation on campaign-owned paths only.
3. Collect and lint exactly the new files, then run the focused admission-inclusive WSL Toast slice.
4. Run the full managed Toast gate and audit the count against the 11,640 pre-campaign working-tree baseline and the 11,591 committed-main baseline.

## Progress update

- Added campaign-owned draft paths only: `docs/TOAST_SEMANTIC_MATRIX_CAMPAIGN.md`, `tools/generate_toast_semantic_matrices.py`, and four generated YAML matrices. None are staged yet.
- Generator/drift check reports exactly 1,122 rows: equality 351, relational 351, membership 260, string search 160.
- Packaged collection selects exactly 1,122 campaign rows and 12,762 total working-tree rows, with 11,640 pre-campaign rows deselected. Collection correctly fails closed if admission is omitted.
- `tests/test_schema.py` plus `tests/test_lint_duplicates.py`: 90 passed.
- Whole-tree duplicate lint with `--baseline ci/duplicate-baseline.json`: passed; reviewed baseline remains exactly 45 name groups and 28 content groups. It scanned 507 YAML files and 4,575 unexpanded test templates.
- New generator passes Ruff after its import order was fixed.
- A schema defect found before runtime (`requires.builtins` rendered as null for the no-builtin relational suite) was fixed in the generator and regenerated output.

## Current oracle action

Use the repository's staged authority shape, not a `-k` same-session shortcut:

1. Create a local Toast profile manifest matching the actual WSL binary/profile.
2. Run `pytest -m admission` against the managed WSL Toast binary, packaged `Test.db`, packaged startup fixtures, strict markers, and a fixed evidence context; write admission JSON/JUnit.
3. Run `pytest -m conformance` with the four campaign `-k` selectors, `--fail-on-unexpected-skip`, and the exact admission evidence/context.
4. If focused green, run the complete packaged suite with the same evidence and strict skip gate.

No blocker is present. Expected-value mistakes discovered by Toast are test-design defects to correct against the cited source, not reasons to skip rows.

## Verified implementation update

- Campaign commit: `feb8b6e` (`Add Toast-derived semantic conformance matrices`) on branch `agent/toast-conformance-1000-useful`.
- The commit contains exactly six campaign paths: the plan, deterministic generator, and four generated YAML suites. Pre-existing tracked edits and all notes/logs/scratch files remained unstaged and uncommitted.
- Focused canonical admission: 1 passed, 12,761 deselected, evidence context `toast-1000-aecc51e`.
- Strict focused WSL Toast result: **1,122 passed, 11,640 deselected, 0 skipped, 0 failed** in 1,902.97 seconds. JUnit/log evidence is under `.tmp/toast-1000-campaign/`.
- Static evidence: generator drift check reports 1,122; focused collection reports 1,122; duplicate baseline passes; schema/duplicate tests are 90/90; MyPy passes 24 source files; Ruff passes all tracked Python plus the generator; `git diff --check` and the staged diff check were clean.
- The full Windows harness unit run is 520/521 because an ignored, pre-existing `build/lib/moo_conformance/test_conformance.py` violates the single-owner test. Do not delete that user-owned build tree or modify the stable test.

## Full-suite execution update

- A serial complete packaged run was started twice and deliberately interrupted without failures because execution is approximately one case per second; the first attempt also paid a 3.5-minute DrvFS collection stall.
- A native WSL candidate snapshot at `/tmp/moo-conformance-campaign-L9rwaSrc` removes collection latency and exactly collects 12,761 conformance cases, but serial execution remains too slow.
- The safe acceleration plan is eight disjoint YAML-suite shards, each with an independent managed Toast process/database, identical profile/admission evidence, strict markers, and strict unexpected-skip handling.
- The sole cross-suite dependency is `capabilities/queued_tasks.yaml` providing `queued_tasks` to `fork/fork_timing.yaml` and `fork/fork_observation.yaml`; these three must stay in the same shard.
- Temporary sharder `.tmp/toast-1000-campaign/shard_full_suite.py` failed before creating `shards/` because `moo_conformance.schema` does not export `load_yaml_test_suite`. Fix it to use the actual loader (`load_test_suite`, to be confirmed by `rg`) and rerun. Since `mkdir(exist_ok=False)` already created an empty `shards/` before the import-time failure did not execute main, inspect whether the directory exists before retrying; do not delete blindly.

## Immediate next action

1. Inspect the actual schema loader name and whether the native `shards/` path exists.
2. Patch the temporary sharder and generate a manifest proving 507 files and 12,761 expanded tests are partitioned exactly once.
3. Run all eight strict shards, aggregate JUnit counts/status, and copy evidence back to `.tmp/toast-1000-campaign/`.
4. Complete the commit/diff/count audit and only then consider the goal complete.

## Exact-HEAD completion evidence

- Created an exact archive of commit `feb8b6ee06e6482577b0e71d28913da26577337a`, excluding every dirty/untracked workspace artifact, at native WSL path `/tmp/moo-conformance-head-feb8b6e-x08hYuk8`.
- Exact parent-vs-head inventory:
  - parent `71e2ba210ebc4788e13d7a843557300eb8234032`: 11,610 conformance IDs
  - head `feb8b6e...`: 12,732 conformance IDs
  - added: exactly 1,122; removed: 0; duplicate IDs in either inventory: 0
  - added IDs occur in exactly the four campaign YAML files
- Exact-head source partition: 500 YAML files, 12,732 conformance cases, assigned exactly once across eight shards. The only capability provider/consumer group stayed together.
- Exact-head full strict managed WSL Toast result, canonical `{db}.new` output naming:
  - 12,301 passed
  - 431 declared skips
  - 0 failures
  - 0 errors
  - all eight shard exit codes 0
- Canonical admission remains 1 passed under context `toast-1000-aecc51e`, so total collected exact-head items are 12,733.
- Exact-head clean-archive quality gate:
  - harness tests: 520 passed, 1 platform skip
  - collection: 12,733
  - duplicate baseline: passed (500 YAML, 4,546 raw templates; reviewed 45 name and 28 content groups unchanged)
  - generator drift: exactly 1,122
  - Ruff: clean
  - MyPy: clean across 24 source files
- Evidence copied to `.tmp/toast-1000-campaign/head-feb8b6e/`: per-shard JUnit/log/status, partition manifest, aggregate JSON, case delta JSON, and static logs.

## Remaining audit action

- A new-row uniqueness script failed before producing its JSON because it called `get_code_to_execute()` on unrelated parent multi-step cases. This is an audit-script bug only.
- Fix by deriving parent executable bodies only for tests without `steps` (or catching `ValueError`), while all 1,122 campaign rows are ordinary `code` tests. Assert 1,122 unique new IDs, 1,122 unique new executable bodies, and zero exact executable-body matches in the parent.
- Then run final branch/diff/status audit, update the plan/goal, and report completion. Keep this notes file uncommitted.

## PR publication checkpoint (2026-08-12)

- Final campaign head is `76b9565fe1a321cbe4576d1c40acafd5f85e0a6a` on `agent/toast-conformance-1000-useful`; the commit subject remains `Add Toast-derived semantic conformance matrices`.
- `origin/main` is `71e2ba210ebc4788e13d7a843557300eb8234032`; the branch is one commit ahead.
- The committed delta is exactly six added campaign paths and 4,897 insertions. `git diff --check origin/main...HEAD` passes and the index is empty.
- The workspace still contains four pre-existing tracked modifications plus extensive untracked user files. They remain unstaged and must not be included in the push or PR.
- No issue was named for this work, so the PR must not invent a closing phrase.
- Current blocker: none. Next action: verify GitHub CLI authentication, repository/default branch, and absence of an existing PR; then push only this committed branch and open a draft PR against `main`. Do not merge it.

## PR publication result

- Pushed `agent/toast-conformance-1000-useful` to `origin`; remote and local heads both resolve to `76b9565fe1a321cbe4576d1c40acafd5f85e0a6a`.
- Opened draft PR #82, `Add 1,122 Toast-derived semantic conformance tests`, against `main`: https://github.com/MongooseMoo/moo-conformance-tests/pull/82
- GitHub read-back confirms the PR is open and draft, contains the single intended commit and exactly the six audited campaign files, and targets the expected head SHA.
- The trusted exact-head probe is green. CI then failed closed because `tools/generate_toast_semantic_matrices.py` is an unclassified semantic path in `moo_conformance.change_boundary`; the dependent quality/full-suite jobs consequently failed or skipped without running the candidate suite. The PR is intentionally unmerged.
- The index remains empty. This notes file and all unrelated dirty/untracked workspace material remain uncommitted.

## CI repair checkpoint (2026-08-12)

- PR #82 failed at the trusted change-boundary classifier with the exact root cause `unclassified semantic paths: tools/generate_toast_semantic_matrices.py`; downstream quality and full-suite jobs failed or skipped without executing the candidate suite.
- The repository policy explicitly rejects unknown generator scripts and mixed controller/data changes. The repair therefore uses the established controller-first split instead of weakening the classifier.
- Created controller-only branch `agent/toast-semantic-matrix-generator` at `2105a88c7369269e3b71e9e006e46405939bcc9a` and opened draft prerequisite PR #83 against `main`: https://github.com/MongooseMoo/moo-conformance-tests/pull/83
- PR #83 contains only `src/moo_conformance/toast_semantic_matrix_generator.py` and `tests/test_toast_semantic_matrix_generator.py`. Local verification is 522/522 harness tests, Ruff clean, MyPy clean across 25 source files, `git diff --check` clean, and controller-only classification.
- In the PR #82 worktree, the unclassified `tools/generate_toast_semantic_matrices.py` copy has been removed and the campaign documentation plus four YAML provenance headers now point to `python -m moo_conformance.toast_semantic_matrix_generator`. These edits are not staged yet.
- No blocker is present. Next action: verify the packaged generator reproduces the four exact YAML files, commit only the six campaign-path adjustments, merge the prerequisite branch into #82, push, retarget #82 to the prerequisite branch, and monitor exact-head CI. Do not merge either PR.

## CI repair handoff

- PR #82 head is now `7116c217e254838b49ccf7af5e80f6e4bfd23fcb`. It contains corrective commit `8d79bad19a149e9cd175f2a129509470418c4d10` plus normal dependency merge commit `7116c217e254838b49ccf7af5e80f6e4bfd23fcb` with parents `8d79bad...` and `2105a88...`.
- PR #82's net diff against the prerequisite is exactly five files: four YAML data suites and one neutral campaign document. The exact clean head classifies as `data` with controller=0, data=4, neutral=1.
- Local trusted-controller parity is green: 11,610 trusted identities within 12,732 candidate identities, 12,733 collected items including admission, duplicate baseline exact, 18 startup fixtures valid, and generator drift exactly 1,122 rows.
- Retargeting #82 to the prerequisite branch changes the GitHub UI diff correctly, but the `pull_request_target` reusable workflow still checks out trusted controller ref `71e2ba2...` from `main`. GitHub therefore still reports controller+data until the prerequisite lands on `main`.
- PR #83 exact head `2105a88c7369269e3b71e9e006e46405939bcc9a` is fully green after rerunning one infrastructure-only failure where `setup-uv` timed out fetching Astral's manifest. The rerun passed classification, both controller quality lanes, harness, all three Toast profiles, exact profile union/ledger, reusable result, and exact-head required-check reporting.
- Current blocker: merging prerequisite PR #83 into `main` requires explicit user authorization. After that normal merge, retarget #82 to `main` and let its data-only CI run. PR #82 itself must remain unmerged.

## CI repair completion

- With explicit user authorization, PR #83 was marked ready and merged with the exact command `gh pr merge 83 --merge`. GitHub records normal merge commit `6528b8cf6d72c065c722469b070fea16d626e602`, whose two parents are `71e2ba210ebc4788e13d7a843557300eb8234032` and controller head `2105a88c7369269e3b71e9e006e46405939bcc9a`.
- PR #82 was retargeted to `main`, brought current by normal merge commit `d888d2f85df47b00fde51e315612f3a952e760f9`, and pushed. Local and remote branch heads match exactly.
- GitHub run `31574130770` completed successfully on exact head `d888d2f...`: trusted boundary classification, trusted controller validation, harness/schema/duplicates/types/lint, all three Toast profiles, full-suite aggregation, reusable result, and exact-head reporting are green. Both required checks report `SUCCESS`.
- Final GitHub read-back confirms PR #82 is `OPEN`, `isDraft: true`, `mergeCommit: null`, targets `main`, and has a clean merge state. Its net diff is exactly the campaign document plus four new YAML matrices: five files and 4,471 insertions.
- The four pre-existing tracked modifications and all unrelated untracked material remain unstaged and untouched. PR #82 remains deliberately unmerged.
