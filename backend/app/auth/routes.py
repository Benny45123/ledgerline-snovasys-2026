"""
How this works / why it is safe:
This module exposes the authentication API endpoints (/auth/login, /auth/logout, /auth/me).
Login queries users by email, applying throttling checks and timing-safe dummy verification
when an email is not found. Successful logins emit a 256-bit opaque token and record an audit event.
Logout immediately revokes the session hash in the database, preventing session reuse.
"""

from typing import Optional
from fastapi import APIRouter, Depends, Header, Request
from sqlalchemy.orm import Session
from app.auth.passwords import dummy_verify, verify_password
from app.auth.schemas import LoginRequest, LoginResponse, UserResponse
from app.auth.sessions import create_session, revoke_session
from app.auth.throttle import check_login_throttle, record_login_attempt
from app.db.engine import get_db
from app.db.models import User
from app.deps import get_current_user, get_request_id
from app.errors import InvalidCredentialsError

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/login", response_model=LoginResponse)
def login(
    req: LoginRequest,
    request: Request,
    request_id: str = Depends(get_request_id),
    db: Session = Depends(get_db),
) -> LoginResponse:
    """Authenticate user with email and password, creating an active session."""
    client_ip = request.client.host if request.client else None
    check_login_throttle(db, req.email, client_ip)

    user = db.query(User).filter(User.email == req.email).first()

    if not user or not user.is_active:
        dummy_verify()
        record_login_attempt(db, False, req.email, client_ip, request_id, None)
        raise InvalidCredentialsError()

    if not verify_password(user.password_hash, req.password):
        record_login_attempt(db, False, req.email, client_ip, request_id, user.id)
        raise InvalidCredentialsError()

    record_login_attempt(db, True, req.email, client_ip, request_id, user.id)
    token, expires_at = create_session(db, user)

    return LoginResponse(
        token=token,
        expires_at=expires_at,
        user=UserResponse(
            id=user.id,
            email=user.email,
            role=user.role,
            is_active=user.is_active,
            created_at=user.created_at,
        ),
    )


@router.post("/logout")
def logout(
    authorization: Optional[str] = Header(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    """Revoke caller's current session token."""
    if authorization and authorization.startswith("Bearer "):
        token = authorization[7:].strip()
        revoke_session(db, token)
    return {"status": "logged_out"}


@router.get("/me", response_model=UserResponse)
def me(current_user: User = Depends(get_current_user)) -> UserResponse:
    """Retrieve details for the currently authenticated session caller."""
    return UserResponse(
        id=current_user.id,
        email=current_user.email,
        role=current_user.role,
        is_active=current_user.is_active,
        created_at=current_user.created_at,
    )
