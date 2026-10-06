"""Database operations with comments."""
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.database.models import Comment, Photo, User


def create_comment(text: str, photo: Photo, user: User, db: Session) -> Comment:
    """Add a comment under a photo.

    :param text: The text.
    :param photo: The photo.
    :param user: The author.
    :param db: The database session.
    :return: The new comment.
    """
    comment = Comment(text=text, photo_id=photo.id, user_id=user.id)
    db.add(comment)
    db.commit()
    db.refresh(comment)
    return comment


def get_comment(comment_id: int, db: Session) -> Comment | None:
    """Find a comment by id.

    :param comment_id: The id of the comment.
    :param db: The database session.
    :return: The comment or ``None``.
    """
    return db.get(Comment, comment_id)


def list_comments(photo_id: int, skip: int, limit: int, db: Session) -> list[Comment]:
    """Comments of a photo, oldest first.

    :param photo_id: The id of the photo.
    :param skip: How many comments to skip.
    :param limit: Maximum number of comments.
    :param db: The database session.
    :return: The comments.
    """
    stmt = (
        select(Comment)
        .where(Comment.photo_id == photo_id)
        .order_by(Comment.created_at, Comment.id)
        .offset(skip)
        .limit(limit)
    )
    return list(db.scalars(stmt))


def update_comment(comment: Comment, text: str, db: Session) -> Comment:
    """Change the text of a comment; ``updated_at`` is set by the database.

    :param comment: The comment.
    :param text: The new text.
    :param db: The database session.
    :return: The updated comment.
    """
    comment.text = text
    db.commit()
    db.refresh(comment)
    return comment


def delete_comment(comment: Comment, db: Session) -> None:
    """Delete a comment.

    :param comment: The comment.
    :param db: The database session.
    """
    db.delete(comment)
    db.commit()
