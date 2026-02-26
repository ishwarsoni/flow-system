"""CustomQuestService — CRUD for user-created quests and dismiss/restore of system quests."""

from __future__ import annotations

from datetime import datetime, UTC
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.user_custom_quest import UserCustomQuest, DismissedSystemQuest
from app.models.quest_template import QuestTemplate
from app.services.difficulty_engine import TIER_RULES, DURATION_CAPS

VALID_CATEGORIES = {"mind", "body", "core", "control", "presence", "system"}
VALID_TIERS      = {"easy", "intermediate", "hard", "extreme"}

# Auto XP values per tier when user does not override
_AUTO_XP: dict[str, int] = {
    "easy":         80,
    "intermediate": 150,
    "hard":         250,
    "extreme":      400,
}

# Metrics template hints shown to user per domain/tier
METRICS_HINTS: dict[str, dict[str, str]] = {
    "mind":     {"hard": "pages read, problems solved, written output", "extreme": "deliverable produced, comprehension score"},
    "body":     {"hard": "sets × reps × weight for each exercise",       "extreme": "total volume, PR attempts, hold times"},
    "core":     {"hard": "sleep hours logged, energy score per hour",    "extreme": "all 7 protocol elements per day"},
    "control":  {"hard": "session duration, violation count",             "extreme": "daily logs for 72h, each rule status"},
    "presence": {"hard": "slide count, recording URL, 3 weaknesses noted", "extreme": "attendee count, outcome, written debrief"},
    "system":   {"hard": "financial figures, net cash flow, 3 actions",  "extreme": "all sections complete, deadlines set"},
}


class CustomQuestService:

    # ── CREATE ─────────────────────────────────────────────────────────────────

    def create(
        self,
        db:                  Session,
        user_id:             int,
        category:            str,
        tier:                str,
        title:               str,
        description:         Optional[str]   = None,
        duration_value:      Optional[float] = None,
        duration_unit:       str             = "minutes",
        xp_override:         Optional[int]   = None,
        constraint_level:    int             = 1,
        performance_required: bool           = False,
        risk_level:          int             = 1,
        metrics_required:    bool            = False,
        metrics_definition:  Optional[dict]  = None,
    ) -> UserCustomQuest:
        category = category.lower().strip()
        tier     = tier.lower().strip()

        if category not in VALID_CATEGORIES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid category '{category}'. Choose from: {sorted(VALID_CATEGORIES)}",
            )
        if tier not in VALID_TIERS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid tier '{tier}'. Choose from: {sorted(VALID_TIERS)}",
            )

        # ── Enforce tier rules ─────────────────────────────────────────────────
        rules = TIER_RULES[tier]

        # Hard / Extreme: metrics are mandatory
        if rules["performance_required"]:
            if not metrics_required or not metrics_definition:
                hint = METRICS_HINTS.get(category, {}).get(tier, "verifiable output")
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=(
                        f"{tier.upper()} quests require metrics_required=True and a "
                        f"metrics_definition. Hint for {category}/{tier}: {hint}."
                    ),
                )

        # Duration cap
        if duration_unit in ("minutes", "min") and duration_value is not None:
            cap = DURATION_CAPS.get(tier, DURATION_CAPS["hard"])
            if duration_value > cap:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=(
                        f"Duration {duration_value:.0f} min exceeds the {tier.upper()} "
                        f"cap of {cap} min. FLOW: no quest may exceed "
                        f"{DURATION_CAPS['extreme']} min (4h) per day."
                    ),
                )

        # Derive max_duration_minutes
        max_dur: Optional[int] = None
        if duration_unit in ("minutes", "min") and duration_value is not None:
            max_dur = int(duration_value)
        elif duration_unit == "hours" and duration_value is not None:
            max_dur = int(duration_value * 60)

        # Override difficulty axes from tier defaults if not explicitly set
        if constraint_level == 1 and tier != "easy":
            constraint_level = rules["constraint_min"]
        if not performance_required and rules["performance_required"]:
            performance_required = True
        if risk_level == 1 and tier != "easy":
            risk_level = rules["risk_min"]

        quest = UserCustomQuest(
            user_id              = user_id,
            category             = category,
            tier                 = tier,
            title                = title.strip(),
            description          = description,
            duration_value       = duration_value,
            duration_unit        = duration_unit,
            max_duration_minutes = max_dur,
            xp_override          = xp_override,
            constraint_level     = constraint_level,
            performance_required = performance_required,
            risk_level           = risk_level,
            metrics_required     = metrics_required,
            metrics_definition   = metrics_definition,
            cooldown_hours       = rules["cooldown_hours"],
            weekly_limit         = rules["weekly_limit"],
        )
        db.add(quest)
        db.flush()
        return quest

    # ── UPDATE ─────────────────────────────────────────────────────────────────

    def update(
        self,
        db:       Session,
        user_id:  int,
        quest_id: int,
        **fields,
    ) -> UserCustomQuest:
        quest = self._owned(db, user_id, quest_id)
        for k, v in fields.items():
            if v is not None and hasattr(quest, k):
                setattr(quest, k, v)
        # Re-validate if tier or metrics changed
        tier  = fields.get("tier", quest.tier)
        rules = TIER_RULES.get(tier, TIER_RULES["easy"])
        if rules["performance_required"]:
            if not quest.metrics_required or not quest.metrics_definition:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=(
                        f"{tier.upper()} quests require metrics_required=True "
                        "and a metrics_definition. Update both fields together."
                    ),
                )
        quest.updated_at = datetime.now(UTC)
        db.flush()
        return quest

    # ── DELETE (hard delete — owner only) ─────────────────────────────────────

    def delete(self, db: Session, user_id: int, quest_id: int) -> None:
        """Soft-delete a manual quest. Only the owner can delete it."""
        quest = self._owned(db, user_id, quest_id)
        quest.is_active  = False
        quest.updated_at = datetime.now(UTC)
        db.flush()

    # ── LIST ───────────────────────────────────────────────────────────────────

    def list_for_user(
        self,
        db:       Session,
        user_id:  int,
        category: Optional[str] = None,
    ) -> list[UserCustomQuest]:
        q = db.query(UserCustomQuest).filter(
            UserCustomQuest.user_id   == user_id,
            UserCustomQuest.is_active == True,
        )
        if category:
            q = q.filter(UserCustomQuest.category == category.lower())
        return q.order_by(UserCustomQuest.created_at.desc()).all()

    # ── DISMISS system quest ───────────────────────────────────────────────────

    def dismiss_system(
        self,
        db:                Session,
        user_id:           int,
        quest_template_id: int,
        reason:            Optional[str] = None,
    ) -> DismissedSystemQuest:
        template = db.query(QuestTemplate).filter(
            QuestTemplate.id == quest_template_id,
        ).first()
        if not template:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Quest template not found.",
            )

        existing = db.query(DismissedSystemQuest).filter(
            DismissedSystemQuest.user_id           == user_id,
            DismissedSystemQuest.quest_template_id == quest_template_id,
        ).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Quest already dismissed.",
            )

        dismissal = DismissedSystemQuest(
            user_id           = user_id,
            quest_template_id = quest_template_id,
            reason            = reason,
        )
        db.add(dismissal)
        db.flush()
        return dismissal

    # ── RESTORE dismissed quest ────────────────────────────────────────────────

    def restore_system(
        self,
        db:                Session,
        user_id:           int,
        quest_template_id: int,
    ) -> None:
        dismissal = db.query(DismissedSystemQuest).filter(
            DismissedSystemQuest.user_id           == user_id,
            DismissedSystemQuest.quest_template_id == quest_template_id,
        ).first()
        if not dismissal:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No dismissal record found.",
            )
        db.delete(dismissal)
        db.flush()

    # ── GET dismissed IDs (used by generator to filter templates) ─────────────

    def get_dismissed_ids(self, db: Session, user_id: int) -> set[int]:
        rows = (
            db.query(DismissedSystemQuest.quest_template_id)
            .filter(DismissedSystemQuest.user_id == user_id)
            .all()
        )
        return {r[0] for r in rows}

    # ── Auto XP helper ─────────────────────────────────────────────────────────

    @staticmethod
    def auto_xp(tier: str) -> int:
        return _AUTO_XP.get(tier, 100)

    # ── Private ────────────────────────────────────────────────────────────────

    def _owned(self, db: Session, user_id: int, quest_id: int) -> UserCustomQuest:
        quest = db.query(UserCustomQuest).filter(
            UserCustomQuest.id       == quest_id,
            UserCustomQuest.user_id  == user_id,
            UserCustomQuest.is_active == True,
        ).first()
        if not quest:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Custom quest not found or you do not own it.",
            )
        return quest


custom_quest_service = CustomQuestService()
