"""Migration: Add hunter_name column to users table."""
import sqlite3

DB_PATH = "flow.db"

def migrate():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    
    # Check if column already exists
    cur.execute("PRAGMA table_info(users)")
    cols = [r[1] for r in cur.fetchall()]
    print(f"Current columns: {cols}")
    
    if "hunter_name" in cols:
        print("hunter_name column already exists, skipping.")
    else:
        cur.execute("ALTER TABLE users ADD COLUMN hunter_name VARCHAR(20) DEFAULT 'Hunter'")
        cur.execute("UPDATE users SET hunter_name = 'Hunter' WHERE hunter_name IS NULL")
        conn.commit()
        print("Added hunter_name column and set defaults.")
    
    # Also check if starting_difficulty column exists
    if "starting_difficulty" not in cols:
        cur.execute("ALTER TABLE users ADD COLUMN starting_difficulty VARCHAR(20) DEFAULT 'normal'")
        conn.commit()
        print("Added starting_difficulty column.")
    
    # Verify
    cur.execute("PRAGMA table_info(users)")
    cols = [r[1] for r in cur.fetchall()]
    print(f"Final columns: {cols}")
    
    conn.close()

if __name__ == "__main__":
    migrate()
