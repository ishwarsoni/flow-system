"""VerificationLog — immutable record of every verification decision.

One log per session close. Never updated, never deleted.
Provides full audit trail for every reward/penalty granted.
"""

from sqlalchemy import (
    Column, Integer, String, DateTime, Float, Boolean,
    ForeignKey, Enum, JSON, Index, Text,
)
from datetime import datetime, UTC
import enum
from app.db.base import Base


class VerificationDecision(str, enum.Enum):
    PASS        = "pass"         # Full reward
    SOFT_FAIL   = "soft_fail"   # Partial reward, trust penalty
    HARD_FAIL   = "hard_fail"   # No reward, full XP penalty
    AUDIT       = "audit"       # Flagged for manual/deeper review


class VerificationLog(Base):
    """Immutable verification record. Written once, never mutated."""
    __tablename__ = "verification_logs"

    id          = Column(Integer, primary_key=True, index=True)
    session_id  = Column(Integer, ForeignKey("quest_sessions.id"), nullable=False, unique=True, index=True)
    player_id   = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    quest_id    = Column(Integer, ForeignKey("quests.id"), nullable=False, index=True)

    # ── Score breakdown ────────────────────────────────────────────────────
    time_score          = Column(Float, nullable=False)    # 0.0 – 1.0
    output_score        = Column(Float, nullable=False)
    consistency_score   = Column(Float, nullable=False)
    behavior_score      = Column(Float, nullable=False)
    verification_score  = Column(Float, nullable=False)    # Weighted final

    # ── Decision ───────────────────────────────────────────────────────────
    decision            = Column(Enum(VerificationDecision), nullable=False)
    failure_reason      = Column(Text, nullable=True)
    reward_multiplier   = Column(Float, default=1.0)       # 1.0 = full, 0.5 = partial, 0.0 = none
    xp_awarded          = Column(Integer, default=0)
    xp_penalty          = Column(Integer, default=0)

    # ── Trust impact ───────────────────────────────────────────────────────
    trust_delta         = Column(Float, default=0.0)       # Applied to player_trust.trust_score
    trust_score_after   = Column(Float, nullable=True)     # Snapshot of score after update

    # ── Checks applied ────────────────────────────────────────────────────
    spot_check_triggered    = Column(Boolean, default=False)
    output_required         = Column(Boolean, default=False)
    layers_applied          = Column(JSON, nullable=True)  # ["time_gate","session","output","consistency","behavior"]
    flags_raised            = Column(JSON, nullable=True)  # list of flag strings

    # ── Retrospective slot ────────────────────────────────────────────────
    retrospective_due_at    = Column(DateTime, nullable=True)
    retrospective_done      = Column(Boolean, default=False)
    retrospective_passed    = Column(Boolean, nullable=True)

    verified_at = Column(DateTime, nullable=False, default=lambda: datetime.now(UTC))

    __table_args__ = (
        Index("ix_vl_player_quest", "player_id", "quest_id"),
        Index("ix_vl_decision", "decision", "player_id"),
    )
