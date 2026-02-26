"""Pydantic schemas for analytics API responses"""

from pydantic import BaseModel, Field
from datetime import datetime
from typing import Dict, Optional
from typing import List


class StatAnalysisResponse(BaseModel):
    """Response model for stat analysis"""
    strongest_stat: str = Field(..., description="Name of the strongest stat")
    strongest_value: float = Field(..., description="Value of strongest stat")
    weakest_stat: str = Field(..., description="Name of the weakest stat")
    weakest_value: float = Field(..., description="Value of weakest stat")
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "strongest_stat": "discipline",
                "strongest_value": 85.5,
                "weakest_stat": "energy",
                "weakest_value": 42.0,
            }
        }
    }


class ProgressionOverviewResponse(BaseModel):
    """Response model for complete user progression overview"""
    
    # Current Progression
    level: int = Field(..., description="Current user level", ge=1)
    xp_current: int = Field(..., description="XP towards next level", ge=0)
    xp_total_earned: int = Field(..., description="Total XP earned all-time", ge=0)
    xp_to_next_level: int = Field(..., description="XP needed to reach next level", ge=0)
    
    # Stats (RPG stats)
    strength: float = Field(..., description="Strength stat value")
    intelligence: float = Field(..., description="Intelligence stat value")
    vitality: float = Field(..., description="Vitality stat value")
    charisma: float = Field(..., description="Charisma stat value")
    mana: float = Field(..., description="Mana stat value")
    
    # Stat Analysis
    strongest_stat: str = Field(..., description="Name of strongest stat")
    strongest_stat_value: float = Field(..., description="Value of strongest stat")
    weakest_stat: str = Field(..., description="Name of weakest stat")
    weakest_stat_value: float = Field(..., description="Value of weakest stat")
    
    # Today
    xp_earned_today: int = Field(..., description="XP earned today", ge=0)
    quests_completed_today: int = Field(..., description="Quests completed today", ge=0)
    quests_failed_today: int = Field(..., description="Quests failed today", ge=0)
    
    # Last 7 Days
    xp_earned_7days: int = Field(..., description="Total XP earned last 7 days", ge=0)
    quests_completed_7days: int = Field(..., description="Quests completed last 7 days", ge=0)
    quests_failed_7days: int = Field(..., description="Quests failed last 7 days", ge=0)
    
    # Streaks
    current_streak_days: int = Field(..., description="Current consecutive days with completions", ge=0)
    longest_streak_days: int = Field(..., description="Longest streak ever achieved", ge=0)
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "level": 5,
                "xp_current": 250,
                "xp_total_earned": 1500,
                "xp_to_next_level": 150,
                "strength": 15.0,
                "intelligence": 12.0,
                "vitality": 14.0,
                "charisma": 10.0,
                "mana": 11.0,
                "strongest_stat": "strength",
                "strongest_stat_value": 15.0,
                "weakest_stat": "charisma",
                "weakest_stat_value": 10.0,
                "xp_earned_today": 100,
                "quests_completed_today": 3,
                "quests_failed_today": 0,
                "xp_earned_7days": 650,
                "quests_completed_7days": 20,
                "quests_failed_7days": 2,
                "current_streak_days": 7,
                "longest_streak_days": 14,
            }
        }
    }


class StreaksResponse(BaseModel):
    """Response model for streak analysis"""
    current_streak_days: int = Field(..., description="Current consecutive days with task completions", ge=0)
    longest_streak_days: int = Field(..., description="Longest streak ever achieved", ge=0)
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "current_streak_days": 7,
                "longest_streak_days": 21,
            }
        }
    }


class SevenDayStatsResponse(BaseModel):
    """Response model for 7-day statistics"""
    xp_earned_7days: int = Field(..., description="Total XP earned last 7 days", ge=0)
    tasks_completed_7days: int = Field(..., description="Tasks completed last 7 days", ge=0)
    tasks_failed_7days: int = Field(..., description="Tasks failed last 7 days", ge=0)
    failure_rate_percent: float = Field(..., description="Failure rate percentage (0-100)", ge=0.0, le=100.0)
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "xp_earned_7days": 650,
                "tasks_completed_7days": 20,
                "tasks_failed_7days": 2,
                "failure_rate_percent": 9.09,
            }
        }
    }


class HealthResponse(BaseModel):
    """Server health check response"""
    status: str = Field(..., description="Health status")
    timestamp: datetime = Field(..., description="Check timestamp")
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "status": "healthy",
                "timestamp": "2026-02-15T10:30:45.123456+00:00",
            }
        }
    }


class MetricsResponse(BaseModel):
    """Application metrics response"""
    total_users: int = Field(..., description="Total registered users", ge=0)
    total_tasks_completed: int = Field(..., description="Total tasks completed all-time", ge=0)
    total_tasks_failed: int = Field(..., description="Total tasks failed all-time", ge=0)
    avg_user_level: float = Field(..., description="Average user level", ge=1.0)
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "total_users": 42,
                "total_tasks_completed": 1250,
                "total_tasks_failed": 85,
                "avg_user_level": 5.2,
            }
        }
    }


class ErrorResponse(BaseModel):
    """Standard error response"""
    detail: str = Field(..., description="Error message")
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "detail": "User not found",
            }
        }
    }


class AnalyticsHistoryResponse(BaseModel):
    """Time series response for the last 7 days used by charts"""
    dates: List[str] = Field(..., description="ISO dates for each day, oldest->newest")
    xp_by_day: List[int] = Field(..., description="XP earned per day, oldest->newest")
    tasks_completed_by_day: List[int] = Field(..., description="Tasks completed per day")
    tasks_failed_by_day: List[int] = Field(..., description="Tasks failed per day")
    stat_deltas_by_day: Dict[str, List[float]] = Field(..., description="Per-stat daily stat delta sums")

    model_config = {
        "json_schema_extra": {
            "example": {
                "dates": ["2026-02-09", "2026-02-10", "2026-02-11", "2026-02-12", "2026-02-13", "2026-02-14", "2026-02-15"],
                "xp_by_day": [0, 120, 80, 0, 50, 200, 100],
                "tasks_completed_by_day": [0, 2, 1, 0, 1, 4, 2],
                "tasks_failed_by_day": [0, 0, 0, 0, 0, 1, 0],
                "stat_deltas_by_day": {
                    "focus": [0, 1.2, 0.5, 0, 0.2, 2.0, 0.7],
                    "discipline": [0, 0.8, 0.2, 0, 0.1, 1.5, 0.4]
                }
            }
        }
    }
