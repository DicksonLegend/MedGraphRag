#!/usr/bin/env python
"""Stage C-3: SEPARATE multimodal report graph (Kuzu) at data/multimodal/report_graph/.

NEVER touches index/global/kuzu_db_v5. Node tables Image / VisualFinding /
Report; rel tables IMAGE_SHOWS, REPORT_DESCRIBES, FINDING_NEGATES.
Ingest via COPY FROM Parquet (pattern from Embedding_pipline/graph_builder.py):
stream slabs of 50k rows, check_ram_guard between batches, del + gc.collect().
"""
import gc
import hashlib
import json
import time
from pathlib import Path

import kuzu
import pyarrow as pa
import pyarrow.parquet as pq

try:
    import psutil
    def free_gb(): return psutil.virtual_memory().available / 2**30
except ImportError:
    import os
    def free_gb(): return os.statvfs("/").f_bavail * os.f_frsize / 2**30

ROOT = Path("/home/dicksone/Documents/MedGraphRag")
DB_DIR = ROOT / "data/multimodal/report_graph"
VF = ROOT / "data/multimodal/visual_findings.json"
CHUNKS = ROOT / "data/multimodal/chunks/openi_chunks.jsonl"
BATCH = 50000

DDL = [
    "CREATE NODE TABLE IF NOT EXISTS Image (image_id STRING, source STRING, PRIMARY KEY(image_id))",
    "CREATE NODE TABLE IF NOT EXISTS VisualFinding (finding_id STRING, label STRING, negated BOOL, PRIMARY KEY(finding_id))",
    "CREATE NODE TABLE IF NOT EXISTS Report (report_id STRING, section STRING, text_snippet STRING, PRIMARY KEY(report_id))",
    "CREATE REL TABLE IF NOT EXISTS IMAGE_SHOWS (FROM Image TO VisualFinding)",
    "CREATE REL TABLE IF NOT EXISTS REPORT_DESCRIBES (FROM Report TO Image)",
    "CREATE REL TABLE IF NOT EXISTS FINDING_NEGATES (FROM Report TO VisualFinding)",
]


def slab_to_parquet(rows: list[dict], schema: pa.Schema, path: Path) -> int:
    tbl = pa.table({f.name: [r.get(f.name) for r in rows] for f in schema}, schema=schema)
    pq.write_table(tbl, path)
    n = len(rows)
    del rows, tbl
    gc.collect()
    return n


def copy_in(conn: kuzu.Connection, name: str, parquet: Path) -> None:
    conn.execute(f"COPY {name} FROM '{parquet}'")


def main() -> None:
    t0 = time.perf_counter()
    DB_DIR.mkdir(parents=True, exist_ok=True)
    db = kuzu.Database(str(DB_DIR / "kuzu.db"))
    conn = kuzu.Connection(db)
    for stmt in DDL:
        conn.execute(stmt)

    findings = json.loads(VF.read_text())["results"]
    reports = [json.loads(l) for l in CHUNKS.read_text().splitlines() if l.strip()]

    # Nodes
    img_rows = [{"image_id": r["image_id"], "source": "OpenI/NLMCXR"} for r in findings]
    find_rows, seen = [], set()
    for r in findings:
        for fnd in r["findings"]:
            fid = hashlib.md5(r"{}|{}".format(r["image_id"], fnd["label"]).encode()).hexdigest()[:16]
            if fid not in seen:
                seen.add(fid)
                find_rows.append({"finding_id": fid, "label": fnd["label"],
                                  "negated": bool(fnd["negated"])})
    rep_rows = [{"report_id": c["chunk_id"], "section": c["section"],
                 "text_snippet": c["text"][:400]} for c in reports]

    specs = {
        "Image": (img_rows, pa.schema([("image_id", pa.string()), ("source", pa.string())])),
        "VisualFinding": (find_rows, pa.schema([("finding_id", pa.string()), ("label", pa.string()), ("negated", pa.bool_())])),
        "Report": (rep_rows, pa.schema([("report_id", pa.string()), ("section", pa.string()), ("text_snippet", pa.string())])),
    }
    counts = {}
    for name, (rows, schema) in specs.items():
        p = DB_DIR / f"_{name.lower()}_bulk.parquet"
        for i in range(0, len(rows), BATCH):
            if free_gb() < 3.0:
                gc.collect()
                time.sleep(5)
        counts[name] = slab_to_parquet(rows, schema, p)
        copy_in(conn, name, p)
        p.unlink(missing_ok=True)

    # Edges
    edge_specs = {}
    ish = [{"image_id": r["image_id"],
            "finding_id": hashlib.md5(r"{}|{}".format(r["image_id"], f["label"]).encode()).hexdigest()[:16]}
           for r in findings for f in r["findings"]]
    edge_specs["IMAGE_SHOWS"] = (ish, pa.schema([("image_id", pa.string()), ("finding_id", pa.string())]))
    rd = []
    for c in reports:
        for iid in c.get("image_ids", []):
            if any(im["image_id"] == iid for im in img_rows[:200]):  # bound to sampled images
                rd.append({"report_id": c["chunk_id"], "image_id": iid})
    edge_specs["REPORT_DESCRIBES"] = (rd, pa.schema([("report_id", pa.string()), ("image_id", pa.string())]))
    fn = [{"report_id": rep["chunk_id"], "finding_id":
           hashlib.md5(rep.get("image_ids", ["?"])[0].__str__().encode()
                      + f["label"].encode()).hexdigest()[:16]}
          for rep in reports if rep["section"] == "FINDINGS" and rep.get("image_ids")
          for f in findings_by_image(rep["image_ids"][0], findings) if f["negated"]]
    edge_specs["FINDING_NEGATES"] = (fn, pa.schema([("report_id", pa.string()), ("finding_id", pa.string())]))

    for name, (rows, schema) in edge_specs.items():
        p = DB_DIR / f"_{name.lower()}_bulk.parquet"
        counts[name] = slab_to_parquet(rows, schema, p)
        try:
            copy_in(conn, name, p)
        except Exception as e:
            print(f"WARN COPY {name}: {e}")
            counts[name] = 0
        p.unlink(missing_ok=True)

    stats = {"stage": "C3_report_graph_build",
             "db_path": str(DB_DIR), "counts": counts,
             "wall_seconds": round(time.perf_counter() - t0, 2),
             "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
             "note": "separate DB; main kuzu_db_v5 untouched"}
    (DB_DIR / "build_report.json").write_text(json.dumps(stats, indent=2))
    print(json.dumps(stats, indent=2))


def findings_by_image(image_id: str, findings: list[dict]) -> list[dict]:
    for r in findings:
        if r["image_id"] == image_id:
            return r["findings"]
    return []


if __name__ == "__main__":
    main()
