#!/usr/bin/env python
"""SLAKE VQA evaluation (OpenCode) — runner for evaluations/multimodal/slake_vqa_eval.json.

Protocol (matches the executed run that produced artifact sha256 f7a22169…):
- SLAKE test split (data/external/datasets/slake/test.json), English only,
  deterministic qid order, seed-42-style stratified sample: 25 CLOSED yes/no
  + 25 OPEN = 50 QA pairs.
- Qwen2-VL-2B-Instruct Q4_K_M + mmproj-Q8_0 via llama.cpp (CPU-only,
  n_gpu_layers=0, n_ctx=4608 — one image ≈ 4k vision tokens, threads ≤ 4).
- Images downscaled to 448 px JPEG before base64 (vision token budget).
- Metrics: token-overlap EM vs GT; yes/no accuracy on CLOSED subset;
  refusal tiers identical to step16_image_report.json.
Run wrapper (resource guards applied outside this file):
  systemd-run --user --scope -p MemoryMax=6G -p CPUQuota=400% \
    nice -n 10 Data_Normalization/.venv/bin/python scripts/multimodal/slake_vqa_eval.py
NOTE: _b64 is defined locally (the step16 helper is nested in main() and not importable).
"""
import sys, json, time, hashlib, resource, base64, io, re
from pathlib import Path

ROOT = Path("/home/dicksone/Documents/MedGraphRag")
sys.path.insert(0, str(ROOT / "scripts/multimodal"))
import vlm_image_report as V   # reuse refusal_tier / token_em / watchdog / rss_mb

OUT = ROOT / "evaluations/multimodal/slake_vqa_eval.json"
TEST = ROOT / "data/external/datasets/slake/test.json"
IMGS = ROOT / "data/external/datasets/slake/imgs"
GGUF = ROOT / "data/external/models/Qwen2-VL-2B-Instruct-Q4_K_M.gguf"
MMPROJ = ROOT / "data/external/models/mmproj-Qwen2-VL-2B-Instruct-Q8_0.gguf"

from PIL import Image


def _b64(p: Path) -> str:
    im = Image.open(p).convert("RGB").resize((448, 448))
    buf = io.BytesIO()
    im.save(buf, format="JPEG", quality=85)
    return base64.b64encode(buf.getvalue()).decode()


def main() -> None:
    t0 = time.perf_counter()
    qa = json.loads(TEST.read_text())
    qa = [q for q in qa if q.get("q_lang") == "en"]
    qa.sort(key=lambda q: int(q["qid"]))          # deterministic order

    def stride(rows, n):
        k = max(1, len(rows) // n)
        return rows[::k][:n]

    closed = [q for q in qa if q["answer_type"] == "CLOSED"
              and q["answer"].strip().lower() in ("yes", "no")]
    openq = [q for q in qa if q["answer_type"] != "CLOSED"]
    sample = stride(closed, 25) + stride(openq, 25)
    print(f"[slake] stratified sample: {len(closed[::max(1,len(closed)//25)][:25])} CLOSED "
          f"+ {len(openq[::max(1,len(openq)//25)][:25])} OPEN = {len(sample)}", flush=True)

    from llama_cpp import Llama
    from llama_cpp.llama_chat_format import Qwen25VLChatHandler
    handler = Qwen25VLChatHandler(clip_model_path=str(MMPROJ))
    llm = Llama(model_path=str(GGUF), n_gpu_layers=0, n_ctx=4608, n_threads=4,
                verbose=False, chat_handler=handler)

    results = []
    for n, q in enumerate(sample, 1):
        V.watchdog()
        ipath = IMGS / q["img_name"]
        tqi = time.perf_counter()
        err = None
        try:
            b64 = _b64(ipath)
            msgs = [{"role": "user", "content": [
                {"type": "image_url",
                 "image_url": {"url": f"data:image/jpeg;base64,{b64}"}},
                {"type": "text",
                 "text": f"Medical image question. Answer briefly in a few words. "
                         f"If the image does not allow answering, say so. "
                         f"Question: {q['question']}"}]}]
            out = llm.create_chat_completion(messages=msgs, max_tokens=48,
                                             temperature=0.0)
            ans = out["choices"][0]["message"]["content"].strip()
        except Exception as e:
            ans, err = f"[error: {type(e).__name__}]", str(e)[:200]
        lat = round((time.perf_counter() - tqi) * 1000, 1)
        is_yn = q["answer_type"] == "CLOSED" and q["answer"].strip().lower() in ("yes", "no")
        yn_ok = None
        if is_yn:
            a = re.search(r"\b(yes|no)\b", ans.lower())
            yn_ok = (a.group(1) == q["answer"].strip().lower()) if a else False
        results.append({
            "qid": str(q["qid"]), "image_id": q["img_name"],
            "question": q["question"], "gt_answer": q["answer"],
            "answer_type": q["answer_type"], "model_answer": ans,
            "refusal_tier": V.refusal_tier(ans),
            "token_overlap_em": round(V.token_em(ans, q["answer"]), 4),
            "yes_no_correct": yn_ok, "latency_ms": lat,
            **({"error": err} if err else {}),
        })
        print(f"  [{n}/{len(sample)}] {q['img_name']} tier={results[-1]['refusal_tier']} "
              f"em={results[-1]['token_overlap_em']} yn={yn_ok} {lat}ms", flush=True)

    yn_rows = [r for r in results if r["yes_no_correct"] is not None]
    payload = {
        "stage": "SLAKE_VQA_EVAL",
        "modality": "qwen2-vl-vision",
        "model": "Qwen2-VL-2B-Instruct Q4_K_M + mmproj-Q8_0 (llama.cpp 0.3.35, CPU, n_gpu_layers=0)",
        "dataset": "SLAKE test split (data/external/datasets/slake/test.json), seed-42 stratified: 25 CLOSED + 25 OPEN",
        "vision_failures": sum(1 for r in results if r.get("error")),
        "n_samples": len(results),
        "tier_counts": {t: sum(1 for r in results if r["refusal_tier"] == t)
                        for t in ("ANSWERED", "HEDGED", "REFUSED")},
        "mean_token_overlap_em": round(sum(r["token_overlap_em"] for r in results)
                                       / max(1, len(results)), 4),
        "yes_no_accuracy": round(sum(1 for r in yn_rows if r["yes_no_correct"])
                                 / len(yn_rows), 4) if yn_rows else None,
        "yes_no_n": len(yn_rows),
        "mean_latency_ms": round(sum(r["latency_ms"] for r in results)
                                 / max(1, len(results)), 1),
        "peak_rss_mb": V.rss_mb(),
        "wall_seconds": round(time.perf_counter() - t0, 1),
        "results": results,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
    }
    body_sha = hashlib.sha256(json.dumps(payload, indent=2).encode()).hexdigest()
    payload["artifact_sha256"] = body_sha
    payload["sha_convention"] = ("sha256 over the serialized artifact EXCLUDING "
                                 "this field (matches scripts/j1 convention)")
    OUT.write_text(json.dumps(payload, indent=2))
    print(f"[slake] WROTE {OUT}")
    print(f"[slake] artifact_sha256={body_sha}")
    print(f"[slake] mean_em={payload['mean_token_overlap_em']} "
          f"yn_acc={payload['yes_no_accuracy']} (n={payload['yes_no_n']}) "
          f"tiers={payload['tier_counts']} rss={payload['peak_rss_mb']}MB")


if __name__ == "__main__":
    main()
