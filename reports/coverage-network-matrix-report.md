# Coverage Network Matrix Report

## Summary

Added `network_matrix` conformance coverage for deterministic local listener and outbound-network behavior:

- `listen()` option-map state for IPv4 listeners, including `print-messages`, `ipv6`, `interface`, object, and port fields in `listeners()`.
- `unlisten(desc, ipv6)` state transition behavior, proving the wrong IPv6 discriminator rejects without removing the IPv4 listener.
- `open_network_connection()` local loopback with options map, outbound `connection_info()` fields, `buffered_output_length()` growth after queued notify output, `connection_name_lookup(..., 0)` non-rewrite behavior, and `boot_player()` cleanup.
- IPv6 option behavior for `open_network_connection()` against an IPv4 numeric host.
- Disabled outbound-network profile rows for two-argument and options-map `open_network_connection()` forms, gated with `skip_if: "option.OUTBOUND_NETWORK"`.

## Files Changed

- `src/moo_conformance/_tests/builtins/network_matrix.yaml`

## Commands Run

- `uv run moo-conformance --collect-only -q -k network_matrix`
  - Outcome: failed before collection with `Access is denied` while installing `pytest.exe` into `.venv`.

- `$env:UV_PROJECT_ENVIRONMENT='.venv-win'; uv run moo-conformance --collect-only -q -k network_matrix`
  - Outcome: passed collection.
  - Exact result: `5/11460 tests collected (11455 deselected)`.

- `$env:UV_PROJECT_ENVIRONMENT='.venv-win'; uv run moo-conformance -q -k network_matrix --server-command="/root/src/toaststunt/build-release/moo {db} {db}.out -p {port}"`
  - Outcome: failed before tests started on Windows because `/root/src/toaststunt/build-release/moo` is a WSL path and Windows `subprocess` raised `FileNotFoundError`.

- `wsl --cd /mnt/c/Users/Q/code/moo-conformance-tests --exec bash -lc 'UV_PROJECT_ENVIRONMENT=.venv-wsl uv run moo-conformance -q -k network_matrix --server-command="/root/src/toaststunt/build-release/moo {db} {db}.out -p {port}"'`
  - First outcome: `1 failed, 2 passed, 2 skipped, 11431 deselected`; failure was an over-specific assertion that outbound `source_port` was positive and `source_ip` non-empty.
  - Final outcome after narrowing to Toast's deterministic fields: `3 passed, 2 skipped, 11455 deselected`.

- `wsl --cd /mnt/c/Users/Q/code/moo-conformance-tests --exec bash -lc 'UV_PROJECT_ENVIRONMENT=.venv-wsl uv run moo-conformance -q -k open_network_connection_loopback_records_outbound_state_and_boots_cleanly --server-command="/root/src/toaststunt/build-release/moo {db} {db}.out -p {port}"'`
  - Outcome: passed.
  - Exact result: `1 passed, 11450 deselected`.

- `git diff --check`
  - Outcome: passed with no output.

- `git diff --cached --check`
  - Outcome: passed with no output for the staged `network_matrix.yaml` slice.

## Commit

- Network coverage commit: `fb10d43576487ce51c690021f99dc0840c592f9c`

## Deferred Behavior

- TLS listener and TLS outbound option behavior is intentionally deferred because local deterministic TLS setup is not present in this slice and would require certificate/key fixtures.
- Successful IPv6 listener loopback is intentionally deferred because IPv6 socket availability is environment-dependent; this slice covers deterministic IPv4 behavior and IPv6 option discrimination without requiring an IPv6-capable local bind.
- Disabled outbound-network rows were not executed in this Toast run because the WSL Toast oracle reports `option.OUTBOUND_NETWORK` enabled; they are present and gated for disabled-profile runs.
