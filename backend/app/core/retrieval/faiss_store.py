"""
MedGraphRAG Backend — FAISS Store
====================================
Read-only access to the IVFpq FAISS index + sidecar parquet.

Responsibilities:
  1. Load the FAISS IVFpq index into CPU memory (read-only).
  2. Load the id_mapping sidecar parquet as an in-memory lookup table.
  3. Load the chunk byte-offset index for O(1) chunk text access.
  4. Expose search() → sorted list of (faiss_id, score, metadata_dict).
  5. Expose load_chunk_text() → raw text for a given faiss_id.

Memory profile (estimated):
  - FAISS IVFpq: ~240 MB
  - Sidecar parquet: ~150 MB (as Arrow table)
  - chunk_line_offsets.npy: ~18 MB
  Total: ~410 MB — well within the 12 GB budget.

GPU policy: FAISS is loaded as a flat CPU index via faiss.read_index().
The code NEVER calls faiss.index_cpu_to_gpu or similar.
"""

from __future__ import annotations

import json
import logging
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import faiss
import numpy as np
import pyarrow.parquet as pq
import pyarrow as pa

from app.config import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Module-level singleton state
# ---------------------------------------------------------------------------
_lock = threading.Lock()
_index: Optional[faiss.Index] = None
_sidecar: Optional[pa.Table] = None         # arrow table, kept in-memory
_offsets: Optional[np.ndarray] = None       # byte offsets into chunks.jsonl
_chunks_fh: Optional[object] = None         # open file handle for chunks.jsonl


def _load_store() -> None:
    """Load all FAISS artifacts. Called once; subsequent calls are no-ops."""
    global _index, _sidecar, _offsets, _chunks_fh

    if _index is not None:
        return

    logger.info("Loading FAISS index from %s …", settings.faiss_index_path)
    idx = faiss.read_index(str(settings.faiss_index_path))

    # --- GPU safety check ---
    if hasattr(idx, "device"):
        raise RuntimeError(
            "FAISS index is on GPU — this violates the CPU-only retrieval constraint. "
            "Rebuild the index with faiss.read_index() on a CPU-only binary."
        )

    # Set nprobe for IVFpq recall/speed trade-off
    if hasattr(idx, "nprobe"):
        idx.nprobe = settings.faiss_nprobe
        logger.info("FAISS nprobe set to %d", settings.faiss_nprobe)

    logger.info(
        "FAISS index loaded. ntotal=%d, d=%d, type=%s",
        idx.ntotal, idx.d, type(idx).__name__,
    )

    logger.info("Loading sidecar parquet from %s …", settings.sidecar_parquet_path)
    sidecar = pq.read_table(str(settings.sidecar_parquet_path))
    logger.info("Sidecar loaded. Rows=%d, Columns=%s", len(sidecar), sidecar.column_names)

    # Validate 1:1 alignment with FAISS ntotal
    if len(sidecar) != idx.ntotal:
        raise RuntimeError(
            f"Sidecar row count ({len(sidecar)}) ≠ FAISS ntotal ({idx.ntotal}). "
            "Index and sidecar are out of sync."
        )

    logger.info("Loading chunk byte offsets from %s …", settings.chunk_offsets_npy_path)
    offsets = np.load(str(settings.chunk_offsets_npy_path))
    if len(offsets) != idx.ntotal:
        raise RuntimeError(
            f"Offset count ({len(offsets)}) ≠ FAISS ntotal ({idx.ntotal}). "
            "chunk_line_offsets.npy is out of sync."
        )

    logger.info("Opening chunks.jsonl file handle …")
    fh = open(str(settings.chunks_jsonl_path), "rb")  # binary for seek+readline

    # Commit
    _index = idx
    _sidecar = sidecar
    _offsets = offsets
    _chunks_fh = fh

    logger.info("FAISSStore ready. Total vectors: %d", _index.ntotal)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def warm_up() -> None:
    """Pre-load FAISS artifacts during startup."""
    with _lock:
        _load_store()


def _build_private_user_snippet(user_id: str) -> str:
    """
    Extract structured lab values and reports from the user's private Kùzu database,
    synthesizing the latest current values per test across all report types and full history.
    """
    user_dir = settings.private_store_dir / user_id
    db_path = user_dir / "kuzu" / "private_kuzu_db"
    if db_path.exists():
        try:
            import kuzu
            db = kuzu.Database(str(db_path), read_only=True)
            conn = kuzu.Connection(db)
            try:
                query = """
                MATCH (r:Report)-[:HAS_LAB_VALUE]->(lv:LabValue)
                RETURN r.id AS report_id, r.report_date AS report_date, r.filename AS filename,
                       lv.test_name AS test_name, lv.value AS value, lv.unit AS unit,
                       lv.ref_low AS ref_low, lv.ref_high AS ref_high, lv.is_critical AS is_critical
                ORDER BY r.report_date DESC, r.id DESC, lv.test_name ASC
                """
                df = conn.execute(query).get_as_df()
                if not df.empty:
                    # 1. Compile latest values and history per unique test across all reports
                    latest_per_test = {}
                    history_per_test = {}
                    for _, row in df.iterrows():
                        t_name = str(row["test_name"])
                        r_date = str(row["report_date"])
                        val = float(row["value"])
                        unit = str(row["unit"])
                        r_low = row["ref_low"]
                        r_high = row["ref_high"]
                        is_crit = (
                            bool(row["is_critical"])
                            or (r_high is not None and val > r_high)
                            or (r_low is not None and val < r_low)
                        )

                        if t_name not in latest_per_test:
                            latest_per_test[t_name] = {
                                "value": val,
                                "unit": unit,
                                "report_date": r_date,
                                "report_id": str(row["report_id"]),
                                "ref_low": r_low,
                                "ref_high": r_high,
                                "is_critical": is_crit,
                            }
                        if t_name not in history_per_test:
                            history_per_test[t_name] = []
                        history_per_test[t_name].append((r_date, val, unit, is_crit))

                    lines = [f"=== PATIENT PRIVATE DIAGNOSTIC LAB REPORTS ({user_id}) ==="]
                    lines.append("\n--- LATEST / CURRENT LAB VALUES (Most Recent Status) ---")
                    for t_name, info in sorted(latest_per_test.items()):
                        crit = " [CRITICAL ALERT / OUT OF RANGE]" if info["is_critical"] else " [NORMAL]"
                        ref_str = (
                            f" (Ref: {info['ref_low']} - {info['ref_high']})"
                            if info.get("ref_low") is not None and info.get("ref_high") is not None and info["ref_high"] < 9000
                            else ""
                        )
                        prior_note = ""
                        priors = [p for p in history_per_test[t_name] if p[0] != info["report_date"]]
                        if priors:
                            p_date, p_val, p_unit, _ = priors[0]
                            prior_note = f"; Prior on {p_date} was {p_val} {p_unit}"
                        lines.append(f"  • {t_name}: {info['value']} {info['unit']}{ref_str}{crit} (Latest from {info['report_date']}{prior_note})")

                    lines.append("\n--- ALL UPLOADED REPORTS (Longitudinal History) ---")
                    grouped = df.groupby(["report_id", "report_date", "filename"], sort=False)
                    for (r_id, r_date, fname), group in grouped:
                        lines.append(f"\nReport {r_id} (Date: {r_date}, File: {fname}):")
                        for _, row in group.iterrows():
                            val = float(row["value"])
                            r_high = row.get("ref_high")
                            r_low = row.get("ref_low")
                            is_crit = (
                                bool(row["is_critical"])
                                or (r_high is not None and val > r_high)
                                or (r_low is not None and val < r_low)
                            )
                            crit = " [CRITICAL ALERT]" if is_crit else ""
                            ref_str = (
                                f" (Ref: {r_low} - {r_high})"
                                if r_low is not None and r_high is not None and r_high < 9000
                                else ""
                            )
                            lines.append(f"  - {row['test_name']}: {row['value']} {row['unit']}{ref_str}{crit}")
                    return "\n".join(lines)
            finally:
                del conn
                del db
        except Exception as ke:
            logger.debug("Error querying private Kùzu snippet for %s: %s", user_id, ke)

    # Fallback to decrypted payload
    try:
        from app.core.report.store import load_private_decrypted_payload
        priv_payload = load_private_decrypted_payload(user_id)
        if priv_payload:
            snip = priv_payload.get("raw_text_snippet", "")
            if snip:
                return snip
            asms = priv_payload.get("assessments", [])
            if asms:
                lines = [f"=== PATIENT PRIVATE DIAGNOSTIC LAB REPORTS ({user_id}) ==="]
                for a in asms:
                    nlv = a.get("normalized_lab_value", {})
                    t_name = nlv.get("canonical_test_name", "Lab Test")
                    val = nlv.get("normalized_value", "")
                    unit = nlv.get("normalized_unit", "")
                    crit = " [CRITICAL ALERT]" if a.get("is_critical") else ""
                    lines.append(f"  - {t_name}: {val} {unit}{crit}")
                return "\n".join(lines)
    except Exception as pe:
        logger.debug("Error loading private decrypted payload for %s: %s", user_id, pe)

    return "User private diagnostic lab report."


def search(
    query_vector: np.ndarray,
    top_k: int,
    category_filter: Optional[List[str]] = None,
    destination: str = "global",
) -> List[Dict[str, Any]]:
    """
    Vector search against the IVFpq FAISS index (and optional private index).

    Parameters
    ----------
    query_vector : np.ndarray, shape=(1, 768), dtype=float32
        L2-normalised query embedding.
    top_k : int
        Number of raw candidates to retrieve.
    category_filter : list of str, optional
        If provided, restrict results to these categories.
    destination : str, default "global"
        Target space ("global" or user_id for private index blending).
    """
    with _lock:
        _load_store()

    if query_vector.dtype != np.float32:
        query_vector = query_vector.astype(np.float32)

    scores, indices = _index.search(query_vector, top_k)
    scores = scores[0]    # (top_k,)
    indices = indices[0]  # (top_k,)

    results = []
    for raw_score, faiss_id in zip(scores, indices):
        if faiss_id < 0:
            continue  # FAISS returns -1 for unfilled slots
        row = _get_sidecar_row(faiss_id)
        if row is None:
            continue
        cat = row["category"]
        if category_filter and cat not in category_filter:
            continue
        row["faiss_score"] = float(raw_score)
        results.append(row)

    # Sort by score descending (FAISS IP metric — higher is better)
    results.sort(key=lambda x: x["faiss_score"], reverse=True)

    # Blending private user hits when destination != "global"
    if destination != "global":
        priv_index_path = settings.private_store_dir / destination / "faiss" / "private_faiss.index"
        if priv_index_path.exists():
            try:
                priv_idx = faiss.read_index(str(priv_index_path))
                p_scores, p_indices = priv_idx.search(query_vector, min(top_k, priv_idx.ntotal))
                snippet = _build_private_user_snippet(destination)
                for p_score in p_scores[0]:
                    results.insert(0, {
                        "faiss_id": -99,
                        "chunk_id": f"private_{destination}_c0",
                        "document_id": f"private_store/{destination}/report",
                        "category": "private_report",
                        "subcategory": "user_report",
                        "source": f"Private_User_Report_{destination}",
                        "title": f"User Diagnostic Report ({destination})",
                        "chunk_type": "body",
                        "token_count": len(snippet.split()),
                        "faiss_score": float(p_score) + 0.5,
                        "text_snippet": snippet,
                    })
            except Exception as pe:
                logger.warning("Private FAISS search for user %s failed: %s", destination, pe)

    return results


def load_chunk_text(faiss_id: int) -> str:
    """
    O(1) random access into chunks.jsonl using precomputed byte offsets.

    Returns the chunk's 'text' field (or empty string if unavailable).
    """
    with _lock:
        _load_store()

    if faiss_id < 0 or faiss_id >= len(_offsets):
        logger.warning("faiss_id %d out of range", faiss_id)
        return ""

    offset = int(_offsets[faiss_id])
    _chunks_fh.seek(offset)
    raw_line = _chunks_fh.readline()
    if not raw_line:
        return ""

    try:
        chunk_data = json.loads(raw_line)
        return chunk_data.get("text", "") or ""
    except json.JSONDecodeError as e:
        logger.warning("Failed to parse chunk at offset %d: %s", offset, e)
        return ""


def batch_load_chunk_texts(faiss_ids: List[int]) -> Dict[int, str]:
    """
    Load chunk texts for multiple faiss_ids efficiently.
    Sorted by offset to minimise seeks.
    """
    id_to_text: Dict[int, str] = {}
    sorted_ids = sorted(faiss_ids, key=lambda fid: int(_offsets[fid]) if 0 <= fid < len(_offsets) else 0)

    with _lock:
        _load_store()

    for fid in sorted_ids:
        id_to_text[fid] = load_chunk_text(fid)

    return id_to_text


def get_metadata(faiss_id: int) -> Optional[Dict[str, Any]]:
    """Return the sidecar metadata dict for a faiss_id (no text load)."""
    with _lock:
        _load_store()
    return _get_sidecar_row(faiss_id)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _get_sidecar_row(faiss_id: int) -> Optional[Dict[str, Any]]:
    """Retrieve a sidecar row by faiss_id (1:1 position in arrow table)."""
    if _sidecar is None or faiss_id < 0 or faiss_id >= len(_sidecar):
        return None

    row = _sidecar.slice(faiss_id, 1).to_pydict()
    return {col: row[col][0] for col in row}


def ntotal() -> int:
    """Return the total number of indexed vectors."""
    with _lock:
        _load_store()
    return _index.ntotal
