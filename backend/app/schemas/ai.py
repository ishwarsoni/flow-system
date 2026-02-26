"""Pydantic schemas for AI task generation endpoints."""

from pydantic import BaseModel, Field
from typing import Any, Optional


class GoalGenerateRequest(BaseModel):
    goal: str = Field(..., min_length=10, max_length=500, description="Describe your real-world goal in plain text.")

    model_config = {
        "json_schema_extra": {
            "example": {
                "goal": "I want to get fit and run a 5K in 4 weeks starting from zero"
            }
        }
    }


class GeneratedTaskSchema(BaseModel):
    title: str
    description: str
    difficulty: str
    primary_stat: str
    base_xp_reward: int
    skill_points: int
    time_limit_minutes: Optional[int]
    week: int
    day_suggestion: str
    rationale: str


class GoalAnalysisResponse(BaseModel):
    goal_text: str
    category: str
    subcategory: str
    difficulty_level: str
    estimated_weeks: int
    primary_stat: str
    secondary_stat: str
    system_message: str
    tasks: list[GeneratedTaskSchema]
    xp_summary: dict[str, Any]


class CustomXPRequest(BaseModel):
    title: str = Field(..., min_length=3, max_length=200)
    description: str = Field(default="", max_length=1000)
    difficulty: str = Field(default="medium", pattern="^(easy|medium|hard|boss)$")
    estimated_minutes: int = Field(default=30, ge=1, le=480)
    category_hint: str = Field(default="")

    model_config = {
        "json_schema_extra": {
            "example": {
                "title": "Read 30 pages of a non-fiction book",
                "difficulty": "easy",
                "estimated_minutes": 45,
            }
        }
    }


class CustomXPResponse(BaseModel):
    recommended_xp: int
    recommended_sp: int
    primary_stat: str
    category_detected: str
    xp_breakdown: dict[str, int]
