"""MOO server micro-benchmark: barn vs toaststunt over TCP socket.

Runs identical CPU-bound MOO workloads against one or more servers, measuring
wall-clock round-trip time per eval. Same work on every server => fair compare.

Usage:
    uv run python .tmp/bench.py toast=7801 barn=7802
"""
from __future__ import annotations

import statistics
import sys
import time

from moo_conformance.transport import SocketTransport

# Each workload: (name, MOO code, expected-value-or-None). Iteration counts are
# fixed so every server does identical work; sized so the C++ reference lands in
# the tens-to-hundreds of ms range.
WORKLOADS = [
    ("noop_latency",
     "return 0;", 0),
    ("int_arith_5M",
     "x = 0; for i in [1..5000000]; x = x + i; endfor; return x;",
     12500002500000),
    ("float_arith_5M",
     "x = 0.0; for i in [1..5000000]; x = x + 1.5; endfor; return x > 0.0;",
     1),
    ("string_concat_50k",
     's = ""; for i in [1..50000]; s = s + "x"; endfor; return length(s);',
     50000),
    ("list_append_30k",
     "l = {}; for i in [1..30000]; l = {@l, i}; endfor; return length(l);",
     30000),
    ("list_index_1M",
     "l = {}; for i in [1..1000]; l = {@l, i}; endfor; "
     "x = 0; for i in [1..1000000]; x = l[1 + (i % 1000)]; endfor; return x;",
     None),
    ("builtin_tostr_1M",
     "n = 0; for i in [1..1000000]; n = n + length(tostr(i)); endfor; return n;",
     None),
    ("prop_access_1M",
     "n = #0; x = 0; for i in [1..1000000]; x = typeof(n.name); endfor; return x;",
     None),
    ("verb_call_200k",
     "x = 0; for i in [1..200000]; x = x + abs(-i); endfor; return x;",
     20000100000),
    ("nested_loop_2500x2500",
     "c = 0; for i in [1..2500]; for j in [1..2500]; c = c + 1; endfor; endfor; return c;",
     6250000),
]

RAISE_LIMITS = (
    "try add_property($server_options, \"fg_ticks\", 2000000000, {$server_options.owner, \"r\"}); except (ANY) endtry "
    "try add_property($server_options, \"fg_seconds\", 30000, {$server_options.owner, \"r\"}); except (ANY) endtry "
    "try add_property($server_options, \"bg_ticks\", 2000000000, {$server_options.owner, \"r\"}); except (ANY) endtry "
    "try add_property($server_options, \"bg_seconds\", 30000, {$server_options.owner, \"r\"}); except (ANY) endtry "
    "return load_server_options();"
)

REPEATS = 5


def bench_server(name: str, port: int) -> dict[str, dict]:
    t = SocketTransport(host="localhost", port=port)
    t.connect("wizard")
    assert t.sock is not None
    t.sock.settimeout(180)  # heavy loops can run many seconds
    t.execute(RAISE_LIMITS)  # idempotent; ensures ceiling is raised

    results: dict[str, dict] = {}
    for wname, code, expected in WORKLOADS:
        # warm-up (parse/compile, JIT-ish warm caches) — not timed
        warm = t.execute(code)
        if not warm.success:
            results[wname] = {"error": warm.error_message or "exec failed"}
            continue
        times = []
        r = warm
        for _ in range(REPEATS):
            start = time.perf_counter()
            r = t.execute(code)
            times.append(time.perf_counter() - start)
        results[wname] = {
            "value": r.value,
            "ok_value": (expected is None or r.value == expected),
            "min_ms": min(times) * 1000,
            "median_ms": statistics.median(times) * 1000,
        }
    t.disconnect()
    return results


def main() -> None:
    servers = []
    for arg in sys.argv[1:]:
        nm, _, p = arg.partition("=")
        servers.append((nm, int(p)))
    if not servers:
        print("usage: bench.py name=port [name=port ...]")
        sys.exit(1)

    all_results = {nm: bench_server(nm, p) for nm, p in servers}

    names = [nm for nm, _ in servers]
    print(f"\nREPEATS={REPEATS}, reporting min(ms) [median(ms)] per workload\n")
    header = f"{'workload':<24}" + "".join(f"{nm:>20}" for nm in names) + "   ratio"
    print(header)
    print("-" * len(header))
    for wname, _code, _exp in WORKLOADS:
        cells = []
        mins = {}
        for nm in names:
            r = all_results[nm].get(wname, {})
            if "error" in r:
                cells.append(f"{'ERR':>20}")
                mins[nm] = None
            else:
                flag = "" if r["ok_value"] else "!"
                cells.append(f"{r['min_ms']:>10.2f}[{r['median_ms']:.1f}]{flag:>3}")
                mins[nm] = r["min_ms"]
        ratio = ""
        if len(names) == 2 and all(mins[nm] for nm in names):
            a, b = mins[names[0]], mins[names[1]]
            if a and b:
                ratio = f"  {names[1]}/{names[0]}={b / a:.1f}x"
        print(f"{wname:<24}" + "".join(cells) + ratio)


if __name__ == "__main__":
    main()
