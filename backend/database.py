from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.db.base import Base

# Change password if different
DB_USER = "postgres"
DB_PASSWORD = "123"   # <-- your postgres password
DB_HOST = "localhost"
DB_PORT = "5432"
DB_NAME = "flow_db"

DATABASE_URL = (
    f"postgresql+psycopg2://{DB_USER}:{DB_PASSWORD}"
    f"@{DB_HOST}:{DB_PORT}/{DB_NAME}"
)

engine = create_engine(DATABASE_URL, echo=True)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

# Export shared Base for external use
# Use Base from app.db.base (SQLAlchemy 2.0 compatible)
