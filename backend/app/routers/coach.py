"""AI Coach Router — system-controlled coaching endpoint.

NOT a chat interface. NOT a free-form AI tool.
This is the FLOW System Coach — runs once per day, returns a directive.

Endpoints:
  POST /api/coach/run    — Trigger a coaching cycle (rate limited: 1/day)
  GET  /api/coach/latest — Get the most recent coaching message
"""

import logging
from datetime import datetime, timedelta, UTC

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.db.database import get_db
from app.dependencies.auth import get_current_user
from app.models.user import User
from app.models.ai_coach_log import AICoachLog
from app.config import get_settings
from app.schemas.coach import (
    CoachRunRequest,
    CoachRunResponse,
    CoachLatestResponse,
)
from app.services.ai.analyzer import analyze_player
from app.services.ai.executor import execute_coach_output
from app.services.ai.validator import DEFAULT_OUTPUT

logger = logging.getLogger(__name__)

router = APIRouter()


# ── Rate-limit check ──────────────────────────────────────────────────────────

def _check_rate_limit(db: Session, user_id: int, trigger: str) -> bool:
    """Return True if the user is rate-limited (already called today).

    Exceptions:
    - 'failure' trigger: allowed 1 extra call per day on top of the daily
    - 'manual' trigger: no extra allowance, same as daily
    """
    now = datetime.now(UTC)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    # Count calls today
    calls_today = (
        db.query(AICoachLog)
        .filter(
            AICoachLog.player_id == user_id,
            AICoachLog.called_at >= today_start,
        )
        .count()
    )

    # Daily limit: 1 normal + 1 failure = max 2
    if trigger == "failure":
        # Allow 1 failure call even if daily was already used
        failure_calls = (
            db.query(AICoachLog)
            .filter(
                AICoachLog.player_id == user_id,
                AICoachLog.called_at >= today_start,
                AICoachLog.trigger_type == "failure",
            )
            .count()
        )
        return failure_calls >= 1  # Only 1 failure call allowed
    else:
        # Standard: 1 call per day
        daily_calls = (
            db.query(AICoachLog)
            .filter(
                AICoachLog.player_id == user_id,
                AICoachLog.called_at >= today_start,
                AICoachLog.trigger_type != "failure",
            )
            .count()
        )
        return daily_calls >= 1


# ── POST /run — Trigger coaching cycle ────────────────────────────────────────

@router.post(
    "/run",
    response_model=CoachRunResponse,
    summary="[ SYSTEM ] Run AI coaching cycle",
)
def run_coach(
    request: CoachRunRequest = CoachRunRequest(),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Trigger an AI coaching analysis for the current player.

    Rate limited: 1 call/day (+ 1 extra on major failure).
    The AI analyzes player data and returns a directive.
    Quests may be created. XP modifier may be adjusted.
    No chat. No free input. System only.
    """
    settings = get_settings()

    # Check API key
    if not settings.GROQ_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AI Coach is not configured. GROQ_API_KEY is missing.",
        )

    # Rate limit
    if _check_rate_limit(db, current_user.id, request.trigger):
        logger.info(f"AI Coach: rate limited user {current_user.id}")
        return CoachRunResponse(
            mode="normal",
            priority_domains=[],
            xp_modifier=0.0,
            message="[ SYSTEM ] Coaching cycle already completed today. Next analysis available tomorrow.",
            quests_created=[],
            valid=True,
            rate_limited=True,
        )

    try:
        # Run analysis pipeline: collect → prompt → Groq → validate
        output = analyze_player(db, current_user.id, settings.GROQ_API_KEY)

        # Execute: create quests, build result
        result = execute_coach_output(db, current_user.id, output)

        # Log the call (immutable audit record)
        log_entry = AICoachLog(
            player_id=current_user.id,
            raw_output=output.as_dict() if output.raw_valid else None,
            validated_output=result,
            was_rejected=not output.raw_valid,
            rejection_reasons=output.rejection_reasons if output.rejection_reasons else None,
            mode_applied=output.mode,
            xp_modifier_applied=output.xp_modifier,
            quests_created=result.get("quests_created", []),
            message_shown=output.message,
            api_success=output.raw_valid,
            trigger_type=request.trigger,
        )
        db.add(log_entry)
        db.commit()

        return CoachRunResponse(
            mode=result["mode"],
            priority_domains=result["priority_domains"],
            xp_modifier=result["xp_modifier"],
            message=result["message"],
            quests_created=result.get("quests_created", []),
            valid=result.get("valid", True),
            warnings=result.get("warnings", []),
        )

    except Exception as e:
        db.rollback()
        logger.exception(f"AI Coach: run failed for user {current_user.id}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="AI Coach cycle failed. Default protocol remains active.",
        )


# ── GET /latest — Get most recent coaching message ───────────────────────────

@router.get(
    "/latest",
    response_model=CoachLatestResponse,
    summary="[ SYSTEM ] Get latest coaching directive",
)
def get_latest_coach_message(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return the most recent AI coaching message for display.

    Used by the frontend to show the [SYSTEM MESSAGE] block.
    No chat history — only the latest directive.
    """
    log = (
        db.query(AICoachLog)
        .filter(AICoachLog.player_id == current_user.id)
        .order_by(desc(AICoachLog.called_at))
        .first()
    )

    if not log:
        return CoachLatestResponse(
            message="[ SYSTEM ] No coaching data available. Run your first coaching cycle.",
            mode="normal",
            xp_modifier=0.0,
            priority_domains=[],
            quests_created=[],
            available=False,
        )

    return CoachLatestResponse(
        message=log.message_shown or DEFAULT_OUTPUT.message,
        mode=log.mode_applied or "normal",
        xp_modifier=log.xp_modifier_applied or 0.0,
        priority_domains=log.validated_output.get("priority_domains", []) if log.validated_output else [],
        quests_created=log.quests_created or [],
        called_at=log.called_at,
        available=True,
    )
