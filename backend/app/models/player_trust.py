"""PlayerTrust — per-player trust score maintained by the verification engine.

One row per player. Updated after every session closes.
Score drives adaptive strictness: how many checks to apply.
All history is logged (immutable), but the rolling score is mutable.
"""

from sqlalchemy import (
    Column, Integer, String, DateTime, Float, Boolean,
    ForeignKey, Enum, JSON, Index, Text,
)
from datetime import datetime, UTC
import enum
from app.db.base import Base


class TrustTier(str, enum.Enum):
    LOW    = "low"    # 0–39   — mandatory output + random checks
    NORMAL = "normal" # 40–69  — standard verification
    HIGH   = "high"   # 70–100 — light checks


class PlayerTrust(Base):
    """Rolling trust profile for a player. One row per player."""
    __tablename__ = "player_trust"

    id          = Column(Integer, primary_key=True, index=True)
    player_id   = Column(Integer, ForeignKey("users.id"), nullable=False, unique=True, index=True)

    # ── Rolling score ───────────────────────────────────────────────────────
    trust_score         = Column(Float, default=50.0)   # 0.0 – 100.0
    trust_tier          = Column(Enum(TrustTier), default=TrustTier.NORMAL)

    # ── Aggregate signals ────────────────────────────────────────────────────
    total_sessions          = Column(Integer, default=0)
    verified_sessions       = Column(Integer, default=0)
    soft_fail_count         = Column(Integer, default=0)
    hard_fail_count         = Column(Integer, default=0)
    spot_check_pass_count   = Column(Integer, default=0)
    spot_check_fail_count   = Column(Integer, default=0)
    output_quality_avg      = Column(Float, default=0.5)    # 0.0 – 1.0
    flag_count              = Column(Integer, default=0)
    audit_mode              = Column(Boolean, default=False) # Severe abuse → full audit

    # ── Weekly recalc ───────────────────────────────────────────────────────
    last_recalculated_at    = Column(DateTime, nullable=True)
    last_session_at         = Column(DateTime, nullable=True)

    # ── Streaks / patterns ───────────────────────────────────────────────────
    consecutive_verified    = Column(Integer, default=0)
    consecutive_fails       = Column(Integer, default=0)
    instant_complete_count  = Column(Integer, default=0)  # Completions < 5% expected time

    created_at  = Column(DateTime, default=lambda: datetime.now(UTC))
    updated_at  = Column(DateTime, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))

    def get_tier(self) -> TrustTier:
        if self.trust_score < 40:
            return TrustTier.LOW
        elif self.trust_score < 70:
            return TrustTier.NORMAL
        else:
            return TrustTier.HIGH
