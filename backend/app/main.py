"""
MedGraphRAG Backend — FastAPI Application Entrypoint
=====================================================
Exposes MedGraphRAG hybrid retrieval, self-verifying generation,
and diagnostic report interpretation services over HTTP.

Lifespan startup:
  - Pre-warms retrieval singletons (FAISS, Kùzu).
  - Purges stale guest session directories (private_store/guest_*).
"""

from __future__ import annotations

import logging
import os
import shutil
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import auth, features, health, query, report, multimodal
from app.config import settings
from app.core.retrieval import faiss_store, graph_store

logger = logging.getLogger(__name__)


def purge_stale_guest_directories() -> int:
    """Purge guest_* directories in private_store/ older than jwt_expire_minutes."""
    private_dir = settings.private_store_dir
    if not private_dir.exists():
        return 0

    purged_count = 0
    now_ts = time.time()
    max_age_seconds = settings.jwt_expire_minutes * 60

    try:
        for item in private_dir.iterdir():
            if item.is_dir() and item.name.startswith("guest_"):
                mtime = item.stat().st_mtime
                if (now_ts - mtime) > max_age_seconds:
                    try:
                        shutil.rmtree(item)
                        purged_count += 1
                        logger.info("Startup cleanup: Purged stale guest directory %s", item)
                    except Exception as e:
                        logger.warning("Failed to purge stale guest directory %s: %s", item, e)
    except Exception as e:
        logger.warning("Error scanning private_store for stale guest directories: %s", e)

    return purged_count


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup & shutdown tasks."""
    # 0. Log resolved private_store_dir and assert writable
    pstore = settings.private_store_dir.resolve()
    pstore.mkdir(parents=True, exist_ok=True)
    logger.info("Resolved private_store_dir: %s", pstore)
    assert os.access(pstore, os.W_OK), f"private_store_dir {pstore} is not writable!"

    # 1. Enforce JWT Secret Warning check
    secret = settings.get_effective_jwt_secret()

    # 2. Startup Cleanup of Stale Guest Directories
    purged = purge_stale_guest_directories()
    if purged > 0:
        logger.info("Startup guest cleanup complete. Purged %d stale guest directories.", purged)

    # 3. Warm up FAISS, Kuzu, and LLM Singletons
    try:
        faiss_store.warm_up()
        graph_store.warm_up()
        logger.info("FAISS and Kùzu singletons warmed up successfully.")
    except Exception as e:
        logger.warning("Singleton warmup warning: %s", e)

    try:
        from app.core.llm.llm_loader import get_llm
        get_llm()
        logger.info("Main LLM singleton pre-warmed on GPU successfully.")
    except Exception as e:
        logger.warning("LLM GPU preload warning: %s", e)

    try:
        from app.multimodal.parser import BiomedCLIPEngine
        BiomedCLIPEngine.get_instance()
        logger.info("BiomedCLIP triage engine pre-warmed on CPU successfully.")
    except Exception as e:
        logger.warning("BiomedCLIP preload warning: %s", e)

    yield

    logger.info("=== MedGraphRAG FastAPI Service Layer Shutdown ===")


app = FastAPI(
    title="MedGraphRAG Backend API",
    description="Self-Verifying Hybrid Vector-Graph RAG & Diagnostic Report Interpretation Engine",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS Middleware (Localhost dev)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include Routers
app.include_router(health.router)
app.include_router(auth.router)
app.include_router(query.router)
app.include_router(report.router)
app.include_router(features.router)
app.include_router(multimodal.router)
