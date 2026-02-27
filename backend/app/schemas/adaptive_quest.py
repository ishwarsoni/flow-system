"""Pydantic schemas for the Adaptive Quest & Mindset Evolution System."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional
from pydantic import BaseModel, Field


# ─── Tier option (one of the three shown to the player) ──────────────────────

class QuestOption(BaseModel):
    """A single difficulty option in the generated panel."""

    tier: str                          # easy | intermediate | hard | extreme
    title: str
    description: str
    xp_reward: int
    coin_reward: int
    value: float                       # numeric magnitude (minutes, reps, etc.)
    unit: str                          # "min" | "reps" | "pages" | …
    primary_stat: str                  # stat trained by this option
    stat_rewards: dict[str, float]     # e.g. {"intelligence": 2.5}
    penalty_xp_on_fail: int
    time_limit_minutes: Optional[int] = None
    # Structured difficulty axes (replaces time-only scaling)
    max_duration_minutes: Optional[int] = None   # enforced cap for this option
    constraint_level: int = 1                    # 1=light, 4=maximum
    performance_required: bool = False           # hard/extreme: must meet metric
    risk_level: int = 1                          # 1=low, 4=high penalty/demotion
    cooldown_hours: int = 0                      # 0 unless extreme (24h)
    difficulty_score: Optional[float] = None     # weighted composite 0.0–1.0
    # Verification — ALL quests must be verifiable (FLOW Rule)
    verification_type: str = "log"     # log | metrics | output
    # Custom-quest fields
    is_custom: bool = False            # True = player-created
    template_id: Optional[int] = None # system template that produced this option
    custom_quest_id: Optional[int] = None
    meta: dict[str, Any] = Field(default_factory=dict)


# ─── Trio (all three options) ─────────────────────────────────────────────────

class QuestTrioResponse(BaseModel):
    """The full four-option panel (easy / intermediate / hard / extreme)
    plus the player's own custom quests for this category."""

    session_id: int
    category: str
    phase: str
    force_challenge_active: bool
    minimum_choosable_tier: str        # easy | intermediate | hard | extreme
    allowed_difficulties: list[str] = Field(default_factory=lambda: ["easy", "intermediate", "hard", "extreme"])  # rank-gated
    mindset_tier: str                  # dormant | awakening | focused | driven | elite
    mindset_score: float
    easy: QuestOption
    intermediate: QuestOption
    hard: QuestOption
    extreme: QuestOption               # ← always present
    custom_quests: list[QuestOption] = Field(default_factory=list)  # player-written
    generated_at: datetime
    expires_at: Optional[datetime] = None
    message: Optional[str] = None

    model_config = {"from_attributes": True}


# ─── Player chooses a tier ────────────────────────────────────────────────────

class ChooseTierRequest(BaseModel):
    session_id: int = Field(..., ge=1)
    chosen_tier: str = Field(..., pattern="^(easy|intermediate|hard|extreme)$")
    # Set when the player picks one of their own custom quests instead
    custom_quest_id: Optional[int] = None

    model_config = {"extra": "forbid"}


class ChooseTierResponse(BaseModel):
    session_id: int
    quest_id: int
    chosen_tier: str
    quest_title: str
    xp_reward: int
    mindset_delta: float               # +/- change applied to mindset score
    new_mindset_score: float
    message: Optional[str] = None

    model_config = {"from_attributes": True}


# ─── Mindset status ───────────────────────────────────────────────────────────

class MindsetStatusResponse(BaseModel):
    user_id: int
    score: float
    tier: str
    hard_choices: int
    intermediate_choices: int
    easy_choices: int
    hard_completion_rate: float        # hard_completions / (hard_completions + hard_failures)
    consecutive_non_hard_days: int
    force_challenge_active: bool
    recovery_mode: bool
    recovery_quests_required: int
    recovery_quests_completed: int
    recovery_deadline: Optional[datetime] = None
    updated_at: datetime

    model_config = {"from_attributes": True}


# ─── Recovery quest ───────────────────────────────────────────────────────────

class RecoveryQuestResponse(BaseModel):
    quest_id: int
    title: str
    description: str
    xp_reward: int
    required_count: int
    completed_count: int
    deadline: Optional[datetime] = None
    message: str

    model_config = {"from_attributes": True}


# ─── Force-challenge status ───────────────────────────────────────────────────

class ForceChallengeStatusResponse(BaseModel):
    active: bool
    until: Optional[datetime] = None
    reason: str
    consecutive_non_hard_days: int
    trigger_threshold: int


# ─── Admin / config views ─────────────────────────────────────────────────────

class DifficultyProfileResponse(BaseModel):
    id: int
    category: str
    phase: str
    level_min: int
    level_max: int
    base_value: float
    easy_multiplier: float
    intermediate_multiplier: float
    hard_multiplier: float
    extreme_multiplier: float = 1.6
    easy_xp_base: int
    intermediate_xp_base: int
    hard_xp_base: int
    extreme_xp_base: int = 400
    primary_stat: str
    description: Optional[str] = None
    is_active: bool

    model_config = {"from_attributes": True}


class ProgressionTierResponse(BaseModel):
    id: int
    phase: str
    level_min: int
    level_max: int
    base_difficulty: float
    easy_multiplier: float
    intermediate_multiplier: float
    hard_multiplier: float
    xp_scale: float
    force_challenge_trigger_days: int
    minimum_choosable_tier: str
    description: Optional[str] = None

    model_config = {"from_attributes": True}


class PenaltyTierResponse(BaseModel):
    id: int
    phase: str
    difficulty_chosen: str
    xp_penalty: int
    hp_damage: int
    streak_penalty: int
    coin_penalty: int
    rank_block_days: int
    demotion_risk: float
    boost_lock_hours: int
    punishment_mode_days: int
    recovery_quest_required: bool
    recovery_quest_count: int
    recovery_window_hours: int
    stat_penalty_fraction: float
    mindset_penalty: float
    description: Optional[str] = None

    model_config = {"from_attributes": True}


class QuestTemplateResponse(BaseModel):
    id: int
    category: str
    tier: str
    phase: str
    title_template: str
    description_template: Optional[str] = None
    unit_type: str
    base_xp: int
    stat_bonus: Optional[dict[str, float]] = None
    selection_weight: float
    is_active: bool
    # Structured difficulty axes
    max_duration_minutes: Optional[int] = None
    constraint_level: int = 1
    performance_required: bool = False
    risk_level: int = 1
    cooldown_hours: int = 0

    model_config = {"from_attributes": True}


# ─── Session history ──────────────────────────────────────────────────────────

class AdaptiveSessionResponse(BaseModel):
    id: int
    category: str
    phase: str
    chosen_tier: Optional[str] = None
    outcome: Optional[str] = None
    mindset_score_at_generation: Optional[float] = None
    force_challenge_was_active: bool
    generated_at: datetime
    chosen_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class AdaptiveSessionHistoryResponse(BaseModel):
    items: list[AdaptiveSessionResponse]
    total: int
    limit: int
    offset: int


# ─── Custom quest schemas ─────────────────────────────────────────────────────

class CustomQuestCreate(BaseModel):
    category:            str             = Field(..., example="body")
    tier:                str             = Field(..., example="hard")
    title:               str             = Field(..., min_length=5, max_length=200)
    description:         Optional[str]   = Field(None, max_length=1000)
    duration_value:      Optional[float] = Field(None, ge=0)
    duration_unit:       Optional[str]   = Field("minutes", max_length=20)
    xp_override:         Optional[int]   = Field(None, ge=10, le=2000)
    # Structured difficulty axes
    constraint_level:    int             = Field(default=1, ge=1, le=4)
    performance_required: bool           = False
    risk_level:          int             = Field(default=1, ge=1, le=4)
    # Metrics — required for hard/extreme
    metrics_required:    bool            = False
    metrics_definition:  Optional[dict]  = Field(
        None,
        description=(
            "What the player must submit to prove completion. "
            "E.g. {\"type\": \"reps\", \"target\": 100} or "
            "{\"type\": \"output\", \"description\": \"written essay\"}. "
            "Required when tier is hard or extreme."
        ),
    )

    model_config = {
        "extra": "forbid",
        "json_schema_extra": {
            "example": {
                "category": "body",
                "tier": "hard",
                "title": "45-min calisthenics session — log every set",
                "description": "Push-ups, pull-ups, squats, dips. Every set logged in real time.",
                "duration_value": 45,
                "duration_unit": "minutes",
                "constraint_level": 3,
                "performance_required": True,
                "risk_level": 3,
                "metrics_required": True,
                "metrics_definition": {"type": "sets_reps", "exercises": ["push-ups", "pull-ups", "squats"]},
            }
        }
    }


class CustomQuestUpdate(BaseModel):
    title:               Optional[str]   = Field(None, min_length=5, max_length=200)
    description:         Optional[str]   = Field(None, max_length=1000)
    tier:                Optional[str]   = None
    duration_value:      Optional[float] = Field(None, ge=0)
    duration_unit:       Optional[str]   = None
    xp_override:         Optional[int]   = Field(None, ge=10, le=2000)
    metrics_required:    Optional[bool]  = None
    metrics_definition:  Optional[dict]  = None

    model_config = {"extra": "forbid"}


class CustomQuestResponse(BaseModel):
    id:                  int
    category:            str
    tier:                str
    title:               str
    description:         Optional[str]  = None
    duration_value:      Optional[float] = None
    duration_unit:       str
    xp_override:         Optional[int]  = None
    constraint_level:    int
    performance_required: bool
    risk_level:          int
    metrics_required:    bool
    metrics_definition:  Optional[dict] = None
    cooldown_hours:      int
    weekly_limit:        Optional[int]  = None
    is_active:           bool
    created_at:          datetime

    model_config = {"from_attributes": True}


class MetricsSubmitRequest(BaseModel):
    """Player submits proof/metrics for a metrics-required quest."""
    quest_id: int = Field(..., ge=1)
    metrics:  dict = Field(
        ...,
        description=(
            "Key-value proof of completion. "
            "Examples: {\"sets\": 5, \"reps\": 100} | "
            "{\"output_url\": \"https://...\", \"notes\": \"...\"}. "
            "Cannot be empty or all-zero."
        ),
    )

    model_config = {
        "extra": "forbid",
        "json_schema_extra": {
            "example": {
                "quest_id": 42,
                "metrics": {"push_ups": 80, "pull_ups": 25, "squats": 60, "notes": "completed full circuit"},
            }
        }
    }


class DismissSystemQuestRequest(BaseModel):
    quest_template_id: int
    reason:            Optional[str] = Field(None, max_length=200)

    model_config = {"extra": "forbid"}


class DismissSystemQuestResponse(BaseModel):
    message:           str
    quest_template_id: int
    dismissed_at:      datetime


# ─── Daily quest panel (all 6 domains pre-generated) ────────────────────────────────────────────────────

class DailyQuestPanel(BaseModel):
    """All six domain panels for the player's daily quest page."""
    date:    str                           # YYYY-MM-DD
    phase:   str
    allowed_difficulties: list[str] = Field(default_factory=lambda: ["easy"])  # rank-gated
    panels:  dict[str, QuestTrioResponse]  # keyed by domain code: mind|body|core|control|presence|system
    already_existed: bool = False         # True if panels were generated earlier today
