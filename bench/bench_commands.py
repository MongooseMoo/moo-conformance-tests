"""Real-command benchmark: typed player commands against live MOO servers.

Complements bench.py (eval micro-workloads): this drives the TYPED command
path — parse, #0:do_command dispatch, verb execution, output — as a logged-in
player, the same mix barn's in-process mongoose harness uses
(barn scheduler/mongoose_real_bench_test.go: look/say/i/@who/home).

Per-command completion is detected with the OUTPUTSUFFIX intrinsic: the server
brackets every command's output with the suffix line, so the round trip is
timed from write to suffix-echo without guessing at output shapes.

Usage (each server already running the SAME database):
    BENCH_LOGIN_SCRIPT=$'PROXY TCP4 203.0.113.5 127.0.0.1 50000 {port}\nq\ncanefan' \
        uv run python bench/bench_commands.py toast=7801 barn=7802

The login script is newline-separated raw lines sent before the mix; a
literal {port} is substituted with the server's port (mongoose's trusted-proxy
prelude embeds it).
"""
from __future__ import annotations

import os
import socket
import statistics
import sys
import time

SUFFIX_TAG = "===BENCH-DONE==="
WARMUP_PER_SHAPE = 3
REPEATS = 60
IDLE_TIMEOUT = 30.0

COMMANDS = [
    ("look", "look"),
    ("say", "say Hello there, this is a benchmark message!"),
    ("inventory", "i"),
    ("who", "@who"),
    ("home", "home"),
]


class Conn:
    def __init__(self, port: int):
        self.sock = socket.create_connection(("localhost", port), timeout=IDLE_TIMEOUT)
        self.sock.settimeout(IDLE_TIMEOUT)
        self.buf = b""

    def send_line(self, line: str) -> None:
        self.sock.sendall(line.encode() + b"\r\n")

    def read_line(self) -> str:
        while b"\n" not in self.buf:
            chunk = self.sock.recv(4096)
            if not chunk:
                raise ConnectionError("server closed connection")
            self.buf += chunk
        line, self.buf = self.buf.split(b"\n", 1)
        return line.rstrip(b"\r").decode(errors="replace")

    def drain_until(self, needle: str, quiet_ok: bool = False) -> None:
        deadline = time.monotonic() + IDLE_TIMEOUT
        while time.monotonic() < deadline:
            try:
                if self.read_line().strip() == needle:
                    return
            except socket.timeout:
                break
        if not quiet_ok:
            raise TimeoutError(f"never saw {needle!r}")

    def close(self) -> None:
        try:
            self.sock.close()
        except OSError:
            pass


def bench_server(name: str, port: int, login: list[str]) -> dict[str, dict]:
    c = Conn(port)
    # Give the banner a moment, then run the login lines with small gaps
    # (mongoose's login is read()-based and prompt-driven).
    time.sleep(1.0)
    for line in login:
        c.send_line(line.replace("{port}", str(port)))
        time.sleep(1.0)
    # Post-login output (MOTD, room render) settles; then arm the suffix.
    time.sleep(3.0)
    c.send_line(f"OUTPUTSUFFIX {SUFFIX_TAG}")
    time.sleep(0.5)
    c.buf = b""
    # Prove the bracket works before timing anything, and settle location
    # (guests spawn wherever the pool parked them; home normalizes).
    c.send_line("look")
    c.drain_until(SUFFIX_TAG)
    c.send_line("home")
    c.drain_until(SUFFIX_TAG)

    results: dict[str, dict] = {}
    for shape, cmd in COMMANDS:
        for _ in range(WARMUP_PER_SHAPE):
            c.send_line(cmd)
            c.drain_until(SUFFIX_TAG)
        times = []
        for _ in range(REPEATS):
            start = time.perf_counter()
            c.send_line(cmd)
            c.drain_until(SUFFIX_TAG)
            times.append(time.perf_counter() - start)
        results[shape] = {
            "min_ms": min(times) * 1000,
            "median_ms": statistics.median(times) * 1000,
            "p90_ms": sorted(times)[int(len(times) * 0.9)] * 1000,
        }
    c.send_line("@quit")
    c.close()
    return results


def main() -> None:
    raw = os.environ.get("BENCH_LOGIN_SCRIPT", "")
    login = [ln for ln in raw.splitlines() if ln.strip()]
    if not login:
        print("BENCH_LOGIN_SCRIPT must hold newline-separated login lines")
        sys.exit(1)
    servers = []
    for arg in sys.argv[1:]:
        nm, _, p = arg.partition("=")
        servers.append((nm, int(p)))
    if not servers:
        print("usage: bench_commands.py name=port [name=port ...]")
        sys.exit(1)

    all_results = {nm: bench_server(nm, p, login) for nm, p in servers}

    names = [nm for nm, _ in servers]
    print(f"\ntyped-command round trips, REPEATS={REPEATS}, min[median/p90] ms\n")
    header = f"{'command':<12}" + "".join(f"{nm:>28}" for nm in names) + "   ratio(min)"
    print(header)
    print("-" * len(header))
    for shape, _cmd in COMMANDS:
        cells = []
        mins = {}
        for nm in names:
            r = all_results[nm][shape]
            cells.append(f"{r['min_ms']:>10.2f}[{r['median_ms']:.1f}/{r['p90_ms']:.1f}]")
            mins[nm] = r["min_ms"]
        ratio = ""
        if len(names) == 2:
            a, b = mins[names[0]], mins[names[1]]
            ratio = f"  {names[1]}/{names[0]}={b / a:.2f}x"
        print(f"{shape:<12}" + "".join(f"{cell:>28}" for cell in cells) + ratio)


if __name__ == "__main__":
    main()
