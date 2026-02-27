"""5xx Error Alerting & Uptime Monitoring.

Tracks 5xx errors with a sliding window. Fires alerts when threshold is breached.
Also provides a periodic health-check poller that logs degraded state.

Alert channels:
- File log (always) — flow_alerts.log
- Stderr (always) — for systemd journal
- Optional: webhook URL (set ALERT_WEBHOOK_URL in .env)

Usage:
    from app.core.alerting import error_tracker, check_uptime
    error_tracker.record_5xx(path, status_code)   # called from middleware
    check_uptime()                                 # called from background task
"""

from __future__ import annotations

import logging
import logging.handlers
import os
import time
import threading
from collections import deque
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# ── Alert logger (separate file for ops) ──────────────────────────────────────
_alert_logger: Optional[logging.Logger] = None


def _get_alert_logger() -> logging.Logger:
    global _alert_logger
    if _alert_logger is not None:
        return _alert_logger

    _alert_logger = logging.getLogger("flow.alerts")
    _alert_logger.setLevel(logging.WARNING)

    # Dedicated alert log file
    log_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "logs"
    )
    Path(log_dir).mkdir(parents=True, exist_ok=True)

    fh = logging.handlers.TimedRotatingFileHandler(
        os.path.join(log_dir, "flow_alerts.log"),
        when="midnight",
        backupCount=90,
        encoding="utf-8",
    )
    fmt = logging.Formatter(
        '{"ts":"%(asctime)s","level":"%(levelname)s","msg":"%(message)s"}',
        datefmt="%Y-%m-%dT%H:%M:%S",
    )
    fh.setFormatter(fmt)
    _alert_logger.addHandler(fh)

    # Also stderr for systemd journal
    sh = logging.StreamHandler()
    sh.setLevel(logging.WARNING)
    sh.setFormatter(fmt)
    _alert_logger.addHandler(sh)

    return _alert_logger


# ── 5xx Error Tracker ─────────────────────────────────────────────────────────

class ErrorTracker:
    """Sliding-window 5xx counter with threshold alerting.

    Parameters (from env or defaults):
        ALERT_5XX_THRESHOLD:  Max 5xx in window before alert (default 10)
        ALERT_5XX_WINDOW_SEC: Window size in seconds (default 300 = 5 min)
        ALERT_COOLDOWN_SEC:   Min seconds between repeated alerts (default 600)
        ALERT_WEBHOOK_URL:    Optional webhook for external alerting
    """

    def __init__(self):
        self._errors: deque = deque()  # (timestamp, path, status)
        self._lock = threading.Lock()
        self._last_alert_time: float = 0.0

        # Config (loaded lazily)
        self._threshold: Optional[int] = None
        self._window: Optional[int] = None
        self._cooldown: Optional[int] = None
        self._webhook_url: Optional[str] = None
        self._configured = False

    def _load_config(self):
        if self._configured:
            return
        self._threshold = int(os.environ.get("ALERT_5XX_THRESHOLD", "10"))
        self._window = int(os.environ.get("ALERT_5XX_WINDOW_SEC", "300"))
        self._cooldown = int(os.environ.get("ALERT_COOLDOWN_SEC", "600"))
        self._webhook_url = os.environ.get("ALERT_WEBHOOK_URL", "")
        self._configured = True

    def record_5xx(self, path: str, status_code: int, detail: str = "") -> None:
        """Record a 5xx error. Triggers alert if threshold breached."""
        self._load_config()
        now = time.time()

        with self._lock:
            self._errors.append((now, path, status_code))
            self._prune(now)
            count = len(self._errors)

        if count >= self._threshold:
            self._maybe_alert(count, path, status_code, detail)

    def get_stats(self) -> dict:
        """Return current 5xx stats for monitoring."""
        self._load_config()
        now = time.time()
        with self._lock:
            self._prune(now)
            count = len(self._errors)
            recent = list(self._errors)[-5:]  # last 5 errors

        return {
            "5xx_count_in_window": count,
            "window_seconds": self._window,
            "threshold": self._threshold,
            "alert_active": count >= self._threshold,
            "recent_errors": [
                {"time": t, "path": p, "status": s} for t, p, s in recent
            ],
        }

    def _prune(self, now: float):
        """Remove errors outside the window. Must hold _lock."""
        cutoff = now - self._window
        while self._errors and self._errors[0][0] < cutoff:
            self._errors.popleft()

    def _maybe_alert(self, count: int, path: str, status_code: int, detail: str):
        """Fire alert if cooldown has elapsed."""
        now = time.time()
        if now - self._last_alert_time < self._cooldown:
            return  # Still in cooldown

        self._last_alert_time = now
        alert_msg = (
            f"5XX ALERT: {count} server errors in last {self._window}s "
            f"(threshold={self._threshold}). Latest: {status_code} on {path}. "
            f"{detail[:200] if detail else ''}"
        )

        alert_log = _get_alert_logger()
        alert_log.critical(alert_msg)
        logger.critical(alert_msg)

        # Fire webhook if configured
        if self._webhook_url:
            self._fire_webhook(alert_msg)

    def _fire_webhook(self, message: str):
        """Best-effort webhook notification (non-blocking)."""
        def _send():
            try:
                import urllib.request
                import json
                data = json.dumps({
                    "text": message,
                    "source": "FLOW-backend",
                    "severity": "critical",
                    "timestamp": time.time(),
                }).encode()
                req = urllib.request.Request(
                    self._webhook_url,
                    data=data,
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                urllib.request.urlopen(req, timeout=5)
            except Exception as e:
                logger.error("Webhook alert failed: %s", e)

        threading.Thread(target=_send, daemon=True).start()


# Singleton
error_tracker = ErrorTracker()


# ── Uptime Monitor ────────────────────────────────────────────────────────────

class UptimeMonitor:
    """Periodic health-check poller. Logs degraded state to alerts.

    Designed to run as a background thread (started at app startup).
    Polls /health internally every UPTIME_CHECK_INTERVAL_SEC (default 60s).
    """

    def __init__(self):
        self._interval = int(os.environ.get("UPTIME_CHECK_INTERVAL_SEC", "60"))
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._consecutive_failures = 0

    def start(self):
        """Start the background health poller."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._poll_loop, daemon=True)
        self._thread.start()
        logger.info("Uptime monitor started (interval=%ds)", self._interval)

    def stop(self):
        self._running = False

    def _poll_loop(self):
        """Poll health endpoint in a loop."""
        # Wait for server to be ready
        time.sleep(5)

        while self._running:
            try:
                self._check_health()
                time.sleep(self._interval)
            except Exception as e:
                logger.error("Uptime monitor error: %s", e)
                time.sleep(self._interval)

    def _check_health(self):
        """Check DB and Redis health internally (no HTTP call needed)."""
        alert_log = _get_alert_logger()
        degraded = False

        # Check DB
        try:
            from app.db.database import SessionLocal
            from sqlalchemy import text
            db = SessionLocal()
            db.execute(text("SELECT 1"))
            db.close()
        except Exception as e:
            degraded = True
            self._consecutive_failures += 1
            msg = f"UPTIME: DB check failed ({self._consecutive_failures} consecutive): {e}"
            alert_log.critical(msg)
            logger.critical(msg)

        # Check Redis
        try:
            from app.core.token_blacklist import check_redis_health
            redis_status = check_redis_health()
            if redis_status.get("status") == "error":
                degraded = True
                self._consecutive_failures += 1
                msg = f"UPTIME: Redis degraded ({self._consecutive_failures} consecutive): {redis_status}"
                alert_log.critical(msg)
                logger.critical(msg)
        except Exception as e:
            degraded = True
            self._consecutive_failures += 1
            msg = f"UPTIME: Redis check failed ({self._consecutive_failures} consecutive): {e}"
            alert_log.critical(msg)
            logger.critical(msg)

        if not degraded:
            if self._consecutive_failures > 0:
                alert_log.warning(
                    "UPTIME: Recovered after %d consecutive failures",
                    self._consecutive_failures,
                )
            self._consecutive_failures = 0


# Singleton
uptime_monitor = UptimeMonitor()
