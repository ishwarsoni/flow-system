"""Player service — profile, HP/MP calculations, rank management, skill point allocation."""

from sqlalchemy.orm import Session
from datetime import datetime, UTC
from typing import Dict, Optional

from app.models.user_stats import UserStats
from app.models.rank import Rank, RANK_CONFIG, get_rank_for_level, get_next_rank, RANK_ORDER, get_title_for_level
from app.models.game_config import GameConfig, DEFAULT_CONFIG
from app.core.exceptions import FLOWException


class PlayerException(FLOWException):
    def __init__(self, message: str):
        super().__init__(message, status_code=400)


class PlayerService:
    """Core player system — everything about the player's state."""

    @staticmethod
    def _cfg(db: Session, key: str) -> float:
        config = db.query(GameConfig).filter(GameConfig.key == key).first()
        return config.value if config else DEFAULT_CONFIG.get(key, 0)

    @staticmethod
    def calculate_hp_max(vitality: float, rank: Rank, db: Session) -> int:
        """HP_max = base_hp + (VIT * hp_per_vit) + rank_bonus"""
        base = PlayerService._cfg(db, "base_hp")
        per_vit = PlayerService._cfg(db, "hp_per_vitality")
        rank_bonus = RANK_CONFIG[rank]["hp_bonus"]
        return int(base + (vitality * per_vit) + rank_bonus)

    @staticmethod
    def calculate_mp_max(mana: float, rank: Rank, db: Session) -> int:
        """MP_max = base_mp + (MANA * mp_per_mana) + rank_bonus"""
        base = PlayerService._cfg(db, "base_mp")
        per_mana = PlayerService._cfg(db, "mp_per_mana")
        rank_bonus = RANK_CONFIG[rank]["mp_bonus"]
        return int(base + (mana * per_mana) + rank_bonus)

    @staticmethod
    def recalculate_vitals(stats: UserStats, db: Session) -> None:
        """Recalculate HP/MP max from current stats and rank. Clamp current to max."""
        stats.hp_max = PlayerService.calculate_hp_max(stats.vitality, stats.rank, db)
        stats.mp_max = PlayerService.calculate_mp_max(stats.mana, stats.rank, db)
        stats.hp_current = min(stats.hp_current, stats.hp_max)
        stats.mp_current = min(stats.mp_current, stats.mp_max)

    @staticmethod
    def check_rank_update(stats: UserStats, db: Session) -> Optional[str]:
        """Check if player should be promoted or demoted based on level. Returns event message or None."""
        correct_rank = get_rank_for_level(stats.level)

        if correct_rank == stats.rank:
            return None

        old_rank = stats.rank
        stats.rank = correct_rank
        # Title is driven by level (Solo Leveling style), not just rank label
        stats.current_title = get_title_for_level(stats.level)

        # Recalculate vitals for new rank bonuses
        PlayerService.recalculate_vitals(stats, db)

        old_idx = RANK_ORDER.index(old_rank)
        new_idx = RANK_ORDER.index(correct_rank)

        if new_idx > old_idx:
            return f"RANK UP! {old_rank.value} → {correct_rank.value} — {RANK_CONFIG[correct_rank]['title']}"
        else:
            return f"RANK DOWN: {old_rank.value} → {correct_rank.value}"

    @staticmethod
    def allocate_skill_points(db: Session, user_id: int, allocations: Dict[str, int]) -> UserStats:
        """Spend skill points to increase stats.
        allocations: {"strength": 2, "intelligence": 1, ...}
        Each point = +1.0 to the stat.
        """
        stats = db.query(UserStats).filter(UserStats.user_id == user_id).first()
        if not stats:
            raise PlayerException("Player not found")

        total_requested = sum(allocations.values())
        if total_requested <= 0:
            raise PlayerException("Must allocate at least 1 point")
        if total_requested > stats.skill_points:
            raise PlayerException(f"Not enough skill points. Have {stats.skill_points}, need {total_requested}")

        valid_stats = {"strength", "intelligence", "vitality", "charisma", "mana"}
        max_stat = PlayerService._cfg(db, "max_stat_value")

        for stat_name, points in allocations.items():
            if stat_name not in valid_stats:
                raise PlayerException(f"Invalid stat: {stat_name}")
            if points < 0:
                raise PlayerException("Cannot allocate negative points")
            if points == 0:
                continue

            current = getattr(stats, stat_name)
            new_val = min(current + (points * 1.0), max_stat)
            setattr(stats, stat_name, new_val)

        stats.skill_points -= total_requested

        # Recalculate vitals if VIT or MANA changed
        if "vitality" in allocations or "mana" in allocations:
            PlayerService.recalculate_vitals(stats, db)

        stats.updated_at = datetime.now(UTC)
        db.add(stats)
        db.commit()
        db.refresh(stats)
        return stats

    @staticmethod
    def get_player_profile(db: Session, user_id: int) -> dict:
        """Get full player HUD data."""
        from app.models.user import User
        from app.models.rank import get_allowed_difficulties
        
        stats = db.query(UserStats).filter(UserStats.user_id == user_id).first()
        if not stats:
            raise PlayerException("Player not found")

        user = db.query(User).filter(User.id == user_id).first()
        hunter_name = (getattr(user, 'hunter_name', None) or "Hunter") if user else "Hunter"
        allowed = get_allowed_difficulties(stats.level)

        from app.services.progression_service import ProgressionService
        xp_to_next = ProgressionService._get_xp_to_next_level(stats.level, stats.xp_current, db)
        xp_for_next = ProgressionService._calculate_xp_for_level(stats.level + 1, db)

        rank_config = RANK_CONFIG[stats.rank]
        next_rank = get_next_rank(stats.rank)
        next_rank_info = None
        if next_rank:
            next_cfg = RANK_CONFIG[next_rank]
            next_rank_info = {
                "rank": next_rank.value,
                "min_level": next_cfg["min_level"],
                "title": next_cfg["title"],
                "levels_away": max(0, next_cfg["min_level"] - stats.level),
            }

        # Streak bonus
        streak_bonus_per_day = PlayerService._cfg(db, "streak_xp_bonus_per_day")
        max_streak_bonus = PlayerService._cfg(db, "max_streak_bonus_percent")
        streak_xp_bonus = min(stats.streak_days * streak_bonus_per_day, max_streak_bonus)

        return {
            # Identity
            "hunter_name": hunter_name,
            "level": stats.level,
            "rank": stats.rank.value,
            "rank_title": rank_config["title"],
            "current_title": stats.current_title,

            # Vitals
            "hp_current": stats.hp_current,
            "hp_max": stats.hp_max,
            "mp_current": stats.mp_current,
            "mp_max": stats.mp_max,

            # XP
            "xp_current": stats.xp_current,
            "xp_total_earned": stats.xp_total_earned,
            "xp_to_next_level": xp_to_next,
            "xp_for_next_level": xp_for_next,

            # Stats
            "strength": stats.strength,
            "intelligence": stats.intelligence,
            "vitality": stats.vitality,
            "charisma": stats.charisma,
            "mana": stats.mana,

            # Economy
            "coins": stats.coins,
            "skill_points": stats.skill_points,
            "reputation": stats.reputation,

            # System
            "fatigue": stats.fatigue,
            "streak_days": stats.streak_days,
            "longest_streak": stats.longest_streak,
            "streak_xp_bonus_percent": streak_xp_bonus,
            "punishment_active": stats.punishment_active,

            # Rank info
            "rank_xp_multiplier": rank_config["xp_multiplier"],
            "rank_coin_multiplier": rank_config["coin_multiplier"],
            "daily_quest_count": rank_config["daily_quest_count"],
            "special_quests_unlocked": rank_config["special_quests_unlocked"],
            "allowed_difficulties": allowed,
            "next_rank": next_rank_info,
        }

    @staticmethod
    def consume_mp(stats: UserStats, cost: int, db: Session) -> bool:
        """Consume MP for quest attempt. Returns False if insufficient."""
        if stats.mp_current < cost:
            return False
        stats.mp_current -= cost
        return True

    @staticmethod
    def apply_hp_damage(stats: UserStats, damage: int) -> None:
        """Apply HP damage (from quest failure, penalties, etc.)."""
        stats.hp_current = max(0, stats.hp_current - damage)

    @staticmethod
    def regenerate(stats: UserStats, hours_elapsed: float, db: Session) -> None:
        """Regenerate HP and MP over time, reduce fatigue."""
        hp_regen = PlayerService._cfg(db, "hp_regen_per_hour")
        mp_regen = PlayerService._cfg(db, "mp_regen_per_hour")
        fatigue_recovery = PlayerService._cfg(db, "fatigue_recovery_per_hour")

        stats.hp_current = min(stats.hp_max, int(stats.hp_current + hp_regen * hours_elapsed))
        stats.mp_current = min(stats.mp_max, int(stats.mp_current + mp_regen * hours_elapsed))
        stats.fatigue = max(0.0, stats.fatigue - fatigue_recovery * hours_elapsed)
