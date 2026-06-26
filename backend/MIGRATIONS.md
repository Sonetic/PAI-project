Database migrations (Flask-Migrate / Alembic)

1. Install dependencies

   python -m venv .venv
   source .venv/bin/activate
   pip install -r backend/requirements.txt

2. Initialize migrations (one-time)

   export FLASK_APP=backend.manage
   flask db init

3. Create an initial migration (after code/schema changes)

   flask db migrate -m "initial"

4. Apply migrations to the database

   flask db upgrade

