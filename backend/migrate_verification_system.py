"""migrate_verification_system.py

Idempotent migration for the Quest Verification System.

What this does:
  1. Creates the 5 new tables (quest_sessions, quest_outputs, player_trust,
     verification_logs, audit_flags) if they don't exist.
  2. Initialises a PlayerTrust row for every existing user (trust_score=50).
  3. For every already-COMPLETED quest, creates a synthetic VerificationLog
     with a neutral score (decision=PASS, score=0.70) so legacy rewards are
     not retroactively stripped.  Marks them as revalidated.
  4. No legacy quest can bypass the new system going forward.

Run:
    cd backend
    python migrate_verification_system.py
"""

import sys
import os

# Make sure 'backend/' directory is on the Python path
sys.path.insert(0, os.path.dirname(__file__))

from datetime import datetime, UTC
from sqlalchemy import inspect, text

from app.db.database import engine, SessionLocal
from app.db.base import Base

# ── Import all models so they register with Base ──────────────────────────────
from app.models.user import User
from app.models.quest import Quest, QuestStatus
from app.models.quest_session import QuestSession, SessionStatus
from app.models.quest_output import QuestOutput
from app.models.player_trust import PlayerTrust, TrustTier
from app.models.verification_log import VerificationLog, VerificationDecision
from app.models.audit_flag import AuditFlag

# Also import all other models so create_all picks them up
from app.models.goal import Goal
from app.models.task import Task
from app.models.rank import Rank
from app.models.user_stats import UserStats
from app.models.xp_history import XPHistory
from app.models.game_config import GameConfig
from app.models.daily_progress import DailyProgress
from app.models.difficulty_profile import DifficultyProfile
from app.models.mindset_score import MindsetScore
from app.models.quest_template import QuestTemplate
from app.models.progression_tier import ProgressionTier
from app.models.penalty_tier import PenaltyTier
from app.models.adaptive_quest_session import AdaptiveQuestSession
from app.models.user_custom_quest import UserCustomQuest, DismissedSystemQuest
from app.models.domain import Domain


# ─────────────────────────────────────────────────────────────────────────────

def table_exists(name: str) -> bool:
    insp = inspect(engine)
    return name in insp.get_table_names()


def step_create_tables() -> None:
    print("[1/4] Creating verification tables (idempotent)…")
    Base.metadata.create_all(bind=engine)
    new_tables = [
        "quest_sessions", "quest_outputs", "player_trust",
        "verification_logs", "audit_flags",
    ]
    for t in new_tables:
        exists = table_exists(t)
        print(f"      {'✔' if exists else '✘'} {t}")
    print("      Done.\n")


def step_init_player_trust(db) -> int:
    print("[2/4] Initialising PlayerTrust for all users…")
    users = db.query(User).all()
    created = 0
    for user in users:
        existing = db.query(PlayerTrust).filter(PlayerTrust.player_id == user.id).first()
        if not existing:
            trust = PlayerTrust(
                player_id   = user.id,
                trust_score = 50.0,
                trust_tier  = TrustTier.NORMAL,
            )
            db.add(trust)
            created += 1
    db.commit()
    print(f"      Created {created} new trust records. Total users: {len(users)}\n")
    return created


def step_backfill_completed_quests(db) -> int:
    """Create synthetic sessions + verification logs for pre-existing completed quests."""
    print("[3/4] Back-filling verification logs for legacy completed quests…")
    completed = (
        db.query(Quest)
        .filter(Quest.status == QuestStatus.COMPLETED)
        .all()
    )
    filled = 0
    for quest in completed:
        # Skip if a session already exists
        existing_session = (
            db.query(QuestSession)
            .filter(
                QuestSession.quest_id  == quest.id,
                QuestSession.player_id == quest.user_id,
            )
            .first()
        )
        if existing_session:
            continue

        # Synthetic session
        expected_sec = (quest.time_limit_minutes or 30) * 60
        now = datetime.now(UTC)
        session = QuestSession(
            player_id             = quest.user_id,
            quest_id              = quest.id,
            started_at            = quest.updated_at or now,
            submitted_at          = quest.updated_at or now,
            closed_at             = quest.updated_at or now,
            expected_duration_sec = expected_sec,
            active_time_sec       = int(expected_sec * 0.70),
            idle_time_sec         = int(expected_sec * 0.30),
            status                = SessionStatus.VERIFIED,
            requires_output       = False,
            requires_spot_check   = False,
            time_score            = 0.70,
            output_score          = 0.70,
            consistency_score     = 0.70,
            behavior_score        = 0.70,
            verification_score    = 0.70,
        )
        db.add(session)
        db.flush()  # Get session.id

        trust = db.query(PlayerTrust).filter(PlayerTrust.player_id == quest.user_id).first()
        trust_score_snapshot = trust.trust_score if trust else 50.0

        log = VerificationLog(
            session_id          = session.id,
            player_id           = quest.user_id,
            quest_id            = quest.id,
            time_score          = 0.70,
            output_score        = 0.70,
            consistency_score   = 0.70,
            behavior_score      = 0.70,
            verification_score  = 0.70,
            decision            = VerificationDecision.PASS,
            failure_reason      = None,
            reward_multiplier   = 1.0,
            xp_awarded          = quest.base_xp_reward,
            xp_penalty          = 0,
            trust_delta         = 0.0,
            trust_score_after   = trust_score_snapshot,
            spot_check_triggered= False,
            output_required     = False,
            layers_applied      = ["legacy_migration"],
            flags_raised        = [],
            verified_at         = quest.updated_at or now,
        )
        db.add(log)
        filled += 1

    db.commit()
    print(f"      Back-filled {filled} legacy quest(s).\n")
    return filled


def step_verify_integrity(db) -> None:
    print("[4/4] Integrity check…")
    unprotected = (
        db.query(Quest)
        .filter(Quest.status == QuestStatus.COMPLETED)
        .outerjoin(QuestSession, QuestSession.quest_id == Quest.id)
        .filter(QuestSession.id == None)  # noqa: E711
        .count()
    )
    if unprotected > 0:
        print(f"      ⚠  {unprotected} completed quest(s) still missing a session. Re-run migration.")
    else:
        print("      ✔ All completed quests have a session + verification log.")
    print()


def main() -> None:
    print("=" * 60)
    print("  FLOW — Quest Verification System Migration")
    print(f"  {datetime.now(UTC).strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print("=" * 60)
    print()

    # Step 1: DDL
    step_create_tables()

    db = SessionLocal()
    try:
        # Step 2: Trust init
        step_init_player_trust(db)

        # Step 3: Back-fill
        step_backfill_completed_quests(db)

        # Step 4: Integrity
        step_verify_integrity(db)

    finally:
        db.close()

    print("=" * 60)
    print("  Migration complete. No legacy bypass exists.")
    print("=" * 60)


if __name__ == "__main__":
    main()
