#!/usr/bin/env python
"""Fetch <=100 sample OpenI chest X-ray PNGs referenced by NLMCXR_reports.

URL pattern (OpenI image CDN): https://openi.nlm.nih.gov/imgs/400/<shard>/<img_id>.png
where <shard> is the numeric prefix of the filename before the first '_'
(e.g. CXR1_1_IM-0001-4001.png -> shard 16 is NOT derivable; we try the
documented API fallback per id). We first try shard candidates 1..40 capped,
else fall back to the retrieve API JSON for the exact URL.
Resumable + headroom-guarded; appends to download.log.
"""
import json
import os
import re
import tarfile
import time
import urllib.request
from pathlib import Path

ROOT = Path("/home/dicksone/Documents/MedGraphRag")
R = ROOT / "data/multimodal/reports"
IMG = ROOT / "data/multimodal/images/sample100"
LOG = ROOT / "data/external/download.log"
TGZ = R / "NLMCXR_reports.tgz"
MAX_IMAGES = 100


def log(msg: str) -> None:
    with open(LOG, "a") as f:
        f.write(f"[{time.strftime('%Y-%m-%dT%H:%M:%S%z')}] {msg}\n")


def free_gb() -> float:
    st = os.statvfs(ROOT)
    return st.f_bavail * st.f_frsize / 2**30


def extract_ids() -> list[str]:
    ids: list[str] = []
    if not TGZ.exists():
        log("fetch_openi_sample: reports tgz missing; aborting image fetch")
        return ids
    with tarfile.open(TGZ, "r:gz") as tf:
        for m in tf.getmembers():
            if m.name.endswith(".xml"):
                f = tf.extractfile(m)
                if not f:
                    continue
                txt = f.read().decode("utf-8", "ignore")
                for mm in re.finditer(r'<parentImage id="([^"]+)"', txt):
                    ids.append(mm.group(1).strip())
            if len(ids) >= MAX_IMAGES:
                break
    log(f"fetch_openi_sample: {len(ids)} image ids extracted")
    return ids[:MAX_IMAGES]


def api_url(uid: str) -> str | None:
    # OpenI CDN pattern: /imgs/400/<shard>/<id>.png where shard is a stable
    # per-image integer; try the documented API first, then shard scan.
    q = f"https://openi.nlm.nih.gov/api/retrieve?dataFormat=json&uid={uid}"
    try:
        with urllib.request.urlopen(q, timeout=20) as r:
            doc = json.loads(r.read().decode())
            img = doc["docs"]["img"]
            return f"https://openi.nlm.nih.gov{img}" if img.startswith("/") else img
    except Exception:
        pass
    for shard in range(1, 41):
        cand = f"https://openi.nlm.nih.gov/imgs/400/{shard}/{uid}.png"
        try:
            req = urllib.request.Request(cand, method="HEAD",
                                         headers={"User-Agent": "MedGraphRAG/1.0"})
            with urllib.request.urlopen(req, timeout=10):
                return cand
        except Exception:
            continue
    return None


def fetch_png(uid: str) -> bool:
    dest = IMG / uid
    if dest.exists() and dest.stat().st_size > 0:
        return True
    url = api_url(uid)
    if not url:
        return False
    tmp = IMG / (uid + ".part")
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "MedGraphRAG/1.0"})
        with urllib.request.urlopen(req, timeout=60) as r, open(tmp, "wb") as f:
            while True:
                chunk = r.read(65536)
                if not chunk:
                    break
                f.write(chunk)
        tmp.rename(dest)
        return True
    except Exception as e:
        log(f"fetch_openi_sample: FAIL {uid}: {e}")
        tmp.unlink(missing_ok=True)
        return False


def main() -> None:
    IMG.mkdir(parents=True, exist_ok=True)
    ids = extract_ids()
    ok = sum(1 for i in ids if fetch_png(i))
    log(f"fetch_openi_sample: done ok={ok}/{len(ids)} free_gb={free_gb():.1f}")


if __name__ == "__main__":
    main()
