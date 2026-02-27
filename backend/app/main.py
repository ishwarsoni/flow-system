from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse, PlainTextResponse
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
import logging
import time

from app.config import get_settings
from app.core.exceptions import FLOWException
from app.core.alerting import error_tracker, uptime_monitor
from app.routers import auth
from app.routers import player, quests
from app.routers import ai as ai_router
from app.routers.analytics import analytics_router, admin_router
from app.routers import adaptive_quests
from app.routers import domains as domains_router
from app.routers import verification as verification_router
from app.routers import coach as coach_router

logger = logging.getLogger(__name__)

# ── Settings ───────────────────────────────────────────────────────────────
settings = get_settings()

# ── Rate Limiter (per-IP) ─────────────────────────────────────────────────
limiter = Limiter(key_func=get_remote_address, default_limits=[settings.GLOBAL_RATE_LIMIT])

# ── FastAPI app ────────────────────────────────────────────────────────────
app = FastAPI(
    title=settings.APP_NAME,
    debug=settings.DEBUG,
    version="1.0.0",
    # Disable interactive docs in production — they expose your full API surface
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
    openapi_url="/openapi.json" if settings.DEBUG else None,
)

# Attach limiter state
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# ── CORS ───────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
    expose_headers=["X-RateLimit-Limit", "X-RateLimit-Remaining", "X-RateLimit-Reset"],
)


# ── Security Headers Middleware ────────────────────────────────────────────
@app.middleware("http")
async def security_middleware(request: Request, call_next):
    """
    Production-grade security headers applied to every response.
    Also rejects oversized request bodies early.
    Logs slow requests (>2s).
    """
    # ── Reject oversized bodies ──
    content_length = request.headers.get("content-length")
    if content_length and int(content_length) > settings.MAX_REQUEST_BODY_BYTES:
        return JSONResponse(status_code=413, content={"detail": "Request body too large"})

    start_time = time.time()
    response = await call_next(request)
    duration = time.time() - start_time

    # ── Log slow requests ──
    if duration > 2.0:
        logger.warning(
            "SLOW REQUEST | %s %s | %.2fs | ip=%s",
            request.method, request.url.path, duration,
            request.client.host if request.client else "unknown",
        )

    # ── Security Headers ──
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "0"  # Modern best practice: rely on CSP instead
    response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains; preload"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=(), interest-cohort=()"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self'; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
        "font-src 'self' https://fonts.gstatic.com; "
        "img-src 'self' data:; "
        "connect-src 'self'; "
        "frame-ancestors 'none'; "
        "base-uri 'self'; "
        "form-action 'self';"
    )
    response.headers["X-Permitted-Cross-Domain-Policies"] = "none"
    # Remove server identity header if present
    if "server" in response.headers:
        del response.headers["server"]

    return response


# ── Global Exception Handlers ──────────────────────────────────────────────
@app.exception_handler(FLOWException)
async def flow_exception_handler(request: Request, exc: FLOWException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.message},
    )

@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    """Catch-all: never leak stack traces to the client in production."""
    if settings.DEBUG:
        raise exc  # re-raise in dev so we see the full traceback
    logger.exception("5XX | %s %s | %s", request.method, request.url.path, str(exc)[:200])
    # Track for alerting
    error_tracker.record_5xx(request.url.path, 500, str(exc)[:200])
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
    )


# ── Routers ────────────────────────────────────────────────────────────────
app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(player.router, prefix="/api/player", tags=["player"])
app.include_router(quests.router, prefix="/api/quests", tags=["quests"])
app.include_router(analytics_router, prefix="/api/analytics", tags=["analytics"])
app.include_router(admin_router, prefix="/api/admin", tags=["admin"])
app.include_router(ai_router.router, prefix="/api/ai", tags=["ai"])
app.include_router(adaptive_quests.router, prefix="/api", tags=["adaptive-quests"])
app.include_router(domains_router.router, prefix="/api", tags=["domains"])
app.include_router(verification_router.router, prefix="/api", tags=["Verification"])
app.include_router(coach_router.router, prefix="/api/coach", tags=["AI Coach"])


@app.get("/")
def root():
    # Never leak version info in production
    if settings.DEBUG:
        return {"message": f"{settings.APP_NAME} backend running", "version": "1.0.0"}
    return {"status": "ok"}


@app.get("/health")
def health_check():
    """Deep health check — verifies DB and Redis connectivity."""
    health = {"status": "healthy"}

    # Check database
    try:
        from app.db.database import SessionLocal
        from sqlalchemy import text
        db = SessionLocal()
        db.execute(text("SELECT 1"))
        db.close()
        health["db"] = "connected"
    except Exception as e:
        health["status"] = "degraded"
        health["db"] = f"error: {str(e)[:100]}"

    # Check Redis
    try:
        from app.core.token_blacklist import check_redis_health
        health["redis"] = check_redis_health()
    except Exception as e:
        health["redis"] = {"status": "error", "detail": str(e)[:100]}

    # 5xx error stats
    health["errors"] = error_tracker.get_stats()

    return health


@app.on_event("startup")
def start_monitoring():
    """Start background uptime monitor and quest expiry scheduler on app startup."""
    uptime_monitor.start()
    logger.info("5xx alerting and uptime monitoring active")

    # Background scheduler: auto-fail quests that exceed 24-hour window
    from app.services.quest_expiry_scheduler import start_quest_expiry_scheduler
    start_quest_expiry_scheduler()


@app.on_event("shutdown")
def stop_background_tasks():
    """Stop background tasks on app shutdown."""
    from app.services.quest_expiry_scheduler import stop_quest_expiry_scheduler
    stop_quest_expiry_scheduler()
    logger.info("Background tasks stopped")

