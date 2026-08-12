"""
MedGraphRAG Backend — Embedding Service
=========================================
CPU-only singleton wrapper around ncbi/MedCPT-Query-Encoder.
The GPU is reserved for the future LLM (Step 7+).

Design decisions:
- Singleton pattern: model is loaded once on first call and kept alive.
- torch.no_grad() for all inference to avoid graph construction overhead.
- Mean-pooled, L2-normalised 768-dim vectors (matches the FAISS index).
- Thread-safe via a threading.Lock.
"""

from __future__ import annotations

import logging
import threading
from typing import List, Optional

import numpy as np
import torch
from transformers import AutoModel, AutoTokenizer

from app.config import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Module-level singleton state
# ---------------------------------------------------------------------------
_lock = threading.Lock()
_tokenizer: Optional[object] = None
_model: Optional[object] = None


def _load_model() -> None:
    """Load tokenizer + model into CPU memory. Called once."""
    global _tokenizer, _model

    if _model is not None:
        return  # already loaded

    logger.info("Loading query encoder: %s (device=cpu)", settings.embed_model_name)

    _tokenizer = AutoTokenizer.from_pretrained(
        settings.embed_model_name,
        use_fast=True,
    )
    _model = AutoModel.from_pretrained(settings.embed_model_name)

    # Ensure model is on CPU regardless of any environment GPU presence
    _model = _model.to("cpu")
    _model.eval()

    logger.info(
        "Query encoder loaded. Param count: %s",
        sum(p.numel() for p in _model.parameters()),
    )


def embed_query(query: str) -> np.ndarray:
    """
    Encode a single query string into a 768-dim L2-normalised float32 vector.

    The FAISS index was built with:
        - ncbi/MedCPT-Article-Encoder (doc side)
        - metric_type = METRIC_INNER_PRODUCT on L2-normalised vectors (= cosine)

    We therefore must:
        1. Use ncbi/MedCPT-Query-Encoder (asymmetric pair).
        2. Mean-pool + L2-normalise output.

    Returns
    -------
    np.ndarray  shape=(1, 768), dtype=float32
    """
    with _lock:
        _load_model()

    inputs = _tokenizer(
        [query],
        padding=True,
        truncation=True,
        max_length=settings.embed_max_length,
        return_tensors="pt",
    )

    # Move to CPU explicitly (safety guard)
    inputs = {k: v.to("cpu") for k, v in inputs.items()}

    with torch.no_grad():
        output = _model(**inputs)

    # Mean-pool over the token dimension (same as embedder.py used during build)
    token_embeddings: torch.Tensor = output.last_hidden_state  # (1, seq_len, 768)
    attention_mask: torch.Tensor = inputs["attention_mask"]    # (1, seq_len)
    mask_expanded = attention_mask.unsqueeze(-1).float()        # (1, seq_len, 1)
    pooled = (token_embeddings * mask_expanded).sum(1) / mask_expanded.sum(1)  # (1, 768)

    # L2-normalise (cosine similarity via inner product in FAISS)
    norm = torch.linalg.norm(pooled, dim=-1, keepdim=True).clamp(min=1e-12)
    normalised = (pooled / norm).cpu().numpy().astype(np.float32)  # (1, 768)

    logger.debug("Query embedded. Shape: %s", normalised.shape)
    return normalised


def embed_queries(queries: List[str]) -> np.ndarray:
    """
    Batch version of embed_query.

    Returns
    -------
    np.ndarray  shape=(N, 768), dtype=float32
    """
    with _lock:
        _load_model()

    inputs = _tokenizer(
        queries,
        padding=True,
        truncation=True,
        max_length=settings.embed_max_length,
        return_tensors="pt",
    )
    inputs = {k: v.to("cpu") for k, v in inputs.items()}

    with torch.no_grad():
        output = _model(**inputs)

    token_embeddings = output.last_hidden_state
    attention_mask = inputs["attention_mask"]
    mask_expanded = attention_mask.unsqueeze(-1).float()
    pooled = (token_embeddings * mask_expanded).sum(1) / mask_expanded.sum(1)

    norm = torch.linalg.norm(pooled, dim=-1, keepdim=True).clamp(min=1e-12)
    normalised = (pooled / norm).cpu().numpy().astype(np.float32)
    return normalised


def is_loaded() -> bool:
    """True if the model has been loaded into memory."""
    return _model is not None


def warm_up() -> None:
    """
    Pre-warm the embedding model with a short dummy query.
    Call this during FastAPI startup to avoid cold-start latency on the first
    real request.
    """
    logger.info("Warming up embedding model …")
    embed_query("test query warm-up")
    logger.info("Embedding model warmed up.")
