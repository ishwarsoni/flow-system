"""Shared rate limiter instance for the entire application.

Import `limiter` from this module in both main.py and routers.
This ensures all rate-limit decorators share the same backing store
and configuration.
"""
from slowapi import Limiter
from slowapi.util import get_remote_address
from app.config import get_settings

settings = get_settings()

limiter = Limiter(
    key_func=get_remote_address,
    default_limits=[settings.GLOBAL_RATE_LIMIT],
)
