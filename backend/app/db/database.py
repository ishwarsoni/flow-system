from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from typing import Generator

from app.config import get_settings

settings = get_settings()

# Create database engine
# SECURITY: echo=DEBUG only — never log SQL statements in production
#           (they contain user emails, hashed passwords, etc.)
_engine_kwargs: dict = {
    "echo": settings.DEBUG,
    "pool_pre_ping": True,  # Verify connections before using them
}
# Add connection pool limits for non-SQLite databases to prevent DoS via pool exhaustion
if not settings.DATABASE_URL.startswith("sqlite"):
    _engine_kwargs.update({
        "pool_size": 20,
        "max_overflow": 10,
        "pool_timeout": 30,
        "pool_recycle": 1800,  # Recycle connections every 30 min
    })

engine = create_engine(
    settings.DATABASE_URL,
    **_engine_kwargs,
)

# Create session factory
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)


def get_db() -> Generator[Session, None, None]:
    """Dependency for getting database session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
