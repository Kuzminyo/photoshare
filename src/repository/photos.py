"""Database operations with photos, their search and statistics."""
from datetime import datetime
from typing import Literal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.database.models import Comment, Photo, Rating, Tag, User


def create_photo(
    url: str, public_id: str, description: str | None, tags: list[Tag], owner: User, db: Session
) -> Photo:
    """Save an uploaded photo.

    :param url: The Cloudinary URL.
    :param public_id: The Cloudinary public id.
    :param description: The description.
    :param tags: Tags of the photo.
    :param owner: The user who uploaded it.
    :param db: The database session.
    :return: The new photo.
    """
    photo = Photo(url=url, public_id=public_id, description=description, owner_id=owner.id, tags=tags)
    db.add(photo)
    db.commit()
    db.refresh(photo)
    return photo


def get_photo(photo_id: int, db: Session) -> Photo | None:
    """Find a photo by id.

    :param photo_id: The id of the photo.
    :param db: The database session.
    :return: The photo or ``None``.
    """
    return db.get(Photo, photo_id)


def update_photo(photo: Photo, description: str | None, tags: list[Tag] | None, db: Session) -> Photo:
    """Change the description and, if ``tags`` is not ``None``, replace the tags.

    :param photo: The photo.
    :param description: The new description.
    :param tags: The new tags or ``None`` to keep the current ones.
    :param db: The database session.
    :return: The updated photo.
    """
    photo.description = description
    if tags is not None:
        photo.tags = tags
    db.commit()
    db.refresh(photo)
    return photo


def delete_photo(photo: Photo, db: Session) -> None:
    """Delete a photo with its comments, ratings and links.

    :param photo: The photo.
    :param db: The database session.
    """
    db.delete(photo)
    db.commit()


def search_photos(
    db: Session,
    keyword: str | None = None,
    tag: str | None = None,
    owner_id: int | None = None,
    min_rating: float | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    sort_by: Literal["date", "rating"] = "date",
    order: Literal["asc", "desc"] = "desc",
    skip: int = 0,
    limit: int = 20,
) -> tuple[list[Photo], int]:
    """Search photos by keyword or tag, filter and sort them.

    The keyword is looked for in the description and in the tag names.

    :param db: The database session.
    :param keyword: Text to search for.
    :param tag: Exact tag name.
    :param owner_id: Only photos of this user.
    :param min_rating: Only photos with an average rating at least this.
    :param date_from: Only photos uploaded at or after this time.
    :param date_to: Only photos uploaded at or before this time.
    :param sort_by: ``date`` (upload time) or ``rating`` (average rating).
    :param order: ``asc`` or ``desc``.
    :param skip: How many photos to skip.
    :param limit: Maximum number of photos.
    :return: The page of photos and the total number of matches.
    """
    ratings = (
        select(Rating.photo_id, func.avg(Rating.value).label("avg"))
        .group_by(Rating.photo_id)
        .subquery()
    )
    avg_rating = func.coalesce(ratings.c.avg, 0)
    stmt = select(Photo).outerjoin(ratings, ratings.c.photo_id == Photo.id)

    if keyword:
        stmt = stmt.where(
            Photo.description.icontains(keyword, autoescape=True)
            | Photo.tags.any(Tag.name.icontains(keyword, autoescape=True))
        )
    if tag:
        stmt = stmt.where(Photo.tags.any(Tag.name == tag.strip().lstrip("#").lower()))
    if owner_id is not None:
        stmt = stmt.where(Photo.owner_id == owner_id)
    if min_rating is not None:
        stmt = stmt.where(avg_rating >= min_rating)
    if date_from is not None:
        stmt = stmt.where(Photo.created_at >= date_from)
    if date_to is not None:
        stmt = stmt.where(Photo.created_at <= date_to)

    total = db.scalar(select(func.count()).select_from(stmt.subquery()))

    key = avg_rating if sort_by == "rating" else Photo.created_at
    if order == "asc":
        stmt = stmt.order_by(key.asc(), Photo.id.asc())
    else:
        stmt = stmt.order_by(key.desc(), Photo.id.desc())
    photos = list(db.scalars(stmt.offset(skip).limit(limit)))
    return photos, total


def get_stats(photo_ids: list[int], db: Session) -> dict[int, tuple[float | None, int, int]]:
    """Average rating, number of ratings and number of comments for each photo.

    :param photo_ids: Ids of the photos.
    :param db: The database session.
    :return: ``{photo_id: (avg_rating, ratings_count, comments_count)}``.
    """
    stats = {pid: (None, 0, 0) for pid in photo_ids}
    if not photo_ids:
        return stats
    rating_rows = db.execute(
        select(Rating.photo_id, func.avg(Rating.value), func.count(Rating.id))
        .where(Rating.photo_id.in_(photo_ids))
        .group_by(Rating.photo_id)
    )
    for pid, avg, count in rating_rows:
        stats[pid] = (round(float(avg), 2), count, 0)
    comment_rows = db.execute(
        select(Comment.photo_id, func.count(Comment.id))
        .where(Comment.photo_id.in_(photo_ids))
        .group_by(Comment.photo_id)
    )
    for pid, count in comment_rows:
        avg, ratings_count, _ = stats[pid]
        stats[pid] = (avg, ratings_count, count)
    return stats
