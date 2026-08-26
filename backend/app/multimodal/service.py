"""
MedGraphRAG Backend — Multimodal Service
=========================================
Orchestrates multimodal medical imaging analysis (BiomedCLIP triage + Qwen2-VL),
AES-256-GCM encrypted private storage, and preview serving.
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from fastapi import HTTPException, status
from PIL import Image

from app.config import settings
from app.multimodal.parser import (
    DICOM_EXTENSIONS,
    IMAGE_EXTENSIONS,
    PDF_EXTENSIONS,
    analyze_medical_image_with_vlm,
    compute_file_hash,
    detect_image_modality,
    detect_orientation,
    ingest_multimodal_files,
    load_dicom_image,
    load_standard_image,
    parse_pdf_with_images,
)
from app.multimodal.schemas import (
    ImageAnalysisResult,
    ImageModality,
    ImageOrientation,
    MedicalImage,
    MultimodalIngestionResult,
    PDFDocument,
)

logger = logging.getLogger(__name__)

ROOT_DIR = Path(__file__).resolve().parent.parent.parent.parent
SAMPLE100_DIR = ROOT_DIR / "data/multimodal/images/sample100"


class MultimodalService:
    """
    Service managing multimodal imaging workflows, isolated encrypted storage,
    and preview delivery.
    """

    def __init__(self) -> None:
        self.private_store_root = settings.private_store_dir.resolve()
        self.private_store_root.mkdir(parents=True, exist_ok=True)

    def _get_user_scan_dir(self, user_id: str, image_id: str) -> Path:
        from app.core.report.crypto import secure_chmod
        user_dir = self.private_store_root / user_id
        scans_dir = user_dir / "scans"
        scan_dir = scans_dir / image_id
        scan_dir.mkdir(parents=True, exist_ok=True)
        secure_chmod(user_dir, 0o700)
        secure_chmod(scans_dir, 0o700)
        secure_chmod(scan_dir, 0o700)
        return scan_dir

    def _encrypt_and_save_metadata(self, scan_dir: Path, data: Dict[str, Any], user_id: str, image_id: str) -> None:
        from app.core.report.crypto import derive_private_key, encrypt_payload_gcm, secure_chmod
        payload_bytes = json.dumps(data).encode("utf-8")
        scan_key = derive_private_key(user_id=user_id, item_id=image_id, purpose="scan")
        encrypted_bytes = encrypt_payload_gcm(scan_key, payload_bytes)

        enc_file = scan_dir / "metadata.enc"
        with open(enc_file, "wb") as f:
            f.write(encrypted_bytes)
        secure_chmod(enc_file, 0o600)

    def _decrypt_metadata(self, scan_dir: Path, user_id: str, image_id: str) -> Optional[Dict[str, Any]]:
        enc_file = scan_dir / "metadata.enc"
        if not enc_file.exists():
            return None

        from app.core.report.crypto import derive_private_key, decrypt_payload_gcm

        with open(enc_file, "rb") as f:
            encrypted_data = f.read()

        # 1. Try HKDF derived key
        try:
            scan_key = derive_private_key(user_id=user_id, item_id=image_id, purpose="scan")
            decrypted_bytes = decrypt_payload_gcm(scan_key, encrypted_data)
            return json.loads(decrypted_bytes.decode("utf-8"))
        except Exception:
            pass

        # 2. Legacy fallback: check if key.bin exists on disk
        key_file = scan_dir / "key.bin"
        if key_file.exists():
            try:
                with open(key_file, "rb") as f:
                    legacy_key = f.read()
                decrypted_bytes = decrypt_payload_gcm(legacy_key, encrypted_data)
                return json.loads(decrypted_bytes.decode("utf-8"))
            except Exception as e:
                logger.warning("Failed legacy decrypting scan metadata in %s: %s", scan_dir, e)

        return None

    def process_and_store_image(
        self,
        file_bytes: bytes,
        filename: str,
        user_id: str,
        mode: str = "triage",
        custom_prompt: Optional[str] = None,
    ) -> ImageAnalysisResult:
        """
        Process single uploaded image (DICOM or standard), run analysis,
        and store encrypted in private_store/{user_id}/scans/{image_id}/.
        """
        file_hash = compute_file_hash(file_bytes)
        image_id = file_hash[:16]
        ext = Path(filename).suffix.lower()

        # 1. Load image and generate ≤1024px 8-bit PNG preview bytes
        if ext in DICOM_EXTENSIONS:
            pil_img, preview_bytes, dicom_tags = load_dicom_image(file_bytes)
            orientation = detect_orientation(filename, dicom_tags)
            body_part = dicom_tags.get("BodyPartExamined", "Chest")
            modality = ImageModality.XRAY
        else:
            pil_img, preview_bytes = load_standard_image(file_bytes)
            orientation = detect_orientation(filename)
            body_part = "Chest"
            modality = detect_image_modality(filename, pil_img)

        med_img = MedicalImage(
            image_id=image_id,
            filename=filename,
            modality=modality,
            orientation=orientation,
            body_part=body_part,
            file_bytes_hash=file_hash,
            image_bytes=file_bytes,
            preview_bytes=preview_bytes,
        )

        # 2. Run analysis (BiomedCLIP triage and/or Qwen2-VL generative interpretation)
        analysis_result = analyze_medical_image_with_vlm(med_img, mode=mode, prompt=custom_prompt)

        # 3. Store into isolated private store
        scan_dir = self._get_user_scan_dir(user_id, image_id)

        # Save preview.png (for GET /multimodal/preview/{image_id})
        with open(scan_dir / "preview.png", "wb") as pf:
            pf.write(preview_bytes)

        # Save original file
        with open(scan_dir / f"original{ext}", "wb") as of:
            of.write(file_bytes)

        # Encrypt and save structured analysis metadata
        meta_dict = analysis_result.model_dump()
        self._encrypt_and_save_metadata(scan_dir, meta_dict, user_id=user_id, image_id=image_id)

        logger.info(
            "Multimodal: Stored scan %s for user %s (mode=%s, findings=%d)",
            image_id,
            user_id,
            mode,
            len(analysis_result.findings),
        )
        return analysis_result

    def get_image_preview(self, user_id: str, image_id: str) -> bytes:
        """
        Serve 8-bit PNG preview bytes for an image_id.
        Enforces user ownership isolation: checks user's private store, or sample100 fallback.
        """
        # 1. Check user's own private scan store
        user_scan_dir = self.private_store_root / user_id / "scans" / image_id
        preview_file = user_scan_dir / "preview.png"
        if preview_file.exists():
            return preview_file.read_bytes()

        # 2. Check sample100 benchmark directory for public OpenI test scans (exact match)
        if SAMPLE100_DIR.exists():
            for ext in (".png", ".jpg", ".jpeg", "_0.png"):
                cand = SAMPLE100_DIR / f"{image_id}{ext}"
                if cand.is_file():
                    _, prev_b = load_standard_image(cand.read_bytes())
                    return prev_b

        # Uniform 404 (no cross-user existence probe oracle)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Scan preview not found for image_id: {image_id}",
        )

    def get_scan_context(self, user_id: str, image_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve structured scan findings for query context injection.
        """
        scan_dir = self.private_store_root / user_id / "scans" / image_id
        if scan_dir.exists():
            data = self._decrypt_metadata(scan_dir, user_id=user_id, image_id=image_id)
            if data:
                return data

        # Check sample100 benchmark directory (exact match)
        if SAMPLE100_DIR.exists():
            for ext in (".png", ".jpg", ".jpeg", "_0.png"):
                cand = SAMPLE100_DIR / f"{image_id}{ext}"
                if cand.is_file():
                    file_b = cand.read_bytes()
                    med_img = MedicalImage(
                        image_id=image_id,
                        filename=cand.name,
                        modality=ImageModality.XRAY,
                        orientation=ImageOrientation.PA,
                        file_bytes_hash=compute_file_hash(file_b),
                        image_bytes=file_b,
                    )
                    res = analyze_medical_image_with_vlm(med_img, mode="triage")
                    return res.model_dump()

        return None

    def list_user_scans(self, user_id: str) -> List[ImageAnalysisResult]:
        """List all stored scans for the authenticated user."""
        user_scans_dir = self.private_store_root / user_id / "scans"
        if not user_scans_dir.exists():
            return []

        results: List[ImageAnalysisResult] = []
        for s_dir in user_scans_dir.iterdir():
            if s_dir.is_dir():
                meta = self._decrypt_metadata(s_dir, user_id=user_id, image_id=s_dir.name)
                if meta:
                    try:
                        results.append(ImageAnalysisResult(**meta))
                    except Exception:
                        pass

        results.sort(key=lambda x: x.created_at, reverse=True)
        return results

    def purge_user_scan(self, user_id: str, image_id: str) -> bool:
        """Purge an individual scan and its encrypted metadata from private storage."""
        scan_dir = self.private_store_root / user_id / "scans" / image_id
        if scan_dir.exists():
            shutil.rmtree(scan_dir)
            return True
        return False