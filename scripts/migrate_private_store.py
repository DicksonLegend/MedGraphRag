#!/usr/bin/env python3
"""
MedGraphRAG Security Tool — Private Store Key Migration (F-02)
===============================================================
Migrates on-disk private store files from legacy plaintext user_key.key / key.bin
to HKDF-SHA256 derived keys (zero decryption keys stored on disk).
Enforces POSIX 0700 (directory) and 0600 (file) permissions.

Usage:
  python scripts/migrate_private_store.py [--dry-run]
"""

import argparse
import json
import logging
import os
import sys
from pathlib import Path

# Add backend directory to Python path
REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = REPO_ROOT / "backend"
sys.path.insert(0, str(BACKEND_DIR))

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from app.config import settings
from app.core.report.crypto import (
    derive_private_key,
    encrypt_payload_gcm,
    secure_chmod,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("migrate_private_store")


def migrate_private_store(dry_run: bool = False) -> None:
    private_root = settings.private_store_dir.resolve()
    if not private_root.exists():
        logger.info("No private store directory found at %s. Nothing to migrate.", private_root)
        return

    logger.info("Scanning private store at %s (dry_run=%s)...", private_root, dry_run)
    migrated_reports = 0
    migrated_scans = 0

    secure_chmod(private_root, 0o700)

    for user_dir in private_root.iterdir():
        if not user_dir.is_dir():
            continue

        user_id = user_dir.name
        secure_chmod(user_dir, 0o700)

        # 1. Migrate Diagnostic Reports (meta/)
        meta_dir = user_dir / "meta"
        if meta_dir.exists() and meta_dir.is_dir():
            secure_chmod(meta_dir, 0o700)
            legacy_key_file = meta_dir / "user_key.key"
            payload_enc_file = meta_dir / "report_payload.enc"

            if legacy_key_file.exists() and payload_enc_file.exists():
                try:
                    with open(legacy_key_file, "rb") as f:
                        legacy_key = f.read()
                    with open(payload_enc_file, "rb") as f:
                        blob = f.read()

                    nonce, ciphertext = blob[:12], blob[12:]
                    aesgcm = AESGCM(legacy_key)
                    decrypted_bytes = aesgcm.decrypt(nonce, ciphertext, None)
                    payload = json.loads(decrypted_bytes.decode("utf-8"))
                    
                    report_id = payload.get("report_id", f"rep_{user_id[:8]}")

                    # Re-encrypt with HKDF derived key
                    hkdf_key = derive_private_key(user_id=user_id, item_id=report_id, purpose="report")
                    new_encrypted_bytes = encrypt_payload_gcm(hkdf_key, decrypted_bytes)

                    if not dry_run:
                        report_enc_file = meta_dir / f"{report_id}.enc"
                        with open(report_enc_file, "wb") as f:
                            f.write(new_encrypted_bytes)
                        with open(payload_enc_file, "wb") as f:
                            f.write(new_encrypted_bytes)
                        secure_chmod(report_enc_file, 0o600)
                        secure_chmod(payload_enc_file, 0o600)
                        legacy_key_file.unlink()
                        logger.info("Migrated report for user %s (%s) -> HKDF encryption", user_id, report_id)
                    else:
                        logger.info("[DRY RUN] Would migrate report %s for user %s", report_id, user_id)
                    migrated_reports += 1
                except Exception as e:
                    logger.error("Failed to migrate report for user %s: %s", user_id, e)

        # 2. Migrate Scans (scans/<scan_id>/)
        scans_dir = user_dir / "scans"
        if scans_dir.exists() and scans_dir.is_dir():
            secure_chmod(scans_dir, 0o700)
            for scan_id_dir in scans_dir.iterdir():
                if not scan_id_dir.is_dir():
                    continue
                scan_id = scan_id_dir.name
                secure_chmod(scan_id_dir, 0o700)

                key_file = scan_id_dir / "key.bin"
                meta_enc_file = scan_id_dir / "metadata.enc"

                if key_file.exists() and meta_enc_file.exists():
                    try:
                        with open(key_file, "rb") as f:
                            legacy_key = f.read()
                        with open(meta_enc_file, "rb") as f:
                            blob = f.read()

                        nonce, ciphertext = blob[:12], blob[12:]
                        aesgcm = AESGCM(legacy_key)
                        decrypted_bytes = aesgcm.decrypt(nonce, ciphertext, None)

                        # Re-encrypt with HKDF derived key
                        hkdf_key = derive_private_key(user_id=user_id, item_id=scan_id, purpose="scan")
                        new_encrypted_bytes = encrypt_payload_gcm(hkdf_key, decrypted_bytes)

                        if not dry_run:
                            with open(meta_enc_file, "wb") as f:
                                f.write(new_encrypted_bytes)
                            secure_chmod(meta_enc_file, 0o600)
                            key_file.unlink()
                            logger.info("Migrated scan %s for user %s -> HKDF encryption", scan_id, user_id)
                        else:
                            logger.info("[DRY RUN] Would migrate scan %s for user %s", scan_id, user_id)
                        migrated_scans += 1
                    except Exception as e:
                        logger.error("Failed to migrate scan %s for user %s: %s", scan_id, user_id, e)

    logger.info(
        "Migration complete: %d reports, %d scans processed (dry_run=%s).",
        migrated_reports, migrated_scans, dry_run
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Migrate private store encryption to HKDF derived keys.")
    parser.add_argument("--dry-run", action="store_true", help="Inspect what would be migrated without modifying files.")
    args = parser.parse_args()
    migrate_private_store(dry_run=args.dry_run)
