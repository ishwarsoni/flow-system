import bcrypt
import secrets
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional
import jwt

from app.config import get_settings
from app.core.exceptions import InvalidTokenException

settings = get_settings()
logger = logging.getLogger(__name__)


# ── Password Hashing ───────────────────────────────────────────────────────
def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(rounds=12)).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Constant-time password comparison via bcrypt."""
    return bcrypt.checkpw(
        plain_password.encode("utf-8"), hashed_password.encode("utf-8")
    )


# ── JWT Access Token ───────────────────────────────────────────────────────
def create_access_token(
    user_id: int,
    expires_delta: Optional[timedelta] = None,
) -> str:
    from app.core.token_blacklist import register_token

    now = datetime.now(timezone.utc)
    delta = expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    expire = now + delta

    jti = secrets.token_hex(16)
    payload = {
        "sub": str(user_id),
        "exp": int(expire.timestamp()),
        "iat": int(now.timestamp()),
        "type": "access",
        "jti": jti,
    }

    token = jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    register_token(jti, "access", int(delta.total_seconds()))
    return token


# ── JWT Refresh Token ──────────────────────────────────────────────────────
def create_refresh_token(
    user_id: int,
    expires_delta: Optional[timedelta] = None,
) -> str:
    from app.core.token_blacklist import register_token

    now = datetime.now(timezone.utc)
    delta = expires_delta or timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    expire = now + delta

    jti = secrets.token_hex(16)
    payload = {
        "sub": str(user_id),
        "exp": int(expire.timestamp()),
        "iat": int(now.timestamp()),
        "type": "refresh",
        "jti": jti,
    }

    token = jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    register_token(jti, "refresh", int(delta.total_seconds()))
    return token


# ── Token Decoding ─────────────────────────────────────────────────────────
def decode_token(token: str, expected_type: str = "access") -> dict:
    """Decode and validate a JWT. Checks blacklist. Raises InvalidTokenException on failure."""
    from app.core.token_blacklist import is_token_blacklisted

    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM],
        )
        # Enforce token type
        if payload.get("type") != expected_type:
            raise InvalidTokenException("Invalid token type")

        # Check blacklist — reject revoked tokens
        jti = payload.get("jti")
        if jti and is_token_blacklisted(jti):
            logger.warning("Blacklisted token used: jti=%s user=%s", jti[:8], payload.get("sub"))
            raise InvalidTokenException("Token has been revoked")

        return payload

    except InvalidTokenException:
        raise
    except jwt.ExpiredSignatureError:
        raise InvalidTokenException("Token has expired")
    except jwt.PyJWTError:
        raise InvalidTokenException("Invalid token")


def revoke_token(token: str) -> None:
    """Revoke a token by adding its jti to the blacklist."""
    from app.core.token_blacklist import blacklist_token

    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM],
            options={"verify_exp": False},  # Allow revoking expired tokens too
        )
        jti = payload.get("jti")
        if not jti:
            return
        # Blacklist for remaining lifetime (or 1 day if already expired)
        exp = payload.get("exp", 0)
        now = int(datetime.now(timezone.utc).timestamp())
        ttl = max(exp - now, 86400)
        blacklist_token(jti, ttl)
    except jwt.PyJWTError:
        pass  # Can't decode → can't revoke → token was invalid anyway


def decode_and_consume_refresh(token: str) -> dict:
    """Decode a refresh token AND atomically mark it as consumed.

    This prevents refresh token replay attacks. If the same refresh token
    is presented twice (even in a race condition), only the first call succeeds.

    Raises InvalidTokenException on:
    - Invalid/expired token
    - Wrong token type
    - Blacklisted token
    - Already-consumed token (replay)
    """
    from app.core.token_blacklist import is_token_blacklisted, consume_refresh_token

    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM],
        )
        if payload.get("type") != "refresh":
            raise InvalidTokenException("Invalid token type")

        jti = payload.get("jti")
        if not jti:
            raise InvalidTokenException("Invalid token: missing jti")

        # Check blacklist first
        if is_token_blacklisted(jti):
            logger.warning("Blacklisted refresh token used: jti=%s user=%s", jti[:8], payload.get("sub"))
            raise InvalidTokenException("Token has been revoked")

        # Atomically consume — rejects replays
        exp = payload.get("exp", 0)
        now = int(datetime.now(timezone.utc).timestamp())
        ttl = max(exp - now, 86400)

        if not consume_refresh_token(jti, ttl):
            logger.warning(
                "REFRESH REPLAY BLOCKED: jti=%s user=%s",
                jti[:8], payload.get("sub"),
            )
            raise InvalidTokenException("Refresh token already used")

        return payload

    except InvalidTokenException:
        raise
    except jwt.ExpiredSignatureError:
        raise InvalidTokenException("Refresh token has expired")
    except jwt.PyJWTError:
        raise InvalidTokenException("Invalid refresh token")
