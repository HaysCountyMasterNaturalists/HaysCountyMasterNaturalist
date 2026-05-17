# Deploying to PythonAnywhere

This runbook covers manual deploys of the HCMN app to PythonAnywhere. It was reconstructed and verified end-to-end on 2026-05-17 after the previous (manual-deploy) maintainer left.

The unrelated GitHub Actions workflow at `.github/workflows/deploy.yml` targets a different self-hosted systemd setup (`/opt/cal-test`, `/opt/cal-prod`); it does **not** deploy to PythonAnywhere.

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

# Reload the web app
touch /var/www/haysmn_pythonanywhere_com_wsgi.py
```

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
