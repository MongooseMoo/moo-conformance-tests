# Benchmark: barn vs ToastStunt (MOO VM execution speed)

**Date:** 2026-06-19
**Both servers on WSL2** (Linux 6.18, x86-64), both optimized builds.

## TL;DR

ToastStunt (C++) executes MOO bytecode roughly **4×–17× faster than barn (Go)**
across CPU-bound workloads. Round-trip latency for a trivial eval is identical
(~0.3 ms), so the gap is pure interpreter/VM throughput, not network or protocol
overhead. barn's weakest spots are list append (~17×) and string concatenation
(~12×); its closest is `tostr()`-heavy work (~4×).

## Is there a "benchmarking aspect" in this repo?

No. `moo-conformance-tests` is purely a **correctness** conformance suite (YAML
tests over a TCP socket). The only "profile"/"gate" code (`profile_gate.py`)
compares *feature manifests* (e.g. `OUTBOUND_NETWORK`) to decide whether a
correctness comparison is even valid — it has nothing to do with performance.
barn's only Go `Benchmark*` measures YAML test-loading, not server execution.

So this benchmark was built from scratch (`bench/bench.py`, `bench/run_bench.sh`).

## Method

- **Workloads:** identical MOO source sent to each server as a `;` eval. Every
  workload has a fixed iteration count, so both servers do exactly the same work.
  Return values are checked equal to an expected value where known (all matched —
  see "fair work" below).
- **Timing:** wall-clock `perf_counter` around each `transport.execute()`
  round-trip, reusing the suite's `SocketTransport`. One untimed warm-up, then
  `min` and `[median]` of 5 timed runs. `min` is the cleanest signal (least
  scheduler/GC noise).
- **Tick limit:** MOO caps a task at ~30 000 ticks by default, which kills any
  large loop. The harness raises `$server_options.{fg,bg}_{ticks,seconds}` to
  2e9 / 30 000 and calls `load_server_options()` on **both** servers identically
  before timing.
- **Fairness controls:**
  - Both built optimized: toast `Release -O3 -march=native -DNDEBUG`
    (`build/CMakeCache.txt`); barn plain `go build` (optimizer on, no race/debug).
  - DB copied to Linux-local `/tmp` to avoid 9p filesystem noise (matters only at
    startup; no disk I/O during eval anyway).
  - Identical `Test.db`, identical wizard login, identical client, same machine.
  - `noop_latency` ~0.3 ms on both confirms the transport layer is not skewing
    compute numbers.

## Results

`min ms [median ms]` over 5 runs. Lower is faster. `ratio` = barn / toast.

| workload | toast (ms) | barn (ms) | barn ÷ toast |
|---|---:|---:|---:|
| noop_latency (round-trip) | 0.3 | 0.3 | ~1.0× |
| int_arith — 5M adds | 66 | 626 | 9.4× |
| float_arith — 5M adds | 69 | 644 | 9.1× |
| string_concat — 50k | 20 | 277 | 12–13× |
| list_append — 30k (`{@l, i}`) | 785 | 13 300 | ~17× |
| list_index — 1M | 28 | 240 | 8.7× |
| builtin tostr() — 1M | 149 | 638 | 4.2× |
| prop_access — 1M | 60 | 450 | 7.4× |
| abs() loop — 200k | 9 | 70 | 7.7× |
| nested loop — 2500×2500 | 85 | 800 | 9.3× |

(Values from two consecutive runs; stable within noise.)

## Observations

- **List append is barn's worst case (~17×).** `l = {@l, i}` is O(n²) on both
  (each step copies the list), but barn's per-copy constant + GC pressure makes
  it much costlier. 30k appends already take ~13 s on barn vs ~0.8 s on toast.
- **String concat (~12×)** is the next worst, same copy-heavy pattern.
- **`tostr()` (~4×) is barn's best ratio** — most time is spent inside the
  builtin (int→string formatting), which narrows the gap.
- Plain arithmetic and loop control sit around **9×**, a reasonable proxy for raw
  interpreter dispatch cost.

## Reproduce

From WSL:

```bash
bash bench/run_bench.sh
```

Or manually (servers in WSL, harness from anywhere that reaches localhost):

```bash
# WSL
cp src/moo_conformance/_db/Test.db /tmp/toast_in.db
cp src/moo_conformance/_db/Test.db /tmp/barn_in.db
~/src/toaststunt/moo /tmp/toast_in.db /tmp/toast_out.db -p 7801 &
( cd ~/code/barn && go build -o /tmp/barn_linux ./cmd/barn )
/tmp/barn_linux -db /tmp/barn_in.db -port 7802 &
uv run python bench/bench.py toast=7801 barn=7802
```

To rebuild toast on Linux if the ELF `moo` is missing:
`cd ~/src/toaststunt && cmake -S . -B build -DCMAKE_BUILD_TYPE=Release && cmake --build build -j`.

## Caveats

- Measures single-connection, sequential eval throughput — not concurrency,
  scheduler fairness, checkpointing, or DB load/save speed.
- `-march=native` gives toast machine-specific codegen; a portable build would be
  marginally slower but not enough to change the order of magnitude.
- Workload set is small/synthetic; representative of VM hot paths, not a real MUD
  workload.
