"""Database operations with tags."""
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.database.models import Tag


def normalize_tags(names: list[str]) -> list[str]:
    """Strip, lowercase and deduplicate tag names keeping their order; drop empty ones.

    A leading ``#`` is removed, so ``#Cats`` and ``cats`` are the same tag.

    :param names: Raw tag names.
    :return: Clean unique names.
    """
    result = []
    for name in names:
        clean = name.strip().lstrip("#").strip().lower()
        if clean and clean not in result:
            result.append(clean)
    return result


def get_or_create_tags(names: list[str], db: Session) -> list[Tag]:
    """Return the tags with these names, creating the missing ones.

    :param names: Normalized tag names.
    :param db: The database session.
    :return: The tags in the order of ``names``.
    """
    if not names:
        return []
    existing = {tag.name: tag for tag in db.scalars(select(Tag).where(Tag.name.in_(names)))}
    tags = []
    for name in names:
        tag = existing.get(name)
        if tag is None:
            tag = Tag(name=name)
            db.add(tag)
        tags.append(tag)
    return tags
