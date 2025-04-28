import sys
import os
from sqlalchemy import text

# Add parent dir to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app, db

app = create_app()

with app.app_context():
    with db.engine.connect() as connection:
        connection.execute(text("DROP TABLE IF EXISTS _alembic_tmp_post"))
        print("✅ Dropped temporary Alembic table.")
