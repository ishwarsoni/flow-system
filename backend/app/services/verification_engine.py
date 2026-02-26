"""VerificationEngine — the central scoring brain of FLOW's anti-cheat layer.

Responsibilities:
  1. Open / close QuestSessions
  2. Evaluate all verification layers and compute a composite score
  3. Apply trust deltas based on outcome
  4. Grant/deny rewards via ProgressionService
  5. Raise AuditFlags for suspicious signals
  6. Ensure every action is persisted to VerificationLog (immutable)

Architecture:
  All writes are explicit.  No side-effects outside of the methods below.
  No direct completion endpoint exists — reward grant requires a PASS from this engine.
"""

from __future__ import annotations

import hashlib
import random
from datetime import datetime, timedelta, UTC
from typing import Optional, List, Tuple

from sqlalchemy.orm import Session

from app.models.quest import Quest, QuestType, QuestStatus
from app.models.quest_session import QuestSession, SessionStatus
from app.models.quest_output import QuestOutput, OutputType, OutputQuality
from app.models.player_trust import PlayerTrust, TrustTier
from app.models.verification_log import VerificationLog, VerificationDecision
from app.models.audit_flag import AuditFlag, FlagType, FlagSeverity
from app.models.user import User


# ── Scoring weights (must sum to 1.0) ─────────────────────────────────────────
_W_TIME         = 0.25
_W_OUTPUT       = 0.35
_W_CONSISTENCY  = 0.20
_W_BEHAVIOR     = 0.20

# ── Thresholds ────────────────────────────────────────────────────────────────
_PASS_THRESHOLD         = 0.60
_SOFT_FAIL_THRESHOLD    = 0.40   # Below this → hard fail
_MIN_ACTIVE_RATIO       = 0.60   # Active time must be ≥ 60% of expected
_INSTANT_COMPLETE_RATIO = 0.05   # < 5% of expected time → instant-complete flag
_SPOT_CHECK_RATE_LOW    = 0.30   # LOW trust: 30% of sessions get spot check
_SPOT_CHECK_RATE_NORMAL = 0.15   # NORMAL trust
_SPOT_CHECK_RATE_HIGH   = 0.05   # HIGH trust

# ── Spot-check prompt bank ────────────────────────────────────────────────────
_SPOT_CHECK_PROMPTS = [
    "In 2–3 sentences, summarize the most important thing you learned or did during this quest.",
    "What was the hardest part of this quest? How did you handle it?",
    "Describe one specific action you took that pushed you toward the goal.",
    "What would you do differently if you repeated this quest tomorrow?",
    "Name one concrete result or output from this session.",
    "What obstacle came up and how did you overcome it?",
    "Rate your focus from 1–10 and explain why.",
    "What skill did this quest exercise most? Give a specific example from today.",
]


# ═══════════════════════════════════════════════════════════════════════════════
class VerificationEngine:
    """Stateless service — all state lives in the database."""

    # ── Layer 1 + 2: Session management ──────────────────────────────────────

    @staticmethod
    def open_session(
        db: Session,
        player: User,
        quest: Quest,
        device_id: Optional[str] = None,
        user_agent: Optional[str] = None,
        ip: Optional[str] = None,
    ) -> QuestSession:
        """Create an active session.  Fails if an ACTIVE session already exists."""
        existing = (
            db.query(QuestSession)
            .filter(
                QuestSession.player_id == player.id,
                QuestSession.quest_id  == quest.id,
                QuestSession.status    == SessionStatus.ACTIVE,
            )
            .first()
        )
        if existing:
            return existing  # Idempotent re-start returns existing

        trust = VerificationEngine._get_or_create_trust(db, player.id)
        tier  = trust.get_tier()

        # Determine window boundaries
        now = datetime.now(UTC)
        window_start, window_end = VerificationEngine._compute_window(quest, now)

        # Should this session require output?
        requires_output = VerificationEngine._requires_output(quest, tier)

        # Should this session have a spot check?
        requires_spot_check = VerificationEngine._roll_spot_check(tier)

        ip_hash = hashlib.sha256(ip.encode()).hexdigest()[:64] if ip else None

        session = QuestSession(
            player_id             = player.id,
            quest_id              = quest.id,
            started_at            = now,
            expected_duration_sec = (quest.time_limit_minutes or 30) * 60,
            window_start          = window_start,
            window_end            = window_end,
            device_id             = device_id,
            user_agent            = user_agent[:512] if user_agent else None,
            ip_hash               = ip_hash,
            status                = SessionStatus.ACTIVE,
            requires_output       = requires_output,
            requires_spot_check   = requires_spot_check,
        )
        db.add(session)

        # Update quest status
        quest.status = QuestStatus.IN_PROGRESS
        db.commit()
        db.refresh(session)
        return session

    @staticmethod
    def apply_heartbeat(
        db: Session,
        session: QuestSession,
        active_delta: int,
        idle_delta: int,
        tab_hidden_delta: int = 0,
        app_bg_delta: int = 0,
    ) -> QuestSession:
        """Update running time counters. Refuses writes to terminal sessions."""
        if session.is_terminal():
            return session
        session.active_time_sec  += active_delta
        session.idle_time_sec    += idle_delta
        session.tab_hidden_sec   += tab_hidden_delta
        session.app_bg_sec       += app_bg_delta
        db.commit()
        db.refresh(session)
        return session

    # ── Core verification ─────────────────────────────────────────────────────

    @staticmethod
    def verify_and_close(
        db: Session,
        session: QuestSession,
        quest: Quest,
        player: User,
    ) -> VerificationLog:
        """Run all verification layers, compute score, persist log, apply rewards/penalties."""
        if session.is_terminal():
            # Return existing log if already processed
            log = db.query(VerificationLog).filter(VerificationLog.session_id == session.id).first()
            if log:
                return log
        
        now = datetime.now(UTC)
        flags_raised: List[str] = []
        layers_applied: List[str] = []

        # ── Layer 1: Time gate ────────────────────────────────────────────────
        time_score, time_flags = VerificationEngine._score_time(session, quest, now)
        flags_raised.extend(time_flags)
        layers_applied.append("time_gate")

        # ── Layer 2: Session activity ─────────────────────────────────────────
        behavior_score, behavior_flags = VerificationEngine._score_behavior(session)
        flags_raised.extend(behavior_flags)
        layers_applied.append("session_tracking")
        layers_applied.append("behavior_signals")

        # ── Layer 3: Output proof ─────────────────────────────────────────────
        outputs = db.query(QuestOutput).filter(QuestOutput.session_id == session.id).all()
        output_score, output_flags = VerificationEngine._score_outputs(session, outputs)
        flags_raised.extend(output_flags)
        layers_applied.append("output_proof")

        # ── Layer 4: Spot check ───────────────────────────────────────────────
        # If triggered, output_score is already partially penalized via spot-check output
        if session.requires_spot_check:
            layers_applied.append("spot_check")

        # ── Layer 5: Consistency (trust-based history) ────────────────────────
        trust = VerificationEngine._get_or_create_trust(db, player.id)
        consistency_score, consistency_flags = VerificationEngine._score_consistency(trust, session)
        flags_raised.extend(consistency_flags)
        layers_applied.append("consistency")

        # ── Composite score ───────────────────────────────────────────────────
        v_score = (
            time_score        * _W_TIME        +
            output_score      * _W_OUTPUT      +
            consistency_score * _W_CONSISTENCY +
            behavior_score    * _W_BEHAVIOR
        )

        # ── Decision ─────────────────────────────────────────────────────────
        decision, reward_mult, failure_reason = VerificationEngine._decide(
            v_score, flags_raised, trust
        )

        # ── Reward / penalty calculation ──────────────────────────────────────
        xp_awarded  = 0
        xp_penalty  = 0
        if decision == VerificationDecision.PASS:
            xp_awarded = int(quest.base_xp_reward * reward_mult)
        elif decision in (VerificationDecision.SOFT_FAIL, VerificationDecision.AUDIT):
            xp_awarded = int(quest.base_xp_reward * reward_mult)
            xp_penalty = int(quest.penalty_xp * 0.3)
        else:  # HARD_FAIL
            xp_penalty = quest.penalty_xp

        # ── Trust delta ───────────────────────────────────────────────────────
        trust_delta = VerificationEngine._compute_trust_delta(decision, v_score, flags_raised)
        trust.trust_score = max(0.0, min(100.0, trust.trust_score + trust_delta))
        trust.trust_tier  = trust.get_tier()
        trust.last_session_at = now
        trust.total_sessions += 1
        if decision == VerificationDecision.PASS:
            trust.verified_sessions    += 1
            trust.consecutive_verified += 1
            trust.consecutive_fails     = 0
        elif decision == VerificationDecision.SOFT_FAIL:
            trust.soft_fail_count += 1
            trust.consecutive_fails += 1
            trust.consecutive_verified = 0
        elif decision == VerificationDecision.HARD_FAIL:
            trust.hard_fail_count += 1
            trust.consecutive_fails += 1
            trust.consecutive_verified = 0
        trust.flag_count += len(flags_raised)

        # ── Audit mode trigger ────────────────────────────────────────────────
        if trust.consecutive_fails >= 5 or trust.trust_score < 10:
            trust.audit_mode = True

        # ── Store computed scores back to session ─────────────────────────────
        session.time_score          = time_score
        session.output_score        = output_score
        session.consistency_score   = consistency_score
        session.behavior_score      = behavior_score
        session.verification_score  = v_score
        session.submitted_at        = now
        session.closed_at           = now
        session.failure_reason      = failure_reason

        if decision == VerificationDecision.PASS:
            session.status  = SessionStatus.VERIFIED
            quest.status    = QuestStatus.COMPLETED
        elif decision == VerificationDecision.SOFT_FAIL:
            session.status  = SessionStatus.SOFT_FAIL
            quest.status    = QuestStatus.COMPLETED  # Partial credit
        else:
            session.status  = SessionStatus.HARD_FAIL
            quest.status    = QuestStatus.FAILED

        # ── Raise audit flags ─────────────────────────────────────────────────
        VerificationEngine._raise_flags(db, player.id, session.id, quest.id, flags_raised)

        # ── Immutable verification log ─────────────────────────────────────────
        retro_due = None
        if quest.quest_type in (QuestType.DAILY,) and "sleep" in (quest.title or "").lower():
            retro_due = now + timedelta(hours=16)

        log = VerificationLog(
            session_id          = session.id,
            player_id           = player.id,
            quest_id            = quest.id,
            time_score          = time_score,
            output_score        = output_score,
            consistency_score   = consistency_score,
            behavior_score      = behavior_score,
            verification_score  = v_score,
            decision            = decision,
            failure_reason      = failure_reason,
            reward_multiplier   = reward_mult,
            xp_awarded          = xp_awarded,
            xp_penalty          = xp_penalty,
            trust_delta         = trust_delta,
            trust_score_after   = trust.trust_score,
            spot_check_triggered= session.requires_spot_check,
            output_required     = session.requires_output,
            layers_applied      = layers_applied,
            flags_raised        = flags_raised,
            retrospective_due_at= retro_due,
            verified_at         = now,
        )
        db.add(log)
        db.commit()
        db.refresh(log)

        # ── Apply XP changes via progression service ──────────────────────────
        if xp_awarded > 0 or xp_penalty > 0:
            try:
                from app.services.progression_service import ProgressionService
                from app.models.xp_history import XPChangeType
                if xp_awarded > 0:
                    ProgressionService.apply_xp(
                        db=db,
                        user_id=player.id,
                        xp_amount=xp_awarded,
                        change_type=XPChangeType.QUEST_COMPLETED,
                        quest_id=quest.id,
                        reason=f"Quest verified: score={v_score:.2f}",
                    )
                if xp_penalty > 0:
                    ProgressionService.apply_xp(
                        db=db,
                        user_id=player.id,
                        xp_amount=-xp_penalty,
                        change_type=XPChangeType.QUEST_FAILED,
                        quest_id=quest.id,
                        reason=f"Quest verification failed: {failure_reason}",
                    )
            except Exception:
                pass  # Progression failure must not block log persistence

        return log

    # ── Layer scorers ─────────────────────────────────────────────────────────

    @staticmethod
    def _score_time(
        session: QuestSession,
        quest: Quest,
        now: datetime,
    ) -> Tuple[float, List[str]]:
        """Time-gate + active-time ratio scoring."""
        flags: List[str] = []

        # Gate: submission window
        if session.window_end and now > session.window_end:
            return 0.0, [FlagType.INSTANT_COMPLETE.value]

        expected = session.expected_duration_sec or 1
        total_elapsed = max(1, (now - session.started_at).total_seconds())
        active = session.active_time_sec or 0

        # Instant-complete detection
        if total_elapsed < expected * _INSTANT_COMPLETE_RATIO:
            flags.append(FlagType.INSTANT_COMPLETE.value)
            return 0.1, flags

        # Active-time ratio
        active_ratio = active / expected
        if active_ratio < _MIN_ACTIVE_RATIO:
            flags.append(FlagType.LOW_ACTIVE_TIME.value)

        # Score increases with active ratio, capped at 1.0
        score = min(1.0, active_ratio / _MIN_ACTIVE_RATIO)
        return round(score, 4), flags

    @staticmethod
    def _score_behavior(session: QuestSession) -> Tuple[float, List[str]]:
        """Lightweight behaviour signal scoring."""
        flags: List[str] = []
        expected = session.expected_duration_sec or 1

        total = max(1, (session.active_time_sec or 0) + (session.idle_time_sec or 0))
        idle_ratio   = (session.idle_time_sec or 0)  / total
        hidden_ratio = (session.tab_hidden_sec or 0) / max(1, expected)

        if idle_ratio > 0.80:
            flags.append(FlagType.IDLE_SPIKE.value)

        # Penalize heavy tab-hiding
        hidden_penalty = min(0.5, hidden_ratio)
        score = max(0.0, 1.0 - idle_ratio * 0.6 - hidden_penalty)
        return round(score, 4), flags

    @staticmethod
    def _score_outputs(
        session: QuestSession,
        outputs: List[QuestOutput],
    ) -> Tuple[float, List[str]]:
        """Output proof scoring."""
        flags: List[str] = []

        if session.requires_output and not outputs:
            flags.append(FlagType.NO_OUTPUT.value)
            return 0.0, flags

        if not outputs:
            # Output not required — neutral score
            return 0.7, flags

        # Average quality of submitted outputs
        qualities = []
        for o in outputs:
            if o.quality_score is not None:
                qualities.append(o.quality_score)
            elif o.word_count and o.word_count > 0:
                # Heuristic until evaluated: word-count proxy
                qualities.append(min(1.0, o.word_count / 100))
            else:
                qualities.append(0.2)

        avg_quality = sum(qualities) / len(qualities)
        if avg_quality < 0.3:
            flags.append(FlagType.POOR_OUTPUT.value)

        # Check spot-check response if required
        if session.requires_spot_check:
            spot = next((o for o in outputs if o.output_type == OutputType.SPOT_CHECK_RESP), None)
            if not spot:
                flags.append(FlagType.SPOT_CHECK_FAIL.value)
                avg_quality = max(0.0, avg_quality - 0.25)

        return round(min(1.0, avg_quality), 4), flags

    @staticmethod
    def _score_consistency(
        trust: PlayerTrust,
        session: QuestSession,
    ) -> Tuple[float, List[str]]:
        """Consistency & trust-history scoring."""
        flags: List[str] = []

        # Base from rolling trust
        base = trust.trust_score / 100.0

        # Penalty for instant-complete history
        ic_penalty = min(0.3, trust.instant_complete_count * 0.05)

        # Penalty for consecutive failures
        fail_penalty = min(0.4, trust.consecutive_fails * 0.08)

        if trust.consecutive_fails >= 3:
            flags.append(FlagType.REPEATED_PATTERN.value)

        score = max(0.0, base - ic_penalty - fail_penalty)
        return round(score, 4), flags

    # ── Decision ─────────────────────────────────────────────────────────────

    @staticmethod
    def _decide(
        v_score: float,
        flags: List[str],
        trust: PlayerTrust,
    ) -> Tuple[VerificationDecision, float, Optional[str]]:
        """Classify the verification outcome."""
        hard_flags = {
            FlagType.INSTANT_COMPLETE.value,
            FlagType.NO_OUTPUT.value,
            FlagType.BOT_BEHAVIOR.value,
        }
        has_hard = bool(set(flags) & hard_flags)

        if trust.audit_mode:
            return VerificationDecision.AUDIT, 0.0, "Player is in audit mode."

        if v_score >= _PASS_THRESHOLD and not has_hard:
            return VerificationDecision.PASS, 1.0, None

        if v_score >= _SOFT_FAIL_THRESHOLD and not has_hard:
            reward_mult = 0.3 + (v_score - _SOFT_FAIL_THRESHOLD) * 0.7
            return (
                VerificationDecision.SOFT_FAIL,
                round(reward_mult, 2),
                f"Verification score {v_score:.2f} below threshold. Partial credit granted.",
            )

        reason_parts = [f"Score: {v_score:.2f}"]
        if flags:
            reason_parts.append(f"Flags: {', '.join(flags)}")
        return (
            VerificationDecision.HARD_FAIL,
            0.0,
            " | ".join(reason_parts),
        )

    # ── Trust delta ───────────────────────────────────────────────────────────

    @staticmethod
    def _compute_trust_delta(
        decision: VerificationDecision,
        v_score: float,
        flags: List[str],
    ) -> float:
        if decision == VerificationDecision.PASS:
            return +min(5.0, 2.0 + v_score * 3.0)
        elif decision == VerificationDecision.SOFT_FAIL:
            return -3.0
        elif decision == VerificationDecision.HARD_FAIL:
            base_penalty = -8.0
            flag_penalty = -len(flags) * 0.5
            return base_penalty + flag_penalty
        else:  # AUDIT
            return -15.0

    # ── Helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _get_or_create_trust(db: Session, player_id: int) -> PlayerTrust:
        trust = db.query(PlayerTrust).filter(PlayerTrust.player_id == player_id).first()
        if not trust:
            trust = PlayerTrust(player_id=player_id, trust_score=50.0)
            db.add(trust)
            db.commit()
            db.refresh(trust)
        return trust

    @staticmethod
    def _compute_window(quest: Quest, now: datetime) -> Tuple[Optional[datetime], Optional[datetime]]:
        if quest.quest_type == QuestType.DAILY:
            start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            end   = now.replace(hour=23, minute=59, second=59, microsecond=0)
            return start, end
        elif quest.quest_type == QuestType.WEEKLY:
            weekday = now.weekday()
            start = (now - timedelta(days=weekday)).replace(hour=0, minute=0, second=0, microsecond=0)
            end   = start + timedelta(days=6, hours=23, minutes=59, seconds=59)
            return start, end
        elif quest.expires_at:
            return now, quest.expires_at
        return None, None

    @staticmethod
    def _requires_output(quest: Quest, tier: TrustTier) -> bool:
        """Determine if this quest+tier combo mandates output."""
        if tier == TrustTier.LOW:
            return True  # Always required for low-trust players
        # Always require for hard/extreme quests with MIND/SYSTEM/CONTROL primaries
        if quest.difficulty and quest.difficulty.value in ("hard", "extreme"):
            return True
        # Trust >= HIGH → skip output on casual quests
        if tier == TrustTier.HIGH and quest.difficulty and quest.difficulty.value in ("trivial", "easy"):
            return False
        return False

    @staticmethod
    def _roll_spot_check(tier: TrustTier) -> bool:
        rates = {
            TrustTier.LOW:    _SPOT_CHECK_RATE_LOW,
            TrustTier.NORMAL: _SPOT_CHECK_RATE_NORMAL,
            TrustTier.HIGH:   _SPOT_CHECK_RATE_HIGH,
        }
        return random.random() < rates.get(tier, _SPOT_CHECK_RATE_NORMAL)

    @staticmethod
    def get_spot_check_prompt() -> str:
        return random.choice(_SPOT_CHECK_PROMPTS)

    @staticmethod
    def _raise_flags(
        db: Session,
        player_id: int,
        session_id: int,
        quest_id: int,
        flag_keys: List[str],
    ) -> None:
        severity_map = {
            FlagType.INSTANT_COMPLETE.value:    FlagSeverity.HIGH,
            FlagType.NO_OUTPUT.value:           FlagSeverity.HIGH,
            FlagType.BOT_BEHAVIOR.value:        FlagSeverity.CRITICAL,
            FlagType.IDLE_SPIKE.value:          FlagSeverity.MEDIUM,
            FlagType.LOW_ACTIVE_TIME.value:     FlagSeverity.MEDIUM,
            FlagType.POOR_OUTPUT.value:         FlagSeverity.MEDIUM,
            FlagType.SPOT_CHECK_FAIL.value:     FlagSeverity.MEDIUM,
            FlagType.REPEATED_PATTERN.value:    FlagSeverity.HIGH,
            FlagType.RETROACTIVE_MISMATCH.value:FlagSeverity.MEDIUM,
        }
        for key in flag_keys:
            try:
                flag_type = FlagType(key)
            except ValueError:
                continue
            flag = AuditFlag(
                player_id   = player_id,
                session_id  = session_id,
                quest_id    = quest_id,
                flag_type   = flag_type,
                severity    = severity_map.get(key, FlagSeverity.LOW),
                description = f"Auto-raised by verification engine: {key}",
            )
            db.add(flag)
        if flag_keys:
            db.commit()

    # ── Output quality evaluator ──────────────────────────────────────────────

    @staticmethod
    def evaluate_output_quality(output: QuestOutput) -> float:
        """Heuristic quality score 0.0 – 1.0. Replace with ML scoring in v2."""
        if output.output_type == OutputType.SCREENSHOT:
            # Presence of media URL is enough
            return 0.8 if output.media_url else 0.1

        text = (output.content or "") + (output.response_text or "")
        if not text.strip():
            return 0.0

        words = len(text.split())
        sentences = text.count(".") + text.count("!") + text.count("?")

        # Penalise very short outputs
        if words < 10:
            return 0.1
        if words < 25:
            return 0.35

        # Reward density and length
        score = min(1.0, 0.4 + (words / 200) * 0.4 + (sentences / 10) * 0.2)

        # Time-to-write signal: suspiciously fast = penalty
        if output.time_to_write_sec is not None and words > 0:
            words_per_sec = words / max(1, output.time_to_write_sec)
            if words_per_sec > 8:   # Human typing max ~5–6 wps bursts
                score *= 0.5

        return round(min(1.0, score), 4)

    # ── Retrospective validation ──────────────────────────────────────────────

    @staticmethod
    def apply_retrospective(
        db: Session,
        log: VerificationLog,
        passed: bool,
        player_id: int,
    ) -> None:
        """Called by a scheduled task when a retrospective check is due."""
        log.retrospective_done   = True
        log.retrospective_passed = passed

        if not passed:
            trust = VerificationEngine._get_or_create_trust(db, player_id)
            trust.trust_score = max(0.0, trust.trust_score - 5.0)
            flag = AuditFlag(
                player_id   = player_id,
                session_id  = log.session_id,
                quest_id    = log.quest_id,
                flag_type   = FlagType.RETROACTIVE_MISMATCH,
                severity    = FlagSeverity.MEDIUM,
                description = "Retrospective validation check failed.",
            )
            db.add(flag)
        db.commit()

    # ── Trust weekly recalculation ────────────────────────────────────────────

    @staticmethod
    def recalculate_trust_weekly(db: Session, player_id: int) -> PlayerTrust:
        """Full recalculation of trust score. Call from weekly cron."""
        trust = VerificationEngine._get_or_create_trust(db, player_id)
        total = trust.total_sessions or 1

        success_rate = trust.verified_sessions / total
        fail_penalty = (trust.hard_fail_count * 2 + trust.soft_fail_count) / total
        output_bonus = trust.output_quality_avg * 20
        flag_penalty = min(30, trust.flag_count * 2)

        new_score = (
            success_rate * 60
            + output_bonus
            - fail_penalty * 20
            - flag_penalty
        )
        new_score = max(0.0, min(100.0, new_score))
        trust.trust_score          = new_score
        trust.trust_tier           = trust.get_tier()
        trust.last_recalculated_at = datetime.now(UTC)

        # Exit audit mode if score recovers above 40
        if trust.audit_mode and trust.trust_score > 40:
            trust.audit_mode = False

        db.commit()
        db.refresh(trust)
        return trust
