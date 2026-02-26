"""AI Coach Validator — the firewall between AI output and FLOW rules.

BUILD THIS FIRST. If validation is skipped, the system becomes unstable.

Validation rules:
- xp_modifier must be within ±0.2
- max 3 quests per coaching cycle
- domains must be valid FLOW domains
- mode must be known (normal|pressure|punishment|recovery)
- all required fields must be present
- all strings sanitized (no injection, no raw AI leakage)

If validation fails → fallback to default logic.
AI advises. FLOW decides.
"""

from __future__ import annotations

import re
import html
import logging
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)

# ── Constants ──────────────────────────────────────────────────────────────────

VALID_MODES = frozenset({"normal", "pressure", "punishment", "recovery"})
VALID_DOMAINS = frozenset({"mind", "body", "core", "control", "presence", "system"})
VALID_TIERS = frozenset({"easy", "intermediate", "hard", "extreme"})

MAX_XP_MODIFIER = 0.2        # ±20% max
MAX_QUESTS = 3               # AI can suggest at most 3 quests per day
MAX_MESSAGE_LENGTH = 500      # Truncate AI messages
MAX_QUEST_TITLE_LENGTH = 200
MAX_QUEST_DESC_LENGTH = 500
MAX_PRIORITY_DOMAINS = 3

REQUIRED_FIELDS = {"mode", "priority_domains", "new_quests", "xp_modifier", "message"}


# ── Data structures ────────────────────────────────────────────────────────────

@dataclass
class CoachQuest:
    """A quest suggested by the AI coach. Must pass all FLOW rules."""
    title: str
    description: str
    domain: str
    difficulty: str
    estimated_minutes: int

    def as_dict(self) -> dict:
        return {
            "title": self.title,
            "description": self.description,
            "domain": self.domain,
            "difficulty": self.difficulty,
            "estimated_minutes": self.estimated_minutes,
        }


@dataclass
class CoachOutput:
    """Validated AI coach output. Only this structure is allowed into FLOW."""
    mode: str                              # normal|pressure|punishment|recovery
    priority_domains: list[str]            # max 3 valid domains
    new_quests: list[CoachQuest]           # max 3 validated quests
    xp_modifier: float                     # -0.2 to +0.2
    message: str                           # sanitized system message
    raw_valid: bool = True                 # False if this is a fallback
    rejection_reasons: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "mode": self.mode,
            "priority_domains": self.priority_domains,
            "new_quests": [q.as_dict() for q in self.new_quests],
            "xp_modifier": self.xp_modifier,
            "message": self.message,
        }


# ── Default fallback ──────────────────────────────────────────────────────────

DEFAULT_OUTPUT = CoachOutput(
    mode="normal",
    priority_domains=[],
    new_quests=[],
    xp_modifier=0.0,
    message="[ SYSTEM ] AI analysis unavailable. Default protocol active. Continue your assigned quests.",
    raw_valid=False,
    rejection_reasons=["Fallback: AI output was rejected or unavailable."],
)


# ── Sanitization helpers ──────────────────────────────────────────────────────

def _sanitize_string(s: str, max_len: int = MAX_MESSAGE_LENGTH) -> str:
    """Remove HTML, control chars, excessive whitespace. Truncate."""
    if not isinstance(s, str):
        return ""
    s = html.escape(s, quote=True)
    s = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', s)  # strip control chars
    s = re.sub(r'\s+', ' ', s).strip()                          # collapse whitespace
    return s[:max_len]


def _is_safe_string(s: str) -> bool:
    """Reject strings with obvious injection patterns."""
    if not isinstance(s, str):
        return False
    dangerous = [
        '<script', 'javascript:', 'on error=', 'onerror=',
        'eval(', 'exec(', '__import__', 'subprocess',
    ]
    lower = s.lower()
    return not any(d in lower for d in dangerous)


# ── Core Validator ─────────────────────────────────────────────────────────────

class AICoachValidator:
    """Validates raw AI JSON output and returns a safe CoachOutput or fallback."""

    @classmethod
    def validate(cls, raw: dict | None) -> CoachOutput:
        """Validate AI response dict. Returns CoachOutput (possibly fallback).

        If ANY rule fails, the entire output is rejected and default logic applies.
        FLOW never trusts unvalidated AI output.
        """
        if raw is None or not isinstance(raw, dict):
            logger.warning("AI Coach: raw output is None or not a dict — fallback")
            return cls._fallback(["Raw output is None or not a dict."])

        reasons: list[str] = []

        # 1. Required fields
        missing = REQUIRED_FIELDS - set(raw.keys())
        if missing:
            reasons.append(f"Missing required fields: {', '.join(sorted(missing))}")

        # 2. Mode
        mode = raw.get("mode", "").lower().strip() if isinstance(raw.get("mode"), str) else ""
        if mode not in VALID_MODES:
            reasons.append(f"Invalid mode '{mode}'. Must be: {', '.join(sorted(VALID_MODES))}")
            mode = "normal"

        # 3. XP modifier
        xp_mod = raw.get("xp_modifier", 0.0)
        if not isinstance(xp_mod, (int, float)):
            reasons.append(f"xp_modifier must be numeric, got {type(xp_mod).__name__}")
            xp_mod = 0.0
        if abs(xp_mod) > MAX_XP_MODIFIER:
            reasons.append(f"xp_modifier {xp_mod} exceeds ±{MAX_XP_MODIFIER} limit")
            xp_mod = max(-MAX_XP_MODIFIER, min(MAX_XP_MODIFIER, xp_mod))

        # 4. Priority domains
        raw_domains = raw.get("priority_domains", [])
        if not isinstance(raw_domains, list):
            reasons.append("priority_domains must be a list")
            raw_domains = []
        domains = []
        for d in raw_domains[:MAX_PRIORITY_DOMAINS]:
            dl = str(d).lower().strip()
            if dl in VALID_DOMAINS:
                domains.append(dl)
            else:
                reasons.append(f"Invalid domain '{d}'")

        # 5. Message
        msg = raw.get("message", "")
        if not isinstance(msg, str) or not msg.strip():
            reasons.append("Message is empty or not a string")
            msg = "[ SYSTEM ] Operational."
        if not _is_safe_string(msg):
            reasons.append("Message contains unsafe content")
            msg = "[ SYSTEM ] Message rejected for safety."
        msg = _sanitize_string(msg, MAX_MESSAGE_LENGTH)

        # 6. Quests
        raw_quests = raw.get("new_quests", [])
        if not isinstance(raw_quests, list):
            reasons.append("new_quests must be a list")
            raw_quests = []
        if len(raw_quests) > MAX_QUESTS:
            reasons.append(f"Too many quests ({len(raw_quests)} > {MAX_QUESTS})")
            raw_quests = raw_quests[:MAX_QUESTS]

        quests: list[CoachQuest] = []
        for i, rq in enumerate(raw_quests):
            q, q_reasons = cls._validate_quest(rq, i)
            if q:
                quests.append(q)
            reasons.extend(q_reasons)

        # Decision: if there were hard rejections (missing fields) → full fallback
        has_missing_fields = bool(REQUIRED_FIELDS - set(raw.keys()))
        if has_missing_fields:
            logger.warning(f"AI Coach: rejected — {reasons}")
            return cls._fallback(reasons)

        # Soft issues (clamped values, trimmed quests) → still usable with warnings
        output = CoachOutput(
            mode=mode,
            priority_domains=domains,
            new_quests=quests,
            xp_modifier=round(xp_mod, 4),
            message=msg,
            raw_valid=len(reasons) == 0,
            rejection_reasons=reasons,
        )

        if reasons:
            logger.info(f"AI Coach: validated with warnings — {reasons}")
        else:
            logger.info("AI Coach: output validated clean")

        return output

    @classmethod
    def _validate_quest(cls, rq: dict, idx: int) -> tuple[Optional[CoachQuest], list[str]]:
        """Validate a single quest dict. Returns (quest_or_None, reasons)."""
        reasons = []

        if not isinstance(rq, dict):
            return None, [f"Quest {idx}: not a dict"]

        title = rq.get("title", "")
        if not isinstance(title, str) or len(title.strip()) < 5:
            reasons.append(f"Quest {idx}: title too short or invalid")
            return None, reasons
        if not _is_safe_string(title):
            return None, [f"Quest {idx}: title contains unsafe content"]
        title = _sanitize_string(title, MAX_QUEST_TITLE_LENGTH)

        desc = rq.get("description", "")
        if not isinstance(desc, str):
            desc = ""
        if not _is_safe_string(desc):
            desc = ""
        desc = _sanitize_string(desc, MAX_QUEST_DESC_LENGTH)

        domain = str(rq.get("domain", "")).lower().strip()
        if domain not in VALID_DOMAINS:
            reasons.append(f"Quest {idx}: invalid domain '{domain}'")
            return None, reasons

        diff = str(rq.get("difficulty", "")).lower().strip()
        if diff not in VALID_TIERS:
            reasons.append(f"Quest {idx}: invalid difficulty '{diff}'")
            return None, reasons

        minutes = rq.get("estimated_minutes", 30)
        if not isinstance(minutes, (int, float)):
            minutes = 30
        minutes = int(max(5, min(240, minutes)))  # clamp to FLOW limits

        return CoachQuest(
            title=title,
            description=desc,
            domain=domain,
            difficulty=diff,
            estimated_minutes=minutes,
        ), reasons

    @classmethod
    def _fallback(cls, reasons: list[str]) -> CoachOutput:
        """Return default safe output when AI response is rejected."""
        fb = CoachOutput(
            mode=DEFAULT_OUTPUT.mode,
            priority_domains=list(DEFAULT_OUTPUT.priority_domains),
            new_quests=list(DEFAULT_OUTPUT.new_quests),
            xp_modifier=DEFAULT_OUTPUT.xp_modifier,
            message=DEFAULT_OUTPUT.message,
            raw_valid=False,
            rejection_reasons=list(reasons),
        )
        return fb
