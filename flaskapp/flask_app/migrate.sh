#!/usr/bin/env bash
# Idempotent DB migration runner used by the deploy.
#
# Invoke from the application root (the directory that holds flask_app/ and,
# where present, a .env):
#
#     SERVICE=cal-test bash flask_app/migrate.sh
#
# It (1) loads the same DB environment the systemd service uses -- so it talks
# to the same database as the running app even when DATABASE_* come from the
# unit's Environment=/EnvironmentFile= rather than a local .env -- then
# (2) finds a Python interpreter with pymysql (preferring the app's venv) and
# runs flask_app/migrate.py. Safe to run on every deploy.
set -euo pipefail

# --- 1. Load the service's environment (DATABASE_* etc.) ---------------------
# A plain SSH session does not inherit a systemd unit's environment, so pull it
# from the unit directly. migrate.py also calls load_dotenv() for a ./.env,
# which covers PythonAnywhere (no systemd).
load_service_env() {
  local svc="$1" ef line
  [ -n "$svc" ] || return 0
  command -v systemctl >/dev/null 2>&1 || return 0
  systemctl cat "$svc" >/dev/null 2>&1 || return 0

  # EnvironmentFile= entries (a leading '-' marks the file optional).
  while IFS= read -r ef; do
    ef="${ef#-}"
    if [ -n "$ef" ] && [ -f "$ef" ]; then
      set -a; . "$ef"; set +a
      echo "migrate: loaded EnvironmentFile $ef"
    fi
  done < <(systemctl cat "$svc" 2>/dev/null | sed -n 's/^EnvironmentFile=//p')

  # Inline Environment= entries (space-separated KEY=VALUE on one line).
  # if/fi, not `&&`, so an empty line under `set -e` doesn't abort the script.
  while IFS= read -r line; do
    if [ -n "$line" ]; then export "$line"; fi
  done < <(systemctl show "$svc" -p Environment --value 2>/dev/null | tr ' ' '\n')
}

load_service_env "${SERVICE:-}"

# --- 2. Pick an interpreter and run the migrations ---------------------------
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
