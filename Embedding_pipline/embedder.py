"""
MedGraphRAG — Step 3 + 4: Embedding + FAISS Index Builder
==========================================================
Stage A (GPU): Load MedCPT-Article-Encoder, embed chunks.jsonl in batches.
  - L2-normalize every vector (METRIC_INNER_PRODUCT → cosine similarity).
  - Write vectors to a pre-allocated memory-mapped .npy file (never holds all
    vectors in RAM at once from Python side).
  - Write id_mapping.jsonl incrementally (append-only).
  - Checkpoint after every batch; fully resumable.
  - VRAM guard: halve batch_size when free < 1.5 GB; CPU fallback on OOM.

Stage B (CPU): Build FAISS index from the memory-mapped embeddings file.
  - RAM guard: free RAM < 10 GB or < 1.5× vector set size → IVFpq.
    Otherwise → HNSWFlat.
  - Add vectors in slices of 50k to avoid RAM spikes.
  - Save: faiss.index, id_mapping.jsonl (already on disk), id_mapping.parquet,
    build_report.json.

Stage C (CPU): 5 spot queries with MedCPT-Query-Encoder to verify quality.
"""

from __future__ import annotations

import gc
import json
import logging
import os
import signal
import sys
import time
import traceback
from pathlib import Path
from typing import Iterator, List, Optional, Tuple

import numpy as np
import psutil
import torch

# ── Paths ─────────────────────────────────────────────────────────────────────
BASE        = Path("/home/dicksone/Documents/MedGraphRag")
INDEX_DIR   = BASE / "index" / "global"
CHUNKS_FILE = INDEX_DIR / "chunks.jsonl"
EMBED_FILE  = INDEX_DIR / "embeddings.npy"       # memory-mapped float32 (N, 768)
IDMAP_FILE  = INDEX_DIR / "id_mapping.jsonl"
IDMAP_PAR   = INDEX_DIR / "id_mapping.parquet"
FAISS_FILE  = INDEX_DIR / "faiss.index"
CKPT_FILE   = INDEX_DIR / "embed_checkpoint.json"
REPORT_FILE = INDEX_DIR / "build_report.json"
LOGS_DIR    = INDEX_DIR / "logs"
FAILED_LOG  = LOGS_DIR  / "failed_embed.jsonl"
PROG_LOG    = LOGS_DIR  / "embed_progress.log"

CHUNKS_CKPT = INDEX_DIR / "chunks_checkpoint.json"  # from chunker (has chunk_count)

# ── Config ────────────────────────────────────────────────────────────────────
EMBED_MODEL_CORPUS = "ncbi/MedCPT-Article-Encoder"
EMBED_MODEL_QUERY  = "ncbi/MedCPT-Query-Encoder"
VECTOR_DIM         = 768
MAX_SEQ_LEN        = 512
BATCH_SIZE_INIT    = 32      # will halve on VRAM pressure
VRAM_RESERVE_GB    = 1.5
RAM_RESERVE_GB     = 2.0
GC_EVERY_N_BATCHES = 25
HNSW_M             = 32
HNSW_EF_CONSTRUCT  = 200
HNSW_EF_SEARCH     = 128
IVFPQ_NLIST        = 4096
IVFPQ_M            = 96      # subquantizers (768 / 96 = 8 dims per sub)
IVFPQ_NBITS        = 8
RAM_HNSW_THRESHOLD_GB = 10.0  # if free RAM < this → prefer IVFpq

# Spot query sentences for Stage C validation
SPOT_QUERIES = [
    "What are the critical blood glucose levels requiring immediate intervention?",
    "Recommended antibiotic treatment for community-acquired pneumonia",
    "Normal range for serum creatinine in adult males",
    "Rabies pre-exposure prophylaxis vaccination schedule",
    "Hypocalcemia-induced seizure pathophysiology and management",
]

# ── Logging ───────────────────────────────────────────────────────────────────
os.makedirs(LOGS_DIR, exist_ok=True)
os.makedirs(INDEX_DIR, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.FileHandler(PROG_LOG), logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger(__name__)


# ── Graceful shutdown ──────────────────────────────────────────────────────────
_shutdown = False
def _handle_sig(sig, frame):
    global _shutdown
    log.warning("SIGNAL received — will stop cleanly after current batch.")
    _shutdown = True
signal.signal(signal.SIGINT,  _handle_sig)
signal.signal(signal.SIGTERM, _handle_sig)


# ── Memory helpers ────────────────────────────────────────────────────────────
def free_ram_gb() -> float:
    return psutil.virtual_memory().available / 1024**3

def free_vram_gb() -> float:
    if not torch.cuda.is_available():
        return 0.0
    free, _ = torch.cuda.mem_get_info(0)
    return free / 1024**3

def ram_guard():
    """Flush GC if RAM is running low."""
    if free_ram_gb() < RAM_RESERVE_GB:
        log.warning(f"RAM low ({free_ram_gb():.1f} GB free) — forcing gc.collect()")
        gc.collect()

def peak_vram_gb() -> float:
    if not torch.cuda.is_available():
        return 0.0
    return torch.cuda.max_memory_allocated(0) / 1024**3


# ── Checkpoint helpers ────────────────────────────────────────────────────────
def load_ckpt() -> dict:
    if CKPT_FILE.exists():
        with open(CKPT_FILE) as f:
            return json.load(f)
    return {"next_chunk_idx": 0, "n_embedded": 0, "batch_size": BATCH_SIZE_INIT}

def save_ckpt(ckpt: dict):
    with open(CKPT_FILE, "w") as f:
        json.dump(ckpt, f, indent=2)


# ── Chunk count from chunker checkpoint ───────────────────────────────────────
def total_chunk_count() -> int:
    with open(CHUNKS_CKPT) as f:
        return json.load(f)["chunk_count"]


# ── Chunk iterator (streaming, never loads full file) ─────────────────────────
def iter_chunks_from(start_idx: int) -> Iterator[Tuple[int, dict]]:
    """Yield (global_idx, chunk) from chunks.jsonl starting at start_idx."""
    with open(CHUNKS_FILE, encoding="utf-8") as f:
        for i, line in enumerate(f):
            if i < start_idx:
                continue
            yield i, json.loads(line)


def make_batches(start_idx: int, batch_size: int) -> Iterator[Tuple[List[int], List[dict]]]:
    """Yield (indices, chunks) in batches."""
    buf_idx:    List[int]  = []
    buf_chunks: List[dict] = []
    for idx, chunk in iter_chunks_from(start_idx):
        buf_idx.append(idx)
        buf_chunks.append(chunk)
        if len(buf_chunks) >= batch_size:
            yield buf_idx, buf_chunks
            buf_idx, buf_chunks = [], []
    if buf_chunks:
        yield buf_idx, buf_chunks


# ── L2 normalizer ─────────────────────────────────────────────────────────────
def l2_normalize(vecs: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(vecs, axis=1, keepdims=True)
    norms = np.where(norms == 0, 1.0, norms)
    return (vecs / norms).astype(np.float32)


# ─────────────────────────────────────────────────────────────────────────────
#  STAGE A — Embedding
# ─────────────────────────────────────────────────────────────────────────────
def run_embedding():
    global _shutdown

    ckpt         = load_ckpt()
    n_total      = total_chunk_count()
    start_idx    = ckpt["next_chunk_idx"]
    n_embedded   = ckpt["n_embedded"]
    batch_size   = ckpt.get("batch_size", BATCH_SIZE_INIT)

    log.info(f"Total chunks: {n_total:,} | Already embedded: {n_embedded:,} | Resuming from idx {start_idx}")

    # Pre-allocate memory-mapped embeddings file
    # If resuming, open in r+ mode (don't clobber existing data)
    mode = "r+" if EMBED_FILE.exists() and n_embedded > 0 else "w+"
    emb_map = np.memmap(str(EMBED_FILE), dtype="float32", mode=mode,
                        shape=(n_total, VECTOR_DIM))
    log.info(f"Memory-mapped embeddings file: {EMBED_FILE} ({n_total:,} × {VECTOR_DIM}), mode={mode}")

    # Open id_mapping in append mode (idempotent on resume)
    idmap_fh = open(IDMAP_FILE, "a", encoding="utf-8") if n_embedded > 0 else open(IDMAP_FILE, "w", encoding="utf-8")

    # Load model
    log.info(f"Loading {EMBED_MODEL_CORPUS} ...")
    from transformers import AutoTokenizer, AutoModel

    device = "cuda" if torch.cuda.is_available() else "cpu"
    tokenizer = AutoTokenizer.from_pretrained(EMBED_MODEL_CORPUS)
    model     = AutoModel.from_pretrained(EMBED_MODEL_CORPUS).to(device)
    model.eval()
    torch.cuda.reset_peak_memory_stats()
    log.info(f"Model loaded on {device}. VRAM free: {free_vram_gb():.2f} GB")

    start_time   = time.time()
    batch_n      = 0
    failed_count = 0

    try:
        for batch_indices, batch_chunks in make_batches(start_idx, batch_size):
            if _shutdown:
                log.warning("Shutdown — flushing and exiting embedding stage.")
                break

            # VRAM guard
            vfree = free_vram_gb()
            if vfree < VRAM_RESERVE_GB and batch_size > 1:
                batch_size = max(1, batch_size // 2)
                log.warning(f"VRAM {vfree:.2f} GB < {VRAM_RESERVE_GB} GB → batch_size halved to {batch_size}")

            # RAM guard
            ram_guard()

            texts = [c.get("text", "") for c in batch_chunks]
            texts = [t if t else " " for t in texts]  # never empty strings

            # Embed batch
            try:
                with torch.no_grad():
                    enc = tokenizer(
                        texts,
                        max_length=MAX_SEQ_LEN,
                        padding=True,
                        truncation=True,
                        return_tensors="pt",
                    )
                    enc = {k: v.to(device) for k, v in enc.items()}
                    out = model(**enc)
                    # CLS token representation
                    vecs_gpu = out.last_hidden_state[:, 0, :]
                    vecs_np  = vecs_gpu.cpu().float().numpy()
                    del out, vecs_gpu, enc

            except RuntimeError as e:
                if "out of memory" in str(e).lower():
                    torch.cuda.empty_cache()
                    if batch_size > 1:
                        batch_size = max(1, batch_size // 2)
                        log.warning(f"CUDA OOM — halving batch_size to {batch_size}; retrying next batch")
                    else:
                        log.error("CUDA OOM at batch_size=1 — switching to CPU for remainder")
                        model = model.cpu()
                        device = "cpu"
                    # Re-run this batch on CPU
                    model_cpu = model if device == "cpu" else AutoModel.from_pretrained(EMBED_MODEL_CORPUS)
                    with torch.no_grad():
                        enc = tokenizer(texts, max_length=MAX_SEQ_LEN, padding=True, truncation=True, return_tensors="pt")
                        out = model_cpu(**enc)
                        vecs_np = out.last_hidden_state[:, 0, :].float().numpy()
                        del out, enc
                else:
                    log.error(f"Embedding error (non-OOM): {e}")
                    with open(FAILED_LOG, "a") as fl:
                        for c in batch_chunks:
                            fl.write(json.dumps({"chunk_id": c.get("chunk_id"), "error": str(e)}) + "\n")
                    failed_count += len(batch_chunks)
                    continue

            # L2-normalize
            vecs_norm = l2_normalize(vecs_np)

            # Write to memory-mapped file
            start_emb = n_embedded
            end_emb   = n_embedded + len(vecs_norm)
            emb_map[start_emb:end_emb] = vecs_norm
            del vecs_np, vecs_norm

            # Write id_mapping entries
            for local_i, chunk in enumerate(batch_chunks):
                rec = {
                    "faiss_id":    start_emb + local_i,
                    "chunk_id":    chunk.get("chunk_id", ""),
                    "document_id": chunk.get("document_id", ""),
                    "category":    chunk.get("category", ""),
                    "subpath":     chunk.get("subpath", ""),
                    "subcategory": chunk.get("subcategory", ""),
                    "source":      chunk.get("source", ""),
                    "title":       chunk.get("title", ""),
                    "chunk_type":  chunk.get("chunk_type", "body"),
                    "token_count": chunk.get("token_count", 0),
                }
                idmap_fh.write(json.dumps(rec) + "\n")

            n_embedded += len(batch_chunks)
            batch_n    += 1

            # GC every N batches
            if batch_n % GC_EVERY_N_BATCHES == 0:
                gc.collect()
                if device == "cuda":
                    torch.cuda.empty_cache()

            # Checkpoint
            ckpt_now = {
                "next_chunk_idx": batch_indices[-1] + 1,
                "n_embedded":     n_embedded,
                "batch_size":     batch_size,
            }
            save_ckpt(ckpt_now)
            idmap_fh.flush()

            # Progress every 500 batches
            if batch_n % 100 == 0:
                elapsed = time.time() - start_time
                rate    = n_embedded / elapsed if elapsed > 0 else 0
                eta     = (n_total - n_embedded) / rate / 60 if rate > 0 else 0
                log.info(
                    f"Embedded {n_embedded:,}/{n_total:,} "
                    f"| batch_size={batch_size} "
                    f"| VRAM free={free_vram_gb():.1f}GB "
                    f"| RAM free={free_ram_gb():.1f}GB "
                    f"| {rate:.0f} chunks/s "
                    f"| ETA {eta:.1f} min"
                )

    finally:
        idmap_fh.close()
        del emb_map   # flush mmap to disk

    # Offload model from GPU — MUST happen before FAISS build
    log.info("Offloading model from GPU ...")
    del model, tokenizer
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
    gc.collect()

    peak_vram = peak_vram_gb()
    elapsed   = time.time() - start_time
    log.info(f"Embedding stage complete: {n_embedded:,} vectors | peak VRAM {peak_vram:.2f} GB | {elapsed/60:.1f} min")

    return n_embedded, batch_n, peak_vram, failed_count


# ─────────────────────────────────────────────────────────────────────────────
#  STAGE B — FAISS Index Build
# ─────────────────────────────────────────────────────────────────────────────
def build_faiss(n_vectors: int) -> Tuple[str, dict]:
    """Build FAISS index from memory-mapped embeddings. Returns (index_type, metrics)."""
    import faiss

    log.info(f"Building FAISS index from {EMBED_FILE} ({n_vectors:,} × {VECTOR_DIM}) ...")
    log.info(f"Free RAM before FAISS build: {free_ram_gb():.2f} GB")

    # Load memory-mapped read-only
    emb_map = np.memmap(str(EMBED_FILE), dtype="float32", mode="r", shape=(n_vectors, VECTOR_DIM))

    # ── Index type decision ──────────────────────────────────────────────────
    vecs_size_gb  = n_vectors * VECTOR_DIM * 4 / 1024**3
    ram_free      = free_ram_gb()
    # HNSW needs: vectors + graph (~1.5× vectors overhead)
    hnsw_needed   = vecs_size_gb * 2.5
    use_hnsw      = (ram_free > RAM_HNSW_THRESHOLD_GB) and (ram_free > hnsw_needed)

    if use_hnsw:
        index_type = "HNSWFlat"
        log.info(f"RAM {ram_free:.1f} GB free, HNSW needs ~{hnsw_needed:.1f} GB → using IndexHNSWFlat")
        index = faiss.IndexHNSWFlat(VECTOR_DIM, HNSW_M, faiss.METRIC_INNER_PRODUCT)
        index.hnsw.efConstruction = HNSW_EF_CONSTRUCT
        index.hnsw.efSearch       = HNSW_EF_SEARCH
    else:
        index_type = "IVFpq"
        log.info(
            f"RAM {ram_free:.1f} GB free (threshold {RAM_HNSW_THRESHOLD_GB} GB) "
            f"or HNSW needs {hnsw_needed:.1f} GB → using IndexIVFPQ"
        )
        quantizer = faiss.IndexFlatIP(VECTOR_DIM)
        index = faiss.IndexIVFPQ(
            quantizer, VECTOR_DIM, IVFPQ_NLIST, IVFPQ_M, IVFPQ_NBITS,
            faiss.METRIC_INNER_PRODUCT
        )
        # Train on a sample (IVFpq needs training; HNSW does not)
        n_train  = min(max(10 * IVFPQ_NLIST, 100_000), n_vectors)
        indices  = np.random.choice(n_vectors, n_train, replace=False)
        indices.sort()
        log.info(f"Training IVFpq on {n_train:,} sample vectors ...")
        train_data = np.array(emb_map[indices], dtype=np.float32)
        faiss.normalize_L2(train_data)   # ensure unit norm (already done but be safe)
        index.train(train_data)
        del train_data
        gc.collect()

    # ── Add vectors in slices to control RAM ─────────────────────────────────
    SLICE = 50_000
    t0 = time.time()
    for start in range(0, n_vectors, SLICE):
        end  = min(start + SLICE, n_vectors)
        slab = np.array(emb_map[start:end], dtype=np.float32)
        index.add(slab)
        del slab
        if start % 500_000 == 0:
            log.info(f"  Added {end:,}/{n_vectors:,} vectors | RAM free {free_ram_gb():.1f} GB")
        ram_guard()

    del emb_map
    gc.collect()

    build_time = time.time() - t0
    log.info(f"FAISS build done: {index.ntotal:,} vectors | {build_time:.1f} s")

    # Save index
    faiss.write_index(index, str(FAISS_FILE))
    log.info(f"Index saved → {FAISS_FILE} ({FAISS_FILE.stat().st_size/1024**2:.1f} MB)")

    # ── Convert id_mapping to Parquet ─────────────────────────────────────────
    log.info("Converting id_mapping.jsonl → id_mapping.parquet ...")
    import pyarrow as pa
    import pyarrow.parquet as pq

    cols = {
        "faiss_id": [], "chunk_id": [], "document_id": [],
        "category": [], "subpath": [], "subcategory": [],
        "source": [], "title": [], "chunk_type": [], "token_count": []
    }
    with open(IDMAP_FILE) as f:
        for line in f:
            rec = json.loads(line)
            for k in cols:
                cols[k].append(rec.get(k))

    table = pa.table({k: pa.array(v) for k, v in cols.items()})
    pq.write_table(table, str(IDMAP_PAR))
    log.info(f"Parquet saved → {IDMAP_PAR} ({IDMAP_PAR.stat().st_size/1024**2:.1f} MB)")

    metrics = {
        "index_type":    index_type,
        "n_vectors":     int(index.ntotal),
        "vector_dim":    VECTOR_DIM,
        "metric":        "METRIC_INNER_PRODUCT (cosine after L2-normalize)",
        "normalization": "L2 pre-normalized",
        "build_time_s":  round(build_time, 1),
        "faiss_size_mb": round(FAISS_FILE.stat().st_size / 1024**2, 1),
        "hnsw_M":        HNSW_M if index_type == "HNSWFlat" else None,
        "hnsw_efC":      HNSW_EF_CONSTRUCT if index_type == "HNSWFlat" else None,
        "hnsw_efS":      HNSW_EF_SEARCH if index_type == "HNSWFlat" else None,
        "ivfpq_nlist":   IVFPQ_NLIST if index_type == "IVFpq" else None,
        "ivfpq_m":       IVFPQ_M if index_type == "IVFpq" else None,
        "ivfpq_nbits":   IVFPQ_NBITS if index_type == "IVFpq" else None,
        "ram_free_at_build_gb": round(free_ram_gb(), 2),
    }
    return index_type, metrics, index


# ─────────────────────────────────────────────────────────────────────────────
#  STAGE C — 5 Spot Queries
# ─────────────────────────────────────────────────────────────────────────────
def run_spot_queries(index, n_vectors: int):
    """Encode 5 queries with the Query Encoder and search the FAISS index."""
    log.info("=== STAGE C: 5 Spot Queries ===")

    import faiss as _faiss
    from transformers import AutoTokenizer, AutoModel

    device    = "cuda" if torch.cuda.is_available() else "cpu"
    log.info(f"Loading query encoder on {device} ...")
    q_tok   = AutoTokenizer.from_pretrained(EMBED_MODEL_QUERY)
    q_model = AutoModel.from_pretrained(EMBED_MODEL_QUERY).to(device)
    q_model.eval()

    # Load id_mapping into a dict for result lookup (sample read, not full load)
    # Use parquet for efficient random access
    import pyarrow.parquet as pq
    imap_tbl = pq.read_table(str(IDMAP_PAR), columns=["faiss_id","chunk_id","category","source","title"])
    imap_faid  = imap_tbl["faiss_id"].to_pylist()
    imap_cid   = imap_tbl["chunk_id"].to_pylist()
    imap_cat   = imap_tbl["category"].to_pylist()
    imap_src   = imap_tbl["source"].to_pylist()
    imap_title = imap_tbl["title"].to_pylist()
    # index by faiss_id for O(1) lookup
    id_lookup  = {fid: (cid, cat, src, title)
                  for fid, cid, cat, src, title
                  in zip(imap_faid, imap_cid, imap_cat, imap_src, imap_title)}
    del imap_tbl, imap_faid, imap_cid, imap_cat, imap_src, imap_title

    results = []
    for q in SPOT_QUERIES:
        with torch.no_grad():
            enc = q_tok([q], max_length=MAX_SEQ_LEN, padding=True,
                        truncation=True, return_tensors="pt")
            enc = {k: v.to(device) for k, v in enc.items()}
            out = q_model(**enc)
            qvec = out.last_hidden_state[:, 0, :].cpu().float().numpy()
            del out, enc

        qvec = l2_normalize(qvec)
        D, I = index.search(qvec, 5)  # top-5

        hits = []
        for score, fid in zip(D[0], I[0]):
            if fid == -1:
                continue
            cid, cat, src, title = id_lookup.get(int(fid), ("?","?","?","?"))
            hits.append({"faiss_id": int(fid), "score": round(float(score), 4),
                         "chunk_id": cid, "category": cat, "source": src, "title": str(title)[:80]})
        results.append({"query": q, "top5": hits})

    del q_model, q_tok, id_lookup
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
    gc.collect()

    print("\n" + "="*70)
    print("SPOT QUERY RESULTS")
    print("="*70)
    for r in results:
        print(f"\nQ: {r['query']}")
        for h in r["top5"]:
            print(f"  [{h['score']:.4f}] [{h['category']}] {h['chunk_id'][:80]}")
    print("="*70)
    return results


# ─────────────────────────────────────────────────────────────────────────────
#  MAIN
# ─────────────────────────────────────────────────────────────────────────────
def main():
    t_start = time.time()

    # ── Stage A: Embedding ─────────────────────────────────────────────────
    n_embedded, n_batches, peak_vram, n_failed = run_embedding()

    if _shutdown:
        log.warning("Interrupted after embedding — run again to resume and continue to FAISS build.")
        return

    peak_ram_embed = round(
        (psutil.virtual_memory().total - psutil.virtual_memory().available) / 1024**3, 2
    )

    # ── Stage B: FAISS ─────────────────────────────────────────────────────
    index_type, faiss_metrics, index = build_faiss(n_embedded)

    # ── Stage C: Spot Queries ──────────────────────────────────────────────
    spot_results = run_spot_queries(index, n_embedded)
    del index

    # ── Build Report ───────────────────────────────────────────────────────
    total_elapsed = time.time() - t_start
    report = {
        "embed_model":    EMBED_MODEL_CORPUS,
        "query_model":    EMBED_MODEL_QUERY,
        "vector_dim":     VECTOR_DIM,
        "normalization":  "L2 pre-normalized",
        "metric":         "METRIC_INNER_PRODUCT (cosine)",
        "n_chunks_total": total_chunk_count(),
        "n_embedded":     n_embedded,
        "n_failed_embed": n_failed,
        "n_batches":      n_batches,
        "peak_vram_gb":   round(peak_vram, 2),
        "peak_ram_gb":    peak_ram_embed,
        "total_time_min": round(total_elapsed / 60, 1),
        **faiss_metrics,
        "spot_queries":   spot_results,
        "status":         "COMPLETE",
    }
    with open(REPORT_FILE, "w") as f:
        json.dump(report, f, indent=2)
    log.info(f"Build report saved → {REPORT_FILE}")

    # ── Final Summary ───────────────────────────────────────────────────────
    log.info("=" * 60)
    log.info("STEP 3+4 COMPLETE — Embedding + FAISS Index")
    log.info(f"  Vectors embedded   : {n_embedded:,}")
    log.info(f"  FAISS index type   : {index_type}")
    log.info(f"  Metric             : METRIC_INNER_PRODUCT (cosine, L2-norm)")
    log.info(f"  Index size         : {faiss_metrics['faiss_size_mb']} MB")
    log.info(f"  Peak VRAM          : {peak_vram:.2f} GB")
    log.info(f"  Peak RAM (embed)   : {peak_ram_embed:.2f} GB")
    log.info(f"  Failures           : {n_failed}")
    log.info(f"  Total time         : {total_elapsed/60:.1f} min")
    log.info(f"  Output files:")
    log.info(f"    {EMBED_FILE}")
    log.info(f"    {FAISS_FILE}")
    log.info(f"    {IDMAP_FILE}")
    log.info(f"    {IDMAP_PAR}")
    log.info(f"    {REPORT_FILE}")
    log.info("=" * 60)
    log.info("DO NOT start graph build until you have reviewed the spot query results above.")
    log.info("=" * 60)


if __name__ == "__main__":
    main()
