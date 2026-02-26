"""Migration: Create ai_coach_logs table.

Run once to add the AI Coach logging table.
Idempotent — safe to run multiple times.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from app.db.database import engine
from app.models.ai_coach_log import AICoachLog
from app.db.base import Base


def migrate():
    """Create the ai_coach_logs table if it doesn't exist."""
    # Import the model so SQLAlchemy knows about it
    AICoachLog.__table__.create(bind=engine, checkfirst=True)
    print("[OK] ai_coach_logs table ready.")


if __name__ == "__main__":
    migrate()
