from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, Enum
from datetime import datetime, UTC
import enum
from app.db.base import Base


class GoalStatus(str, enum.Enum):
    ACTIVE = "active"
    COMPLETED = "completed"
    PAUSED = "paused"
    ABANDONED = "abandoned"


class Goal(Base):
    __tablename__ = "goals"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    status = Column(Enum(GoalStatus), default=GoalStatus.ACTIVE)
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))
    updated_at = Column(DateTime, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))
    
    def __repr__(self):
        return f"<Goal(id={self.id}, user_id={self.user_id}, title={self.title})>"
