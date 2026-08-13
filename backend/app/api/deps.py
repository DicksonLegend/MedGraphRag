"""
MedGraphRAG Backend — API Dependencies & Security
=================================================
Provides:
  1. Global asyncio.Lock singleton for single-flight LLM execution serialization.
  2. PyJWT token creation & verification.
  3. OAuth2 Bearer token dependency for endpoints.
"""

from __future__ import annotations

import asyncio
import logging
import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Optional

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

from app.config import settings

logger = logging.getLogger(__name__)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

# Single-flight LLM execution lock singleton
_llm_lock: Optional[asyncio.Lock] = None


def get_llm_lock() -> asyncio.Lock:
    """Return global single-flight asyncio.Lock for serializing LLM calls."""
    global _llm_lock
    if _llm_lock is None:
        _llm_lock = asyncio.Lock()
    return _llm_lock


def create_access_token(
    user_id: str,
    role: str = "user",
    ephemeral: bool = False,
    expires_delta: Optional[timedelta] = None,
) -> str:
    """Create PyJWT access token."""
    secret_key = settings.get_effective_jwt_secret()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_expire_minutes)

    payload = {
        "sub": user_id,
        "user_id": user_id,
        "role": role,
        "ephemeral": ephemeral,
        "exp": expire,
    }

    encoded_jwt = jwt.encode(payload, secret_key, algorithm=settings.jwt_algorithm)
    return encoded_jwt


async def get_current_user(token: str = Depends(oauth2_scheme)) -> Dict[str, Any]:
    """Validate Bearer JWT token and return claims payload."""
    secret_key = settings.get_effective_jwt_secret()
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials or token expired",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = jwt.decode(token, secret_key, algorithms=[settings.jwt_algorithm])
        user_id: str = payload.get("user_id") or payload.get("sub")
        if user_id is None:
            raise credentials_exception

        exp = payload.get("exp")
        now_ts = datetime.now(timezone.utc).timestamp()
        expires_in_minutes = max(0, int((exp - now_ts) / 60)) if exp else settings.jwt_expire_minutes

        return {
            "user_id": user_id,
            "role": payload.get("role", "user"),
            "ephemeral": payload.get("ephemeral", False),
            "expires_in_minutes": expires_in_minutes,
        }
    except jwt.ExpiredSignatureError:
        logger.info("JWT token expired for incoming request")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired. Please log in again.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.PyJWTError as e:
        logger.warning("JWT decode error: %s", e)
        raise credentials_exception


def purge_guest_user_dir(user_id: str) -> bool:
    """Purge ephemeral guest store directory private_store/guest_<uuid>/."""
    if not user_id.startswith("guest_"):
        return False

    guest_dir = settings.private_store_dir / user_id
    if guest_dir.exists():
        try:
            shutil.rmtree(guest_dir)
            logger.info("Purged ephemeral guest directory: %s", guest_dir)
            return True
        except Exception as e:
            logger.error("Failed to purge guest directory %s: %s", guest_dir, e)
            return False
    return False
