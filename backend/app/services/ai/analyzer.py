"""AI Coach Analyzer — collects player metrics and builds structured prompts.

This is the data-collection step. It queries FLOW's models to build a
snapshot of the player's current state, then constructs a prompt that
asks Groq to return a JSON coaching directive.

No AI call happens here — that's client.py's job.
This module ONLY prepares the inputs.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, UTC, date
from typing import Optional

from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models.user_stats import UserStats
from app.models.player_trust import PlayerTrust
from app.models.mindset_score import MindsetScore
from app.models.quest import Quest, QuestStatus
from app.models.daily_progress import DailyProgress
from app.services.ai.client import GroqClient
from app.services.ai.validator import AICoachValidator, CoachOutput

logger = logging.getLogger(__name__)

# ── System Prompt ──────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are the FLOW System Coach — a strict, analytical AI embedded in a gamified productivity system.
You analyze player data and return ONLY a JSON directive. No conversation. No encouragement. No filler.

FLOW domains: mind, body, core, control, presence, system.
Difficulty tiers: easy, intermediate, hard, extreme.
Modes: normal (default), pressure (high trust + stagnation), punishment (repeated failures), recovery (low HP/trust).

Rules:
- xp_modifier must be between -0.2 and 0.2 (e.g. 0.1 = +10% XP bonus, -0.15 = -15% XP penalty).
- max 3 quests. Each quest needs: title, description, domain, difficulty, estimated_minutes (5-240).
- priority_domains: max 3 domains the player should focus on.
- message: 1-2 sentences. Cold, direct, analytical. No emojis. No motivation speeches.
- If player data looks healthy and balanced, just set mode=normal with no quests and xp_modifier=0.

Return ONLY valid JSON with this exact schema:
{
  "mode": "normal|pressure|punishment|recovery",
  "priority_domains": ["domain1", "domain2"],
  "new_quests": [
    {
      "title": "Quest title (5+ chars, specific, measurable)",
      "description": "What the player must do and how to prove it",
      "domain": "mind|body|core|control|presence|system",
      "difficulty": "easy|intermediate|hard|extreme",
      "estimated_minutes": 30
    }
  ],
  "xp_modifier": 0.0,
  "message": "[ SYSTEM ] Your analysis message here."
}"""


# ── Player Snapshot Builder ────────────────────────────────────────────────────

class PlayerSnapshot:
    """Collects all relevant player data for AI analysis."""

    @staticmethod
    def collect(db: Session, user_id: int) -> Optional[dict]:
        """Build a data snapshot dict for the AI prompt.

        Returns None if the player has no stats (new user, skip coaching).
        """
        stats = db.query(UserStats).filter(UserStats.user_id == user_id).first()
        if not stats:
            logger.info(f"AI Coach: no stats for user {user_id} — skipping")
            return None

        trust = db.query(PlayerTrust).filter(PlayerTrust.player_id == user_id).first()
        mindset = db.query(MindsetScore).filter(MindsetScore.user_id == user_id).first()

        # Quest history — last 7 days
        week_ago = datetime.now(UTC) - timedelta(days=7)
        recent_quests = (
            db.query(Quest)
            .filter(
                Quest.user_id == user_id,
                Quest.created_at >= week_ago,
            )
            .all()
        )

        # Aggregate quest stats by domain
        domain_stats = {}
        total_completed = 0
        total_failed = 0
        for q in recent_quests:
            domain = q.domain or "unknown"
            if domain not in domain_stats:
                domain_stats[domain] = {"completed": 0, "failed": 0, "total": 0}
            domain_stats[domain]["total"] += 1
            if q.status == QuestStatus.COMPLETED:
                domain_stats[domain]["completed"] += 1
                total_completed += 1
            elif q.status in (QuestStatus.FAILED, QuestStatus.EXPIRED, QuestStatus.ABANDONED):
                domain_stats[domain]["failed"] += 1
                total_failed += 1

        # Today's progress
        today = date.today()
        daily = (
            db.query(DailyProgress)
            .filter(
                DailyProgress.user_id == user_id,
                DailyProgress.date == today,
            )
            .first()
        )

        # Difficulty distribution (last 7 days)
        difficulty_dist = {}
        for q in recent_quests:
            diff = q.difficulty.value if q.difficulty else "unknown"
            difficulty_dist[diff] = difficulty_dist.get(diff, 0) + 1

        snapshot = {
            "player": {
                "level": stats.level,
                "rank": stats.rank.value if stats.rank else "E",
                "xp_current": stats.xp_current,
                "xp_total_earned": stats.xp_total_earned,
                "hp": f"{stats.hp_current}/{stats.hp_max}",
                "mp": f"{stats.mp_current}/{stats.mp_max}",
                "fatigue": round(stats.fatigue, 1),
                "streak_days": stats.streak_days,
                "longest_streak": stats.longest_streak,
                "punishment_active": stats.punishment_active,
            },
            "stats": {
                "strength": round(stats.strength, 1),
                "intelligence": round(stats.intelligence, 1),
                "vitality": round(stats.vitality, 1),
                "charisma": round(stats.charisma, 1),
                "mana": round(stats.mana, 1),
            },
            "trust": {
                "score": round(trust.trust_score, 1) if trust else 50.0,
                "tier": trust.trust_tier.value if trust else "normal",
                "total_sessions": trust.total_sessions if trust else 0,
                "verified_sessions": trust.verified_sessions if trust else 0,
                "hard_fail_count": trust.hard_fail_count if trust else 0,
                "consecutive_fails": trust.consecutive_fails if trust else 0,
            },
            "mindset": {
                "score": round(mindset.score, 1) if mindset else 100.0,
                "tier": mindset.tier_label if mindset else "dormant",
                "hard_completions": mindset.hard_completions if mindset else 0,
                "hard_failures": mindset.hard_failures if mindset else 0,
                "recovery_mode": mindset.recovery_mode if mindset else False,
                "force_challenge": mindset.force_challenge_active if mindset else False,
                "consecutive_non_hard_days": mindset.consecutive_non_hard_days if mindset else 0,
            },
            "week_summary": {
                "total_completed": total_completed,
                "total_failed": total_failed,
                "domain_breakdown": domain_stats,
                "difficulty_distribution": difficulty_dist,
            },
            "today": {
                "xp_earned": daily.xp_earned_today if daily else 0,
                "tasks_completed": daily.tasks_completed_today if daily else 0,
                "tasks_failed": daily.tasks_failed_today if daily else 0,
            },
        }

        return snapshot


# ── Prompt Builder ─────────────────────────────────────────────────────────────

def build_user_message(snapshot: dict) -> str:
    """Convert a player snapshot dict into the user message for Groq."""
    return (
        "Analyze this FLOW player's data and return a coaching directive as JSON.\n\n"
        f"```json\n{json.dumps(snapshot, indent=2)}\n```"
    )


# ── Main Analysis Function ─────────────────────────────────────────────────────

def analyze_player(db: Session, user_id: int, api_key: str) -> CoachOutput:
    """Full pipeline: collect → prompt → call Groq → validate → return.

    This is the single entry-point. Returns a validated CoachOutput
    (possibly the default fallback if anything fails).
    """
    # Step 1: Collect data
    snapshot = PlayerSnapshot.collect(db, user_id)
    if snapshot is None:
        logger.info(f"AI Coach: no data for user {user_id} — returning default")
        return AICoachValidator.validate(None)

    # Step 2: Build prompt
    user_message = build_user_message(snapshot)

    # Step 3: Call Groq
    raw_response = GroqClient.chat_json(
        system_prompt=SYSTEM_PROMPT,
        user_message=user_message,
        api_key=api_key,
    )

    if raw_response is None:
        logger.warning(f"AI Coach: Groq returned None for user {user_id} — fallback")
        return AICoachValidator.validate(None)

    # Step 4: Validate
    output = AICoachValidator.validate(raw_response)
    logger.info(
        f"AI Coach: user {user_id} — mode={output.mode}, "
        f"quests={len(output.new_quests)}, xp_mod={output.xp_modifier}, "
        f"valid={output.raw_valid}"
    )

    return output
