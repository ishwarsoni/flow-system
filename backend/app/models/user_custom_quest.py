"""UserCustomQuest + DismissedSystemQuest models.

UserCustomQuest   — quests manually created by the player.
DismissedSystemQuest — system-recommended templates a player has hidden.
"""

from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, ForeignKey, Text, JSON
from datetime import datetime, UTC
from app.db.base import Base


class UserCustomQuest(Base):
    """A quest the player wrote themselves.
    Appears alongside system options in the daily panel.

    Validation rules (enforced by CustomQuestService):
    - Hard / Extreme: metrics_required = True always
    - Extreme: cooldown_hours = 24, weekly_limit = 3
    - duration_minutes must not exceed tier cap
    - All fields are verifiable by the system or the player
    """
    __tablename__ = "user_custom_quests"

    id             = Column(Integer, primary_key=True, index=True)
    user_id        = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    category       = Column(String(32), nullable=False, index=True)   # mind|body|core|control|presence|system
    tier           = Column(String(16), nullable=False, default="easy")  # easy|intermediate|hard|extreme
    title          = Column(String(200), nullable=False)
    description    = Column(Text, nullable=True)

    # Duration — validated against tier caps
    duration_value    = Column(Float, nullable=True)             # e.g. 45
    duration_unit     = Column(String(20), default="minutes")    # minutes|hours|reps|pages|sets|tasks
    # Explicit cap stored in minutes for engine validation (NULL = task-based)
    max_duration_minutes = Column(Integer, nullable=True)

    xp_override    = Column(Integer, nullable=True)              # NULL = auto-calculated from tier

    # Difficulty axes (mirrors quest_templates schema)
    constraint_level     = Column(Integer, nullable=False, default=1)   # 1–4
    performance_required = Column(Boolean, nullable=False, default=False)
    risk_level           = Column(Integer, nullable=False, default=1)    # 1–4

    # Metrics a player must submit to prove completion
    # JSON: {"type": "reps", "target": 100} | {"type": "output", "description": "written essay"}
    # Required when tier is hard or extreme
    metrics_required   = Column(Boolean, nullable=False, default=False)
    metrics_definition = Column(JSON, nullable=True)

    # Cooldown / rate limiting
    cooldown_hours = Column(Integer, nullable=False, default=0)  # EXTREME = 24
    weekly_limit   = Column(Integer, nullable=True)              # EXTREME = 3; NULL = no limit

    is_active      = Column(Boolean, default=True, nullable=False)
    created_at     = Column(DateTime, default=lambda: datetime.now(UTC))
    updated_at     = Column(DateTime, default=lambda: datetime.now(UTC),
                            onupdate=lambda: datetime.now(UTC))

    def __repr__(self) -> str:
        return f"<UserCustomQuest id={self.id} user={self.user_id} tier={self.tier!r} title={self.title!r}>"


class DismissedSystemQuest(Base):
    """Records which system quest templates a user has permanently hidden.

    When the generation engine picks templates it excludes any IDs found here.
    Player can restore a dismissed template at any time.
    """
    __tablename__ = "dismissed_system_quests"

    id                 = Column(Integer, primary_key=True, index=True)
    user_id            = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    quest_template_id  = Column(Integer, ForeignKey("quest_templates.id"), nullable=False, index=True)
    reason             = Column(String(200), nullable=True)
    dismissed_at       = Column(DateTime, default=lambda: datetime.now(UTC))

    def __repr__(self) -> str:
        return (
            f"<DismissedSystemQuest user={self.user_id} "
            f"template={self.quest_template_id}>"
        )
