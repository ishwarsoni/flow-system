from app.models.user import User
from app.models.goal import Goal
from app.models.user_stats import UserStats
from app.models.xp_history import XPHistory, XPChangeType
from app.models.daily_progress import DailyProgress
from app.models.game_config import GameConfig, DEFAULT_CONFIG
from app.models.difficulty_profile import DifficultyProfile
from app.models.mindset_score import MindsetScore
from app.models.quest_template import QuestTemplate
from app.models.progression_tier import ProgressionTier
from app.models.penalty_tier import PenaltyTier
from app.models.adaptive_quest_session import AdaptiveQuestSession
from app.models.user_custom_quest import UserCustomQuest, DismissedSystemQuest
from app.models.domain import Domain
from app.models.quest import Quest, QuestStatus

# ── Quest Verification System ──────────────────────────────────────────────────
from app.models.quest_session import QuestSession, SessionStatus
from app.models.quest_output import QuestOutput, OutputType, OutputQuality
from app.models.player_trust import PlayerTrust, TrustTier
from app.models.verification_log import VerificationLog, VerificationDecision
from app.models.audit_flag import AuditFlag, FlagType, FlagSeverity
from app.models.ai_coach_log import AICoachLog

__all__ = [
    "User",
    "Goal",
    "UserStats",
    "XPHistory",
    "XPChangeType",
    "DailyProgress",
    "GameConfig",
    "DEFAULT_CONFIG",
    # Adaptive Quest & Mindset Evolution System
    "DifficultyProfile",
    "MindsetScore",
    "QuestTemplate",
    "ProgressionTier",
    "PenaltyTier",
    "AdaptiveQuestSession",
]
