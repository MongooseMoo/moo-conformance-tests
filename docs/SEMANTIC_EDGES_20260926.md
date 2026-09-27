# Additional MOO semantic interaction coverage

This campaign starts at `76f3d22606a4e404dba55b64feb0f82c994636c2`.
The committed baseline contains **13,080 expanded cases in 530 YAML files**.
The previous PR #82 comparison matrices are part of that baseline and receive
no credit here. Untracked tests in the original working directory are preserved
and are not included in the campaign baseline or its delivered files.
An additional duplicate audit includes those untracked tests: the original
workspace contains 13,103 cases in 539 YAML files, and none of the new executable
bodies occurs there either.

## Inventory and gaps

The inventory uses `validate_test_suite()` on every committed YAML file so that
table expansions count as collected cases, not as single templates. In addition
to listing the complete corpus, the following existing suites were examined:

| Existing coverage | Baseline cases | Gap addressed here |
| --- | ---: | --- |
| `language/scatter.yaml` | 23 | All legal three-target arrangements of required, optional, observing-default, and rest targets; defaults observing later bindings and earlier defaults; error atomicity |
| `language/scatter_error_messages.yaml` | 4 | Existing diagnostics do not check the resulting bindings and default side effects for every layout/arity |
| `language/index_and_range.yaml` | 130 | Range replacement boundaries combined with list/map nesting, shared siblings, aliases, and assignment expression results |
| `language/control_flow.yaml` | 23 | Truth values combined with lazy evaluation, selected result type, exact effect order, and errors on only the evaluated branch |
| `language/boolean_authority.yaml` | 5 | Boolean comparison/map-key behavior is already covered; new cases exercise branch selection |
| `language/try_except.yaml` | 34 | Cross-product of pending and finalizer control transfers, with additional outer finalizers |
| `language/splice.yaml` | 25 | Existing splice and operand-stack checks inform use of trace lists; no new standalone splice coverage claimed |
| `audit/divergence_waif_statement_semantics.yaml` | existing audit | Zero-bound prepend and final-return override already have examples; new rows combine them with aliasing and other transfers |
| Prior Toast equality/membership/relational/string-search matrices | 1,122 | Entirely existing; not counted as new |

These are interaction gaps, not claims that every individual language construct
was previously untested. Reversing pair order or merely changing numeric payloads
is not used to manufacture extra rows.

## New cases

| Family | Cases | Independently varied contract |
| --- | ---: | --- |
| Scatter binding/defaults | 324 | 54 legal layouts times six RHS arities; supplied targets bind before default expressions; omitted defaults preserve bindings; failures leave targets and expression result untouched |
| Nested range assignment | 432 | Two sequence types, four lvalue shapes, 18 boundary pairs, and empty/single/multiple-element replacement; checks the whole resulting structure, untouched siblings, original leaf, alias, error code, and returned RHS |
| Lazy evaluation | 264 | 22 truth-value representatives times 12 expression shapes; observes exact side-effect trace, selected value, and selected type, including caught division errors |
| Finally transfers | 75 | Five pending transfers times five finalizer transfers at three nesting depths; checks both returned snapshots and the post-call trace, error identity, and loop resumption |
| **Total additional** | **1,095** | Individually collected tests, all with value assertions |

The 18 write-boundary classes include independently clamped starts/ends, prepend,
append, replacement, insertion, overlapping reversed ranges that duplicate the
source, and both rejection branches. The four lvalue shapes are a local variable,
a shared list element, a shared map entry, and a list/map/list path. Expected
aliases and siblings are compared with independent literals, not with another
reference to the potentially mutated object.

Negative lower bounds on string writes expose an additional profile-dependent
contract. `EOP_RANGESET` compares the signed `Num` bound with the cached unsigned
32-bit string length (`var_metadata.size`). With `ONLY_32_BITS`, a negative bound
converts to unsigned and raises `E_RANGE`, leaving the lvalue unchanged. With
64-bit integers it remains negative and is clamped by `strrangeset()`. List
lengths use `Num`, so list writes clamp on both profiles. The 12 affected string
cases select an exact expected result using
`server_version("options/ONLY_32_BITS")` (`{0}` for defined, `#-1` for undefined),
reject unknown metadata, and remain
active on every profile. They do not accept either outcome or infer the expected
result from the operation under test.

The truth corpus includes numeric zeros/nonzeros, Boolean values, empty and
nonempty collections, strings containing zero/space, object references, and error
values. In Toast, object and error values are false even when their underlying
numeric identifier is nonzero. Value and type are both checked because Boolean
and integer equality alone cannot prove which operand was returned.

## Authority and expected results

Expected results are authored in the generator before Toast execution. No result
is learned by copying observed output into expectations. Toast source commit
`eaaa1972f0993a1247f787dbf2dd5a01702ef442`, pinned by this repository's CI,
provides the relevant branch contracts:

- `src/execute.cc`, `EOP_SCATTER`: validates arity before binding, binds supplied
  required/optional/rest targets, then enters omitted-default code.
- `src/execute.cc`, `EOP_RANGESET`: rejects start greater than length plus one or
  negative end, with nested lvalues rebuilt by the enclosing assignment code.
- `src/list.cc`, `listrangeset()` and `strrangeset()`: concatenate the prefix,
  replacement, and suffix independently, including overlapping reversed bounds.
- `src/utils.cc`, `is_true()`, and `src/execute.cc`, `OP_AND`/`OP_OR`: define
  truth dispatch and operand-preserving short circuit behavior.
- `src/execute.cc`, `EOP_END_FINALLY`/`EOP_CONTINUE` and stack unwinding: preserve
  pending transfers unless a finalizer initiates another transfer.

All cases use existing `statement` and `expect.value` support. The finalizer tests
create a temporary object/verb and inspect its trace property after the call,
then recycle it in an enclosing finalizer. This distinguishes a correct captured
return value from skipped cleanup code. They need no sleep, external service,
schema extension, or new test primitive.

## Reproduction

Generate the four YAML files, or detect drift:

```text
python -m moo_conformance.semantic_edges_generator
python -m moo_conformance.semantic_edges_generator --check
```

Run through the managed Toast harness with canonical admission, the packaged
`Test.db` and startup fixtures, matching oracle/target manifests, strict markers,
and `--fail-on-unexpected-skip`. The focused selector is `semantic_edges_`.
Each family also has its own `semantic_edges_*` filename for separate runs.

Completion requires a fresh identity/body audit against the above baseline,
zero unexpected duplicate groups, generator/schema/static checks, and all 1,095
new cases passing Toast without skips, and zero failures in the full suite on
all three CI Toast profiles. The exact profile union must account for every
candidate identity. Runtime evidence and the full inventory are retained
separately from generated test data.

## Verification through September 27, 2026

- Fresh canonical admission and full conformance runs passed for all three CI
  profiles using pinned Toast `eaaa1972f0993a1247f787dbf2dd5a01702ef442`:

  | Profile | Passed | Declared profile skips | Failures | New cases passed |
  | --- | ---: | ---: | ---: | ---: |
  | 64-bit outbound on | 14,145 | 30 | 0 | 1,095 |
  | 64-bit outbound off | 14,128 | 47 | 0 | 1,095 |
  | 32-bit outbound on | 14,123 | 52 | 0 | 1,095 |

- The canonical execution ledger accounts for **14,175 of 14,175** candidate
  identities across the profile union. Every new case passed without skips in
  every profile. Runtime YAML matches the delivered files byte-for-byte.
- 1,095 unique executable bodies, zero matching the committed baseline, zero
  matching the original workspace including untracked YAML. One existing YAML
  changes only checkpoint synchronization as described below; the other 529
  baseline YAML files are unchanged. Candidate inventory: 14,175 cases plus admission.
- Harness tests after the checkpoint correction: 538 passed, one platform skip,
  including eight checkpoint regression cases. Ruff, MyPy and regeneration drift
  checks pass. The reviewed duplicate baseline is checked by the commit hook.

Evidence is retained in the campaign worktree's `.tmp/evidence/`: profile JUnit
and logs, identity audits, `workspace-audit.json`, the complete baseline
inventory, admission, and static-check logs. The native WSL execution copy is
`/tmp/moo-semantic-edges-20260926`.

An earlier run on the correct pin failed the existing anonymous-object restart
case on all profiles. Passing reruns initially left its cause unexplained. The
follow-up investigation reproduced the exact `E_INVIND` by delaying checkpoint
publication beyond the fixed sleep, then letting publication finish after the
harness had already selected its old input database. The restored class was
invalid. The original failed run did not retain its database, so its exact
scheduling cannot be reconstructed; the controlled race is reproduced and fixed.

The existing test now uses `restart_server.checkpoint_timeout_ms: 5000` instead
of `wait: 1500`. The harness requires fresh published output before adopting it
and stopping the process; stale/partial files cannot satisfy the wait. Deadline
expiry fails without stopping or substituting a shutdown dump. Semantic checks
are unchanged. The identical controlled experiment passes after the correction,
as do 20 repetitions with 3-second delayed checkpoints. All three corrected full
profiles pass with the zero-failure counts above; the exact ledger covers every
candidate identity. Delivered harness, regression tests and YAML match runtime
inputs byte-for-byte. See `tests/test_checkpoint_restart.py` for portable
regressions and `docs/YAML_SCHEMA.md` for the new field's contract.

Failed reports remain in `ci-failed-*` and `ci-delayed-gap-red-*`; controlled
passing reports are in `ci-delayed-gap-green-*` and `ci-delayed-repeat-green-*`.
These are local WSL runs matching CI's pinned oracle and profile commands, not
a new hosted CI run.

### Rejected preliminary validation

The preliminary full run used the wrong oracle: local Toast `aecc51e9`, rather
than CI's pinned `eaaa1972`. Its failures are **not accepted baseline failures**.
Repeating them with the new cases excluded did not validate the correct target.
The exact baseline commit's CI run
[`36292503398`](https://github.com/MongooseMoo/moo-conformance-tests/actions/runs/36292503398)
passes all three profiles with zero failures. No baseline expectation, skip,
fixture, or server implementation was changed to accommodate the obsolete
oracle. The earlier completion claim was withdrawn.
