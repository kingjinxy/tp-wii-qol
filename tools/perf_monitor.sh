#!/usr/bin/env bash
# Launch tools/perf_monitor.py from anywhere, using the repo's .venv.
# Usage: tools/perf_monitor.sh [--csv perf.csv] [--interval 0.5]
set -e
REPO="$(cd "$(dirname "$(readlink -f "$0")")/.." && pwd)"
if [ ! -x "$REPO/.venv/bin/python" ]; then
    echo "Setting up $REPO/.venv ..."
    python3 -m venv "$REPO/.venv"
    "$REPO/.venv/bin/pip" install -q dolphin-memory-engine
fi
exec "$REPO/.venv/bin/python" "$REPO/tools/perf_monitor.py" "$@"
