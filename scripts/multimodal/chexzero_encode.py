#!/usr/bin/env python
"""Stage C-2: CheXzero-style offline zero-shot labeling (CPU-only).

CLIP ViT-B/16 backbone (openai/clip-vit-base-patch16 weights under
data/external/models/clip-vit-base-patch16/). Zero-shot classification over
the 14 OpenI/CheXpert finding categories using CheXpert-style positive vs
negated prompt template ensembles; per-finding negated flag = negated-score
> positive-score. Batched, <=4 torch threads, RSS watchdog aborts > 4 GB.

Output: data/multimodal/visual_findings.json
  {"image_id", "findings": [{"label","score","negated"}], "embedding_sha"}
"""
import hashlib
import json
import resource
import sys
import time
from pathlib import Path

import numpy as np
import torch
from PIL import Image

ROOT = Path("/home/dicksone/Documents/MedGraphRag")
MODEL_DIR = ROOT / "data/external/models/clip-vit-base-patch16"
IMAGES = ROOT / "data/multimodal/images/sample100"
OUT = ROOT / "data/multimodal/visual_findings.json"
RSS_LIMIT_BYTES = 4 * 1024**3
BATCH = 8

LABELS = [
    "enlarged cardiomediastinum", "cardiomegaly", "lung lesion",
    "airspace opacity", "edema", "consolidation", "pneumonia",
    "atelectasis", "pneumothorax", "pleural effusion", "pleural other",
    "fracture", "support devices", "no finding",
]
POS_TEMPLATES = [
    "{c}", "chest x-ray showing {c}", "evidence of {c}",
    "presence of {c}", "radiograph demonstrates {c}",
]
NEG_TEMPLATES = [
    "no evidence of {c}", "absent {c}", "free of {c}",
    "chest x-ray without {c}", "negative for {c}",
]


def rss_bytes() -> int:
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024


def watchdog() -> None:
    if rss_bytes() > RSS_LIMIT_BYTES:
        print("RSS WATCHDOG: >4GB — aborting cleanly", file=sys.stderr)
        sys.exit(3)


def load_model():
    from transformers import CLIPModel, CLIPProcessor
    model = CLIPModel.from_pretrained(str(MODEL_DIR), local_files_only=True)
    proc = CLIPProcessor.from_pretrained(str(MODEL_DIR), local_files_only=True)
    model.eval()
    torch.set_num_threads(4)
    return model, proc


def _as_tensor(out):
    """transformers v5 may return ModelOutput instead of Tensor."""
    if torch.is_tensor(out):
        return out
    for key in ("text_embeds", "image_embeds", "pooler_output"):
        v = getattr(out, key, None)
        if v is not None:
            return v
    raise TypeError(f"Unexpected model output type: {type(out)}")


def text_features(model, proc) -> tuple[torch.Tensor, torch.Tensor]:
    def embed(templates):
        prompts = [t.format(c=c) for c in LABELS for t in templates]
        with torch.no_grad():
            toks = proc(text=prompts, return_tensors="pt", padding=True,
                        truncation=True)
            feats = _as_tensor(model.get_text_features(**toks))
            feats = feats / feats.norm(dim=-1, keepdim=True)
        n = len(templates)
        return feats.view(len(LABELS), n, -1).mean(dim=1)

    return embed(POS_TEMPLATES), embed(NEG_TEMPLATES)


def main() -> None:
    t0 = time.perf_counter()
    img_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else IMAGES
    paths = sorted(p for p in img_dir.glob("*.png")) + \
            sorted(p for p in img_dir.glob("*.jpg"))
    if not paths:
        print("No sample images found; nothing to encode.")
        return
    model, proc = load_model()
    pos_f, neg_f = text_features(model, proc)
    results = []
    for i in range(0, len(paths), BATCH):
        watchdog()
        batch = paths[i:i + BATCH]
        imgs = [Image.open(p).convert("RGB") for p in batch]
        with torch.no_grad():
            px = proc(images=imgs, return_tensors="pt")
            img_f = _as_tensor(model.get_image_features(**px))
            img_f = img_f / img_f.norm(dim=-1, keepdim=True)
            pos_sim = (img_f @ pos_f.T).softmax(dim=-1)   # [B, L] positive prob
            neg_sim = (img_f @ neg_f.T).softmax(dim=-1)   # [B, L] negated prob
        for j, p in enumerate(batch):
            findings = []
            for li, label in enumerate(LABELS):
                p_score = float(pos_sim[j, li])
                n_score = float(neg_sim[j, li])
                findings.append({
                    "label": label,
                    "score": round(p_score, 4),
                    "negated": bool(n_score > p_score and label != "no finding"),
                })
            emb_sha = hashlib.sha256(img_f[j].numpy().tobytes()).hexdigest()
            results.append({"image_id": p.stem, "findings": findings,
                            "embedding_sha": emb_sha})
        del imgs, img_f, pos_sim, neg_sim
        print(f"encoded {min(i + BATCH, len(paths))}/{len(paths)} "
              f"peak_rss_mb={rss_bytes() // 2**20}", flush=True)

    payload = {
        "stage": "C2_chexzero_zero_shot",
        "model": "openai/clip-vit-base-patch16 (CheXzero protocol)",
        "image_source": str(img_dir),
        "labels": LABELS,
        "n_images": len(results),
        "wall_seconds": round(time.perf_counter() - t0, 2),
        "peak_rss_bytes": rss_bytes(),
        "results": results,
    }
    OUT.write_text(json.dumps(payload))
    sha = hashlib.sha256(OUT.read_bytes()).hexdigest()
    print(f"WROTE {OUT} images={len(results)} artifact_sha256={sha}")


if __name__ == "__main__":
    main()
