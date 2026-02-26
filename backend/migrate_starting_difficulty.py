"""
migrate_starting_difficulty.py
--------------------------------
1. Adds `starting_difficulty` column to the `users` table (VARCHAR 20, default 'normal').
2. Fixes DifficultyProfile base_value for `mind` category to 1.0 (hours unit).

Run ONCE on an existing database:
  D:/FLOW/.venv/Scripts/python.exe migrate_starting_difficulty.py
"""

import sys, os
sys.path.insert(0, os.path.dirname(__file__))
os.environ.setdefault("SECRET_KEY", "migrationkeyxxx32chars_xxxxxxxxxxxxx")
os.environ.setdefault("ALGORITHM", "HS256")

import app.models  # noqa
from app.db.database import SessionLocal, engine
from sqlalchemy import text, inspect


def main():
    db = SessionLocal()
    try:
        # ── 1. Add starting_difficulty column if it doesn't exist ─────────────
        inspector = inspect(engine)
        existing_cols = [c["name"] for c in inspector.get_columns("users")]

        if "starting_difficulty" not in existing_cols:
            db.execute(text(
                "ALTER TABLE users ADD COLUMN starting_difficulty VARCHAR(20) NOT NULL DEFAULT 'normal'"
            ))
            db.commit()
            print("OK: Added 'starting_difficulty' column to users table.")
        else:
            print("  'starting_difficulty' column already exists -- skipped.")

        # -- 2. Fix mind DifficultyProfile base_value (hours, not minutes) ----
        updated = db.execute(
            text("UPDATE difficulty_profiles SET base_value = 1.0 WHERE category = 'mind'")
        ).rowcount
        db.commit()
        print(f"OK: Updated {updated} mind difficulty_profiles -> base_value=1.0 hours")

        print("\nMigration complete. Now run migrate_quest_templates.py to reseed templates.")

    except Exception as exc:
        db.rollback()
        import traceback; traceback.print_exc()
        print(f"FAILED: {exc}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
