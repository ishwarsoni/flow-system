"""Daily midnight reset service — auto-fail uncompleted quests + streak rewards.

Every day is a new trial. Quests that were not completed by midnight are
automatically failed with penalties. Consistent hunters are rewarded with
streak milestones — bonus XP, coins, titles, and reputation.
"""

import logging
from datetime import datetime, date, timedelta, UTC
from sqlalchemy.orm import Session

from app.models.quest import Quest, QuestStatus
from app.models.daily_progress import DailyProgress
from app.models.user_stats import UserStats
from app.models.xp_history import XPHistory, XPChangeType

logger = logging.getLogger(__name__)


# ── Streak milestone rewards ──────────────────────────────────────────────────
# The System rewards hunters who show up every single day.

# Skill points are the real reward — used to upgrade stats on the STATUS page.
STREAK_MILESTONES: dict[int, dict] = {
    3:   {"bonus_xp": 75,   "bonus_sp": 3,   "title": "Iron Will",        "reputation": 15,
          "message": "3 DAYS UNBROKEN. Iron Will awakened."},
    7:   {"bonus_xp": 200,  "bonus_sp": 7,   "title": "Dedicated Hunter", "reputation": 30,
          "message": "7-DAY STREAK. The System acknowledges your dedication."},
    14:  {"bonus_xp": 400,  "bonus_sp": 14,  "title": "Unstoppable",      "reputation": 60,
          "message": "14 DAYS. Habit forged. You are Unstoppable."},
    21:  {"bonus_xp": 700,  "bonus_sp": 21,  "title": "Elite Fighter",    "reputation": 100,
          "message": "21 DAYS. Neural pathways rewired. Elite Fighter status achieved."},
    30:  {"bonus_xp": 1200, "bonus_sp": 35,  "title": "S-Rank Contender", "reputation": 200,
          "message": "30-DAY STREAK. S-Rank Contender. Most hunters quit by day 3."},
    60:  {"bonus_xp": 3000, "bonus_sp": 75,  "title": "Dungeon Monarch",  "reputation": 500,
          "message": "60 DAYS. You have become the dungeon. Monarch title granted."},
    100: {"bonus_xp": 8000, "bonus_sp": 200, "title": "Shadow King",      "reputation": 1500,
          "message": "100-DAY STREAK. The Shadow King has risen. This is legendary."},
}


def apply_midnight_penalties(db: Session, user_id: int) -> list[dict]:
    """
    Auto-fail any PENDING quests that were created before today's midnight.
    Also resets the hunter's streak if they had no completions yesterday.

    Called at the beginning of every quest list / action request — lazy evaluation
    instead of a cron job, so it works without a scheduler.

    Returns a list of auto-failed quest info dicts (for logging / notifications).
    """
    today_midnight = datetime.combine(date.today(), datetime.min.time())
    # A quest expires 24 hours after it was created, or when its explicit
    # expires_at timestamp has passed — whichever comes first.
    # SQLite stores naive datetimes, so strip tzinfo before comparing.
    now_naive = datetime.now(UTC).replace(tzinfo=None)
    cutoff_24h = now_naive - timedelta(hours=24)

    from sqlalchemy import or_

    # Find pending OR in-progress quests that are past their 24h window
    # or past their explicit expires_at deadline
    stale_quests = (
        db.query(Quest)
        .filter(
            Quest.user_id == user_id,
            Quest.status.in_([QuestStatus.PENDING, QuestStatus.IN_PROGRESS]),
            or_(
                Quest.created_at < cutoff_24h,
                Quest.expires_at <= now_naive,
            ),
        )
        .all()
    )

    stats = db.query(UserStats).filter(UserStats.user_id == user_id).first()

    # Always check streak even if no stale quests
    yesterday = date.today() - timedelta(days=1)
    yest_dp = db.query(DailyProgress).filter(
        DailyProgress.user_id == user_id,
        DailyProgress.date == yesterday,
    ).first()

    streak_broken = False
    if stats and (yest_dp is None or yest_dp.tasks_completed_today == 0):
        if stats.streak_days > 0:
            logger.info(
                f"Streak broken for user {user_id}: was {stats.streak_days} days"
            )
            streak_broken = True
        stats.streak_days = 0
        db.add(stats)

    if not stale_quests:
        if streak_broken:
            try:
                db.commit()
            except Exception as e:
                db.rollback()
                logger.error(f"Streak reset commit failed for user {user_id}: {e}")
        return []

    if not stats:
        return []

    auto_failed = []
    for quest in stale_quests:
        hp_damage = quest.penalty_hp or max(5, int(quest.base_xp_reward * 0.05))
        xp_penalty = quest.penalty_xp or max(5, int(quest.base_xp_reward * 0.15))

        stats.hp_current = max(1, stats.hp_current - hp_damage)
        stats.xp_current = max(0, stats.xp_current - xp_penalty)

        quest.status = QuestStatus.FAILED
        quest.failed_at = today_midnight

        db.add(
            XPHistory(
                user_id=user_id,
                quest_id=quest.id,
                xp_amount=-xp_penalty,
                coin_amount=0,
                change_type=XPChangeType.QUEST_FAILED,
                reason=f"[ MIDNIGHT PENALTY ] Quest expired: {quest.title}",
                level_at_time=stats.level,
                rank_at_time=stats.rank.value,
            )
        )

        auto_failed.append(
            {
                "quest_id": quest.id,
                "title": quest.title,
                "hp_damage": hp_damage,
                "xp_penalty": xp_penalty,
            }
        )
        logger.info(
            f"Auto-failed quest '{quest.title}' (id={quest.id}) for user {user_id}"
        )

    db.add(stats)
    try:
        db.commit()
        logger.info(
            f"Midnight reset complete for user {user_id}: "
            f"{len(auto_failed)} quests auto-failed"
        )
    except Exception as e:
        db.rollback()
        logger.error(f"Midnight penalty commit failed for user {user_id}: {e}")
        return []

    return auto_failed


def cleanup_old_failed_quests(db: Session, user_id: int) -> int:
    """Delete FAILED / EXPIRED / ABANDONED quests older than 24 hours.

    Keeps the quest list clean — only active and recent quests remain.
    XP history is preserved so the audit trail is never lost.

    Returns the number of quests removed.
    """
    now_naive = datetime.now(UTC).replace(tzinfo=None)
    cutoff = now_naive - timedelta(hours=24)

    from sqlalchemy import or_

    old_quests = (
        db.query(Quest)
        .filter(
            Quest.user_id == user_id,
            Quest.status.in_([
                QuestStatus.FAILED,
                QuestStatus.EXPIRED,
                QuestStatus.ABANDONED,
            ]),
            or_(
                Quest.failed_at < cutoff,
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
        logger.info(
            f"Cleaned up {count} old failed/expired quests for user {user_id}"
        )
    except Exception as e:
        db.rollback()
        logger.error(f"Failed quest cleanup failed for user {user_id}: {e}")
        return 0

    return count


def cleanup_old_completed_quests(db: Session, user_id: int) -> int:
    """Delete COMPLETED quests older than 24 hours.

    Keeps the quest panel clean — only recent completions remain visible.
    XP history is preserved so the audit trail is never lost.

    Returns the number of quests removed.
    """
    now_naive = datetime.now(UTC).replace(tzinfo=None)
    cutoff = now_naive - timedelta(hours=24)

    old_completed = (
        db.query(Quest)
        .filter(
            Quest.user_id == user_id,
            Quest.status == QuestStatus.COMPLETED,
            Quest.completed_at < cutoff,
        )
        .all()
    )

    if not old_completed:
        return 0

    count = len(old_completed)
    for quest in old_completed:
        db.delete(quest)

    try:
        db.commit()
        logger.info(
            f"Cleaned up {count} old completed quests for user {user_id}"
        )
    except Exception as e:
        db.rollback()
        logger.error(f"Completed quest cleanup failed for user {user_id}: {e}")
        return 0

    return count
