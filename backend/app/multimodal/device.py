"""Multimodal-local VLM device policy (Q1 binding decision).

The RTX 3050 6 GB is budgeted exclusively for Qwen2.5-7B Q4_K_M.
VLM inference therefore defaults to CPU. Override ONLY via the
MEDGRAPH_VLM_DEVICE environment variable; backend/app/config.py is
intentionally NOT edited (out of scope). Co-residency of a second model
in VRAM is forbidden; swap-in/swap-out behind the serialization lock is a
later option and is not implemented here.
"""
from __future__ import annotations

import logging
import os

logger = logging.getLogger(__name__)

DEFAULT_VLM_DEVICE = "cpu"
_ALLOWED = {"cpu"}


def resolve_vlm_device() -> str:
    """Return the effective VLM device. CPU-only by default.

    If MEDGRAPH_VLM_DEVICE requests cuda, refuse loudly and fall back to
    cpu: VRAM is reserved for the main LLM (single-model policy).
    """
    requested = os.environ.get("MEDGRAPH_VLM_DEVICE", DEFAULT_VLM_DEVICE).lower()
    if requested.startswith("cuda"):
        logger.warning(
            "MEDGRAPH_VLM_DEVICE=cuda refused: GPU is exclusively budgeted for "
            "Qwen2.5-7B Q4_K_M (single-model policy). Forcing cpu."
        )
        return "cpu"
    if requested not in _ALLOWED:
        return DEFAULT_VLM_DEVICE
    return requested
