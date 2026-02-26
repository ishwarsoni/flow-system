from sqlalchemy import Column, Integer, String, DateTime, Boolean
from datetime import datetime, UTC
from app.db.base import Base


class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    email = Column(String(100), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    hunter_name = Column(String(20), nullable=False, default="Hunter")
    is_active = Column(Boolean, default=True)
    # Starting difficulty chosen at registration: beginner | normal | hard | extreme
    starting_difficulty = Column(String(20), nullable=False, default="normal")
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))
    updated_at = Column(DateTime, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))
    
    def __repr__(self):
        return f"<User(id={self.id}, username={self.username}, email={self.email})>"
