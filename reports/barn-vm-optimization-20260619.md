# barn VM optimization — diagnosis, profile, and first deltas

**Date:** 2026-06-19
**Worktree:** `~/code/barn-vm-perf` branch `perf/vm-bench` (isolated; other agents hold
`spike/world-seam` and `feat/runtime-package` — untouched).
**Harness:** `vm/perf_bench_test.go` (`BenchmarkVM`) drives the VM directly, no socket,
so profiles isolate interpreter cost. Run in WSL:
`go test ./vm -run='^$' -bench=BenchmarkVM -benchmem`.

## Why barn is 4–17× slower than ToastStunt (measured, not guessed)

Two independent cost axes, confirmed by `go test -benchmem` + `pprof`:

### Axis 1 — per-instruction overhead (the ~9× arithmetic baseline)
`go test -benchmem` on `int_arith_1M`: **2,000,000 allocs / 1M iterations = 2 heap
allocations per loop iteration.** `Value` is a Go **interface** (`types/value.go`) and
`IntValue`/`FloatValue` are structs, so every result and every loop-variable box goes
through `runtime.convT64` → heap (Go only stack-caches ints < 256). ToastStunt's `Var`
is a value-typed tagged union: zero alloc for int math.

CPU profile (`int_arith`, `pprof -top`):
- **Dispatch machinery ~55–60%:** `Step` 26%, `Execute` 14%, `CurrentFrame` 9% (inlined
  but called several times per instruction), `executeLoop` 6%, `CountsTick` 5%,
  `Push`/`Pop` ~4% each, `ReadByte` 3.5%.
- **Allocation/GC ~20–25%:** `convT64` 15% cum, `mallocgc` 12%, `mallocgcTiny` 9%.

So for arithmetic, **dispatch costs more than boxing** — both need structural fixes.

### Axis 2 — O(n²) accumulation (the 12–17× outliers)
`list_append_10k`: **1.67 GB allocated for 10k appends.** CPU profile shows the killer is
**two compounding O(n) passes per append**:
1. `CheckListLimit → builtins.ValueBytes` (`builtins/limits.go:331`,`268`) walks the
   **entire list** via `Get(i)` on *every* append to re-sum its byte size — **16% flat /
   26% cumulative**, the single hottest function.
2. `executeListAppend`/`executeListExtend` (`vm/op_list.go`) rebuilt the slice element by
   element via `Get(i)` instead of a bulk `copy`.

And `{@l, i}` compiles to `LIST_EXTEND(l)` + `LIST_APPEND(i)` → **two full copies + two
`ValueBytes` walks per loop iteration.** String concat (`s = s + "x"`) is the same shape.

## Quick wins prototyped (safe, semantics-preserving) + measured

| change | file |
|---|---|
| `executeAdd`: test numeric operands **before** string/list | `vm/op_arith.go` |
| `IntValue.String()` + `valueToStr()`: `fmt.Sprintf("%d")` → `strconv.FormatInt` | `types/int.go`, `builtins/types.go` |
| list append/extend: `Get(i)` loop → bulk `copy(Elements())` | `vm/op_list.go` |

`go test ./vm/ ./types/ ./builtins/` → **all pass** (the only repo-wide FAILs are
pre-existing missing-fixture errors in `conformance`/`db.format`, unrelated).

### Delta (ns/op, WSL)

| workload | before | after | improvement |
|---|---:|---:|---:|
| int_arith_1M | 116 ms | 110 ms | ~5% |
| float_arith_1M | 118 ms | 112 ms | ~5% |
| string_concat_10k | 14.3 ms | 11.7 ms | ~18% |
| list_append_10k | 1142 ms | 955 ms | ~16% |
| tostr_200k | 114 ms | 97 ms | ~15% (−200k allocs) |

**Honest read:** surface reorders buy single digits on arithmetic (dispatch + boxing
dominate and are untouched) and ~15–18% on list/string/tostr. The big multipliers need
structural work.

## The structural wins (ranked by leverage), for a funded next phase

1. **Unbox `Value` into a tagged-union struct** `{typ; i int64; f float64; ptr}`.
   Eliminates the 2 allocs/iteration across *every* workload. Biggest single lever;
   biggest blast radius (touches all of `vm/` + `types/`). Est. 2–4× on arithmetic.
2. **O(1) list size accounting** — cache byte-size on the list value so `CheckListLimit`
   stops re-walking. Kills the 26% `ValueBytes` cost; turns the limit check O(n)→O(1).
3. **Amortized list growth / in-place append when unaliased** (ToastStunt's refcount==1
   trick) — turns `{@var, x}` accumulation from O(n²)→amortized O(n). Collapses the 17×.
4. **Dispatch inlining** — cache `CurrentFrame` in the `executeLoop` register, inline the
   `Step` body and the immediate-int fast path, fold `CountsTick` into a table. Attacks the
   ~55% dispatch share.

Recommended order: land #2 (small, kills a 26% hotspot) and #4 (mechanical) first, then
commit to #1 (the rewrite) with the harness as the A/B gate, then #3.

## Reproduce
```bash
# WSL, in the worktree
cd ~/code/barn-vm-perf
go test ./vm -run='^$' -bench=BenchmarkVM -benchmem
go test ./vm -run='^$' -bench=BenchmarkVM/list_append -cpuprofile=/tmp/c.prof -o /tmp/vm.test
go tool pprof -top -nodecount=15 /tmp/c.prof
```
