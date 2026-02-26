"""QuestTemplate — library of real-life action descriptions.

Each template is tied to a category, a difficulty tier, and a phase.
The generation engine picks the best matching template and fills in the
computed values (duration, reps, etc.) via simple string interpolation.

Template variables (use {var} notation):
  {value}    — the computed numeric value (duration in minutes, rep count, etc.)
  {unit}     — the unit string ("min", "reps", "hours", …)
  {stat}     — the primary stat being trained
"""

from sqlalchemy import Column, Integer, String, Float, Boolean, Text, JSON
from app.db.base import Base


class QuestTemplate(Base):
    __tablename__ = "quest_templates"

    id = Column(Integer, primary_key=True, index=True)

    # ── Scope ────────────────────────────────────────────────────────────────
    category = Column(String(32), nullable=False, index=True)  # study|gym|sleep|focus|social
    tier = Column(String(16), nullable=False, index=True)       # easy|intermediate|hard
    phase = Column(String(16), nullable=False, index=True)      # entry|growth|mastery|any

    # ── Template text ────────────────────────────────────────────────────────
    title_template = Column(String(300), nullable=False)
    description_template = Column(Text, nullable=True)

    # ── Unit / value config ───────────────────────────────────────────────────
    # unit_type drives how the computed float is formatted
    # options: "minutes" | "hours" | "reps" | "sets" | "pages" | "km"
    unit_type = Column(String(20), nullable=False, default="minutes")

    # ── Base XP this template contributes (before tier multipliers) ───────────
    base_xp = Column(Integer, nullable=False, default=100)

    # ── Additional quest meta injected at instantiation time ─────────────────
    # Stored as JSON: {"time_limit_minutes": 90, "generates_penalty_quest": true}
    meta_overrides = Column(JSON, nullable=True)

    # ── Stat bonuses awarded on completion (merged with DifficultyProfile) ───
    # {"intelligence": 2.0} — these stack *additively* with base rewards
    stat_bonus = Column(JSON, nullable=True)

    # ── Structured difficulty parameters ───────────────────────────────────────
    # These four axes replace pure time-based difficulty scaling.
    # Validated by DifficultyEngine before any template is accepted.

    # How long the quest runs — hard-capped per tier:
    #   easy ≤60 min | intermediate ≤120 min | hard ≤180 min | extreme ≤300 min
    max_duration_minutes = Column(Integer, nullable=True)

    # How constrained the quest is (1=light rules, 4=maximum restrictions)
    # easy=1, intermediate=2, hard=3, extreme=4
    constraint_level = Column(Integer, nullable=False, default=1)

    # Whether a measurable performance criterion is required (hard/extreme only)
    performance_required = Column(Boolean, nullable=False, default=False)

    # Consequence level (1=low, 4=high penalty/demotion risk)
    # easy=1, intermediate=2, hard=3, extreme=4
    risk_level = Column(Integer, nullable=False, default=1)

    # Hours a player must wait before this template can be chosen again.
    # 0 for easy/intermediate/hard. 48 for extreme.
    cooldown_hours = Column(Integer, nullable=False, default=0)

    # ── Flags ────────────────────────────────────────────────────────────────
    is_active = Column(Boolean, nullable=False, default=True)

    # ── Weight for random selection when multiple templates match ─────────────
    selection_weight = Column(Float, nullable=False, default=1.0)

    def __repr__(self) -> str:
        return (
            f"<QuestTemplate id={self.id} category={self.category!r} "
            f"tier={self.tier!r} phase={self.phase!r}>"
        )
