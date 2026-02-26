"""Player stats — the RPG stat sheet. All values are calculated, nothing hardcoded."""

from sqlalchemy import Column, Integer, Float, DateTime, ForeignKey, Enum, String
from datetime import datetime, UTC
from app.db.base import Base
from app.models.rank import Rank


class UserStats(Base):
    __tablename__ = "user_stats"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False, index=True)

    # === PROGRESSION ===
    level = Column(Integer, default=1)
    xp_current = Column(Integer, default=0)       # XP towards next level
    xp_total_earned = Column(Integer, default=0)   # Lifetime total
    rank = Column(Enum(Rank), default=Rank.E)
    skill_points = Column(Integer, default=0)      # Earned on level-up, spent on stats

    # === VITALS (calculated from stats) ===
    hp_current = Column(Integer, default=100)
    hp_max = Column(Integer, default=100)          # Base 100 + VIT bonus + rank bonus
    mp_current = Column(Integer, default=50)
    mp_max = Column(Integer, default=50)           # Base 50 + MANA bonus + rank bonus

    # === CORE STATS (0-100, mapped to life actions) ===
    strength = Column(Float, default=10.0)         # Physical: gym, exercise, sports
    intelligence = Column(Float, default=10.0)     # Study: learning, reading, courses
    vitality = Column(Float, default=10.0)         # Health: sleep, nutrition, recovery
    charisma = Column(Float, default=10.0)         # Social: networking, leadership, communication
    mana = Column(Float, default=10.0)             # Focus: meditation, deep work, concentration

    # === ECONOMY ===
    coins = Column(Integer, default=0)             # Earned from quests, spent in shop
    reputation = Column(Integer, default=0)        # Earned from streaks + special quests

    # === TITLES ===
    current_title = Column(String(100), default="Novice")  # Active title

    # === SYSTEM ===
    fatigue = Column(Float, default=0.0)           # 0-100, reduces XP gain when high
    streak_days = Column(Integer, default=0)       # Current streak
    longest_streak = Column(Integer, default=0)    # Best ever
    last_active_at = Column(DateTime, default=lambda: datetime.now(UTC))
    punishment_active = Column(Integer, default=0) # 0 = none, >0 = hours remaining

    created_at = Column(DateTime, default=lambda: datetime.now(UTC))
    updated_at = Column(DateTime, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))

    @property
    def focus(self):
        return self.mana

    @focus.setter
    def focus(self, value):
        self.mana = value

    @property
    def discipline(self):
        return self.strength

    @discipline.setter
    def discipline(self, value):
        self.strength = value

    @property
    def energy(self):
        return self.vitality

    @energy.setter
    def energy(self, value):
        self.vitality = value

    @property
    def consistency(self):
        return self.charisma

    @consistency.setter
    def consistency(self, value):
        self.charisma = value

    def __repr__(self):
        return f"<UserStats(user={self.user_id}, lv={self.level}, rank={self.rank}, hp={self.hp_current}/{self.hp_max})>"
