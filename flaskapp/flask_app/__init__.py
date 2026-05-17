import os

from dotenv import load_dotenv
from flask import Flask
from flask_wtf.csrf import CSRFProtect, generate_csrf
from . import auth, db, opportunities, users


# PythonAnywhere's WSGI process doesn't source a shell; without this, the
# .env one level above the package would be silently ignored in prod.
load_dotenv(os.path.join(os.path.dirname(__file__), os.pardir, '.env'))

app = Flask(__name__, instance_relative_config=True)

# Set SECRET_KEY for CSRF Protection. Be sure to set this env variable in
# production.
app.config.from_mapping(
    SECRET_KEY=os.environ.get('SECRET_KEY') or '83645624FF4C6',
)

# ensure the instance folder exists
try:
    os.makedirs(app.instance_path)
except OSError:
    pass

db.init_app(app)


# add user authentication for project coordinators.
app.register_blueprint(auth.bp)

# add main page and opportunities API.
app.register_blueprint(opportunities.bp)
app.add_url_rule('/', endpoint='index')

# add user management for admins.
app.register_blueprint(users.bp)

CSRFProtect(app)

@app.after_request
def after_request_func(response):
    '''Make csrf token available for vue app.'''
    csrf_token = generate_csrf()
    response.set_cookie('CSRF-TOKEN', csrf_token)
    response.headers.add('CSRF-TOKEN', csrf_token)

    # Allow separate frontend port for vue development.
    if os.environ.get('DEV'):
        response.headers.add('Access-Control-Allow-Origin', 'http://localhost:5173')
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type,X-CSRFToken,Cookie,Set-Cookie')
        response.headers.add('Access-Control-Allow-Methods', 'GET,PUT,POST,DELETE')
        response.headers.add('Access-Control-Expose-Headers', 'CSRF-TOKEN')
        response.headers.add('Access-Control-Allow-Credentials', 'true')

    return response

# To run locally:
#   source .venv/bin/activate
#   flask --app VolunteerAT run
def create_app(test_config=None):

    return app
