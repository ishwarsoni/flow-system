import os
os.environ.setdefault("SECRET_KEY", "testkey32chars_xxxxxxxxxxxxxxxxxxxxxx")
os.environ.setdefault("ALGORITHM", "HS256")
from app.db.database import SessionLocal
from sqlalchemy import text
db = SessionLocal()
r = db.execute(text("DELETE FROM adaptive_quest_sessions"))
db.commit()
print(f"Cleared {r.rowcount} cached quest sessions")
db.close()
