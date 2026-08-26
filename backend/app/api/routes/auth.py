"""
MedGraphRAG Backend — Authentication Routes
===========================================
POST /auth/login  — Sha256 authentication against demo users -> JWT token
POST /auth/guest  — Creates ephemeral guest session (guest_<uuid>)
GET  /auth/me     — Session restore endpoint returning token claims
POST /auth/logout — Purges guest private_store directory on logout
"""

from __future__ import annotations

import hashlib
import logging
import uuid
from typing import Any, Dict, Optional

from fastapi import APIRouter, Body, Depends, Form, HTTPException, Request, status
from pydantic import BaseModel, Field

from app.api.deps import create_access_token, get_current_user, purge_guest_user_dir
from app.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Authentication"])


class LoginRequest(BaseModel):
    username: Optional[str] = Field(None, description="Username")
    password: Optional[str] = Field(None, description="Password")


class TokenResponse(BaseModel):
    token: str = Field(..., description="JWT Bearer token")
    token_type: str = "bearer"
    user_id: str = Field(..., description="Authenticated user ID")
    ephemeral: bool = False


from app.core.auth.passwords import (
    LoginThrottler,
    get_dev_hint_credentials,
    get_user_credential_store,
    verify_password,
)


@router.post("/auth/login", response_model=TokenResponse)
@router.post("/api/v1/auth/login", response_model=TokenResponse)
async def login(
    request: Request,
    body: Optional[LoginRequest] = Body(None),
) -> TokenResponse:
    """Authenticate user with salted scrypt/argon2 verification and per-IP/account throttling."""
    username = ""
    password = ""

    if body and body.username and body.password:
        username = body.username.strip()
        password = body.password.strip()
    else:
        # Check form data
        try:
            form = await request.form()
            username = str(form.get("username", "")).strip()
            password = str(form.get("password", "")).strip()
        except Exception:
            pass

    if not username or not password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username and password are required",
        )

    # 1. Rate Limiting Check (5 failures -> 60s cooldown)
    client_ip = request.client.host if request.client else "unknown"
    lockout_rem = LoginThrottler.check_throttle(client_ip, username)
    if lockout_rem is not None:
        logger.warning("Rate-limited login attempt from %s for username %s (%ds remaining)", client_ip, username, lockout_rem)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Too many failed login attempts. Please wait {lockout_rem} seconds before retrying.",
        )

    # 2. Salted Password Verification
    cred_store = get_user_credential_store()
    expected_hash = cred_store.get(username)

    if not expected_hash or not verify_password(password, expected_hash):
        LoginThrottler.record_failure(client_ip, username)
        logger.warning("Failed login attempt for username: %s from IP %s", username, client_ip)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Successful login: reset failure counter
    LoginThrottler.record_success(client_ip, username)
    role = "admin" if username == "admin" else "user"
    token = create_access_token(user_id=username, role=role, ephemeral=False)
    logger.info("Successful login for user %s (role=%s)", username, role)

    return TokenResponse(token=token, user_id=username, ephemeral=False)


@router.get("/auth/dev-hint")
@router.get("/api/v1/auth/dev-hint")
async def dev_hint() -> Dict[str, Any]:
    """Return demo credentials in development environment; 404 in production."""
    hint = get_dev_hint_credentials()
    if hint is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Dev hint endpoint is disabled in non-dev environment.",
        )
    return hint


@router.post("/auth/guest", response_model=TokenResponse)
@router.post("/api/v1/auth/guest", response_model=TokenResponse)
async def guest_login() -> TokenResponse:
    """Generate ephemeral guest session (guest_<uuid>)."""
    guest_id = f"guest_{uuid.uuid4().hex[:12]}"
    token = create_access_token(user_id=guest_id, role="guest", ephemeral=True)

    logger.info("Generated ephemeral guest session: %s", guest_id)
    return TokenResponse(token=token, user_id=guest_id, ephemeral=True)


@router.get("/auth/me")
@router.get("/api/v1/auth/me")
async def get_me(current_user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    """
    Amendment 1: Return decoded JWT user claims for frontend session restore.
    """
    return {
        "user_id": current_user["user_id"],
        "role": current_user["role"],
        "ephemeral": current_user["ephemeral"],
        "expires_in_minutes": current_user["expires_in_minutes"],
    }


@router.post("/auth/logout")
@router.post("/api/v1/auth/logout")
async def logout(current_user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    """Logout user and purge private_store directory if guest user."""
    user_id = current_user["user_id"]
    purged = False

    if current_user["ephemeral"] or user_id.startswith("guest_"):
        purged = purge_guest_user_dir(user_id)

    logger.info("Logged out user %s (guest_purged=%s)", user_id, purged)
    return {
        "status": "logged_out",
        "user_id": user_id,
        "guest_store_purged": purged,
    }
