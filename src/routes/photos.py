"""Photos: upload, search, edit, delete and transformations."""
import io
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from fastapi.responses import RedirectResponse, Response
from sqlalchemy.orm import Session

from src.conf.config import settings
from src.database.db import get_db
from src.database.models import Photo, Role, User
from src.repository import links as repository_links
from src.repository import photos as repository_photos
from src.repository import tags as repository_tags
from src.repository import users as repository_users
from src.schemas import PhotoPage, PhotoResponse, PhotoUpdate, TransformationRequest, TransformedLinkResponse
from src.services import cloud, presenters, qr
from src.services.auth import get_current_user
from src.services.roles import is_staff

router = APIRouter(prefix="/photos", tags=["photos"])
links_router = APIRouter(prefix="/links", tags=["links"])

ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png", "image/gif", "image/webp", "image/bmp", "image/tiff"}


def get_photo_or_404(photo_id: int, db: Session) -> Photo:
    """Load a photo or raise 404.

    :param photo_id: The id of the photo.
    :param db: The database session.
    :return: The photo.
    :raises HTTPException: 404 if there is no such photo.
    """
    photo = repository_photos.get_photo(photo_id, db)
    if photo is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Photo not found")
    return photo


def check_owner_or_admin(photo: Photo, user: User) -> None:
    """Only the owner of the photo or an administrator may change it.

    :param photo: The photo.
    :param user: The current user.
    :raises HTTPException: 403 otherwise.
    """
    if photo.owner_id != user.id and user.role != Role.admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Operation not permitted")


def prepare_tags(raw: list[str] | None) -> list[str]:
    """Split comma separated values, normalize and check the limit of tags.

    Swagger sends a list, other clients often send ``"cat, dog"``; both work.

    :param raw: Tags as received.
    :return: Clean unique tag names.
    :raises HTTPException: 422 if there are too many tags or a tag is too long.
    """
    parts = [part for item in raw or [] for part in item.split(",")]
    names = repository_tags.normalize_tags(parts)
    if len(names) > settings.max_tags_per_photo:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"A photo can have at most {settings.max_tags_per_photo} tags",
        )
    if any(len(name) > 50 for name in names):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="A tag can be at most 50 characters")
    return names


@router.post(
    "",
    response_model=PhotoResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload a photo",
    description="Multipart form: the image, an optional description and up to 5 optional tags. "
    "Unknown tags are created, existing ones are reused.",
    responses={
        413: {"description": "The file is too large"},
        415: {"description": "The file is not an image"},
        503: {"description": "Cloudinary is not configured or unavailable"},
    },
)
def upload_photo(
    file: UploadFile = File(..., description="Image file"),
    description: str | None = Form(None, max_length=1000),
    tags: list[str] | None = Form(None, description="Up to 5 tags"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    names = prepare_tags(tags)
    if file.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail="Only images can be uploaded")
    max_bytes = settings.max_upload_size_mb * 1024 * 1024
    data = file.file.read(max_bytes + 1)
    if len(data) > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail=f"The file is larger than {settings.max_upload_size_mb} MB",
        )
    if not data:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="The file is empty")
    if not cloud.is_configured():
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Photo storage is not configured")
    try:
        url, public_id = cloud.upload_photo(io.BytesIO(data), user.id)
    except Exception:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Could not upload the photo")
    tag_objects = repository_tags.get_or_create_tags(names, db)
    photo = repository_photos.create_photo(url, public_id, description or None, tag_objects, user, db)
    return presenters.photo_to_response(photo, db)


@router.get(
    "",
    response_model=PhotoPage,
    summary="Search photos",
    description="Search by keyword (in the description and tags) or by tag, then filter and sort by rating or date. "
    "Filtering by the author (`username`) is available to moderators and administrators only.",
)
def search_photos(
    keyword: str | None = Query(None, max_length=100),
    tag: str | None = Query(None, max_length=50),
    username: str | None = Query(None, description="Author of the photos (moderators and admins)"),
    min_rating: float | None = Query(None, ge=0, le=5),
    date_from: datetime | None = Query(None),
    date_to: datetime | None = Query(None),
    sort_by: Literal["date", "rating"] = Query("date"),
    order: Literal["asc", "desc"] = Query("desc"),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    owner_id = None
    if username is not None:
        if not is_staff(user):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only moderators and administrators can filter by user",
            )
        owner = repository_users.get_user_by_username(username, db)
        if owner is None:
            return PhotoPage(items=[], total=0, skip=skip, limit=limit)
        owner_id = owner.id
    photos, total = repository_photos.search_photos(
        db,
        keyword=keyword,
        tag=tag,
        owner_id=owner_id,
        min_rating=min_rating,
        date_from=date_from,
        date_to=date_to,
        sort_by=sort_by,
        order=order,
        skip=skip,
        limit=limit,
    )
    return PhotoPage(items=presenters.photos_to_response(photos, db), total=total, skip=skip, limit=limit)


@router.get("/{photo_id}", response_model=PhotoResponse, summary="Get a photo")
def read_photo(photo_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return presenters.photo_to_response(get_photo_or_404(photo_id, db), db)


@router.put(
    "/{photo_id}",
    response_model=PhotoResponse,
    summary="Edit the description of a photo",
    description="Owner or administrator. If `tags` is given it replaces all tags of the photo.",
)
def update_photo(
    photo_id: int,
    body: PhotoUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    photo = get_photo_or_404(photo_id, db)
    check_owner_or_admin(photo, user)
    tag_objects = None
    if body.tags is not None:
        tag_objects = repository_tags.get_or_create_tags(prepare_tags(body.tags), db)
    photo = repository_photos.update_photo(photo, body.description or None, tag_objects, db)
    return presenters.photo_to_response(photo, db)


@router.delete(
    "/{photo_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a photo",
    description="Owner or administrator. Comments, ratings and links of the photo are deleted too.",
)
def delete_photo(photo_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    photo = get_photo_or_404(photo_id, db)
    check_owner_or_admin(photo, user)
    public_id = photo.public_id
    repository_photos.delete_photo(photo, db)
    cloud.delete_photo(public_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/{photo_id}/transform",
    response_model=TransformedLinkResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a link to a transformed photo",
    description="Owner or administrator. Applies Cloudinary transformations (resize, crop, effects, "
    "rotation, rounded corners, format) and saves the link; the response also has the URL of its QR code.",
)
def transform_photo(
    photo_id: int,
    body: TransformationRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    photo = get_photo_or_404(photo_id, db)
    check_owner_or_admin(photo, user)
    options = body.model_dump(exclude_none=True)
    url = cloud.build_transformed_url(photo.public_id, options)
    link = repository_links.create_link(photo, url, cloud.describe(options), db)
    return presenters.link_to_response(link)


@router.get(
    "/{photo_id}/links",
    response_model=list[TransformedLinkResponse],
    summary="Saved links to transformed versions of a photo",
    description="Owner or administrator.",
)
def list_links(photo_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    photo = get_photo_or_404(photo_id, db)
    check_owner_or_admin(photo, user)
    return [presenters.link_to_response(link) for link in repository_links.list_links(photo.id, db)]


def _get_link_or_404(token: str, db: Session):
    link = repository_links.get_link_by_token(token, db)
    if link is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Link not found")
    return link


@links_router.get(
    "/{token}",
    summary="Open a transformed photo",
    description="Public. Redirects to the transformed image.",
    response_class=RedirectResponse,
    status_code=status.HTTP_307_TEMPORARY_REDIRECT,
)
def open_link(token: str, db: Session = Depends(get_db)):
    return RedirectResponse(_get_link_or_404(token, db).url)


@links_router.get(
    "/{token}/qr",
    summary="QR code of a transformed photo",
    description="Public PNG image. Scan it with a phone to open the transformed photo.",
    response_class=Response,
    responses={200: {"content": {"image/png": {}}}},
)
def link_qr(token: str, db: Session = Depends(get_db)):
    link = _get_link_or_404(token, db)
    return Response(content=qr.make_qr_png(link.url), media_type="image/png")
