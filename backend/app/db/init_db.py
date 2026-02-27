"""Database initialization and migrations"""

from sqlalchemy.orm import Session
from datetime import datetime

from app.models.game_config import GameConfig, DEFAULT_CONFIG
from app.core.exceptions import FLOWException


class InitializationException(FLOWException):
    """Raised during database initialization"""
    
    def __init__(self, message: str):
        super().__init__(message, status_code=500)


def initialize_game_config(db: Session) -> None:
    """
    Idempotent initialization of GameConfig defaults.
    Only inserts if keys don't exist.
    """
    try:
        for key, value in DEFAULT_CONFIG.items():
            existing = db.query(GameConfig).filter(GameConfig.key == key).first()
            
            if not existing:
                config_entry = GameConfig(
                    key=key,
                    value=float(value),
                    description=f"FLOW game configuration: {key}",
                )
                db.add(config_entry)
        
        db.commit()
    except Exception as e:
        db.rollback()
        raise InitializationException(f"Failed to initialize game config: {str(e)}")


def create_all_tables(engine) -> None:
    """
    Create all database tables from SQLAlchemy models.
    Safe to run multiple times (idempotent).
    """
    try:
        # Import all models so they register with the shared Base
        from app.models.user import User
        from app.models.goal import Goal
        from app.models.quest import Quest
        from app.models.rank import Rank
        from app.models.user_stats import UserStats
        from app.models.xp_history import XPHistory
        from app.models.game_config import GameConfig
        from app.models.daily_progress import DailyProgress

        # Quest Verification System tables
        from app.models.quest_session import QuestSession
        from app.models.quest_output import QuestOutput
        from app.models.player_trust import PlayerTrust
        from app.models.verification_log import VerificationLog
        from app.models.audit_flag import AuditFlag

        # Security tables
        from app.models.audit_log import AuditLog
        from app.models.login_attempt import LoginAttempt, AccountLockout

        # Use the shared Base.metadata to create all tables at once
        from app.db.base import Base

        Base.metadata.create_all(bind=engine)
        
    except Exception as e:
        raise InitializationException(f"Failed to create tables: {str(e)}")


def migrate_add_anti_grind_tables(engine) -> None:
    """Create DailyProgress table if it doesn't exist"""
    try:
        # Ensure model is imported and create table
        from app.models.daily_progress import DailyProgress
        from app.db.base import Base

        Base.metadata.create_all(bind=engine)
    except Exception as e:
        raise InitializationException(f"Failed to create daily progress table: {str(e)}")
