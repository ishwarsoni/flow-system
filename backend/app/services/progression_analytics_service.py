"""Progression analytics service — RPG stat analysis, 7-day trends, streaks."""

from sqlalchemy.orm import Session  # type: ignore
from sqlalchemy import func, and_  # type: ignore
from datetime import datetime, date, timedelta
from typing import Dict, Tuple

from app.models.user_stats import UserStats  # type: ignore
from app.models.daily_progress import DailyProgress  # type: ignore
from app.models.xp_history import XPHistory, XPChangeType  # type: ignore
from app.core.exceptions import FLOWException  # type: ignore


class ProgressionAnalyticsException(FLOWException):
    def __init__(self, message: str):
        super().__init__(message, status_code=400)  # type: ignore


class ProgressionAnalyticsService:
    """Efficient analytics queries for user progression."""

    # RPG stat names
    STAT_KEYS = ["focus", "discipline", "energy", "intelligence", "consistency"]

    @staticmethod
    def _get_stat_analysis(user_stats: UserStats) -> Tuple[str, float, str, float]:
        """Find strongest and weakest stats."""
        stats = {
            "strength": user_stats.strength,
            "intelligence": user_stats.intelligence,
            "vitality": user_stats.vitality,
            "charisma": user_stats.charisma,
            "mana": user_stats.mana,
        }
        max_val = max(stats.values())
        strongest = sorted([k for k, v in stats.items() if v == max_val])[0]
        min_val = min(stats.values())
        weakest = sorted([k for k, v in stats.items() if v == min_val])[0]
        return strongest, stats[strongest], weakest, stats[weakest]

    @staticmethod
    def _get_7day_stats(user_id: int, db: Session) -> Tuple[int, int, int]:
        seven_days_ago = date.today() - timedelta(days=6)

        xp_query = db.query(func.sum(XPHistory.xp_amount)).filter(
            and_(
                XPHistory.user_id == user_id,
                XPHistory.change_type == XPChangeType.QUEST_COMPLETED,
                func.date(XPHistory.created_at) >= seven_days_ago,
            )
        )
        xp_earned = int(xp_query.scalar() or 0)

        daily_query = db.query(
            func.sum(DailyProgress.tasks_completed_today),
            func.sum(DailyProgress.tasks_failed_today),
        ).filter(
            and_(
                DailyProgress.user_id == user_id,
                DailyProgress.date >= seven_days_ago,
            )
        )
        result = daily_query.first()
        completed = int(result[0] or 0)
        failed = int(result[1] or 0)
        return xp_earned, completed, failed

    @staticmethod
    def _calculate_streak(user_id: int, db: Session) -> Tuple[int, int]:
        daily_records = db.query(DailyProgress).filter(
            DailyProgress.user_id == user_id
        ).order_by(DailyProgress.date.desc()).all()

        if not daily_records:
            return 0, 0

        # Current streak
        current_streak = 0
        today = date.today()
        for i, rec in enumerate(daily_records):
            expected = today - timedelta(days=i)
            if rec.date == expected and rec.tasks_completed_today > 0:
                current_streak += 1
            else:
                break

        # Longest streak
        longest = 0
        temp = 0
        last_date = None
        for rec in reversed(daily_records):
            if rec.tasks_completed_today > 0:
                if last_date is None or (rec.date - last_date).days == 1:
                    temp += 1
                    last_date = rec.date
                else:
                    longest = max(longest, temp)
                    temp = 1
                    last_date = rec.date
            else:
                longest = max(longest, temp)
                temp = 0
                last_date = None
        longest = max(longest, temp)

        return current_streak, longest

    @staticmethod
    def get_user_progress(user_id: int, db: Session) -> dict:
        """Get comprehensive user progression snapshot."""
        try:
            user_stats = db.query(UserStats).filter(UserStats.user_id == user_id).first()
            if not user_stats:
                raise ProgressionAnalyticsException(f"Player {user_id} has no stats")

            today_progress = db.query(DailyProgress).filter(
                and_(
                    DailyProgress.user_id == user_id,
                    DailyProgress.date == date.today(),
                )
            ).first()

            xp_today = today_progress.xp_earned_today if today_progress else 0
            completed_today = today_progress.tasks_completed_today if today_progress else 0
            failed_today = today_progress.tasks_failed_today if today_progress else 0

            xp_7d, completed_7d, failed_7d = ProgressionAnalyticsService._get_7day_stats(user_id, db)
            current_streak, longest_streak = ProgressionAnalyticsService._calculate_streak(user_id, db)

            from app.services.progression_service import ProgressionService  # type: ignore
            xp_to_next = ProgressionService._get_xp_to_next_level(
                user_stats.level, user_stats.xp_current, db
            )

            strongest, strongest_val, weakest, weakest_val = (
                ProgressionAnalyticsService._get_stat_analysis(user_stats)
            )

            return {
                "level": user_stats.level,
                "rank": user_stats.rank.value,
                "xp_current": user_stats.xp_current,
                "xp_total_earned": user_stats.xp_total_earned,
                "xp_to_next_level": xp_to_next,
                # Use original DB column names to match ProgressionOverviewResponse schema
                "strength": user_stats.strength,
                "intelligence": user_stats.intelligence,
                "vitality": user_stats.vitality,
                "charisma": user_stats.charisma,
                "mana": user_stats.mana,
                "strongest_stat": strongest,
                "strongest_stat_value": strongest_val,
                "weakest_stat": weakest,
                "weakest_stat_value": weakest_val,
                "hp_current": user_stats.hp_current,
                "hp_max": user_stats.hp_max,
                "mp_current": user_stats.mp_current,
                "mp_max": user_stats.mp_max,
                "fatigue": user_stats.fatigue,
                "xp_earned_today": xp_today,
                "quests_completed_today": completed_today,
                "quests_failed_today": failed_today,
                "xp_earned_7days": xp_7d,
                "quests_completed_7days": completed_7d,
                "quests_failed_7days": failed_7d,
                "current_streak_days": current_streak,
                "longest_streak_days": longest_streak,
                "streak_days": user_stats.streak_days,
                "skill_points": user_stats.skill_points,
            }
        except ProgressionAnalyticsException:
            raise
        except Exception as e:
            raise ProgressionAnalyticsException(f"Failed to fetch progression: {str(e)}")

    @staticmethod
    def get_user_history(user_id: int, db: Session) -> dict:
        """Build time-series data for last 7 days."""
        today = date.today()
        days = [today - timedelta(days=i) for i in range(6, -1, -1)]
        stat_keys = ProgressionAnalyticsService.STAT_KEYS
        stat_deltas_by_day = {k: [0.0] * 7 for k in stat_keys}
        stat_key_map = {
            "mana": "focus",
            "strength": "discipline",
            "vitality": "energy",
            "intelligence": "intelligence",
            "charisma": "consistency",
            "focus": "focus",
            "discipline": "discipline",
            "energy": "energy",
            "consistency": "consistency",
        }

        start_date = days[0]
        end_date = days[-1]

        xp_records = db.query(XPHistory).filter(
            and_(
                XPHistory.user_id == user_id,
                func.date(XPHistory.created_at) >= start_date,
                func.date(XPHistory.created_at) <= end_date,
            )
        ).all()

        xp_map = {d: 0 for d in days}
        for rec in xp_records:
            rec_date = rec.created_at.date()
            if rec.change_type == XPChangeType.QUEST_COMPLETED and rec_date in xp_map:
                xp_map[rec_date] += int(rec.xp_amount or 0)
            if rec.stat_deltas:
                try:
                    idx = days.index(rec_date)
                except ValueError:
                    idx = None
                if idx is not None:
                    deltas = rec.stat_deltas
                    if isinstance(deltas, str):
                        try:
                            import json
                            deltas = json.loads(deltas)
                        except json.JSONDecodeError:
                            deltas = {}
                    
                    if isinstance(deltas, dict):
                        for key, value in deltas.items():
                            mapped_key = stat_key_map.get(key)
                            if mapped_key in stat_deltas_by_day and value is not None:
                                stat_deltas_by_day[mapped_key][idx] += float(value)  # type: ignore

        daily_records = db.query(DailyProgress).filter(
            and_(
                DailyProgress.user_id == user_id,
                DailyProgress.date >= start_date,
                DailyProgress.date <= end_date,
            )
        ).all()

        dp_completed = {d: 0 for d in days}
        dp_failed = {d: 0 for d in days}
        for rec in daily_records:
            if rec.date in dp_completed:
                dp_completed[rec.date] = int(rec.tasks_completed_today or 0)
                dp_failed[rec.date] = int(rec.tasks_failed_today or 0)

        return {
            "dates": [d.isoformat() for d in days],
            "xp_by_day": [xp_map.get(d, 0) for d in days],
            "quests_completed_by_day": [dp_completed.get(d, 0) for d in days],
            "quests_failed_by_day": [dp_failed.get(d, 0) for d in days],
            "stat_deltas_by_day": stat_deltas_by_day,
        }
