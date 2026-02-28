# Usage: python reset_user_password.py <email> <new_password>
from app.db.database import SessionLocal
from app.models.user import User
from app.core.security import hash_password
import sys

def main():
    if len(sys.argv) != 3:
        print("Usage: python reset_user_password.py <email> <new_password>")
        return
    email, new_password = sys.argv[1], sys.argv[2]
    db = SessionLocal()
    user = db.query(User).filter(User.email == email).first()
    if not user:
        print(f"User not found: {email}")
        return
    user.hashed_password = hash_password(new_password)
    db.commit()
    print(f"Password reset for {email}")
    db.close()

if __name__ == "__main__":
    main()
