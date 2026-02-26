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
        Transactional: user and stats created together or neither.
        """
        try:
            # Check if user already exists
            existing_user = db.query(User).filter(
                (User.email == user_data.email) | (User.username == user_data.username)
            ).first()
            
            if existing_user:
                raise UserAlreadyExistsException(
                    "User with this email or username already exists"
                )
            
            # Hash password and create user
            hashed_password: str = hash_password(user_data.password)
            new_user: User = User(
                username=user_data.username,
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
                "User with this email or username already exists"
            )
        except Exception as e:
            db.rollback()
            raise Exception(f"User registration failed: {str(e)}")
    
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
