"""ProgressionTier — phase-level configuration table.

Defines the three phases of the training arc and their mechanical parameters.
Stored in DB so they can be tuned via the admin panel without code changes.

Phase   Levels   Philosophy
------  -------  ----------------------------------------------------------
entry   1–10     Difficult-for-beginners. No soft options. Build the habit.
growth  11–30    Former easy = intermediate. Hard becomes demanding.
mastery 31+      Disciplined baseline. No comfortable ceiling. Elite standard.
"""

from sqlalchemy import Column, Integer, String, Float, Boolean, Text
from app.db.base import Base


class ProgressionTier(Base):
    __tablename__ = "progression_tiers"

    id = Column(Integer, primary_key=True, index=True)

    # ── Identity ──────────────────────────────────────────────────────────────
    phase = Column(String(16), nullable=False, unique=True, index=True)  # entry|growth|mastery

    # ── Level bounds ──────────────────────────────────────────────────────────
    level_min = Column(Integer, nullable=False, default=1)
    level_max = Column(Integer, nullable=False, default=10)

    # ── Base difficulty scalar (abstract, not directly XP) ────────────────────
    # base_difficulty is multiplied by per-category profile values to produce
    # the raw numeric difficulty before tier-multipliers are applied.
    base_difficulty = Column(Float, nullable=False, default=1.0)

    # ── Tier multipliers for this phase ───────────────────────────────────────
    easy_multiplier = Column(Float, nullable=False, default=0.8)
    intermediate_multiplier = Column(Float, nullable=False, default=1.0)
    hard_multiplier = Column(Float, nullable=False, default=1.3)

    # ── XP scaling applied on top of template base_xp ────────────────────────
    xp_scale = Column(Float, nullable=False, default=1.0)

    # ── Force-challenge trigger: days of avoiding hard before lockout ─────────
    force_challenge_trigger_days = Column(Integer, nullable=False, default=5)

    # ── Soft-option minimum (minimum tier the player may freely choose) ───────
    # "entry" allows all three; "intermediate" disables easy in mastery mode.
    minimum_choosable_tier = Column(String(16), nullable=False, default="easy")

    # ── Misc ──────────────────────────────────────────────────────────────────
    description = Column(Text, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)

    def __repr__(self) -> str:
        return (
            f"<ProgressionTier phase={self.phase!r} "
            f"levels={self.level_min}–{self.level_max} "
            f"difficulty={self.base_difficulty}>"
        )
