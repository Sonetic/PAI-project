from backend.api import app, db
from flask_migrate import Migrate

migrate = Migrate(app, db)

# Expose `app` for the Flask CLI. Usage example:
#   export FLASK_APP=backend.manage
#   flask db init
#   flask db migrate -m "initial"
#   flask db upgrade
