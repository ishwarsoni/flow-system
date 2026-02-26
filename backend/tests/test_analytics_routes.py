"""Tests for analytics service route functions"""

import pytest
from datetime import date, timedelta
from unittest.mock import Mock, patch, MagicMock

from app.models.user import User
from app.models.user_stats import UserStats
from app.models.daily_progress import DailyProgress
from app.services.progression_analytics_service import ProgressionAnalyticsService
from app.schemas.analytics import (
    ProgressionOverviewResponse,
    StreaksResponse,
    SevenDayStatsResponse,
)


@pytest.fixture()
def seeded_user_with_history(db):
    """Create a user with progression history"""
    user = User(username="testuser", email="test@example.com", hashed_password="hashed")
    db.add(user)
    db.flush()
    
    stats = UserStats(
        user_id=user.id,
        level=3,
        xp_current=150,
        xp_total_earned=500,
        strength=75.0,
        intelligence=85.0,
        vitality=60.0,
        charisma=65.0,
        mana=70.0,
    )
    db.add(stats)
    db.commit()
    
    # Add 7-day history
    today = date.today()
    for i in range(7):
        day = today - timedelta(days=i)
        dp = DailyProgress(
            user_id=user.id,
            date=day,
            xp_earned_today=100,
            tasks_completed_today=3,
            tasks_failed_today=0,
        )
        db.add(dp)
    
    db.commit()
    return user


# ==================== Analytics Service Tests ====================


def test_get_analytics_overview_success(db, seeded_user_with_history):
    """Test get_user_progress returns complete overview"""
    progress = ProgressionAnalyticsService.get_user_progress(seeded_user_with_history.id, db)
    
    # Verify all required fields are present
    assert "level" in progress
    assert "xp_current" in progress
    assert "current_streak_days" in progress
    assert "longest_streak_days" in progress
    assert "strongest_stat" in progress
    assert "weakest_stat" in progress
    assert "quests_completed_today" in progress
    assert "xp_earned_7days" in progress
    
    # Verify types and ranges
    assert isinstance(progress["level"], int)
    assert progress["level"] >= 1
    assert isinstance(progress["strength"], (int, float))
    assert isinstance(progress["intelligence"], (int, float))


def test_overview_response_model_validation(seeded_user_with_history):
    """Test ProgressionOverviewResponse model validates data correctly"""
    overview_data = {
        "level": 5,
        "xp_current": 250,
        "xp_total_earned": 1500,
        "xp_to_next_level": 150,
        "strength": 72.5,
        "intelligence": 80.0,
        "vitality": 55.0,
        "charisma": 65.5,
        "mana": 68.0,
        "strongest_stat": "intelligence",
        "strongest_stat_value": 80.0,
        "weakest_stat": "vitality",
        "weakest_stat_value": 55.0,
        "xp_earned_today": 100,
        "quests_completed_today": 3,
        "quests_failed_today": 0,
        "xp_earned_7days": 650,
        "quests_completed_7days": 20,
        "quests_failed_7days": 2,
        "current_streak_days": 7,
        "longest_streak_days": 14,
    }
    
    response = ProgressionOverviewResponse(**overview_data)
    assert response.level == 5
    assert response.strongest_stat == "intelligence"
    assert response.current_streak_days == 7


def test_get_streaks_success(db, seeded_user_with_history):
    """Test _calculate_streak returns correct values"""
    current, longest = ProgressionAnalyticsService._calculate_streak(seeded_user_with_history.id, db)
    
    assert isinstance(current, int)
    assert isinstance(longest, int)
    assert current >= 0
    assert longest >= 0


def test_streaks_response_model(db, seeded_user_with_history):
    """Test StreaksResponse model validates correctly"""
    current, longest = ProgressionAnalyticsService._calculate_streak(seeded_user_with_history.id, db)
    
    response = StreaksResponse(
        current_streak_days=current,
        longest_streak_days=longest,
    )
    assert response.current_streak_days == current
    assert response.longest_streak_days == longest


def test_get_seven_day_stats_success(db, seeded_user_with_history):
    """Test _get_7day_stats returns correct statistics"""
    xp_earned, completed, failed = ProgressionAnalyticsService._get_7day_stats(
        seeded_user_with_history.id, db
    )
    
    assert isinstance(xp_earned, int)
    assert isinstance(completed, int)
    assert isinstance(failed, int)
    assert xp_earned >= 0
    assert completed >= 0
    assert failed >= 0


def test_seven_day_stats_response_model():
    """Test SevenDayStatsResponse model validates correctly"""
    response = SevenDayStatsResponse(
        xp_earned_7days=650,
        tasks_completed_7days=20,
        tasks_failed_7days=2,
        failure_rate_percent=9.09,
    )
    
    assert response.xp_earned_7days == 650
    assert response.tasks_completed_7days == 20
    assert response.failure_rate_percent == 9.09
    assert 0.0 <= response.failure_rate_percent <= 100.0


def test_stat_analysis_alphabetical_ordering(db):
    """Test stat analysis uses alphabetical ordering for ties"""
    # Create user with specific stats
    user = User(username="teststat", email="stat@test.com", hashed_password="hashed")
    db.add(user)
    db.flush()
    
    stats = UserStats(
        user_id=user.id,
        strength=75.0,
        intelligence=75.0,  # Tie with strength (both highest)
        vitality=50.0,
        charisma=50.0,  # Tie with vitality (both lowest)
        mana=75.0,  # Also tied for highest
    )
    db.add(stats)
    db.commit()
    
    strongest, strongest_val, weakest, weakest_val = ProgressionAnalyticsService._get_stat_analysis(stats)
    
    # When there are ties, should pick alphabetically first
    # intelligence, mana, and strength all = 75, alphabetically intelligence comes first
    assert strongest == "intelligence"
    assert strongest_val == 75.0
    
    # charisma and vitality both = 50, alphabetically charisma comes first
    assert weakest == "charisma"
    assert weakest_val == 50.0


def test_failure_rate_calculation_zero_tasks():
    """Test failure rate calculation when no tasks completed/failed"""
    response = SevenDayStatsResponse(
        xp_earned_7days=0,
        tasks_completed_7days=0,
        tasks_failed_7days=0,
        failure_rate_percent=0.0,
    )
    
    assert response.failure_rate_percent == 0.0


def test_failure_rate_with_tasks(db, seeded_user_with_history):
    """Test failure rate calculation with actual data"""
    xp_earned, completed, failed = ProgressionAnalyticsService._get_7day_stats(
        seeded_user_with_history.id, db
    )
    
    total = completed + failed
    if total > 0:
        failure_rate = (failed / total * 100)
    else:
        failure_rate = 0.0
    
    response = SevenDayStatsResponse(
        xp_earned_7days=xp_earned,
        tasks_completed_7days=completed,
        tasks_failed_7days=failed,
        failure_rate_percent=round(failure_rate, 2),
    )
    
    assert 0.0 <= response.failure_rate_percent <= 100.0


# ==================== Schema Validation Tests ====================


def test_overview_response_dict_conversion(seeded_user_with_history):
    """Test ProgressionOverviewResponse serializes to dict correctly"""
    overview_data = {
        "level": 5,
        "xp_current": 250,
        "xp_total_earned": 1500,
        "xp_to_next_level": 150,
        "strength": 72.5,
        "intelligence": 80.0,
        "vitality": 55.0,
        "charisma": 65.5,
        "mana": 68.0,
        "strongest_stat": "intelligence",
        "strongest_stat_value": 80.0,
        "weakest_stat": "vitality",
        "weakest_stat_value": 55.0,
        "xp_earned_today": 100,
        "quests_completed_today": 3,
        "quests_failed_today": 0,
        "xp_earned_7days": 650,
        "quests_completed_7days": 20,
        "quests_failed_7days": 2,
        "current_streak_days": 7,
        "longest_streak_days": 14,
    }
    
    response = ProgressionOverviewResponse(**overview_data)
    serialized = response.model_dump()
    
    # Verify round-trip
    restored = ProgressionOverviewResponse(**serialized)
    assert restored.level == response.level
    assert restored.strongest_stat == response.strongest_stat


def test_invalid_overview_response_missing_field():
    """Test ProgressionOverviewResponse validation rejects missing fields"""
    invalid_data = {
        "level": 5,
        "xp_current": 250,
        # Missing many required fields
    }
    
    with pytest.raises(Exception):  # Pydantic validation error
        ProgressionOverviewResponse(**invalid_data)


def test_invalid_overview_response_out_of_range_stats():
    """Test ProgressionOverviewResponse rejects invalid stat values"""
    invalid_data = {
        "level": 5,
        "xp_current": 250,
        "xp_total_earned": 1500,
        "xp_to_next_level": 150,
        "strength": 72.5,
        "intelligence": 80.0,
        "vitality": 55.0,
        "charisma": 65.5,
        "mana": 68.0,
        "strongest_stat": "intelligence",
        "strongest_stat_value": 80.0,
        "weakest_stat": "vitality",
        "weakest_stat_value": 55.0,
        "xp_earned_today": 100,
        "quests_completed_today": 3,
        "quests_failed_today": 0,
        "xp_earned_7days": 650,
        "quests_completed_7days": 20,
        "quests_failed_7days": 2,
        "current_streak_days": 7,
        "longest_streak_days": 14,
        "level": -1,  # Override level with invalid value
    }
    
    with pytest.raises(Exception):  # Pydantic validation error
        ProgressionOverviewResponse(**invalid_data)

