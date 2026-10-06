"""Comments under photos."""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import Response
from sqlalchemy.orm import Session

from src.database.db import get_db
from src.database.models import User
from src.repository import comments as repository_comments
from src.routes.photos import get_photo_or_404
from src.schemas import CommentCreate, CommentResponse
from src.services.auth import get_current_user
from src.services.roles import allow_moderation

router = APIRouter(tags=["comments"])


@router.post(
    "/photos/{photo_id}/comments",
    response_model=CommentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Comment a photo",
)
def create_comment(
    photo_id: int,
    body: CommentCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    photo = get_photo_or_404(photo_id, db)
    return repository_comments.create_comment(body.text, photo, user, db)


@router.get(
    "/photos/{photo_id}/comments",
    response_model=list[CommentResponse],
    summary="Comments of a photo",
    description="Oldest first.",
)
def list_comments(
    photo_id: int,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    get_photo_or_404(photo_id, db)
    return repository_comments.list_comments(photo_id, skip, limit, db)


def _get_comment_or_404(comment_id: int, db: Session):
    comment = repository_comments.get_comment(comment_id, db)
    if comment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Comment not found")
    return comment


@router.put(
    "/comments/{comment_id}",
    response_model=CommentResponse,
    summary="Edit my comment",
    description="Only the author can edit a comment; `updated_at` is refreshed.",
)
def update_comment(
    comment_id: int,
    body: CommentCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    comment = _get_comment_or_404(comment_id, db)
    if comment.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You can edit only your own comments")
    return repository_comments.update_comment(comment, body.text, db)


@router.delete(
    "/comments/{comment_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a comment (moderator, admin)",
    dependencies=[Depends(allow_moderation)],
)
def delete_comment(comment_id: int, db: Session = Depends(get_db)):
    repository_comments.delete_comment(_get_comment_or_404(comment_id, db), db)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
