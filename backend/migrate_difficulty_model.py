"""
migrate_difficulty_model.py
────────────────────────────
Adds the 4-axis structured difficulty columns to quest_templates and
the extreme tier columns to difficulty_profiles.

This migration is ADDITIVE — existing rows are not deleted.
New columns get sensible defaults derived from the existing tier value.

Tier → defaults
───────────────
    easy         : constraint_level=1, performance_required=0, risk_level=1, cooldown_hours=0
    intermediate : constraint_level=2, performance_required=0, risk_level=2, cooldown_hours=0
    hard         : constraint_level=3, performance_required=1, risk_level=3, cooldown_hours=0
    extreme      : constraint_level=4, performance_required=1, risk_level=4, cooldown_hours=48

Duration caps enforced on max_duration_minutes where unit_type is 'minutes' or 'hours':
    easy         : 60 min
    intermediate : 120 min
    hard         : 180 min
    extreme      : 300 min

Run: D:\\FLOW\\.venv\\Scripts\\python.exe migrate_difficulty_model.py
"""

import sys, os
sys.path.insert(0, os.path.dirname(__file__))
os.environ.setdefault("SECRET_KEY", "migrationkeyxxx32chars_xxxxxxxxxxxxx")
os.environ.setdefault("ALGORITHM", "HS256")

import app.models  # noqa — registers all models
from app.db.database import SessionLocal, engine
from app.db.base import Base
from sqlalchemy import text

# ── Tier → difficulty axis defaults ───────────────────────────────────────────

TIER_DEFAULTS = {
    "easy":         {"constraint_level": 1, "performance_required": 0, "risk_level": 1, "cooldown_hours": 0},
    "intermediate": {"constraint_level": 2, "performance_required": 0, "risk_level": 2, "cooldown_hours": 0},
    "hard":         {"constraint_level": 3, "performance_required": 1, "risk_level": 3, "cooldown_hours": 0},
    "extreme":      {"constraint_level": 4, "performance_required": 1, "risk_level": 4, "cooldown_hours": 48},
}

DURATION_CAPS = {
    "easy":         60,
    "intermediate": 120,
    "hard":         180,
    "extreme":      300,
}


def column_exists(db, table: str, column: str) -> bool:
    """Check if a column exists by querying the table info pragma directly."""
    result = db.execute(text(f"PRAGMA table_info({table})"))
    cols = [row[1] for row in result.fetchall()]
    return column in cols


def main() -> None:
    db = SessionLocal()

    try:
        print("=== FLOW Difficulty Model Migration ===\n")

        # ── 1. Add new columns to quest_templates ─────────────────────────────
        qt_new_cols = [
            ("max_duration_minutes", "INTEGER"),
            ("constraint_level",     "INTEGER NOT NULL DEFAULT 1"),
            ("performance_required", "BOOLEAN NOT NULL DEFAULT 0"),
            ("risk_level",           "INTEGER NOT NULL DEFAULT 1"),
            ("cooldown_hours",       "INTEGER NOT NULL DEFAULT 0"),
        ]

        print("quest_templates — adding columns:")
        for col_name, col_def in qt_new_cols:
            if not column_exists(db, "quest_templates", col_name):
                db.execute(text(f"ALTER TABLE quest_templates ADD COLUMN {col_name} {col_def}"))
                print(f"  + {col_name}")
            else:
                print(f"  ~ {col_name} already exists, skipping")
        db.commit()

        # ── 2. Populate difficulty axes per tier ──────────────────────────────
        print("\nquest_templates — setting difficulty axis defaults per tier:")
        for tier, defaults in TIER_DEFAULTS.items():
            result = db.execute(
                text(
                    "UPDATE quest_templates SET "
                    "  constraint_level     = :constraint_level, "
                    "  performance_required = :performance_required, "
                    "  risk_level           = :risk_level, "
                    "  cooldown_hours       = :cooldown_hours "
                    "WHERE tier = :tier"
                ),
                {**defaults, "tier": tier},
            )
            print(f"  {tier:<14} => {result.rowcount} rows updated")
        db.commit()

        # ── 3. Set max_duration_minutes per tier for timed templates ──────────
        print("\nquest_templates — setting max_duration_minutes caps:")
        for tier, cap in DURATION_CAPS.items():
            result = db.execute(
                text(
                    "UPDATE quest_templates "
                    "SET max_duration_minutes = :cap "
                    "WHERE tier = :tier AND unit_type IN ('minutes', 'min', 'hours')"
                ),
                {"cap": cap, "tier": tier},
            )
            print(f"  {tier:<14} cap={cap} min => {result.rowcount} rows updated")

        # Tasks/reps-based templates get a NULL max_duration (not time-bound)
        print("  task-based templates => max_duration_minutes stays NULL (not time-capped)")
        db.commit()

        # ── 4. Add extreme tier columns to difficulty_profiles ────────────────
        dp_new_cols = [
            ("extreme_multiplier", "REAL NOT NULL DEFAULT 1.6"),
            ("extreme_xp_base",    "INTEGER NOT NULL DEFAULT 400"),
        ]

        print("\ndifficulty_profiles — adding extreme tier columns:")
        for col_name, col_def in dp_new_cols:
            if not column_exists(db, "difficulty_profiles", col_name):
                db.execute(text(f"ALTER TABLE difficulty_profiles ADD COLUMN {col_name} {col_def}"))
                print(f"  + {col_name}")
            else:
                print(f"  ~ {col_name} already exists, skipping")
        db.commit()

        # ── 5. Scale extreme_xp_base from hard_xp_base ───────────────────────
        db.execute(
            text(
                "UPDATE difficulty_profiles "
                "SET extreme_xp_base = CAST(hard_xp_base * 2.0 AS INTEGER) "
                "WHERE extreme_xp_base = 400"   # only update if still at default
            )
        )
        db.commit()
        print("  extreme_xp_base set to hard_xp_base × 2 for all profiles")

        # ── 6. Ensure Difficulty enum has INTERMEDIATE in quests table ────────
        # SQLite does not enforce enum; other DBs may need a migration.
        # We just confirm the column exists and can store the string.
        print("\nquest.difficulty — no structural change needed (enum is stored as string)")

        print("\n=== Migration complete ===")

    except Exception as exc:
        db.rollback()
        import traceback; traceback.print_exc()
        print(f"\nFAILED: {exc}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
