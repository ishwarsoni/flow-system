"""Audit logging service.

Provides a single `audit_log()` function to record security events.
Call from auth, progression, quest, verification, and abuse detection code.

Event types:
  Auth:        login_success, login_failure, login_blocked_lockout, register, logout
  Lockout:     account_locked, account_unlocked
  Token:       token_refresh, token_revoked
  Progression: rank_promotion, rank_demotion
  Quest:       extreme_fail, punishment_mode_triggered
  Abuse:       xp_anomaly_detected, suspicion_score_increased, abuse_penalty_applied
"""

from __future__ import annotations

import logging
from datetime import datetime, UTC
from typing import Optional

from sqlalchemy.orm import Session
from fastapi import Request

from app.models.audit_log import AuditLog

logger = logging.getLogger(__name__)


def audit_log(
    db: Session,
    *,
    user_id: Optional[int] = None,
    event_type: str,
    request: Optional[Request] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
    metadata: Optional[dict] = None,
) -> None:
    """Write an immutable audit log entry.
    
    If a FastAPI `request` is provided, IP and User-Agent are extracted from it.
    Can also be called with explicit ip_address / user_agent.
    """
    try:
        if request:
            if not ip_address:
                ip_address = request.client.host if request.client else "unknown"
            if not user_agent:
                user_agent = request.headers.get("user-agent", "")[:500]

        entry = AuditLog(
            user_id=user_id,
            event_type=event_type,
            ip_address=ip_address,
            user_agent=user_agent,
            event_metadata=metadata,
            created_at=datetime.now(UTC),
        )
        db.add(entry)
        db.flush()  # flush but don't commit — caller owns the transaction

        logger.info(
            "AUDIT | event=%s user=%s ip=%s meta=%s",
            event_type, user_id, ip_address, metadata,
        )
    except Exception as e:
        # Audit logging must NEVER crash the request
        logger.error("Audit log write failed: %s", e)


def get_recent_events(
    db: Session,
    user_id: Optional[int] = None,
    event_type: Optional[str] = None,
    limit: int = 100,
) -> list[AuditLog]:
    """Query recent audit events for admin/monitoring dashboards."""
    query = db.query(AuditLog)
    if user_id is not None:
        query = query.filter(AuditLog.user_id == user_id)
    if event_type:
        query = query.filter(AuditLog.event_type == event_type)
    return query.order_by(AuditLog.created_at.desc()).limit(limit).all()
