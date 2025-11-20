from flask import Blueprint, request

from flask_app.auth import admin_required
from flask_app.db import get_db


bp = Blueprint('users', __name__)

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