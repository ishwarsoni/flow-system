import logging
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.config import get_settings
from app.core.limiter import limiter
from app.db.database import get_db
from app.schemas.user import (
    UserRegisterRequest,
    UserLoginRequest,
    UserResponse,
    TokenResponse,
    RefreshRequest,
)
from app.services.user_service import UserService
from app.core.security import create_access_token, create_refresh_token, decode_token, revoke_token, decode_and_consume_refresh
from app.core.exceptions import FLOWException, InvalidTokenException
from app.dependencies.auth import get_current_user

logger = logging.getLogger(__name__)
settings = get_settings()

router = APIRouter()


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit(settings.REGISTER_RATE_LIMIT)
def register(
    request: Request,
    user_data: UserRegisterRequest,
    db: Session = Depends(get_db),
) -> UserResponse:
    """Register a new user (rate-limited to prevent mass account creation)."""
    try:
        user = UserService.register_user(db, user_data)
        logger.info("New user registered: %s (id=%s)", user.username, user.id)

        # Audit log
        from app.services.audit_service import audit_log
        audit_log(db, user_id=user.id, event_type="register", request=request)

        return user
    except FLOWException as e:
        raise HTTPException(
            status_code=e.status_code,
            detail=e.message,
        )


@router.post("/login", response_model=TokenResponse, status_code=status.HTTP_200_OK)
@limiter.limit(settings.LOGIN_RATE_LIMIT)
def login(
    request: Request,
    login_data: UserLoginRequest,
    db: Session = Depends(get_db),
) -> TokenResponse:
    """Login user — returns short-lived access token + long-lived refresh token."""
    from app.services.lockout_service import LockoutService
    from app.services.audit_service import audit_log

    client_ip = request.client.host if request.client else "unknown"

    # Check lockout BEFORE attempting authentication
    locked, remaining = LockoutService.is_locked_out(db, login_data.email, client_ip)
    if locked:
        audit_log(db, user_id=None, event_type="login_blocked_lockout", request=request,
                  metadata={"email": login_data.email, "remaining_seconds": remaining})
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Account temporarily locked. Try again in {remaining // 60 + 1} minutes.",
        )

    try:
        user = UserService.authenticate_user(db, login_data)
    except FLOWException:
        # Record failed attempt
        LockoutService.record_failed_attempt(db, login_data.email, client_ip)
        audit_log(db, user_id=None, event_type="login_failure", request=request,
                  metadata={"email": login_data.email})
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )
    
    # Successful login — reset failed attempts
    LockoutService.reset_attempts(db, login_data.email, client_ip)

    access_token: str = create_access_token(user.id)
    refresh_token: str = create_refresh_token(user.id)
    
    logger.info("User login: %s (id=%s)", user.username, user.id)
    audit_log(db, user_id=user.id, event_type="login_success", request=request)
    
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        user=UserResponse.model_validate(user),
    )


@router.post("/refresh", response_model=TokenResponse, status_code=status.HTTP_200_OK)
@limiter.limit("10/minute")
def refresh(
    request: Request,
    body: RefreshRequest,
    db: Session = Depends(get_db),
) -> TokenResponse:
    """Exchange a valid refresh token for new tokens.

    Uses atomic consume: the old refresh token is marked as used BEFORE new tokens
    are issued. If two requests race with the same token, only the first succeeds.
    This blocks refresh token replay attacks.
    """
    from app.services.audit_service import audit_log

    try:
        # decode_and_consume_refresh atomically marks the token as used.
        # If the same token is presented again (replay), this raises InvalidTokenException.
        payload = decode_and_consume_refresh(body.refresh_token)
        user_id = int(payload["sub"])
    except (InvalidTokenException, ValueError, KeyError) as e:
        # Log replay attempts specifically
        detail_msg = str(getattr(e, 'message', e))
        if 'already used' in detail_msg.lower():
            audit_log(db, user_id=None, event_type="refresh_replay_blocked", request=request,
                      metadata={"detail": detail_msg})
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )

    user = UserService.get_user_by_id(db, user_id)
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found or inactive")

    # Also blacklist old token (belt-and-suspenders with consume)
    revoke_token(body.refresh_token)

    new_access = create_access_token(user.id)
    new_refresh = create_refresh_token(user.id)

    audit_log(db, user_id=user.id, event_type="token_refresh", request=request)
    
    return TokenResponse(
        access_token=new_access,
        refresh_token=new_refresh,
        token_type="bearer",
        user=UserResponse.model_validate(user),
    )


@router.post("/logout", status_code=status.HTTP_200_OK)
@limiter.limit("10/minute")
def logout(
    request: Request,
    body: RefreshRequest,
    current_user: UserResponse = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Logout — revoke both access and refresh tokens."""
    from app.services.audit_service import audit_log

    # Revoke refresh token
    revoke_token(body.refresh_token)

    # Revoke access token (from Authorization header)
    auth_header = request.headers.get("authorization", "")
    if auth_header.startswith("Bearer "):
        revoke_token(auth_header[7:])

    audit_log(db, user_id=current_user.id, event_type="logout", request=request)
    return {"detail": "Logged out successfully"}


@router.get("/me", response_model=UserResponse, status_code=status.HTTP_200_OK)
def get_current_user_info(
    current_user: UserResponse = Depends(get_current_user),
) -> UserResponse:
    """Get current authenticated user info"""
    return current_user
