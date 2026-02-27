from pathlib import Path
from pydantic_settings import BaseSettings
from pydantic import field_validator, model_validator
from functools import lru_cache

_ENV_FILE = Path(__file__).resolve().parent.parent / ".env"
_BACKEND_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    """Application settings from environment variables.

    Production (DEBUG=False) enforces:
    - SECRET_KEY ≥ 32 chars
    - DATABASE_URL set
    - REDIS_URL set (no memory fallback)
    - ALLOWED_ORIGINS explicitly configured
    Missing any of these will crash at startup — by design.
    """

    # Database
    DATABASE_URL: str

    # JWT
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # App
    APP_NAME: str = "FLOW"
    DEBUG: bool = False

    # Redis (token blacklist) — REQUIRED in production
    REDIS_URL: str = ""  # e.g. redis://127.0.0.1:6379/0

    # Security
    LOGIN_RATE_LIMIT: str = "5/minute"       # max login attempts per IP
    REGISTER_RATE_LIMIT: str = "3/minute"    # max registrations per IP
    GLOBAL_RATE_LIMIT: str = "120/minute"    # max API calls per IP
    MAX_REQUEST_BODY_BYTES: int = 1_048_576  # 1 MB

    # Account lockout
    LOCKOUT_THRESHOLD: int = 10              # failed attempts before lockout
    LOCKOUT_WINDOW_MINUTES: int = 15         # window to count attempts
    LOCKOUT_DURATION_MINUTES: int = 15       # base lockout duration
    LOCKOUT_MAX_DURATION_MINUTES: int = 1440 # max progressive lockout (24h)

    # Secret rotation (days)
    SECRET_ROTATION_DAYS: int = 90

    # CORS — accepts JSON array, comma-separated string, or single URL from env var
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
        "https://flow-system-1.onrender.com",
        "https://flow-wot6.onrender.com",
    ]

    @field_validator("ALLOWED_ORIGINS", mode="before")
    @classmethod
    def parse_allowed_origins(cls, v):
        """Handle ALLOWED_ORIGINS in any format:
        - JSON array: '["https://a.com","https://b.com"]'
        - Comma-separated: 'https://a.com,https://b.com'
        - Single URL: 'https://a.com'
        - Python list (already parsed)
        Always includes the Render deployment URLs.
        """
        import json as _json

        # Already a list
        if isinstance(v, list):
            origins = v
        elif isinstance(v, str):
            v = v.strip()
            # Try JSON parse first
            if v.startswith("["):
                try:
                    origins = _json.loads(v)
                except Exception:
                    origins = [s.strip() for s in v.split(",") if s.strip()]
            else:
                # Comma-separated or single URL
                origins = [s.strip() for s in v.split(",") if s.strip()]
        else:
            origins = []

        # Always ensure Render URLs are present
        required = [
            "https://flow-system-1.onrender.com",
            "https://flow-wot6.onrender.com",
        ]
        for url in required:
            if url not in origins:
                origins.append(url)

        return origins

    # AI (optional — leave blank to use built-in rule-based engine)
    OPENAI_API_KEY: str = ""
    GROQ_API_KEY: str = ""

    # Monitoring (optional)
    SENTRY_DSN: str = ""

    @field_validator("DATABASE_URL")
    @classmethod
    def resolve_database_url(cls, v: str) -> str:
        """Fix database URL for compatibility.
        
        1. Render (and Heroku) provide postgres:// but SQLAlchemy 2.x requires postgresql://
        2. Resolve relative SQLite paths relative to the backend directory.
        """
        # Fix Render/Heroku postgres:// → postgresql://
        if v.startswith("postgres://"):
            v = v.replace("postgres://", "postgresql://", 1)

        # Resolve relative SQLite paths
        if v.startswith("sqlite:///./") or v.startswith("sqlite:///flow"):
            relative = v.replace("sqlite:///./", "").replace("sqlite:///", "")
            absolute = _BACKEND_DIR / relative
            return f"sqlite:///{absolute}"
        return v

    @field_validator("SECRET_KEY")
    @classmethod
    def validate_secret_key(cls, v: str) -> str:
        """Ensure SECRET_KEY is at least 32 characters (256-bit security)."""
        if len(v) < 32:
            raise ValueError(
                "SECRET_KEY must be at least 32 characters long (256-bit). "
                "Generate with: python -c \"import secrets; print(secrets.token_urlsafe(48))\""
            )
        return v

    @model_validator(mode="after")
    def validate_production_requirements(self) -> "Settings":
        """Warn about missing config in production (DEBUG=False).
        Non-fatal so the app can still start on platforms like Render
        while the user provisions Redis / sets ALLOWED_ORIGINS.
        """
        import logging as _logging
        _log = _logging.getLogger("app.config")

        if not self.DEBUG:
            if not self.REDIS_URL:
                _log.warning(
                    "⚠️  REDIS_URL is not set in production (DEBUG=False). "
                    "Token blacklist will use in-memory store — NOT safe for multi-instance. "
                    "Set REDIS_URL for production-grade token management."
                )
            # Warn about localhost CORS in production
            localhost_origins = [o for o in self.ALLOWED_ORIGINS if "localhost" in o or "127.0.0.1" in o or "192.168." in o]
            if localhost_origins and len(localhost_origins) == len(self.ALLOWED_ORIGINS):
                _log.warning(
                    "⚠️  ALLOWED_ORIGINS contains ONLY localhost/private-IP entries in production. "
                    "Set ALLOWED_ORIGINS to your real domain(s) in .env (e.g. https://yourdomain.com)."
                )
        return self

    class Config:
        env_file = str(_ENV_FILE)
        case_sensitive = True
        extra = "ignore"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
