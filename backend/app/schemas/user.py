from pydantic import BaseModel, EmailStr, Field, field_validator
from datetime import datetime
from typing import Literal
import re


class UserRegisterRequest(BaseModel):
    """User registration request schema"""
    username: str = Field(..., min_length=3, max_length=50)
    email: EmailStr
    password: str = Field(..., min_length=8, description="Must be at least 8 characters")
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
    
    @field_validator("username")
    @classmethod
    def validate_username(cls, v: str) -> str:
        """Validate username: alphanumeric and underscores only"""
        if not re.match(r"^[a-zA-Z0-9_-]+$", v):
            raise ValueError("Username can only contain letters, numbers, underscores, and hyphens")
        return v
    
    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        """Validate password strength"""
        if not any(c.isupper() for c in v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not any(c.isdigit() for c in v):
            raise ValueError("Password must contain at least one digit")
        return v
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "username": "john_doe",
                "email": "john@example.com",
                "password": "SecurePass123",
                "starting_difficulty": "normal"
            }
        }
    }


class UserLoginRequest(BaseModel):
    """User login request schema"""
    email: EmailStr
    password: str
    
    model_config = {
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
    token_type: str = "bearer"
    user: UserResponse


class TokenPayload(BaseModel):
    """JWT token payload schema"""
    sub: int  # user_id
    exp: int  # Unix timestamp
    iat: int  # Issued at timestamp
