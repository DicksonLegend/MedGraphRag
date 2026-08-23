#!/usr/bin/env bash
# MedGraphRag multimodal download queue — bounded budget (<10 GB), sequential,
# resumable (curl -C -), headroom-guarded (<3 GB free => stop new downloads).
# Protocol: nice -n 10, one transfer at a time, sha256 logged to MANIFEST.
set -u
ROOT="/home/dicksone/Documents/MedGraphRag"
LOG="$ROOT/data/external/download.log"
R="$ROOT/data/multimodal/reports"
IMG="$ROOT/data/multimodal/images/sample100"
DS="$ROOT/data/external/datasets"
MO="$ROOT/data/external/models"
mkdir -p "$R" "$IMG" "$DS" "$MO"

free_gb() { df -BG / | awk 'NR==2{gsub("G","",$4); print $4}'; }
log() { echo "[$(date -Is)] $*" >> "$LOG"; }

fetch() { # url dest
  local url="$1" dest="$2"
  [ -s "$dest" ] && { log "SKIP (exists) $dest"; return 0; }
  if [ "$(free_gb)" -lt 3 ]; then log "HEADROOM STOP before $url"; return 9; fi
  log "GET $url -> $dest"
  nice -n 10 curl -sSL --retry 3 --retry-delay 10 -C - -o "$dest.part" "$url" \
    && mv "$dest.part" "$dest" && { local s; s=$(sha256sum "$dest" | cut -d' ' -f1); \
       log "OK $dest size=$(stat -c%s "$dest") sha256=$s"; return 0; } \
    || { log "FAIL $url"; rm -f "$dest.part"; return 1; }
}

log "=== download queue start ==="

# 1. OpenI reports (text-only collection, ~40 MB)
fetch "https://openi.nlm.nih.gov/imgs/collections/NLMCXR_reports.tgz" "$R/NLMCXR_reports.tgz"

# 2. VQA-RAD questions JSON (1.4 MB)
fetch "https://osf.io/download/6qdas/" "$DS/VQA_RAD_Dataset_Public.json"

# 3. CLIP ViT-B/16 backbone for CheXzero (~605 MB)
mkdir -p "$MO/clip-vit-base-patch16"
fetch "https://huggingface.co/openai/clip-vit-base-patch16/resolve/main/pytorch_model.bin" "$MO/clip-vit-base-patch16/pytorch_model.bin"
for f in config.json preprocessor_config.json tokenizer.json vocab.json merges.txt special_tokens_map.json tokenizer_config.json; do
  fetch "https://huggingface.co/openai/clip-vit-base-patch16/resolve/main/$f" "$MO/clip-vit-base-patch16/$f"
done

# 4. Qwen2-VL-2B-Instruct GGUF Q4_K_M (~2 GB)
fetch "https://huggingface.co/ggml-org/Qwen2-VL-2B-Instruct-GGUF/resolve/main/Qwen2-VL-2B-Instruct-Q4_K_M.gguf" "$MO/Qwen2-VL-2B-Instruct-Q4_K_M.gguf"

# 5. SLAKE (Google Drive, small zip) — confirm-token flow
if [ "$(free_gb)" -ge 3 ]; then
  log "GET SLAKE via Google Drive"
  nice -n 10 curl -sSL -c /tmp/opencode/slake_cj "https://drive.google.com/uc?export=download&id=1EZ0WpO5Z6BJUqC3iPBUQJJS1INWSMsh7U" -o /tmp/opencode/slake_page.html
  CONFIRM=$(grep -o 'confirm=[0-9A-Za-z_-]*' /tmp/opencode/slake_page.html | head -1 | cut -d= -f2)
  [ -z "$CONFIRM" ] && CONFIRM=t
  nice -n 10 curl -sSL -b /tmp/opencode/slake_cj --retry 3 -C - \
    "https://drive.usercontent.google.com/download?id=1EZ0WpO5Z6BJUqC3iPBUQJJS1INWSMsh7U&export=download&confirm=$CONFIRM" \
    -o "$DS/slake.zip.part" \
    && mv "$DS/slake.zip.part" "$DS/slake.zip" \
    && log "OK slake.zip size=$(stat -c%s "$DS/slake.zip") sha256=$(sha256sum "$DS/slake.zip" | cut -d' ' -f1)" \
    || log "FAIL slake.zip"
fi

# 6. VQA-RAD image folder zip (OSF folder archive)
if [ "$(free_gb)" -ge 3 ]; then
  fetch "https://files.osf.io/v1/resources/89kps/providers/osfstorage/5b21453986d8510011c277bc/?zip=" "$DS/VQA_RAD_images.zip"
fi

# 7. MedMCQA — relocate from existing local HF cache (no network needed)
if [ "$(free_gb)" -ge 3 ]; then
  SRC="$ROOT/Datasets/datasets--openlifescienceai--medmcqa"
  if [ -d "$SRC" ]; then
    mkdir -p "$DS/medmcqa"
    find "$SRC/snapshots" -type f ! -name "*.md" -exec cp {} "$DS/medmcqa/" \; 2>>"$LOG" \
      && log "OK medmcqa relocated from local cache: $(ls "$DS/medmcqa" | tr '\n' ' ')" \
      || log "FAIL medmcqa relocation"
  fi
fi

# 8. OpenI sample100 images — ids extracted from reports XMLs by helper
PY="$ROOT/Data_Normalization/.venv/bin/python"
nice -n 10 "$PY" "$ROOT/scripts/multimodal/fetch_openi_sample.py" >> "$LOG" 2>&1

log "=== download queue end ==="
