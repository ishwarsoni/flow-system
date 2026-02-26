"""AdaptiveQuestSession — records each three-option trio presented to a player.

One row is created every time the engine generates a trio. The player's
choice is recorded when they accept an option. This log drives mindset
score calculations and comfort-zone detection.
"""

from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, ForeignKey, JSON
from datetime import datetime, UTC
from app.db.base import Base


class AdaptiveQuestSession(Base):
    """Tracks the lifecycle of a single generate → choose → complete cycle."""

    __tablename__ = "adaptive_quest_sessions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    # ── Category that was generated ───────────────────────────────────────────
    category = Column(String(32), nullable=False, index=True)
    phase = Column(String(16), nullable=False)

    # ── Computed panel data (snapshot at generation time) ─────────────────────
    # Stored so we can replay or audit even if templates change later.
    easy_snapshot = Column(JSON, nullable=False)           # {title, description, xp, value, unit}
    intermediate_snapshot = Column(JSON, nullable=False)
    hard_snapshot = Column(JSON, nullable=False)
    extreme_snapshot = Column(JSON, nullable=True)         # added in v2

    # ── Mindset context at generation time ────────────────────────────────────
    mindset_score_at_generation = Column(Float, nullable=True)
    force_challenge_was_active = Column(Boolean, nullable=False, default=False)

    # ── Player choice ─────────────────────────────────────────────────────────
    chosen_tier = Column(String(16), nullable=True)        # easy|intermediate|hard|extreme|None
    quest_id_created = Column(Integer, ForeignKey("quests.id"), nullable=True)

    # ── Outcome ───────────────────────────────────────────────────────────────
    outcome = Column(String(16), nullable=True)            # completed|failed|expired|abandoned

    # ── Timestamps ────────────────────────────────────────────────────────────
    generated_at = Column(DateTime, nullable=False, default=lambda: datetime.now(UTC), index=True)
    chosen_at = Column(DateTime, nullable=True)
    resolved_at = Column(DateTime, nullable=True)

    # ── Expires if player never chooses ───────────────────────────────────────
    expires_at = Column(DateTime, nullable=True)

    def __repr__(self) -> str:
        return (
            f"<AdaptiveQuestSession id={self.id} user={self.user_id} "
            f"category={self.category!r} chosen={self.chosen_tier!r}>"
        )
