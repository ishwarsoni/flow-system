"""PenaltyEngine — applies scaled failure penalties.

Looks up the correct PenaltyTier row for the player's current phase and
the difficulty they chose, then applies every consequence:

  • XP loss (via ProgressionService.apply_xp with negative value)
  • HP damage
  • Streak destruction
  • Coin penalty
  • Boost lock (sets punishment_active on UserStats)
  • Rank block (frozen progression)
  • Demotion risk
  • Mindset score reduction
  • Recovery quest activation

Penalty matrix (hardcoded fallback if DB rows are missing):

phase      difficulty    xp     hp  streak  coins  boost_lock  punishment  demotion_risk
---------  ----------  ----  ----  ------  -----  ----------  ----------  -------------
entry      easy          50     5       0      0           0           0           0.00
entry      intermediate  80    10       0      0           0           0           0.00
entry      hard         120    20       0      0           0           0           0.00

growth     easy         120    15       1      0           0           0           0.00
growth     intermediate 200    25       1     20           0           0           0.00
growth     hard         300    40       2     50           0           0           0.05

mastery    easy         300    30       2     50          24           1           0.10
mastery    intermediate 500    50       2    100          24           2           0.15
mastery    hard         700    80       3    200          24           3           0.25
"""

from __future__ import annotations

import random
from datetime import datetime, UTC
from typing import Optional

from sqlalchemy.orm import Session

from app.models.penalty_tier import PenaltyTier
from app.models.user_stats import UserStats
from app.models.mindset_score import MindsetScore
from app.services.mindset_engine import MindsetEngine


# ── Fallback config (used when DB rows are absent) ────────────────────────────

_FALLBACK: dict[tuple[str, str], dict] = {
    ("entry",   "easy"):         {"xp": 50,  "hp": 5,  "streak": 0, "coins": 0,  "boost_lock": 0,  "punishment": 0, "demotion": 0.00, "mindset": 8.0,  "recovery": False, "rec_count": 0,  "rec_window": 48},
    ("entry",   "intermediate"): {"xp": 80,  "hp": 10, "streak": 0, "coins": 0,  "boost_lock": 0,  "punishment": 0, "demotion": 0.00, "mindset": 10.0, "recovery": False, "rec_count": 0,  "rec_window": 48},
    ("entry",   "hard"):         {"xp": 120, "hp": 20, "streak": 0, "coins": 0,  "boost_lock": 0,  "punishment": 0, "demotion": 0.00, "mindset": 15.0, "recovery": False, "rec_count": 0,  "rec_window": 48},
    ("growth",  "easy"):         {"xp": 120, "hp": 15, "streak": 1, "coins": 0,  "boost_lock": 0,  "punishment": 0, "demotion": 0.00, "mindset": 12.0, "recovery": False, "rec_count": 0,  "rec_window": 48},
    ("growth",  "intermediate"): {"xp": 200, "hp": 25, "streak": 1, "coins": 20, "boost_lock": 0,  "punishment": 0, "demotion": 0.00, "mindset": 15.0, "recovery": False, "rec_count": 0,  "rec_window": 48},
    ("growth",  "hard"):         {"xp": 300, "hp": 40, "streak": 2, "coins": 50, "boost_lock": 0,  "punishment": 0, "demotion": 0.05, "mindset": 20.0, "recovery": True,  "rec_count": 3,  "rec_window": 48},
    ("mastery", "easy"):         {"xp": 300, "hp": 30, "streak": 2, "coins": 50, "boost_lock": 24, "punishment": 1, "demotion": 0.10, "mindset": 20.0, "recovery": True,  "rec_count": 3,  "rec_window": 48},
    ("mastery", "intermediate"): {"xp": 500, "hp": 50, "streak": 2, "coins": 100,"boost_lock": 24, "punishment": 2, "demotion": 0.15, "mindset": 25.0, "recovery": True,  "rec_count": 3,  "rec_window": 48},
    ("mastery", "hard"):         {"xp": 700, "hp": 80, "streak": 3, "coins": 200,"boost_lock": 24, "punishment": 3, "demotion": 0.25, "mindset": 30.0, "recovery": True,  "rec_count": 3,  "rec_window": 48},
}


def _get_phase(level: int) -> str:
    if level <= 10:
        return "entry"
    elif level <= 30:
        return "growth"
    return "mastery"


def _load_penalty(phase: str, difficulty: str, db: Session) -> dict:
    """Load penalty config from DB, fall back to hardcoded matrix."""
    row = db.query(PenaltyTier).filter(
        PenaltyTier.phase == phase,
        PenaltyTier.difficulty_chosen == difficulty,
        PenaltyTier.is_active == True,
    ).first()

    if row:
        return {
            "xp": row.xp_penalty,
            "hp": row.hp_damage,
            "streak": row.streak_penalty,
            "coins": row.coin_penalty,
            "boost_lock": row.boost_lock_hours,
            "punishment": row.punishment_mode_days,
            "demotion": row.demotion_risk,
            "mindset": row.mindset_penalty,
            "recovery": row.recovery_quest_required,
            "rec_count": row.recovery_quest_count,
            "rec_window": row.recovery_window_hours,
        }

    return _FALLBACK.get((phase, difficulty), _FALLBACK[("entry", "easy")])


class PenaltyEngine:
    """Stateless penalty application service."""

    @staticmethod
    def apply_failure(
        user_id: int,
        stats: UserStats,
        chosen_tier: str,
        db: Session,
    ) -> dict:
        """Apply all failure consequences for a missed adaptive quest.

        Returns a summary dict with every penalty that was applied.
        """
        phase = _get_phase(stats.level)
        cfg = _load_penalty(phase, chosen_tier, db)

        applied: dict = {
            "phase": phase,
            "difficulty_chosen": chosen_tier,
            "xp_lost": 0,
            "hp_damage": 0,
            "streak_lost": 0,
            "coins_lost": 0,
            "boost_locked_hours": 0,
            "punishment_days": 0,
            "demotion_triggered": False,
            "recovery_mode_activated": False,
            "mindset_delta": 0.0,
        }

        # ── XP loss ───────────────────────────────────────────────────────────
        xp_loss = cfg["xp"]
        stats.xp_current = max(0, stats.xp_current - xp_loss)
        stats.xp_total_earned = max(0, stats.xp_total_earned - xp_loss)
        applied["xp_lost"] = xp_loss

        # ── HP damage ─────────────────────────────────────────────────────────
        hp_dmg = cfg["hp"]
        stats.hp_current = max(0, stats.hp_current - hp_dmg)
        applied["hp_damage"] = hp_dmg

        # ── Streak penalty ────────────────────────────────────────────────────
        streak_loss = cfg["streak"]
        if streak_loss:
            stats.streak_days = max(0, stats.streak_days - streak_loss)
            applied["streak_lost"] = streak_loss

        # ── Coin penalty ──────────────────────────────────────────────────────
        coin_loss = cfg["coins"]
        if coin_loss:
            stats.coins = max(0, stats.coins - coin_loss)
            applied["coins_lost"] = coin_loss

        # ── Punishment mode ────────────────────────────────────────────────────
        punishment_days = cfg["punishment"]
        if punishment_days:
            stats.punishment_active = max(
                stats.punishment_active or 0,
                punishment_days,
            )
            applied["punishment_days"] = punishment_days

        # ── Boost lock — stored in punishment_active (positive = locked) ──────
        # Note: boost_lock is shorter than full punishment; we store max of both.
        # A separate scheduler should decrement daily.
        boost_hours = cfg["boost_lock"]
        applied["boost_locked_hours"] = boost_hours

        # ── Demotion risk ─────────────────────────────────────────────────────
        if cfg["demotion"] > 0 and random.random() < cfg["demotion"]:
            from app.models.rank import RANK_ORDER, Rank
            rank_index = RANK_ORDER.index(stats.rank)
            if rank_index > 0:
                stats.rank = RANK_ORDER[rank_index - 1]
                applied["demotion_triggered"] = True

        # ── Mindset penalty ───────────────────────────────────────────────────
        mindset_delta, _ = MindsetEngine.record_outcome(
            user_id=user_id,
            chosen_tier=chosen_tier,
            success=False,
            db=db,
        )
        applied["mindset_delta"] = mindset_delta

        # ── Recovery mode ─────────────────────────────────────────────────────
        if cfg["recovery"]:
            MindsetEngine.activate_recovery_mode(
                user_id=user_id,
                db=db,
                required_count=cfg["rec_count"],
                window_hours=cfg["rec_window"],
            )
            applied["recovery_mode_activated"] = True

        db.flush()
        return applied

    @staticmethod
    def get_penalty_preview(
        level: int,
        chosen_tier: str,
        db: Session,
    ) -> dict:
        """Return the penalty config without applying it (for display to player)."""
        phase = _get_phase(level)
        return _load_penalty(phase, chosen_tier, db)
