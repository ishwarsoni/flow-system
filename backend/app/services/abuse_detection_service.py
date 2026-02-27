"""XP & Quest Abuse Detection Service.

Detects:
- Unrealistic metrics (completion too fast, XP/hour too high)
- Repeated manual quests with identical titles
- Robotic completion patterns (uniform timing)
- Abnormal XP/hour rates

Tracks suspicion_score on UserStats.
If threshold exceeded: reduce XP multiplier, increase verification, log anomaly.
No auto-ban.
"""

from __future__ import annotations

import logging
import statistics
from datetime import datetime, timedelta, UTC
from typing import Optional, Tuple

from sqlalchemy.orm import Session
from sqlalchemy import and_, func

from app.models.quest import Quest, QuestStatus, QuestType, Difficulty
from app.models.user_stats import UserStats
from app.models.xp_history import XPHistory, XPChangeType
from app.models.daily_progress import DailyProgress

logger = logging.getLogger(__name__)

# ── Thresholds ─────────────────────────────────────────────────────────────────

# XP per hour thresholds (anything above = suspicious)
XP_PER_HOUR_WARNING = 2000      # Soft flag
XP_PER_HOUR_CRITICAL = 4000     # Hard flag

# Minimum completion time (seconds) for a quest to be considered legitimate
MIN_COMPLETION_TIME_SECONDS = {
    "easy": 120,            # 2 min minimum for easy quests
    "intermediate": 300,    # 5 min
    "hard": 600,            # 10 min
    "extreme": 1200,        # 20 min
}

# Max quests per hour before flagging
MAX_QUESTS_PER_HOUR = 8

# Identical manual quest title threshold
DUPLICATE_MANUAL_TITLE_LIMIT = 3  # Same title in 24h = suspicious

# Suspicion score thresholds
SUSPICION_WARNING = 30.0       # Start increased verification
SUSPICION_PENALTY = 60.0       # Reduce XP multiplier
SUSPICION_SEVERE = 85.0        # Maximum restrictions

# Suspicion score decay per day of clean behavior
SUSPICION_DECAY_PER_DAY = 2.0

# XP multiplier reduction at penalty threshold
XP_PENALTY_MULTIPLIER = 0.5    # 50% XP reduction


class AbuseDetectionResult:
    """Result of abuse detection analysis."""

    def __init__(self):
        self.flags: list[dict] = []
        self.suspicion_delta: float = 0.0
        self.xp_multiplier: float = 1.0
        self.should_increase_verification: bool = False
        self.blocked: bool = False
        self.block_reason: Optional[str] = None

    @property
    def is_suspicious(self) -> bool:
        return len(self.flags) > 0

    def add_flag(self, flag_type: str, severity: str, detail: str, score_delta: float):
        self.flags.append({
            "type": flag_type,
            "severity": severity,
            "detail": detail,
        })
        self.suspicion_delta += score_delta


class AbuseDetectionService:
    """Behavioral analysis engine for XP farming and quest abuse."""

    @staticmethod
    def analyze_completion(
        db: Session,
        user_id: int,
        quest: Quest,
    ) -> AbuseDetectionResult:
        """Run all abuse checks before allowing quest completion rewards.
        
        Called from progression_service BEFORE awarding XP.
        Returns an AbuseDetectionResult with flags and multiplier adjustment.
        """
        result = AbuseDetectionResult()
        stats = db.query(UserStats).filter(UserStats.user_id == user_id).first()
        if not stats:
            return result

        # ── Check 1: Unrealistic completion time ──────────────────────────
        AbuseDetectionService._check_completion_time(quest, result)

        # ── Check 2: XP per hour rate ────────────────────────────────────
        AbuseDetectionService._check_xp_rate(db, user_id, result)

        # ── Check 3: Quest completion frequency ──────────────────────────
        AbuseDetectionService._check_completion_frequency(db, user_id, result)

        # ── Check 4: Duplicate manual quests ─────────────────────────────
        AbuseDetectionService._check_duplicate_manuals(db, user_id, quest, result)

        # ── Check 5: Robotic timing patterns ─────────────────────────────
        AbuseDetectionService._check_timing_patterns(db, user_id, result)

        # ── Apply suspicion score update ─────────────────────────────────
        if result.suspicion_delta > 0:
            new_score = min(100.0, (stats.suspicion_score or 0.0) + result.suspicion_delta)
            stats.suspicion_score = new_score
            db.add(stats)

            # Determine enforcement level
            if new_score >= SUSPICION_PENALTY:
                result.xp_multiplier = XP_PENALTY_MULTIPLIER
                result.should_increase_verification = True
                logger.warning(
                    "ABUSE | user=%d suspicion=%.1f — XP reduced to %d%%, verification increased",
                    user_id, new_score, int(result.xp_multiplier * 100),
                )
            elif new_score >= SUSPICION_WARNING:
                result.should_increase_verification = True
                logger.info(
                    "ABUSE | user=%d suspicion=%.1f — verification increased",
                    user_id, new_score,
                )

            # Log anomaly to audit
            try:
                from app.services.audit_service import audit_log
                audit_log(
                    db, user_id=user_id,
                    event_type="xp_anomaly_detected",
                    metadata={
                        "suspicion_score": new_score,
                        "suspicion_delta": result.suspicion_delta,
                        "flags": result.flags,
                        "xp_multiplier": result.xp_multiplier,
                        "quest_id": quest.id,
                    },
                )
            except Exception:
                pass

        return result

    @staticmethod
    def apply_daily_decay(db: Session, user_id: int) -> None:
        """Reduce suspicion score by decay amount for clean daily behavior.
        Called from daily reset or on login.
        """
        stats = db.query(UserStats).filter(UserStats.user_id == user_id).first()
        if stats and (stats.suspicion_score or 0) > 0:
            stats.suspicion_score = max(0.0, stats.suspicion_score - SUSPICION_DECAY_PER_DAY)
            db.add(stats)

    @staticmethod
    def get_abuse_multiplier(db: Session, user_id: int) -> float:
        """Get current XP multiplier based on suspicion score."""
        stats = db.query(UserStats).filter(UserStats.user_id == user_id).first()
        if not stats:
            return 1.0
        score = stats.suspicion_score or 0.0
        if score >= SUSPICION_SEVERE:
            return 0.25  # 75% reduction
        elif score >= SUSPICION_PENALTY:
            return XP_PENALTY_MULTIPLIER
        return 1.0

    # ── Individual Checks ──────────────────────────────────────────────────────

    @staticmethod
    def _check_completion_time(quest: Quest, result: AbuseDetectionResult) -> None:
        """Flag quests completed faster than minimum allowable time."""
        if not quest.created_at:
            return

        now = datetime.now(UTC)
        # Use started_at if available, otherwise created_at
        start = quest.started_at or quest.created_at
        if start.tzinfo is None:
            from datetime import timezone
            start = start.replace(tzinfo=timezone.utc)

        elapsed_seconds = (now - start).total_seconds()
        min_time = MIN_COMPLETION_TIME_SECONDS.get(
            quest.difficulty.value if quest.difficulty else "easy", 120
        )

        if elapsed_seconds < min_time:
            severity = "high" if elapsed_seconds < min_time * 0.25 else "medium"
            score = 15.0 if severity == "high" else 8.0
            result.add_flag(
                "instant_complete", severity,
                f"Completed in {int(elapsed_seconds)}s (min: {min_time}s for {quest.difficulty.value})",
                score,
            )

    @staticmethod
    def _check_xp_rate(db: Session, user_id: int, result: AbuseDetectionResult) -> None:
        """Flag abnormally high XP/hour rate."""
        one_hour_ago = datetime.now(UTC) - timedelta(hours=1)
        xp_last_hour = db.query(func.sum(XPHistory.xp_amount)).filter(
            and_(
                XPHistory.user_id == user_id,
                XPHistory.change_type == XPChangeType.QUEST_COMPLETED,
                XPHistory.xp_amount > 0,
                XPHistory.created_at >= one_hour_ago,
            )
        ).scalar() or 0

        if xp_last_hour >= XP_PER_HOUR_CRITICAL:
            result.add_flag(
                "xp_rate_critical", "high",
                f"XP/hour: {xp_last_hour} (limit: {XP_PER_HOUR_CRITICAL})",
                20.0,
            )
        elif xp_last_hour >= XP_PER_HOUR_WARNING:
            result.add_flag(
                "xp_rate_warning", "medium",
                f"XP/hour: {xp_last_hour} (warning: {XP_PER_HOUR_WARNING})",
                8.0,
            )

    @staticmethod
    def _check_completion_frequency(
        db: Session, user_id: int, result: AbuseDetectionResult
    ) -> None:
        """Flag too many quests completed per hour."""
        one_hour_ago = datetime.now(UTC) - timedelta(hours=1)
        completions = db.query(Quest).filter(
            and_(
                Quest.user_id == user_id,
                Quest.status == QuestStatus.COMPLETED,
                Quest.completed_at >= one_hour_ago,
            )
        ).count()

        if completions >= MAX_QUESTS_PER_HOUR:
            result.add_flag(
                "high_frequency", "medium",
                f"{completions} quests/hour (max: {MAX_QUESTS_PER_HOUR})",
                10.0,
            )

    @staticmethod
    def _check_duplicate_manuals(
        db: Session, user_id: int, quest: Quest, result: AbuseDetectionResult
    ) -> None:
        """Flag repeated manual quests with identical titles in 24h."""
        if not quest.is_manual or not quest.title:
            return

        one_day_ago = datetime.now(UTC) - timedelta(hours=24)
        same_title_count = db.query(Quest).filter(
            and_(
                Quest.user_id == user_id,
                Quest.is_manual == True,
                Quest.title == quest.title,
                Quest.status == QuestStatus.COMPLETED,
                Quest.completed_at >= one_day_ago,
            )
        ).count()

        if same_title_count >= DUPLICATE_MANUAL_TITLE_LIMIT:
            result.add_flag(
                "duplicate_manual", "medium",
                f"Same manual quest title completed {same_title_count}x in 24h",
                12.0,
            )

    @staticmethod
    def _check_timing_patterns(
        db: Session, user_id: int, result: AbuseDetectionResult
    ) -> None:
        """Detect robotic completion patterns (uniform inter-completion intervals)."""
        recent = db.query(Quest).filter(
            and_(
                Quest.user_id == user_id,
                Quest.status == QuestStatus.COMPLETED,
                Quest.completed_at.isnot(None),
            )
        ).order_by(Quest.completed_at.desc()).limit(10).all()

        if len(recent) < 5:
            return

        # Calculate intervals between completions
        intervals = []
        for i in range(len(recent) - 1):
            t1 = recent[i].completed_at
            t2 = recent[i + 1].completed_at
            if t1 and t2:
                delta = abs((t1 - t2).total_seconds())
                if delta > 0:
                    intervals.append(delta)

        if len(intervals) < 4:
            return

        # Check coefficient of variation (CV) — bots have very low CV
        try:
            mean = statistics.mean(intervals)
            stdev = statistics.stdev(intervals)
            if mean > 0:
                cv = stdev / mean
                if cv < 0.05 and mean < 600:  # < 5% variation AND < 10min average
                    result.add_flag(
                        "robotic_pattern", "high",
                        f"Completion timing CV={cv:.3f} (mean={int(mean)}s) — nearly uniform",
                        18.0,
                    )
                elif cv < 0.15 and mean < 300:  # < 15% variation AND < 5min average
                    result.add_flag(
                        "suspicious_pattern", "medium",
                        f"Completion timing CV={cv:.3f} (mean={int(mean)}s) — low variation",
                        8.0,
                    )
        except (statistics.StatisticsError, ZeroDivisionError):
            pass
