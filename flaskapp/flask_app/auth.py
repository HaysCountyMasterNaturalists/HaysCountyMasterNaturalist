import functools
from itsdangerous.url_safe import URLSafeTimedSerializer
import os

import bcrypt
from flask import (
    Blueprint, flash, g, redirect, render_template, request, session, url_for
)

from flask_app.db import get_db

bp = Blueprint('auth', __name__, url_prefix='/auth')


@bp.route('/user')
def user():
    if g.user:
        return g.user
    else:
        return { 'id': None }


def get_user_by_email(email):
    '''Search database for user by email address.'''
    user = None
    with get_db() as cursor:
        cursor.execute(
            """SELECT id, password FROM master_naturalist WHERE email = %(email)s""",
            {'email': email}
        )

        user = cursor.fetchone()

    return user


def signin(user_id):
    session.clear()
    session['user_id'] = user_id
    return { 'success': True }


@bp.route('/signup', methods=['POST'])
def signup():
    email = request.form['email']
    password = request.form['password']

    # hash and salt password.
    hashed_password = bcrypt.hashpw(
        password.encode('utf-8'),
        bcrypt.gensalt()
    )
    error = None

    if not email:
        error = 'Email is required.'
    elif not password:
        error = 'Password is required.'

    if error is None:
        try:
            with get_db() as cursor:
                cursor.execute(
                    """INSERT INTO master_naturalist (email, password)
                        VALUES (%(email)s, %(hashed_password)s)""",
                    {'email': email, 'hashed_password': hashed_password}
                )
        except:
            error = f"Oops! Something went wrong. Please try again."
        else:
            user = get_user_by_email(email)
            return signin(user[0])
    return { 'error': error }


@bp.route('/login', methods=['POST'])
def login():
    email = request.form['email']
    password = request.form['password'].encode('utf-8')
    error = None
    user = get_user_by_email(email)
    if user is None:
        error = 'Incorrect email.'
    # check hashed and salted password.
    elif not bcrypt.checkpw(password, user[1]):
        error = 'Incorrect password.'

    if error is None:
        return signin(user[0])

    return { 'error': error }


@bp.before_app_request
def load_logged_in_user():
    user_id = session.get('user_id')

    if user_id is None:
        g.user = None
    else:
        with get_db() as cursor:
            cursor.execute(
                """SELECT id, email, admin, project_coordinator FROM master_naturalist WHERE id = %(user_id)s""",
                {'user_id': user_id}
            )
            user = cursor.fetchone()
            if not user:
                session.pop('user_id')
                g.user = None
            else:
                cursor.execute(
                    """SELECT project_id, category FROM coordinator_assignments
                        WHERE coordinator_id = %(uid)s""",
                    {'uid': user[0]}
                )
                assigned_combos = [f"{r[0]}::{r[1]}" for r in cursor.fetchall()]
                g.user = {
                    'id': user[0],
                    'email': user[1],
                    'admin': user[2],
                    'project_coordinator': user[3],
                    'assigned_combos': assigned_combos,
                }


@bp.route('/logout', methods=['POST'])
def logout():
    session.clear()
    return { 'success': True }


@bp.route('/reset-password/<token>/<int:id>', methods=['POST'])
def reset_password(token, id):
    new_password = request.form['password']
    error = None
    success = False
    email = None
    if g.user:
        error = 'Already logged in.'
    elif not new_password:
        error = 'Password is required.'

    with get_db() as cursor:
        cursor.execute(
            """SELECT email, password FROM master_naturalist WHERE id = %(id)s""",
            {'id': id}
        )
        email, previous_hashed_password = cursor.fetchone()


    serializer = URLSafeTimedSerializer(os.environ.get('SECRET_KEY'))
    try:
        token_user_email = serializer.loads(
            token,
            max_age=259200, # 3 days in seconds
            salt=previous_hashed_password,
        )
    except:
        error = f"Oops! Something went wrong. Please contact an admin."
    
    if error is None and token_user_email != email:
        error = f"Oops! Something went wrong. Please contact an admin."

    if error is None:
        # hash and salt new password.
        new_hashed_password = bcrypt.hashpw(
            new_password.encode('utf-8'),
            bcrypt.gensalt()
        )
        try:
            with get_db() as cursor:
                cursor.execute(
                    """UPDATE master_naturalist
                        SET
                            password = %(new_hashed_password)s
                        WHERE id = %(id)s""",
                    {
                        'id': id,
                        'new_hashed_password': new_hashed_password
                    }
                )
        except:
            error = f"Oops! Something went wrong. Please try another password."
        else:
            success = True
            return signin(id)

    return { 'success': success, 'error': error }


def admin_required(view):
    '''Requires user be an admin in order to access the
    decorated endpoint.'''
    @functools.wraps(view)
    def wrapped_view(**kwargs):
        if g.user is None:
            return {'error': 'login required'}, 400
        if not g.user['admin']:
            return {'error': 'access denied'}, 400

        return view(**kwargs)

    return wrapped_view


def editor_required(view):
    '''Requires user be an admin or project_coordinator in order to access the
    decorated endpoint.'''
    @functools.wraps(view)
    def wrapped_view(**kwargs):
        if g.user is None:
            return {'error': 'login required'}, 400
        if not g.user['project_coordinator'] and not g.user['admin']:
            return {'error': 'access denied'}, 400

        return view(**kwargs)

    return wrapped_view


@bp.route('/users/reset-password/<int:id>', methods=['GET'])
@admin_required
def generate_password_link(id):
    secret_key = None
    with get_db() as cursor:
        cursor.execute(
            """SELECT email, password FROM master_naturalist WHERE id = %(id)s""",
            {'id': id }
        )
        email, hashed_password = cursor.fetchone()

        serializer = URLSafeTimedSerializer(os.environ.get('SECRET_KEY'))

    secret_key = serializer.dumps(email, salt=hashed_password)

    return { 'secret_key': secret_key }
