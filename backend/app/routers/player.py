"""Player API router — profile, skill allocation, rank info."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.user import User
from app.dependencies.auth import get_current_user
from app.services.player_service import PlayerService
from app.schemas.quest import PlayerProfileResponse, AllocateStatsRequest, AllocateStatsResponse, ShadowRivalResponse

router = APIRouter()


@router.get("/profile", response_model=PlayerProfileResponse)
async def get_player_profile(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get full player HUD data — vitals, stats, rank, economy, streaks."""
    profile = PlayerService.get_player_profile(db, current_user.id)
    return profile


@router.get("/shadow", response_model=ShadowRivalResponse)
async def get_shadow_rival(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Shadow Rival — AI ghost player on the optimal ascension path.
    Returns a comparison of real vs ideal progression so the hunter can
    see exactly which stat areas need urgent attention."""
    from app.models.user_stats import UserStats
    from app.models.rank import RANK_CONFIG, get_rank_for_level

    stats = db.query(UserStats).filter(UserStats.user_id == current_user.id).first()
    if not stats:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Player not found")

    # Shadow: ideal XP = 350 XP per day × days since account creation (capped at reality × 1.5)
    from app.models.user import User as UserModel
    from datetime import datetime, UTC
    user = db.query(UserModel).filter(UserModel.id == current_user.id).first()
    days_since_join = max(1, (datetime.now(UTC).replace(tzinfo=None) - user.created_at.replace(tzinfo=None)).days) if user else 1
    ideal_xp_per_day = 350
    shadow_total_xp = min(days_since_join * ideal_xp_per_day, int(stats.xp_total_earned * 1.5) + 500)

    # Derive shadow level (same XP curve: base 100 * level^1.5)
    shadow_level = 1
    remaining = shadow_total_xp
    while True:
        xp_needed = int(100 * ((shadow_level + 1) ** 1.5))
        if remaining >= xp_needed:
            remaining -= xp_needed
            shadow_level += 1
        else:
            break
    shadow_level = min(shadow_level, 100)
    shadow_rank = get_rank_for_level(shadow_level)

    # Shadow stats: average stat = shadow_level * 0.8 with some variance by category
    shadow_base = shadow_level * 0.8
    shadow_stats = {
        "strength":     round(min(100, shadow_base * 1.0), 1),
        "intelligence": round(min(100, shadow_base * 1.1), 1),
        "vitality":     round(min(100, shadow_base * 0.9), 1),
        "charisma":     round(min(100, shadow_base * 0.85), 1),
        "mana":         round(min(100, shadow_base * 0.95), 1),
    }
    real_stats = {
        "strength":     round(stats.strength, 1),
        "intelligence": round(stats.intelligence, 1),
        "vitality":     round(stats.vitality, 1),
        "charisma":     round(stats.charisma, 1),
        "mana":         round(stats.mana, 1),
    }

    leading  = [s for s in real_stats if real_stats[s] >= shadow_stats[s]]
    trailing = [s for s in real_stats if real_stats[s] < shadow_stats[s]]

    gap_xp   = max(0, shadow_total_xp - stats.xp_total_earned)
    gap_days = max(0, gap_xp // ideal_xp_per_day)

    if not trailing:
        msg = "[ SYSTEM ] Your shadow has been consumed. You are the dominant existence. Maintain the lead."
    elif len(trailing) >= 4:
        msg = f"[ SYSTEM ] Shadow is {gap_days} days ahead. {', '.join(t.upper() for t in trailing[:2])} critically lagging. Begin targeted training."
    else:
        msg = f"[ SYSTEM ] Shadow leads in {', '.join(t.upper() for t in trailing)}. Close the gap before the next gate opens."

    return ShadowRivalResponse(
        shadow_level=shadow_level,
        shadow_rank=shadow_rank.value,
        shadow_xp=shadow_total_xp,
        real_level=stats.level,
        real_rank=stats.rank.value,
        real_xp=stats.xp_total_earned,
        gap_xp=gap_xp,
        gap_days=gap_days,
        leading_stats=leading,
        trailing_stats=trailing,
        shadow_stats=shadow_stats,
        real_stats=real_stats,
        motivational_message=msg,
    )


@router.post("/allocate-stats", response_model=AllocateStatsResponse)
async def allocate_skill_points(
    request: AllocateStatsRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Spend skill points to increase stats."""
    stats = PlayerService.allocate_skill_points(db, current_user.id, request.allocations)
    return AllocateStatsResponse(
        message=f"Allocated {sum(request.allocations.values())} skill points",
        remaining_skill_points=stats.skill_points,
        stats={
            "strength": stats.strength,
            "intelligence": stats.intelligence,
            "vitality": stats.vitality,
            "charisma": stats.charisma,
            "mana": stats.mana,
        },
    )
