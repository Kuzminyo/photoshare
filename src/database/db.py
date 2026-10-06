"""Database engine and session factory."""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.conf.config import settings

engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    """FastAPI dependency that yields a database session and closes it afterwards.

    :return: A generator yielding one session per request.
    :rtype: Iterator[Session]
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
