"""AI Coach API schema — request/response models."""

from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class CoachRunRequest(BaseModel):
    """Optional trigger override. Empty body = standard daily run."""
    trigger: str = Field(
        default="daily",
        description="Trigger type: daily | failure | manual",
        pattern="^(daily|failure|manual)$",
    )

    model_config = {"extra": "forbid"}


class CoachQuestResponse(BaseModel):
    """A single quest created by the AI coach."""
    quest_id: int
    title: str
    domain: str
    difficulty: str
    estimated_minutes: int


class CoachRunResponse(BaseModel):
    """Result of an AI coaching cycle."""
    mode: str
    priority_domains: list[str]
    xp_modifier: float
    message: str
    quests_created: list[int]
    valid: bool
    warnings: list[str] = []
    rate_limited: bool = False


class CoachLatestResponse(BaseModel):
    """The most recent coaching message for display."""
    message: str
    mode: str
    xp_modifier: float
    priority_domains: list[str]
    quests_created: list[int]
    called_at: Optional[datetime] = None
    available: bool = True  # False if no coaching has ever run
