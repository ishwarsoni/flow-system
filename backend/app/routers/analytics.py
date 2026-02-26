"""Analytics and health check API routes — RPG system."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from datetime import datetime, UTC

from app.db.database import get_db
from app.dependencies.auth import get_current_user
from app.models.user import User
from app.services.progression_analytics_service import (
    ProgressionAnalyticsService,
    ProgressionAnalyticsException,
)
from app.schemas.quest import ProgressionOverviewResponse, AnalyticsHistoryResponse
from app.core.exceptions import FLOWException

analytics_router = APIRouter()


@analytics_router.get("/overview", response_model=ProgressionOverviewResponse)
def get_analytics_overview(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Full RPG progression overview — stats, vitals, rank, economy."""
    try:
        progress = ProgressionAnalyticsService.get_user_progress(current_user.id, db)
        return ProgressionOverviewResponse(**progress)
    except ProgressionAnalyticsException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=e.message)
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to fetch progression")


@analytics_router.get("/history", response_model=AnalyticsHistoryResponse)
def get_analytics_history(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """7-day time-series data for charts."""
    try:
        data = ProgressionAnalyticsService.get_user_history(current_user.id, db)
        return AnalyticsHistoryResponse(**data)
    except ProgressionAnalyticsException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=e.message)
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to fetch analytics history")


@analytics_router.get("/streaks")
def get_streaks(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get current and longest streak."""
    try:
        current, longest = ProgressionAnalyticsService._calculate_streak(current_user.id, db)
        return {"current_streak_days": current, "longest_streak_days": longest}
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to fetch streaks")


@analytics_router.get("/stats")
def get_seven_day_stats(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Last 7 days summary stats."""
    try:
        xp, completed, failed = ProgressionAnalyticsService._get_7day_stats(current_user.id, db)
        total = completed + failed
        rate = (failed / total * 100) if total > 0 else 0.0
        return {
            "xp_earned_7days": xp,
            "quests_completed_7days": completed,
            "quests_failed_7days": failed,
            "failure_rate_percent": round(rate, 2),
        }
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to fetch 7-day stats")


@analytics_router.get("/health")
def health_check():
    return {"status": "healthy", "timestamp": datetime.now(UTC).isoformat()}


@analytics_router.get("/metrics")
def get_metrics(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """System-wide metrics."""
    try:
        from app.models.user_stats import UserStats
        from app.models.daily_progress import DailyProgress
        from sqlalchemy import func

        total_users = db.query(func.count(User.id)).scalar() or 0
        avg_level = db.query(func.avg(UserStats.level)).scalar() or 1.0
        total_completed = db.query(func.sum(DailyProgress.tasks_completed_today)).scalar() or 0
        total_failed = db.query(func.sum(DailyProgress.tasks_failed_today)).scalar() or 0

        return {
            "total_users": int(total_users),
            "total_quests_completed": int(total_completed),
            "total_quests_failed": int(total_failed),
            "avg_user_level": float(avg_level),
        }
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to fetch metrics")


admin_router = APIRouter()


@admin_router.get("/health")
def admin_health():
    return {"status": "healthy", "timestamp": datetime.now(UTC).isoformat()}
