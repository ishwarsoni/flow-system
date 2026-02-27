"""AuditLog model — immutable security event log.

Every security-relevant event is recorded here.
No silent events. No deletions.
"""

from sqlalchemy import Column, Integer, String, DateTime, JSON, Index, Text
from datetime import datetime, UTC
from app.db.base import Base


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=True, index=True)       # NULL for anonymous events (failed login)
    event_type = Column(String(50), nullable=False, index=True) # e.g. login_success, login_failure, account_locked
    ip_address = Column(String(45), nullable=True)              # IPv6 max length
    user_agent = Column(String(500), nullable=True)
    event_metadata = Column("metadata", JSON, nullable=True)    # Arbitrary event-specific data
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(UTC), index=True)

    __table_args__ = (
        Index("ix_audit_user_event", "user_id", "event_type"),
        Index("ix_audit_created", "created_at"),
        Index("ix_audit_event_created", "event_type", "created_at"),
    )

    def __repr__(self):
        return f"<AuditLog(id={self.id}, user={self.user_id}, event={self.event_type})>"
