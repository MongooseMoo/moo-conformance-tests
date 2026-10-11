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

## Phase 4 (IN PROGRESS): #2 list-size + #4 dispatch, separate worktrees off perf/vm-bench (558cc99)
Worktrees: ~/code/barn-opt2-listsize (perf/list-size), ~/code/barn-opt4-dispatch (perf/dispatch).
Also note other agents: spike/world-seam, spike/verbcache active - stay clear.

### #2 O(1) list size accounting (kills ValueBytes 26% hotspot)
Problem: CheckListLimit->ValueBytes walks whole list via Get every append (O(n^2)).
Design: move size logic to types.ValueBytes (no import cycle); cache byteSize on sliceList,
maintained INCREMENTALLY on append/concat (new=old+elemBytes, O(1)); builtins.ValueBytes delegates.
All 8 sliceList constructors in types/list.go; only sliceList implements MooList; MapValue.Pairs() [][2]Value.
CORRECTNESS GATE: conformance value_bytes.yaml + limits.yaml must still pass (cached size == computed size).
Progress: #2 EDITS DONE in worktree barn-opt2-listsize:
  - types/value_bytes.go: NEW. types.ValueBytes + valueVarSize=16, listVarOverhead=32.
  - types/list.go: byteSize field(-1=lazy), newSliceList/newSliceListSized, ByteSize() memo on
    sliceList+ListValue, incremental Append & Set, lazy Slice/Insert/Delete/NewList, NewEmptyList sized,
    MooList interface +ByteSize(), added ListValue.Concat(other) incremental.
  - builtins/limits.go: ValueBytes now delegates to types.ValueBytes.
  - vm/op_list.go: executeListAppend->list.Append(elem); executeListExtend->list.Concat(src).
TODO NEXT: go build ./...; go test ./vm ./types ./builtins; bench list_append (expect big drop);
  run conformance value_bytes.yaml + limits.yaml against a barn binary built from this worktree.

### #2 RESULT (DONE, verified): list_append 955->608ms (-36%; cum 1142->608 -47%). string/list_index flat (expected).
  go test vm/types/builtins PASS. Conformance value_bytes+limits: 75 passed. FULL SUITE opt2: 3871 passed,
  131 skipped, 0 FAIL. Baseline full suite running (bg b0bjpylj0) to confirm 3871 matches = no regression.
  barn_opt2.exe + barn_base.exe built in respective worktrees.

### #2 MERGE-READY: baseline full suite = 3871 passed/131 skipped, IDENTICAL to opt2 => ZERO regression.
  Just needs commit on perf/list-size. (Delete barn_opt2.exe/barn_base.exe before commit - build artifacts.)

### #2 COMMITTED: a1fd7db on perf/list-size (4 files). MERGE-READY.

### #4 dispatch (worktree barn-opt4-dispatch) - EDITS DONE
DONE: vm.frame field + pushFrame/popFrame helpers; CurrentFrame()->vm.frame (O(1));
  ALL Frames mutations converted (op_verb,registry,vm.go,stack.go); inlined Step into executeLoop.
  go test vm/types/builtins PASS.
BENCH (vs perf/vm-bench baseline): int 110->97(~12%), float 112->99(~11%), nested 115->99(~14%),
  list_index 217->189(~13%), tostr 97->92(~5%); string/list_append flat (not dispatch-bound). 
GATE PASSED: full suite opt4 = 3871/131, identical to baseline. ZERO regression.

### BOTH MERGE-READY (Phase 4 complete)
- #2 perf/list-size  a1fd7db (types/value_bytes.go,list.go; builtins/limits.go; vm/op_list.go)
- #4 perf/dispatch   d644c8f (vm/vm.go,stack.go,op_verb.go,registry.go)
- Both fork perf/vm-bench (558cc99). DISJOINT files -> verified compose cleanly:
  perf/combined merged both w/ no conflicts, tests green, deltas STACK.
- Combined bench vs perf/vm-bench baseline: int 110->98, float 112->101, list_append 955->606,
  list_index 217->185, nested 115->97. (each win shows up; no interaction.)
- Each verified independently: go test vm/types/builtins PASS + FULL conformance 3871/131 (no regression).
- Build artifacts removed; worktrees barn-opt2-listsize, barn-opt4-dispatch remain. perf/combined
  branch exists (worktree removed) as a ready merged branch if Q wants it.

### Cumulative vs ORIGINAL barn (before any perf work):
  int 116->98(-15%), list_append 1142->606(-47%), tostr 114->94(-18%), string 14.3->12(-16%), nested 115->97(-15%).
### Still O(n^2) on list_append/string (copy volume) = future #3 (amortized/in-place append).
### Biggest remaining lever untouched = #1 unbox Value (2 allocs/iter everywhere).

## Phase 6 RESEARCH: unboxing Value + the TYPE_NONE / sentinel question (no code yet)

### ToastStunt (authority) - src/include/structures.h var_type enum:
  TYPE_INT=0, TYPE_OBJ=1, _TYPE_STR=2, TYPE_ERR=3, _TYPE_LIST=4 (user-visible),
  TYPE_CLEAR=5 (clear property slots), TYPE_NONE=6 (UNINITIALIZED MOO VARIABLES <- our case),
  TYPE_CATCH=7, TYPE_FINALLY=8 (on-stack VM markers), _TYPE_FLOAT=9, _TYPE_MAP=10, _TYPE_ITER=11,
  _TYPE_ANON=12, _TYPE_WAIF=13, TYPE_BOOL=14. TYPE_COMPLEX_FLAG=0x80 OR'd into runtime complex
  (heap/refcounted) types; DB stores low 7 bits. Var = 8-byte union(str/num/obj/err/list/tree/double/
  anon/waif/bool) + type tag (~16B); `num` reused for CATCH/FINALLY payloads.
  => Toast HAS our concept first-class: TYPE_NONE = uninitialized var. is_none() == (type==TYPE_NONE).
  => eval_env.cc:44 EXPLICITLY sets locals to TYPE_NONE (does NOT rely on zero-init). Global `zero`
     (int 0) is the benign default used elsewhere, distinct from none.

### barn today (mechanism differs, semantics same):
  - typecode.go: only user-visible types (INT=0..BOOL=14, toast numbers). NO none/clear/catch/finally.
  - UnboundValue = separate Go struct{} type; Type() LIES (returns TYPE_INT, "not externally observable").
    Detected by type assertion at only 6 non-test sites -> these become `v.kind==NONE`.
  - try/catch: SEPARATE ExceptStack []Handler on StackFrame (program.go/control.go), NOT value-stack
    markers => barn does NOT need CATCH/FINALLY value kinds.
  - clear properties: `Clear bool` flag on the slot (db/store/object.go:47) => NOT a value kind.
  - "232 nil checks" was too broad: sampled sites are vm.Context!=nil / Task!=nil (POINTER nils),
    NOT Value nils. Real Value-nil sites are few; conversion sweep will enumerate. Today zero-value
    Value = nil = unusable (panics) -> maps cleanly to NONE = unusable/fail-loud.

### DESIGN CONCLUSION (sentinel):
  - Need exactly ONE internal sentinel: NONE (= toast TYPE_NONE = barn UnboundValue). Not catch/finally
    (Handler stack), not clear (Clear bool).
  - Use an INTERNAL `kind` tag SEPARATE from MOO-visible TypeCode, with kind 0 = NONE so the struct
    ZERO VALUE is none. Defuses the TYPE_INT=0 hazard: make([]Value,n) locals = auto all-none (can drop
    barn's explicit init loop), and accidental Value{} reads as none (fail-loud E_VARNF) not silent int 0.
  - Type()/typeof maps kind->TypeCode (toast numbers); none has no user-visible TypeCode (reading an
    uninit var raises E_VARNF before typeof, per toast).
  - Proposed struct (safe-wide, no unsafe, ~40B): { kind; num uint64 (int/bool/obj/err/float-bits);
    str string; ref any (list/map/anon/waif) }. Compact unsafe.Pointer variant ~24B = later option.
  - Mapping today->tomorrow is clean: nil Value -> NONE; UnboundValue -> NONE.

### nil-vs-unbound AUDIT (scout, opus; report: reports/nil-value-vs-unbound-audit.md). VERIFIED.
  VERDICT: ZERO sites require nil-Value and UnboundValue to stay distinct. Collapse to NONE is SAFE.
  - UnboundValue: 5 construct sites (all vm/), 1 functional detect (vm/vm.go:398 OP_GET_VAR -> E_VARNF).
    Lives only in frame.Locals, trapped at the single read path before it can escape to Result.Val /
    VMException / Property.Value / Environment / map/list storage. Never meets a meaning-carrying nil.
  - ~12 meaningful nil-Value sites, all SAFE to collapse (port `== nil` -> `kind==NONE`; re-express
    Equal/String nil guards in types/int.go:22, float.go:42, bool.go:23, list.go:92).
  - Two design carries (NOT blockers):
    1. CLEAR-property nil: Property.Value==nil means "clear/inherit" (db/format/reader_value.go:63 etc.),
       backed by Property.Clear bool. Safe, but NONE must stay reliably detectable as the zero value.
    2. PRE-EXISTING possible toast divergence (independent of unboxing): OP_INDEX_SET/OP_RANGE_SET
       (vm/op_index.go:64,:100) read Locals WITHOUT the unbound check, so `x[1]=5` on an unbound x gives
       E_TYPE, not E_VARNF (toast raises E_VARNF reading x first). Collapse PRESERVES current behavior.
       Flag as separate conformance question for Q; not part of the unbox.

### => SENTINEL QUESTION FULLY RESOLVED. Ready to design+code the unbox when Q lands his work.
###    Plan: no shims, uniform-opus subagents per package, compiler-as-checklist, gates: build->go test
###    ->full conformance 3871/131->bench (confirm allocs/iter ~0). Fresh worktree off updated master.

## Phase 6 EXECUTION: UNBOX (IN PROGRESS). Worktree ~/code/barn-unbox, branch perf/unbox-value off master e67f970.
(My perf commits 027e358/fb438f5/507b3b7 confirmed present on master; Q's B1-B5 on top.)

### DESIGN LOCKED:
- types.Value is now a CONCRETE STRUCT (tagged union): {kind Kind; num uint64; str string; ref any}.
  num holds int64/float64bits/ObjID/ErrorCode/bool. ref holds MooList/MooMap/WaifValue.
- Kind enum: KindNone=0 (zero value = unbound/none, Toast TYPE_NONE), Int,Float,Str,Obj,Anon,Err,Bool,List,Map,Waif.
- Internal Kind SEPARATE from MOO TypeCode (so none=0 while TYPE_INT=0). Type() maps kind->TypeCode.
- nil Value AND UnboundValue BOTH collapse to KindNone (audit said safe). None()/Unbound() both return Value{}.
- Constructors NewInt/NewFloat/NewStr/NewObj/NewAnon/NewErr/NewBool return Value.
- HEAP wrapper types ListValue/MapValue/WaifValue SURVIVE as rich views (keep their methods).
  Public NewList/NewEmptyList/NewMap/NewEmptyMap/NewWaif return Value. Access via v.List()/v.Map()/v.Waif().
  Need AsValue() on each wrapper (package-private newListVal/newMapVal/newWaifVal exist).
- Accessors: unchecked Int()/Float()/Str()/ObjNum()/ErrCode()/Bool()/List()/Map()/Waif();
  checked AsInt()/AsFloat()/AsStr()/AsErr()/AsBool()/AsObjID()/AsList()/AsMap()/AsWaif().
- CRITICAL semantics preserved: StrValue.Equal was CASE-INSENSITIVE (strings.EqualFold) -> done in Value.Equal.
  Float NaN!=NaN done. String() quoting/~XX binary encoding + float .0 + obj #N/*#N done.

### DONE in types/: value.go (struct+ctors+accessors+Truthy+Equal), value_string.go (String/formatFloat/quoteMooString).
### TODO types/ (make pkg compile - THE keystone, by hand):
- DELETE folded scalar files: int.go float.go bool.go str.go error.go unbound.go.
- obj.go: DELETE ObjValue type BUT KEEP consts NOTHING/AMBIGUOUS/FAILED_MATCH (used e.g. builtins/objects_hierarchy.go:437). Move consts to objid.go.
- list.go: NewList/NewEmptyList -> return Value; add ListValue.AsValue(); String()/Equal use Value methods (already do).
- map.go: NewMap/NewEmptyMap -> Value; add MapValue.AsValue(); REWRITE keyHash/CompareMapKeys/IsValidMapKey/
  IsValidBuiltinMapKey/GetWithCase that type-switch on Value -> switch on kind/accessors.
- waif.go: NewWaif -> Value; add WaifValue.AsValue(); equalMaps uses Value.Equal.
- result.go: check it (Ok/Err/Result.Val type).
- value_bytes.go: already switches on types.X types -> REWRITE to switch v.Kind().
- Then: go build ./types/ ; go test ./types/. THEN dispatch uniform-opus subagents per dependent package.
### NOTE: gopls "undefined" diagnostics in worktree are EDITOR NOISE (worktree not in workspace); go build is truth.

### PROGRESS UPDATE (types/ conversion, by hand):
DONE: value.go, value_string.go.
DONE map.go: keyHash kind-prefixed; goMap.Get nil->Value{}; NewMap/NewEmptyMap return Value +AsValue();
  CompareMapKeys uses Kind/accessors (+cmpInt64/cmpFloat64 helpers); MapValue.Equal(other MapValue);
  GetWithCase uses AsStr + Value{}.
DONE list.go: NewList/NewEmptyList return Value; +NewListValue (view ctor) +AsValue(); String() uses IsNone;
  ListValue.Equal(other ListValue).
KEY API RULE for sweep: wrapper Equal methods now take the WRAPPER type (ListValue/MapValue/WaifValue),
  NOT Value. value.go dispatches v.List().Equal(o.List()) etc.
STILL TODO types/: 
  - waif.go: NewWaif->Value +AsValue(); WaifValue.Equal(other WaifValue); equalMaps uses Value.Equal.
  - value_bytes.go: switch v.(type) -> switch v.Kind() (uses accessors for str len etc).
  - obj.go: DELETE ObjValue struct+methods, KEEP consts NOTHING/AMBIGUOUS/FAILED_MATCH (move to objid.go).
  - DELETE int.go float.go bool.go str.go error.go unbound.go (folded into Value).
  - result.go: read+check Ok/Err/Result.Val.
  - THEN go build ./types/ + go test ./types/ until green. THEN dispatch subagents per dependent pkg.
CAUTION discovered: ListValue.String had `elem==nil -> "0"`; preserved as elem.IsNone()->"0".
  StrValue.Equal case-insensitive preserved. Map keyHash MUST stay kind-prefixed or int5/str"5" collide.

### *** go build ./types/ IS GREEN *** (keystone package compiles). 2026-06-20.
DONE waif.go (NewWaif->Value, NewWaifValue view, AsValue, Equal(WaifValue)); value_bytes.go (Kind switch);
  objid.go (added NOTHING/AMBIGUOUS/FAILED_MATCH consts); deleted obj/int/float/bool/str/error/unbound.go;
  sliceList.Get nil->Value{}; result.go unchanged (Value is struct field, fine).
NEXT IMMEDIATE: go test ./types/ (may have failing unit tests referencing old types e.g. IntValue{} -
  those test files need conversion too; decide fix-vs-delete per test). THEN dispatch uniform-opus
  subagents, one per dependent package, to convert call sites (compiler-as-checklist).
PACKAGE DEPENDENCY ORDER for sweep (convert nearest-to-types first): builtins, db/store, db/format,
  vm, task, server, trace, cmd. Each agent: own worktree? NO - single worktree, but packages are
  mostly file-disjoint; run SEQUENTIALLY by dep order OR parallel on disjoint dirs. Gate after each:
  go build ./<pkg>/. Final: go build ./... -> go test ./... -> full conformance 3871/131 -> bench allocs.
SWEEP API CHEATSHEET for agents:
  v.(types.IntValue){.Val} -> v.AsInt() or v.Int()/v.IsInt(); same Float/Str(Value())/Obj(ID())/Err(Code())/Bool.
  types.IntValue{Val:x} -> types.NewInt(x); NewStr/NewFloat/NewObj/NewAnon/NewErr/NewBool unchanged-ish (return Value).
  switch v.(type){case types.IntValue:...} -> switch v.Kind(){case types.KindInt:...}.
  types.NewList/NewMap/NewWaif now return Value (were wrapper). For wrapper ops use v.List()/v.Map()/v.Waif()
  then .AsValue() to rewrap. ListValue/MapValue/WaifValue .Equal now take the WRAPPER type not Value.
  UnboundValue{} -> types.Unbound() (==None==Value{}); detect via v.IsNone()/IsUnbound().
  Value can't be nil: `x == nil` -> `x.IsNone()`; `return nil`(Value ctx) -> `return types.Value{}`.
  StrValue.Value() -> v.Str(); ObjValue.ID() -> v.ObjNum(); ObjValue.IsAnonymous() -> v.IsAnonymous().

### *** KEYSTONE COMMITTED: c65fb40 on perf/unbox-value. types/ build+test GREEN. *** 2026-06-20.
SWEEP SCOPE (files using old types.XxxValue, non-test): builtins 27, vm 16, db/store 4, server 3,
  db/format 3, conformance 2, bytecode 1. (Plus nil-Value/.Value()/.ID() sites surface only at build.)
PLAN: dispatch uniform-opus subagents per package in DEPENDENCY WAVES (all in the ONE worktree
  ~/code/barn-unbox; packages are file-disjoint so concurrent within a wave is safe). Verify
  `go build ./<pkg>/` between waves. Need to confirm import DAG before assigning waves.
  Tentative waves: W1 (import only types): db/store, db/format, trace, bytecode, task.
  W2: builtins (needs db/store). W3: vm (needs builtins/task/trace). W4: server, conformance, cmd.
### DEFENDER SCARE (2026-06-20, Q paused sweep): "weird windows trojan defender errors."
INVESTIGATION (read-only):
- go.mod/go.sum UNCHANGED vs master (git diff --stat empty) => WE ADDED ZERO DEPENDENCIES.
  All edits (types/, bytecode, trace by agents) used only stdlib (math/strings/strconv/fmt/sort).
  Existing deps (go-crypt, golang.org/x/crypto, yaml.v3, modernc sqlite, websocket...) all pre-date us.
- HYPOTHESIS: trigger is freshly-built UNSIGNED .exe MOO-server binaries (open listening sockets ->
  Defender heuristic). I built several across phases: barn_opt2.exe, barn_base.exe, barn_integrate.exe,
  barn_masterbase.exe, barn_opt4.exe (some deleted). Plus agents ran go build/test (temp test binaries).
- TODO: enumerate .exe under all barn worktrees; that's the likely culprit, not a dependency.
DEFENDER RESOLVED: detection was C:\...\Temp\go-build*/a.out.exe = Go's OWN temp test binary,
  flagged Trojan:Win32/Bearfoos.A!ml (!ml = ML heuristic, known FP on unsigned static Go binaries).
  NOT a dependency (go.mod/sum unchanged), NOT our logic. Q said proceed. MITIGATION: run ALL go
  build/test in WSL (wsl.exe -e bash -lc 'cd /mnt/c/...; go ...') so outputs land on Linux fs (GOCACHE
  ~/.cache/go-build), invisible to Windows Defender. Final conformance binary: build as WSL ELF too.
  Did NOT change Defender settings (Q's machine, his call). DO NOT run Windows-side `cd /c/... && go`.

WAVE-1 DONE + COMMITTED: 771714b on perf/unbox-value. trace, bytecode, db/store converted.
  Verified WSL: go build ./types/ ./trace/ ./bytecode/ ./db/store/ = RC 0; each unit-test green (db/store 7/7).
  Keystone types/ = c65fb40. So branch has: c65fb40 (types) -> 771714b (wave1).
WAVE-2 DONE+COMMITTED: 8d03a54 (task, db/format). Branch: c65fb40->771714b->8d03a54.
  db/format only test fail = pre-existing TestLoadMongooseSnapshot (missing fixture).
WAVE-3 IN PROGRESS: builtins (27 files, ~1200 broad sites). Split 4 concurrent opus agents, disjoint files,
  each builds ./builtins/ but only fixes errors in ITS files (siblings handled in parallel):
  G1: math,strings,types,maps,limits,url,gc. G2: fileio,verbs,properties,json,objects,ansi.
  G3: objects_hierarchy,signatures,lists,objects_movement,objects_players,objects_misc,registry,protected.
  G4: network,crypto,tasks,system,sqlite,pcre,argon2,curl,crypto_unix.
  After all 4: I central-build ./builtins/, fix residuals, go test, commit. Then vm, then server/conformance.
WAVE-3 builtins: all 4 agents FINISHED. Each reports its files converted + grep-clean, errors only in
  siblings (expected mid-sweep). Known residuals to handle in central build-fix:
  - compat_sqlite_test.go: 5 old-API sites, NOT assigned to any agent (G4 only had sqlite_test.go which
    doesn't exist). I must convert it.
  - stray scratch file left by G4: builtins/.tmp/unbox-notes-network-crypto.md -> DELETE.
  - G1 warned: Edit replace_all with empty replacement on ".Value()" corrupted a file once (reverted);
    watch for that pattern if cleaning up.
CENTRAL CONVERGENCE builtins: go build ./builtins/ GREEN (RC0). Removed builtins/.tmp scratch.
  Fixed residual test files I converted by hand: compat_sqlite_test.go (5 sites), network_http_test.go
  (mustMapValue line 21 - G4 missed it). Pattern: value.(types.XValue)->value.AsX(); %T->value.Type().
  Re-running go vet+test ./builtins/ next.
NEXT: confirm go test ./builtins/ green, commit wave-3. THEN vm (16 files), then server, conformance.
WAVE-3 builtins COMMITTED: 7f76cd4. (compat_sqlite_test.go + network_http_test.go residuals fixed by hand.)

WAVE-4 vm: 3 agents FINISHED. VG1(operators/op_logic/collection_helpers/op_misc),
  VG2(op_arith/op_compare/op_bitwise/op_iter - hot-path ordering PRESERVED), VG3(vm.go/op_property/
  op_index/registry/op_verb/op_list/traceback/stack/environment/anonymous_gc). Each grep-clean, own files
  build. CRITICAL vm.go done right: UnboundValue{} init -> types.Unbound(); OP_GET_VAR detect
  `val.(UnboundValue)` -> `val.IsNone()` -> E_VARNF; frame cache/pushFrame/popFrame untouched.
  HandleError exceptionValue ==nil -> IsNone, .(ListValue) -> AsList.
  RESIDUAL (unassigned, my count showed 0 sites): vm/control.go + vm/waif_gc.go have errors -> I fix centrally.
NEXT: central WSL go build ./vm/, fix control.go+waif_gc.go residuals, go vet+test ./vm/, commit wave-4.
  THEN server(3), conformance(2), cmd. Then go build ./... ; go test ./... ; full conformance 3871/131
  (build runner ELF in WSL); bench: confirm allocs/iter drops (was 2M/1M-loop) + speed delta.
WAVE-4 vm central convergence: go build ./vm/ GREEN after I fixed control.go (fork delay Kind switch)
  + waif_gc.go (collectWaifsForGC Kind switch). Now fixing vm test files by hand: bytecode_execution_test.go
  (requireInt/String/List -> AsInt/AsStr/AsList), dump_persistence_test.go (2 sites .(StrValue).Value()->AsStr/Str).
  Then go test ./vm/, commit wave-4.
WAVE-4 vm COMMITTED: 26d8a14. Branch now: c65fb40(types)->771714b(w1)->8d03a54(w2)->7f76cd4(builtins)->26d8a14(vm).

WAVE-5 server (BY HAND, in progress): files had nil-Value + WakeValue but no concrete-type names so
  earlier count missed them. Fixed: connection_manager.go (IntValue->AsInt, listContainsString AsList/AsStr),
  scheduler_eval.go (suspend Kind switch, WakeValue !=nil->!IsNone + =nil->Value{}, result.Val !=nil->!IsNone),
  scheduler_login.go (AsObjID, connectMessage AsStr, getServerOption return nil->Value{} x3, result.Val==nil->IsNone x2),
  scheduler_task_runtime.go (WakeValue x2 ->IsNone/Value{}, resultValueContains value==nil->IsNone),
  waif_lifecycle.go (waif WaifValue -> waif.AsValue() x2 for ThisValue + SetLocalByName "this").
NEXT: go build ./... (expect server clean now; then conformance + cmd surface). Fix those, go vet/test,
  THEN whole-repo gates: go build ./... ; go test ./... ; full conformance 3871/131 (build runner ELF in WSL);
  bench allocs/iter (was 2M per 1M-loop -> expect ~0) + speed delta vs toast. Commit wave-5. Squash? leave as
  layered commits on perf/unbox-value; merge to master after gates pass (Q approval).

### *** go build ./... IS GREEN — WHOLE MODULE COMPILES UNBOXED *** 2026-06-20.
Server done by hand (connection_manager, scheduler_eval/login/task_runtime, waif_lifecycle).
conformance done by hand (expectations.go valuesEquivalent As*-accessors + return nil->Value{}; setup.go AsObjID + return Value{}).
cmd/barn/main.go result.Val==nil->IsNone.
NEXT GATES (in order): go vet ./... (fix test residuals) -> go test ./... -> commit wave-5 ->
  full conformance suite (build runner ELF in WSL, expect 3871/131) -> bench (allocs/iter ~0, speed delta).
UNCOMMITTED right now: server/, conformance/, cmd/ changes (wave-5) not yet committed.

### *** WHOLE UNBOX DONE + COMMITTED (6 commits c65fb40..d6a4a44) on perf/unbox-value. ***
go build ./... GREEN, go vet ./... CLEAN, go test ./... passes except 2 PRE-EXISTING missing-fixture
fails (TestLoadMongooseSnapshot, conformance cow_py-dir harness) — also fail on master. CORRECTNESS HOLDS.
Full pytest conformance running (bg bb2bkw6b2) to confirm 3871/131.

### *** CRITICAL PERF FINDING: UNBOX IS A NET SLOWDOWN. Hypothesis was WRONG. ***
Allocs DID collapse as predicted (int_arith 2,000,000 -> 11 allocs/run; float, nested same ~11).
BUT TIME WENT UP almost everywhere. Clean A/B (same machine, back-to-back, benchtime=10x):
  workload          master(boxed,16B)      unbox(48B)         delta
  int_arith_1M      128ms / 2.0M allocs     135ms / 11         +5% SLOWER
  float_arith_1M    100ms / 2.0M            129ms / 11         +28% SLOWER
  string_concat_10k 11.2ms                  10.8ms             ~same
  list_append_10k   614ms / 1.67GB          1476ms / 4.88GB    +140% SLOWER (2.4x!)
  list_index_1M     185ms                   252ms              +36% SLOWER
  tostr_200k        92ms / 1.8M             110ms / 1.2M       +20% SLOWER
  nested_1k         99ms                    125ms              +26% SLOWER
ROOT CAUSE: Value struct grew 16B (Go interface) -> 48B (kind+num+string(16)+any(16)). Every stack
  push/pop/copy and every list element now moves 3x bytes; list memory tripled. The struct-copy
  bandwidth cost EXCEEDS the eliminated alloc cost. Go interface (16B) + convT64 pooling was already cheap.
KEY INSIGHT: for copy-bound code (list O(n^2)), ANY tagged-union struct (>=24B) loses to the 16B interface
  on pure copy bandwidth, regardless of alloc elimination. Lists will never win via unboxing here.
  For arithmetic, a SHRUNK 24B Value (kind+num+unsafe.Pointer, strings via unsafe.String) MIGHT beat boxed
  (alloc gone, only 1.5x copy) — but uncertain, and lists stay worse.
DECISION NEEDED FROM Q: (a) shrink Value to 24B via unsafe.Pointer packing + re-measure (more work, lists
  likely still lose); (b) SHELVE unbox unmerged (master stays boxed/faster); (c) keep only if a real
  workload is arithmetic-bound not list-bound. My lean: do NOT merge as-is (net regression); the branch is
  correct + reversible (git). This is why a measurement spike matters — the "obvious" win measured negative.
CLEANUP DONE: barn-masterbench worktree removed, barn_unbox.exe removed. Conformance 3871/131 (==master).

### STRATEGIC CONCLUSION — what the result says about UNBOXING AS A GOAL:
Unboxing as a THROUGHPUT strategy is a DEAD END in Go for this VM. Now measured, not guessed.
- The technique is from C interpreters (Var=16B by value, no GC, no fat-pointer). In Go the premise fails:
  Go's interface is ALREADY 16B and small ints/pointers don't alloc; you can't NaN-box safely; GC is good.
  So the boxed->unboxed gap that's huge in C is ~zero-or-negative in Go.
- Unboxing trades ALLOC for SIZE. Size is paid on EVERY copy (stack push/pop, every list element), forever.
  Any tagged union (>=24B) > 16B interface on copy bandwidth -> copy-bound code (MOO lists, O(n^2)) can NEVER win.
- The CPU profile ALREADY predicted the low ceiling: alloc/GC was ~20-25%, dispatch ~55%. Perfectly removing
  alloc could recover <=25% AND only if it added no new cost; it added 3x copy cost -> net loss. We chased the
  smaller lever with a technique that taxed the bigger one.
- Toast is faster because: C + -O3 -march=native + monomorphic/threaded dispatch + NO GC, NOT because it unboxes.
  The gap to toast is DISPATCH MODEL + native codegen, not boxing.
- ONE unmeasured caveat: under heavy CONCURRENT multi-task GC-pressure, the 2M->11 alloc reduction could help
  tail latency / total GC CPU even if single-thread throughput dips. Our bench is single-thread throughput. Narrow.
- Even the best-case 24B unsafe variant: maybe ~even on arithmetic, still loses on lists. Doesn't reach the goal.
DECISION: SHELVE perf/unbox-value unmerged (correct, complete, reversible — kept as evidence/optionality).
  Keep the REAL wins already on master: #2 (O(1) list size) + #4 (frame cache + inline dispatch).
  If chasing toast further: attack DISPATCH (threaded/computed-goto, superinstructions, fuse hot opcode pairs,
  or register-VM to cut push/pop), not value representation. Or set a realistic target (within ~3-5x of C, not parity).

## Phase 7: dispatch investigation (2026-06-21)
### Q1: is Toast a register VM (are we catching up)? ANSWER (read toast src): NO. Toast is a STACK VM.
  Evidence: execute.cc rt_stack/top_rt_stack push(*top++ =v)/pop(top--); opcode.h OP_PUSH/OP_PUT/OP_POP/
  OP_IMM/OP_MAKE_EMPTY_LIST/OP_LIST_ADD_TAIL/OP_ADD. Same architecture class as barn.
  => Toast's 4-17x is SUBSTRATE (C/-O3/-march=native/no-GC/16B Var), NOT a better dispatch model.
  => A register VM = going BEYOND toast (out-design on a heavier substrate) = risky/speculative. SKIP IT.
  BUT toast DOES specialize: OP_PUSH_n/OP_PUT_n (OP_G_PUSH=OP_PUSH+NUM_READY_VARS, IS_PUSH_n) = dedicated
  opcodes for first N var slots, skipping the operand-byte read. And toast HAS OP_FOR_RANGE (compact loop iter).

### OPCODE HISTOGRAM SPIKE (throwaway worktree barn-opcodehist off master e67f970; instrumentation NOT committed):
  Per-workload dispatched-op breakdown (go test -run TestOpcodeHist):
  - VAR ACCESS (GET/SET_VAR) = 28-47% of ALL dispatched ops; GET_VAR alone 20-33%. THE biggest category.
  - var + stack-shuffle combined = 32-53%.
  - int_arith: ~15 ops/iteration for `x=x+i` loop, of which ~5 are GET_VAR. Loop bookkeeping (LE/DUP/POP/
    JUMP_IF_FALSE/IMM/LOOP + counter GET_VAR/SET_VAR) is ~8-9 ops/iter of pure overhead.
### KEY DISCOVERY: barn HAD compact loop opcodes OP_FOR_RANGE/OP_FOR_LIST/OP_FOR_NEXT but they are marked
  **DEAD — "replaced by while-loop pattern / explicit GET_VAR/ADD/SET_VAR, never emitted by compiler"**
  (bytecode/opcodes.go:80-83). barn DELIBERATELY desugars loops into verbose generic ops. That's why loops
  dispatch ~2x the ops toast would. Toast keeps OP_FOR_RANGE.

### CONCLUSION / RECOMMENDED NEXT (both "catch up to toast", proven, low-risk, NO register VM, NO value-rep change):
  1. LOOP CODEGEN (biggest): re-introduce a compact range/list iterator opcode (un-dead OP_FOR_RANGE/iter),
     collapsing ~8-9 bookkeeping ops/iter -> ~1-2. Loop-heavy code could drop dispatched ops ~40-50%.
  2. VAR-ACCESS SPECIALIZATION: dedicated OP_GET_VAR_n/SET_VAR_n for first N slots (toast's OP_PUSH_n),
     skip ReadByte + tighter switch arm. Attacks the 20-33% GET_VAR share.
  Do #1 first as a spike (one FOR_RANGE op, A/B on bench/BenchmarkVM), measure, then #2. Each incremental+reversible.
  REMINDER: measure each (unboxing lesson). bench harness = bench/bench.py (socket) + vm BenchmarkVM (direct).
CLEANUP DONE: barn-opcodehist worktree removed.

## Phase 8: IMPLEMENT loop-iterator opcode (#1). Worktree ~/code/barn-loopiter, branch perf/loop-iter off master.
DESIGN (surgical, semantics-preserving, loop var stays a normal local so BODY codegen is untouched):
  Repurpose 2 dead opcodes (zero enum shift, no live handlers - verified):
  - OP_FOR_RANGE (renamed OP_FOR_RANGE_CHECK) [valueVar:byte][endVar:byte][exit:short]:
      compareValues(Locals[valueVar], Locals[endVar]); if >0 (value>end) IP+=exit. Replaces GET_VAR/GET_VAR/LE/JUMP_IF_FALSE.
  - OP_FOR_NEXT (renamed OP_FOR_RANGE_NEXT) [valueVar:byte][loop:short]:
      if int: Locals[v]=int+1 else E_TYPE; IP-=loop. Replaces GET_VAR/IMM/ADD/SET_VAR/LOOP.
  TICK FIDELITY: CountsTick only counts OP_LOOP/calls -> loop=1 tick/iter. Made FOR_RANGE_NEXT count 1 tick,
  CHECK 0 -> identical tick accounting. Semantics replicate compare/add exactly (compareValues reused; int+1 wrap matches).
DONE: opcodes.go (rename enum 2 slots + name table + CountsTick += FOR_RANGE_NEXT).
IN PROGRESS: compiler.go compileForRange (~line 1951-1990) replace cond+incr+loop emission with CHECK/NEXT;
  offsets: CHECK exit = emitShort placeholder patched via patchJump(exitJump where exitJump=currentOffset before short);
  NEXT loopback = currentOffset()+2-loopStart (mirrors OP_LOOP). loopStart=currentOffset() after beginLoop.
TODO: vm.go add 2 case handlers (use compareValues, frame.Locals, frame.IP +=/-=); go build; A/B BenchmarkVM
  (int_arith/nested = range loops, expect big drop); FULL conformance 3871/131 (loops everywhere - critical gate).
  NOTE: list-for (compileForList) NOT changed in this step - separate, uses OP_ITER_PREP. Only range-for here.

### #1 IMPLEMENTED. build ./... GREEN, vm+bytecode tests pass. BENCH A/B (vs master e67f970, benchtime=10x):
  int_arith_1M   128ms -> 60ms   (2.1x / -53%)
  float_arith_1M 100ms -> 61ms   (1.6x / -39%)
  nested_1k      99ms  -> 59ms   (1.7x / -40%)
  tostr_200k     92ms  -> 85ms   (-8%)
  string_concat  ~flat (body-dominated), list_append ~flat (list-for not range-for), list_index ~noise(185->212, recheck)
  => HUGE win on range-loop-bound code. allocs unchanged (expected - this is dispatch, not alloc).
  Files: bytecode/opcodes.go, bytecode/compiler.go (compileForRange), vm/vm.go (2 handlers).
GATE: full conformance running bg b0e58oaj8 (barn_loopiter.exe). MUST be 3871/131. Loops everywhere = critical.
  (earlier bg bemapj5da was a botched `&` detach - ignore; this b0e58oaj8 is the real run.)
### #1 DONE + COMMITTED: 6094276 on perf/loop-iter. CONFORMANCE 3871/131 (==master, ZERO regress).
  Final isolated bench A/B vs master: int_arith 132->60 (2.2x), nested 100->58 (1.7x), list_index 186->144 (1.3x).
  LESSON: list_index "207ms regression" was BOGUS - I benchmarked WHILE conformance ran in bg (machine
  contention). Isolated = 144ms = FASTER. DON'T bench during a conformance run.
  barn_loopiter.exe removed.

## Phase 9: #2 var-access specialization (OP_GET_VAR_n/SET_VAR_n), built ON TOP of #1.
  Rationale: even after #1, body var reads remain ~40% of dispatch (int_arith body x=x+i = 3 var ops/iter).
  Toast does OP_PUSH_n/OP_PUT_n (dedicated opcodes for first N slots, skip operand-byte read). barn ALREADY
  has the idiom for ints (OP_IMM_BASE..range, MakeImmediateOpcode/IsImmediateInt/GetImmediateValue) - mirror it.
  PLAN: worktree barn-varspec off perf/loop-iter (branch perf/var-specialize), so #1+#2 stack & measure combined.
  Need: carve a reserved opcode block for GET_VAR_0..N / SET_VAR_0..N (avoid iota shift of later opcodes OR
  accept in-build shift since bytecode recompiled from source). compiler emits specialized when idx<N; vm
  dispatches them (push Locals[n] / set Locals[n]) skipping ReadByte. Gate: build, vm/bytecode tests,
  bench (expect modest 5-15% on var-heavy), FULL conformance 3871/131.

### #2 IMPL (worktree barn-varspec, branch perf/var-specialize off perf/loop-iter):
  Opcode space: OP_PASS=219 last; appended OP_GET_VAR_BASE=220, COUNT=16 (220-235, <256, NO enum shift).
  opcodes.go DONE: block + IsGetVarN/GetVarNIndex/MakeGetVarN + String() "GET_VAR_N".
  compiler.go DONE: emitGetVar(idx) helper (specialized if idx<16 else generic). 
  IN PROGRESS: fuse 55 sites `c.emit(OP_GET_VAR)\n c.emitByte(byte(EXPR))` -> `c.emitGetVar(EXPR)` via perl slurp.
    All operands are byte(intExpr), uniform. After: verify 0 remaining emit(OP_GET_VAR) pairs + emitGetVar=55.
  TODO: vm.go Execute fast-path: `if bytecode.IsGetVarN(op) { push Locals[idx] w/ unbound->E_VARNF; return }`
    (mirror OP_GET_VAR handler; place after IsImmediateInt check). Then build, vm/bytecode tests, bench, conformance.
  NOTE: only GET_VAR specialized (dominant). SET_VAR left generic (smaller share). decompiler/verb_code: barn
    stores source, recompiles - specialized opcodes internal only; but CHECK any bytecode disassembler in tests.

### #2 RESULT: DUD. Neutral-to-NEGATIVE. SHELVE (do not merge). build+vm/bytecode tests green.
  Clean back-to-back (#1 vs #1+#2, 20x): int_arith 59.4->58.6 (~0), nested 57.6->61.8 (+7% WORSE),
  list_index 144.6->150.0 (+4% worse), tostr ~flat.
  WHY: the fast-path `if IsGetVarN(op)` runs on EVERY dispatched op (extra pre-switch branch), but only
  GET_VAR ops benefit, and the only saving is a ReadByte (array index + incr = nearly free). barn's Go
  switch already compiles to a jump table, so specialization removes ~nothing while taxing every dispatch.
  SAME LESSON AS UNBOXING: C-interpreter tricks (OP_PUSH_n specialization) don't port to barn's Go substrate
  (cheap ReadByte + jump-table switch). Toast benefits from it because C + threaded/computed-goto dispatch.
  Putting GET_VAR_N as switch cases instead of pre-switch branch would avoid the tax but the win is sub-1%
  (ReadByte is free) - not worth 16 opcodes + code. NOT pursuing.

### *** STRATEGIC: only OP-COUNT reduction works in barn, not per-op micro-opt. ***
  WINS: #1 loop-iter (9 ops/iter -> 2) = reduced op COUNT = 1.7-2.2x. KEPT (committed 6094276).
  DUDS: unboxing (bigger value copy), var-specialization (per-dispatch branch tax). Both tried to make each
  op cheaper; both failed because barn's per-op cost is already low + the trick added overhead.
  => Future speed = reduce DISPATCHED-OP COUNT further: list/map iterator fusion (like #1 but compileForList,
  currently OP_ITER_PREP + generic loop), superinstructions for common expr patterns. NOT representation/
  per-op tricks. And/or accept within-3-5x-of-C target.
CLEANUP: barn-varspec worktree + perf/var-specialize branch = shelved evidence (keep, do not merge).
  barn-loopiter worktree has #1 (perf/loop-iter, committed) - the one to actually merge.

### #1 MERGED TO MASTER: master fast-forwarded dbcbe56 -> 6094276 (FF-only, clean). master build GREEN.
  (master was checked out in main worktree C:/Users/Q/code/barn on branch master; merged there via
  git merge --ff-only perf/loop-iter; only untracked scratch files present, no tracked changes disturbed.)
  master now ahead of origin/master by 6. NOT pushed (outward action, left for Q - consistent with prior).
  perf/loop-iter branch + barn-loopiter worktree now redundant (merged) - cleanup candidates.
  Conformance already verified 3871/131 on this exact tree before merge.

### CLEANUP DONE (2026-06-21): removed worktrees barn-loopiter/varspec/opt2-listsize/opt4-dispatch/vm-perf/unbox;
  deleted branches perf/{loop-iter,var-specialize,integrate,combined,dispatch,list-size,vm-bench} (all content on master).
  KEPT: perf/unbox-value (shelved evidence, no worktree). Only main worktree (master 6094276) + that branch remain.
  Did NOT touch other agents' worktrees/branches (spike/*, feat/*). var-specialize dud was never committed
  (uncommitted edits discarded with worktree; finding documented in notes above).

## Phase 10: #3 list/map iterator fusion. Worktree barn-listiter, branch perf/list-iter off master 6094276.
  Added bench workload list_iter_1M: `l = {1..1000000}; s = 0; for x in (l); s = s+x; endfor; return s;`
  (uses OP_LIST_RANGE to build big list cheaply so iteration dominates).
### PHASE A DONE: reuse #1's FOR_RANGE_CHECK/NEXT for list-for cond+incr (idx/len are ints, identical shape).
  compileForList: cond GET/GET/LE/JIF -> FOR_RANGE_CHECK(idxVar,lenVar,exit); incr+LOOP -> FOR_RANGE_NEXT(idxVar).
  Element fetch + isPairs/index extract UNCHANGED (that's Phase B). Zero new opcodes.
  BENCH (benchtime=20x): list_iter_1M 164ms -> 116ms (~29% faster). build+vm/bytecode tests GREEN.
  GATE: full conformance running (list/map iteration heavily exercised) - MUST be 3871/131.
  TODO after green: commit Phase A; then Phase B.

### PHASE B DESIGN (after A committed). ITER_PREP normalizes container -> a LIST (always ListValue) + isPairs
  flag (1 = elements are {value,key} pairs: maps, OR any hasIndex form, OR string-with-index; 0 = plain values).
  len captured at start (lenVar), normalized list in listVar (a copy - body mutating original is safe), idx 1..len.
  => element fetch idx is PROVABLY in-bounds; can skip OP_INDEX bounds-check, call list.Get(idx) directly.
  Two fused opcodes (repurpose dead OP_FOR_LIST, OP_FOR_MAP):
  - OP_FOR_LIST_LOAD [listVar][idxVar][valueVar][isPairsVar]  (no-index form):
      list=Locals[listVar].(ListValue); elem=list.Get(idx); if Locals[isPairsVar].Truthy() elem=elem.(ListValue).Get(1); Locals[valueVar]=elem
  - OP_FOR_LIST_LOAD_KV [listVar][idxVar][valueVar][indexVar]  (hasIndex form, elems always pairs):
      elem=list.Get(idx).(ListValue); Locals[valueVar]=elem.Get(1); Locals[indexVar]=elem.Get(2)
  Replaces elem-fetch (GET list,GET idx,INDEX) + extract (DUP/IMM/INDEX/SET x2, or isPairs branch) ~7-10 ops -> 1.
  CAUTION: match OP_INDEX semantics for Get (1-based); type assertions safe (ITER_PREP always pushes ListValue);
  these ops count 0 ticks (INDEX didn't... verify INDEX tick); preserve E_? behavior (none expected, idx in-bounds).
  Gate same: build, vm/bytecode tests, bench, FULL conformance (map iter, for-k,v, string iter all exercised).

### PHASE A COMMITTED: a03f4b2 on perf/list-iter. conformance 3871/131. bench 164->116ms.
### PHASE B IN PROGRESS (same worktree barn-listiter):
  DONE opcodes.go: repurposed dead OP_FOR_LIST->OP_FOR_LIST_LOAD, OP_FOR_MAP->OP_FOR_LIST_LOAD_KV + name table.
    (CountsTick: INDEX counts 0 ticks -> these load ops count 0; left CountsTick unchanged. VERIFY INDEX tick=0.)
  DONE compiler.go: compileForList element-fetch+extract block -> FOR_LIST_LOAD_KV (hasIndex) / FOR_LIST_LOAD (else).
  TODO vm.go: 2 handlers (use comma-ok type asserts to avoid panic; list.Get is 1-based, idx in-bounds):
    FOR_LIST_LOAD: list=Locals[listVar].(ListValue); elem=list.Get(idx); if Locals[isPairsVar].Truthy(){elem=elem.(ListValue).Get(1)}; Locals[valueVar]=elem
    FOR_LIST_LOAD_KV: pair=list.Get(idx).(ListValue); Locals[valueVar]=pair.Get(1); Locals[indexVar]=pair.Get(2)
  Then build, vm/bytecode tests, bench list_iter (expect further drop from 116ms), FULL conformance 3871/131, commit.

### PHASE B DONE: vm.go 2 handlers added (comma-ok asserts, in-bounds Get, isPairs unwrap). build+tests GREEN.
  BENCH list_iter_1M: 116ms (A) -> 94ms (B). Cumulative vs master 164ms -> 94ms = ~43% (1.7x).
  GATE: full conformance running bg bf3wf3c7t - MUST 3871/131 (map iter / for-k,v / string iter / empty containers).
  TODO after green: commit Phase B; report #3 done to Q. (#3 not yet merged to master - perf/list-iter branch.)
  barn_listiter.exe to remove before commit.

### #3 MERGED TO MASTER: FF dbcbe56-line -> 8c43bee (master now has #1 +A +B). build green. conformance
  pre-verified on 8c43bee. perf/list-iter branch + barn-listiter worktree removed. Only master + perf/unbox-value.
  NOT pushed (left for Q, consistent).

## Phase 11: NEXT target via re-profile on master 8c43bee (throwaway worktree barn-hist2, removed after).
### HISTOGRAM (post #1+#3) — NEW BIG FINDING: statement-assignment DUP+POP tax.
  int_arith_1M now: GET_VAR 25%, SET_VAR 12.5%, POP 12.5%, DUP 12.5%, FOR_RANGE_CHECK 12.5%, ADD 12.5%, NEXT 12.5%.
  => `x = x + i;` (statement) compiles to ...ADD, DUP, SET_VAR x, POP. The DUP keeps the assignment's value
  (assignment is an EXPRESSION in MOO), then POP discards it because it's used as a STATEMENT. DUP+POP = ~25%
  of dispatched ops in assignment-heavy loops, PURE DEAD WORK. Seen across int/float/string/tostr/nested (POP+DUP
  ~25%) and list_append (~20%).
  FIX (next target): compile expression-STATEMENTS "for effect not value" — when an ExprStmt's expression is an
  assignment, emit SET_VAR WITHOUT the trailing DUP, and NO POP. Standard value-vs-effect codegen distinction.
  compiler: compileExprStmt (line 491->compileExprStmt) currently does (compile expr leaves value)+OP_POP;
  compileAssign (772) emits OP_DUP (779) then SET so value remains. Need a "statement context" path.
  LOCATION: bytecode/compiler.go compileExprStmt + compileAssign (DUP at 779). Other DUP sites (1465,1499,2445)
  are different (scatter/index-assign) - check separately.
  EXPECTED: ~20-25% fewer dispatched ops in assignment-heavy code = broad win (every statement assignment).
  PLAN: investigate compileExprStmt+compileAssign; add effect-context assignment (no DUP, no POP); gate
  build/tests/bench/conformance. This is op-count reduction (the lever that works). Worktree off master.

### #4 (stmt-assign) IMPLEMENTED. Worktree barn-stmtassign, branch perf/stmt-assign off master 8c43bee.
  compileExprStmt: if expr is AssignExpr with IdentifierExpr target -> compile Value, SET_VAR (NO DUP, NO POP),
  return. Complex targets (scatter/index/property) + non-assign exprs keep general compile+POP path.
  Semantics identical (verified logic: declareVariable idempotent; chained y=x=5 works - inner via compileAssign).
  build+vm/bytecode tests GREEN. Clean back-to-back A/B (20x): int_arith 60.9->53.6 (~12%), nested 57.9->53.3 (~8%),
  list_iter 94.6->83.6 (~12%), string_concat flat (body-dominated). Broad win - every statement var-assign.
  GATE: full conformance running bg bvyzuj3uq - MUST 3871/131 (assignment fundamental; check assign-as-expr,
  chained assign, scatter/index/property assignment still work). barn_sa.exe to remove before commit.
  TODO after green: commit perf/stmt-assign; report to Q (not merged yet). Histogram next-next: after stmt-assign,
  remaining int_arith ops = GET_VAR/SET_VAR/ADD/CHECK/NEXT (all real work) - getting near irreducible for arith.

### #4 (stmt-assign) MERGED: conformance 3871/131; master FF 8c43bee -> 32f1deb; build green; worktree+branch cleaned.
  MASTER NOW HAS 4 WINS: 6094276 (#1 range-for) / a03f4b2+8c43bee (#3 list-for A+B) / 32f1deb (#4 stmt-assign).
  All NOT pushed (origin behind, left for Q).

## Phase 12: RE-GROUND vs ToastStunt (original goal). Arith micro-benches near floor (remaining ops all real
  work; #2 var-spec + unboxing both proven duds). Micro-suite IGNORES real-MOO hot paths: verb calls
  (OP_CALL_VERB), property access (OP_GET_PROP), builtins (OP_CALL_BUILTIN). 
  PLAN: re-run ORIGINAL socket bench (bench/bench.py vs toast on WSL, the harness from Phase 1) on CURRENT master
  to (a) show cumulative gain vs original 4-17x gap, (b) find next frontier (likely prop/verb/builtin, not arith).
  Original gap (Phase 1, before ANY opt): int 9.4x, list_append 17x, strcat 12x, list_index 8.7x, tostr 4.2x,
  prop 7.4x, verb(abs) 7.7x, nested 9.3x slower than toast.
  WSL servers: toast ELF ~/src/toaststunt/moo (built); barn rebuild from master. run_bench.sh raises tick limits.

### *** CUMULATIVE RESULT vs toast (master with all 4 wins), socket bench: GAP ROUGHLY HALVED. ***
  workload          original-gap  NOW    (toast ms / barn ms)
  int_arith_5M       9.4x      -> 4.0x   (67 / 270)
  float_arith_5M     9.1x      -> 4.0x   (70 / 277)
  string_concat_50k  12-13x    -> 13.0x  (21 / 277)   <- NOT improved (O(n^2) string copy, body-dominated)
  list_append_30k    17x       -> 9.1x   (794 / 7229)  <- still WORST absolute (7.2s); O(n^2) list copy
  list_index_1M      8.7x      -> 5.2x   (29 / 148)
  builtin_tostr_1M   4.2x      -> 3.1x   (151 / 475)
  prop_access_1M     7.4x      -> 6.2x   (61 / 377)
  verb_call_200k     7.7x      -> 5.7x   (9 / 52)
  nested_2500^2      9.3x      -> 4.0x   (85 / 341)
  noop ~0.9x (parity). Arith/loops now ~4x = near the realistic "within 3-5x of C" target. Loop work paid off.

### REMAINING FRONTIERS (next targets, ranked):
  1. list_append O(n^2) (9.1x, 7.2s abs - WORST): `{@l,i}` copies whole list each iter. Toast mutates in place
     when refcount==1. FIX: COW/uniqueness tracking -> in-place append when list not shared. O(n^2)->O(n).
     HIGH value (list-building ubiquitous in MOO), MEDIUM-HIGH risk (aliasing/value-semantics; unboxing-scale care).
  2. string_concat O(n^2) (13x - worst ratio): `s=s+x` accumulator. Same idea (mutable builder when unshared). Risk med.
  3. prop_access (6.2x) / verb_call (5.7x): real-MOO dispatch hot paths. Moderate gap, moderate work.
  => The cheap op-count wins are banked. Remaining gaps are STRUCTURAL (O(n^2) append) or dispatch. Next step is
     bigger/riskier - get Q's steer on direction (esp. list-append COW = value-semantics change).

## Phase 13: #A list-append in-place (Q chose A). Worktree barn-inplace, branch perf/list-inplace off master 32f1deb.
### MECHANISM confirmed: `{@l,i}` compiles to MAKE_LIST, GET l, LIST_EXTEND(copies l O(n)), <i>, LIST_APPEND, SET l.
  The LIST_EXTEND copying l each iter = the O(n^2). To be O(1) amortized must NOT copy l - mutate l's storage + rebind.
### THE GO PROBLEM: no refcounts (toast uses refcount==1 to mutate in place). Go struct-copy of ListValue is
  invisible (no hook), so can't track aliasing via copy. SOLUTION = WATERMARK/ownership trick (safe, GC-friendly):
  sliceList gets `watermark *int` (shared per backing array = highest committed append index).
  Append rule: in-place iff len(elements)==*watermark && cap>len -> write backing[len], *watermark++, return view len+1.
  Else COPY (fresh backing w/ growth + fresh watermark=newlen). SAFETY: if two views share backing at same len,
  FIRST to append bumps watermark, others then see len!=watermark -> copy. A shorter prefix view (len<watermark)
  always copies. => no aliased write ever clobbers a committed slot. IN-PLACE CONFINED TO Append ONLY; Set/Slice/
  Insert/Delete keep copying (fresh watermark). NewList(external slice): cap to len (elements[:n:n]) so first append
  copies (don't trust external spare/aliasing). Copy path allocates growth cap so SUBSEQUENT appends hit in-place.
### TWO PARTS NEEDED:
  1. types/list.go: watermark on sliceList; Append in-place-when-owned; copy path grows+fresh watermark; NewList caps;
     maintain byteSize cache incrementally (already does). Other ops unchanged (copy).
  2. compiler: detect idiom `v = {@v, e1..ek}` (AssignExpr, target IdentifierExpr v, Value ListExpr with
     Elements[0]=SpliceExpr of v) -> emit GET v; per trailing elem LIST_APPEND/LIST_EXTEND; SET v. Skips MAKE_LIST +
     EXTEND-of-self. First append mutates v in place (watermark) when uniquely owned.
### GATES (this is the RISKY one): build, vm/bytecode/types tests, + WRITE AGGRESSIVE ALIASING STRESS TEST
  (m=l; l={@l,x}; assert m unchanged; nested; pass-to-verb; list stored in prop then appended; etc.), bench
  list_append (expect 7.2s->~tens of ms, O(n^2)->O(n)), FULL conformance 3871/131. Spike: prove before merge.
  CAUTION: conformance may NOT cover all aliasing -> the hand-written aliasing test is the real safety net.

### #A IMPLEMENTED. types/list.go watermark Append (in-place when watermark!=nil && *wm==len && cap>len; else
  append-with-growth copy + fresh watermark; watermark nil for all non-Append-origin lists = safe). compiler:
  self-append idiom v={@v,e..} -> GET v, [APPEND/EXTEND per trailing elem], SET v (in compileExprStmt).
  ALIASING STRESS TEST (vm/list_inplace_aliasing_test.go, 8 cases: alias-then-append, build+alias+diverge,
  nested capture, 3-way share, multi-trailing, splice-trailing, slice-then-append, alias-chain) ALL PASS.
  build + types/vm/bytecode unit tests GREEN.
  *** BENCH list_append_10k: ~580ms -> 1.35ms (~430x); allocs 1.67GB -> 1.39MB. O(n^2) -> O(n). ***
  GATE: full conformance running - MUST 3871/131. This is THE risky value-semantics change; aliasing test +
  conformance together are the net. barn binary to build + remove.
  ENV GOTCHA: running `bash bench/run_bench.sh` (WSL uv) on the shared /mnt/c .venv created a Linux lib64->lib
  symlink that broke Windows `uv run` ("failed to remove .venv/lib64: Access denied"). FIX: rm -rf .venv/lib64,
  retry. (Don't run WSL-side uv against the Windows .venv, or use a separate venv.)

### #A MERGED: conformance 3871/131 + 8 aliasing tests pass; master FF 32f1deb -> 30d4288; build green;
  worktree+branch cleaned. MASTER NOW HAS 5 WINS: #1 range-for(6094276), #3 list-for A+B(a03f4b2,8c43bee),
  #4 stmt-assign(32f1deb), #A list-append-in-place(30d4288). All UNPUSHED (origin behind).
  list_append O(n^2)->O(n): micro-bench ~580ms->1.35ms (~430x), 1.67GB->1.39MB. This was the WORST gap vs
  toast (9.1x/7.2s) - now should beat/match toast. TODO maybe: re-run socket bench vs toast to confirm
  (careful: run_bench.sh WSL-uv breaks Windows .venv lib64 - rm -rf .venv/lib64 after).

## Phase 14: Q said "A+B" = (a) re-bench vs toast to confirm #A standing, then (b) keep optimizing next target.
  Running socket bench vs toast (bg b397nph8b) on master 30d4288 (5 wins). Will pick B's target from the
  biggest remaining gap (likely string_concat 13x OR prop_access 6.2x / verb_call 5.7x).
  MUST rm -rf .venv/lib64 after this WSL bench so Windows conformance runs work for B.

### RE-BENCH RESULT (master 5 wins vs toast): list_append_30k toast 776ms / barn 5.0ms = barn ~155x FASTER
  than C (toast also O(n^2) on {@l,i}). Other gaps: string_concat 13.2x (worst), prop_access 6.1x, verb_call 6.1x,
  arith ~4x (floor), list_index 5.2x, tostr 3.3x. venv lib64 cleared after.
  KEY: "verb_call" workload is actually abs() = BUILTIN call; "prop_access" is n.name = BUILTIN PROPERTY lookup.
  Micro-suite does NOT test user verb/defined-prop dispatch.

## Phase 15: B = prop-access lookup fix (Q chose). Worktree barn-prop, branch perf/prop-access.
  NOTE master moved to 9b738fb (another agent: scheduler/command refactors stacked on my 5 perf commits;
  verified 30d4288 still ancestor - my work intact). Worktree off 9b738fb.
  WASTE: n.name (builtin prop) does FindProperty(full inheritance walk) which FAILS, THEN getBuiltinProperty.
  FIX (SAFE): add_property rejects builtin names (isBuiltinProperty->E_INVARG), so builtin names can NEVER be
  defined props -> serve builtin path FIRST for builtin names, skip the failed FindProperty walk. getBuiltinProperty
  set == isBuiltinProperty set (verified: name/owner/location/contents/parents/parent/children/programmer/wizard/
  player/r/w/f/a). 
  DONE: exported builtins.IsBuiltinProperty (sed rename, 3 callers+def). 
  TODO: edit vm/op_property.go executeGetProp (~line 63-80): if builtins.IsBuiltinProperty(propName) -> 
  getBuiltinProperty direct (Push or E_PROPNF), else FindProperty (Push or E_PROPNF). build/tests/bench/conformance.
  CAUTION: also check executeGetProp's OTHER prop paths (push-get-prop variant?) + getWaifProp unaffected.

### B (prop-access) IMPLEMENTED + CONFORMANCE PASS (3871/131). build+vm/builtins tests green.
  vm/op_property.go executeGetProp: builtin-name -> getBuiltinProperty direct (skip FindProperty walk); else
  FindProperty. +import barn/builtins. builtins.IsBuiltinProperty exported.
  barn_prop.exe built (conformance). Branch perf/prop-access off master 9b738fb (which has my 5 wins + other
  agent's scheduler/command refactors).
### PERF MEASUREMENT BLOCKER: trying to socket-bench master(7901) vs prop(7902) on WSL to confirm prop_access
  delta. Servers built (/tmp/barn_master,/tmp/barn_prop 18MB) but nohup servers die when wsl.exe one-shot exits
  (WSL2 VM teardown). Running start+bench+stop in ONE wsl.exe -lc returned NO OUTPUT (uv venv churn? grep ate it?).
  NEXT: capture FULL bench output to /tmp file in WSL, read it. Expect prop_access prop/master < 1 (faster).
  Then: rm .venv/lib64 (WSL uv churns it); commit perf/prop-access; merge; report.

### B DONE + MERGED: prop_access_1M master 376ms -> prop 254ms (~33%; vs toast 6.1x -> ~4.2x). Other workloads
  flat (only prop path changed). conformance 3871/131. master FF 9b738fb -> eb59313. build green. worktree+
  branch removed. venv lib64 cleared. 
  WSL BENCH GOTCHA (learned): pkill -f <binary> inside a wsl.exe -lc script SELF-KILLS the script (its cmdline
  contains the binary name) -> exit 15, nothing runs. Also nohup servers die on wsl one-shot exit (VM teardown).
  WORKING PATTERN: start servers + run bench in ONE invocation, save $! to pid files, NO pkill; kill by
  `kill $(cat pidfile)` in a SEPARATE command.

### *** SESSION SCOREBOARD (master eb59313, 6 perf commits + other agent's refactors): ***
  vs toast, original -> now: int 9.4->4.0x, float 9.1->3.8x, nested 9.3->3.9x, list_index 8.7->5.2x,
  tostr 4.2->3.3x, verb/abs 7.7->6.1x, prop_access 7.4->~4.2x (after B), string_concat 13->13.2x (UNTOUCHED),
  list_append 17x -> barn 155x FASTER than toast (#A). Gap halved+ across board; 2 worst structural cases won.
  WINS (op-count + structural): #1 range-for fusion, #3 list-for fusion(A+B), #4 stmt-assign, #A list in-place,
  #B builtin-prop fast path. DUDS (shelved, evidence): unboxing(perf/unbox-value branch), var-specialization.
  REMAINING: string_concat 13x (hard - Go immutable strings, StrValue rep change), arith ~4x (floor),
  builtin-call/tostr ~3-6x (dispatch substrate). ALL UNPUSHED (origin behind; push left for Q).
NEXT WAVE-2: task (deps kernel✓ types✓) + db/format (deps db/store✓ task). task & db/format - does
  db/format import task? yes. So do task FIRST then db/format, OR together but db/format may not
  fully build until task done. Plan: dispatch task + db/format together (disjoint dirs); if db/format
  agent blocks on task symbols, it waits/reports. Then builtins (needs bytecode✓ db/store✓ task trace✓).
  Then vm. Then server, conformance. Gate each: WSL go build ./<pkg>/. Final: go build ./... ; go test ./... ;
  conformance 3871/131 (build runner ELF in WSL); bench allocs/iter ~0 on arithmetic.

  Each agent prompt: give SWEEP API CHEATSHEET above + "make go build ./<pkg>/ green, do not change
  behavior, gopls noise is not real, verify with go build in WSL: cd /mnt/c/...; go build ./<pkg>/".

## Phase 5 (DONE): merge all perf work to barn master
barn master = 0bc99b3 (ahead of origin/master by 1; the kernel-rename: TaskContext->barn/kernel,
ctx.Store now interface{} needing .(*dbstore.Store)). My perf branches forked off spike/world-seam
(e2e3093) which is 2 THROWAWAY spike commits ahead of master -> do NOT merge perf/combined (would drag
spike). Instead REPLAYED 3 perf commits onto master via cherry-pick in worktree ~/code/barn-integrate
(branch perf/integrate).
- 3 cherry-picks AUTO-MERGED, zero conflicts (my changes don't touch ctx/Store lines).
- Only fix needed: perf_bench_test.go used types.NewTaskContext -> kernel.NewTaskContext (+import barn/kernel),
  folded into harness commit via fixup+autosquash. Clean linear history:
  027e358 harness+first-wins / fb438f5 #2 list-size / 507b3b7 #4 dispatch (on 0bc99b3).
- go test vm/types/builtins PASS; bench deltas preserved on master base (int 101, list_append 626,
  index 193, nested 100).
DONE: master fast-forwarded to 507b3b7. Linear history on 0bc99b3:
  027e358 harness+first-wins / fb438f5 #2 list-size / 507b3b7 #4 dispatch.
REGRESSION GATE PASSED (against EXACT master base 0bc99b3):
  master-base full suite 3871/131 == integration full suite 3871/131. ZERO regression.
Temp worktrees barn-integrate, barn-masterbase removed; artifacts cleaned.
NOT pushed (origin/master is behind; pushing is outward-facing - left for Q).
Now-merged but still-present: branches perf/vm-bench, perf/list-size, perf/dispatch, perf/combined,
  perf/integrate + worktrees barn-vm-perf, barn-opt2-listsize, barn-opt4-dispatch (cleanup pending Q's ok).

### STATE: changes UNCOMMITTED in worktree ~/code/barn-vm-perf (branch perf/vm-bench).
  Files: vm/perf_bench_test.go (new), vm/op_arith.go, vm/op_list.go, types/int.go, builtins/types.go.
  Did NOT commit (Q's rule: commit only when asked). Offered to commit/PR.

### BIG structural wins for next phase (ranked): 1) unbox Value->tagged union (kills 2 allocs/iter
  everywhere, ~2-4x arith, big blast radius); 2) O(1) list size cache (kills 26% ValueBytes);
  3) amortized/in-place list append (collapses 17x); 4) dispatch inline + cache CurrentFrame (~55% share).
  Recommended order: 2 + 4 first (small), then 1 (rewrite, harness as A/B gate), then 3.

## Servers: stopped. Re-run bench: `bash bench/run_bench.sh` from WSL.
