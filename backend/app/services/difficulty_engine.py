"""DifficultyEngine — weighted multi-factor difficulty scoring for FLOW quests.

Difficulty is NOT determined by time alone.
It is scored across four independent axes:

    difficulty_score =
        duration_weight   * normalised_duration   +
        constraint_weight * normalised_constraint  +
        performance_weight * performance_factor    +
        risk_weight       * normalised_risk

Score bands
-----------
    EASY         0.00 – 0.30
    INTERMEDIATE 0.30 – 0.55
    HARD         0.55 – 0.75
    EXTREME      0.75 – 1.00

Hard Limits (FLOW Global Rules)
-------------------------------
    No quest > 4 hours (240 min) per day.
    Daily quests       : non-extreme tiers ≤ 180 minutes
    Extreme quests     : ≤ 240 minutes (absolute 4h cap)
    Extreme cooldown   : 24 hours between attempts
    Extreme weekly cap : 3 completions per rolling 7-day window
    Extreme cannot auto-spawn as daily quest

Tier Requirements
-----------------
    ALL tiers    : must be verifiable — proof of effort required
    EASY         : log-based verification (what was done, output noted)
    INTERMEDIATE : log-based verification with measured output
    HARD         : metrics required (measurable performance criterion)
    EXTREME      : metrics required + 24h cooldown + 3/week cap

    Vague wording is forbidden at ALL tiers.
    If a quest cannot prove effort, it is invalid.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


# ── Duration caps (minutes) ────────────────────────────────────────────────────
# FLOW GLOBAL RULE: No quest may exceed 4 hours (240 min) in a single day.
# Extreme cap = 240 min. Daily non-extreme cap = 180 min.

DURATION_CAPS: dict[str, int] = {
    "easy":         60,       # max 1 hour
    "intermediate": 120,      # max 2 hours
    "hard":         180,      # max 3 hours
    "extreme":      240,      # max 4 hours (absolute FLOW cap)
}

DAILY_MAX_MINUTES       = 240   # FLOW rule: no quest > 4 hours per day
DAILY_DURATION_CAP      = 180   # non-extreme daily quests ≤ 180 min
EXTREME_COOLDOWN_HOURS  = 24    # 24h between extreme quests
EXTREME_WEEKLY_LIMIT    = 3     # max extreme completions per 7-day window

# ── Verification requirements per tier ─────────────────────────────────────────
# ALL quests must be verifiable. If it can't prove effort, it's invalid.
VERIFICATION_REQUIREMENTS: dict[str, dict] = {
    "easy":         {"type": "log",     "description": "Log what was done. Note output."},
    "intermediate": {"type": "log",     "description": "Log measured output with numbers."},
    "hard":         {"type": "metrics", "description": "Submit measurable performance data."},
    "extreme":      {"type": "metrics", "description": "Submit full metrics + proof of output."},
}


# ── Tier rules ────────────────────────────────────────────────────────────────

TIER_RULES: dict[str, dict] = {
    "easy": {
        "constraint_min": 1,
        "constraint_max": 1,
        "performance_required": False,
        "verification_required": True,   # ALL tiers require verification
        "risk_min": 1,
        "risk_max": 1,
        "cooldown_hours": 0,
        "can_be_daily": True,
        "weekly_limit": None,
    },
    "intermediate": {
        "constraint_min": 2,
        "constraint_max": 2,
        "performance_required": False,
        "verification_required": True,   # ALL tiers require verification
        "risk_min": 2,
        "risk_max": 2,
        "cooldown_hours": 0,
        "can_be_daily": True,
        "weekly_limit": None,
    },
    "hard": {
        "constraint_min": 3,
        "constraint_max": 3,
        "performance_required": True,    # HARD requires measurable metrics
        "verification_required": True,
        "risk_min": 3,
        "risk_max": 3,
        "cooldown_hours": 0,
        "can_be_daily": True,
        "weekly_limit": None,
    },
    "extreme": {
        "constraint_min": 4,
        "constraint_max": 4,
        "performance_required": True,    # EXTREME requires strict performance criteria
        "verification_required": True,
        "risk_min": 4,
        "risk_max": 4,
        "cooldown_hours": EXTREME_COOLDOWN_HOURS,   # 24h
        "can_be_daily": False,            # cannot auto-spawn as daily
        "weekly_limit": EXTREME_WEEKLY_LIMIT,        # 3/week
    },
}

# ── Scoring weights (must sum to 1.0) ─────────────────────────────────────────

WEIGHT_DURATION    = 0.25
WEIGHT_CONSTRAINT  = 0.30
WEIGHT_PERFORMANCE = 0.25
WEIGHT_RISK        = 0.20


# ── Score thresholds ───────────────────────────────────────────────────────────

TIER_THRESHOLDS: list[tuple[float, str]] = [
    (0.75, "extreme"),
    (0.55, "hard"),
    (0.30, "intermediate"),
    (0.00, "easy"),
]


@dataclass
class DifficultyScore:
    """Full breakdown of the computed difficulty score."""

    tier: str
    score: float
    duration_component: float
    constraint_component: float
    performance_component: float
    risk_component: float
    duration_minutes: int
    constraint_level: int
    performance_required: bool
    risk_level: int
    cooldown_hours: int

    def as_dict(self) -> dict:
        return {
            "tier": self.tier,
            "score": round(self.score, 4),
            "components": {
                "duration":    round(self.duration_component, 4),
                "constraint":  round(self.constraint_component, 4),
                "performance": round(self.performance_component, 4),
                "risk":        round(self.risk_component, 4),
            },
            "duration_minutes":   self.duration_minutes,
            "constraint_level":   self.constraint_level,
            "performance_required": self.performance_required,
            "risk_level":         self.risk_level,
            "cooldown_hours":     self.cooldown_hours,
        }


class DifficultyEngine:
    """Stateless difficulty scoring utility."""

    # ── Core scorer ────────────────────────────────────────────────────────────

    @staticmethod
    def score(
        tier: str,
        duration_minutes: int,
        constraint_level: int,
        performance_required: bool,
        risk_level: int,
    ) -> DifficultyScore:
        """Compute a weighted difficulty score.

        Parameters
        ----------
        tier : str
            Target tier — used to select the appropriate duration cap for
            normalisation. One of: easy | intermediate | hard | extreme
        duration_minutes : int
            Planned duration of the quest in minutes.
        constraint_level : int
            How constrained the quest is (1 = light rules, 4 = maximum).
        performance_required : bool
            Whether a measurable performance criterion must be met.
        risk_level : int
            Consequence of failure (1 = low, 4 = high penalty / demotion risk).
        """
        tier = tier.lower()
        cap = DURATION_CAPS.get(tier, DURATION_CAPS["hard"])

        # Normalise each axis to [0.0, 1.0]
        dur_norm  = min(duration_minutes / cap, 1.0)
        con_norm  = min((constraint_level - 1) / 3.0, 1.0)   # 1–4 → 0.0–1.0
        perf_val  = 1.0 if performance_required else 0.0
        risk_norm = min((risk_level - 1) / 3.0, 1.0)         # 1–4 → 0.0–1.0

        d_comp  = WEIGHT_DURATION    * dur_norm
        c_comp  = WEIGHT_CONSTRAINT  * con_norm
        p_comp  = WEIGHT_PERFORMANCE * perf_val
        r_comp  = WEIGHT_RISK        * risk_norm

        total = d_comp + c_comp + p_comp + r_comp

        # Classify output tier from score
        classified = "easy"
        for threshold, label in TIER_THRESHOLDS:
            if total >= threshold:
                classified = label
                break

        cooldown = TIER_RULES.get(tier, {}).get("cooldown_hours", 0)

        return DifficultyScore(
            tier=classified,
            score=total,
            duration_component=d_comp,
            constraint_component=c_comp,
            performance_component=p_comp,
            risk_component=r_comp,
            duration_minutes=duration_minutes,
            constraint_level=constraint_level,
            performance_required=performance_required,
            risk_level=risk_level,
            cooldown_hours=cooldown,
        )

    # ── Duration cap validator ─────────────────────────────────────────────────

    @staticmethod
    def validate_duration(tier: str, duration_minutes: int, is_daily: bool = True) -> None:
        """Raise ValueError if the duration violates hard limits.

        FLOW Global Rules:
            No quest > 4 hours (240 min) — ever.
            Daily quests     : non-extreme tiers ≤ 180 min
            Extreme quests   : ≤ 240 min (4h absolute cap)
            All other tiers  : tier-specific cap
        """
        tier = tier.lower()

        # FLOW GLOBAL RULE: No quest exceeds 4 hours
        if duration_minutes > DAILY_MAX_MINUTES:
            raise ValueError(
                f"FLOW Rule: No quest may exceed {DAILY_MAX_MINUTES} minutes (4 hours). "
                f"Received {duration_minutes} min. Reduce scope."
            )

        tier_cap = DURATION_CAPS.get(tier, DURATION_CAPS["hard"])

        if duration_minutes > tier_cap:
            raise ValueError(
                f"Quest duration {duration_minutes} min exceeds the {tier.upper()} cap "
                f"of {tier_cap} min. Difficulty scales by performance, not time."
            )

        # Daily cap of 180 min only applies to non-extreme tiers.
        if is_daily and tier != "extreme" and duration_minutes > DAILY_DURATION_CAP:
            raise ValueError(
                f"Daily quests cannot exceed {DAILY_DURATION_CAP} minutes. "
                f"Received {duration_minutes} min. Reduce duration or switch to weekly."
            )

    # ── Template validator ─────────────────────────────────────────────────────

    @staticmethod
    def validate_template(
        tier: str,
        max_duration_minutes: int,
        constraint_level: int,
        performance_required: bool,
        risk_level: int,
    ) -> tuple[bool, str]:
        """Validate a quest template against tier rules.

        Returns (is_valid, reason). If valid, reason is an empty string.
        """
        tier = tier.lower()
        rules = TIER_RULES.get(tier)
        if rules is None:
            return False, f"Unknown tier '{tier}'. Must be: easy | intermediate | hard | extreme."

        # Duration cap
        cap = DURATION_CAPS.get(tier, DURATION_CAPS["hard"])
        if max_duration_minutes > cap:
            return False, (
                f"Duration {max_duration_minutes} min exceeds {tier.upper()} cap of {cap} min. "
                f"Time alone must not determine difficulty — add constraints instead."
            )

        # Constraint level
        c_min, c_max = rules["constraint_min"], rules["constraint_max"]
        if not (c_min <= constraint_level <= c_max):
            return False, (
                f"{tier.upper()} tier requires constraint_level {c_min}–{c_max}, "
                f"got {constraint_level}."
            )

        # Performance requirement
        if rules["performance_required"] and not performance_required:
            return False, (
                f"{tier.upper()} quests must set performance_required=True. "
                f"Hard and Extreme require a measurable success criterion."
            )

        # Risk level
        r_min, r_max = rules["risk_min"], rules["risk_max"]
        if not (r_min <= risk_level <= r_max):
            return False, (
                f"{tier.upper()} tier requires risk_level {r_min}–{r_max}, "
                f"got {risk_level}."
            )

        # Sanity: duration-heavy templates without constraints are rejected
        cap = DURATION_CAPS.get(tier, DURATION_CAPS["hard"])
        pct_of_cap = max_duration_minutes / cap
        if pct_of_cap > 0.85 and constraint_level < (c_min + 1) and not performance_required:
            return False, (
                f"Quest uses {pct_of_cap:.0%} of the duration cap but has no performance "
                f"requirement and low constraints. Rejected: unsustainable and unrealistic."
            )

        return True, ""

    # ── Default tier params ─────────────────────────────────────────────────────

    @staticmethod
    def defaults_for_tier(tier: str) -> dict:
        """Return the canonical constraint/performance/risk defaults for a tier."""
        rules = TIER_RULES.get(tier.lower(), TIER_RULES["easy"])
        return {
            "constraint_level":     rules["constraint_min"],
            "performance_required": rules["performance_required"],
            "verification_required": rules.get("verification_required", True),
            "risk_level":           rules["risk_min"],
            "cooldown_hours":       rules["cooldown_hours"],
            "can_be_daily":         rules["can_be_daily"],
            "weekly_limit":         rules["weekly_limit"],
        }

    # ── Vague wording validator ────────────────────────────────────────────────

    # Words that signal vague, unverifiable intent. Forbidden at ALL tiers.
    _VAGUE_WORDS: set[str] = {
        "did", "do", "some", "stuff", "things", "try", "maybe", "feel",
        "work on", "something", "a bit", "a little", "relax", "chill",
        "idk", "whatever", "misc", "general", "various",
    }

    # Patterns that indicate non-specific goals (checked as substrings)
    _VAGUE_PATTERNS: list[str] = [
        "do some", "try to", "work on stuff", "do things", "feel better",
        "be productive", "get stuff done", "do work", "self care",
        "be more", "try harder",
    ]

    @classmethod
    def validate_quest_title(cls, title: str, tier: str = "easy") -> tuple[bool, str]:
        """Validate that a quest title is specific, measurable, and not vague.

        FLOW Rule: Vague wording is forbidden at ALL tiers.
        Returns (is_valid, reason). If valid, reason is empty.
        """
        title_lower = title.lower().strip()
        title_words = set(title_lower.split())

        # Check for vague individual words
        matched_vague = title_words.intersection(cls._VAGUE_WORDS)
        if matched_vague:
            return False, (
                f"Quest title contains vague wording: {matched_vague}. "
                "All FLOW quests must state a specific, measurable action. "
                "Replace vague words with concrete numbers, outputs, or actions."
            )

        # Check for vague phrase patterns
        for pattern in cls._VAGUE_PATTERNS:
            if pattern in title_lower:
                return False, (
                    f"Quest title contains vague pattern '{pattern}'. "
                    "All FLOW quests must be specific and verifiable. "
                    "State what will be done and how it will be measured."
                )

        # Minimum title length — must contain enough specificity
        if len(title.split()) < 3:
            return False, (
                "Quest title is too short to be specific. "
                "A valid quest title must describe what is being done and the scope. "
                "Example: 'Complete 50 push-ups in 15 minutes'"
            )

        # Hard/Extreme: must contain a number or metric indicator
        if tier.lower() in ("hard", "extreme"):
            has_number = any(c.isdigit() for c in title)
            metric_words = {"reps", "sets", "minutes", "min", "hours", "pages", "words",
                           "km", "laps", "rounds", "sessions", "days", "log", "track",
                           "record", "submit", "prove", "measure", "count"}
            has_metric = bool(title_words.intersection(metric_words))
            if not has_number and not has_metric:
                return False, (
                    f"{tier.upper()} quests must include a measurable target "
                    "(number or metric keyword). "
                    "State the specific output to be proven."
                )

        return True, ""

    # ── Proof-of-effort validator ──────────────────────────────────────────────

    @classmethod
    def verify_effort_provable(cls, tier: str, metrics_required: bool,
                                metrics_definition: dict | None = None,
                                description: str = "") -> tuple[bool, str]:
        """Validate that a quest has sufficient proof-of-effort mechanism.

        FLOW Rule: If a quest cannot prove effort, it is invalid.
        ALL tiers must have some verification path.
        """
        tier = tier.lower()
        rules = TIER_RULES.get(tier, TIER_RULES["easy"])
        req = VERIFICATION_REQUIREMENTS.get(tier, VERIFICATION_REQUIREMENTS["easy"])

        # Hard/Extreme: metrics_required must be True with a definition
        if rules["performance_required"]:
            if not metrics_required:
                return False, (
                    f"{tier.upper()} quests require metrics_required=True. "
                    f"Verification: {req['description']}"
                )
            if not metrics_definition:
                return False, (
                    f"{tier.upper()} quests require a metrics_definition. "
                    "Specify exactly what the player must submit "
                    "(reps, sets, output size, scores, logs)."
                )

        # Easy/Intermediate: description must indicate what will be logged
        if tier in ("easy", "intermediate"):
            desc_lower = (description or "").lower()
            log_indicators = [
                "log", "record", "write", "note", "track", "submit",
                "document", "list", "count", "report", "screenshot",
            ]
            has_log_instruction = any(w in desc_lower for w in log_indicators)
            if not has_log_instruction and not metrics_required:
                return False, (
                    f"Even {tier.upper()} quests must be verifiable. "
                    "The description must instruct the player how to prove "
                    "effort was applied (log, record, note, write, track, etc.). "
                    f"Verification level: {req['description']}"
                )

        return True, ""

    # ── Cap-aware value generator ──────────────────────────────────────────────

    @staticmethod
    def capped_duration(tier: str, raw_minutes: float) -> int:
        """Clamp a raw generated duration to the tier's hard cap.

        Returns the clamped value in whole minutes.
        """
        cap = DURATION_CAPS.get(tier.lower(), DURATION_CAPS["hard"])
        return min(int(raw_minutes), cap)
