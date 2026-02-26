"""AdaptivePushService — comfort-zone detection, force-challenge management,
and recovery quest creation.

This service is called:
  • On each daily reset (daily_pulse) to update streaks and decay mindset.
  • On quest failure to trigger recovery when required.
  • By the router to expose force-challenge status to the frontend.

Recovery quest logic
--------------------
After a major failure the system does NOT let the player reset easily.
They must complete N intermediate quests within a time window.
Failing the recovery escalates the penalty tier.
"""

from __future__ import annotations

from datetime import datetime, timedelta, UTC
from typing import Optional

from sqlalchemy.orm import Session

from app.models.mindset_score import MindsetScore
from app.models.quest import Quest, QuestType, QuestStatus, Difficulty as QuestDifficulty, StatType
from app.models.user_stats import UserStats
from app.services.mindset_engine import MindsetEngine
from app.schemas.adaptive_quest import (
    ForceChallengeStatusResponse,
    RecoveryQuestResponse,
)


class AdaptivePushService:
    """Management layer for force-challenge and recovery mechanics."""

    # ── Daily pulse ────────────────────────────────────────────────────────────

    @classmethod
    def daily_pulse(cls, user_id: int, db: Session) -> dict:
        """Called once per day by the reset scheduler.

        - Determines if the player completed any quest today.
        - Updates MindsetScore via MindsetEngine.daily_pulse.
        - Checks and activates force-challenge if threshold exceeded.
        - Checks for expired recovery windows and escalates if needed.

        Returns a summary dict.
        """
        stats = db.query(UserStats).filter(UserStats.user_id == user_id).first()
        completed_any = stats.streak_days > 0 if stats else False

        new_score = MindsetEngine.daily_pulse(user_id, completed_any, db)
        force_active = MindsetEngine.check_and_set_force_challenge(user_id, db)

        ms = MindsetEngine.get_or_create(user_id, db)
        recovery_expired = cls._check_recovery_expiry(ms, db)

        return {
            "user_id": user_id,
            "new_mindset_score": new_score,
            "force_challenge_activated": force_active,
            "recovery_window_expired": recovery_expired,
        }

    # ── Recovery expiry check ──────────────────────────────────────────────────

    @staticmethod
    def _check_recovery_expiry(ms: MindsetScore, db: Session) -> bool:
        """If recovery deadline has passed and recovery not completed → escalate."""
        if not ms.recovery_mode or not ms.recovery_deadline:
            return False
        if datetime.now(UTC) < ms.recovery_deadline:
            return False

        # Recovery window expired without completion → escalate
        # Escalation: double remaining required quests, extend window
        remaining = ms.recovery_quests_required - ms.recovery_quests_completed
        if remaining > 0:
            ms.recovery_quests_required = ms.recovery_quests_required + remaining
            ms.recovery_deadline = datetime.now(UTC) + timedelta(hours=48)
            ms.score = max(0.0, ms.score - 50.0)   # Additional mindset penalty
            db.flush()
            return True

        return False

    # ── Force-challenge status ─────────────────────────────────────────────────

    @classmethod
    def get_force_challenge_status(
        cls,
        user_id: int,
        db: Session,
    ) -> ForceChallengeStatusResponse:
        from app.models.progression_tier import ProgressionTier

        ms = MindsetEngine.get_or_create(user_id, db)
        stats = db.query(UserStats).filter(UserStats.user_id == user_id).first()
        phase = "entry"
        if stats:
            phase = "entry" if stats.level <= 10 else ("growth" if stats.level <= 30 else "mastery")

        tier = db.query(ProgressionTier).filter(
            ProgressionTier.phase == phase,
            ProgressionTier.is_active == True,
        ).first()
        threshold = tier.force_challenge_trigger_days if tier else 5

        if ms.force_challenge_active:
            reason = (
                f"You have avoided Hard quests for {ms.consecutive_non_hard_days} consecutive days. "
                "Comfort zone lockout in effect."
            )
        elif ms.consecutive_non_hard_days >= threshold - 1:
            reason = (
                f"Warning: {ms.consecutive_non_hard_days} day(s) without a Hard quest. "
                f"Lockout triggers at {threshold}."
            )
        else:
            reason = "Operating within acceptable parameters."

        return ForceChallengeStatusResponse(
            active=ms.force_challenge_active,
            until=ms.force_challenge_until,
            reason=reason,
            consecutive_non_hard_days=ms.consecutive_non_hard_days,
            trigger_threshold=threshold,
        )

    # ── Recovery quest creation ────────────────────────────────────────────────

    @classmethod
    def create_recovery_quest(
        cls,
        user_id: int,
        db: Session,
        category: str = "study",
    ) -> RecoveryQuestResponse:
        """Instantiate a recovery quest tied to the current recovery mode.

        The quest is assigned a specific 'PENALTY' type so it shows in the
        penalty queue on the frontend.
        """
        ms = MindsetEngine.get_or_create(user_id, db)
        if not ms.recovery_mode:
            raise ValueError("User is not currently in recovery mode.")

        remaining = ms.recovery_quests_required - ms.recovery_quests_completed

        # Create a PENALTY type quest in the existing Quest table
        quest = Quest(
            user_id=user_id,
            title="Rebuild Mode — Recovery Quest",
            description=(
                f"You suffered a major failure. "
                f"Complete {remaining} more intermediate quest(s) within the rebuild window. "
                "Prove you can recover. Failure to comply escalates the penalty."
            ),
            quest_type=QuestType.PENALTY,
            difficulty=QuestDifficulty.MEDIUM,
            primary_stat=StatType.STRENGTH,
            base_xp_reward=150,
            coin_reward=10,
            penalty_xp=300,       # If this recovery quest also fails, the penalty is severe
            generates_penalty_quest=True,
            auto_generated=True,
            status=QuestStatus.PENDING,
            expires_at=ms.recovery_deadline,
        )
        db.add(quest)
        db.flush()

        return RecoveryQuestResponse(
            quest_id=quest.id,
            title=quest.title,
            description=quest.description,
            xp_reward=quest.base_xp_reward,
            required_count=ms.recovery_quests_required,
            completed_count=ms.recovery_quests_completed,
            deadline=ms.recovery_deadline,
            message=(
                f"Rebuild Mode: Complete {remaining} intermediate quest(s) "
                f"by {ms.recovery_deadline.strftime('%Y-%m-%d %H:%M UTC') if ms.recovery_deadline else 'deadline'} "
                "to restore your reputation. "
                "Success restores standing. Failure increases penalty tier."
            ),
        )

    # ── Manual clear (admin / test use) ───────────────────────────────────────

    @classmethod
    def clear_force_challenge(cls, user_id: int, db: Session) -> None:
        ms = MindsetEngine.get_or_create(user_id, db)
        ms.force_challenge_active = False
        ms.force_challenge_until = None
        ms.consecutive_non_hard_days = 0
        db.flush()

    @classmethod
    def clear_recovery_mode(cls, user_id: int, db: Session) -> None:
        ms = MindsetEngine.get_or_create(user_id, db)
        ms.recovery_mode = False
        ms.recovery_quests_required = 0
        ms.recovery_quests_completed = 0
        ms.recovery_deadline = None
        db.flush()
