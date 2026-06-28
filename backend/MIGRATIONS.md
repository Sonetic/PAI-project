database migrations 

1. install dependencies

   python -m venv .venv
   source .venv/bin/activate
   pip install -r backend/requirements.txt

2. initialize migrations (one-time)

   export FLASK_APP=backend.manage
   flask db init

3. Create an initial migration (after code/schema changes)

   flask db migrate -m "initial"

4. Apply migrations to the database

   flask db upgrade

