"""Pydantic schemas for the Quest system and Player profile."""

from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, Dict, List


# ═══════════════════════════════
# Template Schemas
# ═══════════════════════════════

class QuestTemplateResponse(BaseModel):
    """Public view of a quest template."""
    id: int
    category: str
    tier: str
    phase: str
    title_template: str
    description_template: Optional[str] = None
    unit_type: str = "minutes"
    base_xp: int = 100
    max_duration_minutes: Optional[int] = None
    constraint_level: int = 1
    performance_required: bool = False
    risk_level: int = 1
    cooldown_hours: int = 0
    is_active: bool = True

    model_config = {"from_attributes": True}


class GenerateQuestRequest(BaseModel):
    """Request to generate a quest from a template."""
    domain: str = Field(..., description="mind | body | core | control | presence | system")
    difficulty: str = Field(..., description="easy | intermediate | hard | extreme")

    model_config = {
        "json_schema_extra": {
            "example": {
                "domain": "mind",
                "difficulty": "hard",
            }
        }
    }


class GenerateQuestResponse(BaseModel):
    """Response after generating a quest from a template."""
    quest: "QuestResponse"
    template_id: int
    message: str


# ═══════════════════════════════
# Quest Schemas
# ═══════════════════════════════

class QuestCreateRequest(BaseModel):
    title: str = Field(..., min_length=5, max_length=200)
    description: Optional[str] = Field(None, max_length=1000)
    difficulty: str = Field(default="easy")
    primary_stat: str = Field(default="strength")
    domain: Optional[str] = Field(
        None,
        description="mind | body | core | control | presence | system"
    )
    estimated_minutes: Optional[int] = Field(
        None, ge=1, le=300,
        description=(
            "Estimated time to complete in minutes. "
            "Hard cap: 300 min (Extreme tier). Daily quests capped at 180 min. "
            "AI uses this to calculate XP & SP."
        )
    )
    time_limit_minutes: Optional[int] = Field(None, ge=1, le=300)
    # Manual quest metrics
    metrics_required:   bool           = False
    metrics_definition: Optional[dict] = Field(
        None,
        description="What must be submitted to prove completion (required for hard/extreme)."
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "title": "Study for 90 minutes",
                "description": "Complete one chapter of algorithms textbook",
                "difficulty": "medium",
                "primary_stat": "intelligence",
                "estimated_minutes": 90,
            }
        }
    }


class AnalyzeQuestRequest(BaseModel):
    """Pure analysis — no DB write. Frontend calls this on debounce."""
    title: str = Field(..., min_length=3, max_length=200)
    description: Optional[str] = Field(None, max_length=1000)
    estimated_minutes: Optional[int] = Field(None, ge=1, le=480)

    model_config = {
        "json_schema_extra": {
            "example": {
                "title": "do 100 pushups",
                "description": "Complete 100 consecutive push-ups",
                "estimated_minutes": 15,
            }
        }
    }


class AnalyzeQuestResponse(BaseModel):
    """AI analysis result returned to frontend for user confirmation/override."""
    recommended_difficulty: str
    recommended_primary_stat: str
    recommended_xp: int
    recommended_sp: int
    category_detected: str
    system_message: str
    sl_title: str
    sl_description: str
    xp_breakdown: Dict[str, int]


class QuestResponse(BaseModel):
    id: int
    user_id: int
    template_id: Optional[int] = None
    title: str
    description: Optional[str]
    quest_type: str
    difficulty: str
    primary_stat: Optional[str]
    domain: Optional[str] = None
    verification_type: Optional[str] = "log"   # log | metrics | output
    base_xp_reward: int
    coin_reward: int
    bonus_skill_points: int
    penalty_xp: int
    penalty_hp: int
    mp_cost: int
    time_limit_minutes: Optional[int]
    max_duration_minutes: Optional[int] = None
    performance_multiplier: float = 1.0
    expires_at: Optional[datetime]
    status: str
    auto_generated: bool
    is_manual: bool = False
    # Metrics / verification
    metrics_required: bool = False
    metrics_submitted: Optional[Dict] = None
    metrics_verified: Optional[bool] = None
    # Difficulty metadata (shown on quest cards)
    cooldown_hours: int = 0
    weekly_limit: Optional[int] = None
    created_at: datetime
    completed_at: Optional[datetime]
    failed_at: Optional[datetime]

    model_config = {"from_attributes": True}


class QuestActionResponse(BaseModel):
    """Response after quest completion or failure."""
    quest: QuestResponse
    xp_earned: Optional[int] = None
    xp_penalty: Optional[int] = None
    skill_points_earned: Optional[int] = None
    hp_damage: Optional[int] = None
    mp_cost: Optional[int] = None
    stat_changes: Dict[str, float] = {}
    level: int
    xp_current: int
    xp_to_next_level: int
    hp_current: int
    mp_current: int
    fatigue: Optional[float] = None
    rank_event: Optional[str] = None
    streak_days: Optional[int] = None
    streak_milestone: Optional[dict] = None


class PaginatedQuestResponse(BaseModel):
    items: List[QuestResponse]
    total: int
    limit: int
    offset: int

    model_config = {"from_attributes": True}


class MetricsSubmitRequest(BaseModel):
    """Player submits verifiable proof/metrics for a metrics-required quest.

    Must be called before /complete on any quest where metrics_required=True.
    Metrics are rejected if empty or all-zero.
    """
    metrics: Dict = Field(
        ...,
        description=(
            "Key-value proof of completion. "
            "Examples: {\"sets\": 5, \"reps\": 100} | "
            "{\"output_url\": \"https://...\", \"notes\": \"written summary\"}. "
            "Cannot be empty or all-zero."
        ),
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "metrics": {
                    "push_ups": 80,
                    "pull_ups": 25,
                    "squats": 60,
                    "notes": "completed full circuit, all sets logged",
                }
            }
        }
    }


class MetricsSubmitResponse(BaseModel):
    quest_id: int
    metrics_submitted: Dict
    metrics_verified: Optional[bool] = None
    message: str


# ═══════════════════════════════
# Player Schemas
# ═══════════════════════════════

class PlayerProfileResponse(BaseModel):
    """Full player HUD data."""
    # Identity
    hunter_name: str = "Hunter"
    level: int
    rank: str
    rank_title: str
    current_title: str

    # Vitals
    hp_current: int
    hp_max: int
    mp_current: int
    mp_max: int

    # XP
    xp_current: int
    xp_total_earned: int
    xp_to_next_level: int
    xp_for_next_level: int

    # Stats
    strength: float
    intelligence: float
    vitality: float
    charisma: float
    mana: float

    # Economy
    coins: int
    skill_points: int
    reputation: int

    # System
    fatigue: float
    streak_days: int
    longest_streak: int
    streak_xp_bonus_percent: float
    punishment_active: int

    # Rank info
    rank_xp_multiplier: float
    rank_coin_multiplier: float
    daily_quest_count: int
    special_quests_unlocked: bool
    allowed_difficulties: list[str] = ["easy"]
    next_rank: Optional[dict] = None


class AllocateStatsRequest(BaseModel):
    allocations: Dict[str, int] = Field(
        ...,
        description="Stat name → points to allocate. e.g. {'strength': 2, 'intelligence': 1}"
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "allocations": {"strength": 2, "intelligence": 1}
            }
        }
    }


class AllocateStatsResponse(BaseModel):
    message: str
    remaining_skill_points: int
    stats: Dict[str, float]


# ═══════════════════════════════
# Analytics (updated for RPG)
# ═══════════════════════════════

class ProgressionOverviewResponse(BaseModel):
    """Complete overview for analytics page."""
    # Progression
    level: int
    rank: str
    xp_current: int
    xp_total_earned: int
    xp_to_next_level: int

    # Stats
    strength: float
    intelligence: float
    vitality: float
    charisma: float
    mana: float

    # Stat Analysis
    strongest_stat: str
    strongest_stat_value: float
    weakest_stat: str
    weakest_stat_value: float

    # Vitals
    hp_current: int
    hp_max: int
    mp_current: int
    mp_max: int
    fatigue: float

    # Today
    xp_earned_today: int
    quests_completed_today: int
    quests_failed_today: int

    # Last 7 Days
    xp_earned_7days: int
    quests_completed_7days: int
    quests_failed_7days: int

    # Streaks
    current_streak_days: int
    longest_streak_days: int
    streak_days: int
    skill_points: int

    model_config = {"from_attributes": True}


class AnalyticsHistoryResponse(BaseModel):
    dates: List[str]
    xp_by_day: List[int]
    quests_completed_by_day: List[int]
    quests_failed_by_day: List[int]
    stat_deltas_by_day: Dict[str, List[float]]

    model_config = {"from_attributes": True}


# ═══════════════════════════════
# Shadow Rival
# ═══════════════════════════════

class ShadowRivalResponse(BaseModel):
    """Shadow Rival — AI ghost player on the optimal ascension path."""
    shadow_level: int
    shadow_rank: str
    shadow_xp: int
    real_level: int
    real_rank: str
    real_xp: int
    gap_xp: int
    gap_days: int
    leading_stats: List[str]   # stats where you beat your shadow
    trailing_stats: List[str]  # stats where shadow is ahead
    shadow_stats: Dict[str, float]
    real_stats: Dict[str, float]
    motivational_message: str
