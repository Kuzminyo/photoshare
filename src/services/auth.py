"""Passwords, JWT tokens and the authentication dependencies.

Access and refresh tokens are told apart by the ``scope`` claim, and the
subject (``sub``) is the user id, so a token survives a change of email or
username. Every token has a unique ``jti`` that logout puts into the blacklist.
"""
import uuid
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer, OAuth2PasswordBearer
from sqlalchemy.orm import Session

from src.conf.config import settings
from src.database.db import get_db
from src.database.models import User
from src.repository import tokens as repository_tokens
from src.repository import users as repository_users

ACCESS_SCOPE = "access_token"
REFRESH_SCOPE = "refresh_token"

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")
refresh_scheme = HTTPBearer(auto_error=False)


def _unauthorized(detail: str = "Could not validate credentials") -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


# ---------- passwords ----------

def hash_password(password: str) -> str:
    """Hash a password with bcrypt (only the first 72 bytes are used by bcrypt).

    :param password: The plain password.
    :return: The bcrypt hash.
    """
    return bcrypt.hashpw(password.encode("utf-8")[:72], bcrypt.gensalt()).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Check a password against its bcrypt hash.

    :param plain_password: The password entered by the user.
    :param hashed_password: The stored hash.
    :return: ``True`` if the password matches.
    """
    return bcrypt.checkpw(plain_password.encode("utf-8")[:72], hashed_password.encode("utf-8"))


# compared against when the login is unknown, to keep the response time the same
DUMMY_HASH = hash_password("dummy-password-for-timing")


# ---------- tokens ----------

def _create_token(user_id: int, scope: str, expires_delta: timedelta) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "scope": scope,
        "jti": uuid.uuid4().hex,
        "iat": now,
        "exp": now + expires_delta,
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def create_access_token(user_id: int) -> str:
    """Create a short-lived access token.

    :param user_id: The id of the user.
    :return: The encoded token.
    """
    return _create_token(user_id, ACCESS_SCOPE, timedelta(minutes=settings.access_token_expire_minutes))


def create_refresh_token(user_id: int) -> str:
    """Create a long-lived refresh token.

    :param user_id: The id of the user.
    :return: The encoded token.
    """
    return _create_token(user_id, REFRESH_SCOPE, timedelta(days=settings.refresh_token_expire_days))


def decode_token(token: str, expected_scope: str) -> dict:
    """Return the payload of a valid token of the expected scope, else raise 401.

    :param token: The encoded token.
    :param expected_scope: The scope the token must have.
    :return: The decoded payload.
    :raises HTTPException: 401 if the token is invalid, expired or of another scope.
    """
    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
    except jwt.ExpiredSignatureError:
        raise _unauthorized("Token has expired")
    except jwt.PyJWTError:
        raise _unauthorized()
    if payload.get("scope") != expected_scope or not str(payload.get("sub", "")).isdigit() or not payload.get("jti"):
        raise _unauthorized()
    return payload


def user_from_payload(payload: dict, db: Session) -> User:
    """Load the active user the token belongs to, rejecting revoked tokens.

    :param payload: A decoded token.
    :param db: The database session.
    :return: The user.
    :raises HTTPException: 401 if the token is revoked or the user is missing,
        403 if the user is banned.
    """
    if repository_tokens.is_blacklisted(payload["jti"], db):
        raise _unauthorized("Token has been revoked")
    user = repository_users.get_user_by_id(int(payload["sub"]), db)
    if user is None:
        raise _unauthorized()
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User is banned")
    return user


# ---------- dependencies ----------

def get_token_payload(token: str = Depends(oauth2_scheme)) -> dict:
    """Decoded access token from the ``Authorization`` header.

    :param token: The raw access token.
    :return: The payload.
    """
    return decode_token(token, ACCESS_SCOPE)


def get_current_user(payload: dict = Depends(get_token_payload), db: Session = Depends(get_db)) -> User:
    """The authenticated, active user.

    :param payload: The decoded access token.
    :param db: The database session.
    :return: The user.
    """
    return user_from_payload(payload, db)


def get_refresh_token(credentials: HTTPAuthorizationCredentials | None = Depends(refresh_scheme)) -> str:
    """Take the raw refresh token from the ``Authorization: Bearer`` header.

    :param credentials: The parsed header, ``None`` if it is missing.
    :return: The token, not yet validated.
    :raises HTTPException: 401 if the header is missing.
    """
    if credentials is None:
        raise _unauthorized("Not authenticated")
    return credentials.credentials
