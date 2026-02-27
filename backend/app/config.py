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

    # Monitoring (optional)
    SENTRY_DSN: str = ""

    @field_validator("DATABASE_URL")
    @classmethod
    def resolve_sqlite_path(cls, v: str) -> str:
        """Resolve relative SQLite paths relative to the backend directory,
        not the process CWD. This makes `sqlite:///./flow.db` always point
        to `<backend>/flow.db` regardless of where uvicorn is launched from."""
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
        """Enforce mandatory config in production (DEBUG=False)."""
        if not self.DEBUG:
            if not self.REDIS_URL:
                raise ValueError(
                    "REDIS_URL is required in production (DEBUG=False). "
                    "Token blacklist, session management, and rate limiting require Redis. "
                    "Set REDIS_URL=redis://127.0.0.1:6379/0 in your .env file."
                )
            # Block localhost CORS in production — these should be replaced
            # with real domain(s) before going live.
            localhost_origins = [o for o in self.ALLOWED_ORIGINS if "localhost" in o or "127.0.0.1" in o or "192.168." in o]
            if localhost_origins and len(localhost_origins) == len(self.ALLOWED_ORIGINS):
                raise ValueError(
                    "ALLOWED_ORIGINS contains ONLY localhost/private-IP entries in production. "
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
