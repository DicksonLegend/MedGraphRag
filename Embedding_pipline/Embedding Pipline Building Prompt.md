
---

# Master Prompt — Reusable Classification · Chunking · Embedding · FAISS + Kùzu Ingestion

Paste everything below into the coding agent (Claude Code / Antigravity). The input is the `/normalized/` folder of per‑file JSONs produced by the normalization pass (schema_version **1.2**). Do not write implementation code until **Step 0** is shown and I confirm, and do not run full‑scale chunking or graph extraction until the two confirmation gates in Steps 2 and 5 are approved.

## 0. Purpose & the one rule that governs everything

This pipeline turns normalized documents into a **searchable vector index (FAISS)** plus a **relationship graph (Kùzu)**. It runs **once, offline, by an admin**, with no LangGraph and no agents.

**The single most important design requirement: this code must be reusable.** Today it builds the **global** knowledge base. Later, the *exact same functions* must build a **private** FAISS index + private Kùzu graph for each user‑uploaded report. Therefore **nothing may be hardcoded to a global path or a global index object.** Every read, write, index handle, and manifest path must flow through a single `StoreDestination` configuration object (see §2). If you hardcode `/index/faiss/global.index` anywhere, the design fails the reusability requirement and must be refactored. Design the function signatures now as e.g. `build_vector_store(chunks_iter, destination, device_policy)` and `build_graph(docs_iter, destination)` so a user upload later just passes a different `destination` and a tiny corpus.

The two knowledge spaces this one codebase serves:
- **Global** (this run): curated guidelines, diseases, drugs, lab refs, ontologies, papers, books → `destination.root = /index/global/`. Read‑only to users afterward; updatable later by re‑running with the same destination (incremental add, see §4).
- **Private per‑user** (later, not this run): one uploaded report → `destination.root = /private_store/<user_id>/`. Same schema, same functions, tiny corpus. Guest sessions delete the directory on end; logged‑in users keep it encrypted. The global store is **never** written to by a user upload, and a user's vectors/nodes are **never** visible to another user. State this invariant in a comment at the top of the destination module.

## 1. Configuration block (all tunables in one place — use these defaults for a 6 GB VRAM / 16 GB RAM laptop)

Put every magic number in a config; do not scatter them. Recommended defaults:

- `chunk_min_tokens=300`, `chunk_max_tokens=500`, `chunk_overlap_ratio=0.15`, `chunk_hard_max_tokens=800` (a table/numeric block that won't fit 500 may grow to 800 with a logged warning; never beyond).
- `embed_model_corpus = "ncbi/MedCPT-Article-Encoder"`, `embed_model_query = "ncbi/MedCPT-Query-Encoder"` (query encoder is **not** used in this offline build except in final validation; record both names + revisions in the build report so query‑time uses the matching family).
- `vector_dim = 768`, `normalize_vectors = true`, `faiss_metric = METRIC_INNER_PRODUCT` (so scores are cosine in [-1,1] after L2‑normalization).
- `faiss_index_type = IndexHNSWFlat`, `hnsw_M = 32`, `hnsw_efConstruction = 200`, `hnsw_efSearch = 128`. **HNSW is mandatory** (not IVF/PQ) because it supports incremental `add()` without retraining — this is what makes the store reusable for per‑user graphs and for incremental global updates.
- `embed_batch_size = 32` (starting value; see §3 for the back‑off ladder).
- `embed_device = "cuda"` for this offline build **only** (nothing else is running). Query‑time embedding later must use CPU — do not bake GPU into any code path that could run at query time.
- `kuzu_batch_rows = 5000`, `kuzu_use_transactions = true`.
- `languages_keep = ["en"]` (filter non‑English at chunking; tag every chunk with its `language` regardless).
- `vram_reserve_gb = 1.5`, `ram_reserve_gb = 2.0`, `gc_every_embed_batches = 25`, `per_batch_timeout_s = 300`.
- `cpu_worker_max = 3` (only for CPU‑only stages: chunking, Kùzu writes. **Never** for the GPU embedder).

## 2. The `StoreDestination` object (reusability contract)

Define one dataclass/dict that fully describes where a build writes, e.g. fields: `root`, `faiss_index_path`, `faiss_mapping_path`, `kuzu_db_path`, `chunks_path`, `manifest_path`, `logs_dir`, `checkpoint_path`, `build_report_path`. The global run instantiates it with `/index/global/...`; a future user run instantiates it with `/private_store/<uid>/...`. **All** file IO in the pipeline reads paths from this object. This is non‑negotiable.

## 3. Hardware safety — read carefully, this laptop has crashed before

These guards are mandatory because the same machine OOM'd during the earlier Docling pass. Implement all of them; do not treat them as optional polish.

- **Load the embedder exactly once**, keep it on GPU only for the embedding stage, then `del` it and call `torch.cuda.empty_cache()` + `gc.collect()` **before** the FAISS build stage begins (FAISS build is CPU; do not let the model sit in VRAM during it).
- **VRAM guard before every embed batch:** read free VRAM via `torch.cuda.mem_get_info()`; if free < `vram_reserve_gb`, halve `embed_batch_size`. If batch size is already 1 and a batch still OOMs, catch the `RuntimeError`, `empty_cache()`, switch the **remainder** of the corpus to CPU embedding, and log `device_fallback=cuda->cpu`. Never let an OOM kill the run.
- **System RAM guard:** before each stage and every N chunks, check `psutil.virtual_memory().available`; if < `ram_reserve_gb`, flush in‑memory buffers to disk, `gc.collect()`, and if still low, pause and log a warning.
- **Never hold the whole corpus in RAM.** Stream `chunks.jsonl` in batches; after `index.add(batch_vectors)` immediately free the numpy batch; keep `id_mapping` as an **append‑only file on disk**, not a giant in‑memory dict. Kùzu writes go in transactions of `kuzu_batch_rows`, committed and freed per transaction.
- **Single process for the GPU embedder.** No multiprocessing/multithreading on the model. CPU‑only stages may use up to `cpu_worker_max` workers.
- **Per‑batch timeout** (`per_batch_timeout_s`) so a stuck batch cannot hang the machine; on timeout, log and skip that batch with a resume marker.
- **Graceful shutdown:** register SIGINT/SIGTERM handlers that flush the partial FAISS index, the id‑mapping file, the manifest, and the checkpoint, then exit cleanly so the next run resumes.

## 4. Step 0 — Dry run (show me, then stop)

Scan `/normalized/` and report, per category: file count; count with non‑empty `structured_data`; count with non‑null `text.abstract`; count with non‑empty `figures[].ocr_text`; total estimated tokens; and a list of any file that does not match schema 1.2 (missing required keys). Also report the **content‑dedup preview** (next paragraph). Show all of this and wait for my go.

## 5. Step 1 — Classification manifest + content dedup (touches no original file)

Produce `<destination.manifest_path>` as JSONL, one line per document: `{"document_id", "category", "subpath", "subcategory", "language", "content_hash", "target", "chunk_count_estimate"}`. Do **not** mutate the normalized JSONs.

Classification rule table (by `category`):

| category | base target |
|---|---|
| guideline | both |
| disease | both |
| drug | both |
| lab_reference | graph (upgrade to both if `text.body` has descriptive prose) |
| ontology | graph |
| textbook | faiss |
| research_paper | faiss |
| evidence_qa | faiss |
| qa_benchmark | **none** (evaluation set — exclude from BOTH indexes entirely) |

Override: if `structured_data` is non‑empty, always add `graph` to the target. Language filter: if `language` not in `languages_keep`, set target contribution for FAISS to none (still allow graph if structured) and log it.

**Content dedup (robustness net):** compute `content_hash = sha256(normalized(text.body) + normalized(serialized(structured_data)))`. If two or more documents share an identical `content_hash`, keep one canonical (lexicographically first `document_id`), mark the others `target=none` with `dedup_of=<canonical_id>`, and log the mapping. This guarantees the index never contains duplicate vectors or duplicate graph nodes, regardless of where a duplicate originated (including any future user upload). This is a pipeline safety property, not a comment on upstream data.

## 6. Step 2 — Chunking (FAISS‑bound docs only) — with confirmation gate

For every document whose `target` includes `faiss` and whose `text.body` is non‑empty:

- Chunk `text.body` into 300–500 token pieces with ~15% overlap. Break only at sentence/paragraph/heading boundaries — **never mid‑sentence**.
- **Medical‑number safety:** detect table‑like / numeric‑dense blocks (lines matching patterns like `<label> <number> <unit>`, ranges `x–y`, or markdown/pipe tables). Keep such a block **atomic** in one chunk even if it slightly exceeds 500 tokens (up to `chunk_hard_max_tokens=800`, log a warning). Never split a single lab‑value row across two chunks.
- If `text.abstract` is non‑null, emit it as its own chunk (`chunk_type=abstract`); do not merge it into body chunks.
- If `figures[]` contains entries with non‑empty `ocr_text`, emit each as its own chunk (`chunk_type=figure`, carry `page_number`); this rescues OCR'd charts/tables that would otherwise be invisible to retrieval.
- Every chunk record:
  ```
  { "chunk_id": "{document_id}__c{n}", "document_id", "text",
    "chunk_type": "abstract|body|figure",
    "category", "subpath", "subcategory", "source", "title", "language",
    "page_number": <or null> }
  ```
  (Inherit `subpath`/`subcategory`/`language` from the parent — they are needed later for filtered retrieval and graph provenance.)
- Documents with `target=graph` only, empty body, or filtered language are **not** chunked.

Write chunks to `<destination.chunks_path>`. **GATE:** before running this on the full corpus, chunk **3 representative documents** (one guideline PDF with a table, one research paper with an abstract, one ontology/lab file if it has any FAISS target) and show me the resulting chunks so I can verify boundary/number handling. Wait for approval.

## 7. Step 3 — Embedding with MedCPT (article encoder, offline, guarded)

- Use `embed_model_corpus` (the **article** encoder) for all corpus chunks. Embedding the corpus with the article encoder and later querying with the query encoder is the correct asymmetric MedCPT setup — do **not** use the query encoder here.
- L2‑normalize every vector (so inner product = cosine).
- Stream `chunks.jsonl` in batches of `embed_batch_size`, applying every guard in §3. Save progress incrementally: after each batch, append vectors via `index.add()` (HNSW supports incremental add), append the corresponding id‑mapping lines to disk, and write a checkpoint (last processed `chunk_id` / batch index). On restart, reload the on‑disk index + mapping and resume from the checkpoint — never re‑embed completed chunks.
- Record `embed_model` name + revision + `vector_dim` + `metric` into `<destination.build_report_path>`.

## 8. Step 4 — FAISS index + id mapping

- Persist `<destination.faiss_index_path>` (the HNSW index) and `<destination.faiss_mapping_path>` (JSONL mapping each internal int id → `{chunk_id, document_id, category, subpath, subcategory, source, title, page_number}`). The mapping stays on disk; load only what a query needs.
- Because HNSW supports `add()`, the same index file can later grow (incremental global updates) or be freshly created per user (private store) using the identical code path.

## 9. Step 5 — Kùzu graph construction — with confirmation gate

For documents whose `target` includes `graph`, extract nodes/edges. Default schema:

- **Node types:** `Disease, Symptom, Test, Drug, Guideline, Treatment, Organ, SideEffect` (each with a stable string primary key and a `source_provenance` property pointing back to `document_id`/`chunk_id`).
- **Edge types:** `HAS_SYMPTOM, INDICATES, TREATED_BY, NORMAL_RANGE, RECOMMENDED_BY, CAUSES_SIDE_EFFECT, CONTRAINDICATED_WITH, MAPPED_TO`.

Per‑source extraction strategy: `structured_data` rows from drug/lab/ontology sources map near‑directly to nodes/edges; guideline/disease prose needs lightweight entity extraction first (dictionary/regex over UMLS/LOINC/RxNorm terms where available, **no LLM** in v1). **Idempotency:** create the schema with `CREATE ... IF NOT EXISTS`; ensure no duplicate nodes on re‑run by keying on the stable id (dedup in‑memory per batch, or ON‑CONFLICT if the Kùzu version supports it — document whichever you use); guard against duplicate edges. Write in transactions of `kuzu_batch_rows`.

**GATE:** before running on the full corpus, show me your proposed node/edge mapping for **Drug_database, Lab_rev_data, Medical_ontologies, and Disease_knowledge**, each with 2–3 real example rows mapped to concrete nodes/edges. Wait for my approval — this step is the most error‑prone and the most expensive to redo at scale.

Persist the graph to `<destination.kuzu_db_path>`.

## 10. Idempotency, logging, error handling

- Before processing any document, compare its `metadata.file_hash_sha256` against the manifest/checkpoint; skip unchanged ones.
- Each stage (classify / chunk / embed / faiss / graph) is independently re‑runnable and resumable via its checkpoint.
- Wrap every per‑document operation in try/except; on failure, log filename + `document_id` + traceback to `<destination.logs_dir>/failed.jsonl` and continue. Never let one bad file stop the run.
- Per‑stage logs + a final `<destination.build_report_path>` containing: encoder name+revision, vector dim, metric, index type+HNSW params, total chunks, vector count, FAISS disk size, Kùzu node/edge counts **by type**, dedup count, language‑filtered count, **peak VRAM, peak RAM**, and per‑stage wall time.

## 11. Final validation (show me, then stop)

Print the build report, then:
- **5 random FAISS searches:** embed each sample medical question with the **query encoder** (`embed_model_query`) and search the corpus index (this is the correct asymmetric retrieval; a random‑vector search would be meaningless). Show question → top‑5 chunk texts + category + source + score.
- **5 random graph queries** (e.g. a disease → its treatments; a drug → its side effects; a test → its normal range). Show the traversed nodes/edges.
So I can sanity‑check quality before anything moves on.

## 12. What NOT to do

- Do not modify the original `/normalized/` files; classification is a separate manifest.
- Do not hardcode any global path or index handle — everything goes through `StoreDestination` (§2).
- Do not chunk graph‑only documents, empty‑body documents, or language‑filtered documents.
- Do not include `qa_benchmark` documents in either index.
- Do not embed the corpus with the query encoder (or vice versa).
- Do not run full‑scale chunking or graph extraction before the two confirmation gates (§6, §9).
- Do not let the GPU embedder run under multiprocessing, and do not keep the model loaded during the CPU FAISS‑build stage.
- Do not hold all chunks or all vectors in RAM; stream and free per batch; keep the id‑mapping on disk.
- Do not split a numeric/lab‑value row across chunks.
- Do not skip duplicates silently — log them in the manifest.
- Do not use GPU for any code path that could later run at query time.
- Do not let an OOM or a single bad file terminate the run — back off, fall back to CPU, or log‑and‑continue.

---

