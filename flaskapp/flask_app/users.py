import io
import re

import openpyxl
from flask import Blueprint, request

from flask_app.auth import admin_required
from flask_app.db import get_db


bp = Blueprint('users', __name__)

EMAIL_RE = re.compile(r'[\w.\-+]+@[\w.\-]+\.\w+')

# The category codes the app recognizes (see utils.js CATEGORY_CODES).
KNOWN_CATEGORIES = {'PO', 'DO', 'TG', 'RM', 'NPA', 'CB', 'FR', 'AT', 'EV'}


def clean_categories(raw, skipped=None):
    '''Parse a spreadsheet "Categories" cell into a deduped, ordered list of
    valid category codes. Tolerates messy delimiters (commas, periods,
    semicolons, slashes, newlines, e.g. the "PO. DO" typo) and drops anything
    not in KNOWN_CATEGORIES, recording drops in ``skipped``.'''
    out = []
    for token in re.split(r'[,\n.;/]+', raw):
        code = token.strip().upper()
        if not code:
            continue
        if code in KNOWN_CATEGORIES:
            if code not in out:
                out.append(code)
        elif skipped is not None:
            skipped.add(code)
    return out

@bp.route('/api/users')
@admin_required
def list():
    users = []
    with get_db() as cursor:
        cursor.execute(
            """SELECT id, email, admin, project_coordinator FROM master_naturalist"""
        )

        db_users = cursor.fetchall()
        users = [{'id': user[0], 'email': user[1], 'admin': user[2], 'project_coordinator': user[3]} for user in db_users]

    return users

@bp.route('/api/users/<int:id>', methods=['POST'])
@admin_required
def update(id):
    data = request.get_json()
    try:
        with get_db() as cursor:
            cursor.execute(
                """UPDATE master_naturalist
                    SET
                        admin = %(admin)s,
                        project_coordinator = %(project_coordinator)s
                    WHERE id = %(id)s""",
                {
                    'id': id,
                    'admin': 1 if data.get('admin') else 0,
                    'project_coordinator': 1 if data.get('project_coordinator') else 0,
                }
            )
    except Exception as e:
        return { 'error': str(e) }, 400

    return { 'success': True }


@bp.route('/api/assignments')
@admin_required
def list_assignments():
    '''All (project, category) <-> coordinator assignments, with email.'''
    with get_db() as cursor:
        cursor.execute(
            """SELECT ca.id, ca.project_id, ca.category, ca.coordinator_id, m.email
                FROM coordinator_assignments ca
                JOIN master_naturalist m ON m.id = ca.coordinator_id
                ORDER BY ca.project_id, ca.category, m.email"""
        )
        rows = cursor.fetchall()
    return [
        {'id': r[0], 'project_id': r[1], 'category': r[2],
         'coordinator_id': r[3], 'email': r[4]}
        for r in rows
    ]


@bp.route('/api/assignments', methods=['POST'])
@admin_required
def create_assignment():
    data = request.get_json()
    project_id = (data.get('project_id') or '').strip()
    category = (data.get('category') or '').strip()
    coordinator_id = data.get('coordinator_id')
    if not project_id or not category or not coordinator_id:
        return { 'error': 'project_id, category and coordinator_id are required' }, 400
    try:
        with get_db() as cursor:
            cursor.execute(
                """INSERT INTO coordinator_assignments (project_id, category, coordinator_id)
                    VALUES (%(project_id)s, %(category)s, %(coordinator_id)s)""",
                {'project_id': project_id, 'category': category, 'coordinator_id': coordinator_id}
            )
    except Exception as e:
        return { 'error': str(e) }, 400

    return { 'success': True }


@bp.route('/api/assignments/delete/<int:id>', methods=['POST'])
@admin_required
def delete_assignment(id):
    try:
        with get_db() as cursor:
            cursor.execute(
                "DELETE FROM coordinator_assignments WHERE id = %(id)s",
                {'id': id}
            )
    except Exception as e:
        return { 'error': str(e) }, 400

    return { 'success': True }


@bp.route('/api/projects/import', methods=['POST'])
@admin_required
def import_projects():
    '''Populate the project registry + coordinator assignments from an uploaded
    "Current Projects" spreadsheet. Upserts projects, and for each coordinator
    email that matches an existing user, creates an assignment. Reports emails
    that didn't match (no users are created). Nothing is persisted to the repo.'''
    upload = request.files.get('file')
    if upload is None:
        return { 'error': 'No file uploaded' }, 400
    try:
        wb = openpyxl.load_workbook(io.BytesIO(upload.read()), data_only=True)
    except Exception as e:
        return { 'error': f'Could not read spreadsheet: {e}' }, 400

    # Prefer the "ACTIVE Projects" sheet; fall back to the first sheet.
    ws = next(
        (s for s in wb.worksheets
         if 'active' in s.title.lower() and 'project' in s.title.lower()),
        wb.worksheets[0]
    )

    try:
        with get_db() as cursor:
            summary = import_workbook(cursor, ws)
    except Exception as e:
        return { 'error': str(e) }, 400

    return { 'success': True, **summary }


def import_workbook(cursor, ws):
    '''Upsert projects and create coordinator assignments from worksheet ``ws``.

    Project rows are those whose first cell is a number (col A=#, B=Name,
    E=Categories, F=Project Coordinator). Returns a summary dict.'''
    cursor.execute("SELECT LOWER(email), id FROM master_naturalist")
    users = {email: uid for email, uid in cursor.fetchall()}

    # One timestamp for the whole upload: projects stamped with it are "in this
    # upload"; any project with an older/NULL last_imported is stale.
    cursor.execute("SELECT UTC_TIMESTAMP()")
    batch_ts = cursor.fetchone()[0]

    projects_upserted = 0
    assignments_created = 0
    unmatched = set()
    skipped_categories = set()
    for row in ws.iter_rows(values_only=True):
        if not isinstance(row[0], (int, float)):
            continue
        project_id = str(int(row[0]))
        name = re.sub(r'\s+', ' ', str(row[1] or '')).strip()[:255]
        categories = clean_categories(str(row[4] or ''), skipped_categories) if len(row) > 4 else []
        cursor.execute(
            """INSERT INTO projects (project_id, name, categories, last_imported)
                VALUES (%(pid)s, %(name)s, %(cat)s, %(ts)s)
                ON DUPLICATE KEY UPDATE
                    name = VALUES(name), categories = VALUES(categories),
                    last_imported = VALUES(last_imported)""",
            {'pid': project_id, 'name': name, 'cat': ','.join(categories), 'ts': batch_ts}
        )
        projects_upserted += 1

        # The project's coordinator(s) get assigned to each of its categories.
        coord_cell = str(row[5] or '') if len(row) > 5 else ''
        for email in EMAIL_RE.findall(coord_cell):
            email = email.lower()
            uid = users.get(email)
            if not uid:
                unmatched.add(email)
                continue
            for category in categories:
                assignments_created += cursor.execute(
                    """INSERT IGNORE INTO coordinator_assignments
                            (project_id, category, coordinator_id)
                        VALUES (%(pid)s, %(cat)s, %(uid)s)""",
                    {'pid': project_id, 'cat': category, 'uid': uid}
                )

    # Projects in the registry that this upload did NOT include (stale).
    cursor.execute(
        """SELECT project_id, name FROM projects
            WHERE last_imported IS NULL OR last_imported < %(ts)s
            ORDER BY project_id""",
        {'ts': batch_ts}
    )
    not_in_upload = [{'project_id': r[0], 'name': r[1]} for r in cursor.fetchall()]

    return {
        'projects_upserted': projects_upserted,
        'assignments_created': assignments_created,
        'unmatched_emails': sorted(unmatched),
        'skipped_categories': sorted(skipped_categories),
        'not_in_upload': not_in_upload,
    }