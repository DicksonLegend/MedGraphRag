# MedGraphRAG Backend

Runtime application for the MedGraphRAG hybrid retrieval engine.

## Architecture

```
backend/
├── app/
│   ├── main.py          # FastAPI entry point
│   ├── config.py        # Paths + retrieval hyper-params (.env driven)
│   ├── core/
│   │   └── retrieval/   # Step 6: Hybrid Retrieval Engine
│   │       ├── embedder.py     # MedCPT query encoder (CPU-only singleton)
│   │       ├── faiss_store.py  # Load IVFpq index + sidecar parquet, vector search
│   │       ├── graph_store.py  # Kùzu seeded graph traversal (1–2 hops)
│   │       ├── fusion.py       # RRF + graph-boost + category balancing
│   │       ├── schemas.py      # EvidenceItem / RetrievalResult typed models
│   │       └── service.py      # HybridRetrievalService.retrieve()
│   └── api/             # Stub — routes to be added in later steps
├── eval/probe_retrieval.py  # 10 probe queries + validation report
├── requirements.txt
└── README.md
```

## Important Constraints

- **CPU-only retrieval**: 0 VRAM. GPU reserved for future LLM (Step 7+).
- **Read-only**: backend/ only reads `index/global/`. Never writes to index/.
- **Do NOT import** from `Embedding_pipline/` or `Data_Normalization/` — those are offline build pipelines.
- **RAM budget**: Peak < 12 GB.
- **Latency target**: < 2 s total per query (baseline 47 ms achieved in validation).

## Running

```bash
# Use the project virtual environment
cd /home/dicksone/Documents/MedGraphRag
source Data_Normalization/.venv/bin/activate

# Run eval probe queries
python backend/eval/probe_retrieval.py

# Start API server (Step 7+)
uvicorn backend.app.main:app --reload
```

## Index Artifacts (read-only)

| Artifact | Path | Size |
|---|---|---|
| FAISS IVFpq index | `index/global/faiss.index` | 240 MB |
| Sidecar parquet | `index/global/id_mapping.parquet` | 30 MB |
| Chunks JSONL | `index/global/chunks.jsonl` | 2.6 GB |
| Chunk line offsets | `index/global/chunk_line_offsets.npy` | 18 MB |
| Kùzu graph DB | `index/global/kuzu_db_v5` | 1.2 GB |
