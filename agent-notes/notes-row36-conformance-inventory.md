# Row 36 WAIF conformance inventory

## State

- Task is read-only: inventory tracked durable WAIF rows; do not edit tests or run an oracle.
- Repository is on `main`, ahead of `origin/main` by 14 commits.
- No tracked files are modified. The worktree contains many pre-existing untracked files which were not touched.

## Observed coverage

- `src/moo_conformance/_tests/audit/gap_followups_toast_oracle.yaml:854` has `audit_waif_callers_preserve_this_and_verb_location`, expected `{{":audit_b", 1, 1}, {":audit_c", 1, 1}}`. It checks callers-frame WAIF `this` and class `verb_location`.
- `src/moo_conformance/_tests/basic/types.yaml:130` has `constant_WAIF_value`, expected `13`.
- `src/moo_conformance/_tests/generated_builtins/new_waif.yaml` covers `function_info("new_waif")`, too many args, and an actual result satisfying `typeof(result) == WAIF` (while also accepting `E_INVARG` or `E_INVIND`).
- `src/moo_conformance/_tests/language/waif.yaml` covers creator ownership, denied writes to `.owner`, `.wizard`, and `.programmer`, two-WAIF recursive assignment `E_RECMOVE`, recycled-class invalidation, anonymous caller construction `E_INVARG`, task-stack/queued-task WAIF frame metadata, ordinary colon-property access and mutation, and WAIF method dispatch.
- `nested_waif_map_indexes` and `deeply_nested_waif_map_indexes` index a map stored in a WAIF property; they do not index the WAIF itself and therefore do not cover `WAIF_DICT`.
- `is_clear_property_rejects_waif_instance_property` proves the builtin rejects a WAIF with `E_INVARG`; it does not cover clearing/inheriting a WAIF local property.
- `src/moo_conformance/_tests/builtins/recycle.yaml:25` is mislabeled `recycle_rejects_waif`: its code is `recycle({[]})`, a list containing a map, so it does not exercise a WAIF.
- `src/moo_conformance/_tests/server/dump_persistence.yaml` only covers ordinary inherited-property overrides and adjacent float/map keys across restart; there is no WAIF persistence/backreference row.

## Missing durable coverage

1. WAIF truth.
2. Exact `tostr()` and `toliteral()` forms.
3. Identity equality, distinct-instance inequality, and alias preservation.
4. Relational operators and `sort()` errors.
5. WAIF map-key lookup/coexistence.
6. Invalid/recycled-class construction behavior.
7. `.class` write denial, `.wizard`/`.programmer` reads, and ordinary property permission behavior.
8. Alias-shared local mutation and actual `clear_property` inheritance.
9. Direct self/list/map recursive assignment variants beyond the existing two-WAIF cycle.
10. Direct `WAIF_DICT` read/write dispatch and its error cases.
11. v17 dump/restart backreference identity.

## Current blocker

No blocker to the inventory. Adding or oracle-proving missing rows is outside this delegated read-only task.

## WAIF_DICT invalid-row diagnosis in progress

- The invalid row is `wizard_owned_waif_class_dispatches_index_handlers` in the untracked candidate `src/moo_conformance/_tests/language/waif_authority.yaml`.
- Harness `permission: wizard` reconnects as the fixture player named `Wizard`; the v4 fixture identifies that player as object `#3` with wizard flags.
- `caller_perms_top_level_eval` already durably asserts that top-level wizard eval runs with `caller_perms() == player`.
- Pinned Toast `bf_create()` defaults a new object's owner to the current programmer. Therefore `create($waif)` in this row should create a class owned by wizard `#3`; the WAIF_DICT owner-wizard gate should pass.
- Pinned Toast has `WAIF_DICT` defined. `OP_INDEXSET` calls `:_set_index(KEY, VALUE)` and `OP_REF` calls `:_index(KEY)`. Both return `E_TYPE` only when the class owner is not wizard or when the relevant handler is missing; invalid class returns `E_INVIND`.
- The row's object/property/verb setup uses ordinary object-valued `class`, so the obvious `add_property()` and `add_verb()` first-argument type gates should not fail.
- Remaining diagnosis: determine whether the handler lookup name or compiled handler body is invalid, or whether the first indexed assignment reaches a source path where the effective class owner differs from the expected creator. No oracle rerun is allowed for this delegated task.
