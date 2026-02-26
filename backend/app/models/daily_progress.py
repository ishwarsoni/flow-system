"""Anti-grind protection: daily progress tracking"""

from sqlalchemy import Column, Integer, DateTime, ForeignKey, Date
from datetime import datetime, date, UTC
from app.db.base import Base


class DailyProgress(Base):
    """Track daily XP and quest completion to prevent grinding.

    NOTE: Column names `tasks_completed_today` / `tasks_failed_today` are
    kept for backward-compatible DB schema. They now count *quest* completions.
    """
    
    __tablename__ = "daily_progress"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    date = Column(Date, default=date.today, index=True)  # Date tracking for daily reset
    
    # Daily stats
    xp_earned_today = Column(Integer, default=0)  # Total XP earned this day
    tasks_completed_today = Column(Integer, default=0)
    tasks_failed_today = Column(Integer, default=0)
    
    # Efficiency tracking (for diminishing returns)
    last_task_completion_time = Column(DateTime, nullable=True)  # Track gaps between tasks
    task_streak = Column(Integer, default=0)  # Consecutive days with task completions
    
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))
    updated_at = Column(DateTime, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))
    
    def __repr__(self):
        return f"<DailyProgress(user_id={self.user_id}, date={self.date}, xp_earned={self.xp_earned_today})>"
