"""
migrate_quest_system.py
------------------------
Adds new columns required by the Quest System v2 (performance-based, domain-gated).

Tables modified:
  quests           — domain, metrics_required, cooldown_hours, weekly_limit,
                     is_manual, metrics_submitted, metrics_verified
  user_custom_quests — max_duration_minutes, constraint_level, performance_required,
                       risk_level, metrics_required, metrics_definition,
                       cooldown_hours, weekly_limit

Run ONCE on an existing database:
  D:/FLOW/.venv/Scripts/python.exe migrate_quest_system.py
"""

import sys, os
sys.path.insert(0, os.path.dirname(__file__))
os.environ.setdefault("SECRET_KEY", "migrationkeyxxx32chars_xxxxxxxxxxxxx")
os.environ.setdefault("ALGORITHM", "HS256")

import app.models  # noqa
from app.db.database import SessionLocal, engine
from sqlalchemy import text, inspect


def _existing_cols(inspector, table: str) -> set:
    return {c["name"] for c in inspector.get_columns(table)}


def add_column(db, inspector, table: str, col: str, ddl: str):
    if col not in _existing_cols(inspector, table):
        db.execute(text(f"ALTER TABLE {table} ADD COLUMN {ddl}"))
        db.commit()
        print(f"  OK: {table}.{col} added.")
    else:
        print(f"  --: {table}.{col} already exists, skipped.")


def main():
    db = SessionLocal()
    try:
        inspector = inspect(engine)

        print("=== Migrating: quests table ===")
        quest_cols = [
            ("domain",            "domain VARCHAR(32)"),
            ("metrics_required",  "metrics_required BOOLEAN NOT NULL DEFAULT 0"),
            ("cooldown_hours",    "cooldown_hours INTEGER NOT NULL DEFAULT 0"),
            ("weekly_limit",      "weekly_limit INTEGER"),
            ("is_manual",         "is_manual BOOLEAN NOT NULL DEFAULT 0"),
            ("metrics_submitted", "metrics_submitted JSON"),
            ("metrics_verified",  "metrics_verified BOOLEAN"),
        ]
        for col, ddl in quest_cols:
            add_column(db, inspector, "quests", col, ddl)

        print("\n=== Migrating: user_custom_quests table ===")
        ucq_cols = [
            ("max_duration_minutes",  "max_duration_minutes INTEGER"),
            ("constraint_level",      "constraint_level REAL NOT NULL DEFAULT 0.5"),
            ("performance_required",  "performance_required BOOLEAN NOT NULL DEFAULT 0"),
            ("risk_level",            "risk_level REAL NOT NULL DEFAULT 0.3"),
            ("metrics_required",      "metrics_required BOOLEAN NOT NULL DEFAULT 0"),
            ("metrics_definition",    "metrics_definition JSON"),
            ("cooldown_hours",        "cooldown_hours INTEGER NOT NULL DEFAULT 0"),
            ("weekly_limit",          "weekly_limit INTEGER"),
        ]
        for col, ddl in ucq_cols:
            add_column(db, inspector, "user_custom_quests", col, ddl)

        print("\nMigration complete.")
        print("Next: run migrate_quest_templates.py to reseed performance-based templates.")

    except Exception as exc:
        db.rollback()
        import traceback; traceback.print_exc()
        print(f"FAILED: {exc}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
