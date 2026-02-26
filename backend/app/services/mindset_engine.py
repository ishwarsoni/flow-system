"""MindsetEngine — hidden behavioral scoring system.

All score mutations happen here. Service is stateless (no __init__ required);
call class methods directly.

Score mechanics summary
-----------------------
Choosing hard          →  +15  (before modifiers)
Choosing intermediate  →   +5
Choosing easy          →   -5

Completing hard        →  +25
Failing hard           →  -20  (but +10 on retry success)
Completing easy        →   +2
Failing easy           →  -15  (no excuse when it's easy)

Consecutive non-hard
  days ≥ threshold     →  daily decay applied by pulse() caller
  score decays         →  -(days_over_threshold * 5) per pulse call

Score is always clamped 0–1000.
"""

from __future__ import annotations

from datetime import datetime, timedelta, UTC
from typing import Optional

from sqlalchemy.orm import Session

from app.models.mindset_score import MindsetScore
from app.models.progression_tier import ProgressionTier


# ── Delta constants ────────────────────────────────────────────────────────────
# All tunable — no magic numbers in callers.

MINDSET_DELTA = {
    # Choice deltas
    "choose_hard": 15.0,
    "choose_intermediate": 5.0,
    "choose_easy": -5.0,
    # Completion deltas
    "complete_hard": 25.0,
    "complete_intermediate": 8.0,
    "complete_easy": 2.0,
    # Failure deltas
    "fail_hard": -20.0,
    "fail_intermediate": -10.0,
    "fail_easy": -15.0,         # Failing something "easy" is psychologically damaging
    # Recovery bonus
    "retry_hard_success": 10.0,
    # Consistency streak bonus (per day, added during pulse)
    "streak_day_bonus": 3.0,
    # Decay per day over the comfort-zone threshold
    "non_hard_day_decay": -5.0,
}

SCORE_MIN = 0.0
SCORE_MAX = 1000.0


def _clamp(value: float) -> float:
    return max(SCORE_MIN, min(SCORE_MAX, value))


class MindsetEngine:
    """Stateless service — interact via class methods."""

    # ── Bootstrap ─────────────────────────────────────────────────────────────

    @staticmethod
    def get_or_create(user_id: int, db: Session) -> MindsetScore:
        ms = db.query(MindsetScore).filter(MindsetScore.user_id == user_id).first()
        if not ms:
            ms = MindsetScore(user_id=user_id)
            db.add(ms)
            db.flush()
        return ms

    # ── Score update helpers ───────────────────────────────────────────────────

    @staticmethod
    def _apply_delta(ms: MindsetScore, delta: float, db: Session) -> float:
        """Apply delta, clamp, persist, return new score."""
        ms.score = _clamp(ms.score + delta)
        ms.updated_at = datetime.now(UTC)
        db.flush()
        return ms.score

    # ── Choice recording ──────────────────────────────────────────────────────

    @classmethod
    def record_choice(
        cls,
        user_id: int,
        chosen_tier: str,
        db: Session,
    ) -> tuple[float, float]:
        """Record that the player chose a tier.

        Returns (delta_applied, new_score).
        """
        ms = cls.get_or_create(user_id, db)
        now = datetime.now(UTC)

        delta_key = {
            "hard": "choose_hard",
            "intermediate": "choose_intermediate",
            "easy": "choose_easy",
        }.get(chosen_tier, "choose_easy")

        delta = MINDSET_DELTA[delta_key]

        # Update counters
        if chosen_tier == "hard":
            ms.hard_choices += 1
            ms.consecutive_non_hard_days = 0
            ms.last_hard_chosen_at = now
            ms.force_challenge_active = False
            ms.force_challenge_until = None
        elif chosen_tier == "intermediate":
            ms.intermediate_choices += 1
        else:
            ms.easy_choices += 1

        new_score = cls._apply_delta(ms, delta, db)
        return delta, new_score

    # ── Outcome recording ─────────────────────────────────────────────────────

    @classmethod
    def record_outcome(
        cls,
        user_id: int,
        chosen_tier: str,
        success: bool,
        was_retry: bool = False,
        db: Session = None,
    ) -> tuple[float, float]:
        """Record quest completion or failure.

        Returns (delta_applied, new_score).
        """
        ms = cls.get_or_create(user_id, db)

        if success:
            delta_key = {
                "hard": "complete_hard",
                "intermediate": "complete_intermediate",
                "easy": "complete_easy",
            }.get(chosen_tier, "complete_easy")
            delta = MINDSET_DELTA[delta_key]

            # Update counters
            if chosen_tier == "hard":
                ms.hard_completions += 1
                if was_retry:
                    ms.hard_retry_successes += 1
                    delta += MINDSET_DELTA["retry_hard_success"]
            elif chosen_tier == "intermediate":
                ms.intermediate_completions += 1
            else:
                ms.easy_completions += 1

            # Consistency streak bonus
            delta += MINDSET_DELTA["streak_day_bonus"]

            # Exit recovery mode if applicable
            if ms.recovery_mode:
                ms.recovery_quests_completed += 1
                if ms.recovery_quests_completed >= ms.recovery_quests_required:
                    ms.recovery_mode = False
                    ms.recovery_quests_required = 0
                    ms.recovery_quests_completed = 0
                    ms.recovery_deadline = None
        else:
            delta_key = {
                "hard": "fail_hard",
                "intermediate": "fail_intermediate",
                "easy": "fail_easy",
            }.get(chosen_tier, "fail_easy")
            delta = MINDSET_DELTA[delta_key]

            if chosen_tier == "hard":
                ms.hard_failures += 1
            elif chosen_tier == "intermediate":
                ms.intermediate_failures += 1
            else:
                ms.easy_failures += 1

        new_score = cls._apply_delta(ms, delta, db)
        return delta, new_score

    # ── Daily pulse ───────────────────────────────────────────────────────────

    @classmethod
    def daily_pulse(cls, user_id: int, completed_any: bool, db: Session) -> float:
        """Called once per day (e.g. during daily reset).

        - Updates consecutive_non_hard_days.
        - Applies decay if player is stagnating.
        - Returns new score.
        """
        ms = cls.get_or_create(user_id, db)
        now = datetime.now(UTC)
        threshold = cls._get_force_challenge_threshold(db)

        if completed_any:
            ms.consistency_streak += 1
        else:
            ms.consistency_streak = 0

        # Check if today had no hard quest chosen
        last_hard = ms.last_hard_chosen_at
        if not last_hard or (now - last_hard).days >= 1:
            ms.consecutive_non_hard_days += 1
        else:
            ms.consecutive_non_hard_days = 0

        # Apply decay if over threshold
        delta = 0.0
        if ms.consecutive_non_hard_days > threshold:
            over = ms.consecutive_non_hard_days - threshold
            delta = MINDSET_DELTA["non_hard_day_decay"] * over
            ms.score = _clamp(ms.score + delta)

        ms.updated_at = now
        db.flush()
        return ms.score

    # ── Force-challenge check ──────────────────────────────────────────────────

    @classmethod
    def check_and_set_force_challenge(cls, user_id: int, db: Session) -> bool:
        """Activate force-challenge if player has avoided hard for too long.

        Returns True if force-challenge is now active.
        """
        ms = cls.get_or_create(user_id, db)
        threshold = cls._get_force_challenge_threshold(db)

        if ms.consecutive_non_hard_days >= threshold and not ms.force_challenge_active:
            ms.force_challenge_active = True
            ms.force_challenge_until = datetime.now(UTC) + timedelta(hours=24)
            db.flush()

        return ms.force_challenge_active

    @staticmethod
    def _get_force_challenge_threshold(db: Session) -> int:
        """Pull trigger threshold from DB (defaults to 5 if not configured)."""
        tier = db.query(ProgressionTier).filter(
            ProgressionTier.phase == "entry",
            ProgressionTier.is_active == True,
        ).first()
        return tier.force_challenge_trigger_days if tier else 5

    # ── Activation of recovery mode ───────────────────────────────────────────

    @classmethod
    def activate_recovery_mode(
        cls,
        user_id: int,
        db: Session,
        required_count: int = 3,
        window_hours: int = 48,
    ) -> MindsetScore:
        ms = cls.get_or_create(user_id, db)
        if not ms.recovery_mode:
            ms.recovery_mode = True
            ms.recovery_quests_required = required_count
            ms.recovery_quests_completed = 0
            ms.recovery_deadline = datetime.now(UTC) + timedelta(hours=window_hours)
            db.flush()
        return ms

    # ── Queries ───────────────────────────────────────────────────────────────

    @classmethod
    def get_mindset_score(cls, user_id: int, db: Session) -> MindsetScore:
        return cls.get_or_create(user_id, db)
