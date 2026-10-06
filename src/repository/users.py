"""Database operations with users."""
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from src.database.models import Comment, Photo, Role, User
from src.schemas import UserCreate


def get_user_by_id(user_id: int, db: Session) -> User | None:
    """Find a user by id.

    :param user_id: The id of the user.
    :param db: The database session.
    :return: The user or ``None``.
    """
    return db.get(User, user_id)


def get_user_by_email(email: str, db: Session) -> User | None:
    """Find a user by email (case insensitive).

    :param email: The email.
    :param db: The database session.
    :return: The user or ``None``.
    """
    return db.scalar(select(User).where(User.email == email.lower()))


def get_user_by_username(username: str, db: Session) -> User | None:
    """Find a user by username (case insensitive, so ``Alice`` and ``alice`` are one user).

    :param username: The username.
    :param db: The database session.
    :return: The user or ``None``.
    """
    return db.scalar(select(User).where(func.lower(User.username) == username.lower()))


def get_user_by_login(login: str, db: Session) -> User | None:
    """Find a user by email or username, whichever matches; case and surrounding spaces are ignored.

    :param login: The email or the username.
    :param db: The database session.
    :return: The user or ``None``.
    """
    login = login.strip().lower()
    return db.scalar(select(User).where(or_(User.email == login, func.lower(User.username) == login)))


def create_user(body: UserCreate, hashed_password: str, db: Session) -> User:
    """Create a user; the very first user of the system becomes an administrator.

    :param body: The sign up data.
    :param hashed_password: The bcrypt hash of the password.
    :param db: The database session.
    :return: The new user.
    """
    is_first = db.scalar(select(func.count(User.id))) == 0
    user = User(
        username=body.username,
        email=body.email.lower(),
        password=hashed_password,
        role=Role.admin if is_first else Role.user,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def update_user(user: User, fields: dict, db: Session) -> User:
    """Set the given fields of a user.

    :param user: The user to change.
    :param fields: Field names and new values.
    :param db: The database session.
    :return: The updated user.
    """
    for name, value in fields.items():
        setattr(user, name, value)
    db.commit()
    db.refresh(user)
    return user


def list_users(skip: int, limit: int, db: Session) -> list[User]:
    """All users ordered by id.

    :param skip: How many users to skip.
    :param limit: Maximum number of users.
    :param db: The database session.
    :return: The users.
    """
    return list(db.scalars(select(User).order_by(User.id).offset(skip).limit(limit)))


def get_profile_counts(user: User, db: Session) -> tuple[int, int]:
    """Number of photos and comments of the user.

    :param user: The user.
    :param db: The database session.
    :return: ``(photos_count, comments_count)``.
    """
    photos = db.scalar(select(func.count(Photo.id)).where(Photo.owner_id == user.id))
    comments = db.scalar(select(func.count(Comment.id)).where(Comment.user_id == user.id))
    return photos, comments
