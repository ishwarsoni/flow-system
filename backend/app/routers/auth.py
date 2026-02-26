from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.schemas.user import (
    UserRegisterRequest,
    UserLoginRequest,
    UserResponse,
    TokenResponse,
)
from app.services.user_service import UserService
from app.core.security import create_access_token
from app.core.exceptions import FLOWException
from app.dependencies.auth import get_current_user

router = APIRouter()


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(
    user_data: UserRegisterRequest,
    db: Session = Depends(get_db),
) -> UserResponse:
    """Register a new user"""
    try:
        user = UserService.register_user(db, user_data)
        return user
    except FLOWException as e:
        raise HTTPException(
            status_code=e.status_code,
            detail=e.message,
        )


@router.post("/login", response_model=TokenResponse, status_code=status.HTTP_200_OK)
def login(
    login_data: UserLoginRequest,
    db: Session = Depends(get_db),
) -> TokenResponse:
    """Login user and return JWT token"""
    try:
        user = UserService.authenticate_user(db, login_data)
    except FLOWException as e:
        raise HTTPException(
            status_code=e.status_code,
            detail=e.message,
        )
    
    # Create access token
    access_token: str = create_access_token(user.id)
    
    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        user=UserResponse.model_validate(user),
    )


@router.get("/me", response_model=UserResponse, status_code=status.HTTP_200_OK)
def get_current_user_info(
    current_user: UserResponse = Depends(get_current_user),
) -> UserResponse:
    """Get current authenticated user info"""
    return current_user
