"""Ratings of photos."""
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.database.db import get_db
from src.database.models import User
from src.repository import ratings as repository_ratings
from src.routes.photos import get_photo_or_404
from src.schemas import RatingCreate, RatingResponse
from src.services.auth import get_current_user
from src.services.roles import allow_moderation

router = APIRouter(tags=["ratings"])


@router.post(
    "/photos/{photo_id}/ratings",
    response_model=RatingResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Rate a photo",
    description="1 to 5 stars, once per photo; you cannot rate your own photos.",
    responses={409: {"description": "Already rated"}},
)
def rate_photo(
    photo_id: int,
    body: RatingCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    photo = get_photo_or_404(photo_id, db)
    if photo.owner_id == user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You cannot rate your own photo")
    if repository_ratings.get_user_rating(photo.id, user.id, db):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="You have already rated this photo")
    try:
        return repository_ratings.create_rating(body.value, photo, user, db)
    except IntegrityError:  # two requests at the same time
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="You have already rated this photo")


@router.get(
    "/photos/{photo_id}/ratings",
    response_model=list[RatingResponse],
    summary="Ratings of a photo (moderator, admin)",
    dependencies=[Depends(allow_moderation)],
)
def list_ratings(photo_id: int, db: Session = Depends(get_db)):
    get_photo_or_404(photo_id, db)
    return repository_ratings.list_ratings(photo_id, db)


@router.delete(
    "/ratings/{rating_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a rating (moderator, admin)",
    dependencies=[Depends(allow_moderation)],
)
def delete_rating(rating_id: int, db: Session = Depends(get_db)):
    rating = repository_ratings.get_rating(rating_id, db)
    if rating is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Rating not found")
    repository_ratings.delete_rating(rating, db)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
