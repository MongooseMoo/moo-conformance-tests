#!/usr/bin/env bash
# Launch barn + toaststunt on WSL and benchmark them with bench/bench.py.
#
# Run from WSL:  bash bench/run_bench.sh
# Both servers run on Linux localhost; the Python harness connects over TCP
# (WSL2 forwards localhost so it also works from a Windows-side `uv run`).
set -euo pipefail

REPO=/mnt/c/Users/Q/code/moo-conformance-tests
BARN=/mnt/c/Users/Q/code/barn
TOAST=/mnt/c/Users/Q/src/toaststunt
DB="$REPO/src/moo_conformance/_db/Test.db"
TOAST_PORT=7801
BARN_PORT=7802

echo "==> building barn (linux)"
( cd "$BARN" && go build -o /tmp/barn_linux ./cmd/barn )

# toast: use the existing Release -O3 ELF build; rebuild instructions in report.
TOAST_BIN="$TOAST/moo"
[ -x "$TOAST_BIN" ] || TOAST_BIN="$TOAST/build/moo"

echo "==> copying DB to linux-local /tmp (avoid 9p IO noise)"
cp "$DB" /tmp/toast_in.db
cp "$DB" /tmp/barn_in.db

echo "==> killing any stale servers"
pkill -f 'moo /tmp/toast_in.db' 2>/dev/null || true
pkill -f 'barn_linux'          2>/dev/null || true
sleep 1

echo "==> starting toast on :$TOAST_PORT"
nohup "$TOAST_BIN" /tmp/toast_in.db /tmp/toast_out.db -p "$TOAST_PORT" >/tmp/toast.log 2>&1 &
echo "==> starting barn on :$BARN_PORT"
nohup /tmp/barn_linux -db /tmp/barn_in.db -port "$BARN_PORT" >/tmp/barn.log 2>&1 &
sleep 3

echo "==> running benchmark (harness raises tick limits via \$server_options)"
cd "$REPO"
uv run python bench/bench.py "toast=$TOAST_PORT" "barn=$BARN_PORT"

echo "==> stopping servers"
pkill -f 'moo /tmp/toast_in.db' 2>/dev/null || true
pkill -f 'barn_linux'          2>/dev/null || true
