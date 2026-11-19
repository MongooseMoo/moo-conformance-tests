# test/scatter-binding-order

## Goal

Pin, as Toast-verified conformance tests, the order in which a scatter
assignment binds its targets and evaluates optional defaults: optionals filled
left to right, a rest target between optionals, defaults that read variables
bound by the same scatter, defaults with side effects, and a target name used
in a default or twice in one scatter.

## State

`src/moo_conformance/_tests/language/scatter_binding_order.yaml` holds 32
tests (all named `scatter_order_*`). Every expectation is what the stock WSL
Toast oracle returned through the managed harness.

Toast source read (stock Toast `03af4fa2b53b418999f03566b646ee42bc7ea647`,
WSL `/root/src/toaststunt/src`):

- `execute.cc:2490-2557` `EOP_SCATTER`: one loop over all targets binds rest,
  required, and optional targets; an optional takes `list[i + offset]` while
  `nopt_avail > 0`, so spare values go to the leftmost optionals. The first
  unfilled optional that has a default sets `where`; after the loop the VM
  jumps to `where` (or to `done` if none).
- `code_gen.cc:849-890`: after the opcode's operand table the generator emits
  each optional default in source order as `<expr>; OP_PUT id; OP_POP`, each
  under its own label, then the `done` label. Jumping to the first unfilled
  default falls through every later default, in order.

Runs (all inside WSL Debian, managed harness, admission test kept in the
selection; fixture `src/moo_conformance/_db/Test.db`, 2035 bytes, SHA-256
`1a3f23ebb549e02ccf5341668425118fcdc935b977096add87bc2a8ef29d408e`, same as
the manifest's `database_checksum`):

Toast, from a barn checkout (`C:/Users/Q/code/barn`, `make conformance-toast`):

```
make conformance-toast CONFORMANCE_SUITE=/mnt/c/Users/Q/code/moo-conformance-tests-scatter \
  CONFORMANCE_ENV=$HOME/.cache/barn-make-conformance-linux-scatter K=scatter_order \
  CONFORMANCE_PATHS=/mnt/c/Users/Q/code/moo-conformance-tests-scatter/src/moo_conformance/_tests/language/scatter_binding_order.yaml
```

which expands to `uv run --project <suite> --frozen moo-conformance <file>
-m "admission or conformance" --server-db=<suite>/src/moo_conformance/_db/Test.db
--server-db-dir=<suite>/src/moo_conformance/_db/startup --moo-host=127.0.0.1
--oracle-profile-manifest=<barn>/profiles/toast/stock-wsl-testdb.json
--fail-on-unexpected-skip --strict-markers -k "capability_admission or (scatter_order)"
--server-command='"/root/src/toaststunt/build-release/moo" {db} {db}.new -p {port}'
--target-profile-manifest=<barn>/profiles/toast/stock-wsl-testdb.json -q`.

Result: `33 passed in 10.97s` (32 scatter tests + capability admission).
Toast binary SHA-256
`61dd1799d82f75e33cb9c42fe48bd1966199ad83fda2f6298e3a7f872cc613dd`.

Barn, `make conformance` with the same `CONFORMANCE_SUITE`, `CONFORMANCE_ENV`,
`K` and `CONFORMANCE_PATHS`, run from a scratch barn worktree (linux build by
the target's `go build -o bin/barn ./cmd/barn`, go1.27.1 linux/amd64):

- branch `origin/fuzz/checkpoint-lanes-export-path` (has "Bind every scatter
  target in OP_SCATTER, as Toast's EOP_SCATTER does"): `33 passed in 12.91s`.
- `origin/master` (tip "Merge pull request #900"): `9 failed, 24 passed in
  11.76s`. The nine failures:
  `scatter_order_rest_between_optionals_one_value`,
  `scatter_order_rest_between_optionals_default_of_unfilled`,
  `scatter_order_default_reads_later_required_target`,
  `scatter_order_default_reads_later_rest_target`,
  `scatter_order_default_reads_rhs_variable_rebound_by_rest`,
  `scatter_order_default_assigns_later_bound_target`,
  `scatter_order_default_error_keeps_bound_targets`,
  `scatter_order_duplicate_unfilled_optional_default_then_required`
  (expected 7, got 1),
  `scatter_order_duplicate_default_reads_required_duplicate`
  (expected 2, got E_VARNF).

Both scratch barn worktrees were removed after the runs.

## Decisions and why

- New file rather than appending to `language/scatter.yaml`: that file covers
  what each target kind does; this one covers the order of effects, and a
  separate suite name lets Barn's CI select it with one `-k`.
- Every unfilled optional without a default is given a prior value in the
  test, so the result shows "left alone" as a value instead of E_VARNF.
- Both claims that started this task are true on Toast:
  `c = 5; {a, ?b = c, @c} = {1}; return {a, b, c};` returns `{1, {}, {}}`, and
  `{?a, @r, ?b} = {1};` fills `a` (with priors `"a0"`, `"r0"`, `"b0"` the
  result is `{1, {}, "b0"}`).

## Surprises

- Toast accepts the same name twice in one scatter. `{?a = 7, a} = {1}` leaves
  `a` as 7: the required binding happens in the opcode, the default runs
  after it.
- With a rest target between two optionals, two values fill both optionals
  and the rest stays empty (`{?a, @r, ?b} = {1, 2}` gives `{1, {}, 2}`).

## Next step

Merge this only after Barn PR 892 (branch `fuzz/checkpoint-lanes-export-path`)
is on Barn's master: until then Barn master fails nine of these tests, and
Barn's CI runs this suite's `main`.
