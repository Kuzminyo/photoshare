"""Sign up, login, token refresh and logout."""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.database.db import get_db
from src.repository import tokens as repository_tokens
from src.repository import users as repository_users
from src.schemas import Message, TokenPair, UserCreate, UserMe
from src.services import auth as auth_service

router = APIRouter(prefix="/auth", tags=["auth"])

class LogoutRequest(BaseModel):
    """Optional refresh token to revoke together with the access token."""

    refresh_token: str | None = None


def _issue_tokens(user_id: int) -> TokenPair:
    return TokenPair(
        access_token=auth_service.create_access_token(user_id),
        refresh_token=auth_service.create_refresh_token(user_id),
    )


def _revoke(payload: dict, db: Session) -> None:
    expires_at = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
    repository_tokens.add_to_blacklist(payload["jti"], expires_at, db)


@router.post(
    "/signup",
    response_model=UserMe,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user",
    description="The first registered user of the system becomes an administrator.",
    responses={409: {"description": "Email or username is already taken"}},
)
def signup(body: UserCreate, db: Session = Depends(get_db)):
    if repository_users.get_user_by_email(body.email, db):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Account with this email already exists")
    if repository_users.get_user_by_username(body.username, db):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Username is already taken")
    return repository_users.create_user(body, auth_service.hash_password(body.password), db)


@router.post(
    "/login",
    response_model=TokenPair,
    summary="Log in with email or username",
    description="OAuth2 form: put the email **or** the username into the `username` field.",
    responses={401: {"description": "Wrong credentials"}, 403: {"description": "User is banned"}},
)
def login(form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = repository_users.get_user_by_login(form.username, db)
    hashed = user.password if user else auth_service.DUMMY_HASH
    password_ok = auth_service.verify_password(form.password, hashed)
    if user is None or not password_ok:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid login or password")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User is banned")
    return _issue_tokens(user.id)


@router.get(
    "/refresh_token",
    response_model=TokenPair,
    summary="Get a new pair of tokens",
    description="Send the refresh token as `Authorization: Bearer <refresh_token>`. "
    "The used refresh token is revoked (rotation).",
)
def refresh_token(token: str = Depends(auth_service.get_refresh_token), db: Session = Depends(get_db)):
    payload = auth_service.decode_token(token, auth_service.REFRESH_SCOPE)
    user = auth_service.user_from_payload(payload, db)
    _revoke(payload, db)
    return _issue_tokens(user.id)


@router.post(
    "/logout",
    response_model=Message,
    summary="Log out",
    description="Puts the access token (and the refresh token, if sent) into the blacklist until they expire.",
)
def logout(
    body: LogoutRequest | None = None,
    payload: dict = Depends(auth_service.get_token_payload),
    db: Session = Depends(get_db),
):
    auth_service.user_from_payload(payload, db)
    _revoke(payload, db)
    if body and body.refresh_token:
        try:
            refresh_payload = auth_service.decode_token(body.refresh_token, auth_service.REFRESH_SCOPE)
        except HTTPException:
            pass  # an invalid or expired refresh token is useless anyway
        else:
            if refresh_payload["sub"] == payload["sub"]:
                _revoke(refresh_payload, db)
    return Message(message="Successfully logged out")
