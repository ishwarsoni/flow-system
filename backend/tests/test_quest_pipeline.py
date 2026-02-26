"""Tests for the quest generation pipeline.

Covers:
- Template selection (weighted random from DB)
- Generator rules (domain + difficulty validation)
- Cooldown enforcement (extreme quests: 24h per domain)
- Weekly limit enforcement (extreme quests: 3/week)
- No blank quests — template_id is always set
- Daily generation (balanced across domains)
"""

import pytest
from datetime import datetime, timedelta, UTC

from app.models.user import User
from app.models.user_stats import UserStats
from app.models.quest import Quest, QuestStatus, QuestType, Difficulty
from app.models.quest_template import QuestTemplate
from app.services.quest_generator import (
    QuestGenerator,
    CooldownActiveError,
    WeeklyLimitError,
    NoTemplateError,
    InvalidRequestError,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture()
def user(db):
    """Create a test user with stats."""
    u = User(username="hunter", email="hunter@test.local", hashed_password="x")
    db.add(u)
    db.flush()
    stats = UserStats(
        user_id=u.id,
        level=5,
        xp_current=500,
        hp_current=100,
        hp_max=100,
        mp_current=50,
        mp_max=50,
        coins=100,
        focus=10.0,
        discipline=10.0,
        energy=10.0,
        intelligence=10.0,
        consistency=10.0,
    )
    db.add(stats)
    db.commit()
    return u


@pytest.fixture()
def templates(db):
    """Seed a minimal set of templates across domains and tiers."""
    created = []
    domains = ["mind", "body", "core", "control", "presence", "system"]
    tiers = ["easy", "intermediate", "hard", "extreme"]

    for domain in domains:
        for tier in tiers:
            t = QuestTemplate(
                category=domain,
                tier=tier,
                phase="foundation",
                title_template=f"Test {domain} {tier} quest",
                description_template=f"Do something {tier} in {domain}.",
                unit_type="minutes",
                base_xp={"easy": 50, "intermediate": 100, "hard": 200, "extreme": 400}[tier],
                max_duration_minutes={"easy": 60, "intermediate": 120, "hard": 180, "extreme": 240}[tier],
                constraint_level={"easy": 1, "intermediate": 2, "hard": 3, "extreme": 4}[tier],
                performance_required=tier in ("hard", "extreme"),
                risk_level={"easy": 1, "intermediate": 2, "hard": 3, "extreme": 4}[tier],
                cooldown_hours={"easy": 0, "intermediate": 0, "hard": 4, "extreme": 24}[tier],
                is_active=True,
                selection_weight=1.0,
            )
            db.add(t)
            created.append(t)

    db.commit()
    return created


@pytest.fixture()
def mind_easy_template(db):
    """Single easy mind template."""
    t = QuestTemplate(
        category="mind",
        tier="easy",
        phase="foundation",
        title_template="Read 20 pages",
        description_template="Read with focus.",
        unit_type="pages",
        base_xp=50,
        max_duration_minutes=60,
        constraint_level=1,
        performance_required=False,
        risk_level=1,
        cooldown_hours=0,
        is_active=True,
        selection_weight=1.0,
    )
    db.add(t)
    db.commit()
    return t


# ── Template selection tests ─────────────────────────────────────────────────

class TestTemplateSelection:
    def test_list_templates_returns_active(self, db, templates):
        result = QuestGenerator.list_templates(db)
        assert len(result) == 24  # 6 domains × 4 tiers

    def test_list_templates_filter_by_domain(self, db, templates):
        result = QuestGenerator.list_templates(db, domain="mind")
        assert len(result) == 4
        assert all(t.category == "mind" for t in result)

    def test_list_templates_filter_by_difficulty(self, db, templates):
        result = QuestGenerator.list_templates(db, difficulty="extreme")
        assert len(result) == 6  # one per domain
        assert all(t.tier == "extreme" for t in result)

    def test_list_templates_excludes_inactive(self, db, templates):
        # Deactivate all mind templates
        for t in templates:
            if t.category == "mind":
                t.is_active = False
        db.commit()

        result = QuestGenerator.list_templates(db, domain="mind")
        assert len(result) == 0

    def test_list_templates_domain_and_difficulty(self, db, templates):
        result = QuestGenerator.list_templates(db, domain="body", difficulty="hard")
        assert len(result) == 1
        assert result[0].category == "body"
        assert result[0].tier == "hard"


# ── Quest generation tests ───────────────────────────────────────────────────

class TestQuestGeneration:
    def test_generate_creates_quest_with_template_id(self, db, user, mind_easy_template):
        quest = QuestGenerator.generate_quest(db, user.id, domain="mind", difficulty="easy")
        db.commit()

        assert quest is not None
        assert quest.template_id == mind_easy_template.id
        assert quest.user_id == user.id
        assert quest.title is not None
        assert len(quest.title) > 0

    def test_generate_sets_correct_difficulty(self, db, user, templates):
        # Hard quests require rank C+ (level 13+), so bump the user's level
        stats = db.query(UserStats).filter(UserStats.user_id == user.id).first()
        stats.level = 25
        db.flush()
        quest = QuestGenerator.generate_quest(db, user.id, domain="body", difficulty="hard")
        db.commit()

        assert quest.difficulty.value in ("hard", "medium")  # TIER_TO_DIFFICULTY maps hard → hard

    def test_generate_sets_status_pending(self, db, user, mind_easy_template):
        quest = QuestGenerator.generate_quest(db, user.id, domain="mind", difficulty="easy")
        db.commit()

        assert quest.status == QuestStatus.PENDING

    def test_generate_sets_xp_from_template(self, db, user, mind_easy_template):
        quest = QuestGenerator.generate_quest(db, user.id, domain="mind", difficulty="easy")
        db.commit()

        assert quest.base_xp_reward > 0

    def test_no_blank_quest_without_template(self, db, user):
        """No quest may exist without a template. If no template → error, not blank record."""
        with pytest.raises(NoTemplateError):
            QuestGenerator.generate_quest(db, user.id, domain="mind", difficulty="easy")

    def test_generate_multiple_different_quests(self, db, user, templates):
        """Multiple generations should produce independent quests."""
        q1 = QuestGenerator.generate_quest(db, user.id, domain="mind", difficulty="easy")
        q2 = QuestGenerator.generate_quest(db, user.id, domain="body", difficulty="easy")
        db.commit()

        assert q1.id != q2.id
        assert q1.template_id is not None
        assert q2.template_id is not None


# ── Input validation tests ───────────────────────────────────────────────────

class TestInputValidation:
    def test_invalid_domain_raises(self, db, user, templates):
        with pytest.raises(InvalidRequestError, match="domain"):
            QuestGenerator.generate_quest(db, user.id, domain="invalid", difficulty="easy")

    def test_invalid_difficulty_raises(self, db, user, templates):
        with pytest.raises(InvalidRequestError, match="difficulty"):
            QuestGenerator.generate_quest(db, user.id, domain="mind", difficulty="godmode")


# ── Cooldown enforcement tests ───────────────────────────────────────────────

class TestCooldownEnforcement:
    def test_extreme_cooldown_blocks_same_domain(self, db, user, templates):
        """After completing an extreme quest in a domain, another extreme in the same domain is blocked."""
        # Extreme requires A-rank (level 40+)
        stats = db.query(UserStats).filter(UserStats.user_id == user.id).first()
        stats.level = 50
        db.flush()
        # Generate and immediately complete an extreme quest
        quest = QuestGenerator.generate_quest(db, user.id, domain="mind", difficulty="extreme")
        quest.status = QuestStatus.COMPLETED
        quest.completed_at = datetime.now(UTC).replace(tzinfo=None)
        db.commit()

        # Trying again should hit cooldown
        with pytest.raises(CooldownActiveError):
            QuestGenerator.generate_quest(db, user.id, domain="mind", difficulty="extreme")

    def test_extreme_cooldown_allows_different_domain(self, db, user, templates):
        """Extreme cooldown is per-domain — different domain should work."""
        stats = db.query(UserStats).filter(UserStats.user_id == user.id).first()
        stats.level = 50
        db.flush()
        quest = QuestGenerator.generate_quest(db, user.id, domain="mind", difficulty="extreme")
        quest.status = QuestStatus.COMPLETED
        quest.completed_at = datetime.now(UTC).replace(tzinfo=None)
        db.commit()

        # Different domain should work
        q2 = QuestGenerator.generate_quest(db, user.id, domain="body", difficulty="extreme")
        db.commit()
        assert q2 is not None

    def test_non_extreme_no_cooldown(self, db, user, templates):
        """Easy/intermediate/hard quests have no generation cooldown."""
        q1 = QuestGenerator.generate_quest(db, user.id, domain="mind", difficulty="easy")
        q1.status = QuestStatus.COMPLETED
        q1.completed_at = datetime.now(UTC).replace(tzinfo=None)
        db.commit()

        # Should work immediately
        q2 = QuestGenerator.generate_quest(db, user.id, domain="mind", difficulty="easy")
        db.commit()
        assert q2 is not None


# ── Weekly limit tests ───────────────────────────────────────────────────────

class TestWeeklyLimit:
    def test_extreme_weekly_limit_blocks_after_3(self, db, user, templates):
        """Only 3 extreme quests per week across all domains."""
        stats = db.query(UserStats).filter(UserStats.user_id == user.id).first()
        stats.level = 50
        db.flush()
        domains = ["mind", "body", "core"]
        for d in domains:
            q = QuestGenerator.generate_quest(db, user.id, domain=d, difficulty="extreme")
            q.status = QuestStatus.COMPLETED
            q.completed_at = datetime.now(UTC).replace(tzinfo=None)
            db.commit()

        # 4th should be blocked
        with pytest.raises(WeeklyLimitError):
            QuestGenerator.generate_quest(db, user.id, domain="control", difficulty="extreme")

    def test_non_extreme_no_weekly_limit(self, db, user, templates):
        """Easy quests have no weekly limit."""
        for i in range(5):
            q = QuestGenerator.generate_quest(db, user.id, domain="mind", difficulty="easy")
            q.status = QuestStatus.COMPLETED
            q.completed_at = datetime.now(UTC).replace(tzinfo=None)
            db.commit()

        # 6th should still work
        q6 = QuestGenerator.generate_quest(db, user.id, domain="mind", difficulty="easy")
        db.commit()
        assert q6 is not None


# ── Daily generation tests ───────────────────────────────────────────────────

class TestDailyGeneration:
    def test_daily_generates_quests(self, db, user, templates):
        quests = QuestGenerator.generate_daily_quests(db, user.id)
        db.commit()

        assert len(quests) > 0
        assert len(quests) <= 4  # default daily count

    def test_daily_quests_have_template_ids(self, db, user, templates):
        quests = QuestGenerator.generate_daily_quests(db, user.id)
        db.commit()

        for q in quests:
            assert q.template_id is not None, f"Quest '{q.title}' has no template_id"

    def test_daily_covers_multiple_domains(self, db, user, templates):
        """Daily generation should spread across domains, not stack one."""
        quests = QuestGenerator.generate_daily_quests(db, user.id, count=4)
        db.commit()

        domains = set(q.domain for q in quests if q.domain)
        # With 4 quests and 6 domains available, expect at least 2 different domains
        assert len(domains) >= 2

    def test_daily_respects_count(self, db, user, templates):
        quests = QuestGenerator.generate_daily_quests(db, user.id, count=2)
        db.commit()

        assert len(quests) <= 2
