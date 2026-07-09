# Optional Extension Coverage Report

## Summary

Implemented Toast-backed behavior coverage for optional extension builtins:

- `url_encode`: plus-vs-space encoding, unreserved pass-through, and Toast's `E_INVARG` rejection for raw high-byte strings.
- `url_decode`: plus literal behavior, encoded plus behavior, malformed percent literals, high-byte decode preservation through `encode_binary`, and NUL truncation from Toast's `str_dup()` path.
- `curl`: wizard permission remains covered; added deterministic protocol restriction/error-map checks for `file:` and `ftp:`, truthy header flag acceptance, and timeout type validation. No uncontrolled public network success case was added.
- `spellcheck`: correct-word success and misspelled-word suggestion-list behavior, gated by `missing builtin.spellcheck`.
- `simplex_noise`: list-member type rejection, invalid dimension error values, deterministic float output, and four-dimensional float output, gated by `missing builtin.simplex_noise`.
- `malloc_stats`: seven-element integer-list shape tests, gated by `missing builtin.malloc_stats`.

Toast source inspected at `/root/src/toaststunt` commit `aecc51e`.

## Files Changed

- `src/moo_conformance/_tests/builtins/url_curl.yaml`
- `src/moo_conformance/_tests/builtins/optional_extensions.yaml`

## Commands Run

- `Get-Content -LiteralPath prompts/coverage-optional-extensions.md`
  - Outcome: read the required prompt.
- `git status --short --branch`
  - Outcome before edits: `main...origin/main` with unrelated untracked files only.
- `rg -n "moo-conformance-tests|coverage|optional extensions|optional-extensions" C:\Users\Q\.codex\memories\MEMORY.md`
  - Outcome: found prior WSL Toast oracle notes and builtin coverage workflow notes.
- `rg --files src/moo_conformance/_tests/builtins`
  - Outcome: found existing builtin suites, including `url_curl.yaml`, presence suites, and no behavior suite for `spellcheck`, `simplex_noise`, or `malloc_stats`.
- `rg -n "curl|url_encode|url_decode|spellcheck|simplex_noise|malloc_stats|skip_if|requires" src/moo_conformance/_tests/builtins src/moo_conformance`
  - Outcome: confirmed current coverage was presence/signature-heavy for this optional-extension surface.
- `wsl --cd /root/src/toaststunt --exec bash -lc "pwd && git rev-parse --short HEAD && rg -n 'bf_(curl|url_encode|url_decode|spellcheck|simplex_noise|malloc_stats)|url_encode|url_decode|spellcheck|simplex_noise|malloc_stats|curl' src tests 2>/dev/null | head -200"`
  - Outcome: Toast source at `aecc51e`; found implementations in `src/curl.cc`, `src/spellcheck.cc`, `src/simplexnoise.cc`, and `src/server.cc`.
- `wsl --cd /root/src/toaststunt --exec bash -lc "sed -n '1,190p' src/curl.cc && sed -n '1,110p' src/spellcheck.cc && sed -n '524,575p' src/simplexnoise.cc && sed -n '2468,2505p' src/server.cc && sed -n '548,570p' src/include/options.h"`
  - Outcome: confirmed `curl` protocol restrictions and error maps, URL helper libcurl calls, spellcheck return shape, simplex invalid-dimension error values, and `malloc_stats` list shape.
- `wsl --cd /root/src/toaststunt --exec bash -lc "sed -n '2505,2555p' src/server.cc && rg -n 'test_.*(curl|url_encode|url_decode|spellcheck|simplex_noise|malloc_stats)|curl\(|url_encode\(|url_decode\(|spellcheck\(|simplex_noise\(|malloc_stats\(' test tests 2>/dev/null"`
  - Outcome: confirmed `malloc_stats` returns seven entries when available and Toast's Ruby tests only cover a curl HTTP request parser case, not deterministic conformance behavior for these helpers.
- `uv run moo-conformance --collect-only -k url_curl`
  - Outcome: passed collection; existing `url_curl` selected 10 rows.
- `uv run pytest tests/test_schema.py tests/test_conformance.py tests/test_builtin_coverage.py`
  - Outcome: mistakenly too broad because `tests/test_conformance.py` expands the YAML suite without a server; terminated after repeated setup errors. No files changed.
- `uv run moo-conformance --server-command="/root/src/toaststunt/build-release/moo {db} {db}.out -p {port}" -k url_curl`
  - Outcome: failed on Windows with `FileNotFoundError` because Windows cannot launch the WSL `/root/.../moo` path.
- `uv run moo-conformance --collect-only -k "url_curl or optional_extensions"`
  - Outcome after final edits: passed collection; 31 selected, 11430 deselected.
- `wsl --cd /mnt/c/Users/Q/code/moo-conformance-tests --exec bash -lc 'UV_PROJECT_ENVIRONMENT=.venv-wsl uv run moo-conformance --server-command="/root/src/toaststunt/build-release/moo {db} {db}.out -p {port}" -k "url_curl or optional_extensions"'`
  - First outcome: 19 passed, 2 skipped, 9 failed; failures corrected by replacing numeric type assumptions with symbolic predicates, recognizing `simplex_noise` invalid dimensionality returns the error value `E_TYPE`, and tightening binary/curl map expectations.
  - Second outcome: 28 passed, 2 skipped, 1 failed; high-byte `url_encode` behavior corrected to `E_INVARG`.
  - Final outcome: 29 passed, 2 skipped, 11430 deselected in 9.04s.
- `git diff --check`
  - Outcome: passed.

## Commit

- Coverage commit: `30cf56d` (`Add optional extension builtin behavior coverage`)

## Deferred Behavior

- `curl` successful HTTP/HTTPS fetching was intentionally deferred. Toast has a Ruby parser test for GET requests, but a conformance test would require a controlled in-harness HTTP endpoint; uncontrolled public services would make the row nondeterministic.
- `malloc_stats` behavior rows were added but skipped in the WSL Toast oracle because `malloc_stats` was missing in that build. The tests are gated with `skip_if: "missing builtin.malloc_stats"` and will run on jemalloc-enabled builds.
- No harness/schema unit tests were run after final edits because this slice changed only YAML test data, not schema or runner code.
