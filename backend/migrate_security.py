"""Migration: Add security infrastructure tables and columns.

Creates:
- audit_logs table
- login_attempts table
- account_lockouts table
- suspicion_score column on user_stats

Run once:
    cd backend
    python migrate_security.py
"""

import sqlite3
import sys


def migrate(db_path: str = "flow.db"):
    conn = sqlite3.connect(db_path)
    c = conn.cursor()

    # ── 1. audit_logs table ──────────────────────────────────────────────
    c.execute("""
        CREATE TABLE IF NOT EXISTS audit_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            event_type VARCHAR(50) NOT NULL,
            ip_address VARCHAR(45),
            user_agent VARCHAR(500),
            metadata JSON,
            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    """)
    c.execute("CREATE INDEX IF NOT EXISTS ix_audit_logs_user_id ON audit_logs(user_id)")
    c.execute("CREATE INDEX IF NOT EXISTS ix_audit_logs_event_type ON audit_logs(event_type)")
    c.execute("CREATE INDEX IF NOT EXISTS ix_audit_logs_created_at ON audit_logs(created_at)")
    c.execute("CREATE INDEX IF NOT EXISTS ix_audit_user_event ON audit_logs(user_id, event_type)")
    c.execute("CREATE INDEX IF NOT EXISTS ix_audit_event_created ON audit_logs(event_type, created_at)")
    print("[+] audit_logs table ready")

    # ── 2. login_attempts table ──────────────────────────────────────────
    c.execute("""
        CREATE TABLE IF NOT EXISTS login_attempts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email VARCHAR(100) NOT NULL,
            ip_address VARCHAR(45) NOT NULL,
            success INTEGER DEFAULT 0,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    c.execute("CREATE INDEX IF NOT EXISTS ix_login_attempts_email ON login_attempts(email)")
    c.execute("CREATE INDEX IF NOT EXISTS ix_login_attempt_email_ip ON login_attempts(email, ip_address)")
    c.execute("CREATE INDEX IF NOT EXISTS ix_login_attempt_created ON login_attempts(created_at)")
    print("[+] login_attempts table ready")

    # ── 3. account_lockouts table ────────────────────────────────────────
    c.execute("""
        CREATE TABLE IF NOT EXISTS account_lockouts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email VARCHAR(100) NOT NULL,
            ip_address VARCHAR(45) NOT NULL,
            locked_until DATETIME NOT NULL,
            reason VARCHAR(255) DEFAULT 'Too many failed login attempts',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    c.execute("CREATE INDEX IF NOT EXISTS ix_lockout_email ON account_lockouts(email)")
    c.execute("CREATE INDEX IF NOT EXISTS ix_lockout_email_ip ON account_lockouts(email, ip_address)")
    print("[+] account_lockouts table ready")

    # ── 4. suspicion_score on user_stats ─────────────────────────────────
    c.execute("PRAGMA table_info(user_stats)")
    cols = {row[1] for row in c.fetchall()}
    if "suspicion_score" not in cols:
        c.execute("ALTER TABLE user_stats ADD COLUMN suspicion_score FLOAT DEFAULT 0.0")
        print("[+] Added user_stats.suspicion_score")
    else:
        print("[=] user_stats.suspicion_score already exists")

    conn.commit()
    conn.close()
    print("\nSecurity migration complete.")


if __name__ == "__main__":
    db = sys.argv[1] if len(sys.argv) > 1 else "flow.db"
    migrate(db)
