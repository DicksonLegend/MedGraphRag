#!/usr/bin/env bash
# Fetch NLMCXR_png.tgz (1.36 GB) AFTER the Qwen2-VL GGUF finishes, extract
# exactly 100 PNGs to images/sample100/, then delete the archive.
# Net permanent footprint ~10 MB. Headroom-guarded (<3 GB => abort).
set -u
ROOT="/home/dicksone/Documents/MedGraphRag"
LOG="$ROOT/data/external/download.log"
IMG="$ROOT/data/multimodal/images/sample100"
ARC="$ROOT/data/multimodal/images/NLMCXR_png.tgz"
URL="https://openi.nlm.nih.gov/imgs/collections/NLMCXR_png.tgz"

free_gb() { df -BG / | awk 'NR==2{gsub("G","",$4); print $4}'; }
log() { echo "[$(date -Is)] [imgblob] $*" >> "$LOG"; }

# Wait for the sequential queue to reach the end (gguf line logged or queue gone)
while pgrep -f download_queue.sh >/dev/null && ! grep -q "Qwen2-VL-2B-Instruct-Q4_K_M.gguf$" "$LOG" 2>/dev/null; do
  sleep 20
done
grep -q "OK .*Qwen2-VL-2B-Instruct-Q4_K_M.gguf" "$LOG" || { log "SKIP blob: gguf not OK"; exit 1; }

mkdir -p "$IMG"
n=$(find "$IMG" -name '*.png' | wc -l)
if [ "$n" -ge 100 ]; then log "SKIP blob: already have $n pngs"; exit 0; fi
if [ "$(free_gb)" -lt 3 ]; then log "HEADROOM STOP blob"; exit 9; fi

log "GET $URL -> $ARC"
nice -n 10 curl -sSL --retry 3 --retry-delay 10 -C - -o "$ARC.part" "$URL" \
  && mv "$ARC.part" "$ARC" \
  && log "OK $ARC size=$(stat -c%s "$ARC") sha256=$(sha256sum "$ARC" | cut -d' ' -f1)" \
  || { log "FAIL blob download"; exit 1; }

tar xzf "$ARC" -C "$(dirname "$IMG")"
# flatten: take first 100 pngs from the extracted png/ dir
SRC="$(dirname "$IMG")/png"
i=0
for f in "$SRC"/*.png; do
  [ $i -ge 100 ] && break
  cp "$f" "$IMG/"; i=$((i+1))
done
rm -rf "$SRC" "$ARC"
log "BLOB DONE: extracted $i pngs to sample100, archive removed, free_gb=$(free_gb)"
