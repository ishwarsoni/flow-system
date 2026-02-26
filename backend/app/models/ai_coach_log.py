"""AICoachLog — immutable log of every AI coaching call.

One row per coaching invocation. Used for:
- Auditing: what did the AI say, what did FLOW apply?
- Rate limiting: 1 call/day/user (check last_called_at)
- Debugging: raw vs validated output comparison
- Safety: track rejection rates and patterns

This table is APPEND-ONLY. Rows are never updated or deleted.
"""

from sqlalchemy import (
    Column, Integer, String, DateTime, Float, Boolean,
    ForeignKey, JSON, Text,
)
from datetime import datetime, UTC
from app.db.base import Base


class AICoachLog(Base):
    """Immutable log entry for a single AI coaching call."""
    __tablename__ = "ai_coach_logs"

    id             = Column(Integer, primary_key=True, index=True)
    player_id      = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    # ── Timing ─────────────────────────────────────────────────────────────
    called_at      = Column(DateTime, nullable=False, default=lambda: datetime.now(UTC))

    # ── AI output ──────────────────────────────────────────────────────────
    raw_output     = Column(JSON, nullable=True)      # Exact Groq response (for audit)
    validated_output = Column(JSON, nullable=True)     # After validator processing

    # ── Verdict ────────────────────────────────────────────────────────────
    was_rejected   = Column(Boolean, default=False)    # True = fallback was used
    rejection_reasons = Column(JSON, nullable=True)    # List of strings

    # ── What was applied ──────────────────────────────────────────────────
    mode_applied   = Column(String(32), nullable=True)
    xp_modifier_applied = Column(Float, default=0.0)
    quests_created = Column(JSON, nullable=True)       # List of quest IDs
    message_shown  = Column(Text, nullable=True)       # The message displayed to user

    # ── Cost tracking ──────────────────────────────────────────────────────
    api_success    = Column(Boolean, default=True)     # False if Groq call failed
    trigger_type   = Column(String(32), default="daily")  # daily | failure | manual

    def __repr__(self):
        return (
            f"<AICoachLog(id={self.id}, player={self.player_id}, "
            f"at={self.called_at}, rejected={self.was_rejected})>"
        )
