"""
MedGraphRAG Backend — Multimodal API Routes
============================================
FastAPI routes for multimodal medical data processing.
Re-exports from backend.multimodal.routes for API consistency.
"""

from __future__ import annotations

from app.multimodal.routes import router

__all__ = ["router"]