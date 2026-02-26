"""Rank system for FLOW RPG — Solo Leveling inspired"""

import enum
from typing import Optional


class Rank(str, enum.Enum):
    """Player rank tiers — affects difficulty scaling, rewards, and feature access."""
    E = "E"
    D = "D"
    C = "C"
    B = "B"
    A = "A"
    S = "S"
    SS = "SS"
    SSS = "SSS"


# Rank thresholds and multipliers — all gameplay-affecting
# All valid quest difficulty values
ALL_DIFFICULTIES = ["easy", "intermediate", "hard", "extreme"]

RANK_CONFIG = {
    Rank.E: {
        "min_level": 1,
        "max_level": 5,
        "xp_multiplier": 1.0,
        "coin_multiplier": 1.0,
        "allowed_difficulties": ["easy"],
        "hp_bonus": 0,
        "mp_bonus": 0,
        "daily_quest_count": 3,
        "weekly_quest_count": 1,
        "special_quests_unlocked": False,
        "title": "Novice",
    },
    Rank.D: {
        "min_level": 6,
        "max_level": 12,
        "xp_multiplier": 1.1,
        "coin_multiplier": 1.1,
        "allowed_difficulties": ["easy", "intermediate"],
        "hp_bonus": 10,
        "mp_bonus": 5,
        "daily_quest_count": 4,
        "weekly_quest_count": 2,
        "special_quests_unlocked": False,
        "title": "Apprentice",
    },
    Rank.C: {
        "min_level": 13,
        "max_level": 24,
        "xp_multiplier": 1.2,
        "coin_multiplier": 1.2,
        "allowed_difficulties": ["easy", "intermediate", "hard"],
        "hp_bonus": 25,
        "mp_bonus": 15,
        "daily_quest_count": 5,
        "weekly_quest_count": 2,
        "special_quests_unlocked": True,
        "title": "Warrior",
    },
    Rank.B: {
        "min_level": 25,
        "max_level": 39,
        "xp_multiplier": 1.35,
        "coin_multiplier": 1.3,
        "allowed_difficulties": ["easy", "intermediate", "hard"],
        "hp_bonus": 50,
        "mp_bonus": 30,
        "daily_quest_count": 6,
        "weekly_quest_count": 3,
        "special_quests_unlocked": True,
        "title": "Elite",
    },
    Rank.A: {
        "min_level": 40,
        "max_level": 59,
        "xp_multiplier": 1.5,
        "coin_multiplier": 1.5,
        "allowed_difficulties": ["easy", "intermediate", "hard", "extreme"],
        "hp_bonus": 80,
        "mp_bonus": 50,
        "daily_quest_count": 7,
        "weekly_quest_count": 3,
        "special_quests_unlocked": True,
        "title": "Commander",
    },
    Rank.S: {
        "min_level": 60,
        "max_level": 79,
        "xp_multiplier": 1.75,
        "coin_multiplier": 1.8,
        "allowed_difficulties": ["easy", "intermediate", "hard", "extreme"],
        "hp_bonus": 120,
        "mp_bonus": 80,
        "daily_quest_count": 8,
        "weekly_quest_count": 4,
        "special_quests_unlocked": True,
        "title": "Shadow Monarch",
    },
    Rank.SS: {
        "min_level": 80,
        "max_level": 94,
        "xp_multiplier": 2.0,
        "coin_multiplier": 2.0,
        "allowed_difficulties": ["easy", "intermediate", "hard", "extreme"],
        "hp_bonus": 170,
        "mp_bonus": 120,
        "daily_quest_count": 10,
        "weekly_quest_count": 5,
        "special_quests_unlocked": True,
        "title": "National Level",
    },
    Rank.SSS: {
        "min_level": 95,
        "max_level": 100,
        "xp_multiplier": 2.5,
        "coin_multiplier": 2.5,
        "allowed_difficulties": ["easy", "intermediate", "hard", "extreme"],
        "hp_bonus": 250,
        "mp_bonus": 180,
        "daily_quest_count": 12,
        "weekly_quest_count": 6,
        "special_quests_unlocked": True,
        "title": "Absolute Being",
    },
}

# Ordered list for iteration
RANK_ORDER = [Rank.E, Rank.D, Rank.C, Rank.B, Rank.A, Rank.S, Rank.SS, Rank.SSS]


def get_rank_for_level(level: int) -> Rank:
    """Determine rank based on current level."""
    for rank in reversed(RANK_ORDER):
        if level >= RANK_CONFIG[rank]["min_level"]:
            return rank
    return Rank.E


def get_next_rank(current_rank: Rank) -> Rank | None:
    """Get the next rank tier, or None if already max."""
    idx = RANK_ORDER.index(current_rank)
    if idx < len(RANK_ORDER) - 1:
        return RANK_ORDER[idx + 1]
    return None


def get_rank_index(rank: Rank) -> int:
    """Get numeric index of rank (0=E, 7=SSS)."""
    return RANK_ORDER.index(rank)


def get_allowed_difficulties(level: int) -> list[str]:
    """Return the list of difficulty tiers unlocked for a given player level.

    E-Rank  (Lv 1-5):   easy only
    D-Rank  (Lv 6-12):  easy, intermediate
    C-Rank  (Lv 13-24): easy, intermediate, hard
    B-Rank+ (Lv 25+):   easy, intermediate, hard
    A-Rank+ (Lv 40+):   easy, intermediate, hard, extreme
    """
    rank = get_rank_for_level(level)
    return list(RANK_CONFIG[rank]["allowed_difficulties"])


# ─── Solo Leveling style per-level titles ────────────────────────────────────
# One title per level range. Used in UserStats.current_title on every level-up.

LEVEL_TITLES: dict[int, str] = {
    1:  "Novice Hunter",
    2:  "Novice Hunter",
    3:  "Awakened",
    4:  "Awakened",
    5:  "Awakened",
    6:  "Apprentice Hunter",      # D-Rank starts
    7:  "Apprentice Hunter",
    8:  "Gate Crawler",
    9:  "Gate Crawler",
    10: "Dungeon Delver",
    11: "Dungeon Delver",
    12: "Dungeon Delver",
    13: "Iron Hunter",            # C-Rank starts
    14: "Iron Hunter",
    15: "Iron Hunter",
    16: "Shadow Walker",
    17: "Shadow Walker",
    18: "Shadow Walker",
    19: "Blade Hunter",
    20: "Blade Hunter",
    21: "Dungeon Raider",
    22: "Dungeon Raider",
    23: "Dungeon Raider",
    24: "Dungeon Raider",
    25: "Elite Hunter",           # B-Rank starts
    26: "Elite Hunter",
    27: "Elite Hunter",
    28: "Gate Breaker",
    29: "Gate Breaker",
    30: "Gate Breaker",
    31: "Dungeon Predator",
    32: "Dungeon Predator",
    33: "Dungeon Predator",
    34: "Sovereign Striker",
    35: "Sovereign Striker",
    36: "Sovereign Striker",
    37: "Sovereign Striker",
    38: "Sovereign Striker",
    39: "Sovereign Striker",
    40: "Commander",              # A-Rank starts
    41: "Commander",
    42: "Dungeon Conqueror",
    43: "Dungeon Conqueror",
    44: "Dungeon Conqueror",
    45: "Dungeon Conqueror",
    46: "Dragon Slayer",
    47: "Dragon Slayer",
    48: "Dragon Slayer",
    49: "Awakened Monarch",
    50: "Awakened Monarch",
    51: "Awakened Monarch",
    52: "Realm Breaker",
    53: "Realm Breaker",
    54: "Realm Breaker",
    55: "Realm Breaker",
    56: "Realm Breaker",
    57: "Realm Breaker",
    58: "Realm Breaker",
    59: "Realm Breaker",
    60: "National Level Hunter",  # S-Rank starts
    61: "National Level Hunter",
    62: "National Level Hunter",
    63: "Shadow Monarch's Vassal",
    64: "Shadow Monarch's Vassal",
    65: "Shadow Monarch's Vassal",
    66: "Shadow Monarch's Vassal",
    67: "Shadow Monarch's Vassal",
    68: "Slayer Class",
    69: "Slayer Class",
    70: "Slayer Class",
    71: "Slayer Class",
    72: "Catastrophe Class",
    73: "Catastrophe Class",
    74: "Catastrophe Class",
    75: "Catastrophe Class",
    76: "Catastrophe Class",
    77: "Catastrophe Class",
    78: "Catastrophe Class",
    79: "Catastrophe Class",
    80: "Transcendent",           # SS-Rank starts
    81: "Transcendent",
    82: "Transcendent",
    83: "Absolute Predator",
    84: "Absolute Predator",
    85: "Absolute Predator",
    86: "Absolute Predator",
    87: "Absolute Predator",
    88: "Monarch",
    89: "Monarch",
    90: "Monarch",
    91: "Monarch",
    92: "Monarch",
    93: "Monarch",
    94: "Monarch",
    95: "Sovereign",              # SSS-Rank starts
    96: "Sovereign",
    97: "Sovereign",
    98: "Sovereign",
    99: "Sovereign",
    100: "Absolute Being",
}


def get_title_for_level(level: int) -> str:
    """Return the Solo Leveling style title for a given level (1-100)."""
    level = max(1, min(level, 100))
    return LEVEL_TITLES.get(level, "Absolute Being")


# ─── Starting difficulty → starting level ────────────────────────────────────
# When a player picks their starting difficulty, they begin at the corresponding
# level so quests are appropriately scaled from day one.

class StartingDifficulty(str, enum.Enum):
    BEGINNER     = "beginner"      # Level  1 — F/E quests, gentle intro
    NORMAL       = "normal"        # Level  1 — balanced, default
    HARD         = "hard"          # Level 13 — C-Rank from start
    EXTREME      = "extreme"       # Level 25 — B-Rank from start


STARTING_DIFFICULTY_LEVELS: dict[StartingDifficulty, int] = {
    StartingDifficulty.BEGINNER: 1,
    StartingDifficulty.NORMAL:   1,
    StartingDifficulty.HARD:     13,
    StartingDifficulty.EXTREME:  25,
}
