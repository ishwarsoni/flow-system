from sqlalchemy import Column, Integer, String, Float
from app.db.base import Base


class GameConfig(Base):
    __tablename__ = "game_config"

    id = Column(Integer, primary_key=True, index=True)
    key = Column(String(100), unique=True, nullable=False, index=True)
    value = Column(Float, nullable=False)
    description = Column(String(500), nullable=True)

    def __repr__(self):
        return f"<GameConfig(key={self.key}, value={self.value})>"


# ═══════════════════════════════════════════════════════════
# DEFAULT GAME CONFIGURATION — All values affect gameplay
# ═══════════════════════════════════════════════════════════
DEFAULT_CONFIG = {
    # ─── XP & Leveling ───
    "base_xp_per_task": 100,
    "xp_curve_exponent": 1.5,          # Non-linear: each level requires more
    "xp_failure_penalty": 0.5,         # 50% of earned XP lost on fail
    "level_cap": 100,
    "skill_points_per_level": 3,       # Skill points awarded per level-up

    # ─── Difficulty XP Ceilings ───
    "xp_max_trivial": 50,
    "xp_max_easy": 150,
    "xp_max_medium": 300,
    "xp_max_hard": 500,
    "xp_max_extreme": 1000,

    # ─── Difficulty XP Multipliers ───
    "xp_mult_trivial": 0.5,
    "xp_mult_easy": 1.0,
    "xp_mult_medium": 1.5,
    "xp_mult_hard": 2.0,
    "xp_mult_extreme": 3.0,

    # ─── Coin Rewards (base per quest) ───
    "coins_trivial": 5,
    "coins_easy": 10,
    "coins_medium": 25,
    "coins_hard": 50,
    "coins_extreme": 100,

    # ─── Stats ───
    "stat_increase_per_xp": 0.1,
    "max_stat_value": 100.0,
    "min_stat_value": 0.0,

    # ─── HP / MP Formulas ───
    "base_hp": 100,
    "hp_per_vitality": 5,              # HP_max = base_hp + (VIT * hp_per_vit) + rank_bonus
    "base_mp": 50,
    "mp_per_mana": 3,                  # MP_max = base_mp + (MANA * mp_per_mana) + rank_bonus
    "hp_regen_per_hour": 5,            # HP regeneration
    "mp_regen_per_hour": 3,            # MP regeneration

    # ─── Quest MP Cost ───
    "mp_cost_trivial": 0,
    "mp_cost_easy": 5,
    "mp_cost_medium": 10,
    "mp_cost_hard": 20,
    "mp_cost_extreme": 35,

    # ─── Fatigue ───
    "fatigue_per_quest": 5.0,          # Fatigue gained per quest completion
    "fatigue_xp_penalty_threshold": 60, # Above this, XP gain reduced
    "fatigue_xp_penalty_percent": 25,  # % XP reduction when fatigued
    "fatigue_recovery_per_hour": 8.0,  # Fatigue reduction per hour
    "max_fatigue": 100.0,

    # ─── Stat Decay ───
    "stat_decay_per_day_inactive": 0.5, # Stats decay per day of inactivity
    "decay_grace_period_hours": 36,     # Hours before decay starts
    "max_decay_per_stat": 5.0,          # Max decay per stat per check

    # ─── Penalties ───
    "inactivity_lock_days": 3,          # Days before special quests locked
    "inactivity_lock_duration_hours": 48,
    "inactivity_xp_penalty_percent": 10,
    "rank_demotion_fail_threshold": 5,  # Failures in 7 days to trigger demotion check
    "streak_xp_bonus_per_day": 2,       # +2% XP per streak day (caps at 50%)
    "max_streak_bonus_percent": 50,

    # ─── Anti-Grind Protection ───
    "daily_xp_cap": 5000,
    "diminishing_returns_threshold": 1000,
    "diminishing_returns_multiplier": 0.5,
    "min_time_between_tasks_seconds": 300,
    "max_quests_per_day": 20,

    # ─── Quest Generation ───
    "daily_quest_base_xp": 80,
    "weekly_quest_base_xp": 250,
    "special_quest_base_xp": 500,
    "penalty_quest_base_xp": 50,       # Low reward — it's punishment
}
