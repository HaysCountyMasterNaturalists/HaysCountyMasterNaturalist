#!/usr/bin/env bash
# Idempotent DB migration runner used by the deploy.
#
# Invoke from the application root (the directory that holds flask_app/ and the
# server's .env):
#
#     bash flask_app/migrate.sh
#
# It finds a Python interpreter that has pymysql -- preferring the app's
# virtualenv, falling back to the system python -- and runs flask_app/migrate.py
# from the current directory (so migrate.py's load_dotenv() reads ./.env).
# Safe to run on every deploy.
set -euo pipefail

find_python() {
  local cand
  # Prefer a venv sitting next to the app (rsync excludes it, so it persists).
  for cand in venv/bin/python venv/bin/python3 .venv/bin/python; do
    if [ -x "$cand" ] && "$cand" -c 'import pymysql' >/dev/null 2>&1; then
      echo "$cand"; return 0
    fi
  done
  # Otherwise any system python that can import pymysql.
  for cand in python3 python; do
    if command -v "$cand" >/dev/null 2>&1 && "$cand" -c 'import pymysql' >/dev/null 2>&1; then
      echo "$cand"; return 0
    fi
  done
  return 1
}

PY="$(find_python)" || { echo "migrate: no Python with pymysql found" >&2; exit 1; }
echo "migrate: using $PY"
exec "$PY" flask_app/migrate.py
