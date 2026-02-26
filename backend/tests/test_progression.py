import pytest
from datetime import datetime, date, timedelta

from app.models.user import User
from app.models.user_stats import UserStats
from app.models.xp_history import XPHistory, XPChangeType
from app.models.daily_progress import DailyProgress
from app.models.game_config import GameConfig

from app.services.progression_service import ProgressionService


def _set_config(db, key, value):
    existing = db.query(GameConfig).filter(GameConfig.key == key).first()
    if existing:
        existing.value = value
    else:
        db.add(GameConfig(key=key, value=value))
    db.commit()


@pytest.fixture()
def user_with_stats(db):
    user = User(username="tester", email="t@test.local", hashed_password="x")
    db.add(user)
    db.flush()

    stats = UserStats(user_id=user.id)
    db.add(stats)
    db.commit()
    db.refresh(user)
    db.refresh(stats)
    return user, stats


def test_apply_xp_levels_and_clamps(db, user_with_stats):
    user, stats = user_with_stats

    # Make progression curve linear and small for predictability
    _set_config(db, "base_xp_per_task", 10)
    _set_config(db, "xp_curve_exponent", 1)
    _set_config(db, "max_stat_value", 100.0)
    _set_config(db, "min_stat_value", 0.0)

    # Apply XP that causes multiple level ups
    # With base=10 and exponent=1: thresholds: level2=20, level3=30, level4=40
    user_stats, xp_entry, _ = ProgressionService.apply_xp(db, user.id, 75, XPChangeType.BONUS)

    assert user_stats.level == 3
    # Leftover XP should be 25 after leveling to 3
    assert user_stats.xp_current == 25

    # Apply large stat deltas to test clamping
    big_deltas = {"focus": 1000.0, "discipline": -1000.0}
    user_stats_before = db.query(UserStats).filter(UserStats.user_id == user.id).first()
    applied = ProgressionService._apply_stat_deltas(user_stats_before, big_deltas, db)
    db.commit()

    # focus clamped to max_stat_value, discipline clamped to min_stat_value
    assert applied["focus"] >= 0
    assert applied["discipline"] <= 0
    assert 0.0 <= user_stats_before.discipline <= 100.0
    assert 0.0 <= user_stats_before.focus <= 100.0


def test_diminishing_returns_and_daily_cap_checks(db, user_with_stats):
    user, stats = user_with_stats

    # Configure threshold and multiplier
    _set_config(db, "diminishing_returns_threshold", 100)
    _set_config(db, "diminishing_returns_multiplier", 0.5)
    _set_config(db, "daily_xp_cap", 150)

    # Ensure today's daily progress exists and simulate some XP already earned
    dp = DailyProgress(user_id=user.id, date=date.today(), xp_earned_today=80)
    db.add(dp)
    db.commit()

    # Applying 50 XP: 20 at full rate (to reach 100), 30 at reduced 50% => 20 + 15 = 35
    reduced = ProgressionService._apply_diminishing_returns(db, user.id, 50)
    assert reduced == 35

    # Check daily cap: trying to apply 100 should be blocked (80 + 100 > 150)
    can_apply, reason = ProgressionService._check_daily_xp_cap(db, user.id, 100)
    assert not can_apply
    assert "Daily XP" in reason
