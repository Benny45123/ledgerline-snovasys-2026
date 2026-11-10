"""
How this works / why it is safe:
This module provides FastAPI dependency injection guards for request context,
session authentication, and role-based access control (RBAC).
Every incoming request receives or generates a unique request_id.
Authentication validates bearer tokens against active, unrevoked DB sessions.
Role guards (require_role) strictly reject unauthorized callers with 403 Forbidden
before endpoint logic executes, ensuring the principle of least privilege.
"""

import uuid
from collections.abc import Callable

from fastapi import Depends, Header
from sqlalchemy.orm import Session

from app.auth.sessions import get_user_from_token
from app.db.engine import get_db
from app.db.models import User
from app.errors import ForbiddenError, UnauthorizedError


def get_request_id(x_request_id: str | None = Header(None)) -> str:
    """Extract client request ID or generate a fresh UUID hex string."""
    if x_request_id and 8 <= len(x_request_id) <= 64:
        return x_request_id
    return uuid.uuid4().hex


def get_current_user(
    authorization: str | None = Header(None),
    db: Session = Depends(get_db),
) -> User:
    """Validate bearer token from Authorization header and return active user."""
    if not authorization or not authorization.startswith("Bearer "):
        raise UnauthorizedError(message="Missing or malformed Authorization header.")

    token = authorization[7:].strip()
    if not token:
        raise UnauthorizedError(message="Empty bearer token provided.")

    user = get_user_from_token(db, token)
    if not user:
        raise UnauthorizedError(message="Invalid, expired, or revoked session.")

    return user


def require_role(*allowed_roles: str) -> Callable[[User], User]:
    """Factory creating an endpoint dependency that asserts caller holds an allowed role."""

    def role_checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in allowed_roles:
            raise ForbiddenError(message=f"Access denied. Requires one of roles: {', '.join(allowed_roles)}")
        return current_user

    return role_checker
