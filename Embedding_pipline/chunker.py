"""
MedGraphRAG — Step 2: Full-Scale Chunking Engine
=================================================
CPU-only. No GPU, no ML models. One document loaded into RAM at a time.
All output written incrementally to disk (streaming). Fully checkpointed.

Chunk rules (approved in Step 2 Gate):
  - Standard docs: sentence-boundary chunking, 300–500 tokens, 15% overlap,
    numeric/table blocks kept atomic (hard max 800 tokens).
  - Abstract: emitted as its own chunk_type=abstract before body chunks.
  - Figures with ocr_text: emitted as chunk_type=figure.
  - Dense structured tables (lab_reference, drug structured rows):
      → verbalize each row into natural-language micro-chunk (one per row).
      → Do NOT also emit the >512-token block into FAISS.
      → Full structured_data still flows to Kùzu Graph unchanged (this step
        only produces FAISS chunks).
  - ontology / qa_benchmark / target=none → NEVER chunked here.
"""

from __future__ import annotations

import gc
import json
import logging
import math
import os
import re
import signal
import sys
import time
import traceback
from dataclasses import dataclass, field
from pathlib import Path
from typing import Generator, Iterator, List, Optional, Tuple

# ── Paths ────────────────────────────────────────────────────────────────────
BASE_DIR   = Path("/home/dicksone/Documents/MedGraphRag")
NORM_DIR   = BASE_DIR / "Datasets" / "normalized"
INDEX_DIR  = BASE_DIR / "index" / "global"
MANIFEST   = BASE_DIR / "Embedding_pipline" / "manifest.jsonl"

# Outputs
CHUNKS_PATH     = INDEX_DIR / "chunks.jsonl"
CHECKPOINT_PATH = INDEX_DIR / "chunks_checkpoint.json"
LOGS_DIR        = INDEX_DIR / "logs"
FAILED_LOG      = LOGS_DIR / "failed_chunking.jsonl"
PROGRESS_LOG    = LOGS_DIR / "chunking_progress.log"

# ── Config (master prompt §1) ─────────────────────────────────────────────────
CHUNK_MIN_TOKENS      = 300
CHUNK_MAX_TOKENS      = 500
CHUNK_OVERLAP_RATIO   = 0.15
CHUNK_HARD_MAX_TOKENS = 800
LANGUAGES_KEEP        = {"en"}

# Checkpoint every N documents to survive crashes
CHECKPOINT_EVERY = 500

# ── Logging ───────────────────────────────────────────────────────────────────
os.makedirs(LOGS_DIR, exist_ok=True)
os.makedirs(INDEX_DIR, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(PROGRESS_LOG),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger(__name__)


# ── Graceful shutdown ────────────────────────────────────────────────────────
_shutdown_requested = False

def _handle_signal(sig, frame):
    global _shutdown_requested
    log.warning("SHUTDOWN SIGNAL received — will flush and stop cleanly after current document.")
    _shutdown_requested = True

signal.signal(signal.SIGINT,  _handle_signal)
signal.signal(signal.SIGTERM, _handle_signal)


# ── Token counter ─────────────────────────────────────────────────────────────
def count_tokens(text: str) -> int:
    """Rough token count: word count × 1.3 (matches MedCPT tokenizer heuristic)."""
    return max(1, int(len(text.split()) * 1.3))


# ── Medical numeric safety ────────────────────────────────────────────────────
MEDICAL_NUM_RE = re.compile(
    r"("
    r"\d+\s*[-–]\s*\d+"                  # ranges: 120–180
    r"|\d+\.?\d*\s*(?:"
        r"mg|mL|mcg|µg|IU|mmol|mEq|kg|g|L|dL|µL|U/L|pg|ng|nmol|mmHg|bpm|%"
        r"|sec|min|ms|ug|meq|mosm|mOsm|mEq/L|g/dL|ng/mL|µmol/L|pmol"
    r")\b"
    r"|\bTable\s+\d+"                     # Table N references
    r"|\|\s*\w"                           # Pipe-table rows
    r"|\d+\.\d+\s+\w{2,}"                # decimal + unit-like token
    r")",
    re.IGNORECASE,
)

def is_numeric_dense(text: str) -> bool:
    return bool(MEDICAL_NUM_RE.search(text))


# ── Sentence splitter ─────────────────────────────────────────────────────────
def split_sentences(text: str) -> List[str]:
    """Split at sentence boundaries (.!?) and paragraph breaks."""
    paras = re.split(r"\n{2,}", text)
    out: List[str] = []
    for para in paras:
        sents = re.split(r"(?<=[.!?])\s+(?=[A-Z\-\d\"\(])", para.strip())
        out.extend(s.strip() for s in sents if s.strip())
        out.append("\n\n")
    return [s for s in out if s.strip()]


# ── Numeric-line merger ───────────────────────────────────────────────────────
def merge_numeric_blocks(lines: List[str]) -> List[str]:
    """Group consecutive numeric-dense lines into atomic blocks."""
    merged: List[str] = []
    i = 0
    while i < len(lines):
        if is_numeric_dense(lines[i]):
            block = [lines[i]]
            j = i + 1
            while j < len(lines) and (is_numeric_dense(lines[j]) or not lines[j].strip()):
                block.append(lines[j])
                j += 1
            merged.append("\n".join(block))
            i = j
        else:
            merged.append(lines[i])
            i += 1
    return merged


# ── Standard body chunker ─────────────────────────────────────────────────────
def chunk_body(body: str, doc_id: str) -> Tuple[List[dict], List[str]]:
    """
    Chunk a document body into 300–500 token pieces with 15% overlap.
    Never splits mid-sentence or mid-numeric-block.
    Returns (chunks, warnings).
    """
    if not body or not body.strip():
        return [], []

    lines = body.split("\n")
    lines = merge_numeric_blocks(lines)
    sentences = split_sentences("\n".join(lines))

    chunks: List[dict] = []
    warnings: List[str] = []
    cur_sents: List[str] = []
    cur_tokens = 0
    n = 0

    def flush(chunk_type: str = "body"):
        nonlocal n, cur_sents, cur_tokens
        if not cur_sents:
            return
        text = " ".join(cur_sents)
        tok = count_tokens(text)
        if tok > CHUNK_HARD_MAX_TOKENS:
            warnings.append(f"chunk {n}: {tok} tokens (numeric block hard-max exceeded, kept atomic)")
        chunks.append({
            "chunk_id":   f"{doc_id}__c{n}",
            "chunk_type": chunk_type,
            "text":       text,
            "token_count": tok,
        })
        n += 1
        cur_sents = []
        cur_tokens = 0

    for sent in sentences:
        if not sent.strip():
            continue
        st = count_tokens(sent)

        # Atomic numeric block that is already huge — emit alone
        if is_numeric_dense(sent) and st > CHUNK_MAX_TOKENS:
            if cur_sents:
                flush()
            cur_sents = [sent]
            cur_tokens = st
            flush()
            continue

        if cur_tokens + st > CHUNK_MAX_TOKENS and cur_tokens >= CHUNK_MIN_TOKENS:
            flush()
            # Carry 15% overlap from previous chunk
            if chunks:
                prev_words = chunks[-1]["text"].split()
                n_overlap  = int(len(prev_words) * CHUNK_OVERLAP_RATIO)
                if n_overlap > 0:
                    overlap_text = " ".join(prev_words[-n_overlap:])
                    cur_sents    = [overlap_text]
                    cur_tokens   = count_tokens(overlap_text)

        cur_sents.append(sent)
        cur_tokens += st

    if cur_sents:
        flush()

    return chunks, warnings


# ── Row verbalizer (structured tables → natural-language micro-chunks) ─────────
def _val(v) -> str:
    """Return string value or empty string for nan/None/NaN."""
    if v is None:
        return ""
    s = str(v).strip()
    if s.lower() in ("nan", "none", "null", ""):
        return ""
    return s


def verbalize_lab_critical_row(row: list, headers: list, doc_id: str, source: str, n: int) -> Optional[dict]:
    """
    Critical-values table verbalizer.
    Headers: Test Name, Category, Specimen, Normal Low, Normal High,
             Critical Low, Critical High, Unit, Age Group, Gender,
             Clinical Interpretation, Source Document, Page Number
    """
    h = {hdr: _val(row[i]) for i, hdr in enumerate(headers) if i < len(row)}

    test_name = h.get("Test Name", "")
    if not test_name:
        return None

    parts: List[str] = []
    category   = h.get("Category", "")
    specimen   = h.get("Specimen", "")
    unit       = h.get("Unit", "")
    age_group  = h.get("Age Group", "")
    gender     = h.get("Gender", "")
    norm_lo    = h.get("Normal Low", "")
    norm_hi    = h.get("Normal High", "")
    crit_lo    = h.get("Critical Low", "")
    crit_hi    = h.get("Critical High", "")
    interp     = h.get("Clinical Interpretation", "")

    # Header phrase
    ctx_parts = [p for p in [category, specimen] if p]
    header_phrase = f"{test_name} ({', '.join(ctx_parts)})" if ctx_parts else test_name

    # Normal range
    if norm_lo and norm_hi:
        range_str = f"{norm_lo}–{norm_hi} {unit}".strip()
        parts.append(f"normal range {range_str}")
    elif norm_lo:
        parts.append(f"normal low {norm_lo} {unit}".strip())
    elif norm_hi:
        parts.append(f"normal high {norm_hi} {unit}".strip())

    # Critical values
    if crit_lo:
        parts.append(f"critical low {crit_lo} {unit}".strip())
    if crit_hi:
        parts.append(f"critical high {crit_hi} {unit}".strip())

    # Skip rows with no values at all (qualitative-only rows go to graph, not FAISS)
    if not parts:
        return None

    # Context qualifiers
    qualifiers = [p for p in [age_group, gender] if p]
    if qualifiers:
        parts.append(f"for {', '.join(qualifiers)}")

    if interp:
        sentence = f"{header_phrase}: {'; '.join(parts)}. {interp}"
    else:
        sentence = f"{header_phrase}: {'; '.join(parts)}."

    tok = count_tokens(sentence)
    return {
        "chunk_id":   f"{doc_id}__row{n}",
        "chunk_type": "structured_row",
        "text":       sentence,
        "token_count": tok,
    }


def verbalize_loinc_row(row: list, headers: list, doc_id: str, n: int) -> Optional[dict]:
    """
    LOINC reference interval table verbalizer.
    Headers: LOINC, Lab Test, Specimen, Gender-specific, Age group-specific,
             Women-related condition, Category of Lab Test, Other condition,
             Types of reference range, Traditional Reference Interval,
             Traditional Units, Conversion Factor, SI Reference Interval, SI Units, ...
    """
    h = {hdr: _val(row[i]) for i, hdr in enumerate(headers) if i < len(row)}

    lab_test = h.get("Lab Test", "")
    if not lab_test:
        return None

    loinc    = h.get("LOINC", "")
    specimen = h.get("Specimen", "")
    ref_type = h.get("Types of reference range", "")
    trad_int = h.get("Traditional Reference Interval", "")
    trad_u   = h.get("Traditional Units", "")
    si_int   = h.get("SI Reference Interval", "")
    si_u     = h.get("SI Units", "")
    gender   = h.get("Gender-specific", "")
    age_grp  = h.get("Age group-specific", "")
    condition= h.get("Women-related condition", "") or h.get("Other condition", "")

    # Build sentence
    parts: List[str] = []
    ctx = [p for p in [specimen, gender, age_grp, condition] if p]
    loinc_str = f" (LOINC: {loinc})" if loinc else ""

    header_phrase = f"{lab_test}{loinc_str}"
    if ctx:
        header_phrase += f" ({', '.join(ctx)})"

    if ref_type:
        parts.append(f"reference type: {ref_type}")
    if trad_int and trad_u:
        parts.append(f"reference interval {trad_int} {trad_u}")
    elif trad_int:
        parts.append(f"reference interval {trad_int}")
    if si_int and si_u:
        parts.append(f"SI interval {si_int} {si_u}")

    if not parts:
        return None

    sentence = f"{header_phrase}: {'; '.join(parts)}."
    tok = count_tokens(sentence)
    return {
        "chunk_id":   f"{doc_id}__row{n}",
        "chunk_type": "structured_row",
        "text":       sentence,
        "token_count": tok,
    }


def verbalize_generic_row(row: list, headers: list, doc_id: str, source: str, n: int) -> Optional[dict]:
    """
    Generic fallback verbalizer for structured tables with unknown schema.
    Only emit rows with ≥2 non-empty meaningful fields.
    """
    pairs = []
    for i, hdr in enumerate(headers):
        if i >= len(row):
            break
        val = _val(row[i])
        if val and hdr and "Unnamed" not in hdr and "CID" not in hdr:
            pairs.append(f"{hdr}: {val}")

    if len(pairs) < 2:
        return None

    sentence = "; ".join(pairs) + "."
    tok = count_tokens(sentence)
    if tok > CHUNK_MAX_TOKENS:
        # Truncate at sentence boundary — still better than a raw CSV blob
        words = sentence.split()[:int(CHUNK_MAX_TOKENS / 1.3)]
        sentence = " ".join(words) + "…"
        tok = count_tokens(sentence)

    return {
        "chunk_id":   f"{doc_id}__row{n}",
        "chunk_type": "structured_row",
        "text":       sentence,
        "token_count": tok,
    }


def verbalize_table(doc_id: str, category: str, table: dict, source: str) -> Tuple[List[dict], int]:
    """
    Dispatch to the right verbalizer based on table headers.
    Returns (chunks, skipped_count).
    """
    headers = table.get("headers") or []
    rows    = table.get("rows") or []
    chunks: List[dict] = []
    skipped = 0

    h_set = set(headers)
    has_critical   = "Critical Low" in h_set or "Critical High" in h_set
    has_loinc      = "LOINC" in h_set and "Traditional Reference Interval" in h_set

    for n, row in enumerate(rows):
        chunk = None
        if has_critical:
            chunk = verbalize_lab_critical_row(row, headers, doc_id, source, n)
        elif has_loinc:
            chunk = verbalize_loinc_row(row, headers, doc_id, n)
        else:
            chunk = verbalize_generic_row(row, headers, doc_id, source, n)

        if chunk:
            chunks.append(chunk)
        else:
            skipped += 1

    return chunks, skipped


# ── Per-document chunker ───────────────────────────────────────────────────────
def chunk_document(rec: dict) -> Tuple[List[dict], List[str], int]:
    """
    Process one manifest record → list of chunks.
    Loads the document, chunks it, frees memory.
    Returns (chunks, warnings, structured_rows_emitted).
    """
    doc_id   = rec["document_id"]
    category = rec["category"]
    target   = rec["target"]
    language = rec.get("language") or "en"

    filepath = NORM_DIR / (doc_id + ".json")
    if not filepath.exists():
        return [], [f"File not found: {filepath}"], 0

    file_size = filepath.stat().st_size
    if file_size > 50 * 1024 * 1024:
        return [], [f"Large file skipped for chunking (>{file_size//1024//1024} MB). Flows to graph only."], 0

    with open(filepath, "r", encoding="utf-8") as f:
        doc = json.load(f)

    text_obj  = doc.get("text") or {}
    body      = text_obj.get("body") or ""
    abstract  = text_obj.get("abstract")
    figures   = doc.get("figures") or []
    sdata     = doc.get("structured_data") or []
    source    = doc.get("source") or category

    all_chunks: List[dict]  = []
    warnings:   List[str]   = []
    struct_rows = 0

    # ── 1. Abstract chunk ────────────────────────────────────────────────────
    if abstract and str(abstract).strip():
        abs_text = str(abstract).strip()
        all_chunks.append({
            "chunk_id":    f"{doc_id}__abs",
            "chunk_type":  "abstract",
            "text":        abs_text,
            "token_count": count_tokens(abs_text),
        })

    # ── 2. Structured table rows (lab_reference + drug with structured_data) ─
    # Rule: emit verbalized rows instead of the raw block chunks.
    # The raw block is intentionally NOT emitted to FAISS (>512 token truncation issue).
    has_verbalized_table = False
    if sdata and category in ("lab_reference", "drug", "disease", "guideline", "textbook", "research_paper"):
        for table in sdata:
            hdrs = table.get("headers") or []
            rows = table.get("rows") or []
            if not rows or not hdrs:
                continue
            row_chunks, skipped = verbalize_table(doc_id, category, table, source)
            if row_chunks:
                all_chunks.extend(row_chunks)
                struct_rows += len(row_chunks)
                has_verbalized_table = True
                if skipped:
                    warnings.append(f"Verbalized {len(row_chunks)} rows, skipped {skipped} empty/unverbalizable rows.")

    # ── 3. Body chunks (sentence-boundary chunking) ──────────────────────────
    # Skip body chunking for dense structured-table-only lab docs where the body
    # is just a raw CSV dump (high token count, low information density for FAISS).
    skip_body_for_dense_table = (
        has_verbalized_table
        and category == "lab_reference"
        and count_tokens(body) > CHUNK_HARD_MAX_TOKENS
    )

    if body and body.strip() and not skip_body_for_dense_table:
        body_chunks, body_warns = chunk_body(body, doc_id)
        all_chunks.extend(body_chunks)
        warnings.extend(body_warns)

    # ── 4. Figure / OCR chunks ───────────────────────────────────────────────
    for fig_i, fig in enumerate(figures):
        if isinstance(fig, dict):
            ocr = (fig.get("ocr_text") or "").strip()
            if ocr:
                all_chunks.append({
                    "chunk_id":    f"{doc_id}__fig{fig_i}",
                    "chunk_type":  "figure",
                    "text":        ocr,
                    "token_count": count_tokens(ocr),
                    "page_number": fig.get("page_number"),
                })

    # Attach shared metadata to every chunk
    shared_meta = {
        "document_id":  doc_id,
        "category":     category,
        "subpath":      rec.get("subpath", ""),
        "subcategory":  rec.get("subcategory", ""),
        "source":       source,
        "title":        rec.get("title", ""),
        "language":     language,
    }
    for c in all_chunks:
        c.update(shared_meta)

    del doc
    gc.collect()

    return all_chunks, warnings, struct_rows


# ── Checkpoint helpers ────────────────────────────────────────────────────────
def load_checkpoint() -> dict:
    if CHECKPOINT_PATH.exists():
        with open(CHECKPOINT_PATH) as f:
            return json.load(f)
    return {"last_doc_id": None, "processed": 0, "chunk_count": 0, "skipped": 0, "failed": 0}

def save_checkpoint(ckpt: dict):
    with open(CHECKPOINT_PATH, "w") as f:
        json.dump(ckpt, f, indent=2)


# ── Failed-file logger ────────────────────────────────────────────────────────
def log_failure(doc_id: str, category: str, error: str):
    with open(FAILED_LOG, "a") as f:
        f.write(json.dumps({
            "document_id": doc_id,
            "category":    category,
            "error":       error,
            "timestamp":   time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }) + "\n")


# ── Main loop ─────────────────────────────────────────────────────────────────
def main():
    global _shutdown_requested

    ckpt          = load_checkpoint()
    resume_doc_id = ckpt.get("last_doc_id")
    processed     = ckpt.get("processed", 0)
    chunk_count   = ckpt.get("chunk_count", 0)
    skipped       = ckpt.get("skipped", 0)
    failed        = ckpt.get("failed", 0)
    struct_total  = ckpt.get("struct_rows", 0)

    if resume_doc_id:
        log.info(f"Resuming from checkpoint: last_doc_id={resume_doc_id}, "
                 f"processed={processed}, chunks_so_far={chunk_count}")

    # Count total FAISS-bound records for progress display
    total_faiss = 0
    with open(MANIFEST) as f:
        for line in f:
            r = json.loads(line)
            if r.get("target") in ("faiss", "both"):
                total_faiss += 1
    log.info(f"FAISS-bound documents to chunk: {total_faiss:,}")

    start_time   = time.time()
    past_resume  = (resume_doc_id is None)

    # Open chunks.jsonl in append mode (safe for resume)
    with open(CHUNKS_PATH, "a", encoding="utf-8") as chunks_file:
        with open(MANIFEST) as mf:
            for line in mf:
                if _shutdown_requested:
                    log.warning("Shutdown requested — flushing checkpoint and exiting.")
                    break

                rec    = json.loads(line)
                target = rec.get("target", "none")
                doc_id = rec["document_id"]

                # Only chunk FAISS-bound docs
                if target not in ("faiss", "both"):
                    continue

                # Resume: skip docs we already processed
                if not past_resume:
                    if doc_id == resume_doc_id:
                        past_resume = True
                    continue

                # Exclude non-English (may still flow to graph, but no FAISS chunks)
                lang = rec.get("language") or "en"
                if lang not in LANGUAGES_KEEP:
                    skipped += 1
                    continue

                try:
                    chunks, warns, sr = chunk_document(rec)
                except Exception as e:
                    err_msg = traceback.format_exc()
                    log.error(f"FAILED: {doc_id} — {e}")
                    log_failure(doc_id, rec.get("category", ""), err_msg)
                    failed += 1
                    continue

                if warns:
                    for w in warns:
                        log.debug(f"[{doc_id}] {w}")

                for chunk in chunks:
                    chunks_file.write(json.dumps(chunk) + "\n")

                chunk_count   += len(chunks)
                struct_total  += sr
                processed     += 1

                # Progress every 500 docs
                if processed % 500 == 0:
                    elapsed   = time.time() - start_time
                    rate      = processed / elapsed if elapsed > 0 else 0
                    remaining = (total_faiss - processed) / rate if rate > 0 else 0
                    log.info(
                        f"Progress: {processed:,}/{total_faiss:,} docs "
                        f"| {chunk_count:,} chunks "
                        f"| {struct_total:,} verbalized rows "
                        f"| failed: {failed} "
                        f"| {rate:.1f} docs/s "
                        f"| ETA {remaining/60:.1f} min"
                    )

                # Checkpoint every N docs
                if processed % CHECKPOINT_EVERY == 0:
                    ckpt = {
                        "last_doc_id":  doc_id,
                        "processed":    processed,
                        "chunk_count":  chunk_count,
                        "struct_rows":  struct_total,
                        "skipped":      skipped,
                        "failed":       failed,
                    }
                    save_checkpoint(ckpt)
                    chunks_file.flush()

    # Final checkpoint
    save_checkpoint({
        "last_doc_id":  doc_id if processed else None,
        "processed":    processed,
        "chunk_count":  chunk_count,
        "struct_rows":  struct_total,
        "skipped":      skipped,
        "failed":       failed,
        "status":       "COMPLETE" if not _shutdown_requested else "INTERRUPTED",
    })

    elapsed = time.time() - start_time
    log.info("=" * 60)
    log.info("CHUNKING COMPLETE" if not _shutdown_requested else "CHUNKING INTERRUPTED (checkpoint saved)")
    log.info(f"  Documents processed : {processed:,}")
    log.info(f"  Total chunks written: {chunk_count:,}")
    log.info(f"  Verbalized rows     : {struct_total:,}")
    log.info(f"  Skipped (language)  : {skipped}")
    log.info(f"  Failed              : {failed}")
    log.info(f"  Time elapsed        : {elapsed/60:.1f} min")
    log.info(f"  Chunks file         : {CHUNKS_PATH}")
    log.info("=" * 60)


if __name__ == "__main__":
    main()
