"""AdaptiveQuestService — three-tier quest generation engine.

Design contract
---------------
1.  Call generate_trio(user_id, category, db) → QuestTrioResponse
2.  Frontend shows all three options to the player.
3.  Player calls choose_tier(session_id, chosen_tier, user_id, db) → ChooseTierResponse
    This creates the actual Quest row and records the mindset delta.
4.  Quest completion / failure flows through existing ProgressionService +
    PenaltyEngine.  Call resolve_session() to mark the session outcome.

Generation algorithm
--------------------
    phase         = phase_for_level(stats.level)
    tier_config   = load ProgressionTier for phase
    diff_profile  = load DifficultyProfile for (category, phase)

    base_difficulty = tier_config.base_difficulty * f(stats)    ← stat amplifier
    mindset_bonus   = mindset_amplifier(mindset_score)          ← 0.9 – 1.2

    easy_value         = base_difficulty * diff_profile.easy_multiplier
    intermediate_value = base_difficulty * diff_profile.intermediate_multiplier
    hard_value         = base_difficulty * diff_profile.hard_multiplier

    xp for each tier = diff_profile.{tier}_xp_base
                     * tier_config.xp_scale
                     * rank_multiplier
                     * mindset_bonus

Then templates are selected from quest_templates and the computed values
are interpolated into title / description strings.

Stat amplifier
--------------
The player's primary stat for the category increases base difficulty slightly
so high-stat players face harder numbers:

    amplifier = 1.0 + (relevant_stat / max_stat) * 0.3
    (caps at 1.30 amplification)
"""

from __future__ import annotations

import math
import random
from datetime import datetime, timedelta, UTC
from typing import Optional

from sqlalchemy.orm import Session

from app.models.difficulty_profile import DifficultyProfile
from app.models.progression_tier import ProgressionTier
from app.models.quest_template import QuestTemplate
from app.models.adaptive_quest_session import AdaptiveQuestSession
from app.models.user_stats import UserStats
from app.models.quest import Quest, QuestType, QuestStatus, Difficulty as QuestDifficulty, StatType, VerificationType
from app.models.rank import RANK_CONFIG, Rank, get_allowed_difficulties
from app.services.mindset_engine import MindsetEngine
from app.services.custom_quest_service import custom_quest_service
from app.services.difficulty_engine import DifficultyEngine, TIER_RULES, DURATION_CAPS
from app.schemas.adaptive_quest import (
    QuestOption,
    QuestTrioResponse,
    ChooseTierResponse,
    DailyQuestPanel,
)


from app.models.domain import DOMAIN_CODES

# ── Domain → stat mapping ─────────────────────────────────────────────────────

DOMAIN_STAT_MAP: dict[str, str] = {
    "mind":     "intelligence",
    "body":     "strength",
    "core":     "vitality",
    "control":  "mana",
    "presence": "charisma",
    "system":   "intelligence",
}

# ── Tier → QuestDifficulty enum ───────────────────────────────────────────────

TIER_TO_DIFFICULTY: dict[str, QuestDifficulty] = {
    "easy":         QuestDifficulty.EASY,
    "intermediate": QuestDifficulty.INTERMEDIATE,
    "hard":         QuestDifficulty.HARD,
    "extreme":      QuestDifficulty.EXTREME,
}

TIER_TO_STAT_TYPE: dict[str, StatType] = {
    "mind":     StatType.INTELLIGENCE,
    "body":     StatType.STRENGTH,
    "core":     StatType.VITALITY,
    "control":  StatType.MANA,
    "presence": StatType.CHARISMA,
    "system":   StatType.INTELLIGENCE,
}

SESSION_EXPIRY_HOURS = 12   # Player has 12 h to choose from a generated trio


# ── Default templates (guaranteed fallback) ───────────────────────────────────

_DEFAULT_TEMPLATES: dict[str, dict[str, dict]] = {
    "mind": {
        "easy":         {"title": "Read 15 pages + write 5-bullet summary",                "desc": "Passive input is banned. Read 15 pages, then write exactly 5 bullet points of what you retained. If you can't write them, you didn't read.", "unit": "tasks"},
        "intermediate": {"title": "90-min deep work block + concept map output",           "desc": "90 min. One topic. Full focus. End product: a drawn concept map that someone else could understand.",                                       "unit": "tasks"},
        "hard":         {"title": "2-hour deep work sprint + publish your notes",          "desc": "Two full hours, no exits. Produce notes clean enough to share. Then share them — email, upload, or show someone. Output is evidence.",       "unit": "tasks"},
        "extreme":      {"title": "3-hour focused sprint — defined output delivered",      "desc": "Three hours. One task. Zero tolerance for interruption. You define the output target before you start. Deliver it. No extensions.",          "unit": "tasks"},
    },
    "body": {
        "easy":         {"title": "30 squats + 20 pushups — log your reps",                "desc": "Full depth squats. Chest-to-floor pushups. No partial reps counted. Write down what you actually completed.",                               "unit": "tasks"},
        "intermediate": {"title": "45-min workout — log every set and rep",                "desc": "45 minutes of structured training. Every set, every rep logged. No memory — write it in real time.",                                       "unit": "tasks"},
        "hard":         {"title": "60-min training session — performance focus",           "desc": "60 minutes. Defined exercises. Performance target set before you start. Track against last session.",                                        "unit": "tasks"},
        "extreme":      {"title": "90-min structured training — split logged",             "desc": "90 minutes. Pre-written programme. Every exercise performed as written. Total volume calculated at the end.",                               "unit": "tasks"},
    },
    "core": {
        "easy":         {"title": "Sleep before 11 PM — no exceptions tonight",            "desc": "In bed by 22:45. Lights off by 23:00. No scrolling. No justifications. Log your actual sleep time.",                                       "unit": "tasks"},
        "intermediate": {"title": "Fixed sleep window — same time for 3 days",             "desc": "Pick a sleep time and wake time. Hit it for 3 consecutive nights. Variance allowed: 15 minutes max. Log each night.",                      "unit": "tasks"},
        "hard":         {"title": "Sleep consistency 5 days straight — log nightly",       "desc": "Same bedtime (±15 min) for 5 nights. Log each: time in bed, estimated sleep onset, wake time. Miss one night = restart.",                 "unit": "tasks"},
        "extreme":      {"title": "7-day sleep + recovery protocol — every element logged","desc": "7 days: sleep before 23:00, 7.5h minimum, 3L water, no alcohol, controlled caffeine, blue light off by 21:00. Log every single day.",     "unit": "tasks"},
    },
    "control": {
        "easy":         {"title": "No phone for 30 minutes — do a real task instead",      "desc": "Phone off or in another room. 30 full minutes. Use the time for one focused, real task.",                                                  "unit": "tasks"},
        "intermediate": {"title": "90-min phone-free work block — timed",                  "desc": "Set a 90-minute timer. No phone access. No social media. Successful completion must be uninterrupted.",                                   "unit": "tasks"},
        "hard":         {"title": "4-hour low-dopamine day — no instant gratification",    "desc": "4 hours of your waking time: no social media, no gaming, no TV, no YouTube. Log what you did with the time instead. Output required.",    "unit": "tasks"},
        "extreme":      {"title": "72-hour discipline protocol — logged every hour",       "desc": "3 days: no social media, cold shower daily, wake same time, hard task first, no junk. Every day logged. Every failure noted honestly.",    "unit": "tasks"},
    },
    "presence": {
        "easy":         {"title": "Start a conversation with a stranger today",            "desc": "Initiate. Not a text. Not online. In person or on a call. Ask a question, make an observation, start something. Log what happened.",      "unit": "tasks"},
        "intermediate": {"title": "Present a 5-minute talk on any topic",                  "desc": "Prepare and deliver a 5-minute presentation. Real audience or recorded. Structured: opening, 3 points, close. Review and note weaknesses.","unit": "tasks"},
        "hard":         {"title": "Deliver a prepared public speech or presentation",      "desc": "Audience of 5+. Prepared material. No reading from notes.",                                                                               "unit": "tasks"},
        "extreme":      {"title": "Lead an event or group from start to finish",           "desc": "You organize, you lead, you facilitate, you close. Real people. Real outcome. Pre-planning required. Post-event written debrief mandatory.","unit": "tasks"},
    },
    "system": {
        "easy":         {"title": "Plan tomorrow — every task written down tonight",       "desc": "Before you sleep: write out tomorrow's full task list. Prioritised. Specific. No vague items.",                                           "unit": "tasks"},
        "intermediate": {"title": "Build a full plan for this week — every block scheduled","desc": "Every major activity this week assigned to a time block. Work, training, recovery, admin. Written. Calendar-ready.",                     "unit": "tasks"},
        "hard":         {"title": "Build a monthly roadmap — every goal has a deadline",   "desc": "Map out the full month: goals, milestones, weekly targets. Every item has a due date and success criterion. This must be actionable.",     "unit": "tasks"},
        "extreme":      {"title": "Build a personal life dashboard — all key metrics",     "desc": "One document tracking: finance, health, learning, relationships, projects — each with a target and current status. Update it.",            "unit": "tasks"},
    },
}

# Per-tier XP/stat reward templates for easy/intermediate/hard/extreme
_STAT_REWARD_MAP: dict[str, dict[str, float]] = {
    "easy":         {"primary": 1.0, "secondary": 0.5},
    "intermediate": {"primary": 2.0, "secondary": 1.0},
    "hard":         {"primary": 3.5, "secondary": 1.5},
    "extreme":      {"primary": 5.5, "secondary": 2.0},
}


def _get_relevant_stat(domain: str, stats: UserStats) -> float:
    """Return the player's current value for the primary stat of the domain."""
    attr = DOMAIN_STAT_MAP.get(domain, "intelligence")
    return float(getattr(stats, attr, 10.0))


def _stat_amplifier(stat_value: float, max_stat: float = 100.0) -> float:
    """Convert a stat value to a difficulty amplifier (1.0 – 1.30)."""
    return 1.0 + min(stat_value / max_stat, 1.0) * 0.30


def _mindset_amplifier(mindset_score: float) -> float:
    """Higher mindset → slightly harder generated quests and better XP.

    Range: 0.90 (dormant) – 1.20 (elite).
    """
    normalised = mindset_score / 1000.0          # 0.0 – 1.0
    return 0.90 + normalised * 0.30


def _phase_for_level(level: int) -> str:
    if level <= 10:
        return "entry"
    elif level <= 30:
        return "growth"
    return "mastery"


def _rank_xp_multiplier(rank: Rank) -> float:
    return RANK_CONFIG[rank].get("xp_multiplier", 1.0)


def _format_value(value: float, unit_type: str) -> tuple[float, str]:
    """Round value appropriately for display."""
    if unit_type in ("minutes", "min"):
        return round(value / 5) * 5, "min"   # Round to nearest 5 min
    elif unit_type == "hours":
        return round(value * 2) / 2, "hours"  # Round to 0.5
    elif unit_type in ("reps",):
        return max(1, round(value / 5) * 5), "reps"
    elif unit_type == "pages":
        return max(1, round(value)), "pages"
    elif unit_type == "km":
        return round(value * 10) / 10, "km"
    else:
        return round(value), unit_type


def _load_tier_config(phase: str, db: Session) -> Optional[ProgressionTier]:
    return db.query(ProgressionTier).filter(
        ProgressionTier.phase == phase,
        ProgressionTier.is_active == True,
    ).first()


def _load_diff_profile(category: str, phase: str, db: Session) -> Optional[DifficultyProfile]:
    return db.query(DifficultyProfile).filter(
        DifficultyProfile.category == category,
        DifficultyProfile.phase == phase,
        DifficultyProfile.is_active == True,
    ).first()


def _load_template(category: str, tier: str, phase: str, db: Session) -> Optional[QuestTemplate]:
    """Load a random template matching category/tier/phase (or category/tier/any)."""
    rows = db.query(QuestTemplate).filter(
        QuestTemplate.category == category,
        QuestTemplate.tier == tier,
        QuestTemplate.phase.in_([phase, "any"]),
        QuestTemplate.is_active == True,
    ).all()
    if not rows:
        return None
    # Weighted random selection
    weights = [r.selection_weight for r in rows]
    return random.choices(rows, weights=weights, k=1)[0]


def _build_option(
    tier: str,
    category: str,
    template: Optional[QuestTemplate],
    value: float,
    xp: int,
    coin: int,
    penalty_xp: int,
    primary_stat: str,
    stat_rewards: dict,
    diff_profile: Optional[DifficultyProfile],
) -> QuestOption:
    """Construct a QuestOption from computed values and template text."""

    default_t = _DEFAULT_TEMPLATES.get(category, {}).get(tier, {})

    if template:
        unit_type = template.unit_type
        title_raw = template.title_template
        desc_raw = template.description_template or ""
        # Use template's structured difficulty axes if available
        constraint_level    = template.constraint_level
        performance_req     = template.performance_required
        risk_level          = template.risk_level
        cooldown_hours      = template.cooldown_hours
        max_dur             = template.max_duration_minutes
    else:
        unit_type = default_t.get("unit", "min")
        title_raw = default_t.get("title", f"{tier.capitalize()} {category} challenge")
        desc_raw = default_t.get("desc", "")
        # Fall back to engine defaults
        _defaults        = DifficultyEngine.defaults_for_tier(tier)
        constraint_level = _defaults["constraint_level"]
        performance_req  = _defaults["performance_required"]
        risk_level       = _defaults["risk_level"]
        cooldown_hours   = _defaults["cooldown_hours"]
        max_dur          = DURATION_CAPS.get(tier)

    # ── Cap duration to hard limit ─────────────────────────────────────────────
    capped_value = DifficultyEngine.capped_duration(tier, value) if unit_type in ("minutes", "min", "hours") else value
    display_value, unit_label = _format_value(capped_value, unit_type)

    # Compute weighted difficulty score for this option
    dur_minutes = int(display_value * 60) if unit_label == "hours" else int(display_value)
    diff_score = DifficultyEngine.score(
        tier=tier,
        duration_minutes=dur_minutes,
        constraint_level=constraint_level,
        performance_required=performance_req,
        risk_level=risk_level,
    )

    def interp(s: str) -> str:
        return s.format(value=display_value, unit=unit_label, stat=primary_stat)

    return QuestOption(
        tier=tier,
        title=interp(title_raw),
        description=interp(desc_raw),
        xp_reward=xp,
        coin_reward=coin,
        value=display_value,
        unit=unit_label,
        primary_stat=primary_stat,
        stat_rewards=stat_rewards,
        penalty_xp_on_fail=penalty_xp,
        max_duration_minutes=max_dur,
        constraint_level=constraint_level,
        performance_required=performance_req,
        risk_level=risk_level,
        cooldown_hours=cooldown_hours,
        difficulty_score=round(diff_score.score, 4),
        verification_type="metrics" if tier in ("hard", "extreme") else "log",
    )


class AdaptiveQuestService:
    """Core generation + choice management service."""

    # ── Generate trio ──────────────────────────────────────────────────────────

    @classmethod
    def generate_trio(
        cls,
        user_id: int,
        category: str,
        db: Session,
    ) -> QuestTrioResponse:
        """Generate three difficulty options for the player.

        Raises ValueError if the category is unsupported.
        """
        if category not in DOMAIN_STAT_MAP:
            raise ValueError(
                f"Unknown domain {category!r}. "
                f"Supported: {list(DOMAIN_STAT_MAP)}"
            )

        stats = db.query(UserStats).filter(UserStats.user_id == user_id).first()
        if not stats:
            raise LookupError(f"No UserStats found for user_id={user_id}")

        phase = _phase_for_level(stats.level)
        tier_config = _load_tier_config(phase, db)
        diff_profile = _load_diff_profile(category, phase, db)
        ms = MindsetEngine.get_or_create(user_id, db)

        # ── Check force challenge ──────────────────────────────────────────────
        force_active = MindsetEngine.check_and_set_force_challenge(user_id, db)

        # ── Minimum choosable tier ─────────────────────────────────────────────
        min_tier = "easy"
        if tier_config:
            min_tier = tier_config.minimum_choosable_tier
        if force_active:
            min_tier = "hard"  # Override — no opt-out

        # ── Amplifiers ────────────────────────────────────────────────────────
        relevant_stat = _get_relevant_stat(category, stats)
        stat_amp = _stat_amplifier(relevant_stat)
        mind_amp = _mindset_amplifier(ms.score)
        rank_mult = _rank_xp_multiplier(stats.rank)

        # ── Base difficulty scalar ─────────────────────────────────────────────
        base_diff = (
            tier_config.base_difficulty if tier_config else 1.0
        ) * stat_amp

        # ── Per-tier multipliers ───────────────────────────────────────────────
        if diff_profile:
            e_mult  = diff_profile.easy_multiplier
            im_mult = diff_profile.intermediate_multiplier
            h_mult  = diff_profile.hard_multiplier
            e_xp_base  = diff_profile.easy_xp_base
            im_xp_base = diff_profile.intermediate_xp_base
            h_xp_base  = diff_profile.hard_xp_base
            primary_stat = diff_profile.primary_stat
        else:
            e_mult, im_mult, h_mult = 0.8, 1.0, 1.3
            e_xp_base, im_xp_base, h_xp_base = 80, 120, 200
            primary_stat = DOMAIN_STAT_MAP.get(category, "intelligence")

        xp_scale = tier_config.xp_scale if tier_config else 1.0

        # ── Computed difficulty values (duration-capped per tier) ──────────────
        # Anchor to tier duration caps, scale by phase base_difficulty & mindset.
        # entry:   ~45 min easy, ~108 min inter, ~162 min hard
        # mastery: all tiers hit their caps (60/120/180/240 min)
        e_value  = DifficultyEngine.capped_duration("easy",         DURATION_CAPS["easy"]         * e_mult  * base_diff * mind_amp)
        im_value = DifficultyEngine.capped_duration("intermediate", DURATION_CAPS["intermediate"]  * im_mult * base_diff * mind_amp)
        h_value  = DifficultyEngine.capped_duration("hard",         DURATION_CAPS["hard"]          * h_mult  * base_diff * mind_amp)

        # ── XP rewards ────────────────────────────────────────────────────────
        def calc_xp(base: int) -> int:
            return max(10, round(base * xp_scale * rank_mult * mind_amp))

        def calc_coins(xp_val: int) -> int:
            return max(1, round(xp_val * 0.05))

        def calc_penalty(xp_val: int) -> int:
            return round(xp_val * 0.6)

        e_xp  = calc_xp(e_xp_base)
        im_xp = calc_xp(im_xp_base)
        h_xp  = calc_xp(h_xp_base)

        # ── Stat rewards ──────────────────────────────────────────────────────
        def stat_rewards_for(tier_name: str) -> dict:
            mult = _STAT_REWARD_MAP[tier_name]
            primary_val = round(mult["primary"] * mind_amp, 2)
            # Pick a secondary stat
            all_stats = ["strength", "intelligence", "vitality", "mana", "charisma"]
            secondary = next(
                (s for s in all_stats if s != primary_stat), "vitality"
            )
            return {
                primary_stat: primary_val,
                secondary: round(mult["secondary"] * mind_amp, 2),
            }

        # ── Per-tier multipliers (extreme: anchored to 240 min cap) ──────────────
        ex_mult    = (diff_profile.hard_multiplier if diff_profile else 1.3) * 1.3
        ex_xp_base = (getattr(diff_profile, 'extreme_xp_base', None) if diff_profile else None) or 400
        ex_value   = DifficultyEngine.capped_duration("extreme", DURATION_CAPS["extreme"] * ex_mult * base_diff * mind_amp)

        ex_xp = calc_xp(ex_xp_base)

        # ── Load templates ─────────────────────────────────────────────────────
        t_easy    = _load_template(category, "easy",         phase, db)
        t_inter   = _load_template(category, "intermediate", phase, db)
        t_hard    = _load_template(category, "hard",         phase, db)
        t_extreme = _load_template(category, "extreme",      phase, db)

        # ── Build options ──────────────────────────────────────────────────────
        opt_easy = _build_option(
            "easy", category, t_easy, e_value,
            e_xp, calc_coins(e_xp), calc_penalty(e_xp),
            primary_stat, stat_rewards_for("easy"), diff_profile,
        )
        opt_inter = _build_option(
            "intermediate", category, t_inter, im_value,
            im_xp, calc_coins(im_xp), calc_penalty(im_xp),
            primary_stat, stat_rewards_for("intermediate"), diff_profile,
        )
        opt_hard = _build_option(
            "hard", category, t_hard, h_value,
            h_xp, calc_coins(h_xp), calc_penalty(h_xp),
            primary_stat, stat_rewards_for("hard"), diff_profile,
        )
        opt_extreme = _build_option(
            "extreme", category, t_extreme, ex_value,
            ex_xp, calc_coins(ex_xp), calc_penalty(ex_xp),
            primary_stat, stat_rewards_for("extreme"), diff_profile,
        )

        # ── Custom quests for this category ───────────────────────────────────
        dismissed_ids = custom_quest_service.get_dismissed_ids(db, user_id)
        custom_rows   = custom_quest_service.list_for_user(db, user_id, category=category)
        custom_options: list[QuestOption] = []
        for cq in custom_rows:
            xp_val   = cq.xp_override or custom_quest_service.auto_xp(cq.tier)
            coin_val = calc_coins(xp_val)
            pen_val  = calc_penalty(xp_val)
            custom_options.append(QuestOption(
                tier=cq.tier,
                title=cq.title,
                description=cq.description or "",
                xp_reward=xp_val,
                coin_reward=coin_val,
                value=float(cq.duration_value or 0),
                unit=cq.duration_unit or "min",
                primary_stat=primary_stat,
                stat_rewards=stat_rewards_for(cq.tier),
                penalty_xp_on_fail=pen_val,
                is_custom=True,
                custom_quest_id=cq.id,
            ))

        # ── Persist session ────────────────────────────────────────────────────
        session = AdaptiveQuestSession(
            user_id=user_id,
            category=category,
            phase=phase,
            easy_snapshot=opt_easy.model_dump(),
            intermediate_snapshot=opt_inter.model_dump(),
            hard_snapshot=opt_hard.model_dump(),
            extreme_snapshot=opt_extreme.model_dump(),
            mindset_score_at_generation=ms.score,
            force_challenge_was_active=force_active,
            expires_at=datetime.now(UTC) + timedelta(hours=SESSION_EXPIRY_HOURS),
        )
        db.add(session)
        db.flush()

        # ── Session message ────────────────────────────────────────────────────
        message: Optional[str] = None
        if force_active:
            message = (
                "Force challenge active. "
                f"Avoided hard path for {ms.consecutive_non_hard_days} days. "
                "Hard quest is mandatory. No opt-out."
            )
        elif ms.recovery_mode:
            remaining = ms.recovery_quests_required - ms.recovery_quests_completed
            message = (
                f"Rebuild Mode active. "
                f"Complete {remaining} more intermediate quest(s) to restore reputation."
            )

        # ── Allowed difficulties for this rank ──────────────────────────────
        allowed = get_allowed_difficulties(stats.level)

        return QuestTrioResponse(
            session_id=session.id,
            category=category,
            phase=phase,
            force_challenge_active=force_active,
            minimum_choosable_tier=min_tier,
            allowed_difficulties=allowed,
            mindset_tier=ms.tier_label,
            mindset_score=ms.score,
            easy=opt_easy,
            intermediate=opt_inter,
            hard=opt_hard,
            extreme=opt_extreme,
            custom_quests=custom_options,
            generated_at=session.generated_at,
            expires_at=session.expires_at,
            message=message,
        )

    # ── Choose a tier ──────────────────────────────────────────────────────────

    @classmethod
    def choose_tier(
        cls,
        session_id: int,
        chosen_tier: str,
        user_id: int,
        db: Session,
    ) -> ChooseTierResponse:
        """Player selects one of the three tiers.  Creates the Quest row."""

        session = db.query(AdaptiveQuestSession).filter(
            AdaptiveQuestSession.id == session_id,
            AdaptiveQuestSession.user_id == user_id,
        ).first()
        if not session:
            raise LookupError(f"Session {session_id} not found for user {user_id}.")
        if session.chosen_tier:
            raise ValueError("A tier has already been chosen for this session.")
        if session.expires_at and datetime.now(UTC) > session.expires_at:
            raise ValueError("This quest trio has expired. Generate a new one.")

        # ── Enforce rank-based difficulty lock ─────────────────────────────
        stats = db.query(UserStats).filter(UserStats.user_id == user_id).first()
        if stats:
            allowed = get_allowed_difficulties(stats.level)
            if chosen_tier not in allowed:
                raise ValueError(
                    f"Difficulty '{chosen_tier}' is locked at your rank. "
                    f"Allowed: {', '.join(allowed)}. Level up to unlock more."
                )

        # ── Enforce force-challenge ────────────────────────────────────────────
        if session.force_challenge_was_active and chosen_tier != "hard":
            raise ValueError(
                "Force-challenge is active. You must choose the Hard tier. "
                "No opt-out."
            )

        # ── Enforce extreme cooldown ───────────────────────────────────────────
        if chosen_tier == "extreme":
            from app.services.difficulty_engine import EXTREME_COOLDOWN_HOURS
            cooldown_cutoff = datetime.now(UTC) - timedelta(hours=EXTREME_COOLDOWN_HOURS)
            recent_extreme = db.query(AdaptiveQuestSession).filter(
                AdaptiveQuestSession.user_id == user_id,
                AdaptiveQuestSession.chosen_tier == "extreme",
                AdaptiveQuestSession.chosen_at >= cooldown_cutoff,
            ).first()
            if recent_extreme:
                hours_since = (
                    datetime.now(UTC) - recent_extreme.chosen_at
                ).total_seconds() / 3600
                hours_remaining = EXTREME_COOLDOWN_HOURS - hours_since
                raise ValueError(
                    f"Extreme quests require a {EXTREME_COOLDOWN_HOURS}h cooldown. "
                    f"{hours_remaining:.1f}h remaining. "
                    "Recovery between extreme efforts is mandatory."
                )

        # ── Enforce minimum choosable tier ─────────────────────────────────────
        tier_order = ["easy", "intermediate", "hard", "extreme"]
        stats = db.query(UserStats).filter(UserStats.user_id == user_id).first()
        phase = _phase_for_level(stats.level) if stats else "entry"
        tier_config = _load_tier_config(phase, db)
        min_tier = tier_config.minimum_choosable_tier if tier_config else "easy"
        if tier_order.index(chosen_tier) < tier_order.index(min_tier):
            raise ValueError(
                f"In the {phase} phase you must choose at least '{min_tier}'. "
                f"Soft options are no longer available."
            )

        # ── Pull snapshot ──────────────────────────────────────────────────────
        snapshot_map = {
            "easy":         session.easy_snapshot,
            "intermediate": session.intermediate_snapshot,
            "hard":         session.hard_snapshot,
            "extreme":      session.extreme_snapshot,
        }
        snap = snapshot_map.get(chosen_tier)
        if snap is None:
            raise ValueError(f"No snapshot found for tier '{chosen_tier}' in session {session_id}.")

        # ── Create Quest row ───────────────────────────────────────────────────
        # FLOW Rule: ALL quests must be verifiable.
        # Hard/Extreme → metrics verification, Easy/Intermediate → log verification
        verification = (
            VerificationType.METRICS if chosen_tier in ("hard", "extreme")
            else VerificationType.LOG
        )

        # ── Performance multiplier from tier ──────────────────────────────────
        TIER_MULTIPLIERS = {
            "easy": 1.0, "intermediate": 1.5, "hard": 2.0, "extreme": 3.0,
        }

        quest = Quest(
            user_id=user_id,
            title=snap["title"],
            description=snap["description"],
            quest_type=QuestType.DAILY,
            difficulty=TIER_TO_DIFFICULTY[chosen_tier],
            primary_stat=TIER_TO_STAT_TYPE.get(session.category, StatType.STRENGTH),
            base_xp_reward=snap["xp_reward"],
            coin_reward=snap["coin_reward"],
            stat_rewards=snap.get("stat_rewards"),
            penalty_xp=snap["penalty_xp_on_fail"],
            generates_penalty_quest=(chosen_tier in ("hard", "extreme")),
            auto_generated=True,
            status=QuestStatus.PENDING,
            domain=session.category,
            verification_type=verification,
            metrics_required=(chosen_tier in ("hard", "extreme")),
            cooldown_hours=TIER_RULES[chosen_tier]["cooldown_hours"],
            weekly_limit=TIER_RULES[chosen_tier].get("weekly_limit"),
            is_manual=False,
            performance_multiplier=TIER_MULTIPLIERS.get(chosen_tier, 1.0),
            max_duration_minutes=DURATION_CAPS.get(chosen_tier, 180),
        )
        db.add(quest)
        db.flush()

        # ── Update session ─────────────────────────────────────────────────────
        session.chosen_tier = chosen_tier
        session.quest_id_created = quest.id
        session.chosen_at = datetime.now(UTC)
        db.flush()

        # ── Record mindset choice ──────────────────────────────────────────────
        delta, new_score = MindsetEngine.record_choice(user_id, chosen_tier, db)

        # ── Message ────────────────────────────────────────────────────────────
        messages = {
            "easy":         "Quest accepted. Minimum standard. Don't get comfortable.",
            "intermediate": "Quest accepted. Push through.",
            "hard":         "Hard quest locked in. Prove it.",
            "extreme":      "EXTREME locked in. No excuses. No ceiling.",
        }

        return ChooseTierResponse(
            session_id=session_id,
            quest_id=quest.id,
            chosen_tier=chosen_tier,
            quest_title=quest.title,
            xp_reward=quest.base_xp_reward,
            mindset_delta=delta,
            new_mindset_score=new_score,
            message=messages[chosen_tier],
        )

    # ── Resolve session outcome ────────────────────────────────────────────────

    @classmethod
    def resolve_session(
        cls,
        session_id: int,
        user_id: int,
        outcome: str,
        db: Session,
    ) -> None:
        """Mark a session as completed/failed/expired.

        Called by the quest router after ProgressionService / PenaltyEngine.
        """
        session = db.query(AdaptiveQuestSession).filter(
            AdaptiveQuestSession.id == session_id,
            AdaptiveQuestSession.user_id == user_id,
        ).first()
        if session:
            session.outcome = outcome
            session.resolved_at = datetime.now(UTC)
            db.flush()

    # ── Session history ────────────────────────────────────────────────────────

    @classmethod
    def get_history(
        cls,
        user_id: int,
        db: Session,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[AdaptiveQuestSession], int]:
        q = db.query(AdaptiveQuestSession).filter(
            AdaptiveQuestSession.user_id == user_id
        )
        total = q.count()
        items = q.order_by(AdaptiveQuestSession.generated_at.desc()) \
                 .limit(limit).offset(offset).all()
        return items, total

    # ── Daily panel (all 5 categories at once) ─────────────────────────────────

    @classmethod
    def generate_daily_panel(
        cls,
        user_id: int,
        db: Session,
        force_refresh: bool = False,
    ) -> DailyQuestPanel:
        """Generate (or return cached) quest trios for all 6 categories.

        If sessions already exist for today (midnight boundary) the cached
        snapshots are re-used so the player sees the same options on refresh.
        Pass force_refresh=True to delete today's unchosen sessions and
        regenerate from current templates.
        """
        from datetime import date

        today_start = datetime.combine(date.today(), datetime.min.time()).replace(tzinfo=UTC)

        if force_refresh:
            # Delete today's unchosen sessions so they get regenerated below
            stale = db.query(AdaptiveQuestSession).filter(
                AdaptiveQuestSession.user_id == user_id,
                AdaptiveQuestSession.generated_at >= today_start,
                AdaptiveQuestSession.chosen_tier.is_(None),
            ).all()
            for s in stale:
                db.delete(s)
            db.flush()

        categories = ["mind", "body", "core", "control", "presence", "system"]
        panels: dict[str, QuestTrioResponse] = {}
        already_existed = True

        for cat in categories:
            # Check if a fresh session was already generated today
            existing = db.query(AdaptiveQuestSession).filter(
                AdaptiveQuestSession.user_id == user_id,
                AdaptiveQuestSession.category == cat,
                AdaptiveQuestSession.generated_at >= today_start,
            ).order_by(AdaptiveQuestSession.generated_at.desc()).first()

            if existing:
                ms = MindsetEngine.get_or_create(user_id, db)
                stats = db.query(UserStats).filter(UserStats.user_id == user_id).first()
                phase = _phase_for_level(stats.level) if stats else "entry"
                tier_config = _load_tier_config(phase, db)
                min_tier = tier_config.minimum_choosable_tier if tier_config else "easy"
                dismissed_ids = custom_quest_service.get_dismissed_ids(db, user_id)
                custom_rows   = custom_quest_service.list_for_user(db, user_id, category=cat)

                def _snap_to_option(snap: dict | None) -> QuestOption:
                    if snap is None:
                        return QuestOption(
                            tier="easy", title="Quest unavailable", description="",
                            xp_reward=0, coin_reward=0, value=0, unit="min",
                            primary_stat="strength", stat_rewards={},
                            penalty_xp_on_fail=0,
                        )
                    return QuestOption(**snap)

                custom_options = []
                for cq in custom_rows:
                    xp_val = cq.xp_override or custom_quest_service.auto_xp(cq.tier)
                    custom_options.append(QuestOption(
                        tier=cq.tier,
                        title=cq.title,
                        description=cq.description or "",
                        xp_reward=xp_val,
                        coin_reward=max(1, round(xp_val * 0.05)),
                        value=float(cq.duration_value or 0),
                        unit=cq.duration_unit or "min",
                        primary_stat=DOMAIN_STAT_MAP.get(cat, "intelligence"),
                        stat_rewards={},
                        penalty_xp_on_fail=round(xp_val * 0.6),
                        is_custom=True,
                        custom_quest_id=cq.id,
                    ))

                panels[cat] = QuestTrioResponse(
                    session_id=existing.id,
                    category=cat,
                    phase=existing.phase,
                    force_challenge_active=existing.force_challenge_was_active,
                    minimum_choosable_tier=min_tier,
                    allowed_difficulties=get_allowed_difficulties(stats.level) if stats else ["easy"],
                    mindset_tier=ms.tier_label,
                    mindset_score=ms.score,
                    easy=_snap_to_option(existing.easy_snapshot),
                    intermediate=_snap_to_option(existing.intermediate_snapshot),
                    hard=_snap_to_option(existing.hard_snapshot),
                    extreme=_snap_to_option(existing.extreme_snapshot),
                    custom_quests=custom_options,
                    generated_at=existing.generated_at,
                    expires_at=existing.expires_at,
                    message=None,
                )
            else:
                already_existed = False
                panels[cat] = cls.generate_trio(user_id, cat, db)

        db.commit()

        stats = db.query(UserStats).filter(UserStats.user_id == user_id).first()
        phase = _phase_for_level(stats.level) if stats else "entry"

        return DailyQuestPanel(
            date=str(date.today()),
            phase=phase,
            allowed_difficulties=get_allowed_difficulties(stats.level) if stats else ["easy"],
            panels=panels,
            already_existed=already_existed,
        )
