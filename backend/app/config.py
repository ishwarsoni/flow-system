from pydantic_settings import BaseSettings
from pydantic import field_validator
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings from environment variables"""
    
    # Database
    DATABASE_URL: str
    
    # JWT
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    
    # App
    APP_NAME: str = "FLOW"
    DEBUG: bool = False
    
    # CORS
    ALLOWED_ORIGINS: list[str] = [
        "http://localhost:3000",
        "http://localhost:5173",
        "http://localhost:8000",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:8000",
        "http://192.168.56.1:3000",
        "http://192.168.56.1:5173",
        "http://192.168.56.1:8000",
    ]
    
    # AI (optional — leave blank to use built-in rule-based engine)
    OPENAI_API_KEY: str = ""
    GROQ_API_KEY: str = ""

    @field_validator("SECRET_KEY")
    @classmethod
    def validate_secret_key(cls, v: str) -> str:
        """Ensure SECRET_KEY is at least 32 characters (256-bit security)"""
        if len(v) < 32:
            raise ValueError(
                "SECRET_KEY must be at least 32 characters long (256-bit). "
                "Generate with: python -c \"import secrets; print(secrets.token_urlsafe(32))\""
            )
        return v

    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = "ignore"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
