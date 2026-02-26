"""Domain model — the six power domains of the FLOW System."""

from __future__ import annotations

from datetime import datetime, UTC
from sqlalchemy import Column, Integer, String, Text, DateTime, JSON
from app.db.base import Base


DOMAIN_CODES = ["mind", "body", "core", "control", "presence", "system"]

# Old category → new domain code (migration map)
CATEGORY_TO_DOMAIN: dict[str, str] = {
    "study":  "mind",
    "gym":    "body",
    "sleep":  "core",
    "focus":  "control",
    "social": "presence",
    # system is new — no legacy mapping
}

DOMAIN_TO_CATEGORY: dict[str, str] = {v: k for k, v in CATEGORY_TO_DOMAIN.items()}

DOMAIN_DEFINITIONS: list[dict] = [
    {
        "code":        "mind",
        "name":        "MIND",
        "description": "Learning, deep work, strategy, skill development, knowledge output.",
        "stat_mapping": {"primary": "intelligence", "secondary": "mana", "xp_boost": 1.15},
        "color":       "#00d4ff",
        "icon":        "◈",
    },
    {
        "code":        "body",
        "name":        "BODY",
        "description": "Strength, endurance, conditioning, physical discipline.",
        "stat_mapping": {"primary": "strength", "secondary": "vitality", "xp_boost": 1.0},
        "color":       "#ff2040",
        "icon":        "⚡",
    },
    {
        "code":        "core",
        "name":        "CORE",
        "description": "Sleep, recovery, nutrition, energy regulation.",
        "stat_mapping": {"primary": "vitality", "secondary": "strength", "xp_boost": 1.05},
        "color":       "#00ff88",
        "icon":        "◉",
    },
    {
        "code":        "control",
        "name":        "CONTROL",
        "description": "Willpower, dopamine regulation, routine enforcement, distraction blocking.",
        "stat_mapping": {"primary": "mana", "secondary": "intelligence", "xp_boost": 1.1},
        "color":       "#7c3aed",
        "icon":        "◆",
    },
    {
        "code":        "presence",
        "name":        "PRESENCE",
        "description": "Communication, confidence, social authority, influence.",
        "stat_mapping": {"primary": "charisma", "secondary": "intelligence", "xp_boost": 1.0},
        "color":       "#ffd700",
        "icon":        "◇",
    },
    {
        "code":        "system",
        "name":        "SYSTEM",
        "description": "Planning, finance, environment setup, long-term optimization.",
        "stat_mapping": {"primary": "intelligence", "secondary": "charisma", "xp_boost": 1.2},
        "color":       "#e2e8f0",
        "icon":        "⬡",
    },
]


class Domain(Base):
    __tablename__ = "domains"

    id          = Column(Integer, primary_key=True, index=True)
    code        = Column(String(32), unique=True, nullable=False, index=True)
    name        = Column(String(64), nullable=False)
    description = Column(Text, nullable=True)
    stat_mapping = Column(JSON, nullable=True)   # {"primary": "intelligence", ...}
    color       = Column(String(16), nullable=True)
    icon        = Column(String(8), nullable=True)
    created_at  = Column(DateTime, default=lambda: datetime.now(UTC))
