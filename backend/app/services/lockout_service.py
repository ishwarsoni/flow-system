"""Account lockout service — hybrid (email + IP + combined).

Three lockout vectors:
  1. Email-only:  Same email attacked from many IPs (credential stuffing).
  2. IP-only:     Same IP attacking many emails (brute force / stuffing).
  3. Email+IP:    Standard per-user-per-origin lockout.

Any vector exceeding LOCKOUT_THRESHOLD → lock for LOCKOUT_DURATION_MINUTES.

Progressive delay: repeated lockouts double the duration each time,
up to LOCKOUT_MAX_DURATION_MINUTES.

Reset on successful login: clears lockouts for that email+IP.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, UTC
from typing import Tuple

from sqlalchemy.orm import Session
from sqlalchemy import and_, func

from app.models.login_attempt import LoginAttempt, AccountLockout
from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class LockoutService:

    @staticmethod
    def is_locked_out(db: Session, email: str, ip_address: str) -> Tuple[bool, int]:
        """Check if email OR IP is currently locked out (any vector).

        Returns:
            (is_locked, remaining_seconds)
        """
        now = datetime.now(UTC)
        email_lower = email.lower()

        # Check all lockouts matching email OR ip
        lockout = db.query(AccountLockout).filter(
            and_(
                AccountLockout.locked_until > now,
            )
        ).filter(
            # email+ip, email-only, or ip-only
            (
                (AccountLockout.email == email_lower) |
                (AccountLockout.ip_address == ip_address)
            )
        ).order_by(AccountLockout.locked_until.desc()).first()

        if lockout:
            remaining = int((lockout.locked_until - now).total_seconds())
            return True, max(remaining, 0)
        return False, 0

    @staticmethod
    def record_failed_attempt(db: Session, email: str, ip_address: str) -> None:
        """Record a failed login attempt. Lock if any threshold exceeded.

        Checks three vectors independently:
        - email+ip combined
        - email alone (across all IPs)
        - ip alone (across all emails)
        """
        now = datetime.now(UTC)
        email_lower = email.lower()

        attempt = LoginAttempt(
            email=email_lower,
            ip_address=ip_address,
            success=0,
            created_at=now,
        )
        db.add(attempt)
        db.flush()

        window_start = now - timedelta(minutes=settings.LOCKOUT_WINDOW_MINUTES)
        threshold = settings.LOCKOUT_THRESHOLD

        # ── Vector 1: email + IP combined ────────────────────────────────
        combined_count = db.query(LoginAttempt).filter(
            and_(
                LoginAttempt.email == email_lower,
                LoginAttempt.ip_address == ip_address,
                LoginAttempt.success == 0,
                LoginAttempt.created_at >= window_start,
            )
        ).count()

        if combined_count >= threshold:
            LockoutService._apply_lockout(
                db, email_lower, ip_address, combined_count,
                f"Locked email+IP after {combined_count} failures"
            )

        # ── Vector 2: email-only (credential stuffing across IPs) ────────
        email_count = db.query(LoginAttempt).filter(
            and_(
                LoginAttempt.email == email_lower,
                LoginAttempt.success == 0,
                LoginAttempt.created_at >= window_start,
            )
        ).count()

        if email_count >= threshold * 2:
            # Higher threshold for email-only (multiple IPs might share email)
            LockoutService._apply_lockout(
                db, email_lower, "*",  # wildcard IP = email-level lock
                email_count,
                f"Locked email globally after {email_count} failures from multiple IPs"
            )

        # ── Vector 3: IP-only (brute force across emails) ───────────────
        ip_count = db.query(LoginAttempt).filter(
            and_(
                LoginAttempt.ip_address == ip_address,
                LoginAttempt.success == 0,
                LoginAttempt.created_at >= window_start,
            )
        ).count()

        if ip_count >= threshold * 3:
            # Highest threshold for IP-only (shared NATs, offices)
            LockoutService._apply_lockout(
                db, "*", ip_address,  # wildcard email = IP-level lock
                ip_count,
                f"Locked IP after {ip_count} failures across multiple accounts"
            )

        db.commit()

    @staticmethod
    def _apply_lockout(
        db: Session,
        email: str,
        ip_address: str,
        fail_count: int,
        reason: str,
    ) -> None:
        """Create or escalate a lockout with progressive delay."""
        now = datetime.now(UTC)
        base_minutes = settings.LOCKOUT_DURATION_MINUTES
        max_minutes = getattr(settings, "LOCKOUT_MAX_DURATION_MINUTES", 1440)

        # Count previous lockouts for progressive escalation
        previous_lockouts = db.query(AccountLockout).filter(
            and_(
                AccountLockout.email == email,
                AccountLockout.ip_address == ip_address,
            )
        ).count()

        # Progressive: base * 2^(previous_lockouts), capped at max
        multiplier = min(2 ** previous_lockouts, max_minutes // max(base_minutes, 1))
        duration_minutes = min(base_minutes * multiplier, max_minutes)
        locked_until = now + timedelta(minutes=duration_minutes)

        # Upsert lockout
        existing = db.query(AccountLockout).filter(
            and_(
                AccountLockout.email == email,
                AccountLockout.ip_address == ip_address,
            )
        ).first()

        if existing:
            # Only escalate — never reduce an active lockout
            if locked_until > (existing.locked_until or now):
                existing.locked_until = locked_until
                existing.reason = f"{reason} (progressive: {duration_minutes}min)"
        else:
            lockout = AccountLockout(
                email=email,
                ip_address=ip_address,
                locked_until=locked_until,
                reason=f"{reason} (duration: {duration_minutes}min)",
            )
            db.add(lockout)

        logger.warning(
            "LOCKOUT | email=%s ip=%s until=%s duration=%dmin failures=%d previous_lockouts=%d",
            email, ip_address, locked_until.isoformat(),
            duration_minutes, fail_count, previous_lockouts,
        )

        # Audit log
        try:
            from app.services.audit_service import audit_log
            audit_log(
                db, user_id=None, event_type="account_locked",
                ip_address=ip_address if ip_address != "*" else None,
                metadata={
                    "email": email if email != "*" else None,
                    "fail_count": fail_count,
                    "locked_until": locked_until.isoformat(),
                    "duration_minutes": duration_minutes,
                    "previous_lockouts": previous_lockouts,
                    "progressive": previous_lockouts > 0,
                },
            )
        except Exception:
            pass  # Audit failure should never block lockout

    @staticmethod
    def reset_attempts(db: Session, email: str, ip_address: str) -> None:
        """Reset failed attempts + remove lockout on successful login."""
        email_lower = email.lower()

        # Remove lockout for this email+IP
        db.query(AccountLockout).filter(
            and_(
                AccountLockout.email == email_lower,
                AccountLockout.ip_address == ip_address,
            )
        ).delete()

        # Also clear email-level global lockout (wildcard IP) if it exists
        # so the user isn't still locked out after proving their identity
        db.query(AccountLockout).filter(
            and_(
                AccountLockout.email == email_lower,
                AccountLockout.ip_address == "*",
            )
        ).delete()

        # Don't delete history (useful for audit), but record success
        attempt = LoginAttempt(
            email=email_lower,
            ip_address=ip_address,
            success=1,
        )
        db.add(attempt)
        db.commit()

    @staticmethod
    def cleanup_old_attempts(db: Session, days: int = 30) -> int:
        """Purge login attempts older than N days. Run periodically."""
        if days < 1:
            raise ValueError("cleanup_old_attempts: days must be >= 1 to prevent accidental purge")
        cutoff = datetime.now(UTC) - timedelta(days=days)
        deleted = db.query(LoginAttempt).filter(
            LoginAttempt.created_at < cutoff
        ).delete()
        db.query(AccountLockout).filter(
            AccountLockout.locked_until < datetime.now(UTC)
        ).delete()
        db.commit()
        return deleted
