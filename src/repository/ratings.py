"""Database operations with ratings."""
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.database.models import Photo, Rating, User


def get_user_rating(photo_id: int, user_id: int, db: Session) -> Rating | None:
    """The rating the user gave to the photo, if any.

    :param photo_id: The id of the photo.
    :param user_id: The id of the user.
    :param db: The database session.
    :return: The rating or ``None``.
    """
    return db.scalar(select(Rating).where(Rating.photo_id == photo_id, Rating.user_id == user_id))


def create_rating(value: int, photo: Photo, user: User, db: Session) -> Rating:
    """Rate a photo.

    :param value: 1 to 5 stars.
    :param photo: The photo.
    :param user: The user who rates.
    :param db: The database session.
    :return: The new rating.
    """
    rating = Rating(value=value, photo_id=photo.id, user_id=user.id)
    db.add(rating)
    db.commit()
    db.refresh(rating)
    return rating


def get_rating(rating_id: int, db: Session) -> Rating | None:
    """Find a rating by id.

    :param rating_id: The id of the rating.
    :param db: The database session.
    :return: The rating or ``None``.
    """
    return db.get(Rating, rating_id)


def list_ratings(photo_id: int, db: Session) -> list[Rating]:
    """All ratings of a photo, newest first.

    :param photo_id: The id of the photo.
    :param db: The database session.
    :return: The ratings.
    """
    stmt = select(Rating).where(Rating.photo_id == photo_id).order_by(Rating.created_at.desc(), Rating.id.desc())
    return list(db.scalars(stmt))


def delete_rating(rating: Rating, db: Session) -> None:
    """Delete a rating.

    :param rating: The rating.
    :param db: The database session.
    """
    db.delete(rating)
    db.commit()
