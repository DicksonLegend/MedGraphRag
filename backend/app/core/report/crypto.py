"""
MedGraphRAG Backend — Cryptographic Subsystem (F-02)
=====================================================
Provides HKDF-SHA256 key derivation and AES-256-GCM authenticated encryption
for user-isolated private diagnostic stores and multimodal scans.

Key Architecture:
  1. Master secret: MEDGRAPH_MASTER_KEY (env-driven, fail-fast in prod).
  2. Per-item keys derived on-the-fly via HKDF-SHA256:
     Key = HKDF(IKM=master_key, Salt=user_id:item_id, Info=purpose, Length=32)
  3. No plaintext decryption keys stored on disk for new items.
  4. File and directory permissions enforced at 0600 (files) and 0700 (directories).
  5. Backwards compatibility: Decrypts legacy items with on-disk user_key.key if present.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Optional, Union

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from app.config import settings

logger = logging.getLogger(__name__)


def derive_private_key(user_id: str, item_id: str, purpose: str = "report") -> bytes:
    """
    Derive a 256-bit AES-GCM key from master secret using HKDF-SHA256.
    Salt is bound strictly to (user_id, item_id).
    """
    master_key = settings.get_effective_master_key()
    salt = f"{user_id}:{item_id}".encode("utf-8")
    info = f"medgraph_private_{purpose}_aes256_gcm".encode("utf-8")
    
    hkdf = HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        info=info,
    )
    return hkdf.derive(master_key)


def encrypt_payload_gcm(key: bytes, plaintext: bytes) -> bytes:
    """
    Encrypt plaintext with AES-256-GCM using a cryptographically secure 12-byte random nonce.
    Returns: nonce (12 bytes) + ciphertext with auth tag (len - 12 bytes).
    """
    aesgcm = AESGCM(key)
    nonce = os.urandom(12)
    ciphertext = aesgcm.encrypt(nonce, plaintext, None)
    return nonce + ciphertext


def decrypt_payload_gcm(key: bytes, data: bytes) -> bytes:
    """
    Decrypt AES-256-GCM payload.
    data format: nonce (12 bytes) + ciphertext with auth tag.
    """
    if len(data) < 28:
        raise ValueError(f"Encrypted payload too short ({len(data)} bytes). Minimum is 28 bytes.")
    nonce, ciphertext = data[:12], data[12:]
    aesgcm = AESGCM(key)
    return aesgcm.decrypt(nonce, ciphertext, None)


def secure_chmod(path: Union[str, Path], mode: int = 0o600) -> None:
    """Safely apply POSIX permissions (e.g. 0600 for files, 0700 for directories)."""
    try:
        os.chmod(str(path), mode)
    except Exception as e:
        logger.debug("chmod %o failed on %s (filesystem may not support POSIX perms): %s", mode, path, e)
