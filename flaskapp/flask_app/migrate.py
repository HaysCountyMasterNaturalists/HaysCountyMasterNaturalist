"""Idempotent database migrations for the HCMN calendar app.

Run from the application root (the directory that contains the ``flask_app/``
package and, on the servers, the ``.env`` file)::

    python flask_app/migrate.py

Every migration here is written to be safe to run repeatedly: it inspects the
current schema and only applies a change when it is missing. That means this
script can run on *every* deploy without harm, and can also be run by hand on
any target (systemd server, PythonAnywhere, or local).

The DB connection mirrors ``flask_app/db.py`` exactly -- it reads the same
``DATABASE_*`` environment variables, and (like ``flask_app/__init__.py``)
loads an optional ``.env`` from the working directory first.
"""
import os
import sys

import pymysql

try:
    from dotenv import load_dotenv
    load_dotenv()  # picks up ./.env when present, matching flask_app/__init__.py
except ImportError:
    pass


def connect():
    """Open a connection using the same defaults as flask_app/db.py:get_db()."""
    host = os.environ.get('DATABASE_URL') or 'localhost'
    name = os.environ.get('DATABASE_NAME') or 'hcmn'
    user = os.environ.get('DATABASE_USER') or 'root'
    # Diagnostic only -- never print the password.
    print(f"  connecting as {user}@{host}/{name}")
    return pymysql.connect(
        host=host,
        database=name,
        user=user,
        password=os.environ.get('DATABASE_PASSWORD') or '',
        autocommit=True,
    )


def column_exists(cursor, table, column):
    cursor.execute(
        "SELECT 1 FROM information_schema.columns "
        "WHERE table_schema = DATABASE() "
        "AND table_name = %s AND column_name = %s",
        (table, column),
    )
    return cursor.fetchone() is not None


def ensure_column(cursor, table, column, definition):
    """Add ``column`` to ``table`` if it isn't there yet.

    MySQL has no ``ADD COLUMN IF NOT EXISTS``, so we check information_schema
    first. ``definition`` is the full column spec, e.g.
    ``"recurring_days VARCHAR(20) AFTER recurring_monthly"``.
    """
    if column_exists(cursor, table, column):
        print(f"  - {table}.{column}: already present, skipping")
        return False
    cursor.execute(f"ALTER TABLE {table} ADD COLUMN {definition}")
    print(f"  - {table}.{column}: added")
    return True


def table_exists(cursor, table):
    cursor.execute(
        "SELECT 1 FROM information_schema.tables "
        "WHERE table_schema = DATABASE() AND table_name = %s",
        (table,),
    )
    return cursor.fetchone() is not None


def ensure_table(cursor, table, ddl):
    """Create ``table`` from ``ddl`` if it doesn't exist. Returns True if it
    was just created (so one-time seeding can be tied to creation)."""
    if table_exists(cursor, table):
        print(f"  - table {table}: already present, skipping")
        return False
    cursor.execute(ddl)
    print(f"  - table {table}: created")
    return True


def run():
    conn = connect()
    try:
        with conn.cursor() as cursor:
            print("Applying migrations...")

            # 2026-06 (commit f2e8b00): multi-day weekly recurrence.
            ensure_column(
                cursor, 'opportunities', 'recurring_days',
                'recurring_days VARCHAR(20) AFTER recurring_monthly',
            )

            # 2026-06 (#24): record who last created/updated an opportunity.
            ensure_column(
                cursor, 'opportunities', 'updated_by',
                'updated_by INT AFTER owner',
            )

            # 2026-06 (#26): project registry, populated by the admin
            # spreadsheet import (POST /api/projects/import). Starts empty.
            ensure_table(cursor, 'projects', """
                CREATE TABLE projects (
                    project_id VARCHAR(50) PRIMARY KEY,
                    name VARCHAR(255),
                    categories VARCHAR(100),
                    last_imported DATETIME
                )
            """)
            # last_imported flags which projects were in the most recent import
            # (older/NULL => "not in latest upload"). ensure_column covers a
            # projects table created before this column existed.
            ensure_column(cursor, 'projects', 'last_imported', 'last_imported DATETIME')

            # 2026-06 (#26): coordinators are assigned to a (project, category)
            # combination -- edit rights come from a matching row here (plus
            # admins), not from ownership. (Renamed from project_assignments,
            # which was never deployed.)
            cursor.execute("DROP TABLE IF EXISTS project_assignments")
            created = ensure_table(cursor, 'coordinator_assignments', """
                CREATE TABLE coordinator_assignments (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    project_id VARCHAR(50) NOT NULL,
                    category VARCHAR(50) NOT NULL,
                    coordinator_id INT NOT NULL,
                    created DATETIME DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE KEY uq_combo_coordinator (project_id, category, coordinator_id),
                    CONSTRAINT fk_ca_coordinator FOREIGN KEY (coordinator_id)
                        REFERENCES master_naturalist(id)
                )
            """)
            if created:
                # One-time seed: keep current opportunity owners as coordinators
                # of the (project, category) combos they've posted for. AT/EV are
                # exempt (not assignment-gated), so they're excluded.
                n = cursor.execute("""
                    INSERT IGNORE INTO coordinator_assignments (project_id, category, coordinator_id)
                    SELECT DISTINCT o.project_id, o.category, o.owner
                    FROM opportunities o
                    JOIN master_naturalist m ON m.id = o.owner
                    WHERE o.project_id IS NOT NULL AND o.project_id <> ''
                      AND o.category NOT IN ('AT', 'EV')
                      AND (m.project_coordinator = 1 OR m.admin = 1)
                """)
                print(f"  - coordinator_assignments: seeded {n} owner rows from opportunities")

            # 2026-06 (#24): per-action audit log (full snapshot each time).
            # No FK to opportunities so history survives deletes.
            ensure_table(cursor, 'opportunity_history', """
                CREATE TABLE opportunity_history (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    opportunity_id INT,
                    action VARCHAR(10),
                    changed_by INT,
                    changed_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    snapshot JSON
                )
            """)

            # 2026-06: record each user's last successful login (stamped in
            # auth.signin). NULL until the user next logs in -- no backfill.
            ensure_column(
                cursor, 'master_naturalist', 'last_login',
                'last_login DATETIME AFTER project_coordinator',
            )

            # 2026-06: store the field-level diff (old/new per field) computed at
            # edit time, so the history view doesn't have to infer it from
            # neighbouring snapshots (which breaks for pre-audit opportunities).
            ensure_column(
                cursor, 'opportunity_history', 'changes',
                'changes JSON AFTER snapshot',
            )

            # Add future migrations below, each guarded so it is a no-op once
            # applied (use ensure_column / ensure_table).

            print("Migrations complete.")
    finally:
        conn.close()


if __name__ == '__main__':
    try:
        run()
    except Exception as error:
        print(f"migrate: FAILED: {error}", file=sys.stderr)
        sys.exit(1)
