"""
MedGraphRAG Backend — Password Hashing & Login Throttling (F-03)
================================================================
Implements salted scrypt/argon2 password hashing, credential loading from env,
and per-IP / per-account login rate limiting (5 failures -> 60s backoff).
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import os
import secrets
import time
from typing import Dict, Optional, Tuple

from app.config import settings

logger = logging.getLogger(__name__)

# In-memory throttle state: key -> (failure_count, lockout_until_timestamp)
_throttle_state: Dict[str, Tuple[int, float]] = {}


def hash_password(password: str) -> str:
    """Hash password using stdlib scrypt with a cryptographically secure 16-byte random salt."""
    salt = os.urandom(16)
    derived = hashlib.scrypt(
        password.encode("utf-8"),
        salt=salt,
        n=16384,
        r=8,
        p=1,
    )
    return f"scrypt$16384$8$1${salt.hex()}${derived.hex()}"


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify plain password against hashed password string."""
    if not hashed_password or not plain_password:
        return False

    # Check for scrypt format
    if hashed_password.startswith("scrypt$"):
        try:
            parts = hashed_password.split("$")
            if len(parts) == 6:
                _, n_s, r_s, p_s, salt_hex, hash_hex = parts
                n, r, p = int(n_s), int(r_s), int(p_s)
                salt = bytes.fromhex(salt_hex)
                expected_hash = bytes.fromhex(hash_hex)
                candidate = hashlib.scrypt(
                    plain_password.encode("utf-8"),
                    salt=salt,
                    n=n,
                    r=r,
                    p=p,
                )
                return hmac.compare_digest(candidate, expected_hash)
        except Exception as e:
            logger.warning("scrypt verification error: %s", e)
            return False

    # Check for legacy SHA-256 during migration
    if len(hashed_password) == 64:
        candidate_hex = hashlib.sha256(plain_password.encode("utf-8")).hexdigest()
        return hmac.compare_digest(candidate_hex, hashed_password)

    return False


class LoginThrottler:
    """Per-IP and per-account login rate limiting (5 failures -> 60s cooldown)."""

    MAX_FAILURES = 5
    LOCKOUT_SECONDS = 60.0

    @classmethod
    def check_throttle(cls, ip: str, username: str) -> Optional[int]:
        """
        Check if (ip, username) is currently rate-limited.
        Returns remaining cooldown seconds if locked out, or None if permitted.
        """
        now = time.time()
        for key in (f"ip:{ip}", f"user:{username}"):
            if key in _throttle_state:
                count, lockout_until = _throttle_state[key]
                if now < lockout_until:
                    return int(lockout_until - now) + 1
        return None

    @classmethod
    def record_failure(cls, ip: str, username: str) -> None:
        """Record login failure for IP and username, triggering lockout if threshold reached."""
        now = time.time()
        for key in (f"ip:{ip}", f"user:{username}"):
            count, lockout_until = _throttle_state.get(key, (0, 0.0))
            if now > lockout_until:
                # Reset if previous lockout expired
                count = count + 1
            else:
                count = count + 1

            if count >= cls.MAX_FAILURES:
                lockout_until = now + cls.LOCKOUT_SECONDS
                logger.warning(
                    "Login rate-limit triggered for %s (%d failures). Locked out for %ds.",
                    key, count, int(cls.LOCKOUT_SECONDS)
                )
            _throttle_state[key] = (count, lockout_until)

    @classmethod
    def record_success(cls, ip: str, username: str) -> None:
        """Clear failure counts on successful login."""
        _throttle_state.pop(f"ip:{ip}", None)
        _throttle_state.pop(f"user:{username}", None)


# Cached user credential store (username -> hashed_password)
_cached_user_hashes: Optional[Dict[str, str]] = None
_dev_hint_password: Optional[str] = None


def get_user_credential_store() -> Dict[str, str]:
    """
    Load user password hashes from environment or durable dev defaults.
    Stores only salted hashes in memory; no plaintext credentials stored.
    """
    global _cached_user_hashes, _dev_hint_password
    if _cached_user_hashes is not None:
        return _cached_user_hashes

    demo_pass = os.getenv("DEMO_USER_PASSWORD", "password123")
    admin_pass = os.getenv("ADMIN_PASSWORD", "admin_secure_pass_2026")

    is_dev = settings.app_env.lower() in ("dev", "development", "local", "test")
    if not is_dev and (not os.getenv("DEMO_USER_PASSWORD") or not os.getenv("ADMIN_PASSWORD")):
        raise RuntimeError(
            "FATAL: DEMO_USER_PASSWORD and ADMIN_PASSWORD environment variables must be set in non-dev environment."
        )

    _dev_hint_password = demo_pass

    _cached_user_hashes = {
        "demo_user": hash_password(demo_pass),
        "admin": hash_password(admin_pass),
    }
    return _cached_user_hashes


def get_dev_hint_credentials() -> Optional[Dict[str, str]]:
    """Return demo credentials hint only in dev environment."""
    is_dev = settings.app_env.lower() in ("dev", "development", "local", "test")
    if not is_dev:
        return None
    get_user_credential_store()
    return {
        "username": "demo_user",
        "password": _dev_hint_password or "password123",
        "role": "user",
        "environment": settings.app_env,
    }
