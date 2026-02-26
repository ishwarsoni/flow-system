"""DifficultyProfile — per-category, per-phase difficulty scaling configuration.

All multipliers and thresholds are stored here so the system can be tuned
without a redeploy. Loaded once at startup and cached.
"""

from sqlalchemy import Column, Integer, String, Float, Boolean, Text
from app.db.base import Base


class DifficultyProfile(Base):
    """Defines the base difficulty value and tier multipliers for each
    combination of (category, phase). One row = one configuration cell.

    Phases
    ------
    entry   → Level  1–10
    growth  → Level 11–30
    mastery → Level 31+

    Categories
    ----------
    study | gym | sleep | focus | social
    """

    __tablename__ = "difficulty_profiles"

    id = Column(Integer, primary_key=True, index=True)

    # --- Identity ---
    category = Column(String(32), nullable=False, index=True)   # study|gym|sleep|focus|social
    phase = Column(String(16), nullable=False, index=True)       # entry|growth|mastery

    # --- Phase level bounds (informational, enforcement is in progression_tiers) ---
    level_min = Column(Integer, nullable=False, default=1)
    level_max = Column(Integer, nullable=False, default=10)

    # --- Base difficulty unit (abstract numeric, converted to real duration/reps) ---
    base_value = Column(Float, nullable=False, default=10.0)

    # --- Four-tier multipliers (applied to base_value) ---
    easy_multiplier = Column(Float, nullable=False, default=0.8)
    intermediate_multiplier = Column(Float, nullable=False, default=1.0)
    hard_multiplier = Column(Float, nullable=False, default=1.3)
    extreme_multiplier = Column(Float, nullable=False, default=1.6)

    # --- XP seeds for each tier before rank/mindset bonuses ---
    easy_xp_base = Column(Integer, nullable=False, default=80)
    intermediate_xp_base = Column(Integer, nullable=False, default=120)
    hard_xp_base = Column(Integer, nullable=False, default=200)
    extreme_xp_base = Column(Integer, nullable=False, default=400)

    # --- Stat this category primarily trains ---
    primary_stat = Column(String(20), nullable=False, default="strength")

    # --- Misc ---
    description = Column(Text, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)

    def __repr__(self) -> str:
        return (
            f"<DifficultyProfile category={self.category!r} phase={self.phase!r} "
            f"base={self.base_value}>"
        )
