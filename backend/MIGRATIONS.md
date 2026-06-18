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

Notes:
- The project previously used db.create_all(); that's removed. Use migrations to evolve the schema.
- DATABASE_URL env var is read in backend/api.py; ensure it points to your Postgres instance.
- To generate subsequent migrations after model changes: repeat `flask db migrate -m "msg"` then `flask db upgrade`.
