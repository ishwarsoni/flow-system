"""Structured logging and monitoring configuration.

Sets up:
- File logging (rotated daily, 30-day retention)
- Console logging (for Docker/systemd)
- Error log (errors only)
- Slow request tracking
- Optional Sentry integration

Usage:
    from app.core.monitoring import setup_logging
    setup_logging()  # Call once at startup
"""

from __future__ import annotations

import logging
import logging.handlers
import os
import sys
from pathlib import Path
from typing import Optional

from app.config import get_settings


def setup_logging(log_dir: Optional[str] = None) -> None:
    """Configure production-grade logging.
    
    Args:
        log_dir: Directory for log files. Defaults to ./logs/
    """
    settings = get_settings()
    
    if not log_dir:
        log_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "logs")
    Path(log_dir).mkdir(parents=True, exist_ok=True)

    # ── Log format ────────────────────────────────────────────────────────
    detailed_fmt = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)s:%(lineno)d | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    json_fmt = logging.Formatter(
        '{"ts":"%(asctime)s","level":"%(levelname)s","logger":"%(name)s","line":%(lineno)d,"msg":"%(message)s"}',
        datefmt="%Y-%m-%dT%H:%M:%S",
    )

    root = logging.getLogger()
    root.setLevel(logging.DEBUG if settings.DEBUG else logging.INFO)

    # Clear existing handlers to avoid duplicates on reload
    root.handlers.clear()

    # ── Console handler (stdout) ──────────────────────────────────────────
    console = logging.StreamHandler(sys.stdout)
    console.setLevel(logging.DEBUG if settings.DEBUG else logging.INFO)
    console.setFormatter(detailed_fmt)
    root.addHandler(console)

    # ── Main log file (rotated daily, 30 days) ───────────────────────────
    main_log = logging.handlers.TimedRotatingFileHandler(
        os.path.join(log_dir, "flow.log"),
        when="midnight",
        interval=1,
        backupCount=30,
        encoding="utf-8",
    )
    main_log.setLevel(logging.INFO)
    main_log.setFormatter(detailed_fmt)
    root.addHandler(main_log)

    # ── Error log (errors only) ──────────────────────────────────────────
    error_log = logging.handlers.TimedRotatingFileHandler(
        os.path.join(log_dir, "flow_errors.log"),
        when="midnight",
        interval=1,
        backupCount=90,
        encoding="utf-8",
    )
    error_log.setLevel(logging.ERROR)
    error_log.setFormatter(detailed_fmt)
    root.addHandler(error_log)

    # ── Security/audit log ───────────────────────────────────────────────
    security_logger = logging.getLogger("app.services.audit_service")
    security_handler = logging.handlers.TimedRotatingFileHandler(
        os.path.join(log_dir, "flow_security.log"),
        when="midnight",
        interval=1,
        backupCount=90,
        encoding="utf-8",
    )
    security_handler.setLevel(logging.INFO)
    security_handler.setFormatter(json_fmt)
    security_logger.addHandler(security_handler)

    # ── Suppress noisy loggers ───────────────────────────────────────────
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(
        logging.INFO if settings.DEBUG else logging.WARNING
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)

    logging.info("Logging initialized — dir=%s debug=%s", log_dir, settings.DEBUG)


def setup_sentry(dsn: Optional[str] = None) -> None:
    """Optional Sentry integration for error tracking.
    
    Set SENTRY_DSN in .env to enable.
    """
    if not dsn:
        settings = get_settings()
        dsn = getattr(settings, "SENTRY_DSN", "")
    
    if not dsn:
        return

    try:
        import sentry_sdk
        from sentry_sdk.integrations.fastapi import FastApiIntegration
        from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration

        sentry_sdk.init(
            dsn=dsn,
            integrations=[
                FastApiIntegration(transaction_style="endpoint"),
                SqlalchemyIntegration(),
            ],
            traces_sample_rate=0.1,  # 10% of transactions
            profiles_sample_rate=0.1,
            send_default_pii=False,
            environment="production" if not get_settings().DEBUG else "development",
        )
        logging.info("Sentry initialized")
    except ImportError:
        logging.info("sentry-sdk not installed — Sentry disabled")
    except Exception as e:
        logging.warning("Sentry init failed: %s", e)
