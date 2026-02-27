"""Adaptive Quest & Mindset Evolution System — API router.

Prefix: /api/adaptive

Endpoints
---------
GET   /daily                             Full daily panel (all 5 categories)
POST  /generate                          Generate a three-option trio
POST  /choose                            Player accepts one tier
GET   /mindset                           Current mindset status
GET   /force-challenge                   Force-challenge status
POST  /recovery/create                   Create a recovery quest (if in recovery mode)
POST  /fail/{quest_id}                   Apply adaptive penalty on quest failure
POST  /resolve/{session_id}              Mark session outcome (called internally)
GET   /history                           Paginated session history

Custom Quests
-------------
GET   /custom                            List user's custom quests
POST  /custom                            Create a custom quest
PUT   /custom/{quest_id}                 Update a custom quest
DELETE /custom/{quest_id}               Delete (soft) a custom quest
POST  /system/dismiss                   Dismiss a system-recommended quest
DELETE /system/dismiss/{template_id}    Restore a dismissed system quest

Admin
-----
GET   /config/difficulty-profiles        List all difficulty profile rows
GET   /config/progression-tiers         List all progression tier rows
GET   /config/penalty-tiers             List all penalty tier rows
GET   /config/templates                 List all quest templates
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.dependencies.auth import get_current_user, get_admin_user
from app.models.user import User
from app.models.user_stats import UserStats
from app.models.difficulty_profile import DifficultyProfile
from app.models.progression_tier import ProgressionTier
from app.models.penalty_tier import PenaltyTier
from app.models.quest_template import QuestTemplate
from app.services.adaptive_quest_service import AdaptiveQuestService
from app.services.mindset_engine import MindsetEngine
from app.services.penalty_engine import PenaltyEngine
from app.services.adaptive_push_service import AdaptivePushService
from app.services.custom_quest_service import custom_quest_service
from app.schemas.adaptive_quest import (
    ChooseTierRequest,
    ChooseTierResponse,
    QuestTrioResponse,
    DailyQuestPanel,
    MindsetStatusResponse,
    ForceChallengeStatusResponse,
    RecoveryQuestResponse,
    DifficultyProfileResponse,
    ProgressionTierResponse,
    PenaltyTierResponse,
    QuestTemplateResponse,
    AdaptiveSessionResponse,
    AdaptiveSessionHistoryResponse,
    CustomQuestCreate,
    CustomQuestUpdate,
    CustomQuestResponse,
    MetricsSubmitRequest,
    DismissSystemQuestRequest,
    DismissSystemQuestResponse,
)

router = APIRouter(prefix="/adaptive", tags=["adaptive-quests"])

# ── Daily panel ──────────────────────────────────────────────────────

@router.get(
    "/daily",
    response_model=DailyQuestPanel,
    summary="Get all 6 domain quest panels for today",
    description=(
        "Returns Easy / Intermediate / Hard / Extreme quest options for every "
        "domain (mind, body, core, control, presence, system) in one call. "
        "If panels were already generated today they are returned from cache. "
        "Pass ?force=true to clear today's sessions and regenerate with current templates."
    ),
)
def get_daily_panel(
    force: bool = Query(False, description="Clear stale sessions and regenerate from current templates"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DailyQuestPanel:
    try:
        return AdaptiveQuestService.generate_daily_panel(
            user_id=current_user.id,
            db=db,
            force_refresh=force,
        )
    except (ValueError, LookupError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))


# ── Generate trio ──────────────────────────────────────────────────────────────

@router.post(
    "/generate",
    response_model=QuestTrioResponse,
    summary="Generate three difficulty options for a quest category",
    description=(
        "Returns Easy / Intermediate / Hard quest options computed from the "
        "player's level, rank, stats, and mindset score. "
        "If force-challenge is active the Hard option is the only valid choice."
    ),
)
def generate_trio(
    category: str = Query(..., description="mind | body | core | control | presence | system"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> QuestTrioResponse:
    try:
        return AdaptiveQuestService.generate_trio(
            user_id=current_user.id,
            category=category.lower().strip(),
            db=db,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


# ── Choose tier ────────────────────────────────────────────────────────────────

@router.post(
    "/choose",
    response_model=ChooseTierResponse,
    summary="Accept a difficulty tier and create the quest",
    description=(
        "The player selects one of the three generated tiers. "
        "A Quest row is created and returned. "
        "Force-challenge sessions ONLY accept 'hard'."
    ),
)
def choose_tier(
    body: ChooseTierRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ChooseTierResponse:
    try:
        result = AdaptiveQuestService.choose_tier(
            session_id=body.session_id,
            chosen_tier=body.chosen_tier,
            user_id=current_user.id,
            db=db,
        )
        db.commit()
        return result
    except (ValueError, LookupError) as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc))


# ── Fail an adaptive quest ─────────────────────────────────────────────────────

@router.post(
    "/fail/{quest_id}",
    summary="Apply adaptive failure penalties to a quest",
    description=(
        "Applies the full PenaltyEngine consequence chain for a failed adaptive quest. "
        "Call this INSTEAD OF the generic /quests/{id}/fail endpoint for quests that "
        "were generated by the adaptive system."
    ),
)
def fail_adaptive_quest(
    quest_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    from app.models.quest import Quest, QuestStatus

    quest = db.query(Quest).filter(
        Quest.id == quest_id,
        Quest.user_id == current_user.id,
    ).first()
    if not quest:
        raise HTTPException(status_code=404, detail="Quest not found.")
    if quest.status not in (QuestStatus.PENDING, QuestStatus.IN_PROGRESS):
        raise HTTPException(status_code=400, detail="Quest is not active.")

    stats = db.query(UserStats).filter(
        UserStats.user_id == current_user.id,
    ).first()
    if not stats:
        raise HTTPException(status_code=404, detail="Player stats not found.")

    # Map QuestDifficulty enum back to tier string
    difficulty_map = {"easy": "easy", "medium": "intermediate", "hard": "hard"}
    chosen_tier = difficulty_map.get(quest.difficulty.value, "easy")

    penalties = PenaltyEngine.apply_failure(
        user_id=current_user.id,
        stats=stats,
        chosen_tier=chosen_tier,
        db=db,
    )

    from datetime import datetime, UTC
    quest.status = QuestStatus.FAILED
    quest.failed_at = datetime.now(UTC)
    db.commit()

    return {
        "quest_id": quest_id,
        "status": "failed",
        "penalties_applied": penalties,
    }


# ── Mindset status ─────────────────────────────────────────────────────────────

@router.get(
    "/mindset",
    response_model=MindsetStatusResponse,
    summary="Get the player's current mindset score and behavioural profile",
)
def get_mindset_status(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MindsetStatusResponse:
    ms = MindsetEngine.get_mindset_score(current_user.id, db)
    return MindsetStatusResponse(
        user_id=current_user.id,
        score=ms.score,
        tier=ms.tier_label,
        hard_choices=ms.hard_choices,
        intermediate_choices=ms.intermediate_choices,
        easy_choices=ms.easy_choices,
        hard_completion_rate=ms.completion_rate,
        consecutive_non_hard_days=ms.consecutive_non_hard_days,
        force_challenge_active=ms.force_challenge_active,
        recovery_mode=ms.recovery_mode,
        recovery_quests_required=ms.recovery_quests_required,
        recovery_quests_completed=ms.recovery_quests_completed,
        recovery_deadline=ms.recovery_deadline,
        updated_at=ms.updated_at,
    )


# ── Force-challenge status ─────────────────────────────────────────────────────

@router.get(
    "/force-challenge",
    response_model=ForceChallengeStatusResponse,
    summary="Check if force-challenge mode is active",
)
def get_force_challenge_status(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ForceChallengeStatusResponse:
    return AdaptivePushService.get_force_challenge_status(current_user.id, db)


# ── Recovery quest ─────────────────────────────────────────────────────────────

@router.post(
    "/recovery/create",
    response_model=RecoveryQuestResponse,
    summary="Create the next recovery quest in the rebuild sequence",
)
def create_recovery_quest(
    category: str = Query("mind", description="Domain for the recovery quest"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> RecoveryQuestResponse:
    try:
        result = AdaptivePushService.create_recovery_quest(
            user_id=current_user.id,
            db=db,
            category=category.lower().strip(),
        )
        db.commit()
        return result
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc))


# ── Session history ────────────────────────────────────────────────────────────

@router.get(
    "/history",
    response_model=AdaptiveSessionHistoryResponse,
    summary="Paginated adaptive quest session history",
)
def get_history(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AdaptiveSessionHistoryResponse:
    items, total = AdaptiveQuestService.get_history(
        user_id=current_user.id,
        db=db,
        limit=limit,
        offset=offset,
    )
    return AdaptiveSessionHistoryResponse(
        items=[AdaptiveSessionResponse.model_validate(i) for i in items],
        total=total,
        limit=limit,
        offset=offset,
    )


# ── Resolve session (internal utility) ────────────────────────────────────────

@router.post(
    "/resolve/{session_id}",
    summary="Mark a session as completed, failed, or expired (internal)",
    include_in_schema=False,
)
def resolve_session(
    session_id: int,
    outcome: str = Query(..., pattern="^(completed|failed|expired|abandoned)$"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    AdaptiveQuestService.resolve_session(session_id, current_user.id, outcome, db)
    db.commit()
    return {"session_id": session_id, "outcome": outcome}


# ── Custom quests ──────────────────────────────────────────────────────────────

@router.get(
    "/custom",
    response_model=list[CustomQuestResponse],
    summary="List user's active custom quests",
)
def list_custom_quests(
    category: Optional[str] = Query(None, description="Filter by category"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[CustomQuestResponse]:
    rows = custom_quest_service.list_for_user(
        db, current_user.id, category=category
    )
    return [CustomQuestResponse.model_validate(r) for r in rows]


@router.post(
    "/custom",
    response_model=CustomQuestResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new custom quest",
)
def create_custom_quest(
    body: CustomQuestCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CustomQuestResponse:
    try:
        cq = custom_quest_service.create(
            db=db,
            user_id=current_user.id,
            category=body.category,
            tier=body.tier,
            title=body.title,
            description=body.description,
            duration_value=body.duration_value,
            duration_unit=body.duration_unit or "minutes",
            xp_override=body.xp_override,
            constraint_level=body.constraint_level,
            performance_required=body.performance_required,
            risk_level=body.risk_level,
            metrics_required=body.metrics_required,
            metrics_definition=body.metrics_definition,
        )
        db.commit()
        db.refresh(cq)
        return CustomQuestResponse.model_validate(cq)
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc))


@router.put(
    "/custom/{quest_id}",
    response_model=CustomQuestResponse,
    summary="Update an existing custom quest",
)
def update_custom_quest(
    quest_id: int,
    body: CustomQuestUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CustomQuestResponse:
    try:
        cq = custom_quest_service.update(
            db=db,
            user_id=current_user.id,
            quest_id=quest_id,
            **body.model_dump(exclude_none=True),
        )
        db.commit()
        db.refresh(cq)
        return CustomQuestResponse.model_validate(cq)
    except (ValueError, LookupError) as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc))


@router.delete(
    "/custom/{quest_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Soft-delete a custom quest",
    response_class=Response,
)
def delete_custom_quest(
    quest_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    try:
        custom_quest_service.delete(db, current_user.id, quest_id)
        db.commit()
        return Response(status_code=204)
    except LookupError as exc:
        db.rollback()
        raise HTTPException(status_code=404, detail=str(exc))


# ── System quest dismissal ─────────────────────────────────────────────────────

@router.post(
    "/system/dismiss",
    response_model=DismissSystemQuestResponse,
    summary="Dismiss a system-recommended quest template",
)
def dismiss_system_quest(
    body: DismissSystemQuestRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DismissSystemQuestResponse:
    try:
        record = custom_quest_service.dismiss_system(
            db=db,
            user_id=current_user.id,
            quest_template_id=body.quest_template_id,
            reason=body.reason,
        )
        db.commit()
        db.refresh(record)
        return DismissSystemQuestResponse(
            id=record.id,
            user_id=record.user_id,
            quest_template_id=record.quest_template_id,
            reason=record.reason,
            dismissed_at=record.dismissed_at,
        )
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc))


@router.delete(
    "/system/dismiss/{template_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Restore a previously dismissed system quest",
    response_class=Response,
)
def restore_system_quest(
    template_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    custom_quest_service.restore_system(db, current_user.id, template_id)
    db.commit()
    return Response(status_code=204)


# ── Config endpoints ───────────────────────────────────────────────────────────

@router.get(
    "/config/difficulty-profiles",
    response_model=list[DifficultyProfileResponse],
    summary="[Config] List all difficulty profile rows",
)
def list_difficulty_profiles(
    db: Session = Depends(get_db),
    _: User = Depends(get_admin_user),
) -> list[DifficultyProfileResponse]:
    rows = db.query(DifficultyProfile).order_by(
        DifficultyProfile.category, DifficultyProfile.phase
    ).all()
    return [DifficultyProfileResponse.model_validate(r) for r in rows]


@router.get(
    "/config/progression-tiers",
    response_model=list[ProgressionTierResponse],
    summary="[Config] List all progression tier rows",
)
def list_progression_tiers(
    db: Session = Depends(get_db),
    _: User = Depends(get_admin_user),
) -> list[ProgressionTierResponse]:
    rows = db.query(ProgressionTier).order_by(ProgressionTier.level_min).all()
    return [ProgressionTierResponse.model_validate(r) for r in rows]


@router.get(
    "/config/penalty-tiers",
    response_model=list[PenaltyTierResponse],
    summary="[Config] List all penalty tier rows",
)
def list_penalty_tiers(
    db: Session = Depends(get_db),
    _: User = Depends(get_admin_user),
) -> list[PenaltyTierResponse]:
    rows = db.query(PenaltyTier).order_by(
        PenaltyTier.phase, PenaltyTier.difficulty_chosen
    ).all()
    return [PenaltyTierResponse.model_validate(r) for r in rows]


@router.get(
    "/config/templates",
    response_model=list[QuestTemplateResponse],
    summary="[Config] List all quest templates",
)
def list_quest_templates(
    category: Optional[str] = Query(None),
    tier: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    _: User = Depends(get_admin_user),
) -> list[QuestTemplateResponse]:
    q = db.query(QuestTemplate)
    if category:
        q = q.filter(QuestTemplate.category == category.lower())
    if tier:
        q = q.filter(QuestTemplate.tier == tier.lower())
    rows = q.order_by(QuestTemplate.category, QuestTemplate.tier, QuestTemplate.phase).all()
    return [QuestTemplateResponse.model_validate(r) for r in rows]
