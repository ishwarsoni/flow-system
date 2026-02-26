"""
Startup initialization script for FLOW backend.

Run this once during deployment to:
1. Create all database tables
2. Initialize GameConfig defaults
"""

import sys
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.database import engine, SessionLocal
from app.db.init_db import initialize_game_config, create_all_tables, InitializationException


def init_database():
    """Initialize database: create tables and seed config"""
    print("🚀 Initializing FLOW database...")
    
    try:
        # Create all tables
        print("  📋 Creating database tables...")
        create_all_tables(engine)
        print("     ✅ Tables created")
        
        # Initialize game config
        print("  ⚙️  Initializing game configuration...")
        db: Session = SessionLocal()
        try:
            initialize_game_config(db)
            print("     ✅ Configuration initialized")
        finally:
            db.close()
        
        print("✅ Database initialization complete!")
        return True
    
    except InitializationException as e:
        print(f"❌ Initialization failed: {e.message}")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {str(e)}")
        return False


if __name__ == "__main__":
    success = init_database()
    sys.exit(0 if success else 1)
