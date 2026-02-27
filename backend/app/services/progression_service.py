"""Core progression engine — XP, leveling, stat gains, quest completion/failure.
Rebuilt for the Quest system with HP/MP, coins, rank, fatigue, and streak bonuses."""

from sqlalchemy.orm import Session
from datetime import datetime, date, timedelta, UTC
from typing import Dict, Optional, Tuple

from app.models.user_stats import UserStats
from app.models.quest import Quest, QuestStatus, Difficulty, QuestType
from app.models.xp_history import XPHistory, XPChangeType
from app.models.daily_progress import DailyProgress
from app.models.game_config import GameConfig, DEFAULT_CONFIG
from app.models.rank import RANK_CONFIG, get_title_for_level
from app.services.player_service import PlayerService
from app.core.exceptions import FLOWException


class ProgressionException(FLOWException):
    def __init__(self, message: str):
        super().__init__(message, status_code=400)


class ProgressionService:
    """Core progression/leveling engine for FLOW RPG."""

    # ─── Config Helpers ───

    @staticmethod
    def _cfg(db: Session, key: str) -> float:
        config = db.query(GameConfig).filter(GameConfig.key == key).first()
        return config.value if config else DEFAULT_CONFIG.get(key, 0)

    @staticmethod
    def _get_or_create_daily_progress(db: Session, user_id: int) -> DailyProgress:
        today = date.today()
        dp = db.query(DailyProgress).filter(
            DailyProgress.user_id == user_id,
            DailyProgress.date == today,
        ).first()
        if not dp:
            dp = DailyProgress(user_id=user_id, date=today)
            db.add(dp)
            db.flush()
        return dp

    # ─── XP Calculations ───

    @staticmethod
    def _calculate_xp_for_level(level: int, db: Session) -> int:
        """Non-linear XP curve: base * (level ^ exponent)"""
        exponent = ProgressionService._cfg(db, "xp_curve_exponent")
        base = ProgressionService._cfg(db, "base_xp_per_task")
        return int(base * (level ** exponent))

    @staticmethod
    def _get_xp_to_next_level(current_level: int, current_xp: int, db: Session) -> int:
        xp_for_next = ProgressionService._calculate_xp_for_level(current_level + 1, db)
        return max(0, xp_for_next - current_xp)

    @staticmethod
    def _get_difficulty_multiplier(difficulty: Difficulty, db: Session) -> float:
        key = f"xp_mult_{difficulty.value}"
        return ProgressionService._cfg(db, key)

    @staticmethod
    def _get_coin_reward(difficulty: Difficulty, db: Session) -> int:
        key = f"coins_{difficulty.value}"
        return int(ProgressionService._cfg(db, key))

    @staticmethod
    def _get_mp_cost(difficulty: Difficulty, db: Session) -> int:
        key = f"mp_cost_{difficulty.value}"
        return int(ProgressionService._cfg(db, key))

    # ─── Anti-Grind ───

    @staticmethod
    def _check_daily_xp_cap(db: Session, user_id: int, xp: int) -> Tuple[bool, str]:
        dp = ProgressionService._get_or_create_daily_progress(db, user_id)
        cap = ProgressionService._cfg(db, "daily_xp_cap")
        if dp.xp_earned_today + xp > cap:
            remaining = cap - dp.xp_earned_today
            return False, f"[ SYSTEM ] Daily XP threshold reached. The System limits rapid ascension. Rest and return tomorrow. ({remaining} XP remaining today.)"
        return True, ""

    @staticmethod
    def _apply_diminishing_returns(db: Session, user_id: int, xp: int) -> int:
        dp = ProgressionService._get_or_create_daily_progress(db, user_id)
        threshold = ProgressionService._cfg(db, "diminishing_returns_threshold")
        mult = ProgressionService._cfg(db, "diminishing_returns_multiplier")
        current = dp.xp_earned_today
        if current >= threshold:
            return int(xp * mult)
        if current + xp > threshold:
            full = threshold - current
            reduced = (current + xp - threshold)
            return full + int(reduced * mult)
        return xp

    @staticmethod
    def _check_spam(db: Session, user_id: int) -> Tuple[bool, str]:
        dp = ProgressionService._get_or_create_daily_progress(db, user_id)
        min_time = ProgressionService._cfg(db, "min_time_between_tasks_seconds")
        if dp.last_task_completion_time is None:
            return True, ""
        elapsed = (datetime.now(UTC) - dp.last_task_completion_time).total_seconds()
        if elapsed < min_time:
            wait = int(min_time - elapsed)
            return False, f"[ SYSTEM ] Combat cooldown active. Dungeon re-entry locked for {wait}s. Recover and return."
        return True, ""

    # ─── Stat Gains ───

    @staticmethod
    def _calculate_stat_gains(xp: int, difficulty: Difficulty, primary_stat: str, db: Session) -> Dict[str, float]:
        """Calculate stat gains. Primary stat gets the biggest boost."""
        stat_per = ProgressionService._cfg(db, "stat_increase_per_xp")
        base = xp * stat_per / 100

        # Primary stat always gets bonus
        gains = {primary_stat: base * 1.5}

        # Difficulty affects secondary gains
        if difficulty in (Difficulty.MEDIUM, Difficulty.HARD, Difficulty.EXTREME):
            all_stats = {"strength", "intelligence", "vitality", "charisma", "mana"}
            for s in all_stats - {primary_stat}:
                mult = {"MEDIUM": 0.3, "HARD": 0.5, "EXTREME": 0.8}.get(difficulty.name, 0.2)
                gains[s] = base * mult

        return gains

    @staticmethod
    def _apply_stat_deltas(stats: UserStats, deltas: Dict[str, float], db: Session) -> Dict[str, float]:
        min_s = ProgressionService._cfg(db, "min_stat_value")
        max_s = ProgressionService._cfg(db, "max_stat_value")
        applied = {}
        for name, delta in deltas.items():
            if not hasattr(stats, name):
                continue
            old = getattr(stats, name)
            new = max(min_s, min(max_s, old + delta))
            setattr(stats, name, new)
            applied[name] = round(new - old, 2)
        return applied

    # ─── Core XP Application ───

    @staticmethod
    def apply_xp(
        db: Session, user_id: int, xp_amount: int,
        change_type: XPChangeType, quest_id: Optional[int] = None,
        reason: Optional[str] = None, stat_deltas: Optional[Dict[str, float]] = None,
        coin_amount: int = 0,
    ) -> Tuple[UserStats, XPHistory]:
        stats = db.query(UserStats).filter(UserStats.user_id == user_id).first()
        if not stats:
            raise ProgressionException(f"Player {user_id} not found")

        old_level = stats.level

        # Apply XP
        stats.xp_total_earned += max(0, xp_amount)
        stats.xp_current += xp_amount

        # Level up loop
        skill_pts_per_lvl = int(ProgressionService._cfg(db, "skill_points_per_level"))
        level_ups = 0
        while stats.xp_current >= ProgressionService._calculate_xp_for_level(stats.level + 1, db):
            stats.xp_current -= ProgressionService._calculate_xp_for_level(stats.level + 1, db)
            stats.level += 1
            stats.skill_points += skill_pts_per_lvl
            stats.current_title = get_title_for_level(stats.level)
            level_ups += 1

        # Prevent negative XP
        stats.xp_current = max(0, stats.xp_current)

        # Level cap
        cap = int(ProgressionService._cfg(db, "level_cap"))
        stats.level = min(stats.level, cap)

        # Apply coins
        stats.coins += coin_amount

        # Apply stat deltas
        actual_deltas = {}
        if stat_deltas:
            actual_deltas = ProgressionService._apply_stat_deltas(stats, stat_deltas, db)

        # Check rank change
        rank_event = PlayerService.check_rank_update(stats, db)

        # Audit rank changes
        if rank_event:
            try:
                from app.services.audit_service import audit_log
                event_type = "rank_promotion" if "UP" in str(rank_event) else "rank_demotion"
                audit_log(db, user_id=user_id, event_type=event_type,
                          metadata={"rank_event": rank_event, "level": stats.level, "rank": stats.rank.value})
            except Exception:
                pass

        # Recalculate HP/MP if stats changed
        if actual_deltas:
            PlayerService.recalculate_vitals(stats, db)

        stats.last_active_at = datetime.now(UTC)
        stats.updated_at = datetime.now(UTC)

        # Record history
        entry = XPHistory(
            user_id=user_id, quest_id=quest_id, xp_amount=xp_amount,
            coin_amount=coin_amount, change_type=change_type,
            reason=reason, stat_deltas=actual_deltas if actual_deltas else None,
            level_at_time=stats.level, rank_at_time=stats.rank.value,
        )

        db.add(stats)
        db.add(entry)
        db.commit()
        db.refresh(stats)
        db.refresh(entry)

        return stats, entry, rank_event

    # ─── Quest Completion ───

    @staticmethod
    def complete_quest(db: Session, user_id: int, quest_id: int) -> Tuple[UserStats, Quest, dict]:
        """Complete a quest: award XP, coins, stat gains, update HP/MP."""
        try:
            # Anti-spam
            can, reason = ProgressionService._check_spam(db, user_id)
            if not can:
                raise ProgressionException(reason)

            quest = db.query(Quest).filter(Quest.id == quest_id, Quest.user_id == user_id).first()
            if not quest:
                raise ProgressionException(f"Quest {quest_id} not found")
            if quest.status == QuestStatus.COMPLETED:
                raise ProgressionException("Quest already completed")
            if quest.status in (QuestStatus.FAILED, QuestStatus.EXPIRED, QuestStatus.ABANDONED):
                raise ProgressionException(f"Cannot complete quest with status {quest.status.value}")

            # Check expiry
            if quest.expires_at and datetime.now(UTC) > quest.expires_at:
                quest.status = QuestStatus.EXPIRED
                db.add(quest)
                db.commit()
                raise ProgressionException("Quest has expired")

            stats = db.query(UserStats).filter(UserStats.user_id == user_id).first()
            if not stats:
                raise ProgressionException("Player not found")

            # ── Abuse Detection ──────────────────────────────────────────────
            from app.services.abuse_detection_service import AbuseDetectionService
            abuse_result = AbuseDetectionService.analyze_completion(db, user_id, quest)
            abuse_xp_multiplier = abuse_result.xp_multiplier

            # MP cost
            mp_cost = quest.mp_cost or ProgressionService._get_mp_cost(quest.difficulty, db)
            if not PlayerService.consume_mp(stats, mp_cost, db):
                raise ProgressionException(
                    f"[ SYSTEM ] Insufficient Mana. Required: {mp_cost} MP. Current reserves: {stats.mp_current} MP. "
                    f"Rest to restore mana or complete lighter dungeons first."
                )

            # Calculate XP with multipliers
            diff_mult = ProgressionService._get_difficulty_multiplier(quest.difficulty, db)
            rank_mult = RANK_CONFIG[stats.rank]["xp_multiplier"]

            # Streak bonus
            streak_bonus_pct = min(
                stats.streak_days * ProgressionService._cfg(db, "streak_xp_bonus_per_day"),
                ProgressionService._cfg(db, "max_streak_bonus_percent")
            )
            streak_mult = 1.0 + (streak_bonus_pct / 100)

            # Fatigue penalty
            fatigue_thresh = ProgressionService._cfg(db, "fatigue_xp_penalty_threshold")
            fatigue_mult = 1.0
            if stats.fatigue >= fatigue_thresh:
                fatigue_penalty = ProgressionService._cfg(db, "fatigue_xp_penalty_percent") / 100
                fatigue_mult = 1.0 - fatigue_penalty

            xp_earned = int(quest.base_xp_reward * diff_mult * rank_mult * streak_mult * fatigue_mult * getattr(quest, 'performance_multiplier', 1.0) * abuse_xp_multiplier)

            # Diminishing returns
            xp_earned = ProgressionService._apply_diminishing_returns(db, user_id, xp_earned)

            # Skill points awarded (from quest + difficulty bonus, scales with rank)
            diff_sp = {"trivial": 1, "easy": 1, "medium": 2, "hard": 3, "extreme": 5}
            sp_base = diff_sp.get(quest.difficulty.value, 1)
            sp_bonus = (quest.bonus_skill_points or 0)
            # Higher ranks get bonus SP (+1 per rank tier)
            rank_sp_bonus = {"E": 0, "D": 0, "C": 1, "B": 1, "A": 2, "S": 3, "SS": 4, "SSS": 5}.get(stats.rank.value, 0)
            skill_points_earned = sp_base + sp_bonus + rank_sp_bonus

            # Stat gains
            primary_stat = quest.primary_stat.value if quest.primary_stat else "strength"
            stat_gains = ProgressionService._calculate_stat_gains(xp_earned, quest.difficulty, primary_stat, db)

            # Apply custom stat rewards from quest
            if quest.stat_rewards:
                for stat_name, val in quest.stat_rewards.items():
                    stat_gains[stat_name] = stat_gains.get(stat_name, 0) + val

            # Apply XP + stats (no more coins)
            updated_stats, xp_entry, rank_event = ProgressionService.apply_xp(
                db=db, user_id=user_id, xp_amount=xp_earned,
                change_type=XPChangeType.QUEST_COMPLETED, quest_id=quest_id,
                reason=f"[ QUEST CLEARED ] {quest.title} — {quest.difficulty.value.upper()} DUNGEON CONQUERED",
                stat_deltas=stat_gains, coin_amount=0,
            )
            # Award skill points directly
            updated_stats.skill_points = (updated_stats.skill_points or 0) + skill_points_earned
            db.add(updated_stats)

            # Update quest
            quest.status = QuestStatus.COMPLETED
            quest.completed_at = datetime.now(UTC)

            # Update daily progress + streak
            dp = ProgressionService._get_or_create_daily_progress(db, user_id)
            is_first_today = (dp.tasks_completed_today == 0)  # DB column name kept for compat
            dp.tasks_completed_today += 1  # tracks quest completions
            dp.xp_earned_today += xp_earned
            dp.last_task_completion_time = datetime.now(UTC)

            # ─── Streak tracking (first quest of each day only) ───────
            streak_milestone = None
            if is_first_today:
                yesterday = date.today() - timedelta(days=1)
                yest_dp = db.query(DailyProgress).filter(
                    DailyProgress.user_id == user_id,
                    DailyProgress.date == yesterday,
                ).first()
                had_yesterday = yest_dp and yest_dp.tasks_completed_today > 0  # quest completions
                if had_yesterday or updated_stats.streak_days == 0:
                    updated_stats.streak_days += 1
                else:
                    updated_stats.streak_days = 1
                if updated_stats.streak_days > updated_stats.longest_streak:
                    updated_stats.longest_streak = updated_stats.streak_days

                # Check milestone reward
                from app.services.daily_reset_service import STREAK_MILESTONES
                milestone = STREAK_MILESTONES.get(updated_stats.streak_days)
                if milestone:
                    updated_stats.xp_current += milestone["bonus_xp"]
                    updated_stats.xp_total_earned += milestone["bonus_xp"]
                    updated_stats.skill_points = (updated_stats.skill_points or 0) + milestone["bonus_sp"]
                    updated_stats.reputation = (updated_stats.reputation or 0) + milestone["reputation"]
                    if milestone.get("title"):
                        updated_stats.current_title = milestone["title"]
                    db.add(XPHistory(
                        user_id=user_id,
                        xp_amount=milestone["bonus_xp"],
                        coin_amount=0,
                        change_type=XPChangeType.QUEST_COMPLETED,
                        reason=f"[ STREAK MILESTONE ] {updated_stats.streak_days}-Day Streak — {milestone.get('title', '')}",
                        level_at_time=updated_stats.level,
                        rank_at_time=updated_stats.rank.value,
                    ))
                    streak_milestone = {
                        "streak_days": updated_stats.streak_days,
                        "bonus_xp": milestone["bonus_xp"],
                        "bonus_sp": milestone["bonus_sp"],
                        "new_title": milestone.get("title"),
                        "message": milestone.get("message", f"[ {updated_stats.streak_days}-DAY STREAK ]"),
                    }
                db.add(updated_stats)

            # Fatigue increase
            fatigue_per = ProgressionService._cfg(db, "fatigue_per_quest")
            max_fatigue = ProgressionService._cfg(db, "max_fatigue")
            updated_stats.fatigue = min(max_fatigue, updated_stats.fatigue + fatigue_per)

            db.add(quest)
            db.add(dp)
            db.commit()
            db.refresh(quest)

            xp_to_next = ProgressionService._get_xp_to_next_level(updated_stats.level, updated_stats.xp_current, db)

            # Build SL-voiced rank event if one occurred
            sl_rank_event = None
            if rank_event:
                if "RANK UP" in rank_event:
                    parts = rank_event.replace("RANK UP! ", "").split(" — ")
                    sl_rank_event = (
                        f"[ SYSTEM ] RANK UP DETECTED. {parts[0]}. "
                        f"Title: {parts[1] if len(parts) > 1 else 'Hunter'}. "
                        f"The gates of a new dungeon have opened."
                    )
                else:
                    sl_rank_event = f"[ SYSTEM ] {rank_event}. Maintain your performance, Hunter."

            return updated_stats, quest, {
                "xp_earned": xp_earned,
                "skill_points_earned": skill_points_earned,
                "stat_gains": xp_entry.stat_deltas or {},
                "mp_cost": mp_cost,
                "level": updated_stats.level,
                "xp_current": updated_stats.xp_current,
                "xp_to_next_level": xp_to_next,
                "hp_current": updated_stats.hp_current,
                "mp_current": updated_stats.mp_current,
                "fatigue": updated_stats.fatigue,
                "streak_days": updated_stats.streak_days,
                "streak_milestone": streak_milestone,
                "rank_event": sl_rank_event,
            }

        except ProgressionException:
            db.rollback()
            raise
        except Exception as e:
            db.rollback()
            raise ProgressionException(f"Quest completion failed: {str(e)}")

    # ─── Quest Failure ───

    @staticmethod
    def fail_quest(db: Session, user_id: int, quest_id: int) -> Tuple[UserStats, Quest, dict]:
        """Fail a quest: apply penalties — XP loss, HP damage, stat penalties."""
        try:
            quest = db.query(Quest).filter(Quest.id == quest_id, Quest.user_id == user_id).first()
            if not quest:
                raise ProgressionException(f"Quest {quest_id} not found")
            if quest.status == QuestStatus.FAILED:
                raise ProgressionException("Quest already failed")
            if quest.status in (QuestStatus.COMPLETED, QuestStatus.ABANDONED):
                raise ProgressionException(f"Cannot fail quest with status {quest.status.value}")

            stats = db.query(UserStats).filter(UserStats.user_id == user_id).first()
            if not stats:
                raise ProgressionException("Player not found")

            # XP penalty
            diff_mult = ProgressionService._get_difficulty_multiplier(quest.difficulty, db)
            xp_would_earn = int(quest.base_xp_reward * diff_mult)
            fail_mult = ProgressionService._cfg(db, "xp_failure_penalty")
            xp_penalty = int(xp_would_earn * fail_mult * -1)

            # HP damage from failure
            hp_damage = quest.penalty_hp or int(xp_would_earn * 0.1)
            PlayerService.apply_hp_damage(stats, hp_damage)

            # Stat penalties (50% of what would have been gained, negative)
            primary_stat = quest.primary_stat.value if quest.primary_stat else "strength"
            full_gains = ProgressionService._calculate_stat_gains(xp_would_earn, quest.difficulty, primary_stat, db)
            stat_penalties = {k: v * -0.5 for k, v in full_gains.items()}

            # Custom penalties from quest
            if quest.penalty_stat:
                for stat_name, val in quest.penalty_stat.items():
                    stat_penalties[stat_name] = stat_penalties.get(stat_name, 0) + val

            # Apply penalties (no coin loss — coins removed)
            updated_stats, xp_entry, rank_event = ProgressionService.apply_xp(
                db=db, user_id=user_id, xp_amount=xp_penalty,
                change_type=XPChangeType.QUEST_FAILED, quest_id=quest_id,
                reason=f"[ HUNTER DOWN ] {quest.title} — Dungeon Break recorded",
                stat_deltas=stat_penalties, coin_amount=0,
            )

            # Update quest
            quest.status = QuestStatus.FAILED
            quest.failed_at = datetime.now(UTC)

            # Audit extreme failures
            if quest.difficulty in (Difficulty.HARD, Difficulty.EXTREME):
                try:
                    from app.services.audit_service import audit_log
                    audit_log(db, user_id=user_id, event_type="extreme_fail",
                              metadata={"quest_id": quest_id, "difficulty": quest.difficulty.value,
                                        "xp_penalty": xp_penalty, "hp_damage": hp_damage})
                except Exception:
                    pass

            # Daily progress
            dp = ProgressionService._get_or_create_daily_progress(db, user_id)
            dp.tasks_failed_today += 1  # tracks quest failures

            db.add(quest)
            db.add(dp)
            db.commit()
            db.refresh(quest)

            xp_to_next = ProgressionService._get_xp_to_next_level(updated_stats.level, updated_stats.xp_current, db)

            return updated_stats, quest, {
                "xp_penalty": xp_penalty,
                "hp_damage": hp_damage,
                "stat_penalties": xp_entry.stat_deltas or {},
                "level": updated_stats.level,
                "xp_current": updated_stats.xp_current,
                "xp_to_next_level": xp_to_next,
                "hp_current": updated_stats.hp_current,
                "mp_current": updated_stats.mp_current,
                "rank_event": rank_event,
            }

        except ProgressionException:
            db.rollback()
            raise
        except Exception as e:
            db.rollback()
            raise ProgressionException(f"Quest failure handling failed: {str(e)}")
