from pydantic import BaseModel, EmailStr, Field, field_validator
from datetime import datetime
from typing import Literal
import re


class UserRegisterRequest(BaseModel):
    """User registration request schema"""
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128, description="Must be 8-128 characters")
    hunter_name: str = Field(default="Hunter", min_length=3, max_length=20, description="Hunter display name (3-20 letters only)")
    # Player picks their starting difficulty at sign-up.
    # hard  → starts at level 13 (C-Rank)
    # extreme → starts at level 25 (B-Rank)
    starting_difficulty: Literal["beginner", "normal", "hard", "extreme"] = "normal"
    
    @field_validator("hunter_name")
    @classmethod
    def validate_hunter_name(cls, v: str) -> str:
        v = v.strip()
        if not re.match(r"^[a-zA-Z]+$", v):
            raise ValueError("Hunter name must contain only letters (a-z, A-Z)")
        return v
    
    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        """Enforce strong password policy."""
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        if not any(c.isupper() for c in v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not any(c.islower() for c in v):
            raise ValueError("Password must contain at least one lowercase letter")
        if not any(c.isdigit() for c in v):
            raise ValueError("Password must contain at least one digit")
        if not any(c in "!@#$%^&*()-_=+[]{}|;:'\",.<>?/`~" for c in v):
            raise ValueError("Password must contain at least one special character")
        return v
    
    model_config = {
        "extra": "forbid",
        "json_schema_extra": {
            "example": {
                "email": "john@example.com",
                "password": "SecurePass123!",
                "hunter_name": "Jinwoo",
                "starting_difficulty": "normal"
            }
        }
    }


class UserLoginRequest(BaseModel):
    """User login request schema"""
    email: EmailStr
    password: str
    
    model_config = {
        "extra": "forbid",
        "json_schema_extra": {
            "example": {
                "email": "john@example.com",
                "password": "securepassword123"
            }
        }
    }


class UserResponse(BaseModel):
    """User response schema (for API responses)"""
    id: int
    username: str
    email: str
    hunter_name: str = "Hunter"
    is_active: bool
    created_at: datetime
    
    model_config = {"from_attributes": True}


class TokenResponse(BaseModel):
    """Token response schema"""
    access_token: str
    refresh_token: str = ""
    token_type: str = "bearer"
    user: UserResponse


class RefreshRequest(BaseModel):
    """Refresh token exchange request"""
    refresh_token: str = Field(..., min_length=10)

    model_config = {"extra": "forbid"}


class TokenPayload(BaseModel):
    """JWT token payload schema"""
    sub: int  # user_id
    exp: int  # Unix timestamp
    iat: int  # Issued at timestamp
