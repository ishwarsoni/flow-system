"""XP and event history — audit trail for all progression changes."""

from sqlalchemy import Column, Integer, DateTime, ForeignKey, Enum, String, JSON
from datetime import datetime, UTC
import enum
from app.db.base import Base


class XPChangeType(str, enum.Enum):
    QUEST_COMPLETED = "quest_completed"
    QUEST_FAILED = "quest_failed"
    QUEST_EXPIRED = "quest_expired"
    PENALTY = "penalty"
    BONUS = "bonus"
    STREAK_BONUS = "streak_bonus"
    RANK_PROMOTION = "rank_promotion"
    STAT_DECAY = "stat_decay"
    ITEM_USED = "item_used"


class XPHistory(Base):
    __tablename__ = "xp_history"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    quest_id = Column(Integer, ForeignKey("quests.id"), nullable=True)

    xp_amount = Column(Integer, nullable=False)  # Can be negative
    coin_amount = Column(Integer, default=0)     # Coins gained/lost
    change_type = Column(Enum(XPChangeType), nullable=False)
    reason = Column(String(255), nullable=True)

    # Stat deltas: {"strength": 5.2, "vitality": 3.1, "mana": -2.0, ...}
    stat_deltas = Column(JSON, nullable=True)

    # Snapshot at time of event (for replay/analytics)
    level_at_time = Column(Integer, nullable=True)
    rank_at_time = Column(String(10), nullable=True)

    created_at = Column(DateTime, default=lambda: datetime.now(UTC), index=True)

    def __repr__(self):
        return f"<XPHistory(user={self.user_id}, xp={self.xp_amount}, type={self.change_type})>"
