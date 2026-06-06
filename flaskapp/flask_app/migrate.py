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

            # Add future migrations below, each guarded so it is a no-op once
            # applied (use ensure_column, or a SHOW/information_schema check).

            print("Migrations complete.")
    finally:
        conn.close()


if __name__ == '__main__':
    try:
        run()
    except Exception as error:
        print(f"migrate: FAILED: {error}", file=sys.stderr)
        sys.exit(1)
