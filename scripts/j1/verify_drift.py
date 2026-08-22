#!/usr/bin/env python3
import json
import hashlib
from pathlib import Path

pre_path = Path("evaluations/j1_regression_pre.json")
post_path = Path("evaluations/j1_regression_post.json")

with open(pre_path) as f:
    pre = json.load(f)

with open(post_path) as f:
    post = json.load(f)

# Strip runtime latency and compare pure retrieval outcomes
def extract_retrieval_signature(data):
    sig = []
    for q in data["results"]:
        q_sig = {
            "id": q["id"],
            "query": q["query"],
            "top_doc_id": q["top_doc_id"],
            "top_fused_score": q["top_fused_score"],
            "items_count": q["items_count"],
            "entities_reached": q["entities_reached"],
            "chunks_from_graph": q["chunks_from_graph"],
            "items": q["retrieved_items"],
        }
        sig.append(q_sig)
    return sig

pre_sig = extract_retrieval_signature(pre)
post_sig = extract_retrieval_signature(post)

pre_bytes = json.dumps(pre_sig, indent=2, sort_keys=True).encode("utf-8")
post_bytes = json.dumps(post_sig, indent=2, sort_keys=True).encode("utf-8")

pre_hash = hashlib.sha256(pre_bytes).hexdigest()
post_hash = hashlib.sha256(post_bytes).hexdigest()

print(f"Pre-Build Retrieval Content SHA-256 : {pre_hash}")
print(f"Post-Build Retrieval Content SHA-256: {post_hash}")
print(f"Drift: {'0.00% DRIFT (100% IDENTICAL)' if pre_hash == post_hash else 'DRIFT DETECTED'}")

# Update the json files to also save the deterministic retrieval_content_sha256
pre["retrieval_content_sha256"] = pre_hash
with open(pre_path, "w") as f:
    json.dump(pre, f, indent=2, sort_keys=True)

post["retrieval_content_sha256"] = post_hash
with open(post_path, "w") as f:
    json.dump(post, f, indent=2, sort_keys=True)
