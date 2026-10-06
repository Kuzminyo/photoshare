"""Role based access to routes."""
from fastapi import Depends, HTTPException, status

from src.database.models import Role, User
from src.services.auth import get_current_user


class RoleAccess:
    """Dependency that lets in only users with one of the given roles.

    Usage::

        @router.delete("/{id}", dependencies=[Depends(RoleAccess([Role.admin]))])
    """

    def __init__(self, allowed_roles: list[Role]):
        self.allowed_roles = allowed_roles

    def __call__(self, user: User = Depends(get_current_user)) -> User:
        """Check the role of the current user.

        :param user: The current user.
        :return: The same user if the role is allowed.
        :raises HTTPException: 403 otherwise.
        """
        if user.role not in self.allowed_roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Operation not permitted")
        return user


allow_admin = RoleAccess([Role.admin])
allow_moderation = RoleAccess([Role.admin, Role.moderator])


def is_staff(user: User) -> bool:
    """Whether the user is a moderator or an administrator.

    :param user: The user.
    :return: ``True`` for moderators and administrators.
    """
    return user.role in (Role.admin, Role.moderator)
