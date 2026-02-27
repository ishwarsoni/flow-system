"""Migration: add is_admin column to users table.

Run: python migrate_admin_role.py
"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
os.environ.setdefault("SECRET_KEY", "migration_placeholder_key_32chars!")
os.environ.setdefault("DATABASE_URL", "sqlite:///./flow.db")
os.environ.setdefault("DEBUG", "True")

from sqlalchemy import text, inspect
from app.db.database import engine

def migrate():
    inspector = inspect(engine)
    columns = [c["name"] for c in inspector.get_columns("users")]

    with engine.begin() as conn:
        if "is_admin" not in columns:
            conn.execute(text("ALTER TABLE users ADD COLUMN is_admin BOOLEAN NOT NULL DEFAULT 0"))
            print("[OK] Added is_admin column to users table (default=False)")
        else:
            print("[SKIP] is_admin column already exists")

    print("Done. To promote a user to admin:")
    print("  UPDATE users SET is_admin = 1 WHERE email = 'your@email.com';")

if __name__ == "__main__":
    migrate()
