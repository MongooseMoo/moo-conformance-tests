# Toast oracle verification (2026-07-21)

## Goal

Verify whether the current `main` checkout remains 100% compliant with ToastStunt as the oracle after the Banteng-related conformance work.

## Oracle identity

- WSL binary: `/root/src/toaststunt/build-release/moo`
- Toast source HEAD: `aecc51e9449c6e7c95272f0f044b5ba38948459e`
- Stock profile: `../barn/profiles/toast/stock-wsl-testdb.json`
- `src/include/options.h` SHA-256: `a88a8c6c37b66ca65a08a318988361827f131421edeff25e5b4af83fb3fa8036`
- Bundled `src/moo_conformance/_db/Test.db` SHA-256: `1a3f23ebb549e02ccf5341668425118fcdc935b977096add87bc2a8ef29d408e`
- The live source revision and both hashes match the stock profile manifest.

## Findings

1. Documented default managed full suite:
   - Command used: `uv run moo-conformance --server-command="/root/src/toaststunt/build-release/moo {db} {db}.out -p {port}" -v`
   - Result: `11409 passed, 149 skipped in 340.44s`
   - This is green for executed rows but is not proof of 100% coverage because 149 rows were skipped.

2. Strict managed full suite with canned Toast databases:
   - Added `--server-db-dir=/root/src/toaststunt/test/tests --fail-on-unexpected-skip`.
   - Result: `63 failed, 11414 passed, 81 skipped in 345.25s`.
   - 57 failures are dynamic profile/capability skips rejected by the strict flag, including absent optional builtins, 32-bit-only rows on the 64-bit oracle, option variants, and listener/transport requirements.
   - Six failures are executed behavioral failures: `startup_repair_anon1` through `startup_repair_anon6`.

3. Focused startup-repair verification:
   - Command selected 11 rows using the exact Toast canned DB directory.
   - Result: `6 failed, 5 passed, 11547 deselected in 22.33s`.
   - `startup_repair_broken1` through `startup_repair_broken5` pass.
   - `startup_repair_anon1` through `startup_repair_anon6` all fail because the expected `AnonN.db.new` file does not exist in the managed server directory.

## Current state

- Conclusion: the current suite is not verified 100% compliant with Toast.
- Branch: `main`, 38 commits ahead of `origin/main` at verification start and end.
- Tracked worktree remained clean. Pre-existing untracked logs, reports, scripts, prompts, and temporary files were left untouched.
- This note is intentionally uncommitted and unstaged.

## Blocker

The six `Anon*.db` startup-repair expectations do not match the observed managed Toast result. Separately, the single stock 64-bit profile cannot execute 57 rows that require other compile-time features, option variants, architecture, listener capabilities, or optional builtins.

## Next action

If authorized to fix rather than only verify, first investigate the six `startup_repair_anon*` YAML expectations and managed-server output-path behavior against Toast's original canned-database tests. Do not alter or suppress the rows before determining whether the YAML expectation or harness path is wrong.
