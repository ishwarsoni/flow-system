from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.models.user import User
from app.models.user_stats import UserStats
from app.schemas.user import UserRegisterRequest, UserLoginRequest
from app.core.security import hash_password, verify_password
from app.core.exceptions import (
    UserAlreadyExistsException,
    InvalidCredentialsException,
    InactiveUserException,
    UserNotFoundException,
)
from app.models.rank import (
    Rank,
    StartingDifficulty,
    STARTING_DIFFICULTY_LEVELS,
    get_rank_for_level,
    get_title_for_level,
)


class UserService:
    """Business logic for user operations"""
    
    @staticmethod
    def register_user(db: Session, user_data: UserRegisterRequest) -> User:
        """
        Register a new user and auto-create progression stats.
        Username is auto-generated from email (user never picks it).
        Transactional: user and stats created together or neither.
        """
        try:
            # Auto-generate username from email prefix
            # e.g. "ishwar@gmail.com" → "ishwar", with numeric suffix if taken
            import re as _re
            email_prefix = user_data.email.split("@")[0]
            # Keep only alphanumeric and underscores
            base_username = _re.sub(r"[^a-zA-Z0-9_]", "", email_prefix)[:40] or "hunter"

            # Ensure uniqueness
            username = base_username
            counter = 1
            while db.query(User).filter(User.username == username).first():
                username = f"{base_username}_{counter}"
                counter += 1

            # Check if email already exists
            existing_user = db.query(User).filter(User.email == user_data.email).first()
            if existing_user:
                raise UserAlreadyExistsException(
                    "An account with this email already exists"
                )
            
            # Hash password and create user
            hashed_password: str = hash_password(user_data.password)
            new_user: User = User(
                username=username,
                email=user_data.email,
                hashed_password=hashed_password,
                hunter_name=getattr(user_data, 'hunter_name', 'Hunter') or 'Hunter',
                starting_difficulty=user_data.starting_difficulty,
            )
            
            db.add(new_user)
            db.flush()  # Flush to get user ID without committing
            
            # Resolve starting level, rank, and title from chosen difficulty
            sd = StartingDifficulty(user_data.starting_difficulty)
            start_level = STARTING_DIFFICULTY_LEVELS[sd]
            start_rank  = get_rank_for_level(start_level)
            start_title = get_title_for_level(start_level)

            # Auto-create RPG player profile for new user
            user_stats = UserStats(
                user_id=new_user.id,
                level=start_level,
                xp_current=0,
                xp_total_earned=0,
                rank=start_rank,
                hp_current=100,
                hp_max=100,
                mp_current=50,
                mp_max=50,
                strength=10.0,
                intelligence=10.0,
                vitality=10.0,
                charisma=10.0,
                mana=10.0,
                coins=0,
                skill_points=0,
                reputation=0,
                current_title=start_title,
                fatigue=0.0,
                streak_days=0,
                longest_streak=0,
                punishment_active=0,
            )
            db.add(user_stats)
            db.commit()
            db.refresh(new_user)
            
            return new_user
        
        except UserAlreadyExistsException:
            db.rollback()
            raise
        except IntegrityError:
            db.rollback()
            raise UserAlreadyExistsException(
                "An account with this email already exists"
            )
        except Exception as e:
            db.rollback()
            # SECURITY: never expose internal exception details to caller
            import logging
            logging.getLogger(__name__).exception("User registration failed")
            raise Exception("User registration failed. Please try again.")
    
    @staticmethod
    def get_user_by_email(db: Session, email: str) -> User | None:
        """Get user by email"""
        return db.query(User).filter(User.email == email).first()
    
    @staticmethod
    def get_user_by_id(db: Session, user_id: int) -> User | None:
        """Get user by ID"""
        return db.query(User).filter(User.id == user_id).first()
    
    @staticmethod
    def authenticate_user(db: Session, login_data: UserLoginRequest) -> User:
        """Authenticate user with email and password"""
        user: User | None = UserService.get_user_by_email(db, login_data.email)
        
        if not user:
            raise InvalidCredentialsException()
        
        if not verify_password(login_data.password, user.hashed_password):
            raise InvalidCredentialsException()
        
        if not user.is_active:
            raise InactiveUserException()
        
        return user
