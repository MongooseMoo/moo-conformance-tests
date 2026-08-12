# Toast semantic matrix campaign

## Goal

Add at least 1,000 independently collected, behavior-asserting conformance rows
whose expected results come from observable Toast semantics and identifiable Toast
implementation branches. The campaign deliberately excludes signature-only rows,
duplicate expressions, tautologies, sleeps, and tests which merely assert that the
server stayed alive.

The generated campaign contains **1,122 tests**:

| Contract | Rows | What each row proves |
|---|---:|---|
| Equality | 351 | One unordered pair from a 26-value corpus; `==`, `!=`, operand symmetry, and case-sensitive `equal()` |
| Relational operators | 351 | The same unordered pairs; `<`, `<=`, `>`, and `>=` in both operand directions, including exact `E_TYPE` boundaries |
| Membership | 260 | 26 probes across 10 deliberately ordered lists; `in`, case-sensitive `is_member()`, and case-insensitive `is_member(..., 0)` |
| String search offsets | 160 | Eight overlapping/case-varying source/needle pairs across both case modes and five boundary offsets for each of `index()` and `rindex()` |

The corpus includes integers, booleans, floats (including signed zero), strings
with case-equivalent spellings, object references, errors, lists, and maps. The
collection values make equality and membership exercise recursive comparison,
not only scalar dispatch.

## Toast authority

The expectations were derived from Toast source commit `aecc51e` and are verified
against `/root/src/toaststunt/build-release/moo` in WSL.

- `src/utils.cc:408-492` defines scalar, recursive collection, Boolean/integer,
  case-sensitive, and case-insensitive equality.
- `src/execute.cc:1295-1407` dispatches equality, relational operators, and `in`,
  including collection and mixed-type `E_TYPE` boundaries.
- `src/numbers.cc:195-247` makes numeric comparison strict: integers and floats
  do not coerce.
- `src/collection.cc:31-95` defines first-position list membership and the
  case-mode difference between `in` and `is_member()`.
- `src/map.cc:765-788` recursively compares map keys and values.
- `src/list.cc:787-795` exposes case-sensitive `equal()`.
- `src/list.cc:1113-1158` defines the deliberately asymmetric offset contracts:
  `index()` accepts only nonnegative offsets and returns a position relative to
  the suffix, while `rindex()` accepts only nonpositive offsets and returns a
  position in the retained prefix.

Toast's `test/tests/test_equality.rb` samples seven equal and four unequal
expressions. These matrices extend that seed into a systematic cross-type and
recursive-collection contract rather than copying the Ruby cases.

## Why the rows are useful

Every equality/relational row has a unique value pair. Equality uses unordered
pairs because the row itself asserts symmetry; adding the reverse row would be
padding. Relational rows assert both directions because `<` and `>` can diverge
under an incorrect implementation. The same corpus is retained across the two
operator families because equality permits combinations (Boolean/integer and
recursive collections) that relational operators reject.

Membership containers are intentionally ordered. They expose first-match rules,
Boolean/integer equality collisions, strict integer/float separation, ASCII case
folding, and recursive list/map equality. The expected position therefore carries
more information than a present/absent Boolean.

String-search rows cover matches before/at/after offsets, offsets at and beyond
the source boundary, overlapping needles, repeated needles, misses, and case-mode
changes. `index()` and `rindex()` are separate rows because Toast interprets their
offsets and result coordinates differently.

## Reproduction and acceptance

Regenerate or verify the checked-in YAML:

```powershell
$env:UV_PROJECT_ENVIRONMENT = ".venv-win"
uv run python tools/generate_toast_semantic_matrices.py --check
```

The campaign is complete only when all of the following are true:

1. The generator reports exactly 1,122 unique rows and no generated-file drift.
2. Pytest collects exactly 1,122 tests from the four generated files.
3. Duplicate lint and schema/unit tests pass.
4. The admission-inclusive focused campaign passes against managed WSL Toast
   with zero skips, failures, or errors.
5. The full packaged suite passes against the same Toast binary with strict
   unexpected-skip accounting and the packaged startup fixtures.
