# Notes: barn vs ToastStunt benchmark + optimization diagnosis

## Phase 1 (DONE): benchmark — toast ~4-17x faster than barn
See reports/benchmark-barn-vs-toast-20260619.md. Harness: bench/bench.py + bench/run_bench.sh.
Both WSL, both -O3/optimized. noop latency identical => gap is pure VM throughput.
Ratios: int 9.4x, float 9.1x, strcat 12x, list_append 17x (worst), list_index 8.7x,
tostr 4.2x (best), prop 7.4x, abs 7.7x, nested 9.3x.

## Phase 2 (DONE - analysis): WHY barn is slower (read the actual barn code)
Root causes, ranked by leverage:

1. BOXED VALUES = the ~9x baseline. types/value.go: `Value` is a Go INTERFACE.
   IntValue/FloatValue are structs (types/int.go). Every vm.Push(IntValue{...}) boxes
   into interface -> Go convT64 HEAP-ALLOCATES for any int >=256. 5M-add loop = ~5M
   allocs + GC. Toast Var is a value-typed tagged union = zero alloc for int math.
   FIX A (big, highest impact): make Value a tagged-union struct {typ; i int64; f float64;
   ptr for heap types}. Kills numeric allocs. Touches everything.
   FIX B (cheap, partial): intern small ints (-256..256). Limited.

2. ARITH HOT-PATH ORDERING (cheap win). vm/op_arith.go executeAdd checks string, then
   list, then int -> int (common) pays 4 failed type assertions first. Reorder numeric-first.

3. PER-INSTRUCTION CALL OVERHEAD. vm/vm.go: Step->CountsTick->Execute->executeXxx, several
   calls/op. syncContextTicks is cheap (checked, just int sub) - leave it. Inline tick count
   + immediate-int fast path = modest gain.

4. LIST APPEND O(n^2) full-copy = the 17x outlier. types/list.go:41 sliceList.Append does
   make+copy of WHOLE slice every call. MooList interface comment: "allows swapping impl later"
   (seam exists). Fix: (a) compiler detects `var = {@var, expr}` -> in-place append opcode that
   mutates when list not aliased (mirrors Toast refcount==1), or (b) growable backing + COW.
   Expected: O(n^2)->amortized O(n), collapses 17x toward baseline.

5. STRING CONCAT O(n^2) = 12x. Same accumulation pattern. Same idiom fix / builder.

6. tostr/stringify uses fmt.Sprintf("%d") (types/int.go:16). Replace w/ strconv.FormatInt.
   Quick safe win for tostr workload + all stringify.

## Proposed attack order
Quick wins first (reorder add #2, strconv #6) - cheap/safe/measurable.
Then PROVE ranking with CPU profile before the big value-repr refactor (#1).
Then list/string append idiom (#4,#5).

## NEXT STEP (recommended, awaiting Q go-ahead)
Build `go test -bench -cpuprofile` harness driving VM directly (no socket) on these workloads
to get allocs-vs-dispatch flame graph BEFORE touching code. No existing VM benchmarks in barn.
Need to find compile(MOO src)->Program->Run API (check vm/*_test.go and server/scheduler_eval.go).

## Phase 3 (IN PROGRESS): profiling harness + evidence (worktree)
ISOLATION: other agents active in barn (main=spike/world-seam dirty, worktree barn-runtime-move
=feat/runtime-package). I made my OWN worktree: ~/code/barn-vm-perf branch perf/vm-bench off HEAD e2e3093.
Harness: vm/perf_bench_test.go (BenchmarkVM, drives VM directly, no socket). Run in WSL:
  cd /mnt/c/Users/Q/code/barn-vm-perf && go test ./vm -run='^$' -bench=BenchmarkVM -benchmem
Pre-existing vet warning ReadByte signature is NOT mine (stack.go, ignore).

### go test -benchmem results (Linux/WSL)
int_arith_1M:   116ms  16MB   2,000,000 allocs  => 2 heap allocs PER iteration (result box + loop var box)
float_arith_1M: 118ms  16MB   2,000,000 allocs
tostr_200k:     114ms  21MB   2,000,000 allocs  => 10 allocs/iter (fmt.Sprintf!)
string_concat:  14ms   53MB   29k allocs        => O(n^2) BYTES
list_append_10k:1142ms 1.67GB 91k allocs        => O(n^2) full-copy, memory-bandwidth bound (THE 17x)
list_index_1M:  222ms  45MB   3.5M allocs
nested_1k(1M):  115ms  14MB   1.75M allocs

### CPU profile int_arith (pprof -top): DISPATCH dominates, alloc is ~2nd
Step 26% / Execute 14% / CurrentFrame 9% (inline, called many times/instr!) / executeLoop 6% /
CountsTick 5% / Push 4% / Pop 4% / ReadByte 3.5%  => dispatch machinery ~55-60%
convT64 (boxing) cum 15% / mallocgc 12% / mallocgcTiny 9%  => alloc+GC ~20-25%
KEY REFRAME: for arithmetic, per-instruction DISPATCH overhead (function-call layering
Step->Execute->executeAdd + repeated CurrentFrame + ReadByte + CountsTick) costs MORE than boxing.
=> Cheap wins: cache CurrentFrame ptr in loop; inline Step body into executeLoop; fast-path
   immediate int. PLUS reorder executeAdd numeric-first. PLUS unbox (#1) still ~20%.
list_append is a SEPARATE axis (O(n^2) copy) - needs in-place append / capacity growth.

### CPU profile list_append (pprof -top): TWO compounding O(n) per append
ValueBytes 16% flat/26% cum (THE surprise: CheckListLimit->ValueBytes walks WHOLE list via Get
every append to sum byte size, builtins/limits.go:331 + 268; limit=max_list_value_bytes, real check
but should be O(1) incremental) + sliceList.Get 11.6% + GC (futex/findObject/scanobject/memclr ~30%).
ALSO executeListAppend/Extend (op_list.go:59,86) rebuilt slice via Get(i) loop instead of bulk copy.
`{@l,i}` compiles to LIST_EXTEND(l)+LIST_APPEND(i) => TWO full copies + TWO ValueBytes per iteration.

### QUICK-WIN PROTOTYPE (done on perf/vm-bench) + measured delta (benchtime=5x)
Edits: (1) op_arith.go executeAdd numeric-first reorder; (2) types/int.go String() Sprintf->strconv.FormatInt;
(3) op_list.go executeListAppend/Extend Get-loop -> bulk copy(Elements()).
Result before->after: int 116->112ms(~3%), float 118->115(~3%), strconcat 14.3->10.6(~26%),
list_append 1142->907ms(~21%, bytes/allocs unchanged - copy volume same, ValueBytes still O(n)),
tostr 114->110(~3%, allocs STILL 10/iter).
=> tostr fix MISSED: tostr uses builtins/types.go valueToStr(), NOT IntValue.String(). Need to fix valueToStr.
=> Honest takeaway: surface reorders give single-digit% on arith (dispatch+boxing dominate, untouched),
   ~20-26% on list/string from bulk-copy. BIG multipliers need structural fixes:
   (A) unbox Value (tagged union) - kills 2 allocs/iter everywhere; (B) O(1) list size accounting
   (cache bytes on list) - kills ValueBytes O(n); (C) dispatch inline / cache CurrentFrame.

### DONE: valueToStr fixed (builtins/types.go:52 Sprintf->strconv). tostr 114->97ms, -200k allocs.
### DONE: go test ./vm ./types ./builtins all PASS. Repo-wide FAILs (conformance, db/format)
  are pre-existing missing-fixture/env errors, NOT mine (verified: "no such file/dir" messages).
### DONE: Phase-3 report = reports/barn-vm-optimization-20260619.md
### Final deltas (10x): int 116->110(5%), float 118->112(5%), strcat 14.3->11.7(18%),
  list_append 1142->955(16%), tostr 114->97(15%).

### STATE: changes UNCOMMITTED in worktree ~/code/barn-vm-perf (branch perf/vm-bench).
  Files: vm/perf_bench_test.go (new), vm/op_arith.go, vm/op_list.go, types/int.go, builtins/types.go.
  Did NOT commit (Q's rule: commit only when asked). Offered to commit/PR.

### BIG structural wins for next phase (ranked): 1) unbox Value->tagged union (kills 2 allocs/iter
  everywhere, ~2-4x arith, big blast radius); 2) O(1) list size cache (kills 26% ValueBytes);
  3) amortized/in-place list append (collapses 17x); 4) dispatch inline + cache CurrentFrame (~55% share).
  Recommended order: 2 + 4 first (small), then 1 (rewrite, harness as A/B gate), then 3.

## Servers: stopped. Re-run bench: `bash bench/run_bench.sh` from WSL.
