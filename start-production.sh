#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
python -c 'import app'
python worker.py &
feed_pid=$!
trap 'kill "$feed_pid" 2>/dev/null || true' EXIT INT TERM
gunicorn --workers 2 --bind "${HOST:-127.0.0.1}:${PORT:-5050}" app:app
