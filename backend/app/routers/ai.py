"""AI Quest Generation API — Solo Leveling Style Goal → Quest Chain."""

import logging
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

from app.db.database import get_db
from app.dependencies.auth import get_current_user
from app.models.user import User
from app.models.quest import Quest, QuestStatus, QuestType, Difficulty, StatType
from app.schemas.ai import (
    GoalGenerateRequest,
    GoalAnalysisResponse,
    GeneratedTaskSchema,
    CustomXPRequest,
    CustomXPResponse,
)
from app.services.ai_service import generate_goal_tasks, AITaskService
from app.config import get_settings

router = APIRouter()


def _difficulty_to_enum(d: str) -> Difficulty:
    try:
        return Difficulty(d.lower())
    except ValueError:
        return Difficulty.MEDIUM


def _stat_to_enum(s: str) -> StatType:
    # Map Solo Leveling stat aliases back to DB enum values
    alias_map = {
        "focus": "mana",
        "discipline": "strength",
        "energy": "vitality",
        "consistency": "charisma",
    }
    s = alias_map.get(s.lower(), s.lower())
    try:
        return StatType(s)
    except ValueError:
        return StatType.INTELLIGENCE


@router.post(
    "/generate",
    response_model=GoalAnalysisResponse,
    summary="[ AI ] Analyze goal and generate quest chain",
)
def generate_quests_for_goal(
    request: GoalGenerateRequest,
    current_user: User = Depends(get_current_user),
):
    """
    Submit a real-world goal in plain text. The system analyzes it,
    detects category and difficulty, and returns a structured 4-week
    quest chain with XP values, stat bonuses, and time estimates.
    """
    settings = get_settings()
    analysis = generate_goal_tasks(request.goal, settings.OPENAI_API_KEY, settings.GROQ_API_KEY)

    tasks = [
        GeneratedTaskSchema(
            title=t.title,
            description=t.description,
            difficulty=t.difficulty,
            primary_stat=t.primary_stat,
            base_xp_reward=t.base_xp_reward,
            skill_points=t.skill_points,
            time_limit_minutes=t.time_limit_minutes,
            week=t.week,
            day_suggestion=t.day_suggestion,
            rationale=t.rationale,
        )
        for t in analysis.tasks
    ]

    return GoalAnalysisResponse(
        goal_text=analysis.goal_text,
        category=analysis.category,
        subcategory=analysis.subcategory,
        difficulty_level=analysis.difficulty_level,
        estimated_weeks=analysis.estimated_weeks,
        primary_stat=analysis.primary_stat,
        secondary_stat=analysis.secondary_stat,
        system_message=analysis.system_message,
        tasks=tasks,
        xp_summary=analysis.xp_summary,
    )


@router.post(
    "/generate-and-save",
    summary="[ AI ] Generate quest chain and save to Quest Board",
)
def generate_and_save_quests(
    request: GoalGenerateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Generate quests for a goal AND immediately create them in the
    database so they appear on the Quest Board.
    """
    settings = get_settings()
    try:
        analysis = generate_goal_tasks(request.goal, settings.OPENAI_API_KEY, settings.GROQ_API_KEY)
        created = []

        for t in analysis.tasks:
            quest = Quest(
                user_id=current_user.id,
                title=t.title,
                description=t.description,
                quest_type=QuestType.CUSTOM,
                difficulty=_difficulty_to_enum(t.difficulty),
                primary_stat=_stat_to_enum(t.primary_stat),
                base_xp_reward=t.base_xp_reward,
                coin_reward=0,
                bonus_skill_points=t.skill_points,
                penalty_xp=int(t.base_xp_reward * 0.2),
                penalty_hp=int(t.base_xp_reward * 0.05),
                mp_cost=5,
                auto_generated=True,
                status=QuestStatus.PENDING,
            )
            db.add(quest)
            created.append(t.title)

        db.commit()

        return {
            "message": f"[ SYSTEM ] {len(created)} quests accepted. Your trial begins now.",
            "quests_created": len(created),
            "category": analysis.category,
            "system_message": analysis.system_message,
            "total_xp_available": analysis.xp_summary.get("total_xp_available", 0),
            "estimated_levels_gained": analysis.xp_summary.get("estimated_levels_gained", 1),
            "quest_titles": created,
        }
    except Exception as e:
        db.rollback()
        logger.exception("generate-and-save failed")
        raise HTTPException(status_code=500, detail="Failed to save quests. Please try again.")


@router.post(
    "/calculate-xp",
    response_model=CustomXPResponse,
    summary="[ AI ] Calculate XP for a custom task",
)
def calculate_task_xp(
    request: CustomXPRequest,
    current_user: User = Depends(get_current_user),
):
    """
    Submit a custom task description. The AI analyzes it and recommends
    appropriate XP, coins, and stat assignments.
    """
    result = AITaskService.calculate_custom_xp(
        title=request.title,
        description=request.description,
        difficulty=request.difficulty,
        estimated_minutes=request.estimated_minutes,
        category_hint=request.category_hint,
    )
    return CustomXPResponse(**result)
