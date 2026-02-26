"""
Migration script: Add RPG columns to user_stats and create quests table.
Run this AFTER stopping the backend server:
  python migrate_rpg.py
"""
import sqlite3
import sys

DB_PATH = "flow.db"

def get_existing_columns(cursor, table):
    cursor.execute(f"PRAGMA table_info({table})")
    return {row[1] for row in cursor.fetchall()}

def migrate():
    print("🔄 FLOW RPG Migration Script")
    print(f"   Database: {DB_PATH}")
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # ─── 1. Add missing columns to user_stats ───
    existing = get_existing_columns(cursor, "user_stats")
    print(f"\n📋 user_stats has {len(existing)} columns: {sorted(existing)}")
    
    new_columns = {
        "rank":              ("VARCHAR(10)", "'E'"),
        "skill_points":      ("INTEGER", "0"),
        "hp_current":        ("INTEGER", "100"),
        "hp_max":            ("INTEGER", "100"),
        "mp_current":        ("INTEGER", "50"),
        "mp_max":            ("INTEGER", "50"),
        "strength":          ("FLOAT", "10.0"),
        "intelligence":      ("FLOAT", "10.0"),
        "vitality":          ("FLOAT", "10.0"),
        "charisma":          ("FLOAT", "10.0"),
        "mana":              ("FLOAT", "10.0"),
        "coins":             ("INTEGER", "0"),
        "reputation":        ("INTEGER", "0"),
        "current_title":     ("VARCHAR(100)", "'Novice'"),
        "fatigue":           ("FLOAT", "0.0"),
        "streak_days":       ("INTEGER", "0"),
        "longest_streak":    ("INTEGER", "0"),
        "last_active_at":    ("DATETIME", "NULL"),
        "punishment_active": ("INTEGER", "0"),
    }
    
    # Remove old stat columns that might exist with different names
    old_stats = {"focus", "discipline", "energy", "consistency"}
    
    added: int = 0
    for col, (col_type, default) in new_columns.items():
        if col not in existing:
            sql = f"ALTER TABLE user_stats ADD COLUMN {col} {col_type} DEFAULT {default}"
            print(f"   ✅ Adding: {col} ({col_type}, default={default})")
            cursor.execute(sql)
            added = added + 1  # type: ignore
        else:
            print(f"   ⏭️  Exists: {col}")
    
    print(f"\n   Added {added} columns to user_stats")
    
    # ─── 2. Migrate old stat names → new ones ───
    if "focus" in existing and "mana" in existing:
        print("\n🔄 Migrating old stat values to new names...")
        cursor.execute("UPDATE user_stats SET mana = focus WHERE mana = 10.0 AND focus != 10.0")
        print("   focus → mana")
    if "energy" in existing and "strength" in existing:
        cursor.execute("UPDATE user_stats SET strength = energy WHERE strength = 10.0 AND energy != 10.0")
        print("   energy → strength")
    if "discipline" in existing and "vitality" in existing:
        cursor.execute("UPDATE user_stats SET vitality = discipline WHERE vitality = 10.0 AND discipline != 10.0")
        print("   discipline → vitality")
    if "consistency" in existing and "charisma" in existing:
        cursor.execute("UPDATE user_stats SET charisma = consistency WHERE charisma = 10.0 AND consistency != 10.0")
        print("   consistency → charisma")
    
    # ─── 3. Create quests table ───
    print("\n📋 Creating quests table...")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS quests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL REFERENCES users(id),
            title VARCHAR(200) NOT NULL,
            description TEXT,
            quest_type VARCHAR(20) DEFAULT 'custom',
            difficulty VARCHAR(20) DEFAULT 'easy',
            primary_stat VARCHAR(20),
            base_xp_reward INTEGER DEFAULT 100,
            coin_reward INTEGER DEFAULT 10,
            stat_rewards JSON,
            item_rewards JSON,
            bonus_skill_points INTEGER DEFAULT 0,
            penalty_xp INTEGER DEFAULT 0,
            penalty_hp INTEGER DEFAULT 0,
            penalty_stat JSON,
            generates_penalty_quest BOOLEAN DEFAULT 0,
            mp_cost INTEGER DEFAULT 0,
            time_limit_minutes INTEGER,
            expires_at DATETIME,
            deadline DATETIME,
            status VARCHAR(20) DEFAULT 'pending',
            auto_generated BOOLEAN DEFAULT 0,
            completed_at DATETIME,
            failed_at DATETIME,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    print("   ✅ quests table ready")
    
    # ─── 4. Update xp_history if needed ───
    xp_cols = get_existing_columns(cursor, "xp_history")
    xp_new = {
        "coin_amount":    ("INTEGER", "0"),
        "quest_id":       ("INTEGER", "NULL"),
        "stat_deltas":    ("JSON", "NULL"),
        "level_at_time":  ("INTEGER", "NULL"),
        "rank_at_time":   ("VARCHAR(10)", "NULL"),
    }
    
    xp_added: int = 0
    for col, (col_type, default) in xp_new.items():
        if col not in xp_cols:
            sql = f"ALTER TABLE xp_history ADD COLUMN {col} {col_type} DEFAULT {default}"
            print(f"   ✅ xp_history: Adding {col}")
            cursor.execute(sql)
            xp_added = xp_added + 1  # type: ignore
    
    if xp_added:
        print(f"   Added {xp_added} columns to xp_history")
    
    conn.commit()
    conn.close()
    
    print("\n✅ Migration complete! Restart the backend server.")


if __name__ == "__main__":
    migrate()
