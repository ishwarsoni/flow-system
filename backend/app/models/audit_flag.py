"""AuditFlag — raised whenever suspicious behavior is detected.

Multiple flags can exist per session or per player.
Used to classify failure type and trigger audit mode.
Immutable once created.
"""

from sqlalchemy import (
    Column, Integer, String, DateTime, Boolean,
    ForeignKey, Enum, JSON, Index, Text,
)
from datetime import datetime, UTC
import enum
from app.db.base import Base


class FlagSeverity(str, enum.Enum):
    LOW      = "low"      # Informational — watch
    MEDIUM   = "medium"   # Suspicious — extra checks
    HIGH     = "high"     # Strong signal of manipulation
    CRITICAL = "critical" # Proven abuse — audit mode triggers


class FlagType(str, enum.Enum):
    INSTANT_COMPLETE    = "instant_complete"    # Completed in < 5% expected time
    LOW_ACTIVE_TIME     = "low_active_time"     # active_time < 60% expected
    IDLE_SPIKE          = "idle_spike"          # > 80% idle during session
    REPEATED_PATTERN    = "repeated_pattern"    # Same timing fingerprint across sessions
    BOT_BEHAVIOR        = "bot_behavior"        # Inhuman interaction density
    NO_OUTPUT           = "no_output"           # Output required but not submitted
    POOR_OUTPUT         = "poor_output"         # Output quality scored < 0.3
    SPOT_CHECK_FAIL     = "spot_check_fail"     # Failed random validation prompt
    RETROACTIVE_MISMATCH= "retroactive_mismatch"# Retrospective check failed
    MULTI_DEVICE        = "multi_device"        # Suspicious multi-device switch mid-session
    RAPID_RESUBMIT      = "rapid_resubmit"      # Re-submitted same quest within minutes
    SEQUENCE_GAMING     = "sequence_gaming"     # Completes quests in suspicious order/speed


class AuditFlag(Base):
    """Immutable flag record. One flag per detected pattern per session."""
    __tablename__ = "audit_flags"

    id          = Column(Integer, primary_key=True, index=True)
    player_id   = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    session_id  = Column(Integer, ForeignKey("quest_sessions.id"), nullable=True, index=True)
    quest_id    = Column(Integer, ForeignKey("quests.id"), nullable=True, index=True)

    flag_type   = Column(Enum(FlagType), nullable=False)
    severity    = Column(Enum(FlagSeverity), nullable=False, default=FlagSeverity.LOW)

    # ── Evidence ──────────────────────────────────────────────────────────
    description = Column(Text, nullable=True)
    evidence    = Column(JSON, nullable=True)   # Raw signal data attached to flag

    # ── Resolution ────────────────────────────────────────────────────────
    resolved         = Column(Boolean, default=False)
    resolution_notes = Column(Text, nullable=True)
    resolved_at      = Column(DateTime, nullable=True)

    raised_at   = Column(DateTime, nullable=False, default=lambda: datetime.now(UTC))

    __table_args__ = (
        Index("ix_af_player_severity", "player_id", "severity"),
        Index("ix_af_session", "session_id"),
    )
