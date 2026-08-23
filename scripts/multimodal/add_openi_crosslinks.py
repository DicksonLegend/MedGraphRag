#!/usr/bin/env python
"""STEP 3: Populate REPORT_DESCRIBES + FINDING_NEGATES in the separate
multimodal report graph using REAL OpenI ids (sample100) joined to report
chunks via normalized study-base keys.

Id normalization: 'CXR1000_IM-0003-1001' (XML) and 'CXR1000_IM-0003_0'
(IU-Xray zip) both -> 'cxr1000im0003'.
Main kuzu_db_v5 untouched. Direct parameterized inserts (row counts < 10k).
"""
import json
import re
import time
from pathlib import Path

import kuzu

ROOT = Path("/home/dicksone/Documents/MedGraphRag")
DB = ROOT / "data/multimodal/report_graph/kuzu.db"
VF = ROOT / "data/multimodal/visual_findings_v2.json"
CHUNKS = ROOT / "data/multimodal/chunks/openi_chunks.jsonl"


def norm(img_id: str) -> str:
    # 'CXR1000_IM-0003-1001' and 'CXR1000_IM-0003_0' -> 'cxr1000im0003'
    s = re.sub(r"[^A-Za-z0-9]", "", img_id).lower()
    m = re.match(r"(cxr\d+im\d{4})", s)
    return m.group(1) if m else s


def fid(image_id: str, label: str) -> str:
    import hashlib
    return hashlib.md5(f"{image_id}|{label}".encode()).hexdigest()[:16]


def main() -> None:
    t0 = time.perf_counter()
    vf = json.loads(VF.read_text())
    openi = vf["results_openi_sample100"]
    reports = [json.loads(l) for l in CHUNKS.read_text().splitlines() if l.strip()]

    db = kuzu.Database(str(DB))
    conn = kuzu.Connection(db)

    img_norm = {norm(r["image_id"]): r["image_id"] for r in openi}
    print(f"[xlink] sample images={len(openi)} unique bases={len(img_norm)}")

    # Upsert Image + VisualFinding nodes for OpenI ids
    n_img = n_find = 0
    for r in openi:
        conn.execute("MERGE (i:Image {image_id: $id}) SET i.source = 'OpenI/NLMCXR'",
                     {"id": r["image_id"]})
        n_img += 1
        for f in r["findings"]:
            conn.execute(
                "MERGE (v:VisualFinding {finding_id: $fid}) "
                "SET v.label = $label, v.negated = $neg",
                {"fid": fid(r["image_id"], f["label"]),
                 "label": f["label"], "neg": bool(f["negated"])})
            n_find += 1

    # IMAGE_SHOWS for OpenI images
    n_is = 0
    for r in openi:
        for f in r["findings"]:
            conn.execute(
                "MATCH (i:Image {image_id:$iid}), (v:VisualFinding {finding_id:$fid}) "
                "MERGE (i)-[:IMAGE_SHOWS]->(v)",
                {"iid": r["image_id"], "fid": fid(r["image_id"], f["label"])})
            n_is += 1

    # REPORT_DESCRIBES + FINDING_NEGATES via base-key join
    n_rd = n_fn = 0
    matched_reports = set()
    for c in reports:
        if c["section"] != "FINDINGS":
            continue
        hits = []
        for xid in c.get("image_ids", []):
            base = norm(xid)
            if base in img_norm:
                hits.append((xid, img_norm[base]))
        if not hits:
            continue
        matched_reports.add(c["chunk_id"])
        for xid, iid in hits:
            conn.execute(
                "MATCH (r:Report {report_id:$rid}), (i:Image {image_id:$iid}) "
                "MERGE (r)-[:REPORT_DESCRIBES]->(i)",
                {"rid": c["chunk_id"], "iid": iid})
            n_rd += 1
            vres = next((v for v in openi if v["image_id"] == iid), None)
            if vres:
                for f in vres["findings"]:
                    if f["negated"]:
                        conn.execute(
                            "MATCH (r:Report {report_id:$rid}), "
                            "(v:VisualFinding {finding_id:$fid}) "
                            "MERGE (r)-[:FINDING_NEGATES]->(v)",
                            {"rid": c["chunk_id"],
                             "fid": fid(iid, f["label"])})
                        n_fn += 1

    stats = {
        "stage": "STEP3_crosslink",
        "images_upserted": n_img,
        "findings_upserted": n_find,
        "image_shows_edges": n_is,
        "report_describes_edges": n_rd,
        "finding_negates_edges": n_fn,
        "reports_matched": len(matched_reports),
        "wall_seconds": round(time.perf_counter() - t0, 2),
    }
    (ROOT / "data/multimodal/report_graph/crosslink_report.json").write_text(
        json.dumps(stats, indent=2))
    print(json.dumps(stats, indent=2))


if __name__ == "__main__":
    main()
