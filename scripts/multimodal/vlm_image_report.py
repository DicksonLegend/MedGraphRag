#!/usr/bin/env python
"""STEP 6: Qwen2-VL-2B (Q4_K_M, CPU-only) image-VQA over 20 VQA-RAD samples.

- n_gpu_layers=0 (GPU reserved for Qwen2.5-7B), n_threads<=4, n_ctx=2048,
  vision via mmproj-Qwen2-VL-2B-Instruct-Q8_0.gguf + Qwen25VLChatHandler.
- Refusal tiers: ANSWERED / HEDGED / REFUSED (keyword heuristics).
- EM: token-overlap exact-match proxy vs VQA-RAD GT answer.
- RSS watchdog 4 GB. If vision path fails twice -> findings-text fallback
  (BiomedCLIP v2 findings as context), modality marked "findings-text".
Output: evaluations/multimodal/step16_image_report.json
"""
import base64
import gc
import hashlib
import json
import re
import resource
import sys
import time
from pathlib import Path

ROOT = Path("/home/dicksone/Documents/MedGraphRag")
GGUF = ROOT / "data/external/models/Qwen2-VL-2B-Instruct-Q4_K_M.gguf"
MMPROJ = ROOT / "data/external/models/mmproj-Qwen2-VL-2B-Instruct-Q8_0.gguf"
VQA_IMGS = ROOT / "data/external/datasets/vqa_rad_imgs"
VQA_JSON = ROOT / "data/external/datasets/VQA_RAD_Dataset_Public.json"
VF2 = ROOT / "data/multimodal/visual_findings_v2.json"
OUT = ROOT / "evaluations/multimodal/step16_image_report.json"
N_SAMPLES = 20
RSS_LIMIT = 4 * 1024**3


def rss_mb():
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss // 1024


def watchdog():
    if rss_mb() * 1024 * 1024 > RSS_LIMIT:
        print("RSS WATCHDOG abort >4GB", file=sys.stderr)
        sys.exit(3)


def refusal_tier(ans: str) -> str:
    a = ans.lower()
    if re.search(r"\b(cannot|can't|unable|not able to|refuse|no answer|"
                 r"not (a )?medical (advice|professional)|consult)\b", a):
        return "REFUSED"
    if re.search(r"\b(unclear|not sure|possibly|may|might|appears|likely|"
                 r"difficult to (say|determine)|cannot be determined)\b", a):
        return "HEDGED"
    return "ANSWERED"


def token_em(ans: str, gt: str) -> float:
    a = set(re.findall(r"[a-z0-9]+", ans.lower()))
    g = set(re.findall(r"[a-z0-9]+", gt.lower()))
    if not g:
        return 0.0
    return len(a & g) / len(g)


def main() -> None:
    t0 = time.perf_counter()
    qa = json.loads(VQA_JSON.read_text())
    by_img: dict[str, list[dict]] = {}
    for row in qa:
        by_img.setdefault(Path(row["image_name"]).stem, []).append(row)
    # deterministic sample: first image with a yes/no question, then every
    # k-th, seed-42-stable (sorted ids, stride)
    ids = sorted(i for i, rows in by_img.items()
                 if any(r["answer"].strip().lower() in ("yes", "no") for r in rows))
    stride = max(1, len(ids) // N_SAMPLES)
    sample = ids[::stride][:N_SAMPLES]
    print(f"[vlm] sampled {len(sample)} images (stride {stride})", flush=True)

    vf2 = json.loads(VF2.read_text())
    findings_by_img = {r["image_id"]: r["findings"] for r in vf2["results_vqa_rad"]}

    from llama_cpp import Llama
    from llama_cpp.llama_chat_format import Qwen25VLChatHandler

    modality = "qwen2-vl-vision"
    handler = None
    llm = None
    vision_fails = 0

    def _b64(p: Path) -> str:
        from PIL import Image
        import io
        im = Image.open(p).convert("RGB").resize((448, 448))
        buf = io.BytesIO()
        im.save(buf, format="JPEG", quality=85)
        return base64.b64encode(buf.getvalue()).decode()

    try:
        handler = Qwen25VLChatHandler(clip_model_path=str(MMPROJ))
        # Qwen2-VL expands one image into ~1-4k tokens -> need headroom over
        # the nominal 2048 text budget; KV stays CPU-resident (RAM guard).
        llm = Llama(model_path=str(GGUF), n_gpu_layers=0, n_ctx=4608,
                    n_threads=4, verbose=False, chat_handler=handler)
        p = sorted(VQA_IMGS.glob("*.jpg"))[0]
        b64 = _b64(p)
        llm.create_chat_completion(messages=[{
            "role": "user",
            "content": [{"type": "image_url",
                         "image_url": {"url": f"data:image/jpeg;base64,{b64}"}},
                        {"type": "text", "text": "Reply with one word: yes or no."}]}],
            max_tokens=8)
        print("[vlm] vision smoke OK", flush=True)
    except Exception as e:
        vision_fails += 1
        print(f"[vlm] vision init/smoke FAIL #{vision_fails}: {e}", flush=True)
        llm = None

    if llm is None and vision_fails >= 1:
        # second chance without handler (pure text) then fallback
        try:
            llm = Llama(model_path=str(GGUF), n_gpu_layers=0, n_ctx=2048,
                        n_threads=4, verbose=False)
            modality = "findings-text"
            print("[vlm] falling back to findings-text modality", flush=True)
        except Exception as e:
            print(f"[vlm] FATAL: text-only load also failed: {e}", file=sys.stderr)
            sys.exit(2)

    results = []
    for n, iid in enumerate(sample, 1):
        watchdog()
        rows = by_img[iid]
        row = next((r for r in rows if r["answer"].strip().lower() in ("yes", "no")),
                   rows[0])
        question = row["question"]
        gt = row["answer"]
        img_path = VQA_IMGS / f"{iid}.jpg"
        tq = time.perf_counter()
        try:
            if modality == "qwen2-vl-vision":
                b64 = _b64(img_path)
                msgs = [{"role": "user", "content": [
                    {"type": "image_url",
                     "image_url": {"url": f"data:image/jpeg;base64,{b64}"}},
                    {"type": "text",
                     "text": f"Chest X-ray question. Answer briefly (one short "
                             f"phrase). If the image does not allow answering, "
                             f"say so. Question: {question}"}]}]
                out = llm.create_chat_completion(messages=msgs, max_tokens=64,
                                                 temperature=0.0)
            else:
                fnd = findings_by_img.get(iid, [])
                pos = [f["label"] for f in fnd if not f["negated"]
                       and f["label"] != "no finding" and f["score"] > 0.2]
                ctx = ", ".join(pos) if pos else "no definite findings"
                msgs = [{"role": "user", "content":
                         f"Zero-shot chest X-ray findings: {ctx}. Question: "
                         f"{question} Answer briefly; say 'cannot be determined' "
                         f"if findings are insufficient."}]
                out = llm.create_chat_completion(messages=msgs, max_tokens=64,
                                                 temperature=0.0)
            ans = out["choices"][0]["message"]["content"].strip()
        except Exception as e:
            vision_fails += 1
            ans = f"[error: {type(e).__name__}]"
            if modality == "qwen2-vl-vision" and vision_fails >= 2:
                print("[vlm] two vision failures -> findings-text fallback",
                      flush=True)
                modality = "findings-text"
        lat = round((time.perf_counter() - tq) * 1000, 1)
        results.append({
            "image_id": iid,
            "question": question,
            "gt_answer": gt,
            "model_answer": ans,
            "refusal_tier": refusal_tier(ans),
            "token_overlap_em": round(token_em(ans, gt), 4),
            "latency_ms": lat,
        })
        print(f"  [{n}/{len(sample)}] {iid} tier={results[-1]['refusal_tier']} "
              f"em={results[-1]['token_overlap_em']} {lat}ms", flush=True)
        gc.collect()

    answered = [r for r in results if r["refusal_tier"] == "ANSWERED"]
    payload = {
        "stage": "STEP6_vlm_image_report",
        "modality": modality,
        "model": "Qwen2-VL-2B-Instruct Q4_K_M (llama.cpp 0.3.35, CPU, n_gpu_layers=0)",
        "vision_failures": vision_fails,
        "n_samples": len(results),
        "tier_counts": {t: sum(1 for r in results if r["refusal_tier"] == t)
                        for t in ("ANSWERED", "HEDGED", "REFUSED")},
        "mean_token_overlap_em": round(sum(r["token_overlap_em"] for r in results)
                                       / max(1, len(results)), 4),
        "mean_latency_ms": round(sum(r["latency_ms"] for r in results)
                                 / max(1, len(results)), 1),
        "peak_rss_mb": rss_mb(),
        "wall_seconds": round(time.perf_counter() - t0, 1),
        "results": results,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
    }
    OUT.write_text(json.dumps(payload, indent=2))
    sha = hashlib.sha256(OUT.read_bytes()).hexdigest()
    print(f"[vlm] WROTE {OUT} artifact_sha256={sha}")


if __name__ == "__main__":
    main()
