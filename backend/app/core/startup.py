"""Startup hooks for FLOW application"""

import logging
from sqlalchemy.orm import Session

from app.db.database import SessionLocal, engine
from app.db.init_db import initialize_game_config, create_all_tables
from app.core.monitoring import setup_logging, setup_sentry

logger = logging.getLogger(__name__)


def startup_event():
    """Run on application startup"""
    try:
        # Initialize structured logging before anything else
        setup_logging()
        setup_sentry()
        
        logger.info("Running startup initialization...")
        
        # Create tables if they don't exist
        create_all_tables(engine)
        
        # Initialize game config defaults
        db: Session = SessionLocal()
        try:
            initialize_game_config(db)
            logger.info("Startup initialization complete")
        finally:
            db.close()

        # Secret rotation warning
        _check_secret_rotation()

    except Exception as e:
        logger.error(f"Startup initialization failed: {str(e)}")


def _check_secret_rotation():
    """Warn if SECRET_KEY is overdue for rotation."""
    import os
    from datetime import datetime, UTC
    from app.config import get_settings
    settings = get_settings()
    
    env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "..", ".env")
    try:
        mtime = os.path.getmtime(env_path)
        days_since_modified = (datetime.now(UTC).timestamp() - mtime) / 86400
        if days_since_modified > settings.SECRET_ROTATION_DAYS:
            logger.warning(
                "SECRET_KEY may be overdue for rotation (%.0f days since .env modified, limit=%d). "
                "Rotate with: python -c \"import secrets; print(secrets.token_urlsafe(48))\"",
                days_since_modified, settings.SECRET_ROTATION_DAYS,
            )
    except Exception:
        pass


def shutdown_event():
    """Run on application shutdown"""
    logger.info("FLOW backend shutting down")
