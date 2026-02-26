"""migrate_adaptive_quests.py — One-time setup for the Adaptive Quest system.

Run from the backend directory:
    python migrate_adaptive_quests.py

What it does:
  1. Creates the 6 new tables (if they don't exist).
  2. Seeds default ProgressionTier rows (entry / growth / mastery).
  3. Seeds default DifficultyProfile rows (5 categories × 3 phases = 15 rows).
  4. Seeds default PenaltyTier rows (3 phases × 3 difficulties = 9 rows).
  5. Seeds default QuestTemplate rows (5 categories × 3 tiers × 3 phases = 45 rows).

All rows use INSERT-or-IGNORE semantics — safe to re-run.
"""

import sys
import os

# Ensure backend root is in path when running directly
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import inspect
from app.db.database import engine
from app.db.base import Base

# Import ALL models so Base.metadata knows about them
import app.models  # noqa: F401 — registers all models
# Quest model is not exported from app.models.__init__ — import explicitly
from app.models.quest import Quest  # noqa: F401
from app.models.difficulty_profile import DifficultyProfile
from app.models.progression_tier import ProgressionTier
from app.models.penalty_tier import PenaltyTier
from app.models.quest_template import QuestTemplate
from app.models.mindset_score import MindsetScore
from app.models.adaptive_quest_session import AdaptiveQuestSession

from sqlalchemy.orm import sessionmaker


def create_tables() -> None:
    """Create all new tables that don't exist yet."""
    print("Creating tables …")
    Base.metadata.create_all(bind=engine)
    print("  ✓ Tables ready.")


# ── ProgressionTier seed data ─────────────────────────────────────────────────

PROGRESSION_TIERS = [
    {
        "phase": "entry",
        "level_min": 1,
        "level_max": 10,
        "base_difficulty": 1.0,
        "easy_multiplier": 0.8,
        "intermediate_multiplier": 1.0,
        "hard_multiplier": 1.3,
        "xp_scale": 1.0,
        "force_challenge_trigger_days": 5,
        "minimum_choosable_tier": "easy",
        "description": (
            "Entry phase (Levels 1–10). "
            "Build foundational habits. "
            "Easy is still challenging for beginners. Hard is deliberately uncomfortable."
        ),
    },
    {
        "phase": "growth",
        "level_min": 11,
        "level_max": 30,
        "base_difficulty": 1.5,
        "easy_multiplier": 0.8,
        "intermediate_multiplier": 1.0,
        "hard_multiplier": 1.3,
        "xp_scale": 1.3,
        "force_challenge_trigger_days": 4,
        "minimum_choosable_tier": "easy",
        "description": (
            "Growth phase (Levels 11–30). "
            "Former easy tasks are now the baseline. Hard becomes genuinely demanding. "
            "Force-challenge triggers 1 day earlier."
        ),
    },
    {
        "phase": "mastery",
        "level_min": 31,
        "level_max": 9999,
        "base_difficulty": 2.5,
        "easy_multiplier": 0.8,
        "intermediate_multiplier": 1.0,
        "hard_multiplier": 1.3,
        "xp_scale": 1.7,
        "force_challenge_trigger_days": 3,
        "minimum_choosable_tier": "intermediate",
        "description": (
            "Mastery phase (Level 31+). "
            "Easy option is DISABLED. Minimum choice is Intermediate. "
            "Hard = elite standard. No soft options. "
            "Penalties are severe. Force-challenge triggers after 3 non-hard days."
        ),
    },
]

# ── DifficultyProfile seed data ───────────────────────────────────────────────

_CATEGORIES = {
    "study":  {"stat": "intelligence", "unit": "minutes",  "base": 30.0, "xp": (80, 120, 200)},
    "gym":    {"stat": "strength",     "unit": "reps",     "base": 4.0,  "xp": (90, 140, 220)},
    "sleep":  {"stat": "vitality",     "unit": "hours",    "base": 0.7,  "xp": (60, 100, 160)},
    "focus":  {"stat": "mana",         "unit": "minutes",  "base": 5.0,  "xp": (70, 110, 180)},
    "social": {"stat": "charisma",     "unit": "people",   "base": 0.2,  "xp": (60, 100, 160)},
}

_PHASE_BASE_MULTIPLIER = {
    "entry":   1.0,
    "growth":  2.0,
    "mastery": 4.0,
}

_PHASE_LEVELS = {
    "entry":   (1, 10),
    "growth":  (11, 30),
    "mastery": (31, 9999),
}

def build_difficulty_profiles():
    rows = []
    for phase, base_mult in _PHASE_BASE_MULTIPLIER.items():
        lmin, lmax = _PHASE_LEVELS[phase]
        for cat, cfg in _CATEGORIES.items():
            e_xp, im_xp, h_xp = cfg["xp"]
            rows.append({
                "category": cat,
                "phase": phase,
                "level_min": lmin,
                "level_max": lmax,
                "base_value": cfg["base"] * base_mult,
                "easy_multiplier": 0.8,
                "intermediate_multiplier": 1.0,
                "hard_multiplier": 1.3,
                "easy_xp_base": e_xp,
                "intermediate_xp_base": im_xp,
                "hard_xp_base": h_xp,
                "primary_stat": cfg["stat"],
                "description": f"{cat.capitalize()} / {phase} phase",
            })
    return rows


# ── PenaltyTier seed data ─────────────────────────────────────────────────────

PENALTY_TIERS = [
    # ── Entry phase ────────────────────────────────────────────────────────────
    {"phase": "entry",   "difficulty_chosen": "easy",         "xp_penalty": 50,  "hp_damage": 5,  "streak_penalty": 0, "coin_penalty": 0,   "rank_block_days": 0, "demotion_risk": 0.00, "boost_lock_hours": 0,  "punishment_mode_days": 0, "recovery_quest_required": False, "recovery_quest_count": 0, "recovery_window_hours": 48, "stat_penalty_fraction": 0.25, "mindset_penalty": 8.0,  "description": "Entry / Easy fail — small XP loss, lesson learned."},
    {"phase": "entry",   "difficulty_chosen": "intermediate", "xp_penalty": 80,  "hp_damage": 10, "streak_penalty": 0, "coin_penalty": 0,   "rank_block_days": 0, "demotion_risk": 0.00, "boost_lock_hours": 0,  "punishment_mode_days": 0, "recovery_quest_required": False, "recovery_quest_count": 0, "recovery_window_hours": 48, "stat_penalty_fraction": 0.25, "mindset_penalty": 10.0, "description": "Entry / Intermediate fail — moderate XP loss."},
    {"phase": "entry",   "difficulty_chosen": "hard",         "xp_penalty": 120, "hp_damage": 20, "streak_penalty": 0, "coin_penalty": 0,   "rank_block_days": 0, "demotion_risk": 0.00, "boost_lock_hours": 0,  "punishment_mode_days": 0, "recovery_quest_required": False, "recovery_quest_count": 0, "recovery_window_hours": 48, "stat_penalty_fraction": 0.50, "mindset_penalty": 15.0, "description": "Entry / Hard fail — larger XP loss. Mindset hit."},
    # ── Growth phase ───────────────────────────────────────────────────────────
    {"phase": "growth",  "difficulty_chosen": "easy",         "xp_penalty": 120, "hp_damage": 15, "streak_penalty": 1, "coin_penalty": 0,   "rank_block_days": 0, "demotion_risk": 0.00, "boost_lock_hours": 0,  "punishment_mode_days": 0, "recovery_quest_required": False, "recovery_quest_count": 0, "recovery_window_hours": 48, "stat_penalty_fraction": 0.25, "mindset_penalty": 12.0, "description": "Growth / Easy fail — streak + XP loss. No excuses."},
    {"phase": "growth",  "difficulty_chosen": "intermediate", "xp_penalty": 200, "hp_damage": 25, "streak_penalty": 1, "coin_penalty": 20,  "rank_block_days": 0, "demotion_risk": 0.00, "boost_lock_hours": 0,  "punishment_mode_days": 0, "recovery_quest_required": False, "recovery_quest_count": 0, "recovery_window_hours": 48, "stat_penalty_fraction": 0.40, "mindset_penalty": 15.0, "description": "Growth / Intermediate fail — XP + streak + coin loss."},
    {"phase": "growth",  "difficulty_chosen": "hard",         "xp_penalty": 300, "hp_damage": 40, "streak_penalty": 2, "coin_penalty": 50,  "rank_block_days": 0, "demotion_risk": 0.05, "boost_lock_hours": 0,  "punishment_mode_days": 0, "recovery_quest_required": True,  "recovery_quest_count": 3, "recovery_window_hours": 48, "stat_penalty_fraction": 0.50, "mindset_penalty": 20.0, "description": "Growth / Hard fail — severe. Recovery quest required. 5% demotion risk."},
    # ── Mastery phase ──────────────────────────────────────────────────────────
    {"phase": "mastery", "difficulty_chosen": "easy",         "xp_penalty": 300, "hp_damage": 30, "streak_penalty": 2, "coin_penalty": 50,  "rank_block_days": 0, "demotion_risk": 0.10, "boost_lock_hours": 24, "punishment_mode_days": 1, "recovery_quest_required": True,  "recovery_quest_count": 3, "recovery_window_hours": 48, "stat_penalty_fraction": 0.50, "mindset_penalty": 20.0, "description": "Mastery / Easy fail — punishment mode + boost lock + demotion risk. Should not happen."},
    {"phase": "mastery", "difficulty_chosen": "intermediate", "xp_penalty": 500, "hp_damage": 50, "streak_penalty": 2, "coin_penalty": 100, "rank_block_days": 0, "demotion_risk": 0.15, "boost_lock_hours": 24, "punishment_mode_days": 2, "recovery_quest_required": True,  "recovery_quest_count": 3, "recovery_window_hours": 48, "stat_penalty_fraction": 0.60, "mindset_penalty": 25.0, "description": "Mastery / Intermediate fail — severe. Punishment mode 2 days."},
    {"phase": "mastery", "difficulty_chosen": "hard",         "xp_penalty": 700, "hp_damage": 80, "streak_penalty": 3, "coin_penalty": 200, "rank_block_days": 0, "demotion_risk": 0.25, "boost_lock_hours": 24, "punishment_mode_days": 3, "recovery_quest_required": True,  "recovery_quest_count": 3, "recovery_window_hours": 48, "stat_penalty_fraction": 0.75, "mindset_penalty": 30.0, "description": "Mastery / Hard fail — −700 XP, 3-day punishment, 24h boost lock, 25% demotion risk, recovery required."},
]

# ── QuestTemplate seed data ───────────────────────────────────────────────────

QUEST_TEMPLATES = [
    # ── STUDY ──────────────────────────────────────────────────────────────────
    # Entry
    {"category": "study", "tier": "easy",         "phase": "entry",   "title_template": "Study for {value} {unit}",                          "description_template": "Focused session. Phone away. One subject only.",                                               "unit_type": "minutes", "base_xp": 80,  "stat_bonus": {"intelligence": 1.0}},
    {"category": "study", "tier": "intermediate", "phase": "entry",   "title_template": "Study for {value} {unit}",                          "description_template": "Active recall required. Take notes. No passive reading.",                                       "unit_type": "minutes", "base_xp": 120, "stat_bonus": {"intelligence": 2.0}},
    {"category": "study", "tier": "hard",         "phase": "entry",   "title_template": "Study for {value} {unit} + full notes",             "description_template": "Deep work. No breaks. Summarise everything learned at the end.",                               "unit_type": "minutes", "base_xp": 200, "stat_bonus": {"intelligence": 3.5}},
    # Growth
    {"category": "study", "tier": "easy",         "phase": "growth",  "title_template": "Study for {value} {unit} — Pomodoro block",         "description_template": "Structured study session. 25/5 cycles. Paper notes only.",                                    "unit_type": "minutes", "base_xp": 80,  "stat_bonus": {"intelligence": 1.0}},
    {"category": "study", "tier": "intermediate", "phase": "growth",  "title_template": "Study for {value} {unit} + active recall test",     "description_template": "No passive reviewing. Test yourself after each block.",                                        "unit_type": "minutes", "base_xp": 120, "stat_bonus": {"intelligence": 2.0}},
    {"category": "study", "tier": "hard",         "phase": "growth",  "title_template": "Study for {value} {unit} — no phone, full notes",   "description_template": "Deep work protocol. Phone in another room. Complete notes. Teach-back one concept at the end.", "unit_type": "minutes", "base_xp": 200, "stat_bonus": {"intelligence": 3.5}},
    # Mastery
    {"category": "study", "tier": "easy",         "phase": "mastery", "title_template": "Disciplined study — {value} {unit}",                "description_template": "Minimum standard. Full environment control. Notes mandatory.",                                   "unit_type": "minutes", "base_xp": 80,  "stat_bonus": {"intelligence": 1.0}},
    {"category": "study", "tier": "intermediate", "phase": "mastery", "title_template": "Study sprint — {value} {unit} + output document",   "description_template": "Produce a written output (summary, mind-map, flashcards). No output = incomplete.",            "unit_type": "minutes", "base_xp": 120, "stat_bonus": {"intelligence": 2.0}},
    {"category": "study", "tier": "hard",         "phase": "mastery", "title_template": "Elite study block — {value} {unit} + teach-back",   "description_template": "Absolute focus. End with a 5-minute verbal teach-back. Prove you absorbed it.",                 "unit_type": "minutes", "base_xp": 200, "stat_bonus": {"intelligence": 3.5}},

    # ── GYM ────────────────────────────────────────────────────────────────────
    {"category": "gym", "tier": "easy",         "phase": "entry",   "title_template": "{value} pushups + 10 min walk",                      "description_template": "Minimum physical output. No rest days for the weak.",                  "unit_type": "reps", "base_xp": 90,  "stat_bonus": {"strength": 1.0}},
    {"category": "gym", "tier": "intermediate", "phase": "entry",   "title_template": "{value} pushups + 20 min workout",                   "description_template": "Push beyond the minimum. Structured workout protocol.",                 "unit_type": "reps", "base_xp": 140, "stat_bonus": {"strength": 2.0}},
    {"category": "gym", "tier": "hard",         "phase": "entry",   "title_template": "Full {value}-min workout — no shortcuts",            "description_template": "Complete the session. No skipping sets. No early exit.",               "unit_type": "minutes", "base_xp": 220, "stat_bonus": {"strength": 3.5}},
    {"category": "gym", "tier": "easy",         "phase": "growth",  "title_template": "{value} reps compound movement + cardio",            "description_template": "Compound lifts only. No isolation fluff. Cardio to finish.",          "unit_type": "reps", "base_xp": 90,  "stat_bonus": {"strength": 1.0}},
    {"category": "gym", "tier": "intermediate", "phase": "growth",  "title_template": "{value}-min structured training session",            "description_template": "Progressive overload applied. Track your numbers.",                    "unit_type": "minutes", "base_xp": 140, "stat_bonus": {"strength": 2.0}},
    {"category": "gym", "tier": "hard",         "phase": "growth",  "title_template": "High-intensity {value}-min session + cold finish",   "description_template": "Peak effort every set. Finish with 2 min cold shower.",               "unit_type": "minutes", "base_xp": 220, "stat_bonus": {"strength": 3.5}},
    {"category": "gym", "tier": "easy",         "phase": "mastery", "title_template": "Base training — {value}-min full-body",              "description_template": "Disciplined baseline. Non-negotiable.",                                "unit_type": "minutes", "base_xp": 90,  "stat_bonus": {"strength": 1.0}},
    {"category": "gym", "tier": "intermediate", "phase": "mastery", "title_template": "{value}-min performance session + logging",          "description_template": "Every set logged. No ego lifting. Form over weight.",                  "unit_type": "minutes", "base_xp": 140, "stat_bonus": {"strength": 2.0}},
    {"category": "gym", "tier": "hard",         "phase": "mastery", "title_template": "Elite session — {value} min + PR attempt",           "description_template": "Attempt a personal record on one lift. Track. Reflect. Recover.",    "unit_type": "minutes", "base_xp": 220, "stat_bonus": {"strength": 3.5}},

    # ── SLEEP ──────────────────────────────────────────────────────────────────
    {"category": "sleep", "tier": "easy",         "phase": "entry",   "title_template": "Sleep {value} {unit}",                              "description_template": "Minimum recovery standard. Phone off. Consistent bedtime.",                         "unit_type": "hours", "base_xp": 60,  "stat_bonus": {"vitality": 1.0}},
    {"category": "sleep", "tier": "intermediate", "phase": "entry",   "title_template": "Sleep {value} {unit} + no screens 30 min before",   "description_template": "Quality over quantity. Wind-down protocol mandatory.",                             "unit_type": "hours", "base_xp": 100, "stat_bonus": {"vitality": 2.0}},
    {"category": "sleep", "tier": "hard",         "phase": "entry",   "title_template": "Sleep {value} {unit} + full sleep protocol",        "description_template": "No screens 1 hour before. Dark room. Same sleep/wake time. Journal before sleep.",   "unit_type": "hours", "base_xp": 160, "stat_bonus": {"vitality": 3.0}},
    {"category": "sleep", "tier": "easy",         "phase": "growth",  "title_template": "Sleep {value} {unit} — consistent schedule",        "description_template": "Same sleep time every night. Maximum ±15 min variance.",                           "unit_type": "hours", "base_xp": 60,  "stat_bonus": {"vitality": 1.0}},
    {"category": "sleep", "tier": "intermediate", "phase": "growth",  "title_template": "Sleep {value} {unit} + recovery protocol",          "description_template": "No alcohol. Sleep hygiene checklist complete.",                                    "unit_type": "hours", "base_xp": 100, "stat_bonus": {"vitality": 2.0}},
    {"category": "sleep", "tier": "hard",         "phase": "growth",  "title_template": "Elite sleep — {value} {unit} + HRV track",          "description_template": "Full protocol: no screens, cold room, same schedule. Track HRV on waking.",        "unit_type": "hours", "base_xp": 160, "stat_bonus": {"vitality": 3.0}},
    {"category": "sleep", "tier": "easy",         "phase": "mastery", "title_template": "Disciplined rest — {value} {unit} minimum",         "description_template": "Non-negotiable baseline.",                                                         "unit_type": "hours", "base_xp": 60,  "stat_bonus": {"vitality": 1.0}},
    {"category": "sleep", "tier": "intermediate", "phase": "mastery", "title_template": "Optimised sleep — {value} {unit} + tracking",       "description_template": "Track sleep quality. Adjust based on data. No excuses.",                           "unit_type": "hours", "base_xp": 100, "stat_bonus": {"vitality": 2.0}},
    {"category": "sleep", "tier": "hard",         "phase": "mastery", "title_template": "Mastery rest — {value} {unit} + full protocol",     "description_template": "Peak recovery. Every variable controlled.",                                        "unit_type": "hours", "base_xp": 160, "stat_bonus": {"vitality": 3.0}},

    # ── FOCUS ──────────────────────────────────────────────────────────────────
    {"category": "focus", "tier": "easy",         "phase": "entry",   "title_template": "No phone for {value} {unit}",                       "description_template": "Put the phone in a drawer. Work on one task.",                                              "unit_type": "minutes", "base_xp": 70,  "stat_bonus": {"mana": 1.0}},
    {"category": "focus", "tier": "intermediate", "phase": "entry",   "title_template": "Single-task focus — {value} {unit}",                "description_template": "One task. One tab. Phone off. No interruptions allowed.",                                    "unit_type": "minutes", "base_xp": 110, "stat_bonus": {"mana": 2.0}},
    {"category": "focus", "tier": "hard",         "phase": "entry",   "title_template": "Deep work — {value} {unit}, zero distraction",      "description_template": "No phone. No social media. No background music. Pure deep work.",                           "unit_type": "minutes", "base_xp": 180, "stat_bonus": {"mana": 3.5}},
    {"category": "focus", "tier": "easy",         "phase": "growth",  "title_template": "Focus block — {value} {unit}",                      "description_template": "Pre-work ritual. Clear desk. One task defined before starting.",                            "unit_type": "minutes", "base_xp": 70,  "stat_bonus": {"mana": 1.0}},
    {"category": "focus", "tier": "intermediate", "phase": "growth",  "title_template": "Flow session — {value} {unit} + output",            "description_template": "Produce a tangible output by the end of the session. No output = failed.",                   "unit_type": "minutes", "base_xp": 110, "stat_bonus": {"mana": 2.0}},
    {"category": "focus", "tier": "hard",         "phase": "growth",  "title_template": "Extended deep work — {value} {unit}",               "description_template": "Impossible to do casually. Full shutdown of all communications. Timed. Logged.",            "unit_type": "minutes", "base_xp": 180, "stat_bonus": {"mana": 3.5}},
    {"category": "focus", "tier": "easy",         "phase": "mastery", "title_template": "Disciplined focus — {value} {unit}",                "description_template": "Baseline standard. Already second nature.",                                                 "unit_type": "minutes", "base_xp": 70,  "stat_bonus": {"mana": 1.0}},
    {"category": "focus", "tier": "intermediate", "phase": "mastery", "title_template": "High-output session — {value} {unit} + review",     "description_template": "5-min end-of-session review. What was accomplished? What slowed you down?",                  "unit_type": "minutes", "base_xp": 110, "stat_bonus": {"mana": 2.0}},
    {"category": "focus", "tier": "hard",         "phase": "mastery", "title_template": "Elite focus — {value} {unit} in flow state",        "description_template": "Engineered flow state. Pre-defined output target. No stopping until target is met.",          "unit_type": "minutes", "base_xp": 180, "stat_bonus": {"mana": 3.5}},

    # ── SOCIAL ─────────────────────────────────────────────────────────────────
    {"category": "social", "tier": "easy",         "phase": "entry",   "title_template": "Reach out to {value} person(s)",                    "description_template": "Start a conversation. Any medium. Real interaction only.",                              "unit_type": "people", "base_xp": 60,  "stat_bonus": {"charisma": 1.0}},
    {"category": "social", "tier": "intermediate", "phase": "entry",   "title_template": "Meaningful conversation with {value} person(s)",    "description_template": "No small talk. Go deep. Ask a question you actually want the answer to.",               "unit_type": "people", "base_xp": 100, "stat_bonus": {"charisma": 2.0}},
    {"category": "social", "tier": "hard",         "phase": "entry",   "title_template": "Introduce yourself to {value} new person(s)",       "description_template": "Cold approach. In person preferred. No pre-existing relationship.",                      "unit_type": "people", "base_xp": 160, "stat_bonus": {"charisma": 3.0}},
    {"category": "social", "tier": "easy",         "phase": "growth",  "title_template": "Follow up with {value} contact(s)",                 "description_template": "Maintain existing connections. Most people neglect this.",                              "unit_type": "people", "base_xp": 60,  "stat_bonus": {"charisma": 1.0}},
    {"category": "social", "tier": "intermediate", "phase": "growth",  "title_template": "Network actively — {value} new connection(s)",      "description_template": "Professional or personal. Genuine intent only. No collecting contacts.",                "unit_type": "people", "base_xp": 100, "stat_bonus": {"charisma": 2.0}},
    {"category": "social", "tier": "hard",         "phase": "growth",  "title_template": "Build relationship — {value} person(s) + follow-up","description_template": "Connect, converse, and send a follow-up within 24 h. Prove the relationship matters.",   "unit_type": "people", "base_xp": 160, "stat_bonus": {"charisma": 3.0}},
    {"category": "social", "tier": "easy",         "phase": "mastery", "title_template": "Social baseline — {value} meaningful interaction(s)","description_template": "Non-negotiable. Isolation is not discipline.",                                          "unit_type": "people", "base_xp": 60,  "stat_bonus": {"charisma": 1.0}},
    {"category": "social", "tier": "intermediate", "phase": "mastery", "title_template": "Leadership interaction — {value} person(s)",        "description_template": "Influence, teach, or help someone meaningfully. Contribution over consumption.",          "unit_type": "people", "base_xp": 100, "stat_bonus": {"charisma": 2.0}},
    {"category": "social", "tier": "hard",         "phase": "mastery", "title_template": "Elite networking — {value} high-value connection(s)","description_template": "Reach out to someone above your current level. You are the average of your network.",    "unit_type": "people", "base_xp": 160, "stat_bonus": {"charisma": 3.0}},
]


# ── Seed functions ────────────────────────────────────────────────────────────

def seed_progression_tiers(session) -> int:
    count = 0
    for row in PROGRESSION_TIERS:
        exists = session.query(ProgressionTier).filter_by(phase=row["phase"]).first()
        if not exists:
            session.add(ProgressionTier(**row))
            count += 1
    session.flush()
    return count


def seed_difficulty_profiles(session) -> int:
    count = 0
    for row in build_difficulty_profiles():
        exists = session.query(DifficultyProfile).filter_by(
            category=row["category"], phase=row["phase"]
        ).first()
        if not exists:
            session.add(DifficultyProfile(**row))
            count += 1
    session.flush()
    return count


def seed_penalty_tiers(session) -> int:
    count = 0
    for row in PENALTY_TIERS:
        exists = session.query(PenaltyTier).filter_by(
            phase=row["phase"], difficulty_chosen=row["difficulty_chosen"]
        ).first()
        if not exists:
            session.add(PenaltyTier(**row))
            count += 1
    session.flush()
    return count


def seed_quest_templates(session) -> int:
    count = 0
    for row in QUEST_TEMPLATES:
        exists = session.query(QuestTemplate).filter_by(
            category=row["category"],
            tier=row["tier"],
            phase=row["phase"],
        ).first()
        if not exists:
            session.add(QuestTemplate(**row))
            count += 1
    session.flush()
    return count


def main() -> None:
    print("=" * 60)
    print("  FLOW — Adaptive Quest & Mindset Evolution System")
    print("  Database Migration & Seed Script")
    print("=" * 60)

    create_tables()

    Session = sessionmaker(bind=engine)
    with Session() as session:
        pt_count = seed_progression_tiers(session)
        print(f"  ✓ ProgressionTier rows added:   {pt_count}")

        dp_count = seed_difficulty_profiles(session)
        print(f"  ✓ DifficultyProfile rows added: {dp_count}")

        pen_count = seed_penalty_tiers(session)
        print(f"  ✓ PenaltyTier rows added:       {pen_count}")

        tpl_count = seed_quest_templates(session)
        print(f"  ✓ QuestTemplate rows added:     {tpl_count}")

        session.commit()

    print()
    print("  Migration complete.")
    print("  Total new rows:", pt_count + dp_count + pen_count + tpl_count)
    print("=" * 60)


if __name__ == "__main__":
    main()
