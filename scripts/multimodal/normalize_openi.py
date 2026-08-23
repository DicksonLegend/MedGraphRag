#!/usr/bin/env python
"""Stage C-1: OpenI report normalization -> existing MedGraphRAG chunk schema.

Reads NLMCXR_reports.tgz (ecgen-radiology XMLs), emits one JSONL line per
report section chunk:
  {"chunk_id", "document_id", "source", "category": "radiology_report",
   "text", "byte_offset", "token_count", "image_ids"}
Output: data/multimodal/chunks/openi_chunks.jsonl (+ manifest json).
CPU-only, streaming per-member (never holds corpus in RAM), resumable by
skipping document_ids already present in the output file.
"""
import hashlib
import json
import re
import tarfile
import time
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path("/home/dicksone/Documents/MedGraphRag")
TGZ = ROOT / "data/multimodal/reports/NLMCXR_reports.tgz"
OUT_DIR = ROOT / "data/multimodal/chunks"
OUT = OUT_DIR / "openi_chunks.jsonl"

SECTION_TAGS = ("FINDINGS", "INDICATION", "IMPRESSION")


def approx_tokens(text: str) -> int:
    return max(1, round(len(text) / 4))


def clean(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    done: set[str] = set()
    if OUT.exists():
        with open(OUT) as f:
            for line in f:
                try:
                    done.add(json.loads(line)["document_id"])
                except Exception:
                    pass
    mode = "a" if done else "w"
    t0 = time.perf_counter()
    n_docs = n_chunks = 0
    with tarfile.open(TGZ, "r:gz") as tf, open(OUT, mode) as out:
        for member in tf.getmembers():
            if not member.name.endswith(".xml"):
                continue
            fh = tf.extractfile(member)
            if fh is None:
                continue
            doc_id = Path(member.name).stem  # e.g. 1.xml -> "1"
            if doc_id in done:
                continue
            try:
                tree = ET.parse(fh)
            except ET.ParseError as e:
                print(f"WARN parse {member.name}: {e}", flush=True)
                continue
            img_ids = [i.get("id").strip() for i in tree.iter("parentImage")
                       if i.get("id")]
            offset = 0
            for tag in SECTION_TAGS:
                node = tree.find(f".//AbstractText[@Label='{tag}']")
                if node is None or not ((node.text or "").strip() or len(node)):
                    continue
                # text may live in the element or in MeSH/child markup
                raw = "".join(node.itertext())
                text = clean(raw)
                if not text:
                    continue
                cid = hashlib.md5(f"{doc_id}||{tag}".encode()).hexdigest()[:16]
                rec = {
                    "chunk_id": f"openi_{cid}",
                    "document_id": doc_id,
                    "source": "OpenI/NLMCXR",
                    "category": "radiology_report",
                    "section": tag,
                    "text": text,
                    "byte_offset": offset,
                    "token_count": approx_tokens(text),
                    "image_ids": img_ids if tag == "FINDINGS" else [],
                }
                offset += len(rec["text"])
                out.write(json.dumps(rec, ensure_ascii=False) + "\n")
                n_chunks += 1
            n_docs += 1
    dt = time.perf_counter() - t0
    manifest = {
        "stage": "C1_openi_normalization",
        "input": str(TGZ),
        "output": str(OUT),
        "documents_normalized": n_docs,
        "chunks_written": n_chunks,
        "resumed_skipped": len(done),
        "wall_seconds": round(dt, 2),
        "schema": ["chunk_id", "document_id", "source", "category", "section",
                   "text", "byte_offset", "token_count", "image_ids"],
        "artifact_sha256": hashlib.sha256(OUT.read_bytes()).hexdigest() if OUT.exists() else None,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
    }
    (OUT_DIR / "normalization_report.json").write_text(json.dumps(manifest, indent=2))
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
