"""QuestOutput — stores player-submitted proof for a quest session.

Outputs are required for serious quests (MIND, SYSTEM, CONTROL).
No output on a required quest → automatic hard fail.
All outputs are immutable once submitted.
"""

from sqlalchemy import (
    Column, Integer, String, DateTime, Float,
    ForeignKey, Enum, Text, JSON, Index,
)
from datetime import datetime, UTC
import enum
from app.db.base import Base


class OutputType(str, enum.Enum):
    SUMMARY         = "summary"         # Written summary of work done
    NOTES           = "notes"           # Raw notes / bullet points
    EXPLANATION     = "explanation"     # Explained a concept
    PLAN            = "plan"            # Step-by-step plan
    CHECKLIST       = "checklist"       # Completed checklist JSON
    SCREENSHOT      = "screenshot"      # Image proof (URL / storage key)
    REFLECTION      = "reflection"      # Mindset / emotional reflection
    SPOT_CHECK_RESP = "spot_check"      # Response to a random validation prompt


class OutputQuality(str, enum.Enum):
    NOT_EVALUATED = "not_evaluated"
    POOR          = "poor"
    ACCEPTABLE    = "acceptable"
    GOOD          = "good"
    EXCELLENT     = "excellent"


class QuestOutput(Base):
    """One row per submitted proof artifact. Multiple outputs per session allowed."""
    __tablename__ = "quest_outputs"

    id          = Column(Integer, primary_key=True, index=True)
    session_id  = Column(Integer, ForeignKey("quest_sessions.id"), nullable=False, index=True)
    player_id   = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    quest_id    = Column(Integer, ForeignKey("quests.id"), nullable=False, index=True)

    output_type = Column(Enum(OutputType), nullable=False)
    content     = Column(Text, nullable=True)       # Free-text content
    media_url   = Column(String(512), nullable=True)  # For screenshots / uploads
    extra_data  = Column(JSON, nullable=True)         # Additional structured data

    # ── Spot-check specific ──────────────────────────────────────────────────
    prompt_text     = Column(String(512), nullable=True)  # The question asked
    response_text   = Column(Text, nullable=True)         # Player answer

    # ── Evaluation ──────────────────────────────────────────────────────────
    quality             = Column(Enum(OutputQuality), default=OutputQuality.NOT_EVALUATED)
    quality_score       = Column(Float, nullable=True)    # 0.0 – 1.0
    evaluated_at        = Column(DateTime, nullable=True)
    evaluation_notes    = Column(String(512), nullable=True)

    # Word count & timing (signals)
    word_count          = Column(Integer, default=0)
    time_to_write_sec   = Column(Integer, nullable=True)  # How long player typed

    submitted_at    = Column(DateTime, nullable=False, default=lambda: datetime.now(UTC))

    __table_args__ = (
        Index("ix_qo_session", "session_id"),
        Index("ix_qo_player_quest", "player_id", "quest_id"),
    )
