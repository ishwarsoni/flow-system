"""
migrate_domains.py
──────────────────
1. Rename old category values in quest_templates, difficulty_profiles,
   adaptive_quest_sessions, user_custom_quests
2. Seed the `domains` table with all 6 domains
3. Add "system" domain templates to quest_templates

Run: D:\FLOW\.venv\Scripts\python.exe migrate_domains.py
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from app.db.database import SessionLocal, engine
from app.db.base import Base
import app.models  # noqa: F401 — registers all models in metadata
from sqlalchemy import text

# ── Category → Domain rename map ──────────────────────────────────────────────
RENAMES = {
    "study":  "mind",
    "gym":    "body",
    "sleep":  "core",
    "focus":  "control",
    "social": "presence",
}

TABLES_WITH_CATEGORY = [
    "quest_templates",
    "difficulty_profiles",
    "adaptive_quest_sessions",
    "user_custom_quests",
]

# ── Domain seed data ───────────────────────────────────────────────────────────
DOMAIN_SEEDS = [
    {
        "code":        "mind",
        "name":        "MIND",
        "description": "Cognitive output, learning, and knowledge retention.",
        "stat_mapping": '{"primary": "intelligence"}',
        "color":       "#00d4ff",
        "icon":        "◈",
    },
    {
        "code":        "body",
        "name":        "BODY",
        "description": "Physical strength, endurance, and kinetic power.",
        "stat_mapping": '{"primary": "strength"}',
        "color":       "#ff2040",
        "icon":        "⚡",
    },
    {
        "code":        "core",
        "name":        "CORE",
        "description": "Recovery, sleep quality, and baseline vitality.",
        "stat_mapping": '{"primary": "vitality"}',
        "color":       "#00ff88",
        "icon":        "◉",
    },
    {
        "code":        "control",
        "name":        "CONTROL",
        "description": "Focus, impulse management, and deep work capacity.",
        "stat_mapping": '{"primary": "mana"}',
        "color":       "#7c3aed",
        "icon":        "◆",
    },
    {
        "code":        "presence",
        "name":        "PRESENCE",
        "description": "Social influence, communication, and leadership.",
        "stat_mapping": '{"primary": "charisma"}',
        "color":       "#ffd700",
        "icon":        "◇",
    },
    {
        "code":        "system",
        "name":        "SYSTEM",
        "description": "Strategic planning, environment design, and operational efficiency.",
        "stat_mapping": '{"primary": "intelligence", "secondary": "charisma"}',
        "color":       "#e2e8f0",
        "icon":        "⬡",
    },
]

# ── System domain quest templates (12 rows: 4 tiers × 3 phases) ───────────────
SYSTEM_TEMPLATES = [
    # entry phase
    {"phase": "entry", "tier": "easy",         "base_xp": 80,  "title_template": "Review and plan {value} {unit}", "description_template": "Audit your task list. Eliminate noise. Set priority.",               "unit_type": "items"},
    {"phase": "entry", "tier": "intermediate", "base_xp": 120, "title_template": "System audit — {value} {unit}",  "description_template": "Review finances, environment, or workflow. Fix one thing.",           "unit_type": "min"},
    {"phase": "entry", "tier": "hard",         "base_xp": 200, "title_template": "Strategic planning — {value} {unit}", "description_template": "Long-horizon thinking. Document the plan. Assign deadlines.",  "unit_type": "min"},
    {"phase": "entry", "tier": "extreme",      "base_xp": 350, "title_template": "Full system overhaul — {value} {unit} + written output", "description_template": "Total environment audit. Written strategy with metrics and deadlines.", "unit_type": "min"},
    # mid phase
    {"phase": "mid",   "tier": "easy",         "base_xp": 90,  "title_template": "Review and plan {value} {unit}", "description_template": "Audit your task list. Eliminate noise. Set priority.",               "unit_type": "items"},
    {"phase": "mid",   "tier": "intermediate", "base_xp": 140, "title_template": "System audit — {value} {unit}",  "description_template": "Review finances, environment, or workflow. Fix one thing.",           "unit_type": "min"},
    {"phase": "mid",   "tier": "hard",         "base_xp": 240, "title_template": "Strategic planning — {value} {unit}", "description_template": "Long-horizon thinking. Document the plan. Assign deadlines.",  "unit_type": "min"},
    {"phase": "mid",   "tier": "extreme",      "base_xp": 420, "title_template": "Full system overhaul — {value} {unit} + written output", "description_template": "Total environment audit. Written strategy with metrics and deadlines.", "unit_type": "min"},
    # elite phase
    {"phase": "elite", "tier": "easy",         "base_xp": 110, "title_template": "Review and plan {value} {unit}", "description_template": "Audit your task list. Eliminate noise. Set priority.",               "unit_type": "items"},
    {"phase": "elite", "tier": "intermediate", "base_xp": 170, "title_template": "System audit — {value} {unit}",  "description_template": "Review finances, environment, or workflow. Fix one thing.",           "unit_type": "min"},
    {"phase": "elite", "tier": "hard",         "base_xp": 290, "title_template": "Strategic planning — {value} {unit}", "description_template": "Long-horizon thinking. Document the plan. Assign deadlines.",  "unit_type": "min"},
    {"phase": "elite", "tier": "extreme",      "base_xp": 500, "title_template": "Full system overhaul — {value} {unit} + written output", "description_template": "Total environment audit. Written strategy with metrics and deadlines.", "unit_type": "min"},
]


def main():
    # Ensure all tables exist (creates any missing, including `domains`)
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        # ── 1. Rename categories in DB tables ─────────────────────────────────
        print("Step 1: renaming categories → domains")
        for table in TABLES_WITH_CATEGORY:
            for old, new in RENAMES.items():
                result = db.execute(
                    text(f"UPDATE {table} SET category = :new WHERE category = :old"),
                    {"new": new, "old": old},
                )
                if result.rowcount:
                    print(f"  {table}: '{old}' → '{new}' ({result.rowcount} rows)")
        db.commit()
        print("  ✓ Category rename complete")

        # ── 2. Seed domains table ──────────────────────────────────────────────
        print("\nStep 2: seeding domains table")
        existing = db.execute(text("SELECT code FROM domains")).fetchall()
        existing_codes = {r[0] for r in existing}

        for d in DOMAIN_SEEDS:
            if d["code"] in existing_codes:
                print(f"  skipped (exists): {d['code']}")
                continue
            db.execute(
                text(
                    "INSERT INTO domains (code, name, description, stat_mapping, color, icon) "
                    "VALUES (:code, :name, :description, :stat_mapping, :color, :icon)"
                ),
                d,
            )
            print(f"  inserted: {d['code']}")
        db.commit()
        print("  ✓ Domain seed complete")

        # ── 3. Seed system quest templates ─────────────────────────────────────
        print("\nStep 3: seeding system domain quest templates")
        for t in SYSTEM_TEMPLATES:
            # Check if already exists
            existing_t = db.execute(
                text(
                    "SELECT id FROM quest_templates "
                    "WHERE category = 'system' AND phase = :phase AND tier = :tier"
                ),
                {"phase": t["phase"], "tier": t["tier"]},
            ).fetchone()
            if existing_t:
                print(f"  skipped (exists): system/{t['phase']}/{t['tier']}")
                continue
            db.execute(
                text(
                    "INSERT INTO quest_templates "
                    "(category, phase, tier, title_template, description_template, unit_type, base_xp, is_active, selection_weight) "
                    "VALUES (:category, :phase, :tier, :title_template, :description_template, :unit_type, :base_xp, 1, 1.0)"
                ),
                {**t, "category": "system"},
            )
            print(f"  inserted: system/{t['phase']}/{t['tier']}")
        db.commit()
        print("  ✓ System templates seeded")

        print("\n✅ Migration complete.")

    except Exception as exc:
        db.rollback()
        print(f"\n❌ Migration failed: {exc}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
