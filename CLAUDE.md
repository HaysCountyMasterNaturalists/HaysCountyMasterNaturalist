# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Architecture

This is a two-tier app for the Hays County Master Naturalist chapter: a Vue 3 SPA frontend served by a Flask backend that talks to MySQL.

- **`opportunities/`** — Vue 3 + Vite SPA. Uses `vue-router` (web history), `@vueform/vueform` for forms, `vue-final-modal` for modals, axios for API calls. Vite builds into `../flaskapp/flask_app/static/dist` (see `vite.config.js`).
- **`flaskapp/flask_app/`** — Flask app split into three blueprints registered in `__init__.py`:
  - `auth.py` — signup/login/logout, password reset via signed token (`itsdangerous.URLSafeTimedSerializer` salted with the user's current password hash, 3-day expiry), and the `admin_required` / `editor_required` decorators. `g.user` is populated per-request from the session in `load_logged_in_user`.
  - `opportunities.py` — CRUD on opportunities + the catch-all `/` route that serves the SPA via `templates/opportunities/index.html`. Write endpoints are gated by `@editor_required`; non-admins can only modify rows they own.
  - `users.py` — admin-only user list/role-flag updates.
- **DB** — MySQL via PyMySQL with `autocommit=True`; all queries use a per-request cursor from `db.get_db()` and named parameters. Two tables, defined in `db.init_db()` (NOT `schema.sql` — that file is unused in the init path): `master_naturalist` (with `admin` and `project_coordinator` boolean flags) and `opportunities` (FK to `master_naturalist.id` via `owner`).

### Cross-cutting things to know

- **CSRF** — Flask-WTF `CSRFProtect` is on. The `after_request` hook in `__init__.py` sets a `CSRF-TOKEN` cookie/header on every response; the Vue app picks it up via an axios response interceptor in `src/main.js` and sends it back as `X-CSRFToken`. Initial token is also injected into `index.html` as `window.CSRF_TOKEN`.
- **DEV mode CORS** — Setting `DEV=1` adds CORS headers for `http://localhost:5173` (the Vite dev server) including credentials and the CSRF-TOKEN expose header. Without `DEV=1`, the Flask server expects to serve the built SPA itself.
- **Times** — Datetimes are stored as UTC in MySQL. The backend localizes to `US/Central` (`pytz`) when returning data to the client and parses incoming `YYYY-MM-DD HH:MM` strings (with am/pm suffix handling in `clean_date`) as Central before storing as UTC.
- **Recurring events** — `opportunities.find_recurring()` expands `recurring_weekly` and `recurring_monthly` opportunities server-side into individual occurrences from 45 days back to 6 months out, before sending to the client. `recurring_monthly` is an integer N meaning "the Nth week of the month."
- **SPA routing** — `index()` in `opportunities.py` is a catch-all (`/` and `/<path:path>`) so deep links resolve client-side. Don't add Flask routes that would shadow SPA routes defined in `src/main.js`.
- **Roles** — three tiers, encoded as boolean flags on `master_naturalist`: regular user (read-only API access), `project_coordinator` (can create/edit/delete their own opportunities), `admin` (can edit/delete anyone's, manage users, generate password-reset links). Use `@editor_required` for write endpoints and `@admin_required` for admin-only endpoints — don't roll your own checks.

## Development

Node version is pinned to 22 via `.nvmrc`. If you use nvm, run `nvm use` (no args) in the repo root — it reads `.nvmrc` and switches automatically. On older Node (e.g. 16), `vite build` crashes with `crypto.getRandomValues is not a function`. Python deps are in `flaskapp/requirements.txt`.

**Frontend dev (Vite, hot reload):**
```sh
cd opportunities && npm install && npm run dev   # serves http://localhost:5173
```

**Backend dev (Flask, separate terminal):**
```sh
cd flaskapp
pip install -r requirements.txt
export DEV=1                                # required when running Vite separately, enables CORS
flask --app flask_app init-db               # first time only — drops & recreates tables
flask --app flask_app run
```
DB defaults (override with `DATABASE_URL`/`DATABASE_NAME`/`DATABASE_USER`/`DATABASE_PASSWORD` env vars): `localhost` / `hcmn` / `root` / `armadillo`. Create the `hcmn` database in MySQL before running `init-db`.

**Production build:** `npm run build` from `opportunities/` produces hashed asset filenames in `flaskapp/flask_app/static/dist/assets/`. The `index.html` template references those filenames directly — the deploy workflow rewrites them via `sed` (see `.github/workflows/deploy.yml`). When testing a prod-style build locally, update the `<script>` and `<link>` tags in `templates/opportunities/index.html` to match the new hash, or run the same sed substitution.

## Tests

Playwright + axe-core accessibility tests live in `opportunities/tests/`. The Playwright config auto-starts the Vite dev server, so Flask does NOT need to be running for these tests — they exercise the static SPA shell.

```sh
cd opportunities
npm test                              # all tests, both chromium-light and chromium-dark projects
npm run test:ui                       # interactive UI mode
npx playwright test accessibility     # filter by name
npx playwright test --project=chromium-light --grep "color contrast"
```

CI runs these on PRs to `main` and `dev` (`.github/workflows/test.yml`).

## Deployment

`.github/workflows/deploy.yml` deploys on push:
- push to `test` → test environment (`/opt/cal-test`, systemd unit `cal-test`)
- push to `main` → prod environment (`/opt/cal-prod`, systemd unit `cal-prod`)

The flow: build Vue → sed-rewrite asset hashes in `index.html` → rsync `flaskapp/` to the server → write a one-line `wsgi.py` → restart the systemd unit. `dev` is the default working branch; PRs typically target `dev`, and `dev` is later merged to `test` / `main` to deploy.
