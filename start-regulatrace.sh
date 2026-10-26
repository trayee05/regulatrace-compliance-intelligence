#!/usr/bin/env sh
set -eu

cd "$(dirname "$0")"
if [ ! -x .venv/bin/python ]; then
  if command -v python3.12 >/dev/null 2>&1; then
    python3.12 -m venv .venv
  else
    python3 -m venv .venv
  fi
fi

.venv/bin/python -m pip install -r requirements.txt
port="${REGULATRACE_PORT:-8000}"
printf 'RegulaTrace: http://127.0.0.1:%s/#executive\n' "$port"
exec .venv/bin/python -m uvicorn backend.main:app --host 127.0.0.1 --port "$port"
