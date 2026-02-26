"""
clear_adaptive_sessions.py
--------------------------
Deletes all adaptive quest sessions so the frontend will regenerate
fresh sessions using the current quest templates on next /daily call.

Run: D:/FLOW/.venv/Scripts/python.exe clear_adaptive_sessions.py
"""

import sys, os
sys.path.insert(0, os.path.dirname(__file__))
os.environ.setdefault("SECRET_KEY", "migrationkeyxxx32chars_xxxxxxxxxxxxx")
os.environ.setdefault("ALGORITHM", "HS256")

import app.models  # noqa
from app.db.database import SessionLocal
from sqlalchemy import text

def main():
    db = SessionLocal()
    try:
        # Only delete unchosen sessions (no quest was locked in yet)
        deleted = db.execute(text(
            "DELETE FROM adaptive_quest_sessions WHERE chosen_tier IS NULL"
        )).rowcount
        db.commit()
        print(f"Cleared {deleted} stale adaptive quest session(s).")
        print("Next /adaptive/daily call will regenerate fresh sessions from current templates.")
    except Exception as exc:
        db.rollback()
        import traceback; traceback.print_exc()
        print(f"FAILED: {exc}")
        raise
    finally:
        db.close()

if __name__ == "__main__":
    main()
