"""QuestSession — tracks an active quest attempt from start to completion.

Every quest start creates a session. Sessions are immutable once closed.
Rewards can ONLY be granted if a linked VerificationLog passes.
"""

from sqlalchemy import (
    Column, Integer, String, DateTime, Float, Boolean,
    ForeignKey, Enum, JSON, Index,
)
from datetime import datetime, UTC
import enum
from app.db.base import Base


class SessionStatus(str, enum.Enum):
    ACTIVE      = "active"        # Quest is running
    SUBMITTED   = "submitted"     # Player hit submit — awaiting verification
    VERIFIED    = "verified"      # Verification passed — reward granted
    SOFT_FAIL   = "soft_fail"     # Suspicious / partial credit
    HARD_FAIL   = "hard_fail"     # Proven fake — full penalty
    EXPIRED     = "expired"       # Time window passed before submit
    ABANDONED   = "abandoned"     # Player explicitly gave up


class QuestSession(Base):
    """One row per quest attempt. Immutable after status reaches a terminal state."""
    __tablename__ = "quest_sessions"

    id               = Column(Integer, primary_key=True, index=True)
    player_id        = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    quest_id         = Column(Integer, ForeignKey("quests.id"), nullable=False, index=True)

    # ── Time gate ──────────────────────────────────────────────────────────────
    started_at            = Column(DateTime, nullable=False, default=lambda: datetime.now(UTC))
    submitted_at          = Column(DateTime, nullable=True)
    closed_at             = Column(DateTime, nullable=True)   # Terminal state reached
    expected_duration_sec = Column(Integer, nullable=True)    # From quest.time_limit_minutes * 60
    window_start          = Column(DateTime, nullable=True)   # Valid-completion window start
    window_end            = Column(DateTime, nullable=True)   # Valid-completion window end

    # ── Active-time tracking (updated by heartbeat or on submit) ────────────────
    active_time_sec    = Column(Integer, default=0)    # Time with interaction detected
    idle_time_sec      = Column(Integer, default=0)    # Time with no interaction
    tab_hidden_sec     = Column(Integer, default=0)    # Tab was not visible
    app_bg_sec         = Column(Integer, default=0)    # App was backgrounded (mobile)

    # ── Device/env fingerprint ──────────────────────────────────────────────────
    device_id          = Column(String(128), nullable=True)
    user_agent         = Column(String(512), nullable=True)
    ip_hash            = Column(String(64), nullable=True)    # Hashed — not raw IP

    # ── Session status ──────────────────────────────────────────────────────────
    status             = Column(Enum(SessionStatus), default=SessionStatus.ACTIVE, index=True)
    requires_output    = Column(Boolean, default=False)   # Set at session-start by engine
    requires_spot_check= Column(Boolean, default=False)   # Random validation prompt triggered

    # ── Computed scores (filled by verification engine on submit) ──────────────
    time_score        = Column(Float, nullable=True)          # 0.0 – 1.0
    output_score      = Column(Float, nullable=True)
    consistency_score = Column(Float, nullable=True)
    behavior_score    = Column(Float, nullable=True)
    verification_score= Column(Float, nullable=True)          # Weighted final

    # ── Failure classification ──────────────────────────────────────────────────
    failure_reason     = Column(String(512), nullable=True)

    # ── Immutability guard ─────────────────────────────────────────────────────
    # Once closed_at is set, no further writes allowed (enforced in service).

    __table_args__ = (
        Index("ix_qs_player_quest", "player_id", "quest_id"),
        Index("ix_qs_status_player", "status", "player_id"),
    )

    def is_terminal(self) -> bool:
        return self.status in (
            SessionStatus.VERIFIED, SessionStatus.SOFT_FAIL,
            SessionStatus.HARD_FAIL, SessionStatus.EXPIRED,
            SessionStatus.ABANDONED,
        )
