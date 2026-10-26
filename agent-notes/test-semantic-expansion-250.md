# Semantic expansion: 216 cases

## Goal

Open one PR from an isolated worktree with 200–300 genuinely new semantic conformance cases, all passing on Toast. Q authorized implementation with "Make it so!" No merge requested.

## State

Branch test/semantic-expansion-250 in C:/Users/Q/code/mct-semantic-expansion-250, based on origin/main 80eb0b6. Added three YAML files, 72 cases each. Each file passed its focused managed WSL Toast run. No skips or failures remain. Commit/publication and PR CI are next.

## Decisions and why

Recent merged PRs #150, #146, #143, #140, #136 and #135 emphasize observable object-system state across mutations: identity, inherited resolution, dispatch and rejected changes. Extend those contracts using the existing YAML harness. Implementation is approximately 5,350 lines, within the initial 4,000–7,000-line estimate; no harness, generator, baseline or workflow changes.

- semantic_verb_mutation_dispatch.yaml: 24 mutation sequences in three callable-lookup contexts: local definition, empty inheriting receiver, and inheriting receiver with its own unrelated verb. Calls warm three successful names and one missing name before the mutation; all four are checked afterward. The contexts distinguish lookup starting at the receiver from skipping to an ancestor with verbs. Includes rename/collision, execute-flag changes, deletion/redefinition, ancestor changes, command-argument changes, and failed compilation after a successful replacement.
- semantic_renamed_property_slots.yaml: 24 operations after renaming a live definition, observed through a clear child, an overridden child, or a clear grandchild inheriting an intermediate override. Checks remapped names, values, clear bits, slot metadata, collisions and reparenting.
- semantic_property_collection_updates.yaml: 24 indexed/range update scenarios through a defining slot, clear inherited slot, or explicit inherited slot. Checks the updated value, saved pre-update value, parent and sibling values, and clear state. Includes mixed nested lists/maps/strings and six rejected-update paths.

The dimensions represent different source paths or state, not arbitrary constants or renamed fixtures. Each test makes its own objects and recycles them in finally. These are same-task semantic cases; they do not claim persistence, task-boundary, concurrency, anonymous-object or Barn evidence.

## Novelty evidence

Compared current tracked suites and open PRs #145/#151. Existing basic/property.yaml and builtins/properties.yaml cover ordinary inheritance, permissions, clear slots, reparenting and definition order. New property cases first rename an existing definition with live descendant slots, then exercise a second operation against those slots.

Existing objects/verb_matching.yaml and audit/verb_dispatch_toast_oracle.yaml cover static alias matching/selection and permissions. builtins/verb_cache.yaml covers renumber/recycle cache statistics. The new dispatch cases warm positive and negative name lookups before changing definitions and observe all affected names across the three receiver contexts.

Existing builtins/collection_improvements.yaml tests collection sharing through local variables. builtins/map.yaml:388–432 checks property indexed writes but not saved-value/parent/sibling isolation or inherited clear-state preservation on rejection. The new collection cases assert those additional contracts.

Read the recent merged diffs and searched all existing YAML for renaming and collection-property writes, then inspected matching map and cache tests. This is semantic coverage accounting, not a claim of formal program-equivalence proof. CI's existing duplicate check remains unchanged.

## Source evidence

Read local Toast checkout eaaa1972f0993a1247f787dbf2dd5a01702ef442, also the revision pinned in PR CI:

- src/verbs.cc:321–362: validation and permission checks precede verb metadata mutation.
- src/verbs.cc:504–549: only successful compilation installs the replacement program.
- src/db_verbs.cc:219–254: definition insertion and matching order; :481–620: callable lookup and receiver/ancestor starting points; :793–875: name/flag invalidation and program replacement.
- src/property.cc:147–193: rename is validated before metadata changes.
- src/db_properties.cc:271–299: rename rejects collisions, updates the definition name in place; :570–624: inherited clear-value lookup; :658 onward: property writeback.
- src/execute.cc:1175–1255: index update errors and collection writeback operations; :1855 and :1959 onward: property read/write; :2291 onward: range assignment.
- src/list.cc:171–193, :302–331, :551–579: copy-on-write list replacement and list/string range reconstruction.
- src/map.cc:678–714: shared map duplication before insertion/replacement.

Managed WSL source checkout is aecc51e9449c6e7c95272f0f044b5ba38948459e; its rename and callable lookup source was also inspected. property.cc, verbs.cc, list.cc and map.cc have no diff between those two source revisions. Differences in db_properties.cc/db_verbs.cc include later multiple-inheritance traversal hardening. The binary's build provenance was not independently reconstructed.

## Verification

Binary: /root/src/toaststunt/build-release/moo
SHA-256: 72fb1cf96cb303647a8ee72808e7c1ff62a491ecf44f547e6757e71ba2402bde

For each of the three new files, ran from the worktree in WSL:

```sh
PYTHONPATH=src /root/.venvs/moo-conformance/bin/python -m pytest src/moo_conformance/test_conformance.py --moo-suite-path objects/FILE.yaml --server-command "/root/src/toaststunt/build-release/moo {db} {db}.out -p {port}" -q --tb=short
```

Each final invocation passed the 72 authored cases and the existing admission test. Only files actively authored were run locally; full-suite/schema/duplicate/lint checks belong to PR CI.

## Surprises

Initial collection run failed because I used catch fallback => "ok": that replaced errors with "ok", while successful assignments returned their assigned values. Example: expected [0, "ok", 1, 1, 1, 1, 0], got [0, 9, 1, 1, 1, 1, 0]. Fixed the shared expression in the cases to retain caught errors and normalize successful values by type. The subsequent file run passed. No new check or workflow step added.

## Next step

Commit, push and open the PR. Follow the PR's existing CI and repair any in-scope failure. Preserve all pre-existing files in the primary checkout. Do not merge.
