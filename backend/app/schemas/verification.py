"""Pydantic schemas for the Quest Verification System."""

from pydantic import BaseModel, Field, field_validator
from datetime import datetime
from typing import Optional, List, Dict, Any


# ═══════════════════════════════════════════════════════════
# Session schemas
# ═══════════════════════════════════════════════════════════

class SessionStartRequest(BaseModel):
    """POST /quests/{id}/start"""
    device_id:          Optional[str]  = Field(None, max_length=128)
    user_agent:         Optional[str]  = Field(None, max_length=512)

    model_config = {"extra": "forbid", "json_schema_extra": {"example": {
        "device_id": "abc123",
        "user_agent": "Mozilla/5.0...",
    }}}


class HeartbeatRequest(BaseModel):
    """PATCH /quests/{id}/session/heartbeat — sent every 30 s from frontend."""
    active_delta_sec:   int  = Field(..., ge=0, le=60, description="Seconds of active time since last heartbeat")
    idle_delta_sec:     int  = Field(..., ge=0, le=60)
    tab_hidden_delta:   int  = Field(0,  ge=0, le=60)
    app_bg_delta:       int  = Field(0,  ge=0, le=60)

    model_config = {"extra": "forbid"}


class SessionResponse(BaseModel):
    session_id:             int
    quest_id:               int
    started_at:             datetime
    expected_duration_sec:  Optional[int]
    window_end:             Optional[datetime]
    requires_output:        bool
    requires_spot_check:    bool
    status:                 str
    active_time_sec:        int
    idle_time_sec:          int
    time_score:             Optional[float]
    output_score:           Optional[float]
    consistency_score:      Optional[float]
    behavior_score:         Optional[float]
    verification_score:     Optional[float]

    model_config = {"from_attributes": True}


# ═══════════════════════════════════════════════════════════
# Output / proof schemas
# ═══════════════════════════════════════════════════════════

class OutputSubmitRequest(BaseModel):
    """POST /quests/{id}/output — submit proof artifact."""
    output_type:        str  = Field(..., description="summary|notes|explanation|plan|checklist|screenshot|reflection|spot_check")
    content:            Optional[str]  = Field(None, max_length=8000)
    media_url:          Optional[str]  = Field(None, max_length=512)
    metadata:           Optional[Dict[str, Any]] = None
    prompt_text:        Optional[str]  = Field(None, max_length=512)
    response_text:      Optional[str]  = Field(None, max_length=4000)
    time_to_write_sec:  Optional[int]  = Field(None, ge=0)

    model_config = {"extra": "forbid"}

    @field_validator("content")
    @classmethod
    def content_not_empty(cls, v):
        if v is not None and v.strip() == "":
            raise ValueError("Output content must not be blank")
        return v


class OutputResponse(BaseModel):
    id:                 int
    session_id:         int
    output_type:        str
    content:            Optional[str]
    media_url:          Optional[str]
    quality:            str
    quality_score:      Optional[float]
    word_count:         int
    submitted_at:       datetime

    model_config = {"from_attributes": True}


# ═══════════════════════════════════════════════════════════
# Submission / completion schemas
# ═══════════════════════════════════════════════════════════

class QuestSubmitRequest(BaseModel):
    """POST /quests/{id}/submit — player declares completion."""
    final_active_sec:   Optional[int]  = Field(None, ge=0)
    final_idle_sec:     Optional[int]  = Field(None, ge=0)
    self_rating:        Optional[int]  = Field(None, ge=1, le=5, description="Optional self-assessment 1–5")

    model_config = {"extra": "forbid"}


class QuestCompleteRequest(BaseModel):
    """POST /quests/{id}/complete — triggers verification + reward grant.
    Only valid after /submit passes."""

    model_config = {"extra": "forbid"}


# ═══════════════════════════════════════════════════════════
# Spot check schemas
# ═══════════════════════════════════════════════════════════

class SpotCheckQuestion(BaseModel):
    prompt:     str
    session_id: int


class SpotCheckResponse(BaseModel):
    """POST /quests/{id}/spot-check"""
    session_id:     int
    response_text:  str = Field(..., min_length=10, max_length=2000)

    model_config = {"extra": "forbid"}


# ═══════════════════════════════════════════════════════════
# Verification result schemas
# ═══════════════════════════════════════════════════════════

class VerificationResultResponse(BaseModel):
    session_id:             int
    decision:               str
    verification_score:     float
    time_score:             float
    output_score:           float
    consistency_score:      float
    behavior_score:         float
    reward_multiplier:      float
    xp_awarded:             int
    xp_penalty:             int
    trust_delta:            float
    trust_score_after:      Optional[float]
    failure_reason:         Optional[str]
    flags_raised:           List[str]
    layers_applied:         List[str]
    spot_check_triggered:   bool
    output_required:        bool

    model_config = {"from_attributes": True}


class VerificationStatusResponse(BaseModel):
    """GET /quests/{id}/verification — current state for frontend."""
    session_id:             Optional[int]
    session_status:         Optional[str]
    requires_output:        bool
    requires_spot_check:    bool
    spot_check_prompt:      Optional[str]
    verification_score:     Optional[float]
    decision:               Optional[str]
    can_submit:             bool
    failure_reason:         Optional[str]


# ═══════════════════════════════════════════════════════════
# Trust profile schemas
# ═══════════════════════════════════════════════════════════

class TrustProfileResponse(BaseModel):
    player_id:              int
    trust_score:            float
    trust_tier:             str
    total_sessions:         int
    verified_sessions:      int
    soft_fail_count:        int
    hard_fail_count:        int
    spot_check_pass_count:  int
    spot_check_fail_count:  int
    output_quality_avg:     float
    flag_count:             int
    audit_mode:             bool
    consecutive_verified:   int
    consecutive_fails:      int
    instant_complete_count: int
    last_recalculated_at:   Optional[datetime]

    model_config = {"from_attributes": True}


# ═══════════════════════════════════════════════════════════
# Audit / admin schemas
# ═══════════════════════════════════════════════════════════

class AuditFlagResponse(BaseModel):
    id:             int
    player_id:      int
    session_id:     Optional[int]
    quest_id:       Optional[int]
    flag_type:      str
    severity:       str
    description:    Optional[str]
    evidence:       Optional[Dict[str, Any]]
    resolved:       bool
    raised_at:      datetime

    model_config = {"from_attributes": True}
