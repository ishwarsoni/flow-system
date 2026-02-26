from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.core.exceptions import FLOWException
from app.routers import auth
from app.routers import player, quests
from app.routers import ai as ai_router
from app.routers.analytics import analytics_router, admin_router
from app.routers import adaptive_quests
from app.routers import domains as domains_router
from app.routers import verification as verification_router
from app.routers import coach as coach_router

# Initialize FastAPI app
settings = get_settings()
app = FastAPI(
    title=settings.APP_NAME,
    debug=settings.DEBUG,
    version="1.0.0",
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
)


# Add security headers middleware
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    """Add security headers to all responses"""
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response


# Global exception handler for custom exceptions
@app.exception_handler(FLOWException)
async def flow_exception_handler(request: Request, exc: FLOWException):
    """Handle custom FLOW exceptions"""
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.message},
    )

# Include routers
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
    """Root endpoint - returns app info"""
    return {"message": f"{settings.APP_NAME} backend running", "version": "1.0.0"}


@app.get("/health")
def legacy_health():
    """Legacy health endpoint (use /api/admin/health for new format)"""
    return {"status": "healthy"}

