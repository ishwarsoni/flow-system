"""Startup hooks for FLOW application"""

import logging
from sqlalchemy.orm import Session

from app.db.database import SessionLocal, engine
from app.db.init_db import initialize_game_config, create_all_tables

logger = logging.getLogger(__name__)


def startup_event():
    """Run on application startup"""
    try:
        logger.info("Running startup initialization...")
        
        # Create tables if they don't exist
        create_all_tables(engine)
        
        # Initialize game config defaults
        db: Session = SessionLocal()
        try:
            initialize_game_config(db)
            logger.info("✅ Startup initialization complete")
        finally:
            db.close()
    
    except Exception as e:
        logger.error(f"Startup initialization failed: {str(e)}")
        # Don't crash on startup - config might exist already


def shutdown_event():
    """Run on application shutdown"""
    logger.info("🛑 FLOW backend shutting down")
