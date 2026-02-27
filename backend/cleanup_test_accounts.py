"""One-time cleanup: delete test accounts created during CORS debugging.
Run during deploy only once, then remove this file.
"""
import os
import sys

def cleanup():
    db_url = os.environ.get("DATABASE_URL", "")
    if not db_url or "sqlite" in db_url:
        print("CLEANUP: Skipping (not production DB)")
        return

    # Fix Render's postgres:// prefix
    if db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql://", 1)

    from sqlalchemy import create_engine, text
    engine = create_engine(db_url)

    test_emails = [
        "corstest@test.com",
        "testuser123@test.com",
    ]

    with engine.connect() as conn:
        for email in test_emails:
            # Delete related records first (foreign keys)
            result = conn.execute(text("SELECT id FROM users WHERE email = :e"), {"e": email})
            row = result.fetchone()
            if row:
                uid = row[0]
                # Clean up related tables
                for table in [
                    "user_stats", "xp_history", "daily_progress", "quests",
                    "quest_sessions", "adaptive_quest_sessions", "goals",
                    "mindset_scores", "audit_logs", "login_attempts",
                    "difficulty_profiles", "penalty_tiers", "player_trust",
                    "verification_logs", "ai_coach_logs", "inventory",
                ]:
                    try:
                        conn.execute(text(f"DELETE FROM {table} WHERE user_id = :uid"), {"uid": uid})
                    except Exception:
                        pass  # Table might not exist
                conn.execute(text("DELETE FROM users WHERE id = :uid"), {"uid": uid})
                print(f"CLEANUP: Deleted test account {email} (id={uid})")
            else:
                print(f"CLEANUP: {email} not found, skipping")
        conn.commit()
    print("CLEANUP: Done")


if __name__ == "__main__":
    cleanup()
