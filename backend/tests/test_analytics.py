import pytest
from datetime import date, timedelta

from app.models.user import User
from app.models.user_stats import UserStats
from app.models.xp_history import XPHistory, XPChangeType
from app.models.daily_progress import DailyProgress
from app.models.game_config import GameConfig

from app.services.progression_analytics_service import ProgressionAnalyticsService


@pytest.fixture()
def seeded_user(db):
    user = User(username="analytics", email="a@test.local", hashed_password="x")
    db.add(user)
    db.flush()
    stats = UserStats(user_id=user.id, focus=10.0, discipline=20.0, energy=30.0, intelligence=40.0, consistency=50.0)
    db.add(stats)
    db.commit()
    return user, stats


def test_get_7day_stats_and_failure_rate(db, seeded_user):
    user, stats = seeded_user

    today = date.today()
    # Create XPHistory entries over last 7 days
    for i in range(7):
        day = today - timedelta(days=i)
        # one completion per day with 100 xp
        xp = XPHistory(user_id=user.id, quest_id=None, xp_amount=100, change_type=XPChangeType.QUEST_COMPLETED, created_at=day)
        db.add(xp)
    # Add failures in last 7 days (3 failures)
    for i in range(3):
        day = today - timedelta(days=i)
        xp = XPHistory(user_id=user.id, quest_id=None, xp_amount=-20, change_type=XPChangeType.QUEST_FAILED, created_at=day)
        db.add(xp)

    # DailyProgress entries
    for i in range(7):
        day = today - timedelta(days=i)
        dp = DailyProgress(user_id=user.id, date=day, xp_earned_today=100, tasks_completed_today=1, tasks_failed_today=0)
        db.add(dp)

    db.commit()

    xp_7, completed_7, failed_7 = ProgressionAnalyticsService._get_7day_stats(user.id, db)
    assert xp_7 == 700
    assert completed_7 == 7
    # failed_7 comes from daily_progress (0), failures recorded in XPHistory shouldn't affect tasks_failed_today
    assert failed_7 == 0

    # Calculate a simple failure rate using XPHistory counts
    total_failures = db.query(XPHistory).filter(XPHistory.user_id == user.id, XPHistory.change_type == XPChangeType.QUEST_FAILED).count()
    total_completions = db.query(XPHistory).filter(XPHistory.user_id == user.id, XPHistory.change_type == XPChangeType.QUEST_COMPLETED).count()
    failure_rate = total_failures / (total_failures + total_completions)
    assert failure_rate == pytest.approx(3 / (3 + 7))


def test_calculate_streaks(seeded_user, db):
    user, stats = seeded_user
    today = date.today()

    # Create daily progress with a 3-day current streak and a longest streak of 4
    # Days: -5:- no, -4: yes, -3: yes, -2: yes, -1: yes, 0: yes -> longest 4, current 2? We'll craft explicitly
    dates_with_completion = [today - timedelta(days=d) for d in (0, 1, 2, 4)]
    # create entries
    for d in range(7):
        dp = DailyProgress(user_id=user.id, date=today - timedelta(days=d), xp_earned_today=100 if (today - timedelta(days=d)) in dates_with_completion else 0, tasks_completed_today=1 if (today - timedelta(days=d)) in dates_with_completion else 0)
        db.add(dp)
    db.commit()

    current, longest = ProgressionAnalyticsService._calculate_streak(user.id, db)
    # Today, yesterday, day before yesterday are in dates_with_completion -> current streak should be 3
    assert current == 3
    # Longest streak in this pattern is 3 as well (days 0-2)
    assert longest == 3


def test_stat_analysis_tiebreak_db(seeded_user, db):
    user, stats = seeded_user
    # Force a tie between strength and intelligence (set to 75, others lower)
    stats.strength = 75.0
    stats.intelligence = 75.0
    stats.vitality = 30.0
    stats.charisma = 40.0
    stats.mana = 50.0
    db.commit()

    strongest, strong_val, weakest, weak_val = ProgressionAnalyticsService._get_stat_analysis(stats)
    # Tiebreaker is alphabetical, intelligence < strength, so intelligence should be chosen as strongest when equal values
    assert strongest == "intelligence"  # Alphabetically first among tied max values
    assert weakest == "vitality"  # Lowest value
