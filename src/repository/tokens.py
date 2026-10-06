"""Blacklist of revoked access tokens."""
from datetime import datetime, timezone

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from src.database.models import BlacklistedToken


def add_to_blacklist(jti: str, expires_at: datetime, db: Session) -> None:
    """Revoke a token until it expires; expired entries are cleaned up on the way.

    :param jti: The unique id of the token.
    :param expires_at: When the token expires.
    :param db: The database session.
    """
    db.execute(delete(BlacklistedToken).where(BlacklistedToken.expires_at < datetime.now(timezone.utc)))
    if not is_blacklisted(jti, db):
        db.add(BlacklistedToken(jti=jti, expires_at=expires_at))
    db.commit()


def is_blacklisted(jti: str, db: Session) -> bool:
    """Check whether the token was revoked.

    :param jti: The unique id of the token.
    :param db: The database session.
    :return: ``True`` if the token is in the blacklist.
    """
    return db.scalar(select(BlacklistedToken.id).where(BlacklistedToken.jti == jti)) is not None
