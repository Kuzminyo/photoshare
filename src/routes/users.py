"""Own account, public profiles and user administration."""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from src.database.db import get_db
from src.database.models import User
from src.repository import users as repository_users
from src.schemas import RoleUpdate, UserAdminView, UserMe, UserProfile, UserUpdate
from src.services import auth as auth_service
from src.services.roles import allow_admin

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=UserMe, summary="My account")
def read_me(user: User = Depends(auth_service.get_current_user)):
    return user


@router.patch(
    "/me",
    response_model=UserMe,
    summary="Edit my account",
    description="Only the given fields are changed.",
    responses={409: {"description": "Email or username is already taken"}},
)
def update_me(
    body: UserUpdate,
    user: User = Depends(auth_service.get_current_user),
    db: Session = Depends(get_db),
):
    fields = body.model_dump(exclude_unset=True, exclude_none=True)
    if "username" in fields:
        other = repository_users.get_user_by_username(fields["username"], db)
        if other is not None and other.id != user.id:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Username is already taken")
    if "email" in fields:
        fields["email"] = fields["email"].lower()
        other = repository_users.get_user_by_email(fields["email"], db)
        if other is not None and other.id != user.id:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Account with this email already exists")
    if "password" in fields:
        fields["password"] = auth_service.hash_password(fields["password"])
    return repository_users.update_user(user, fields, db)


@router.get(
    "",
    response_model=list[UserAdminView],
    summary="List all users (admin)",
    dependencies=[Depends(allow_admin)],
)
def list_users(skip: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=200), db: Session = Depends(get_db)):
    return repository_users.list_users(skip, limit, db)


@router.get(
    "/{username}",
    response_model=UserProfile,
    summary="Public profile",
    description="Public information about a user: name, registration date, number of photos and comments.",
)
def read_profile(username: str, db: Session = Depends(get_db)):
    user = repository_users.get_user_by_username(username, db)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    photos_count, comments_count = repository_users.get_profile_counts(user, db)
    return UserProfile(
        id=user.id,
        username=user.username,
        full_name=user.full_name,
        bio=user.bio,
        role=user.role,
        created_at=user.created_at,
        photos_count=photos_count,
        comments_count=comments_count,
    )


def _get_other_user(user_id: int, admin: User, db: Session) -> User:
    if user_id == admin.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="You cannot change your own account here")
    user = repository_users.get_user_by_id(user_id, db)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user


@router.patch("/{user_id}/ban", response_model=UserAdminView, summary="Ban a user (admin)")
def ban_user(user_id: int, admin: User = Depends(allow_admin), db: Session = Depends(get_db)):
    user = _get_other_user(user_id, admin, db)
    return repository_users.update_user(user, {"is_active": False}, db)


@router.patch("/{user_id}/unban", response_model=UserAdminView, summary="Unban a user (admin)")
def unban_user(user_id: int, admin: User = Depends(allow_admin), db: Session = Depends(get_db)):
    user = _get_other_user(user_id, admin, db)
    return repository_users.update_user(user, {"is_active": True}, db)


@router.patch("/{user_id}/role", response_model=UserAdminView, summary="Change the role of a user (admin)")
def change_role(user_id: int, body: RoleUpdate, admin: User = Depends(allow_admin), db: Session = Depends(get_db)):
    user = _get_other_user(user_id, admin, db)
    return repository_users.update_user(user, {"role": body.role}, db)
