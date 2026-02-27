from fastapi import Depends, HTTPException, status, Header
from sqlalchemy.orm import Session
from typing import Optional

from app.core.security import decode_token
from app.core.exceptions import InvalidTokenException
from app.db.database import get_db
from app.models.user import User
from app.services.user_service import UserService


def get_current_user(
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
) -> User:
    """Get current authenticated user from JWT token in Authorization header"""
    
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    try:
        scheme, token = authorization.split()
        if scheme.lower() != "bearer":
            raise ValueError("Invalid authentication scheme")
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        payload = decode_token(token, expected_type="access")

        sub = payload.get("sub")
        if not sub:
            raise InvalidTokenException("Invalid token")

        user_id = int(sub)

    except InvalidTokenException as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=e.message,
            headers={"WWW-Authenticate": "Bearer"},
        )

    except (ValueError, TypeError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token format",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user: User | None = UserService.get_user_by_id(db, user_id)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user


def get_admin_user(
    current_user: User = Depends(get_current_user),
) -> User:
    """Require the current user to have admin privileges.

    Use as a dependency on any admin-only endpoint:
        current_user: User = Depends(get_admin_user)
    """
    if not getattr(current_user, "is_admin", False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required",
        )
    return current_user
