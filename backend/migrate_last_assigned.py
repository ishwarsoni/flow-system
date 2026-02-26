"""Migration: Add last_assigned_at column to quests table.

RULE 3 support — tracks when a template was last assigned to prevent
reassignment within 48 hours.

Run: python migrate_last_assigned.py
"""

import sqlite3
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))
from app.config import get_settings

settings = get_settings()
db_url = settings.DATABASE_URL

if "sqlite" not in db_url:
    print("Non-SQLite DB — use Alembic or manual migration.")
    sys.exit(1)

db_path = db_url.split("///")[-1]
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Check if quests table exists
cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='quests'")
if not cursor.fetchone():
    print("quests table not found — nothing to migrate.")
    conn.close()
    sys.exit(0)

# Check existing columns
cursor.execute("PRAGMA table_info(quests)")
existing_cols = {row[1] for row in cursor.fetchall()}

added = False
if "last_assigned_at" not in existing_cols:
    cursor.execute("ALTER TABLE quests ADD COLUMN last_assigned_at DATETIME DEFAULT NULL")
    print("✅ Added quests.last_assigned_at")
    added = True

    # Backfill: set last_assigned_at = created_at for existing quests with template_id
    cursor.execute("""
        UPDATE quests
        SET last_assigned_at = created_at
        WHERE template_id IS NOT NULL AND last_assigned_at IS NULL
    """)
    count = cursor.rowcount
    print(f"✅ Backfilled last_assigned_at for {count} existing template-based quests")
else:
    print("quests.last_assigned_at already exists — no migration needed.")

conn.commit()
conn.close()

if added:
    print("🎮 Migration complete: last_assigned_at column added to quests table.")
else:
    print("📋 Schema is up to date.")
