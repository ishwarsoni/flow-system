"""Quest model — the core unit of the FLOW RPG system.

FLOW Quest Rules:
- Quests are NOT tasks. They have types, time limits, penalties, and rewards.
- ALL quests must be real-world, measurable, performance-based, progressive, verifiable.
- No vague self-help tasks.
- If a quest cannot prove effort, it is invalid.
- Four difficulty tiers: EASY | INTERMEDIATE | HARD | EXTREME
- Six domains: MIND | BODY | CORE | CONTROL | PRESENCE | SYSTEM
- No quest > 4 hours (240 min) per day.
- EXTREME: 24h cooldown, max 3/week.
- HARD + EXTREME require metrics.
"""

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Enum, Float, Boolean, JSON
from datetime import datetime, UTC
import enum
from app.db.base import Base


class QuestType(str, enum.Enum):
    DAILY = "daily"           # Auto-generated, expires at midnight
    WEEKLY = "weekly"         # Auto-generated Monday, expires Sunday
    CUSTOM = "custom"         # Player-created
    SPECIAL = "special"       # Rank-gated, high reward
    PENALTY = "penalty"       # Assigned on failure, must complete
    TIMED = "timed"           # Has countdown, expire = fail
    GATE = "gate"             # Daily dungeon Gate — must clear or face penalty quest
    AWAKENING = "awakening"   # Weekly boss trial — perfect-streak unlock, extreme difficulty


class QuestStatus(str, enum.Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    EXPIRED = "expired"       # Time ran out — counts as failure
    ABANDONED = "abandoned"


class Difficulty(str, enum.Enum):
    """Four canonical difficulty tiers for FLOW.

    Difficulty scales by performance and output, NOT time alone.
    TRIVIAL and MEDIUM are legacy values — never generated, kept for migration compat.
    """
    TRIVIAL = "trivial"           # LEGACY — not generated (0.5x multiplier)
    EASY = "easy"                 # 1x multiplier  — log-based verification
    MEDIUM = "medium"             # LEGACY — maps to INTERMEDIATE
    INTERMEDIATE = "intermediate" # 1.5x multiplier — log-based verification + measured output
    HARD = "hard"                 # 2x multiplier  — metrics required
    EXTREME = "extreme"           # 3x multiplier  — metrics required, 24h cooldown, 3/week


class VerificationType(str, enum.Enum):
    """How a quest proves effort was applied. ALL quests must have one."""
    LOG = "log"                   # Easy/Intermediate: player logs what was done
    METRICS = "metrics"           # Hard/Extreme: player submits measurable data
    OUTPUT = "output"             # Player must produce a deliverable


class StatType(str, enum.Enum):
    """Which stat a quest primarily trains."""
    STRENGTH = "strength"
    INTELLIGENCE = "intelligence"
    VITALITY = "vitality"
    CHARISMA = "charisma"
    MANA = "mana"


class Quest(Base):
    __tablename__ = "quests"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    # === TEMPLATE PROVENANCE ===
    # Every system-generated quest MUST link back to its source template.
    # NULL only allowed for legacy quests and player-created (is_manual=True) quests.
    template_id = Column(Integer, ForeignKey("quest_templates.id"), nullable=True, index=True)

    # === QUEST IDENTITY ===
    title = Column(String(200), nullable=False)
    description = Column(String(1000), nullable=True)
    quest_type = Column(Enum(QuestType), default=QuestType.CUSTOM, index=True)
    difficulty = Column(Enum(Difficulty), default=Difficulty.EASY)
    primary_stat = Column(Enum(StatType), default=StatType.STRENGTH)  # Which stat this trains

    # === DOMAIN & DIFFICULTY META ===
    # Domain matches adaptive quest categories: mind|body|core|control|presence|system
    domain = Column(String(32), nullable=True, index=True)
    # How this quest proves effort — ALL quests must have a verification type
    # "log" = Easy/Intermediate (write what was done), "metrics" = Hard/Extreme (submit data)
    verification_type = Column(
        Enum(VerificationType), default=VerificationType.LOG, nullable=False,
        comment="How effort is proven: log (easy/inter) or metrics (hard/extreme)"
    )
    # If True, player must submit verifiable proof/metrics before completion is accepted
    metrics_required = Column(Boolean, default=False, nullable=False)
    # Hours player must wait before attempting this quest again (EXTREME = 24)
    cooldown_hours = Column(Integer, default=0, nullable=False)
    # Max times this quest type can be completed in a 7-day window (EXTREME = 3)
    weekly_limit = Column(Integer, nullable=True)   # NULL = no limit
    # True for player-created quests; False for system-generated
    is_manual = Column(Boolean, default=False, nullable=False)

    # === REWARDS (earned on completion) ===
    base_xp_reward = Column(Integer, default=100)
    coin_reward = Column(Integer, default=10)
    stat_rewards = Column(JSON, nullable=True)       # {"strength": 2.5, "vitality": 1.0}
    item_rewards = Column(JSON, nullable=True)       # [{"item_id": 1, "quantity": 1}]
    bonus_skill_points = Column(Integer, default=0)

    # === PENALTIES (applied on failure) ===
    penalty_xp = Column(Integer, default=0)           # XP lost on fail (positive number)
    penalty_hp = Column(Integer, default=0)            # HP lost on fail
    penalty_stat = Column(JSON, nullable=True)         # {"strength": -1.5}
    generates_penalty_quest = Column(Boolean, default=False)  # Creates a penalty quest on fail

    # === PERFORMANCE MULTIPLIER ===
    # XP = base_xp_reward × performance_multiplier after completion verification
    performance_multiplier = Column(Float, default=1.0, nullable=False,
                                    comment="0.0–3.0; set by tier or verification engine")
    # Max duration for this quest in minutes (tier cap); NULL = no limit
    max_duration_minutes = Column(Integer, nullable=True,
                                  comment="Hard cap for this quest's duration based on tier")

    # === TIME ===
    time_limit_minutes = Column(Integer, nullable=True)  # For timed quests
    expires_at = Column(DateTime, nullable=True)          # Auto-fail datetime
    deadline = Column(DateTime, nullable=True)            # Soft deadline display

    # === MP COST ===
    mp_cost = Column(Integer, default=0)              # MP consumed to attempt

    # === STATUS ===
    status = Column(Enum(QuestStatus), default=QuestStatus.PENDING, index=True)
    auto_generated = Column(Boolean, default=False)
    parent_quest_id = Column(Integer, ForeignKey("quests.id"), nullable=True)  # For penalty chains

    # === VERIFICATION ===
    # Submitted proof/metric data (set when player claims completion on a metrics_required quest)
    # Format: {"reps": 100, "sets": 4, "notes": "...", "proof_url": "..."}
    metrics_submitted = Column(JSON, nullable=True)
    metrics_verified = Column(Boolean, nullable=True)  # True/False/None (pending review)

    # === SPECIAL QUEST FLAGS ===
    is_awakening_trial = Column(Boolean, default=False)   # Weekly boss \u2014 cleared difficulty gates permanent stat bonus
    gate_rank = Column(String(8), nullable=True)          # Gate rank label: F | E | D | C | B | A | S

    # === TIMESTAMPS ===
    created_at = Column(DateTime, default=lambda: datetime.now(UTC), index=True)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    failed_at = Column(DateTime, nullable=True)
    last_assigned_at = Column(DateTime, nullable=True, index=True,
                              comment="When this template was last assigned to this user — for 48h cooldown")

    def __repr__(self):
        return f"<Quest(id={self.id}, type={self.quest_type}, title={self.title}, status={self.status})>"
