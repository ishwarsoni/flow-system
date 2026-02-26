"""Quest API router — create, list, complete, fail, GENERATE quests."""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import and_
from datetime import datetime, date, timedelta, UTC
from typing import Optional

from app.db.database import get_db
from app.models.user import User
from app.models.quest import Quest, QuestStatus, QuestType, Difficulty, StatType, VerificationType
from app.models.daily_progress import DailyProgress
from app.models.game_config import DEFAULT_CONFIG
from app.schemas.quest import (
    QuestCreateRequest, QuestResponse, QuestActionResponse, PaginatedQuestResponse,
    AnalyzeQuestRequest, AnalyzeQuestResponse, MetricsSubmitRequest, MetricsSubmitResponse,
    GenerateQuestRequest, GenerateQuestResponse, QuestTemplateResponse,
)
from app.dependencies.auth import get_current_user
from app.services.progression_service import ProgressionService
from app.services.daily_reset_service import apply_midnight_penalties
from app.services.difficulty_engine import DifficultyEngine, VERIFICATION_REQUIREMENTS, DURATION_CAPS
from app.services.quest_rules_service import quest_rules_service
from app.services.quest_generator import (
    QuestGenerator, GenerationError, CooldownActiveError,
    WeeklyLimitError, NoTemplateError, InvalidRequestError,
    DuplicateTemplateError, DomainAlreadyAssignedError, TemplateCooldownError,
)
from app.core.exceptions import FLOWException

router = APIRouter()


def _map_difficulty(val: str) -> Difficulty:
    try:
        return Difficulty(val.lower())
    except ValueError:
        return Difficulty.EASY


def _map_stat(val: str) -> StatType:
    try:
        return StatType(val.lower())
    except ValueError:
        return StatType.STRENGTH


# ══════════════════════════════════════════════════════════════════════════════
#  TEMPLATE-BASED GENERATION ENDPOINTS
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/templates", response_model=list[QuestTemplateResponse])
async def list_templates(
    domain: Optional[str] = Query(None, description="Filter by domain"),
    difficulty: Optional[str] = Query(None, description="Filter by difficulty"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List available quest templates. Frontend uses this to show domain quest boards.

    No static data — everything loads from the database.
    """
    templates = QuestGenerator.list_templates(db, domain=domain, difficulty=difficulty)
    return [QuestTemplateResponse.model_validate(t) for t in templates]


@router.post("/generate", response_model=GenerateQuestResponse, status_code=status.HTTP_201_CREATED)
async def generate_quest(
    request: GenerateQuestRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Generate a quest from a template. This is the ONLY way to create system quests.

    Pipeline: select template → check cooldown → check weekly limit → create quest.
    Direct insert into user_quests is forbidden. All quests originate from templates.
    """
    try:
        quest = QuestGenerator.generate_quest(
            db=db,
            user_id=current_user.id,
            domain=request.domain,
            difficulty=request.difficulty,
        )
        db.commit()
        db.refresh(quest)

        tier_label = request.difficulty.upper()
        domain_label = request.domain.upper()
        return GenerateQuestResponse(
            quest=QuestResponse.model_validate(quest),
            template_id=quest.template_id,
            message=f"[ SYSTEM ] {tier_label} {domain_label} quest generated. Prove your effort.",
        )

    except CooldownActiveError as e:
        raise HTTPException(status_code=429, detail=str(e))
    except WeeklyLimitError as e:
        raise HTTPException(status_code=429, detail=str(e))
    except NoTemplateError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except InvalidRequestError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except GenerationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Quest generation failed: {str(e)}")


@router.post("/generate-daily", status_code=status.HTTP_201_CREATED)
async def generate_daily_quests(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Generate balanced daily quests for the current user.

    Picks domains and difficulties based on player level.
    Respects cooldowns and limits. Skips domains that fail.
    """
    try:
        quests = QuestGenerator.generate_daily_quests(db, current_user.id)
        db.commit()

        return {
            "quests_created": len(quests),
            "quests": [QuestResponse.model_validate(q) for q in quests],
            "message": f"[ SYSTEM ] {len(quests)} daily quests generated. Begin.",
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Daily generation failed: {str(e)}")


# ══════════════════════════════════════════════════════════════════════════════
#  EXISTING ENDPOINTS
# ══════════════════════════════════════════════════════════════════════════════

@router.post("/analyze", response_model=AnalyzeQuestResponse)
async def analyze_quest(
    request: AnalyzeQuestRequest,
    current_user: User = Depends(get_current_user),
):
    """Pure AI analysis — returns difficulty, stat, XP suggestion + SL title/description.
    No database write. Frontend calls this on a 500ms debounce as the user types."""
    from app.services.ai_service import AITaskService

    minutes = request.estimated_minutes or 30
    category = AITaskService.detect_category(f"{request.title} {request.description or ''}")
    suggested_diff = AITaskService.suggest_difficulty(request.title, request.description or "", minutes)
    ai = AITaskService.calculate_custom_xp(
        title=request.title,
        description=request.description or "",
        difficulty=suggested_diff,
        estimated_minutes=minutes,
    )

    return AnalyzeQuestResponse(
        recommended_difficulty=suggested_diff,
        recommended_primary_stat=ai["primary_stat"],
        recommended_xp=ai["recommended_xp"],
        recommended_sp=ai["recommended_sp"],
        category_detected=ai["category_detected"],
        system_message=ai["system_message"],
        sl_title=ai["sl_title"],
        sl_description=ai["sl_description"],
        xp_breakdown=ai["xp_breakdown"],
    )


@router.post("/create", response_model=QuestActionResponse, status_code=status.HTTP_201_CREATED)
async def create_quest(
    request: QuestCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create a custom quest.

    FLOW Rules enforced:
    - Vague wording forbidden (all tiers)
    - Duration caps per tier (no quest > 4h)
    - Metrics required for Hard/Extreme
    - All quests must be verifiable
    - If a quest cannot prove effort, it is invalid
    """
    difficulty = _map_difficulty(request.difficulty)
    primary_stat = _map_stat(request.primary_stat)

    # ── Map tier for rule lookups ──────────────────────────────────────────────
    tier_label = difficulty.value
    if tier_label in ("medium", "intermediate"):
        tier_label = "intermediate"

    # ── FLOW Rule: Validate quest title — no vague wording (ALL tiers) ────────
    valid, reason = DifficultyEngine.validate_quest_title(request.title, tier_label)
    if not valid:
        raise HTTPException(status_code=422, detail=reason)

    # ── FLOW Rule: Validate proof of effort is possible ───────────────────────
    valid, reason = DifficultyEngine.verify_effort_provable(
        tier=tier_label,
        metrics_required=request.metrics_required,
        metrics_definition=getattr(request, 'metrics_definition', None),
        description=request.description or "",
    )
    if not valid:
        raise HTTPException(status_code=422, detail=reason)

    # ── Validate duration against tier hard limits ─────────────────────────────
    if request.estimated_minutes:
        try:
            DifficultyEngine.validate_duration(
                tier=tier_label,
                duration_minutes=request.estimated_minutes,
                is_daily=False,   # custom quests are not auto-daily
            )
        except ValueError as e:
            raise HTTPException(status_code=422, detail=str(e))

    # ── Determine verification type based on tier ──────────────────────────────
    verification_type = (
        VerificationType.METRICS if tier_label in ("hard", "extreme")
        else VerificationType.LOG
    )

    # Let AI judge XP and SP based on title, description, difficulty, and time estimate
    from app.services.ai_service import AITaskService
    from app.models.game_config import GameConfig
    def cfg(key):
        c = db.query(GameConfig).filter(GameConfig.key == key).first()
        return c.value if c else DEFAULT_CONFIG.get(key, 0)

    ai_result = AITaskService.calculate_custom_xp(
        title=request.title,
        description=request.description or "",
        difficulty=difficulty.value,
        estimated_minutes=request.estimated_minutes or 30,
    )
    base_xp = ai_result["recommended_xp"]
    bonus_sp = ai_result["recommended_sp"]
    mp_cost = int(cfg(f"mp_cost_{difficulty.value}"))
    penalty_xp = int(base_xp * cfg("xp_failure_penalty"))
    penalty_hp = int(base_xp * 0.1)

    expires_at = None
    if request.time_limit_minutes:
        expires_at = datetime.now(UTC) + timedelta(minutes=request.time_limit_minutes)

    # ── Enforce metrics_required for Hard/Extreme automatically ────────────────
    metrics_required = request.metrics_required
    if tier_label in ("hard", "extreme"):
        metrics_required = True   # FLOW Rule: Hard + Extreme require metrics

    # ── Performance multiplier from tier ───────────────────────────────────────
    TIER_MULTIPLIERS = {
        "easy": 1.0, "intermediate": 1.5, "hard": 2.0, "extreme": 3.0,
        "trivial": 0.5, "medium": 1.5,  # legacy compat
    }
    perf_mult = TIER_MULTIPLIERS.get(tier_label, 1.0)

    tier_defaults = DifficultyEngine.defaults_for_tier(tier_label)

    quest = Quest(
        user_id=current_user.id,
        title=request.title,
        description=request.description,
        quest_type=QuestType.CUSTOM,
        difficulty=difficulty,
        primary_stat=primary_stat,
        domain=request.domain,
        verification_type=verification_type,
        base_xp_reward=base_xp,
        coin_reward=0,
        bonus_skill_points=bonus_sp,
        penalty_xp=penalty_xp,
        penalty_hp=penalty_hp,
        mp_cost=mp_cost,
        time_limit_minutes=request.time_limit_minutes,
        max_duration_minutes=DURATION_CAPS.get(tier_label, DURATION_CAPS["hard"]),
        performance_multiplier=perf_mult,
        expires_at=expires_at,
        status=QuestStatus.PENDING,
        auto_generated=False,
        is_manual=True,
        metrics_required=metrics_required,
        cooldown_hours=tier_defaults["cooldown_hours"],
        weekly_limit=tier_defaults["weekly_limit"],
    )

    db.add(quest)
    db.commit()
    db.refresh(quest)

    from app.services.player_service import PlayerService
    stats_profile = PlayerService.get_player_profile(db, current_user.id)

    return QuestActionResponse(
        quest=QuestResponse.model_validate(quest),
        level=stats_profile["level"],
        xp_current=stats_profile["xp_current"],
        xp_to_next_level=stats_profile["xp_to_next_level"],
        hp_current=stats_profile["hp_current"],
        mp_current=stats_profile["mp_current"],
    )


@router.get("", response_model=PaginatedQuestResponse)
async def list_quests(
    quest_status: str = Query(None, alias="status"),
    quest_type: str = Query(None, alias="type"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List quests with optional status and type filters."""
    # ── Midnight reset: auto-fail any stale pending quests ──
    apply_midnight_penalties(db, current_user.id)

    # ── Lazy daily generation: if no active quests created today, auto-generate ──
    today_start = datetime.combine(date.today(), datetime.min.time())
    todays_active = (
        db.query(Quest)
        .filter(
            Quest.user_id == current_user.id,
            Quest.status.in_([QuestStatus.PENDING, QuestStatus.IN_PROGRESS]),
            Quest.created_at >= today_start,
        )
        .count()
    )
    if todays_active == 0:
        try:
            daily = QuestGenerator.generate_daily_quests(db, current_user.id)
            if daily:
                db.commit()
                import logging
                logging.getLogger(__name__).info(
                    f"Auto-generated {len(daily)} daily quests for user {current_user.id}"
                )
        except Exception:
            db.rollback()  # fail silently — user still sees their quest list

    query = db.query(Quest).filter(Quest.user_id == current_user.id)

    if quest_status:
        try:
            s = QuestStatus(quest_status.lower())
            query = query.filter(Quest.status == s)
        except ValueError:
            pass

    if quest_type:
        try:
            t = QuestType(quest_type.lower())
            query = query.filter(Quest.quest_type == t)
        except ValueError:
            pass

    total = query.count()
    quests = query.order_by(Quest.created_at.asc()).offset(offset).limit(limit).all()

    return PaginatedQuestResponse(
        items=[QuestResponse.model_validate(q) for q in quests],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post("/{quest_id}/complete", response_model=QuestActionResponse)
async def complete_quest(
    quest_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Complete a quest — earn XP, coins, stat gains, pay MP.

    Completion is REJECTED if:
    - The quest requires metrics that have not been submitted
    - An active cooldown is blocking the tier
    - The weekly extreme limit has been reached
    """
    # ── Pre-completion rules check ─────────────────────────────────────────────
    quest = db.query(Quest).filter(
        Quest.id == quest_id,
        Quest.user_id == current_user.id,
    ).first()
    if quest:
        allowed, reason = quest_rules_service.validate_completion(quest, db)
        if not allowed:
            raise HTTPException(status_code=422, detail=reason)

    try:
        apply_midnight_penalties(db, current_user.id)
        stats, quest, progress = ProgressionService.complete_quest(db, current_user.id, quest_id)
        return QuestActionResponse(
            quest=QuestResponse.model_validate(quest),
            xp_earned=progress["xp_earned"],
            skill_points_earned=progress["skill_points_earned"],
            mp_cost=progress["mp_cost"],
            stat_changes=progress["stat_gains"],
            level=progress["level"],
            xp_current=progress["xp_current"],
            xp_to_next_level=progress["xp_to_next_level"],
            hp_current=progress["hp_current"],
            mp_current=progress["mp_current"],
            fatigue=progress["fatigue"],
            streak_days=progress.get("streak_days"),
            streak_milestone=progress.get("streak_milestone"),
            rank_event=progress.get("rank_event"),
        )
    except FLOWException as e:
        raise HTTPException(status_code=e.status_code, detail=str(e))


@router.post("/{quest_id}/submit-metrics", response_model=MetricsSubmitResponse)
async def submit_quest_metrics(
    quest_id: int,
    request: MetricsSubmitRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Submit verifiable proof/metrics for a metrics-required quest.

    Call this BEFORE /complete on any quest where metrics_required=True.
    Rejected if metrics are empty or all-zero.
    """
    quest = db.query(Quest).filter(
        Quest.id == quest_id,
        Quest.user_id == current_user.id,
    ).first()
    if not quest:
        raise HTTPException(status_code=404, detail="Quest not found.")
    if quest.status not in (QuestStatus.PENDING, QuestStatus.IN_PROGRESS):
        raise HTTPException(status_code=400, detail="Quest is not active — cannot submit metrics.")

    valid, reason = quest_rules_service.validate_metrics_submission(quest, request.metrics)
    if not valid:
        raise HTTPException(status_code=422, detail=reason)

    quest.metrics_submitted = request.metrics
    quest.metrics_verified = None   # Pending — auto-accepted unless flagged
    db.commit()

    return MetricsSubmitResponse(
        quest_id=quest_id,
        metrics_submitted=request.metrics,
        metrics_verified=None,
        message="Metrics recorded. Quest is now eligible for completion.",
    )


@router.delete("/{quest_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_quest(
    quest_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Delete / remove a quest. Any quest can be removed by the user."""
    quest = db.query(Quest).filter(
        Quest.id == quest_id,
        Quest.user_id == current_user.id,
    ).first()
    if not quest:
        raise HTTPException(status_code=404, detail="[ SYSTEM ] Quest not found in your dungeon registry.")
    db.delete(quest)
    db.commit()


@router.post("/{quest_id}/fail", response_model=QuestActionResponse)
async def fail_quest(
    quest_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Fail a quest — lose XP, take HP damage, stat penalties."""
    try:
        apply_midnight_penalties(db, current_user.id)
        stats, quest, penalty = ProgressionService.fail_quest(db, current_user.id, quest_id)
        return QuestActionResponse(
            quest=QuestResponse.model_validate(quest),
            xp_penalty=penalty["xp_penalty"],
            hp_damage=penalty["hp_damage"],
            stat_changes=penalty["stat_penalties"],
            level=penalty["level"],
            xp_current=penalty["xp_current"],
            xp_to_next_level=penalty["xp_to_next_level"],
            hp_current=penalty["hp_current"],
            mp_current=penalty["mp_current"],
            rank_event=penalty.get("rank_event"),
        )
    except FLOWException as e:
        raise HTTPException(status_code=e.status_code, detail=str(e))
