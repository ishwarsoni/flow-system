"""Quick test for the FLOW Quest System v2 rules.

Run: D:/FLOW/.venv/Scripts/python.exe test_quest_rules.py
"""
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))
os.environ.setdefault("SECRET_KEY", "testkeyxxx32chars_xxxxxxxxxxxxx")
os.environ.setdefault("ALGORITHM", "HS256")

from app.services.difficulty_engine import (
    DifficultyEngine, VERIFICATION_REQUIREMENTS, TIER_RULES,
    DURATION_CAPS, DAILY_MAX_MINUTES, EXTREME_COOLDOWN_HOURS, EXTREME_WEEKLY_LIMIT,
)


def test_config():
    print("=== FLOW Quest System v2 — Configuration Test ===\n")

    # 1. Global caps
    assert DAILY_MAX_MINUTES == 240, "Daily max must be 240 min (4h)"
    assert EXTREME_COOLDOWN_HOURS == 24, "Extreme cooldown must be 24h"
    assert EXTREME_WEEKLY_LIMIT == 3, "Extreme weekly limit must be 3"
    print("[OK] Global caps: 4h daily, 24h cooldown, 3/week extreme")

    # 2. Duration caps
    assert DURATION_CAPS == {"easy": 60, "intermediate": 120, "hard": 180, "extreme": 240}
    print("[OK] Duration caps: 60/120/180/240 min")

    # 3. All tiers require verification
    for tier, rules in TIER_RULES.items():
        assert rules["verification_required"], f"{tier} must require verification"
    print("[OK] ALL tiers require verification")

    # 4. Hard/Extreme require performance metrics
    assert TIER_RULES["hard"]["performance_required"] is True
    assert TIER_RULES["extreme"]["performance_required"] is True
    assert TIER_RULES["easy"]["performance_required"] is False
    assert TIER_RULES["intermediate"]["performance_required"] is False
    print("[OK] Hard/Extreme require metrics; Easy/Intermediate use logs")

    # 5. Extreme restrictions
    assert TIER_RULES["extreme"]["cooldown_hours"] == 24
    assert TIER_RULES["extreme"]["weekly_limit"] == 3
    assert TIER_RULES["extreme"]["can_be_daily"] is False
    print("[OK] Extreme: 24h cooldown, 3/week, cannot be daily")

    # 6. Verification types
    assert VERIFICATION_REQUIREMENTS["easy"]["type"] == "log"
    assert VERIFICATION_REQUIREMENTS["intermediate"]["type"] == "log"
    assert VERIFICATION_REQUIREMENTS["hard"]["type"] == "metrics"
    assert VERIFICATION_REQUIREMENTS["extreme"]["type"] == "metrics"
    print("[OK] Verification types: log/log/metrics/metrics")


def test_vague_rejection():
    print("\n=== Vague Wording Rejection (ALL Tiers) ===\n")

    # Should REJECT
    rejects = [
        ("do some stuff", "easy"),
        ("try to feel productive", "easy"),
        ("idk", "easy"),
        ("maybe do something", "intermediate"),
        ("work on stuff", "hard"),
        ("be productive today", "extreme"),
        ("do things", "easy"),
        ("hi", "easy"),
    ]
    for title, tier in rejects:
        ok, reason = DifficultyEngine.validate_quest_title(title, tier)
        status = "REJECT" if not ok else "UNEXPECTED PASS"
        print(f"  [{status}] ({tier:>12}) \"{title}\"")
        assert not ok, f"Should reject: '{title}' at {tier}"

    # Should PASS
    passes = [
        ("Complete 50 push-ups in 15 minutes", "easy"),
        ("Read 20 pages and write 3 key points", "easy"),
        ("Deep work block: 90 minutes on algorithms", "intermediate"),
        ("3-hour problem set. Log attempted, solved, error rate.", "hard"),
        ("4-hour mastery session. Zero distractions. Prove output.", "extreme"),
    ]
    for title, tier in passes:
        ok, reason = DifficultyEngine.validate_quest_title(title, tier)
        status = "PASS" if ok else f"UNEXPECTED REJECT: {reason}"
        print(f"  [{status}] ({tier:>12}) \"{title}\"")
        assert ok, f"Should pass: '{title}' at {tier} — {reason}"

    print("\n[OK] Vague wording correctly rejected at all tiers")


def test_duration_validation():
    print("\n=== Duration Validation ===\n")

    # Should pass
    DifficultyEngine.validate_duration("easy", 60)
    DifficultyEngine.validate_duration("intermediate", 120)
    DifficultyEngine.validate_duration("hard", 180)
    DifficultyEngine.validate_duration("extreme", 240)
    print("  [OK] Valid durations pass: 60/120/180/240")

    # Should fail — exceeds tier cap
    try:
        DifficultyEngine.validate_duration("easy", 61)
        assert False, "Should have raised"
    except ValueError:
        pass
    print("  [OK] Easy 61 min rejected")

    try:
        DifficultyEngine.validate_duration("extreme", 241)
        assert False, "Should have raised"
    except ValueError:
        pass
    print("  [OK] Extreme 241 min rejected (4h cap)")

    # Should fail — exceeds global 4h cap
    try:
        DifficultyEngine.validate_duration("hard", 241)
        assert False, "Should have raised"
    except ValueError:
        pass
    print("  [OK] 241 min rejected globally (FLOW 4h rule)")


def test_proof_of_effort():
    print("\n=== Proof of Effort Validation ===\n")

    # Hard without metrics → reject
    ok, reason = DifficultyEngine.verify_effort_provable(
        "hard", metrics_required=False
    )
    assert not ok
    print("  [OK] Hard without metrics_required → rejected")

    # Extreme without metrics_definition → reject
    ok, reason = DifficultyEngine.verify_effort_provable(
        "extreme", metrics_required=True, metrics_definition=None
    )
    assert not ok
    print("  [OK] Extreme without metrics_definition → rejected")

    # Hard with full metrics → pass
    ok, reason = DifficultyEngine.verify_effort_provable(
        "hard", metrics_required=True,
        metrics_definition={"reps": "total reps completed"},
        description="Log all sets and reps."
    )
    assert ok
    print("  [OK] Hard with metrics + definition → passed")

    # Easy without log instruction → reject
    ok, reason = DifficultyEngine.verify_effort_provable(
        "easy", metrics_required=False,
        description="Just do a workout."
    )
    assert not ok
    print("  [OK] Easy without log instruction → rejected")

    # Easy with log instruction → pass
    ok, reason = DifficultyEngine.verify_effort_provable(
        "easy", metrics_required=False,
        description="Complete 30 push-ups. Log your count."
    )
    assert ok
    print("  [OK] Easy with 'log' in description → passed")


def test_difficulty_scoring():
    print("\n=== Difficulty Scoring ===\n")

    score = DifficultyEngine.score(
        tier="easy", duration_minutes=30,
        constraint_level=1, performance_required=False, risk_level=1,
    )
    assert score.tier == "easy"
    print(f"  [OK] Easy quest score: {score.score:.4f} → {score.tier}")

    score = DifficultyEngine.score(
        tier="extreme", duration_minutes=240,
        constraint_level=4, performance_required=True, risk_level=4,
    )
    assert score.tier == "extreme"
    print(f"  [OK] Extreme quest score: {score.score:.4f} → {score.tier}")


if __name__ == "__main__":
    test_config()
    test_vague_rejection()
    test_duration_validation()
    test_proof_of_effort()
    test_difficulty_scoring()
    print("\n" + "=" * 50)
    print("ALL TESTS PASSED — FLOW Quest System v2 is valid.")
    print("=" * 50)
