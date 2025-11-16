# Hays County Master Naturalist Volunteer, Advanced Training, and Events App

## To build vue app

```sh
cd opportunities
```

```sh
npm install
```

```sh
npm run dev
```

Run the flask app:

## To run flask app locally
- Be sure you have MySQL installed and running.
- Create an `hcmn` database.
- Edit credentials in the `get_db` function as needed in flaskapp/flask_app/db.py
- Create virtual env if desired.

```sh
cd flaskapp
```

```sh
pip install -r requirements.txt
```

```sh
export DEV=1
```

```sh
flask --app flask_app init-db
```

```sh
flask --app flask_app run
```

## To run flask app in production

First, build the vue app:

```sh
npm run build
```

Add generated .js and .css filenames to flaskapp/flask_app/templates/opportunities/index.html

Be sure to set the following environment variables:
- SECRET_KEY
- DATABASE_URL
- DATABASE_NAME
- DATABASE_USER
- DATABASE_PASSWORD
