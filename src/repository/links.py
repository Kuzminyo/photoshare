"""Database operations with links to transformed images."""
import secrets

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.database.models import Photo, TransformedLink


def create_link(photo: Photo, url: str, transformation: str, db: Session) -> TransformedLink:
    """Save a link to a transformed image under a new random token.

    :param photo: The original photo.
    :param url: The URL of the transformed image.
    :param transformation: Text description of the transformation.
    :param db: The database session.
    :return: The new link.
    """
    link = TransformedLink(
        token=secrets.token_urlsafe(16), url=url, transformation=transformation, photo_id=photo.id
    )
    db.add(link)
    db.commit()
    db.refresh(link)
    return link


def get_link_by_token(token: str, db: Session) -> TransformedLink | None:
    """Find a link by its token.

    :param token: The token from the URL.
    :param db: The database session.
    :return: The link or ``None``.
    """
    return db.scalar(select(TransformedLink).where(TransformedLink.token == token))


def list_links(photo_id: int, db: Session) -> list[TransformedLink]:
    """All links of a photo, newest first.

    :param photo_id: The id of the photo.
    :param db: The database session.
    :return: The links.
    """
    stmt = (
        select(TransformedLink)
        .where(TransformedLink.photo_id == photo_id)
        .order_by(TransformedLink.created_at.desc(), TransformedLink.id.desc())
    )
    return list(db.scalars(stmt))
