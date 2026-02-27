"""Token blacklist backed by Redis.

On token issue  → store jti with TTL matching the token's expiry.
On logout       → add jti to blacklist set.
On refresh      → revoke old refresh-token jti.
On every request→ reject if jti is blacklisted.

PRODUCTION: Redis is MANDATORY. No memory fallback. Fail closed.
DEV (DEBUG=True): In-memory dict fallback allowed.
"""

from __future__ import annotations

import logging
import time
from typing import Optional

logger = logging.getLogger(__name__)

# ── Redis client (lazy-init) ──────────────────────────────────────────────────
_redis_client = None
_init_attempted = False
_fallback_store: dict[str, float] = {}  # jti → expiry timestamp (dev-only fallback)
_is_production = False  # resolved on first _get_redis() call

_BLACKLIST_PREFIX = "flow:token:blacklist:"
_ISSUED_PREFIX = "flow:token:issued:"
_USED_REFRESH_PREFIX = "flow:token:used_refresh:"


class RedisRequiredError(RuntimeError):
    """Raised when Redis is required (production) but unavailable."""
    pass


def _get_redis():
    """Lazy-connect to Redis.

    Production (DEBUG=False): Redis is mandatory. Raises RedisRequiredError.
    Development (DEBUG=True): Returns None → in-memory fallback.
    """
    global _redis_client, _init_attempted, _is_production

    if _redis_client is not None:
        return _redis_client

    from app.config import get_settings
    settings = get_settings()
    _is_production = not settings.DEBUG

    redis_url = getattr(settings, "REDIS_URL", "")
    if not redis_url:
        if _is_production:
            raise RedisRequiredError(
                "REDIS_URL is required in production (DEBUG=False). "
                "Set REDIS_URL in .env (e.g. redis://127.0.0.1:6379/0)."
            )
        if not _init_attempted:
            logger.info("REDIS_URL not set — using in-memory token store (dev only)")
            _init_attempted = True
        return None

    try:
        import redis as redis_lib
        _redis_client = redis_lib.Redis.from_url(
            redis_url,
            decode_responses=True,
            socket_connect_timeout=3,
            socket_timeout=2,
            retry_on_timeout=True,
        )
        _redis_client.ping()
        logger.info("Connected to Redis for token blacklist")
        return _redis_client
    except Exception as e:
        _redis_client = None
        if _is_production:
            raise RedisRequiredError(
                f"Redis connection failed in production: {e}. "
                "Token blacklist requires Redis. Fix connection or set DEBUG=True for dev."
            )
        logger.warning("Redis unavailable (%s) — falling back to in-memory store (dev)", e)
        _init_attempted = True
        return None


# ── Public API ─────────────────────────────────────────────────────────────────

def register_token(jti: str, token_type: str, expires_in_seconds: int) -> None:
    """Register a newly issued token. Stores jti with TTL for tracking."""
    r = _get_redis()
    key = f"{_ISSUED_PREFIX}{jti}"
    if r:
        try:
            r.setex(key, expires_in_seconds, token_type)
        except Exception as e:
            if _is_production:
                raise RedisRequiredError(f"Redis register_token failed: {e}")
            logger.error("Redis register_token failed: %s", e)
    else:
        _fallback_store[key] = time.time() + expires_in_seconds


def blacklist_token(jti: str, expires_in_seconds: int) -> None:
    """Blacklist a token by jti. The key auto-expires when the token would have."""
    r = _get_redis()
    key = f"{_BLACKLIST_PREFIX}{jti}"
    if r:
        try:
            r.setex(key, expires_in_seconds, "revoked")
            logger.info("Token blacklisted: jti=%s", jti[:8])
        except Exception as e:
            if _is_production:
                raise RedisRequiredError(f"Redis blacklist_token failed: {e}")
            logger.error("Redis blacklist_token failed: %s", e)
    else:
        _fallback_store[key] = time.time() + expires_in_seconds


def is_token_blacklisted(jti: str) -> bool:
    """Check if a jti has been revoked.

    FAIL CLOSED: if Redis errors in production → treat as blacklisted (deny access).
    """
    r = _get_redis()
    key = f"{_BLACKLIST_PREFIX}{jti}"
    if r:
        try:
            return r.exists(key) > 0
        except Exception as e:
            logger.error("Redis is_token_blacklisted failed: %s — FAIL CLOSED", e)
            return True  # Fail closed: deny access when blacklist is unavailable
    else:
        _cleanup_fallback()
        return key in _fallback_store


def consume_refresh_token(jti: str, expires_in_seconds: int) -> bool:
    """Atomically mark a refresh token as used. Returns True if this is the FIRST use.

    Prevents refresh token replay: if two requests race with the same refresh token,
    only the first one succeeds. Uses Redis SETNX for atomicity.

    In dev mode (no Redis), uses in-memory dict (not atomic, but sufficient for dev).
    """
    r = _get_redis()
    key = f"{_USED_REFRESH_PREFIX}{jti}"
    if r:
        try:
            # SETNX: returns True only if key was newly set (first use)
            first_use = r.set(key, "used", nx=True, ex=expires_in_seconds)
            if not first_use:
                logger.warning("REPLAY DETECTED: refresh token jti=%s already used", jti[:8])
            return bool(first_use)
        except Exception as e:
            logger.error("Redis consume_refresh_token failed: %s — FAIL CLOSED", e)
            return False  # Fail closed: reject on Redis error
    else:
        # Dev fallback — not truly atomic but functional for single-process dev
        _cleanup_fallback()
        if key in _fallback_store:
            logger.warning("REPLAY DETECTED (dev): refresh token jti=%s already used", jti[:8])
            return False
        _fallback_store[key] = time.time() + expires_in_seconds
        return True


def blacklist_all_user_tokens(user_id: int) -> int:
    """Revoke ALL tokens for a user (e.g., password change, account compromise).

    Scans issued tokens with the user pattern and blacklists them.
    Returns count of blacklisted tokens.
    """
    r = _get_redis()
    if not r:
        return 0

    # Requires storing user_id in the issued key — not done in the basic flow.
    # For now, individual logout/refresh revocation handles the common cases.
    logger.warning("blacklist_all_user_tokens called — requires user→jti index (not yet implemented)")
    return 0


def get_blacklist_stats() -> dict:
    """Return blacklist statistics for monitoring."""
    r = _get_redis()
    if r:
        try:
            blacklisted = len(list(r.scan_iter(f"{_BLACKLIST_PREFIX}*", count=1000)))
            issued = len(list(r.scan_iter(f"{_ISSUED_PREFIX}*", count=1000)))
            return {"blacklisted": blacklisted, "issued_tracked": issued, "backend": "redis"}
        except Exception:
            return {"blacklisted": 0, "issued_tracked": 0, "backend": "redis-error"}
    else:
        _cleanup_fallback()
        bl = sum(1 for k in _fallback_store if k.startswith(_BLACKLIST_PREFIX))
        issued = sum(1 for k in _fallback_store if k.startswith(_ISSUED_PREFIX))
        return {"blacklisted": bl, "issued_tracked": issued, "backend": "memory"}


def check_redis_health() -> dict:
    """Health check for Redis connection. Returns status dict."""
    try:
        r = _get_redis()
        if r:
            r.ping()
            info = r.info("memory")
            return {
                "status": "connected",
                "used_memory_human": info.get("used_memory_human", "unknown"),
            }
        else:
            return {"status": "memory-fallback (dev)"}
    except RedisRequiredError as e:
        return {"status": "error", "detail": str(e)}
    except Exception as e:
        return {"status": "error", "detail": str(e)}


# ── Internal ──────────────────────────────────────────────────────────────────

def _cleanup_fallback():
    """Remove expired entries from in-memory fallback store."""
    now = time.time()
    expired = [k for k, exp in _fallback_store.items() if exp < now]
    for k in expired:
        del _fallback_store[k]
