"""Background scheduler — auto-fails quests that exceed the 24-hour window.

FLOW RULE: Every quest has a 24-hour deadline. If a hunter does not
complete or explicitly fail a quest within 24 hours, the System marks it
as FAILED and applies XP + HP penalties automatically.

This scheduler runs every 30 minutes in a background thread so penalties
are applied even when the user is not actively hitting the API.
The lazy `apply_midnight_penalties` in the quest router remains as a
real-time fallback for immediate consistency when a user opens the app.
"""

import asyncio
import logging
from datetime import datetime, timedelta, UTC

from sqlalchemy.orm import Session

from app.db.database import SessionLocal
from app.models.quest import Quest, QuestStatus
from app.models.user_stats import UserStats
from app.models.xp_history import XPHistory, XPChangeType

logger = logging.getLogger(__name__)

# How often the scheduler checks for expired quests (seconds)
CHECK_INTERVAL_SECONDS = 30 * 60  # 30 minutes


def _expire_stale_quests_for_all_users(db: Session) -> int:
    """Find and auto-fail all quests older than 24 hours across ALL users.

    Returns the number of quests that were auto-failed.
    """
    now_naive = datetime.now(UTC).replace(tzinfo=None)
    cutoff = now_naive - timedelta(hours=24)

    stale_quests = (
        db.query(Quest)
        .filter(
            Quest.status.in_([QuestStatus.PENDING, QuestStatus.IN_PROGRESS]),
            Quest.created_at < cutoff,
        )
        .all()
    )

    if not stale_quests:
        return 0

    # Group by user for efficient stats lookup
    user_ids = {q.user_id for q in stale_quests}
    stats_map: dict[int, UserStats] = {}
    for uid in user_ids:
        stats = db.query(UserStats).filter(UserStats.user_id == uid).first()
        if stats:
            stats_map[uid] = stats

    failed_count = 0
    for quest in stale_quests:
        stats = stats_map.get(quest.user_id)
        if not stats:
            # No stats record — still mark as failed but skip penalties
            quest.status = QuestStatus.FAILED
            quest.failed_at = datetime.now(UTC)
            failed_count += 1
            continue

        # Calculate penalties
        hp_damage = quest.penalty_hp or max(5, int(quest.base_xp_reward * 0.05))
        xp_penalty = quest.penalty_xp or max(5, int(quest.base_xp_reward * 0.15))

        stats.hp_current = max(1, stats.hp_current - hp_damage)
        stats.xp_current = max(0, stats.xp_current - xp_penalty)

        quest.status = QuestStatus.FAILED
        quest.failed_at = datetime.now(UTC)

        db.add(
            XPHistory(
                user_id=quest.user_id,
                quest_id=quest.id,
                xp_amount=-xp_penalty,
                coin_amount=0,
                change_type=XPChangeType.QUEST_EXPIRED,
                reason=f"[ 24H EXPIRED ] Quest auto-failed: {quest.title}",
                level_at_time=stats.level,
                rank_at_time=stats.rank.value if stats.rank else "E",
            )
        )

        failed_count += 1
        logger.info(
            "Auto-expired quest '%s' (id=%d) for user %d — XP -%d, HP -%d",
            quest.title, quest.id, quest.user_id, xp_penalty, hp_damage,
        )

    if failed_count:
        for stats in stats_map.values():
            db.add(stats)
        try:
            db.commit()
            logger.info("Quest expiry check complete: %d quests auto-failed", failed_count)
        except Exception as e:
            db.rollback()
            logger.error("Quest expiry commit failed: %s", e)
            return 0

    return failed_count


def _cleanup_old_failed_quests_all_users(db: Session) -> int:
    """Delete FAILED / EXPIRED / ABANDONED quests whose failure is older than 24 hours.

    Runs for ALL users. XP history is preserved — only the quest rows are removed
    so the quest list doesn't pile up with dead entries.
    """
    now_naive = datetime.now(UTC).replace(tzinfo=None)
    cutoff = now_naive - timedelta(hours=24)

    from sqlalchemy import or_

    old_quests = (
        db.query(Quest)
        .filter(
            Quest.status.in_([QuestStatus.FAILED, QuestStatus.EXPIRED, QuestStatus.ABANDONED]),
            or_(
                Quest.failed_at < cutoff,
                # Abandoned quests may not have failed_at — fall back to created_at
                Quest.created_at < cutoff,
            ),
        )
        .all()
    )

    if not old_quests:
        return 0

    count = len(old_quests)
    for quest in old_quests:
        db.delete(quest)

    try:
        db.commit()
        logger.info("Cleaned up %d old failed/expired quests across all users", count)
    except Exception as e:
        db.rollback()
        logger.error("Failed quest cleanup commit failed: %s", e)
        return 0

    return count


async def _scheduler_loop():
    """Async loop that runs the expiry check every CHECK_INTERVAL_SECONDS."""
    logger.info(
        "Quest expiry scheduler started — checking every %d minutes",
        CHECK_INTERVAL_SECONDS // 60,
    )
    while True:
        await asyncio.sleep(CHECK_INTERVAL_SECONDS)
        try:
            db = SessionLocal()
            try:
                # 1) Auto-fail quests past 24h
                count = _expire_stale_quests_for_all_users(db)
                if count:
                    logger.info("Scheduler tick: %d quests expired", count)

                # 2) Cleanup old failed quests (>24h after failure)
                cleaned = _cleanup_old_failed_quests_all_users(db)
                if cleaned:
                    logger.info("Scheduler tick: %d old failed quests cleaned up", cleaned)
            finally:
                db.close()
        except Exception as e:
            logger.error("Quest expiry scheduler error: %s", e)


_scheduler_task: asyncio.Task | None = None


def start_quest_expiry_scheduler():
    """Start the background scheduler. Call once at app startup."""
    global _scheduler_task
    if _scheduler_task is not None:
        return  # Already running
    loop = asyncio.get_event_loop()
    _scheduler_task = loop.create_task(_scheduler_loop())
    logger.info("Quest expiry background scheduler registered")


def stop_quest_expiry_scheduler():
    """Cancel the background scheduler. Call at app shutdown."""
    global _scheduler_task
    if _scheduler_task:
        _scheduler_task.cancel()
        _scheduler_task = None
        logger.info("Quest expiry background scheduler stopped")
