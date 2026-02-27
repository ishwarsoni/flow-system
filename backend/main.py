import sqlite3
import logging
import time

from fastapi import FastAPI, Request  # type: ignore
from fastapi.responses import JSONResponse  # type: ignore
from fastapi.middleware.cors import CORSMiddleware  # type: ignore
from slowapi import Limiter, _rate_limit_exceeded_handler  # type: ignore
from slowapi.util import get_remote_address  # type: ignore
from slowapi.errors import RateLimitExceeded  # type: ignore

from app.config import get_settings  # type: ignore
from app.core.exceptions import FLOWException  # type: ignore
from app.core.alerting import error_tracker, uptime_monitor  # type: ignore
from app.routers import auth  # type: ignore
from app.routers.quests import router as quests_router  # type: ignore
from app.routers.player import router as player_router  # type: ignore
from app.routers.analytics import analytics_router  # type: ignore

logger = logging.getLogger(__name__)
settings = get_settings()

# ── Rate Limiter (per-IP) ─────────────────────────────────────────────────
limiter = Limiter(key_func=get_remote_address, default_limits=[settings.GLOBAL_RATE_LIMIT])

app = FastAPI(
    title=settings.APP_NAME,
    debug=settings.DEBUG,
    version="2.0.0",
    description="FLOW RPG — Life Operating System",
    # Disable interactive API docs in production
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
    openapi_url="/openapi.json" if settings.DEBUG else None,
)

# Attach rate limiter
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


# ─── Auto-migrate database on startup ───
def _get_columns(cursor: sqlite3.Cursor, table: str) -> set:
    cursor.execute(f"PRAGMA table_info({table})")
    return {row[1] for row in cursor.fetchall()}


def _auto_migrate():
    """Add missing RPG columns to existing tables."""
    db_url = settings.DATABASE_URL
    # Extract file path from sqlite URL
    if "sqlite" not in db_url:
        logger.info("Non-SQLite DB — skipping auto-migration")
        return

    db_path = db_url.split("///")[-1]
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Check if user_stats table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='user_stats'")
        if not cursor.fetchone():
            logger.info("user_stats table doesn't exist yet — skipping migration")
            conn.close()
            return

        existing = _get_columns(cursor, "user_stats")
        new_cols = {
            "rank":              ("VARCHAR(10)", "'E'"),
            "skill_points":      ("INTEGER", "0"),
            "hp_current":        ("INTEGER", "100"),
            "hp_max":            ("INTEGER", "100"),
            "mp_current":        ("INTEGER", "50"),
            "mp_max":            ("INTEGER", "50"),
            "strength":          ("FLOAT", "10.0"),
            "intelligence":      ("FLOAT", "10.0"),
            "vitality":          ("FLOAT", "10.0"),
            "charisma":          ("FLOAT", "10.0"),
            "mana":              ("FLOAT", "10.0"),
            "coins":             ("INTEGER", "0"),
            "reputation":        ("INTEGER", "0"),
            "current_title":     ("VARCHAR(100)", "'Novice'"),
            "fatigue":           ("FLOAT", "0.0"),
            "streak_days":       ("INTEGER", "0"),
            "longest_streak":    ("INTEGER", "0"),
            "last_active_at":    ("DATETIME", "NULL"),
            "punishment_active": ("INTEGER", "0"),
        }

        migrated = False
        for col, (col_type, default) in new_cols.items():
            if col not in existing:
                cursor.execute(f"ALTER TABLE user_stats ADD COLUMN {col} {col_type} DEFAULT {default}")
                logger.info(f"✅ Added user_stats.{col}")
                migrated = True

        # Create quests table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS quests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL REFERENCES users(id),
                title VARCHAR(200) NOT NULL,
                description TEXT,
                quest_type VARCHAR(20) DEFAULT 'custom',
                difficulty VARCHAR(20) DEFAULT 'easy',
                primary_stat VARCHAR(20),
                base_xp_reward INTEGER DEFAULT 100,
                coin_reward INTEGER DEFAULT 10,
                stat_rewards JSON,
                item_rewards JSON,
                bonus_skill_points INTEGER DEFAULT 0,
                penalty_xp INTEGER DEFAULT 0,
                penalty_hp INTEGER DEFAULT 0,
                penalty_stat JSON,
                generates_penalty_quest BOOLEAN DEFAULT 0,
                mp_cost INTEGER DEFAULT 0,
                time_limit_minutes INTEGER,
                expires_at DATETIME,
                deadline DATETIME,
                status VARCHAR(20) DEFAULT 'pending',
                auto_generated BOOLEAN DEFAULT 0,
                completed_at DATETIME,
                failed_at DATETIME,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Add missing xp_history columns
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='xp_history'")
        if cursor.fetchone():
            xp_cols = _get_columns(cursor, "xp_history")
            for col, (col_type, default) in {
                "coin_amount": ("INTEGER", "0"),
                "quest_id": ("INTEGER", "NULL"),
                "stat_deltas": ("JSON", "NULL"),
                "level_at_time": ("INTEGER", "NULL"),
                "rank_at_time": ("VARCHAR(10)", "NULL"),
            }.items():
                if col not in xp_cols:
                    cursor.execute(f"ALTER TABLE xp_history ADD COLUMN {col} {col_type} DEFAULT {default}")
                    logger.info(f"✅ Added xp_history.{col}")
                    migrated = True

        conn.commit()

        if migrated:
            logger.info("🎮 RPG database migration complete!")
        else:
            logger.info("📋 Database schema is up to date")

        # ─── Inventory Tables (Phase 4) ───
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='items'")
        if not cursor.fetchone():
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS items (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    slug VARCHAR(50) NOT NULL UNIQUE,
                    name VARCHAR(100) NOT NULL,
                    description TEXT,
                    item_type VARCHAR(20) DEFAULT 'consumable',
                    rarity VARCHAR(20) DEFAULT 'common',
                    effect JSON,
                    icon VARCHAR(50),
                    max_stack INTEGER DEFAULT 99,
                    is_tradable BOOLEAN DEFAULT 1,
                    coin_value INTEGER DEFAULT 10,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            logger.info("✅ Created items table")
            
            # Seed default items
            from app.models.inventory import ItemType  # type: ignore
            items = [
                ("potion_hp_small", "Small Health Potion", "Restores 20 HP", "consumable", "common", '{"type": "heal_hp", "value": 20}', "🍷", 50),
                ("potion_mp_small", "Small Mana Potion", "Restores 15 MP", "consumable", "common", '{"type": "restore_mp", "value": 15}', "🧪", 50),
                ("potion_fatigue", "Energy Drink", "Reduces fatigue by 10%", "consumable", "uncommon", '{"type": "reduce_fatigue", "value": 10}', "⚡", 100),
                ("xp_tome_small", "Novice XP Tome", "Grant 500 XP instantly", "consumable", "rare", '{"type": "xp_boost", "value": 500}', "📖", 250)
            ]
            cursor.executemany(
                "INSERT OR IGNORE INTO items (slug, name, description, item_type, rarity, effect, icon, coin_value) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                items
            )
            logger.info("🌱 Seeded default items")

        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='player_inventory'")
        if not cursor.fetchone():
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS player_inventory (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL REFERENCES users(id),
                    item_id INTEGER NOT NULL REFERENCES items(id),
                    quantity INTEGER DEFAULT 1,
                    acquired_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            logger.info("✅ Created player_inventory table")

        conn.commit()
        conn.close()

    except Exception as e:
        logger.error(f"Migration error: {e}")


# Run migration on import (before first request)
# _auto_migrate()  # Disable auto-migration to prevent DB locks on reload
pass


# ── CORS — use settings-defined origins (NO wildcard *) ────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
    expose_headers=["X-RateLimit-Limit", "X-RateLimit-Remaining", "X-RateLimit-Reset"],
)


# ── Security Headers + Request Size Guard ──────────────────────────────────
@app.middleware("http")
async def security_middleware(request: Request, call_next):
    # Reject oversized request bodies
    content_length = request.headers.get("content-length")
    if content_length and int(content_length) > settings.MAX_REQUEST_BODY_BYTES:
        return JSONResponse(status_code=413, content={"detail": "Request body too large"})

    start_time = time.time()
    response = await call_next(request)
    duration = time.time() - start_time

    # Log slow requests (>2s)
    if duration > 2.0:
        logger.warning(
            "SLOW REQUEST | %s %s | %.2fs | ip=%s",
            request.method, request.url.path, duration,
            request.client.host if request.client else "unknown",
        )

    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "0"
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
    if "server" in response.headers:
        del response.headers["server"]

    return response


# Global exception handlers
@app.exception_handler(FLOWException)
async def flow_exception_handler(request: Request, exc: FLOWException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.message},
    )

@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    """Never leak stack traces to the client in production."""
    if settings.DEBUG:
        raise exc
    logger.exception("Unhandled exception on %s %s", request.method, request.url.path)
    error_tracker.record_5xx(request.url.path, 500, str(exc)[:200])
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
    )


# ─── Routers ───
from app.routers import shop as shop_router  # type: ignore
from app.routers import adaptive_quests  # type: ignore
from app.routers import domains as domains_router  # type: ignore
from app.routers import verification as verification_router  # type: ignore
from app.routers import ai as ai_router  # type: ignore
from app.routers import coach as coach_router  # type: ignore

app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(quests_router, prefix="/api/quests", tags=["quests"])
app.include_router(player_router, prefix="/api/player", tags=["player"])
app.include_router(analytics_router, prefix="/api/analytics", tags=["analytics"])
app.include_router(shop_router.router, prefix="/api/shop", tags=["shop"])
app.include_router(adaptive_quests.router, prefix="/api", tags=["adaptive-quests"])
app.include_router(domains_router.router, prefix="/api", tags=["domains"])
app.include_router(verification_router.router, prefix="/api", tags=["Verification"])
app.include_router(ai_router.router, prefix="/api/ai", tags=["ai"])
app.include_router(coach_router.router, prefix="/api/coach", tags=["AI Coach"])


@app.get("/")
def root():
    if settings.DEBUG:
        return {"message": f"{settings.APP_NAME} RPG backend running", "version": "2.0.0"}
    return {"status": "ok"}


@app.get("/health")
def health():
    """Deep health check — verifies DB and Redis connectivity."""
    result = {"status": "healthy"}

    # Check database
    try:
        from app.db.database import SessionLocal
        from sqlalchemy import text
        db = SessionLocal()
        db.execute(text("SELECT 1"))
        db.close()
        result["db"] = "connected"
    except Exception as e:
        result["status"] = "degraded"
        result["db"] = f"error: {str(e)[:100]}"

    # Check Redis
    try:
        from app.core.token_blacklist import check_redis_health
        result["redis"] = check_redis_health()
    except Exception as e:
        result["redis"] = {"status": "error", "detail": str(e)[:100]}

    # 5xx error stats
    result["errors"] = error_tracker.get_stats()

    return result


@app.on_event("startup")
def start_monitoring():
    """Start background uptime monitor on app startup."""
    uptime_monitor.start()
    logger.info("5xx alerting and uptime monitoring active")
