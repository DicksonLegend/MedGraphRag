#!/usr/bin/env python
"""STEP 2: BiomedCLIP zero-shot v2 (fixes uniform ~0.07 scores of v1 CLIP-B/16).

- Backbone: chuhac/BiomedCLIP-vit-bert-hf (HF-native microsoft BiomedCLIP,
  PubMedBERT text tower) — official CheXzero weights are not publicly hosted.
- Per-class positive + negated prompt ensembles, temperature-scaled softmax
  (model logit_scale), CheXzero-style 14 labels.
- Encodes BOTH corpora: VQA-RAD 315 imgs (validation) + OpenI sample100.
- VALIDATION: per-label AUC vs VQA-RAD yes/no ground truth via keyword rules;
  mean AUC gate > 0.65 else exit code 4 (STOP AND ASK).
Output: data/multimodal/visual_findings_v2.json (+ auc_table inside).
"""
import gc
import hashlib
import json
import resource
import sys
import time
from pathlib import Path

import torch

ROOT = Path("/home/dicksone/Documents/MedGraphRag")
MODEL_DIR = ROOT / "data/external/models/biomedclip-hf"
VQA_IMGS = ROOT / "data/external/datasets/vqa_rad_imgs"
OPENI_IMGS = ROOT / "data/multimodal/images/sample100"
VQA_JSON = ROOT / "data/external/datasets/VQA_RAD_Dataset_Public.json"
OUT = ROOT / "data/multimodal/visual_findings_v2.json"
RSS_LIMIT = 4 * 1024**3
BATCH = 16

LABELS = [
    "enlarged cardiomediastinum", "cardiomegaly", "lung lesion",
    "airspace opacity", "edema", "consolidation", "pneumonia",
    "atelectasis", "pneumothorax", "pleural effusion", "pleural other",
    "fracture", "support devices", "no finding",
]
POS_T = ["{c}", "{c} shown", "evidence of {c}", "indication of {c}",
         "the patient has {c}", "chest x-ray showing {c}",
         "presence of {c}", "radiograph demonstrates {c}"]
NEG_T = ["no {c}", "no evidence of {c}", "{c} absent", "free of {c}",
         "negative for {c}", "chest x-ray without {c}",
         "unremarkable for {c}", "resolution of {c}"]

# VQA-RAD question -> label keyword rules (for yes/no ground truth)
Q_RULES = {
    "cardiomegaly": ["cardiomegaly", "enlarged heart", "heart size"],
    "enlarged cardiomediastinum": ["mediastin", "cardiac silhouette"],
    "lung lesion": ["lesion", "mass", "nodule", "tumor"],
    "airspace opacity": ["opacity", "opacit", "infiltrat"],
    "edema": ["edema"],
    "consolidation": ["consolidation"],
    "pneumonia": ["pneumonia"],
    "atelectasis": ["atelecta"],
    "pneumothorax": ["pneumothorax"],
    "pleural effusion": ["effusion"],
    "pleural other": ["pleural", "thickening", "calcification", " pneumo"],
    "fracture": ["fracture", "rib "],
    "support devices": ["device", "pacemaker", "tube", "line", "implant", "catheter"],
}


def rss_mb() -> int:
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss // 1024


def watchdog() -> None:
    if rss_mb() * 1024 * 1024 > RSS_LIMIT:
        print("RSS WATCHDOG abort >4GB", file=sys.stderr)
        sys.exit(3)


def load_model():
    from transformers import AutoModel, AutoProcessor
    model = AutoModel.from_pretrained(str(MODEL_DIR), local_files_only=True,
                                      trust_remote_code=True)
    proc = AutoProcessor.from_pretrained(str(MODEL_DIR), local_files_only=True,
                                         trust_remote_code=True)
    # transformers>=5 quirk: non-persistent buffers can arrive uninitialized
    emb = model.text_model.embeddings
    L = emb.position_ids.shape[-1]
    emb.position_ids = torch.arange(L).unsqueeze(0)
    emb.token_type_ids = torch.zeros_like(emb.position_ids)
    model.eval()
    torch.set_num_threads(4)
    return model, proc


@torch.no_grad()
def embed_prompts(model, proc, templates):
    prompts = [t.format(c=c) for c in LABELS for t in templates]
    toks = proc(text=prompts, return_tensors="pt", padding="max_length",
                truncation=True)
    feats = model.get_text_features(**toks)
    feats = feats / feats.norm(dim=-1, keepdim=True)
    n = len(templates)
    return feats.view(len(LABELS), n, -1).mean(dim=1)


@torch.no_grad()
def encode_images(model, proc, paths):
    out = []
    for i in range(0, len(paths), BATCH):
        watchdog()
        from PIL import Image
        imgs = [Image.open(p).convert("RGB") for p in paths[i:i + BATCH]]
        px = proc(images=imgs, return_tensors="pt")
        f = model.get_image_features(**px)
        f = f / f.norm(dim=-1, keepdim=True)
        out.append(f)
        del imgs, f
        gc.collect()
        print(f"  encoded {min(i + BATCH, len(paths))}/{len(paths)} rss={rss_mb()}MB",
              flush=True)
    return torch.cat(out)


def classify(model, proc, paths, pos_f, neg_f, logit_scale):
    img_f = encode_images(model, proc, paths)
    pos = logit_scale * (img_f @ pos_f.T)   # [B,L]
    neg = logit_scale * (img_f @ neg_f.T)
    p_pos = pos.softmax(dim=-1)
    p_neg = neg.softmax(dim=-1)
    results = []
    for j, p in enumerate(paths):
        findings = []
        for li, label in enumerate(LABELS):
            s = float(p_pos[j, li])
            n = float(p_neg[j, li])
            findings.append({
                "label": label,
                "score": round(s, 4),
                "negated": bool(n > s and label != "no finding"),
                "neg_score": round(n, 4),
            })
        emb_sha = hashlib.sha256(img_f[j].cpu().numpy().tobytes()).hexdigest()
        results.append({"image_id": p.stem, "findings": findings,
                        "embedding_sha": emb_sha})
    del img_f, pos, neg, p_pos, p_neg
    gc.collect()
    return results


def auc(scores: list[float], labels: list[int]) -> float:
    """Rank-based AUC (Mann-Whitney). Returns None-equivalent if degenerate."""
    pos = [s for s, l in zip(scores, labels) if l == 1]
    neg = [s for s, l in zip(scores, labels) if l == 0]
    if not pos or not neg:
        return -1.0
    ranked = sorted(range(len(scores)), key=lambda i: scores[i])
    rank = {}
    for r, idx in enumerate(ranked, 1):
        rank[idx] = r
    rp = sum(rank[i] for i, l in enumerate(labels) if l == 1)
    n1, n0 = len(pos), len(neg)
    return (rp - n1 * (n1 + 1) / 2) / (n1 * n0)


def main() -> None:
    t0 = time.perf_counter()
    model, proc = load_model()
    try:
        scale = float(model.logit_scale.exp().item())
    except Exception:
        scale = 100.0
    print(f"[v2] logit_scale={scale:.1f}", flush=True)
    pos_f = embed_prompts(model, proc, POS_T)
    neg_f = embed_prompts(model, proc, NEG_T)

    # Corpus 1: VQA-RAD 315 (validation)
    vqa_paths = sorted(VQA_IMGS.glob("*.jpg"))[:400]
    vqa_res = classify(model, proc, vqa_paths, pos_f, neg_f, scale)

    # Ground truth from VQA_RAD json keyword rules
    qa = json.loads(VQA_JSON.read_text())
    gt: dict[str, dict[str, int]] = {}
    for row in qa:
        q = row["question"].lower()
        ans = str(row["answer"]).strip().lower()
        if ans not in ("yes", "no"):
            continue
        iid = Path(row["image_name"]).stem
        for label, kws in Q_RULES.items():
            if any(k in q for k in kws):
                d = gt.setdefault(iid, {}).setdefault(label, {"y": 0, "n": 0})
                d["y" if ans == "yes" else "n"] += 1

    # Per-label AUC
    score_by_img = {r["image_id"]: {f["label"]: f["score"] for f in r["findings"]}
                    for r in vqa_res}
    neg_by_img = {r["image_id"]: {f["label"]: f.get("neg_score", 1 - f["score"])
                                  for f in r["findings"]} for r in vqa_res}
    auc_table = {}
    for label in LABELS:
        ids, ys, ss, sn = [], [], [], []
        for iid, labs in gt.items():
            c = labs.get(label)
            if not c or (c["y"] + c["n"]) < 1:
                continue
            y = 1 if c["y"] > c["n"] else 0
            if iid not in score_by_img:
                continue
            ids.append(iid)
            ys.append(y)
            ss.append(score_by_img[iid][label])
            sn.append(neg_by_img[iid][label])
        a_pos = auc(ss, ys)
        a_neg = auc(sn, [1 - y for y in ys])   # inverted GT vs neg-score
        best = max(a_pos, a_neg)
        auc_table[label] = {
            "auc_positive": round(a_pos, 4),
            "auc_negated_inverted": round(a_neg, 4),
            "best_auc": round(best, 4) if best > 0 else round(max(a_pos, a_neg), 4),
            "n_images_with_gt": len(ids),
        }
    valid = [v["best_auc"] for v in auc_table.values() if v["best_auc"] >= 0]
    mean_auc = sum(valid) / len(valid) if valid else 0.0
    passed = mean_auc > 0.65
    print(f"[v2] MEAN AUC={mean_auc:.4f} gate>0.65 pass={passed}")

    # Corpus 2: OpenI sample100 (cross-link corpus; only if validation passed)
    openi_res = []
    if passed:
        oi_paths = sorted(OPENI_IMGS.glob("*.png"))
        openi_res = classify(model, proc, oi_paths, pos_f, neg_f, scale)

    payload = {
        "stage": "C2_v2_biomedclip_zero_shot",
        "model": "chuhac/BiomedCLIP-vit-bert-hf (= microsoft BiomedCLIP-PubMedBERT_256 vit_base_patch16_224); official CheXzero weights not publicly hosted",
        "logit_scale_used": round(scale, 2),
        "prompting": "per-class positive+negative template ensembles (8+8)",
        "labels": LABELS,
        "validation": {
            "protocol": "per-label AUC vs VQA-RAD yes/no GT (keyword rules)",
            "mean_best_auc": round(mean_auc, 4),
            "gate": "> 0.65",
            "passed": passed,
            "auc_table": auc_table,
        },
        "results_vqa_rad": vqa_res,
        "results_openi_sample100": openi_res,
        "wall_seconds": round(time.perf_counter() - t0, 2),
        "peak_rss_mb": rss_mb(),
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
    }
    OUT.write_text(json.dumps(payload))
    sha = hashlib.sha256(OUT.read_bytes()).hexdigest()
    print(f"[v2] WROTE {OUT} artifact_sha256={sha}")
    sys.exit(0 if passed else 4)


if __name__ == "__main__":
    main()
