"""Drop the legacy tasks table from the database."""
import sqlite3

conn = sqlite3.connect("flow.db")
cursor = conn.cursor()

# Check if tasks table exists
cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='tasks'")
if cursor.fetchone():
    cursor.execute("DROP TABLE tasks")
    conn.commit()
    print("Dropped 'tasks' table.")
else:
    print("No 'tasks' table found — already clean.")

conn.close()
