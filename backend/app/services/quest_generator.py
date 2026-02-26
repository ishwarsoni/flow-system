"""QuestGenerator — the ONLY way to create quests from templates.

Architecture: Templates → Generator → User Quests → Registry

Rules:
- ALL system quests originate from templates. No exceptions.
- No blank quests. No empty titles. No NULL template_id on system quests.
- Cooldown and weekly limits are enforced before generation.
- Template must be active and match the requested domain+difficulty.
- This service is the single choke-point for quest creation from templates.

UNIQUENESS RULES (v2):
- RULE 1: No duplicate templates — same template_id cannot be active twice.
- RULE 2: One quest per domain per daily batch — no domain stacking.
- RULE 3: No same quest template reassigned within 48 hours.
- RULE 4: Level-aware generation — Level 1 = 1 EASY per domain = 6 total.
- RULE 5: Auto-cleanup of existing duplicates on generation.

Manual quests (is_manual=True) are the only quests allowed without template_id.
"""

from __future__ import annotations

import logging
import random
from datetime import datetime, timedelta, UTC
from typing import Optional

from sqlalchemy.orm import Session
from sqlalchemy import func, and_

from app.models.quest_template import QuestTemplate
from app.models.quest import (
    Quest, QuestType, QuestStatus, Difficulty, StatType, VerificationType,
)
from app.models.user_stats import UserStats
from app.models.domain import DOMAIN_CODES
from app.models.rank import get_allowed_difficulties
from app.services.difficulty_engine import (
    DURATION_CAPS, TIER_RULES, DifficultyEngine,
    EXTREME_COOLDOWN_HOURS, EXTREME_WEEKLY_LIMIT,
)

logger = logging.getLogger(__name__)

# ── Constants ──────────────────────────────────────────────────────────────────

VALID_DOMAINS = frozenset(DOMAIN_CODES)
ALL_DOMAINS = sorted(DOMAIN_CODES)  # deterministic order
VALID_DIFFICULTIES = frozenset({"easy", "intermediate", "hard", "extreme"})

TIER_TO_DIFFICULTY = {
    "easy": Difficulty.EASY,
    "intermediate": Difficulty.INTERMEDIATE,
    "hard": Difficulty.HARD,
    "extreme": Difficulty.EXTREME,
}

TIER_MULTIPLIERS = {
    "easy": 1.0,
    "intermediate": 1.5,
    "hard": 2.0,
    "extreme": 3.0,
}

COIN_PER_XP = 0.05  # 5% of XP as coins

DOMAIN_STAT_MAP = {
    "mind": StatType.INTELLIGENCE,
    "body": StatType.STRENGTH,
    "core": StatType.VITALITY,
    "control": StatType.MANA,
    "presence": StatType.CHARISMA,
    "system": StatType.INTELLIGENCE,
}

# RULE 3: Template reassignment cooldown
TEMPLATE_REASSIGN_COOLDOWN_HOURS = 48

# RULE 4: Daily quest count = one per domain = 6
DAILY_QUEST_COUNT = 6


# ── Exceptions ─────────────────────────────────────────────────────────────────

class GenerationError(Exception):
    """Raised when quest generation is rejected."""
    pass


class CooldownActiveError(GenerationError):
    """Raised when cooldown blocks generation."""
    pass


class WeeklyLimitError(GenerationError):
    """Raised when weekly limit is exceeded."""
    pass


class NoTemplateError(GenerationError):
    """Raised when no valid template matches."""
    pass


class InvalidRequestError(GenerationError):
    """Raised when domain/difficulty is invalid."""
    pass


class DuplicateTemplateError(GenerationError):
    """Raised when the template is already active for this user."""
    pass


class DomainAlreadyAssignedError(GenerationError):
    """Raised when the domain already has a quest today."""
    pass


class TemplateCooldownError(GenerationError):
    """Raised when the template was assigned within the last 48 hours."""
    pass


# ── Core Generator ─────────────────────────────────────────────────────────────

class QuestGenerator:
    """Stateless quest generation service. All methods are classmethods.

    UNIQUENESS GUARANTEES:
    - No duplicate template_id in active quests (RULE 1)
    - One quest per domain in daily batch (RULE 2)
    - No template reassignment within 48h (RULE 3)
    - Level-aware difficulty selection (RULE 4)
    - Auto-cleanup of stale duplicates (RULE 5)
    """

    # ── Public API ─────────────────────────────────────────────────────────────

    @classmethod
    def generate_quest(
        cls,
        db: Session,
        user_id: int,
        domain: str,
        difficulty: str,
    ) -> Quest:
        """Generate a single quest from a matching template.

        Pipeline:
            validate → cleanup duplicates → check active template →
            check 48h cooldown → check domain today → check extreme cooldown →
            check weekly limit → select template → create quest.

        Raises GenerationError (or subclass) on any rule violation.
        Returns the created Quest (already flushed but NOT committed — caller decides).
        """
        domain = domain.lower().strip()
        difficulty = difficulty.lower().strip()

        # 1. Validate inputs
        if domain not in VALID_DOMAINS:
            raise InvalidRequestError(
                f"Invalid domain '{domain}'. Must be one of: {', '.join(sorted(VALID_DOMAINS))}"
            )
        if difficulty not in VALID_DIFFICULTIES:
            raise InvalidRequestError(
                f"Invalid difficulty '{difficulty}'. Must be one of: {', '.join(sorted(VALID_DIFFICULTIES))}"
            )

        # 2. Enforce rank-based difficulty gate (single check, no duplicates)
        stats = db.query(UserStats).filter(UserStats.user_id == user_id).first()
        if stats:
            allowed = get_allowed_difficulties(stats.level)
            if difficulty not in allowed:
                raise InvalidRequestError(
                    f"Difficulty '{difficulty}' is locked. "
                    f"Your rank allows: {', '.join(allowed)}. Level up to unlock more."
                )

        # 3. RULE 5 — Cleanup any existing duplicate quests before generating
        cls._cleanup_duplicates(db, user_id)

        # 4. Check cooldown (extreme only)
        if difficulty == "extreme":
            cls._enforce_cooldown(db, user_id, domain)

        # 5. Check weekly limit (extreme only)
        if difficulty == "extreme":
            cls._enforce_weekly_limit(db, user_id)

        # 6. RULE 2 — Check if domain already has an active quest today
        cls._enforce_domain_uniqueness_today(db, user_id, domain)

        # 7. Get active template IDs for this user (RULE 1 filter)
        active_template_ids = cls._get_active_template_ids(db, user_id)

        # 8. Get templates on 48h cooldown (RULE 3 filter)
        cooldown_template_ids = cls._get_cooldown_template_ids(db, user_id)

        # 9. Combine exclusion sets
        excluded_template_ids = active_template_ids | cooldown_template_ids

        # 10. Select template (excluding active + cooldown)
        template = cls._select_template(db, domain, difficulty, excluded_template_ids)
        if template is None:
            raise NoTemplateError(
                f"No active template found for domain={domain}, difficulty={difficulty} "
                f"(excluded {len(excluded_template_ids)} active/cooldown templates). "
                "System cannot generate a quest without a unique template."
            )

        # 11. Build quest from template
        quest = cls._create_quest_from_template(db, user_id, template, difficulty)

        logger.info(
            f"QuestGenerator: created quest {quest.id} from template {template.id} "
            f"[{domain}/{difficulty}] for user {user_id} "
            f"(excluded {len(excluded_template_ids)} templates)"
        )
        return quest

    @classmethod
    def generate_daily_quests(
        cls,
        db: Session,
        user_id: int,
    ) -> list[Quest]:
        """Generate a balanced daily set: exactly ONE quest per domain.

        RULE 2: No domain stacking — each domain gets exactly one quest.
        RULE 4: Level-aware difficulty:
            - Level 1-5:  EASY only, all 6 domains
            - Level 6-12: EASY/INTERMEDIATE mix
            - Level 13-24: EASY/INTER/HARD mix
            - Level 25-39: INTER/HARD dominant
            - Level 40+:  Full spread including EXTREME

        Skips any domain where generation fails (cooldown, no template, etc.)
        Returns the list of created quests.
        """
        stats = db.query(UserStats).filter(UserStats.user_id == user_id).first()
        if not stats:
            logger.warning(f"QuestGenerator: no stats for user {user_id} — skip daily")
            return []

        # RULE 5 — Cleanup before generation
        cls._cleanup_duplicates(db, user_id)

        # Check which domains already have ANY active quest (PENDING/IN_PROGRESS)
        # Not just today — if yesterday's quest is still pending, don't generate a new one.
        existing_active = db.query(Quest).filter(
            Quest.user_id == user_id,
            Quest.auto_generated == True,
            Quest.status.in_([QuestStatus.PENDING, QuestStatus.IN_PROGRESS]),
        ).all()

        # RULE 2 — Track which domains already have active quests
        domains_used_today = {q.domain for q in existing_active if q.domain}

        if len(domains_used_today) >= len(ALL_DOMAINS):
            logger.info(
                f"QuestGenerator: user {user_id} already has quests for all domains today — skip"
            )
            return []

        # RULE 4 — Level-aware difficulty selection
        level = stats.level
        allowed = get_allowed_difficulties(level)
        difficulty_weights = cls._get_difficulty_weights(level, allowed)

        created = []
        # Iterate ALL domains in deterministic order — one quest per domain
        for domain in ALL_DOMAINS:
            # RULE 2 — Skip domains that already have a quest today
            if domain in domains_used_today:
                logger.debug(
                    f"QuestGenerator: domain {domain} already assigned today for user {user_id} — skip"
                )
                continue

            # RULE 4 — Pick difficulty based on level
            diff = cls._pick_difficulty(difficulty_weights)

            try:
                quest = cls.generate_quest(db, user_id, domain, diff)
                quest.quest_type = QuestType.DAILY
                quest.auto_generated = True
                quest.expires_at = (
                    datetime.now(UTC).replace(hour=23, minute=59, second=59, microsecond=0)
                )
                created.append(quest)
                domains_used_today.add(domain)  # Mark domain as used
            except GenerationError as e:
                logger.debug(f"QuestGenerator: daily gen skipped {domain}/{diff} — {e}")
                continue

        logger.info(
            f"QuestGenerator: generated {len(created)} daily quests for user {user_id} "
            f"(domains: {', '.join(q.domain for q in created)})"
        )
        return created

    @classmethod
    def list_templates(
        cls,
        db: Session,
        domain: Optional[str] = None,
        difficulty: Optional[str] = None,
        active_only: bool = True,
    ) -> list[QuestTemplate]:
        """List templates with optional filters."""
        query = db.query(QuestTemplate)

        if active_only:
            query = query.filter(QuestTemplate.is_active == True)
        if domain:
            query = query.filter(QuestTemplate.category == domain.lower().strip())
        if difficulty:
            query = query.filter(QuestTemplate.tier == difficulty.lower().strip())

        return query.order_by(QuestTemplate.category, QuestTemplate.tier, QuestTemplate.id).all()

    # ── RULE 5: Duplicate cleanup ──────────────────────────────────────────────

    @classmethod
    def _cleanup_duplicates(cls, db: Session, user_id: int) -> int:
        """Find and remove duplicate active quests for a user.

        RULE 5: If duplicates detected:
        - Keep the oldest (smallest id / earliest created_at)
        - Delete the newer duplicate
        - Log the system correction

        Duplicates are defined as:
        - Same user_id + same template_id + both active (PENDING or IN_PROGRESS)
        - Same domain appearing multiple times in today's auto-generated quests
        """
        active_quests = db.query(Quest).filter(
            Quest.user_id == user_id,
            Quest.template_id.isnot(None),
            Quest.status.in_([QuestStatus.PENDING, QuestStatus.IN_PROGRESS]),
        ).order_by(Quest.created_at.asc()).all()

        seen_templates: dict[int, Quest] = {}
        duplicates_removed = 0

        for quest in active_quests:
            template_id = quest.template_id
            if template_id in seen_templates:
                logger.warning(
                    f"RULE 5 CLEANUP: Removing duplicate quest {quest.id} "
                    f"(template={template_id}, domain={quest.domain}) for user {user_id}. "
                    f"Keeping quest {seen_templates[template_id].id}."
                )
                db.delete(quest)
                duplicates_removed += 1
            else:
                seen_templates[template_id] = quest

        # Also remove domain-stacked quests across ALL active quests (not just today)
        all_active_quests = db.query(Quest).filter(
            Quest.user_id == user_id,
            Quest.auto_generated == True,
            Quest.status.in_([QuestStatus.PENDING, QuestStatus.IN_PROGRESS]),
        ).order_by(Quest.created_at.asc()).all()

        seen_domains: dict[str, Quest] = {}
        for quest in all_active_quests:
            domain = quest.domain
            if domain and domain in seen_domains:
                logger.warning(
                    f"RULE 5 CLEANUP: Removing domain-stacked quest {quest.id} "
                    f"(domain={domain}) for user {user_id}. "
                    f"Keeping quest {seen_domains[domain].id}."
                )
                db.delete(quest)
                duplicates_removed += 1
            elif domain:
                seen_domains[domain] = quest

        if duplicates_removed > 0:
            db.flush()
            logger.info(
                f"RULE 5: Cleaned up {duplicates_removed} duplicate quests for user {user_id}"
            )

        return duplicates_removed

    # ── Internal uniqueness checks ─────────────────────────────────────────────

    @classmethod
    def _get_active_template_ids(cls, db: Session, user_id: int) -> set[int]:
        """RULE 1: Get template IDs currently active for this user."""
        rows = db.query(Quest.template_id).filter(
            Quest.user_id == user_id,
            Quest.template_id.isnot(None),
            Quest.status.in_([QuestStatus.PENDING, QuestStatus.IN_PROGRESS]),
        ).distinct().all()
        return {row[0] for row in rows}

    @classmethod
    def _get_cooldown_template_ids(cls, db: Session, user_id: int) -> set[int]:
        """RULE 3: Get template IDs assigned within the last 48 hours."""
        cutoff = datetime.now(UTC) - timedelta(hours=TEMPLATE_REASSIGN_COOLDOWN_HOURS)
        rows = db.query(Quest.template_id).filter(
            Quest.user_id == user_id,
            Quest.template_id.isnot(None),
            Quest.created_at >= cutoff,
        ).distinct().all()
        return {row[0] for row in rows}

    @classmethod
    def _enforce_domain_uniqueness_today(
        cls, db: Session, user_id: int, domain: str
    ) -> None:
        """RULE 2: Raise error if domain already has ANY active quest (PENDING/IN_PROGRESS).

        This prevents stacking across days — if a quest from yesterday is still
        pending, no new quest for that domain is generated until it's completed/failed.
        """
        existing = db.query(Quest).filter(
            Quest.user_id == user_id,
            Quest.domain == domain,
            Quest.auto_generated == True,
            Quest.status.in_([QuestStatus.PENDING, QuestStatus.IN_PROGRESS]),
        ).first()

        if existing:
            raise DomainAlreadyAssignedError(
                f"Domain '{domain.upper()}' already has an active quest "
                f"(quest #{existing.id}, created {existing.created_at}). "
                f"Complete or fail it before a new one can be generated."
            )

    # ── Template selection ─────────────────────────────────────────────────────

    @classmethod
    def _select_template(
        cls,
        db: Session,
        domain: str,
        difficulty: str,
        excluded_template_ids: set[int] | None = None,
    ) -> Optional[QuestTemplate]:
        """Select a random active template matching domain + difficulty.

        RULE 1 + RULE 3: Excludes templates that are already active or on 48h cooldown.
        """
        query = db.query(QuestTemplate).filter(
            QuestTemplate.category == domain,
            QuestTemplate.tier == difficulty,
            QuestTemplate.is_active == True,
        )

        if excluded_template_ids:
            query = query.filter(QuestTemplate.id.notin_(excluded_template_ids))

        templates = query.all()
        if not templates:
            return None

        weights = [t.selection_weight or 1.0 for t in templates]
        return random.choices(templates, weights=weights, k=1)[0]

    # ── Difficulty selection ───────────────────────────────────────────────────

    @classmethod
    def _get_difficulty_weights(cls, level: int, allowed: list[str]) -> dict[str, float]:
        """RULE 4: Get difficulty weights based on player level."""
        all_weights = {
            1:  {"easy": 1.0},
            6:  {"easy": 0.5, "intermediate": 0.5},
            13: {"easy": 0.2, "intermediate": 0.5, "hard": 0.3},
            25: {"easy": 0.1, "intermediate": 0.4, "hard": 0.5},
            40: {"easy": 0.05, "intermediate": 0.2, "hard": 0.5, "extreme": 0.25},
        }
        weights = {"easy": 1.0}
        for min_lv in sorted(all_weights.keys()):
            if level >= min_lv:
                weights = all_weights[min_lv]
        weights = {k: v for k, v in weights.items() if k in allowed}
        if not weights:
            weights = {"easy": 1.0}
        return weights

    @classmethod
    def _pick_difficulty(cls, weights: dict[str, float]) -> str:
        """Pick a difficulty using weighted random selection."""
        return random.choices(
            list(weights.keys()),
            weights=list(weights.values()),
            k=1,
        )[0]

    # ── Quest creation ─────────────────────────────────────────────────────────

    @classmethod
    def _create_quest_from_template(
        cls,
        db: Session,
        user_id: int,
        template: QuestTemplate,
        difficulty: str,
    ) -> Quest:
        """Instantiate a Quest from a QuestTemplate.

        Stamps last_assigned_at for RULE 3 enforcement.
        """
        tier = difficulty.lower()
        domain = template.category

        verification = (
            VerificationType.METRICS if tier in ("hard", "extreme")
            else VerificationType.LOG
        )

        base_xp = template.base_xp or 100
        coin_reward = max(1, round(base_xp * COIN_PER_XP))
        stat_rewards = template.stat_bonus or {}
        meta = template.meta_overrides or {}
        generates_penalty = meta.get("generates_penalty_quest", tier in ("hard", "extreme"))
        max_dur = template.max_duration_minutes or DURATION_CAPS.get(tier, 180)
        time_limit = max_dur
        perf_mult = TIER_MULTIPLIERS.get(tier, 1.0)
        rules = DifficultyEngine.defaults_for_tier(tier)
        cooldown = template.cooldown_hours or rules["cooldown_hours"]
        weekly_limit = rules.get("weekly_limit")

        title = template.title_template or f"{tier.capitalize()} {domain} quest"
        description = template.description_template or ""
        title = title.replace("{value}", str(max_dur)).replace("{unit}", "min").replace("{stat}", domain)
        description = description.replace("{value}", str(max_dur)).replace("{unit}", "min").replace("{stat}", domain)

        now = datetime.now(UTC)

        quest = Quest(
            user_id=user_id,
            template_id=template.id,
            title=title,
            description=description,
            quest_type=QuestType.DAILY,
            difficulty=TIER_TO_DIFFICULTY.get(tier, Difficulty.EASY),
            primary_stat=DOMAIN_STAT_MAP.get(domain, StatType.INTELLIGENCE),
            domain=domain,
            verification_type=verification,
            metrics_required=(tier in ("hard", "extreme")),
            cooldown_hours=cooldown,
            weekly_limit=weekly_limit,
            is_manual=False,
            base_xp_reward=base_xp,
            coin_reward=coin_reward,
            stat_rewards=stat_rewards if stat_rewards else None,
            penalty_xp=int(base_xp * 0.5),
            penalty_hp=int(base_xp * 0.1),
            generates_penalty_quest=generates_penalty,
            performance_multiplier=perf_mult,
            max_duration_minutes=max_dur,
            time_limit_minutes=time_limit,
            mp_cost=meta.get("mp_cost", 0),
            status=QuestStatus.PENDING,
            auto_generated=True,
            last_assigned_at=now,  # RULE 3: stamp for 48h cooldown
        )

        db.add(quest)
        db.flush()
        return quest

    # ── Extreme-specific enforcement ───────────────────────────────────────────

    @classmethod
    def _enforce_cooldown(cls, db: Session, user_id: int, domain: str) -> None:
        """Raise CooldownActiveError if an extreme quest was completed recently in this domain."""
        cutoff = datetime.now(UTC) - timedelta(hours=EXTREME_COOLDOWN_HOURS)
        recent = db.query(Quest).filter(
            Quest.user_id == user_id,
            Quest.domain == domain,
            Quest.difficulty == Difficulty.EXTREME,
            Quest.status == QuestStatus.COMPLETED,
            Quest.completed_at >= cutoff,
        ).order_by(Quest.completed_at.desc()).first()

        if recent and recent.completed_at:
            elapsed = (datetime.now(UTC) - recent.completed_at.replace(tzinfo=UTC)).total_seconds() / 3600
            remaining = EXTREME_COOLDOWN_HOURS - elapsed
            raise CooldownActiveError(
                f"Extreme cooldown active in {domain.upper()} domain. "
                f"{remaining:.1f}h remaining. Recovery between extreme efforts is mandatory."
            )

    @classmethod
    def _enforce_weekly_limit(cls, db: Session, user_id: int) -> None:
        """Raise WeeklyLimitError if extreme completions this week >= limit."""
        week_start = datetime.now(UTC) - timedelta(days=7)
        count = db.query(Quest).filter(
            Quest.user_id == user_id,
            Quest.difficulty == Difficulty.EXTREME,
            Quest.status == QuestStatus.COMPLETED,
            Quest.completed_at >= week_start,
        ).count()

        if count >= EXTREME_WEEKLY_LIMIT:
            raise WeeklyLimitError(
                f"Extreme weekly limit reached ({EXTREME_WEEKLY_LIMIT}/week). "
                "Wait until one of this week's extreme completions ages past 7 days."
            )
