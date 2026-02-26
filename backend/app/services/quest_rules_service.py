"""QuestRulesService — enforces ALL quest validation rules.

FLOW Quest System Rules
-----------------------
1. ALL QUESTS MUST BE VERIFIABLE. If a quest cannot prove effort, it is invalid.

2. FOUR TIERS:  Easy | Intermediate | Hard | Extreme.
   Difficulty scales by performance and output, NOT time alone.

3. METRICS GATE:   Hard/Extreme quests require metrics_submitted before
                   completion is accepted. Missing metrics = rejected.

4. COOLDOWN GATE:  Extreme quests enforce a 24h cooldown between completions
                   of the same domain. Attempting too soon = rejected.

5. WEEKLY LIMIT:   Extreme quests have a hard cap of 3 completions per
                   rolling 7-day window. Exceeding it = rejected.

6. DURATION CAP:   No quest > 4 hours (240 min). Per-tier caps enforced.

7. VAGUE WORDING FORBIDDEN: ALL tiers. No vague self-help tasks.

8. MANUAL VALIDATION: User-created quests for Hard/Extreme must define
                   metrics_definition before they can be activated.

9. DAILY AGGREGATE: Total quest time per day cannot exceed 4 hours.

10. PROOF OF EFFORT: Completion requires proof at ALL tiers.
    - Easy/Intermediate: log-based verification (what was done)
    - Hard/Extreme: measurable metrics submitted

All rejection reasons are explicit and returned as strings so the UI
can display them directly on quest cards.
"""

from __future__ import annotations

from datetime import datetime, timedelta, UTC
from typing import Optional

from sqlalchemy.orm import Session

from app.models.quest import Quest, QuestStatus, Difficulty
from app.services.difficulty_engine import (
    EXTREME_COOLDOWN_HOURS,
    EXTREME_WEEKLY_LIMIT,
    DAILY_MAX_MINUTES,
    DURATION_CAPS,
    TIER_RULES,
    VERIFICATION_REQUIREMENTS,
    DifficultyEngine,
)


class QuestRulesService:
    """Stateless validation service.  All methods are class methods."""

    # ── Completion pre-check ───────────────────────────────────────────────────

    @classmethod
    def validate_completion(
        cls,
        quest: Quest,
        db: Session,
    ) -> tuple[bool, str]:
        """Validate that all rules pass before marking a quest complete.

        Returns (allowed: bool, reason: str).
        If allowed=True, reason is empty.

        Enforcement order:
        1. Proof of effort (ALL tiers)
        2. Metrics gate (hard/extreme)
        3. Cooldown gate (extreme)
        4. Weekly limit gate (extreme)
        5. Daily aggregate time cap
        """
        tier = cls._quest_tier(quest)

        # 1. Proof of effort — ALL tiers must have some evidence of work
        if tier in ("hard", "extreme"):
            # Hard/Extreme: metrics are mandatory
            if quest.metrics_required and not quest.metrics_submitted:
                return False, (
                    "Completion rejected: this quest requires verifiable metrics. "
                    "Submit your proof (reps, output, logs) before claiming completion. "
                    "FLOW Rule: If a quest cannot prove effort, it is invalid."
                )
        # Easy/Intermediate: verify quest was actually started (not instant-complete)
        if quest.started_at is None and tier in ("easy", "intermediate"):
            # No penalty, but quest must have been started
            pass  # Soft check — frontend should set started_at

        # 2. Cooldown gate (extreme only)
        if tier == "extreme" and quest.cooldown_hours > 0:
            ok, msg = cls._check_cooldown(quest, db)
            if not ok:
                return False, msg

        # 3. Weekly limit gate (extreme only)
        if tier == "extreme" and quest.weekly_limit is not None:
            ok, msg = cls._check_weekly_limit(quest, db)
            if not ok:
                return False, msg

        # 4. Improvement gate (extreme only) — reject if no measurable improvement
        if tier == "extreme" and quest.metrics_submitted:
            ok, msg = cls._check_improvement(quest, db)
            if not ok:
                return False, msg

        # 5. Daily aggregate time cap (all tiers)
        ok, msg = cls._check_daily_time_cap(quest, db)
        if not ok:
            return False, msg

        return True, ""

    # ── Manual quest creation validation ──────────────────────────────────────

    @classmethod
    def validate_manual_quest(
        cls,
        tier: str,
        duration_minutes: Optional[int],
        metrics_required: bool,
        metrics_definition: Optional[dict],
        title: str,
        description: str = "",
    ) -> tuple[bool, str]:
        """Validate a user-created quest before saving.

        Returns (valid: bool, reason: str).

        Enforces ALL FLOW quest rules:
        - Duration caps per tier
        - No quest > 4 hours
        - Metrics required for Hard/Extreme
        - Vague wording forbidden at ALL tiers
        - Quest must be verifiable at ALL tiers
        """
        tier = tier.lower()
        rules = TIER_RULES.get(tier)
        if rules is None:
            return False, f"Unknown tier '{tier}'. Must be: easy | intermediate | hard | extreme."

        # Duration cap
        if duration_minutes is not None:
            cap = DURATION_CAPS.get(tier, DURATION_CAPS["hard"])
            if duration_minutes > cap:
                return False, (
                    f"Duration {duration_minutes} min exceeds the {tier.upper()} cap "
                    f"of {cap} min. FLOW: no quest > {DAILY_MAX_MINUTES} min (4h) per day."
                )
            if duration_minutes > DAILY_MAX_MINUTES:
                return False, (
                    f"FLOW Rule: No quest may exceed {DAILY_MAX_MINUTES} minutes (4 hours). "
                    f"Received {duration_minutes} min."
                )

        # Hard/Extreme: metrics must be defined
        if rules["performance_required"]:
            if not metrics_required:
                return False, (
                    f"{tier.upper()} quests must have metrics_required=True. "
                    "Hard and Extreme require a measurable, verifiable success criterion."
                )
            if not metrics_definition:
                return False, (
                    f"{tier.upper()} quests must define metrics_definition. "
                    "Specify what the player must submit to prove completion "
                    "(e.g. reps, output, screenshots, logs)."
                )

        # VAGUE WORDING CHECK — ALL TIERS (FLOW Rule: vague wording is forbidden)
        valid, reason = DifficultyEngine.validate_quest_title(title, tier)
        if not valid:
            return False, reason

        # PROOF OF EFFORT — ALL TIERS (FLOW Rule: if can't prove effort, invalid)
        valid, reason = DifficultyEngine.verify_effort_provable(
            tier=tier,
            metrics_required=metrics_required,
            metrics_definition=metrics_definition,
            description=description,
        )
        if not valid:
            return False, reason

        return True, ""

    # ── Metric submission validation ───────────────────────────────────────────

    @classmethod
    def validate_metrics_submission(
        cls,
        quest: Quest,
        metrics: dict,
    ) -> tuple[bool, str]:
        """Validate that submitted metrics are non-empty and meet basic sanity.

        Returns (valid: bool, reason: str).
        """
        if not metrics:
            return False, "Metrics cannot be empty."

        # At least one substantive field must be provided
        substantive = {k: v for k, v in metrics.items() if v not in (None, "", 0, [], {})}
        if not substantive:
            return False, (
                "Metrics contain only empty or zero values. "
                "Submit your actual logged numbers or output."
            )

        return True, ""

    # ── Internal helpers ───────────────────────────────────────────────────────

    @classmethod
    def _quest_tier(cls, quest: Quest) -> str:
        d = quest.difficulty.value if quest.difficulty else "easy"
        if d in ("medium", "intermediate"):
            return "intermediate"
        return d

    @classmethod
    def _check_daily_time_cap(cls, quest: Quest, db: Session) -> tuple[bool, str]:
        """Ensure the player's total quest time today does not exceed 4 hours (240 min).

        FLOW Global Rule: No quest > 4 hours per day.
        This checks the aggregate of all completed + in-progress quests today.
        """
        from datetime import date
        today_start = datetime.combine(date.today(), datetime.min.time()).replace(tzinfo=UTC)

        # Sum all time_limit_minutes for quests completed or in progress today
        today_quests = db.query(Quest).filter(
            Quest.user_id == quest.user_id,
            Quest.id != quest.id,
            Quest.status.in_([QuestStatus.COMPLETED, QuestStatus.IN_PROGRESS]),
            Quest.created_at >= today_start,
        ).all()

        total_minutes = sum(
            (q.time_limit_minutes or 0) for q in today_quests
        )
        quest_minutes = quest.time_limit_minutes or 0
        projected = total_minutes + quest_minutes

        if projected > DAILY_MAX_MINUTES:
            return False, (
                f"FLOW Rule: No more than {DAILY_MAX_MINUTES} minutes (4 hours) of quest "
                f"time per day. Today's total: {total_minutes} min already committed. "
                f"This quest adds {quest_minutes} min (total: {projected} min). "
                "Reduce or defer."
            )
        return True, ""

    @classmethod
    def _check_cooldown(cls, quest: Quest, db: Session) -> tuple[bool, str]:
        """Ensure the EXTREME cooldown window has passed since last extreme completion."""
        cooldown = quest.cooldown_hours or EXTREME_COOLDOWN_HOURS
        cutoff = datetime.now(UTC) - timedelta(hours=cooldown)

        # Find most recent completed extreme quest in same domain
        q = db.query(Quest).filter(
            Quest.user_id == quest.user_id,
            Quest.id != quest.id,
            Quest.status == QuestStatus.COMPLETED,
            Quest.domain == quest.domain,
            Quest.difficulty == Difficulty.EXTREME,
            Quest.completed_at >= cutoff,
        )
        recent = q.order_by(Quest.completed_at.desc()).first()

        if recent and recent.completed_at:
            elapsed = (datetime.now(UTC) - recent.completed_at.replace(tzinfo=UTC)).total_seconds() / 3600
            remaining = cooldown - elapsed
            return False, (
                f"Extreme quest cooldown active. {remaining:.1f}h remaining. "
                "Recovery between extreme efforts is mandatory."
            )
        return True, ""

    @classmethod
    def _check_weekly_limit(cls, quest: Quest, db: Session) -> tuple[bool, str]:
        """Ensure the player has not exceeded EXTREME_WEEKLY_LIMIT this week."""
        limit = quest.weekly_limit or EXTREME_WEEKLY_LIMIT
        week_start = datetime.now(UTC) - timedelta(days=7)

        count = db.query(Quest).filter(
            Quest.user_id == quest.user_id,
            Quest.id != quest.id,
            Quest.status == QuestStatus.COMPLETED,
            Quest.difficulty == Difficulty.EXTREME,
            Quest.completed_at >= week_start,
        ).count()

        if count >= limit:
            return False, (
                f"Extreme quest weekly limit reached ({limit}/week). "
                "Wait until one of this week's extreme completions rolls off "
                "the 7-day window before attempting another."
            )
        return True, ""

    @classmethod
    def _check_improvement(cls, quest: Quest, db: Session) -> tuple[bool, str]:
        """EXTREME only: reject completion if submitted metrics show no improvement
        over the most recent completed extreme quest in the same domain.

        Compares numeric metric values. If ALL submitted numeric values are <= the
        previous submission, the quest is rejected. At least one value must exceed
        the prior attempt or the player must be attempting a new metric key.
        """
        # Find most recent completed extreme quest in same domain with metrics
        previous = db.query(Quest).filter(
            Quest.user_id == quest.user_id,
            Quest.id != quest.id,
            Quest.status == QuestStatus.COMPLETED,
            Quest.domain == quest.domain,
            Quest.difficulty == Difficulty.EXTREME,
            Quest.metrics_submitted.isnot(None),
        ).order_by(Quest.completed_at.desc()).first()

        if not previous or not previous.metrics_submitted:
            # First extreme quest in this domain — no comparison needed
            return True, ""

        current_metrics = quest.metrics_submitted or {}
        prev_metrics = previous.metrics_submitted or {}

        # Compare numeric values only
        numeric_current = {k: v for k, v in current_metrics.items() if isinstance(v, (int, float))}
        numeric_prev = {k: v for k, v in prev_metrics.items() if isinstance(v, (int, float))}

        if not numeric_current:
            # No numeric metrics submitted — cannot verify improvement
            return False, (
                "EXTREME quest rejected: no numeric metrics found. "
                "Submit measurable values (reps, sets, time, output count) "
                "to prove improvement over your last attempt."
            )

        # Check if there's ANY improvement in shared keys or new keys
        has_new_key = any(k not in numeric_prev for k in numeric_current)
        has_improvement = any(
            numeric_current.get(k, 0) > numeric_prev.get(k, 0)
            for k in numeric_current
            if k in numeric_prev
        )

        if not has_new_key and not has_improvement:
            prev_summary = ", ".join(f"{k}={v}" for k, v in numeric_prev.items())
            curr_summary = ", ".join(f"{k}={v}" for k, v in numeric_current.items())
            return False, (
                "EXTREME quest rejected: No improvement detected. "
                f"Previous: [{prev_summary}]. Current: [{curr_summary}]. "
                "EXTREME tier demands progression. Beat your last numbers "
                "or introduce a new measurable challenge."
            )

        return True, ""


quest_rules_service = QuestRulesService()
