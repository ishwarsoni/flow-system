"""Migration: Add template_id column to quests table.

Adds the FK linking every quest back to its source template.
Idempotent — safe to run multiple times.
"""

import sys, os
sys.path.insert(0, os.path.dirname(__file__))
os.environ.setdefault("SECRET_KEY", "migrationkeyxxx32chars_xxxxxxxxxxxxx")
os.environ.setdefault("ALGORITHM", "HS256")

from app.db.database import engine
from sqlalchemy import text


def migrate():
    with engine.connect() as conn:
        # Check if column already exists
        result = conn.execute(text("PRAGMA table_info(quests)")).fetchall()
        columns = [row[1] for row in result]

        if "template_id" not in columns:
            conn.execute(text(
                "ALTER TABLE quests ADD COLUMN template_id INTEGER "
                "REFERENCES quest_templates(id)"
            ))
            conn.execute(text(
                "CREATE INDEX IF NOT EXISTS ix_quests_template_id ON quests (template_id)"
            ))
            conn.commit()
            print("[OK] Added template_id column to quests table.")
        else:
            print("[SKIP] template_id column already exists.")


if __name__ == "__main__":
    migrate()
