"""PenaltyTier — configurable failure-penalty table.

Penalties scale with phase and quest difficulty chosen.  Every combination
of (phase, difficulty_chosen) has a precise penalty row so there are no
magic numbers in service code.

Penalty sequence (late game):
  fail any    → punishment mode flag set on UserStats
  fail hard   → demotion + boost lock for N hours
"""

from sqlalchemy import Column, Integer, String, Float, Boolean, Text
from app.db.base import Base


class PenaltyTier(Base):
    __tablename__ = "penalty_tiers"

    id = Column(Integer, primary_key=True, index=True)

    # ── Scope ────────────────────────────────────────────────────────────────
    phase = Column(String(16), nullable=False, index=True)              # entry|growth|mastery
    difficulty_chosen = Column(String(16), nullable=False, index=True)  # easy|intermediate|hard

    # ── XP penalty (positive integer = loss) ─────────────────────────────────
    xp_penalty = Column(Integer, nullable=False, default=50)

    # ── HP damage ─────────────────────────────────────────────────────────────
    hp_damage = Column(Integer, nullable=False, default=5)

    # ── Streak penalty (days lost from streak) ────────────────────────────────
    streak_penalty = Column(Integer, nullable=False, default=0)

    # ── Coin penalty ──────────────────────────────────────────────────────────
    coin_penalty = Column(Integer, nullable=False, default=0)

    # ── Rank mechanics ────────────────────────────────────────────────────────
    # rank_block: progress toward next rank is frozen for N days
    rank_block_days = Column(Integer, nullable=False, default=0)
    # demotion_risk: probability 0.0–1.0 that a rank demotion is applied
    demotion_risk = Column(Float, nullable=False, default=0.0)

    # ── Boost lock (blocks XP multiplier items / streak bonuses) ─────────────
    boost_lock_hours = Column(Integer, nullable=False, default=0)

    # ── Punishment mode: sets UserStats.punishment_active = N days ───────────
    punishment_mode_days = Column(Integer, nullable=False, default=0)

    # ── Recovery quest trigger ────────────────────────────────────────────────
    recovery_quest_required = Column(Boolean, nullable=False, default=False)
    # How many intermediate quests must be completed to exit recovery
    recovery_quest_count = Column(Integer, nullable=False, default=3)
    # Hours the player has to complete the recovery quests before penalty escalates
    recovery_window_hours = Column(Integer, nullable=False, default=48)

    # ── Negative stat penalty (fraction of normal gain as loss) ───────────────
    # 0.5 = lose 50 % of a normal hard-quest stat gain
    stat_penalty_fraction = Column(Float, nullable=False, default=0.25)

    # ── Mindset penalty applied per failure ───────────────────────────────────
    mindset_penalty = Column(Float, nullable=False, default=10.0)

    # ── Misc ──────────────────────────────────────────────────────────────────
    description = Column(Text, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)

    def __repr__(self) -> str:
        return (
            f"<PenaltyTier phase={self.phase!r} "
            f"difficulty={self.difficulty_chosen!r} "
            f"xp=-{self.xp_penalty}>"
        )
