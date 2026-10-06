"""Building API responses from ORM objects."""
from sqlalchemy.orm import Session

from src.conf.config import settings
from src.database.models import Photo, TransformedLink
from src.repository import photos as repository_photos
from src.schemas import OwnerShort, PhotoResponse, TransformedLinkResponse


def photos_to_response(photos: list[Photo], db: Session) -> list[PhotoResponse]:
    """Photos with their tags, average rating and counters (one query for all stats).

    :param photos: The photos.
    :param db: The database session.
    :return: The response items in the same order.
    """
    stats = repository_photos.get_stats([p.id for p in photos], db)
    result = []
    for photo in photos:
        rating, ratings_count, comments_count = stats[photo.id]
        result.append(
            PhotoResponse(
                id=photo.id,
                url=photo.url,
                description=photo.description,
                owner=OwnerShort.model_validate(photo.owner),
                tags=[tag.name for tag in photo.tags],
                rating=rating,
                ratings_count=ratings_count,
                comments_count=comments_count,
                created_at=photo.created_at,
                updated_at=photo.updated_at,
            )
        )
    return result


def photo_to_response(photo: Photo, db: Session) -> PhotoResponse:
    """One photo as an API response.

    :param photo: The photo.
    :param db: The database session.
    :return: The response.
    """
    return photos_to_response([photo], db)[0]


def link_to_response(link: TransformedLink) -> TransformedLinkResponse:
    """A transformed link with the absolute URL of its QR code.

    :param link: The link.
    :return: The response.
    """
    return TransformedLinkResponse(
        id=link.id,
        photo_id=link.photo_id,
        url=link.url,
        transformation=link.transformation,
        qr_code_url=f"{settings.base_url.rstrip('/')}/api/links/{link.token}/qr",
        created_at=link.created_at,
    )
