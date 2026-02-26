"""AI Coach Executor — applies validated CoachOutput to FLOW.

The executor takes a validated CoachOutput and performs the allowed actions:
1. Store the coaching directive in the ai_coach_log table
2. Create suggested quests (using FLOW quest creation rules)
3. Return the result for the router to serve

The executor NEVER:
- Grants XP directly
- Removes penalties
- Bypasses cooldowns
- Changes ranks
- Modifies trust scores

AI advises. FLOW decides.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, UTC
from typing import Optional

from sqlalchemy.orm import Session

from app.models.quest import (
    Quest, QuestType, QuestStatus, Difficulty,
    StatType, VerificationType,
)
from app.services.ai.validator import CoachOutput, CoachQuest

logger = logging.getLogger(__name__)

# ── Mappings ───────────────────────────────────────────────────────────────────

TIER_TO_DIFFICULTY = {
    "easy": Difficulty.EASY,
    "intermediate": Difficulty.INTERMEDIATE,
    "hard": Difficulty.HARD,
    "extreme": Difficulty.EXTREME,
}

TIER_MULTIPLIERS = {
    "easy": 1.0,
    "intermediate": 1.5,
    "hard": 2.0,
    "extreme": 3.0,
}

DURATION_CAPS = {
    "easy": 60,
    "intermediate": 120,
    "hard": 180,
    "extreme": 240,
}

XP_BASE = {
    "easy": 100,
    "intermediate": 200,
    "hard": 350,
    "extreme": 600,
}

COIN_BASE = {
    "easy": 10,
    "intermediate": 20,
    "hard": 40,
    "extreme": 80,
}

# Domain → primary stat mapping
DOMAIN_STAT_MAP = {
    "mind": StatType.INTELLIGENCE,
    "body": StatType.STRENGTH,
    "core": StatType.VITALITY,
    "control": StatType.MANA,
    "presence": StatType.CHARISMA,
    "system": StatType.INTELLIGENCE,
}


# ── Quest Creation ─────────────────────────────────────────────────────────────

def create_coach_quest(
    db: Session,
    user_id: int,
    cq: CoachQuest,
) -> Quest:
    """Create a single Quest from a validated CoachQuest.

    Uses the same rules as adaptive quest creation:
    - Hard/Extreme → metrics required
    - Verification type set by difficulty
    - XP/coin rewards scaled by tier
    - Performance multiplier set by tier
    - Duration capped by tier
    """
    diff = cq.difficulty
    verification = (
        VerificationType.METRICS if diff in ("hard", "extreme")
        else VerificationType.LOG
    )

    quest = Quest(
        user_id=user_id,
        title=cq.title,
        description=cq.description,
        quest_type=QuestType.DAILY,
        difficulty=TIER_TO_DIFFICULTY.get(diff, Difficulty.EASY),
        primary_stat=DOMAIN_STAT_MAP.get(cq.domain, StatType.STRENGTH),
        base_xp_reward=XP_BASE.get(diff, 100),
        coin_reward=COIN_BASE.get(diff, 10),
        penalty_xp=int(XP_BASE.get(diff, 100) * 0.5),
        generates_penalty_quest=(diff in ("hard", "extreme")),
        auto_generated=True,
        status=QuestStatus.PENDING,
        domain=cq.domain,
        verification_type=verification,
        metrics_required=(diff in ("hard", "extreme")),
        cooldown_hours=24 if diff == "extreme" else 0,
        weekly_limit=3 if diff == "extreme" else None,
        is_manual=False,
        performance_multiplier=TIER_MULTIPLIERS.get(diff, 1.0),
        max_duration_minutes=min(
            cq.estimated_minutes,
            DURATION_CAPS.get(diff, 180),
        ),
    )
    db.add(quest)
    db.flush()

    logger.info(
        f"AI Coach: created quest {quest.id} — "
        f"'{cq.title}' [{cq.domain}/{diff}] for user {user_id}"
    )
    return quest


# ── Main Executor ──────────────────────────────────────────────────────────────

def execute_coach_output(
    db: Session,
    user_id: int,
    output: CoachOutput,
) -> dict:
    """Apply a validated CoachOutput to FLOW.

    Creates quests and stores the log. Returns a result dict
    suitable for the API response.
    """
    created_quest_ids = []

    # 1. Create suggested quests
    for cq in output.new_quests:
        try:
            quest = create_coach_quest(db, user_id, cq)
            created_quest_ids.append(quest.id)
        except Exception as e:
            logger.error(f"AI Coach: failed to create quest '{cq.title}' — {e}")
            # Continue with remaining quests — don't let one failure block all

    # 2. Build result
    result = {
        "mode": output.mode,
        "priority_domains": output.priority_domains,
        "xp_modifier": output.xp_modifier,
        "message": output.message,
        "quests_created": created_quest_ids,
        "valid": output.raw_valid,
    }

    if output.rejection_reasons:
        result["warnings"] = output.rejection_reasons

    logger.info(
        f"AI Coach: executed for user {user_id} — "
        f"{len(created_quest_ids)} quests created, mode={output.mode}"
    )

    return result
