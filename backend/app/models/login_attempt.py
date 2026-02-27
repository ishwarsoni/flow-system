"""Login attempt tracking model for account lockout."""

from sqlalchemy import Column, Integer, String, DateTime, Index
from datetime import datetime, UTC
from app.db.base import Base


class LoginAttempt(Base):
    """Track failed login attempts per email + IP for lockout enforcement."""
    __tablename__ = "login_attempts"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(100), nullable=False, index=True)
    ip_address = Column(String(45), nullable=False)  # IPv6 max
    success = Column(Integer, default=0)              # 0 = failure, 1 = success
    created_at = Column(DateTime, default=lambda: datetime.now(UTC), index=True)

    __table_args__ = (
        Index("ix_login_attempt_email_ip", "email", "ip_address"),
        Index("ix_login_attempt_created", "created_at"),
    )


class AccountLockout(Base):
    """Active lockouts. Checked before every login attempt."""
    __tablename__ = "account_lockouts"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(100), nullable=False, index=True)
    ip_address = Column(String(45), nullable=False)
    locked_until = Column(DateTime, nullable=False)
    reason = Column(String(255), default="Too many failed login attempts")
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))

    __table_args__ = (
        Index("ix_lockout_email_ip", "email", "ip_address"),
    )
