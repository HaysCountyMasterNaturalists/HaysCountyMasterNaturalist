# Deploying to PythonAnywhere (legacy environment)

> **Status: legacy.** PythonAnywhere is where the app currently serves production traffic, but the intended future deploy path is the automated GitHub Actions workflow at `.github/workflows/deploy.yml` (pushes to `main` → `/opt/cal-prod`, pushes to `test` → `/opt/cal-test`, both via systemd on a self-hosted server). The GH Actions workflow does **not** deploy to PythonAnywhere — the two paths are independent.
>
> This document exists so that maintenance of the legacy PA deployment remains possible during the interim, and so the procedure isn't lost the next time it's needed.

This runbook was reconstructed and verified end-to-end on 2026-05-17 after the previous (manual-deploy) maintainer left.

## Infrastructure & ops — see the `calendar_infra` repo

The **systemd `cal-test` / `cal-prod` server is provisioned and documented separately** in
[HaysCountyMasterNaturalists/calendar_infra](https://github.com/HaysCountyMasterNaturalists/calendar_infra)
(Terraform). That repo's README is the source of truth for hosting and ops. Quick reference:

- **Host:** one **Hetzner Cloud CX22 VPS** running both environments. IP is a Hetzner floating IP (`terraform output -raw floating_ip`), stored as this repo's `SERVER_HOST` Actions secret; SSH key is `SSH_PRIVATE_KEY`.
- **Routing:** Caddy (auto TLS) → `calendar.haysmn.org` → gunicorn **:5000** (`cal-prod`, `/opt/cal-prod`); `test-calendar.haysmn.org` → gunicorn **:5001** (`cal-test`, `/opt/cal-test`).
- **DBs (local only; 3306 not exposed):** `cal_prod` / `cal_prod_user`, `cal_test` / `cal_test_user`. Connect remotely via SSH tunnel: `ssh -L 3307:localhost:3306 root@<ip>` then `mysql -h127.0.0.1 -P3307 -u cal_test_user -p cal_test`.
- **SSH:** `ssh -i ~/.ssh/hcmn_cal_deploy root@<floating_ip>`.
- **DB ops (manual GitHub Actions in `calendar_infra`):** *List Backups*, *Backup Database*, **Reset Test Database** (copies `cal_prod` → `cal_test`, then restarts cal-test — re-run `migrate.sh` afterward if the app schema is ahead of prod), *Restore Backup* (`CONFIRM` required for prod). Nightly backups run via cron → Google Drive / S3.
- **Note:** `calendar_infra/docs/app-repo-deploy-setup.md` is an idealized setup guide and is out of date with this repo's actual `deploy.yml` (factory app, SQLAlchemy strings, different secret names, test←dev). Trust `.github/workflows/deploy.yml` for current behavior.
- **Web-app login** is the app's own email/password against that environment's `master_naturalist` table (separate per env) — there are no shared/committed credentials.

## Production environment

| Thing | Value |
|---|---|
| PA account | `haysmn` |
| App root on PA | `~/mysite/` |
| WSGI file | `/var/www/haysmn_pythonanywhere_com_wsgi.py` |
| Reload mechanism | `touch` the WSGI file (no `systemctl` on PA) |
| Python interpreter | system `python3` (Python 3.10), packages installed with `pip install --user` |
| Virtualenv | none — `~/.virtualenvs/` only contains virtualenvwrapper hooks |
| MySQL host | `haysmn.mysql.pythonanywhere-services.com` |
| MySQL database | `haysmn$hcmn` (PA prefixes user DBs with `haysmn$`) |
| MySQL credentials | `~/.my.cnf` (used via `--defaults-file=~/.my.cnf`) |
| Production env vars | `~/mysite/.env` (loaded by `load_dotenv()` in `flask_app/__init__.py`) |

The WSGI file imports the module-level `app` directly:
```python
from flask_app import app as application
```

## Before you deploy: snapshot

Run this in a PA Bash console **every time** before touching the live app. The rollback step relies on this snapshot.

```sh
mkdir -p ~/backups
tar -czf ~/backups/mysite-pre-deploy-$(date +%Y%m%d-%H%M%S).tar.gz -C ~ mysite/
mysqldump --defaults-file=~/.my.cnf \
  -h haysmn.mysql.pythonanywhere-services.com \
  'haysmn$hcmn' > ~/backups/db-$(date +%Y%m%d-%H%M%S).sql
```

The `mysqldump` PROCESS-privilege warning about tablespaces is harmless on PA — the dump still completes.

Verify the file-tree backup is faithful:
```sh
mkdir -p /tmp/verify && rm -rf /tmp/verify/mysite
tar -xzf ~/backups/mysite-pre-deploy-*.tar.gz -C /tmp/verify
diff -rq ~/mysite /tmp/verify/mysite   # should print nothing, exit 0
rm -rf /tmp/verify
```

## Deploy

### 1. Build the Vue bundle locally

```sh
cd opportunities
nvm use                # uses .nvmrc → Node 22; Vite crashes on Node 16
npm install
npm run build
```

This writes new hashed assets into `flaskapp/flask_app/static/dist/assets/`.

### 2. Rewrite asset hashes in the Flask template

`flaskapp/flask_app/templates/opportunities/index.html` references hashed filenames that change on every build. Same sed pattern the GitHub Actions workflow uses:

```sh
cd ..   # back to repo root
JS_FILE=$(basename flaskapp/flask_app/static/dist/assets/index-*.js)
CSS_FILE=$(basename flaskapp/flask_app/static/dist/assets/index-*.css)
sed -i "s|dist/assets/index-[^'\"]*\.js|dist/assets/${JS_FILE}|g" \
  flaskapp/flask_app/templates/opportunities/index.html
sed -i "s|dist/assets/index-[^'\"]*\.css|dist/assets/${CSS_FILE}|g" \
  flaskapp/flask_app/templates/opportunities/index.html
```

### 3. Build the deploy tarball

```sh
cd flaskapp
tar -czf ~/flask_app-deploy-$(date +%Y%m%d-%H%M%S).tar.gz \
  --exclude='__pycache__' --exclude='*.pyc' --exclude='schema.sql' \
  flask_app/
```

Size is typically ~450KB (mostly the JS bundle). The tarball contains only `flask_app/` — nothing from `instance/` or `.env`, so the swap below won't touch production config.

### 4. Upload via the PA Files UI

1. PA dashboard → **Files** tab
2. Navigate to `/home/haysmn/`
3. **Upload a file** → pick the tarball from step 3
4. Confirm it appears in the listing

### 5. Swap in the new code (PA Bash console)

```sh
# Sanity check
ls -lh ~/flask_app-deploy-*.tar.gz

# Park the current flask_app so we can revert fast
mv ~/mysite/flask_app ~/mysite/flask_app.preswap

# Extract the new code in place
tar -xzf ~/flask_app-deploy-*.tar.gz -C ~/mysite/

# Confirm contents
ls -la ~/mysite/flask_app/
ls -lh ~/mysite/flask_app/static/dist/assets/

# Confirm .env and instance/ are untouched
ls -la ~/mysite/.env ~/mysite/instance/

# Apply any pending DB schema migrations BEFORE the reload, so the new code and
# its schema go live together. Idempotent — safe to run on every deploy; prints
# "already present, skipping" when there's nothing to do. PA has no venv, so the
# system python3 (with the --user pymysql/python-dotenv) runs it; cwd must be
# ~/mysite so load_dotenv() picks up ~/mysite/.env for the DB credentials.
cd ~/mysite && python3 flask_app/migrate.py

# Reload the web app
touch /var/www/haysmn_pythonanywhere_com_wsgi.py
```

This is the same `flask_app/migrate.py` the systemd deploy runs automatically — on PA you run it by hand (one line) as part of the swap. Adding a future column is identical: commit the guarded step to `migrate.py`, and it gets applied on the next deploy to each environment. Back up first via the snapshot step above; if a migration ever needs reverting, restore the SQL dump (migrations here are forward-only).

### 6. Smoke test in the browser

1. Load https://haysmn.pythonanywhere.com/ (first request after a reload can take 5–15s).
2. Confirm the opportunities list renders — proves `load_dotenv()` populated `DATABASE_URL` and DB queries work.
3. Log in as a known user — proves `SECRET_KEY` round-trips for sessions and CSRF.
4. Edit an opportunity (if you have project_coordinator or admin) — proves writes still work and role gating is intact.
5. Watch the PA error log either via the **Web tab → Log files** UI or `tail -f /var/log/haysmn.pythonanywhere.com.error.log` for tracebacks.

### 7. Cleanup (after the deploy stays healthy)

```sh
rm -rf ~/mysite/flask_app.preswap
```

Keep the `~/backups/` snapshots — they're cheap insurance.

## Rollback

If anything is broken after step 5 or 6:

```sh
rm -rf ~/mysite/flask_app
mv ~/mysite/flask_app.preswap ~/mysite/flask_app
touch /var/www/haysmn_pythonanywhere_com_wsgi.py
```

This works because step 5 deliberately left `~/mysite/flask_app.preswap` in place — the `mv` was a single atomic rename within the same filesystem, so it's instant.

If the issue surfaced later (after step 7 cleanup) or affected the database too, restore from the snapshot tarball + SQL dump instead:

```sh
# Code: extract the snapshot and atomically swap
mkdir -p ~/staging && rm -rf ~/staging/mysite
tar -xzf ~/backups/mysite-pre-deploy-<timestamp>.tar.gz -C ~/staging
mv ~/mysite ~/mysite.old
mv ~/staging/mysite ~/mysite
rmdir ~/staging

# DB: restore the SQL dump
mysql --defaults-file=~/.my.cnf \
  -h haysmn.mysql.pythonanywhere-services.com \
  'haysmn$hcmn' < ~/backups/db-<timestamp>.sql

# Reload
touch /var/www/haysmn_pythonanywhere_com_wsgi.py

# After confirming the rolled-back app is healthy:
rm -rf ~/mysite.old
```

## Gotchas

- **`load_dotenv()` is mandatory for PA.** The PA WSGI process doesn't source a shell, so without it `~/mysite/.env` is silently ignored and the app starts with `DATABASE_URL=None`. The call lives in `flask_app/__init__.py` and is a no-op when the file is missing, so it's safe to keep for the systemd deployment too.
- **The Vue build needs Node 22.** Node 16 will crash with `crypto.getRandomValues is not a function`. Run `nvm use` to pick up `.nvmrc`.
- **Downloading PA tarballs decompresses them in transit.** If you grab one via the Files UI, extract with `tar -xf` (not `tar -xzf`) — the `.tar.gz` extension is stale. Uploads to PA are not affected.
- **`schema.sql` is unused.** The DB tables come from `db.init_db()` Python code, not from `schema.sql`. Safe to exclude from deploy tarballs.
- **New dependencies must be installed by hand on PA.** Unlike the systemd deploy (which runs `pip install -r requirements.txt`), the PA tarball contains only `flask_app/` — not `requirements.txt`. When a deploy adds a package (e.g. `python-dotenv`), `pip install --user <package>` in a PA Bash console before reloading, or the app will crash on import. Compare `requirements.txt` against `pip freeze --user` when in doubt.

---

# Schema migrations

Schema lives in two places that must stay consistent:
- `flask_app/db.py:init_db()` — the full current schema, used to build a **fresh** DB. `flask init-db` **drops and recreates** the tables (destructive — never run it against a live DB).
- `flask_app/migrate.py` — **idempotent, incremental** migrations for **existing** DBs. Each migration checks the current schema (via `information_schema`, since MySQL has no `ADD COLUMN IF NOT EXISTS`) and only applies a change when it's missing, so it's safe to run repeatedly.

When you change a table definition in `db.py`, add the matching guarded step to `migrate.py` (e.g. another `ensure_column(...)`). That single script is what brings every existing environment up to date.

## systemd (`cal-test` / `cal-prod`)

**Automatic.** After code sync, `.github/workflows/deploy.yml` runs `venv/bin/python -m pip install -r requirements.txt` (so new dependencies land before the app restarts — a missing dep crashes gunicorn on boot → 502), then `flask_app/migrate.sh` (which finds the app's Python and runs `migrate.py`) **before** the service restart — so any new column exists before the new code starts serving. The restart step then waits and checks `systemctl is-active`, so a crash-on-boot fails the deploy instead of shipping a dead service. Just commit the migration; pushing to `test` / `main` applies it.

The unit (`cal-test.service`) loads its DB creds via `EnvironmentFile=/opt/cal-test/.env`, and `migrate.sh` loads that same unit environment, so both the app and the migration target the same DB (`cal_test` as `cal_test_user`, not the `hcmn`/`root` dev defaults).

The migration step reads DB credentials the same way the app does (`DATABASE_*` from `/opt/cal-test/.env`, loaded via `load_dotenv()`), so it always targets the same DB the app uses. If the step fails, the workflow stops *before* the restart, leaving the old code running — fail-safe.

> **Note:** if a server ever supplies DB creds only through the systemd unit's `Environment=`/`EnvironmentFile=` (not a readable `.env` in the app dir), the deploy-time SSH session won't see them and `migrate.py` would fall back to defaults. Confirm `/opt/cal-test/.env` exists; if not, point `migrate.sh`/the deploy step at the unit's env file.

**Manual run** (ad-hoc, or to pre-seed before a force-push):
```sh
ssh root@<SERVER_HOST>
cd /opt/cal-test            # or /opt/cal-prod
bash flask_app/migrate.sh
```

## Migration log

One line per schema change so each environment's drift from `init_db()` is auditable.

| Change | Source commit | local | cal-test | cal-prod | PA (legacy) |
|---|---|---|---|---|---|
| `opportunities.recurring_days VARCHAR(20)` | f2e8b00 (multi-day weekly recurrence) | ✅ applied 2026-06-06 | ✅ applied 2026-06-06 (deploy) | auto on next deploy to `main` | pending (see PA section) |
