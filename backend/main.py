import sqlite3
import logging

from fastapi import FastAPI, Request  # type: ignore
from fastapi.responses import JSONResponse  # type: ignore
from fastapi.middleware.cors import CORSMiddleware  # type: ignore

from app.config import get_settings  # type: ignore
from app.core.exceptions import FLOWException  # type: ignore
from app.routers import auth  # type: ignore
from app.routers.quests import router as quests_router  # type: ignore
from app.routers.player import router as player_router  # type: ignore
from app.routers.analytics import analytics_router  # type: ignore

logger = logging.getLogger(__name__)
settings = get_settings()

app = FastAPI(
    title=settings.APP_NAME,
    debug=settings.DEBUG,
    version="2.0.0",
    description="FLOW RPG — Life Operating System",
)


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


# CORS — permissive for development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Security headers
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Strict-Transport-Security"] = "max-age=31536000"
    return response


# Global exception handler
@app.exception_handler(FLOWException)
async def flow_exception_handler(request: Request, exc: FLOWException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.message},
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
    return {"message": f"{settings.APP_NAME} RPG backend running", "version": "2.0.0"}


@app.get("/health")
def health():
    return {"status": "healthy"}
