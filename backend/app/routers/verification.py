"""Quest Verification Router — all quest lifecycle endpoints that require validation.

Endpoint contract
─────────────────
POST /quests/{id}/start           → opens a session
PATCH /quests/{id}/session/heartbeat → updates live time counters
POST /quests/{id}/output          → submits a proof artifact
POST /quests/{id}/spot-check      → answers the random validation prompt
POST /quests/{id}/submit          → player declares done (triggers verify)
POST /quests/{id}/complete        → finalises after verified (idempotent)
GET  /quests/{id}/verification    → current verification state
GET  /player/trust                → player's trust profile
GET  /admin/audit-flags           → paginated audit flag list (admin only)
"""

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session
from datetime import datetime, UTC

from app.db.database import get_db
from app.models.user import User
from app.models.quest import Quest, QuestStatus
from app.models.quest_session import QuestSession, SessionStatus
from app.models.quest_output import QuestOutput, OutputType
from app.models.player_trust import PlayerTrust
from app.models.verification_log import VerificationLog
from app.models.audit_flag import AuditFlag
from app.dependencies.auth import get_current_user, get_admin_user
from app.services.verification_engine import VerificationEngine
from app.schemas.verification import (
    SessionStartRequest,
    SessionResponse,
    HeartbeatRequest,
    OutputSubmitRequest,
    OutputResponse,
    QuestSubmitRequest,
    SpotCheckQuestion,
    SpotCheckResponse,
    VerificationResultResponse,
    VerificationStatusResponse,
    TrustProfileResponse,
    AuditFlagResponse,
)

router = APIRouter(tags=["Verification"])


# ── Helpers ───────────────────────────────────────────────────────────────────

def _get_quest_or_404(db: Session, quest_id: int, player_id: int) -> Quest:
    quest = db.query(Quest).filter(
        Quest.id == quest_id,
        Quest.user_id == player_id,
    ).first()
    if not quest:
        raise HTTPException(status_code=404, detail="Quest not found.")
    return quest


def _get_active_session_or_404(db: Session, quest_id: int, player_id: int) -> QuestSession:
    session = db.query(QuestSession).filter(
        QuestSession.quest_id  == quest_id,
        QuestSession.player_id == player_id,
        QuestSession.status    == SessionStatus.ACTIVE,
    ).first()
    if not session:
        raise HTTPException(
            status_code=400,
            detail="No active session found. Start the quest first via POST /quests/{id}/start.",
        )
    return session


# ════════════════════════════════════════════════════════════════════════════════
# 1. Start session
# ════════════════════════════════════════════════════════════════════════════════

@router.post(
    "/quests/{quest_id}/start",
    response_model=SessionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Start a quest — opens a tracked session",
)
async def start_quest(
    quest_id: int,
    body: SessionStartRequest,
    request: Request,
    current_user: User         = Depends(get_current_user),
    db: Session                = Depends(get_db),
):
    """
    Opens a QuestSession.
    - Sets the valid completion window (daily/weekly/timed).
    - Determines if output proof is required based on trust tier.
    - Optionally schedules a spot-check prompt.
    """
    quest = _get_quest_or_404(db, quest_id, current_user.id)
    if quest.status not in (QuestStatus.PENDING, QuestStatus.IN_PROGRESS):
        raise HTTPException(status_code=400, detail=f"Quest is already {quest.status.value}.")

    ip = request.client.host if request.client else None
    session = VerificationEngine.open_session(
        db=db,
        player=current_user,
        quest=quest,
        device_id=body.device_id,
        user_agent=body.user_agent,
        ip=ip,
    )
    return session


# ════════════════════════════════════════════════════════════════════════════════
# 2. Heartbeat
# ════════════════════════════════════════════════════════════════════════════════

@router.patch(
    "/quests/{quest_id}/session/heartbeat",
    response_model=SessionResponse,
    summary="Send a 30-second heartbeat with activity deltas",
)
async def heartbeat(
    quest_id: int,
    body: HeartbeatRequest,
    current_user: User  = Depends(get_current_user),
    db: Session         = Depends(get_db),
):
    """
    Called every 30 seconds from the frontend.
    Updates active / idle / tab-hidden / app-bg counters on the session.
    Frontend must track these locally and send deltas.
    """
    session = _get_active_session_or_404(db, quest_id, current_user.id)
    session = VerificationEngine.apply_heartbeat(
        db=db,
        session=session,
        active_delta=body.active_delta_sec,
        idle_delta=body.idle_delta_sec,
        tab_hidden_delta=body.tab_hidden_delta,
        app_bg_delta=body.app_bg_delta,
    )
    return session


# ════════════════════════════════════════════════════════════════════════════════
# 3. Output submission
# ════════════════════════════════════════════════════════════════════════════════

@router.post(
    "/quests/{quest_id}/output",
    response_model=OutputResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Submit a proof artifact (summary, notes, screenshot…)",
)
async def submit_output(
    quest_id: int,
    body: OutputSubmitRequest,
    current_user: User  = Depends(get_current_user),
    db: Session         = Depends(get_db),
):
    """
    Attaches a proof artifact to the active session.
    Multiple outputs per session are allowed.
    Quality is evaluated immediately by the heuristic engine.
    """
    session = _get_active_session_or_404(db, quest_id, current_user.id)

    try:
        out_type = OutputType(body.output_type)
    except ValueError:
        raise HTTPException(status_code=422, detail=f"Unknown output_type: {body.output_type}")

    text = (body.content or "") + (body.response_text or "")
    word_count = len(text.split()) if text.strip() else 0

    output = QuestOutput(
        session_id       = session.id,
        player_id        = current_user.id,
        quest_id         = quest_id,
        output_type      = out_type,
        content          = body.content,
        media_url        = body.media_url,
        extra_data       = body.metadata,
        prompt_text      = body.prompt_text,
        response_text    = body.response_text,
        time_to_write_sec= body.time_to_write_sec,
        word_count       = word_count,
    )
    # Evaluate quality immediately
    quality_score = VerificationEngine.evaluate_output_quality(output)
    output.quality_score = quality_score

    from app.models.quest_output import OutputQuality
    if quality_score >= 0.8:
        output.quality = OutputQuality.EXCELLENT
    elif quality_score >= 0.6:
        output.quality = OutputQuality.GOOD
    elif quality_score >= 0.35:
        output.quality = OutputQuality.ACCEPTABLE
    else:
        output.quality = OutputQuality.POOR

    output.evaluated_at = datetime.now(UTC)
    db.add(output)
    db.commit()
    db.refresh(output)
    return output


# ════════════════════════════════════════════════════════════════════════════════
# 4. Spot-check prompt retrieval
# ════════════════════════════════════════════════════════════════════════════════

@router.get(
    "/quests/{quest_id}/spot-check",
    response_model=SpotCheckQuestion,
    summary="Get the random spot-check prompt for this session",
)
async def get_spot_check(
    quest_id: int,
    current_user: User  = Depends(get_current_user),
    db: Session         = Depends(get_db),
):
    """Returns the spot-check question if this session requires one."""
    session = _get_active_session_or_404(db, quest_id, current_user.id)
    if not session.requires_spot_check:
        raise HTTPException(status_code=404, detail="No spot-check required for this session.")
    return SpotCheckQuestion(
        prompt=VerificationEngine.get_spot_check_prompt(),
        session_id=session.id,
    )


# ════════════════════════════════════════════════════════════════════════════════
# 5. Submit quest (player declares completion)
# ════════════════════════════════════════════════════════════════════════════════

@router.post(
    "/quests/{quest_id}/submit",
    response_model=VerificationResultResponse,
    summary="Declare quest complete — triggers full verification",
)
async def submit_quest(
    quest_id: int,
    body: QuestSubmitRequest,
    current_user: User  = Depends(get_current_user),
    db: Session         = Depends(get_db),
):
    """
    Player calls this when they believe they are done.
    Runs all 8 verification layers and returns the scored result.
    Rewards are only applied when decision == PASS or SOFT_FAIL.
    """
    session = _get_active_session_or_404(db, quest_id, current_user.id)
    quest   = _get_quest_or_404(db, quest_id, current_user.id)

    # Apply any final activity deltas provided at submit time
    if body.final_active_sec is not None:
        current_active = session.active_time_sec or 0
        delta = max(0, body.final_active_sec - current_active)
        session.active_time_sec = body.final_active_sec
        if body.final_idle_sec is not None:
            session.idle_time_sec = body.final_idle_sec
        db.commit()

    # Mark session as submitted before verification
    session.status       = SessionStatus.SUBMITTED
    session.submitted_at = datetime.now(UTC)
    db.commit()

    log = VerificationEngine.verify_and_close(
        db=db,
        session=session,
        quest=quest,
        player=current_user,
    )
    return log


# ════════════════════════════════════════════════════════════════════════════════
# 6. Complete (idempotent finalisation)
# ════════════════════════════════════════════════════════════════════════════════

@router.post(
    "/quests/{quest_id}/complete",
    response_model=VerificationResultResponse,
    summary="Finalise a submitted quest (idempotent)",
)
async def complete_quest(
    quest_id: int,
    current_user: User  = Depends(get_current_user),
    db: Session         = Depends(get_db),
):
    """
    Idempotent finalisation.  Returns the existing VerificationLog if
    the session is already in a terminal state.  If the session is in
    SUBMITTED state and not yet verified, runs verification now.
    Direct completion without a prior /submit call is rejected.
    """
    quest = _get_quest_or_404(db, quest_id, current_user.id)

    # Find the most recent session for this quest
    session = (
        db.query(QuestSession)
        .filter(
            QuestSession.quest_id  == quest_id,
            QuestSession.player_id == current_user.id,
        )
        .order_by(QuestSession.started_at.desc())
        .first()
    )
    if not session:
        raise HTTPException(status_code=400, detail="No session found. Use /start first.")

    if session.status == SessionStatus.ACTIVE:
        raise HTTPException(
            status_code=400,
            detail="Session is still active. Call /submit to declare completion.",
        )

    # Return existing log if already terminal
    log = db.query(VerificationLog).filter(VerificationLog.session_id == session.id).first()
    if log:
        return log

    # SUBMITTED but not yet logged — run verification
    if session.status == SessionStatus.SUBMITTED:
        log = VerificationEngine.verify_and_close(
            db=db, session=session, quest=quest, player=current_user,
        )
        return log

    raise HTTPException(status_code=400, detail=f"Session in unexpected state: {session.status.value}")


# ════════════════════════════════════════════════════════════════════════════════
# 7. Verification status (GET)
# ════════════════════════════════════════════════════════════════════════════════

@router.get(
    "/quests/{quest_id}/verification",
    response_model=VerificationStatusResponse,
    summary="Get current verification state for a quest",
)
async def get_verification_status(
    quest_id: int,
    current_user: User  = Depends(get_current_user),
    db: Session         = Depends(get_db),
):
    """
    Returns the real-time verification state.
    Frontend polls this to show progress indicators and
    whether a spot-check / output is still needed.
    """
    session = (
        db.query(QuestSession)
        .filter(
            QuestSession.quest_id  == quest_id,
            QuestSession.player_id == current_user.id,
        )
        .order_by(QuestSession.started_at.desc())
        .first()
    )
    if not session:
        return VerificationStatusResponse(
            session_id=None,
            session_status=None,
            requires_output=False,
            requires_spot_check=False,
            spot_check_prompt=None,
            verification_score=None,
            decision=None,
            can_submit=False,
            failure_reason=None,
        )

    log = db.query(VerificationLog).filter(VerificationLog.session_id == session.id).first()
    spot_prompt = None
    if session.requires_spot_check and session.status == SessionStatus.ACTIVE:
        spot_prompt = VerificationEngine.get_spot_check_prompt()

    return VerificationStatusResponse(
        session_id          = session.id,
        session_status      = session.status.value,
        requires_output     = session.requires_output,
        requires_spot_check = session.requires_spot_check,
        spot_check_prompt   = spot_prompt,
        verification_score  = log.verification_score if log else None,
        decision            = log.decision.value if log else None,
        can_submit          = session.status == SessionStatus.ACTIVE,
        failure_reason      = session.failure_reason,
    )


# ════════════════════════════════════════════════════════════════════════════════
# 8. Trust profile
# ════════════════════════════════════════════════════════════════════════════════

@router.get(
    "/player/trust",
    response_model=TrustProfileResponse,
    summary="Get your trust profile",
)
async def get_trust_profile(
    current_user: User  = Depends(get_current_user),
    db: Session         = Depends(get_db),
):
    """Returns the player's current trust score, tier, and aggregate statistics."""
    trust = db.query(PlayerTrust).filter(PlayerTrust.player_id == current_user.id).first()
    if not trust:
        # Initialise if missing
        trust = PlayerTrust(player_id=current_user.id, trust_score=50.0)
        db.add(trust)
        db.commit()
        db.refresh(trust)
    return trust


# ════════════════════════════════════════════════════════════════════════════════
# 9. Admin: audit flags
# ════════════════════════════════════════════════════════════════════════════════

@router.get(
    "/admin/audit-flags",
    response_model=list[AuditFlagResponse],
    summary="[Admin] List audit flags",
)
async def list_audit_flags(
    player_id:  int | None = Query(None),
    resolved:   bool | None = Query(None),
    skip:       int = Query(0, ge=0),
    limit:      int = Query(50, ge=1, le=200),
    current_user: User  = Depends(get_admin_user),
    db: Session         = Depends(get_db),
):
    """
    Returns audit flags. Filter by player or resolved state.
    Restricted to admin/moderator users.
    """
    q = db.query(AuditFlag)
    if player_id is not None:
        q = q.filter(AuditFlag.player_id == player_id)
    if resolved is not None:
        q = q.filter(AuditFlag.resolved == resolved)
    return q.order_by(AuditFlag.raised_at.desc()).offset(skip).limit(limit).all()


# ════════════════════════════════════════════════════════════════════════════════
# 10. Admin: verification logs for a quest
# ════════════════════════════════════════════════════════════════════════════════

@router.get(
    "/quests/{quest_id}/verification/history",
    response_model=list[VerificationResultResponse],
    summary="All verification logs for a quest",
)
async def verification_history(
    quest_id:   int,
    current_user: User  = Depends(get_current_user),
    db: Session         = Depends(get_db),
):
    logs = (
        db.query(VerificationLog)
        .filter(
            VerificationLog.quest_id  == quest_id,
            VerificationLog.player_id == current_user.id,
        )
        .order_by(VerificationLog.verified_at.desc())
        .all()
    )
    return logs
