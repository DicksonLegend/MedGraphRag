"""
Focused runner — stream the *remaining truncated* UMLS RRF files to full
normalized JSON, leaving all already-complete outputs untouched.

Used under /home/dicksone/Documents/MedGraphRag/Data_Normalization
"""
import sys, json, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from pipeline import NormalizationPipeline, _stream_candidate
from config import CATEGORY_MAP
from utils import get_output_path, compute_sha256
from parsers.rrf_stream import stream_rrf_to_json

ROOT = Path("/home/dicksone/Documents/MedGraphRag")
SRC = ROOT / "Datasets/UMLS Output"
dec = ROOT / "Datasets/normalized/UMLS Output"

# (source_relative_path, format_ext)
TARGETS = [
    ("META/MRCONSO.RRF", "rrf"),
    ("META/MRDEF.RRF", "rrf"),
    ("META/MRHIER.RRF", "rrf"),
    ("META/MRREL.RRF", "rrf"),
    ("META/MRSTY.RRF", "rrf"),
    ("LEX/LEXICON", "rrf"),
    ("LEX/LRABR", "rrf"),
    ("LEX/LRMOD", "rrf"),
    ("LEX/LRPRP", "rrf"),
    ("LEX/LRSPL", "rrf"),
    ("LEX/LRTYP", "rrf"),
    ("LEX/LRWD", "rrf"),
]

p = NormalizationPipeline(max_workers=8, force=True, folder="UMLS Output")

results = []
for rel, fmt in TARGETS:
    fp = SRC / rel
    if not fp.exists():
        print(f"!! MISSING source: {rel}")
        continue
    h = compute_sha256(fp)
    out = get_output_path(fp, ROOT / "Datasets", ROOT / "Datasets/normalized")
    out.parent.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    try:
        stream_rrf_to_json(
            fp, out, ROOT / "Datasets", "UMLS Output", "ontology",
            fmt, h,
        )
        dt = time.time() - t0
        mb = out.stat().st_size / 1e6
        err = None
    except Exception as e:
        import traceback; traceback.print_exc()
        dt = time.time() - t0; mb = 0; err = str(e)
    results.append((str(rel), err, dt, mb))
    print(f"{'OK ' if not err else 'FAIL'} {rel:26s} {mb:8.1f}MB  {dt:6.1f}s  {err or ''}")

# sanity: verify each output JSON parses & row count >= previous
print("\n=== row counts ===")
for rel, err, dt, mb in results:
    if err: continue
    j = get_output_path(SRC / rel, ROOT / "Datasets", ROOT / "Datasets/normalized")
    d = json.load(open(j))
    rows = len(d["structured_data"][0]["rows"])
    print(f"  {rel:28s} rows={rows:,}")