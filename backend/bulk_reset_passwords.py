# Usage: python bulk_reset_passwords.py <new_password>
from app.db.database import SessionLocal
from app.models.user import User
from app.core.security import hash_password
import sys

def main():
    if len(sys.argv) != 2:
        print("Usage: python bulk_reset_passwords.py <new_password>")
        return
    new_password = sys.argv[1]
    db = SessionLocal()
    users = db.query(User).all()
    for user in users:
        user.hashed_password = hash_password(new_password)
        print(f"Reset password for {user.email}")
    db.commit()
    db.close()
    print("All passwords reset.")

if __name__ == "__main__":
    main()
