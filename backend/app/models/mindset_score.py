"""MindsetScore — hidden per-user behavioral tracking table.

Tracks how the player makes decisions over time and derives a mindset score
that influences quest generation, force-challenge triggers, and recovery.

Score range: 0 – 1000
Tiers (informational labels only):
    0–199   Dormant      — avoidance patterns, comfort-seeking
    200–399 Awakening    — inconsistent, recovering
    400–599 Focused      — building discipline
    600–799 Driven       — reliable hard-quest engagement
    800–1000 Elite       — sustained mastery behaviour
"""

from sqlalchemy import Column, Integer, Float, Boolean, DateTime, ForeignKey
from datetime import datetime, UTC
from app.db.base import Base


class MindsetScore(Base):
    __tablename__ = "mindset_scores"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False, index=True)

    # ── Core score ────────────────────────────────────────────────────────────
    score = Column(Float, nullable=False, default=100.0)   # 0–1000

    # ── Choice tracking (lifetime counters) ───────────────────────────────────
    hard_choices = Column(Integer, nullable=False, default=0)
    intermediate_choices = Column(Integer, nullable=False, default=0)
    easy_choices = Column(Integer, nullable=False, default=0)

    # ── Completion tracking (lifetime) ────────────────────────────────────────
    hard_completions = Column(Integer, nullable=False, default=0)
    hard_failures = Column(Integer, nullable=False, default=0)
    hard_retry_successes = Column(Integer, nullable=False, default=0)   # failed hard → retried → succeeded

    intermediate_completions = Column(Integer, nullable=False, default=0)
    intermediate_failures = Column(Integer, nullable=False, default=0)

    easy_completions = Column(Integer, nullable=False, default=0)
    easy_failures = Column(Integer, nullable=False, default=0)

    # ── Streak / consistency ──────────────────────────────────────────────────
    # Days in a row any quest was completed (mirrors UserStats.streak_days but
    # mindset-specific so it can diverge when the penalty engine needs it)
    consistency_streak = Column(Integer, nullable=False, default=0)

    # Days in a row the player deliberately avoided choosing hard
    consecutive_non_hard_days = Column(Integer, nullable=False, default=0)
    last_hard_chosen_at = Column(DateTime, nullable=True)

    # ── Recovery mode ─────────────────────────────────────────────────────────
    recovery_mode = Column(Boolean, nullable=False, default=False)
    recovery_quests_required = Column(Integer, nullable=False, default=0)
    recovery_quests_completed = Column(Integer, nullable=False, default=0)
    recovery_deadline = Column(DateTime, nullable=True)   # NULL = not in recovery

    # ── Force-challenge flag ───────────────────────────────────────────────────
    force_challenge_active = Column(Boolean, nullable=False, default=False)
    force_challenge_until = Column(DateTime, nullable=True)

    # ── Timestamps ────────────────────────────────────────────────────────────
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(UTC))
    updated_at = Column(DateTime, nullable=False,
                        default=lambda: datetime.now(UTC),
                        onupdate=lambda: datetime.now(UTC))

    # ── Derived helpers (not stored) ─────────────────────────────────────────
    @property
    def completion_rate(self) -> float:
        total = self.hard_completions + self.hard_failures
        return (self.hard_completions / total) if total else 0.0

    @property
    def tier_label(self) -> str:
        if self.score < 200:
            return "dormant"
        elif self.score < 400:
            return "awakening"
        elif self.score < 600:
            return "focused"
        elif self.score < 800:
            return "driven"
        return "elite"

    def __repr__(self) -> str:
        return f"<MindsetScore user_id={self.user_id} score={self.score:.1f} tier={self.tier_label!r}>"
