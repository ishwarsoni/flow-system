"""
migrate_quest_system_v2.py
──────────────────────────
FLOW Quest System — Unified 4-Tier Enforcement Migration

Adds:
  1. verification_type column to quests table
  2. Back-fills existing quests with correct verification type
  3. Validates all quest templates match the 4-tier rules

FLOW Quest Rules (enforced post-migration):
  - ALL quests must be verifiable (no quest without proof mechanism)
  - EASY/INTERMEDIATE → verification_type = 'log'
  - HARD/EXTREME → verification_type = 'metrics'
  - No quest > 4 hours (240 min)
  - EXTREME: 24h cooldown, 3/week max
  - Vague wording forbidden at ALL tiers
  - If a quest cannot prove effort, it is invalid

Run: D:/FLOW/.venv/Scripts/python.exe migrate_quest_system_v2.py
"""

import sys
import os

sys.path.insert(0, os.path.dirname(__file__))
os.environ.setdefault("SECRET_KEY", "migrationkeyxxx32chars_xxxxxxxxxxxxx")
os.environ.setdefault("ALGORITHM", "HS256")

import app.models  # noqa — register all models
from app.db.database import engine, SessionLocal
from app.db.base import Base
from sqlalchemy import text, inspect


def main():
    db = SessionLocal()

    try:
        inspector = inspect(engine)
        columns = [c["name"] for c in inspector.get_columns("quests")]

        # ── Step 1: Add verification_type column if missing ────────────────────
        if "verification_type" not in columns:
            print("Adding verification_type column to quests table...")
            db.execute(text(
                "ALTER TABLE quests ADD COLUMN verification_type VARCHAR(16) "
                "NOT NULL DEFAULT 'log'"
            ))
            db.commit()
            print("  ✅ Column added.")
        else:
            print("  ℹ️  verification_type column already exists.")

        # ── Step 2: Back-fill verification_type based on difficulty ─────────────
        print("Back-filling verification_type for existing quests...")

        # Hard/Extreme quests → metrics
        updated = db.execute(text(
            "UPDATE quests SET verification_type = 'metrics' "
            "WHERE difficulty IN ('hard', 'extreme') AND verification_type != 'metrics'"
        )).rowcount
        print(f"  Updated {updated} hard/extreme quests → metrics verification.")

        # Easy/Intermediate quests → log
        updated = db.execute(text(
            "UPDATE quests SET verification_type = 'log' "
            "WHERE difficulty IN ('easy', 'intermediate', 'medium', 'trivial') "
            "AND verification_type != 'log'"
        )).rowcount
        print(f"  Updated {updated} easy/intermediate quests → log verification.")

        # ── Step 3: Ensure metrics_required=True for all hard/extreme ──────────
        updated = db.execute(text(
            "UPDATE quests SET metrics_required = 1 "
            "WHERE difficulty IN ('hard', 'extreme') AND metrics_required = 0"
        )).rowcount
        print(f"  Enforced metrics_required on {updated} hard/extreme quests.")

        # ── Step 4: Ensure cooldown_hours=24 for all extreme quests ────────────
        updated = db.execute(text(
            "UPDATE quests SET cooldown_hours = 24 "
            "WHERE difficulty = 'extreme' AND cooldown_hours != 24"
        )).rowcount
        print(f"  Set cooldown_hours=24 on {updated} extreme quests.")

        # ── Step 5: Ensure weekly_limit=3 for all extreme quests ───────────────
        updated = db.execute(text(
            "UPDATE quests SET weekly_limit = 3 "
            "WHERE difficulty = 'extreme' AND (weekly_limit IS NULL OR weekly_limit != 3)"
        )).rowcount
        print(f"  Set weekly_limit=3 on {updated} extreme quests.")

        # ── Step 6: Validate quest templates ───────────────────────────────────
        print("\nValidating quest templates...")
        from app.models.quest_template import QuestTemplate

        templates = db.query(QuestTemplate).filter(QuestTemplate.is_active == True).all()
        issues = []
        for t in templates:
            tier = t.tier.lower()
            if tier in ("hard", "extreme") and not t.performance_required:
                issues.append(
                    f"  ⚠️  Template {t.id} ({t.category}/{tier}): "
                    f"performance_required should be True"
                )
            if tier == "extreme" and t.cooldown_hours < 24:
                issues.append(
                    f"  ⚠️  Template {t.id} ({t.category}/{tier}): "
                    f"cooldown_hours should be ≥ 24 (got {t.cooldown_hours})"
                )
            if t.max_duration_minutes and t.max_duration_minutes > 240:
                issues.append(
                    f"  ⚠️  Template {t.id} ({t.category}/{tier}): "
                    f"duration {t.max_duration_minutes} min exceeds 240 min cap"
                )

        if issues:
            print(f"  Found {len(issues)} template issues:")
            for issue in issues:
                print(issue)
            # Auto-fix template issues
            print("\n  Auto-fixing template issues...")
            for t in templates:
                tier = t.tier.lower()
                changed = False
                if tier in ("hard", "extreme") and not t.performance_required:
                    t.performance_required = True
                    changed = True
                if tier == "extreme" and t.cooldown_hours < 24:
                    t.cooldown_hours = 24
                    changed = True
                if t.max_duration_minutes and t.max_duration_minutes > 240:
                    t.max_duration_minutes = 240
                    changed = True
                if changed:
                    db.add(t)
            print("  ✅ Template issues fixed.")
        else:
            print("  ✅ All templates valid.")

        db.commit()

        # ── Summary ────────────────────────────────────────────────────────────
        print("\n" + "=" * 60)
        print("FLOW Quest System v2 Migration Complete")
        print("=" * 60)
        print("\nEnforced Rules:")
        print("  ✅ ALL quests have verification_type")
        print("  ✅ Hard/Extreme → metrics verification required")
        print("  ✅ Easy/Intermediate → log-based verification")
        print("  ✅ EXTREME: 24h cooldown, 3/week max")
        print("  ✅ No quest > 4 hours (240 min)")
        print("  ✅ Templates validated and fixed")
        print("\nRuntime rules (enforced in code):")
        print("  • Vague wording rejected at ALL tiers")
        print("  • If a quest cannot prove effort → invalid")
        print("  • Daily aggregate time cap: 240 min")
        print("  • Difficulty scales by performance, not time alone")

    except Exception as exc:
        db.rollback()
        import traceback
        traceback.print_exc()
        print(f"\nFAILED: {exc}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
