"""
MedGraphRAG Backend — Configuration
=====================================
All paths and retrieval hyper-parameters are driven from environment variables
(.env file or shell exports). No magic numbers in the retrieval or generation code.

Environment variables can be set in a .env file at the project root or in the
backend/ directory. Pydantic-settings auto-discovers them.

Step 6: Retrieval settings (FAISS + Kùzu + RRF fusion)
Step 7: LLM settings (llama-cpp-python, Qwen2.5-7B-Instruct Q4_K_M, GPU offload)
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Dict, List, Optional

from pydantic import BaseModel, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Project root resolved relative to this file's location
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parents[2]  # backend/app/config.py -> MedGraphRag/
_BACKEND_DIR = PROJECT_ROOT / "backend"
_PROJECT_ROOT = PROJECT_ROOT


# ---------------------------------------------------------------------------
# LLM configuration sub-model (Step 7)
# Nested inside Settings so all values are env-var driven with prefix MEDGRAPH_LLM_
# ---------------------------------------------------------------------------

class LLMSettings(BaseModel):
    """
    Configuration for the GGUF language model loaded via llama-cpp-python.

    Default: Qwen2.5-7B-Instruct-Q4_K_M (bartowski/Qwen2.5-7B-Instruct-GGUF)
    Documented fallback: bartowski/Mistral-7B-Instruct-v0.3-GGUF
                         Mistral-7B-Instruct-v0.3-Q4_K_M.gguf

    To swap models: change repo + gguf_file, download the file to models/,
    and update model_path accordingly — no code changes required.

    Qwen2.5 notes:
    - No thinking mode (not a Qwen3 variant — do NOT set thinking=True).
    - ChatML template is embedded in the GGUF; always use create_chat_completion().

    VRAM budget (RTX 3050, 6 GB):
    - Q4_K_M weights: ~4.4–4.7 GB
    - Quantized KV cache (Q8_0, 6144 ctx): ~0.2–0.6 GB
    - CUDA overhead: ~0.1 GB
    - Total: ~4.7–5.4 GB → headroom ~0.6–1.4 GB
    """

    # ── Model identity ────────────────────────────────────────────────────────
    repo: str = Field(
        default="bartowski/Qwen2.5-7B-Instruct-GGUF",
        description="HuggingFace repo for documentation and `hf download` reference.",
    )
    gguf_file: str = Field(
        default="Qwen2.5-7B-Instruct-Q4_K_M.gguf",
        description="GGUF filename inside the repo and under models/.",
    )
    model_path: Path = Field(
        default=PROJECT_ROOT / "models" / "Qwen2.5-7B-Instruct-Q4_K_M.gguf",
        description=(
            "Local path to the GGUF file, relative to project root. "
            "Override with an absolute path if needed."
        ),
    )

    # ── Documented fallback (Mistral-7B-Instruct-v0.3) ───────────────────────
    # fallback_repo: bartowski/Mistral-7B-Instruct-v0.3-GGUF
    # fallback_gguf: Mistral-7B-Instruct-v0.3-Q4_K_M.gguf
    # Download: hf download bartowski/Mistral-7B-Instruct-v0.3-GGUF \
    #           Mistral-7B-Instruct-v0.3-Q4_K_M.gguf --local-dir models/
    # Then set: model_path = models/Mistral-7B-Instruct-v0.3-Q4_K_M.gguf

    # ── GPU offload ───────────────────────────────────────────────────────────
    n_gpu_layers: int = Field(
        default=-1,
        description=(
            "Number of layers to offload to GPU. "
            "-1 = all layers (full GPU offload). "
            "28 = partial offload fallback. "
            "0 = CPU-only fallback."
        ),
    )
    offload_kqv: bool = Field(
        default=True,
        description="Offload K/V/Q tensors to GPU (requires n_gpu_layers > 0).",
    )
    flash_attn: bool = Field(
        default=True,
        description="Enable Flash Attention 2 (RTX 3050 Ampere supports FA2 via CUDA 12.x).",
    )

    # ── KV cache quantization ─────────────────────────────────────────────────
    type_k: str = Field(
        default="q8_0",
        description="K-cache quantization type. Q8_0 ≈ 0.25–0.5 GB at 6k ctx.",
    )
    type_v: str = Field(
        default="q8_0",
        description="V-cache quantization type.",
    )

    # ── Context window ────────────────────────────────────────────────────────
    n_ctx: int = Field(
        default=6144,
        description=(
            "Context window size in tokens. "
            "Keep total prompt + output ≤ 6144 to stay within KV-cache budget."
        ),
    )

    # ── Generation ────────────────────────────────────────────────────────────
    temperature: float = Field(
        default=0.0,
        description="Sampling temperature. 0.0 for deterministic medical answers.",
    )
    max_tokens: int = Field(
        default=800,
        description="Maximum output tokens per generation call.",
    )
    top_p: float = Field(
        default=0.9,
        description="Top-p nucleus sampling parameter.",
    )
    repeat_penalty: float = Field(
        default=1.1,
        description="Repetition penalty to reduce citation loops.",
    )

    # ── Context builder budget ────────────────────────────────────────────────
    context_max_tokens: int = Field(
        default=2500,
        description=(
            "Maximum tokens allocated to evidence blocks in the prompt. "
            "Leaves room for system prompt (~200t) + user query (~100t) + output (~800t) "
            "within the 6144 ctx window."
        ),
    )
    evidence_max_per_prompt: int = Field(
        default=8,
        description="Maximum number of EvidenceItems included in each prompt.",
    )

    # ── Evidence confidence weights ───────────────────────────────────────────
    confidence_score_weight: float = Field(
        default=0.6,
        description="Weight given to mean fused_score in confidence calculation.",
    )
    confidence_diversity_weight: float = Field(
        default=0.4,
        description="Weight given to source/category diversity in confidence calculation.",
    )

    # ── Prompt template ───────────────────────────────────────────────────────
    system_prompt: str = Field(
        default=(
            "You are a medical assistant. Answer ONLY from the provided evidence. "
            "Cite every claim as [E#]. If evidence is insufficient, say so. "
            "Do NOT diagnose or prescribe. "
            "End with: This is information, not medical advice — consult your physician."
        ),
        description="System prompt sent to the model on every generation call.",
    )

    # ── Verbosity ─────────────────────────────────────────────────────────────
    verbose: bool = Field(
        default=False,
        description="Enable verbose llama.cpp logging (chatty — disable in production).",
    )


# ---------------------------------------------------------------------------
# Project root resolved relative to this file's location
# ---------------------------------------------------------------------------
_BACKEND_DIR = Path(__file__).parent.parent        # backend/
_PROJECT_ROOT = _BACKEND_DIR.parent               # MedGraphRag/


class Settings(BaseSettings):
    """
    All tunable knobs for the MedGraphRAG retrieval backend.

    Defaults are production-ready for the global CPU-only index.
    Override any value via environment variable or .env file.
    """

    model_config = SettingsConfigDict(
        env_prefix="MEDGRAPH_",
        env_file=[str(_PROJECT_ROOT / ".env"), str(_BACKEND_DIR / ".env")],
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Core system paths ───────────────────────────────────────────────────
    project_root: Path = Field(
        default=PROJECT_ROOT,
        description="Absolute path to the MedGraphRag project root.",
    )
    index_dir: Path = Field(
        default=PROJECT_ROOT / "index" / "global",
        description="Read-only index artifact directory.",
    )
    models_dir: Path = Field(
        default=PROJECT_ROOT / "models",
        description="Directory for local model weight files.",
    )
    evaluations_dir: Path = Field(
        default=PROJECT_ROOT / "evaluations",
        description="Directory for evaluation output reports and fixtures.",
    )
    faiss_index_path: Path = Field(
        default=PROJECT_ROOT / "index" / "global" / "faiss.index",
        description="Path to the IVFpq FAISS index file.",
    )
    sidecar_parquet_path: Path = Field(
        default=PROJECT_ROOT / "index" / "global" / "id_mapping.parquet",
        description="Path to the chunk-id sidecar Parquet file.",
    )
    chunks_jsonl_path: Path = Field(
        default=PROJECT_ROOT / "index" / "global" / "chunks.jsonl",
        description="Path to the chunks JSONL text file.",
    )
    chunk_offsets_npy_path: Path = Field(
        default=PROJECT_ROOT / "index" / "global" / "chunk_line_offsets.npy",
        description="Path to the precomputed byte-offset index for chunks.jsonl.",
    )
    kuzu_db_path: Path = Field(
        default=PROJECT_ROOT / "index" / "global" / "kuzu_db_v5",
        description="Path to the Kùzu single-file graph database.",
    )

    # ── Embedding model ───────────────────────────────────────────────────────
    embed_model_name: str = Field(
        default="ncbi/MedCPT-Query-Encoder",
        description="HuggingFace model name for query encoding (CPU-only).",
    )
    embed_device: str = Field(
        default="cpu",
        description="Torch device for embedding. Must remain 'cpu' to reserve GPU for LLM.",
    )
    embed_max_length: int = Field(
        default=512,
        description="Max token length for the query encoder.",
    )
    embed_batch_size: int = Field(
        default=1,
        description="Batch size for query encoding (1 is fine; queries arrive one at a time).",
    )

    # ── FAISS search ─────────────────────────────────────────────────────────
    faiss_top_k_raw: int = Field(
        default=80,
        description=(
            "Number of raw candidates to fetch from FAISS before category filtering. "
            "Larger value compensates for lab_reference dominance (71% of index)."
        ),
    )
    faiss_nprobe: int = Field(
        default=64,
        description=(
            "IVFpq nprobe — number of Voronoi cells to inspect. "
            "Higher = better recall, lower latency cost. 64 is a good balance."
        ),
    )

    # ── BM25 sparse retrieval (for baselines) ─────────────────────────────────
    bm25_candidate_pool: int = Field(
        default=200,
        validation_alias="MEDGRAPH_BM25_CANDIDATE_POOL",
        description="FAISS candidate pool size for per-query BM25 indexing (memory vs recall tradeoff).",
    )
    bm25_batch_size: int = Field(
        default=64,
        validation_alias="MEDGRAPH_BM25_BATCH_SIZE",
        description="Batch size for faiss_store.batch_load_chunk_texts (tune for seek efficiency).",
    )

    # ── Category balancing / caps ─────────────────────────────────────────────
    # lab_reference is 71.70% of the index; without a cap it floods every result.
    # These caps apply AFTER FAISS retrieval and BEFORE fusion.
    category_max_chunks: Dict[str, int] = Field(
        default={
            "lab_reference":      5,   # hard cap — lab templates dominate (71% of index)
            "guideline":         10,
            "drug":               8,
            "textbook":          10,
            "research_paper":    10,
            "disease":            6,
            "clinical_reference": 5,
        },
        description=(
            "Per-category hard cap on number of FAISS chunks included in fusion. "
            "Prevents lab_reference (71% of index) from flooding non-lab queries."
        ),
    )
    faiss_final_k: int = Field(
        default=30,
        description="Total candidate pool size after category balancing, fed into fusion.",
    )

    # ── Ablation flags ───────────────────────────────────────────────────────
    retrieval_graph_enabled: bool = Field(
        default=True,
        description="Enable Kùzu graph traversal in hybrid retrieval.",
    )
    pipeline_verification_enabled: bool = Field(
        default=True,
        description="Enable single-pass verification in MedGraphRAG pipeline.",
    )

    # ── Graph traversal ───────────────────────────────────────────────────────
    graph_seed_docs: int = Field(
        default=5,
        description="Number of top FAISS document_ids used as graph traversal seeds.",
    )
    graph_max_hops: int = Field(
        default=2,
        description="Maximum graph traversal depth from seed nodes.",
    )
    graph_entity_chunk_limit: int = Field(
        default=6,
        description=(
            "Max chunks to pull back per graph-reached entity "
            "(via DOCUMENT_MENTIONS or HAS_CHUNK pivot)."
        ),
    )
    graph_max_results: int = Field(
        default=20,
        description="Max number of graph-sourced EvidenceItems returned.",
    )

    # ── Edge trust tiers ─────────────────────────────────────────────────────
    # High-trust: ontological / diagnostic / structural linkage.
    # Low-trust: drug–disease edges — known noisy (Ketorolac→Asthma, etc.)
    high_trust_edges: List[str] = Field(
        default=["LABTEST_RELATED_TO", "DISEASE_MAPPED_TO", "DOCUMENT_MENTIONS",
                 "IS_A", "RELATED_TO"],
        description="Edge types treated as high-trust; their evidence gets a graph boost.",
    )
    low_trust_edges: List[str] = Field(
        default=["DRUG_TREATS", "DRUG_CAUSES", "DRUG_CAUSES_SE"],
        description=(
            "Edge types treated as low-trust (noisy drug–disease edges). "
            "Graph results reached exclusively via these edges are down-weighted."
        ),
    )
    low_trust_score_penalty: float = Field(
        default=0.5,
        description="Multiplicative penalty applied to graph_score for low-trust-only paths.",
    )

    # ── Reciprocal Rank Fusion (RRF) ─────────────────────────────────────────
    rrf_k: int = Field(
        default=60,
        description="RRF smoothing constant k. Standard value: 60.",
    )
    rrf_faiss_weight: float = Field(
        default=1.0,
        description="Weight for the FAISS ranking list in RRF fusion.",
    )
    rrf_graph_weight: float = Field(
        default=0.8,
        description="Weight for the graph ranking list in RRF fusion.",
    )
    graph_boost: float = Field(
        default=0.15,
        description=(
            "Additive bonus to fused_score for chunks supported by ≥1 high-trust edge. "
            "Rewards evidence corroborated by the knowledge graph."
        ),
    )

    # ── Kùzu database ────────────────────────────────────────────────────────
    kuzu_buffer_pool_mb: int = Field(
        default=384,
        description="Kùzu buffer pool size in MB. Kept low to stay within 12 GB RAM budget.",
    )
    kuzu_max_db_size_gb: int = Field(
        default=4,
        description="Kùzu max virtual DB size cap in GB.",
    )
    kuzu_max_threads: int = Field(
        default=2,
        description="Kùzu max worker threads.",
    )

    # ── Final output ─────────────────────────────────────────────────────────
    retrieval_top_n: int = Field(
        default=10,
        description="Number of EvidenceItems returned in the final RetrievalResult.",
    )
    text_snippet_max_chars: int = Field(
        default=400,
        description="Max characters in the text snippet stored on each EvidenceItem.",
    )

    # ── LLM & Generation settings (Step 7) ───────────────────────────────────
    llm_repo: str = Field(
        default="bartowski/Qwen2.5-7B-Instruct-GGUF",
        description="HuggingFace GGUF repository for the generation LLM.",
    )
    llm_gguf_file: str = Field(
        default="Qwen2.5-7B-Instruct-Q4_K_M.gguf",
        description="GGUF filename to download/load.",
    )
    llm_model_path: Path = Field(
        default=_PROJECT_ROOT / "models" / "Qwen2.5-7B-Instruct-Q4_K_M.gguf",
        description="Local filesystem path to the GGUF model weights.",
    )

    # Documented fallback model info (for reference/swapping):
    # llm_repo="bartowski/Mistral-7B-Instruct-v0.3-GGUF"
    # llm_gguf_file="Mistral-7B-Instruct-v0.3-Q4_K_M.gguf"

    llm_n_gpu_layers: int = Field(
        default=-1,
        description="Number of layers to offload to GPU (-1 = full offload).",
    )
    llm_n_ctx: int = Field(
        default=6144,
        description="Context window size in tokens (6144 keeps VRAM usage ≤ 5.5 GB).",
    )
    llm_flash_attn: bool = Field(
        default=True,
        description="Enable Flash Attention in llama.cpp.",
    )
    llm_offload_kqv: bool = Field(
        default=True,
        description="Offload KV cache to GPU memory.",
    )
    llm_type_k: str = Field(
        default="q8_0",
        description="Quantization type for key cache (q8_0 saves VRAM).",
    )
    llm_type_v: str = Field(
        default="q8_0",
        description="Quantization type for value cache (q8_0 saves VRAM).",
    )
    llm_temperature: float = Field(
        default=0.0,
        description="Sampling temperature for deterministic medical grounding.",
    )
    llm_max_tokens: int = Field(
        default=500,
        description="Maximum generation tokens per answer (Step 8.2 cap).",
    )
    verification_max_tokens: int = Field(
        default=250,
        description="Maximum verification output tokens (Step 8.2 cap).",
    )

    # Context builder limits
    context_max_tokens: int = Field(
        default=3000,
        description="Maximum estimated tokens for evidence context prompt payload.",
    )
    evidence_max_per_prompt: int = Field(
        default=10,
        description="Max number of top evidence items formatted into system context.",
    )

    # System prompt
    system_prompt: str = Field(
        default=(
            "You are a medical assistant. Answer ONLY from the provided evidence. "
            "Cite every claim as [E#]. If evidence is insufficient, say so. "
            "Recognize initial treatment recommendations in clinical guidelines (e.g. 'offer an ACE inhibitor as initial therapy for adults under 55') as first-line treatment recommendations. "
            "Do NOT diagnose or prescribe. End with: This is information, not medical advice — consult your physician."
        ),
        description="Strict medical grounding system prompt.",
    )

    # Stricter system prompt for faithfulness retry
    strict_system_prompt: str = Field(
        default=(
            "Answer ONLY from the evidence below; if a fact is not stated, say it is not provided; "
            "do not use general knowledge. Cite every claim as [E#]. End with: This is information, not medical advice — consult your physician."
        ),
        description="Stricter system prompt used when regenerating for low faithfulness.",
    )

    # Evidence confidence weights
    confidence_weight_fused: float = Field(
        default=0.6,
        description="Weight of mean fused score in evidence confidence.",
    )
    confidence_weight_agreement: float = Field(
        default=0.4,
        description="Weight of distinct category/source agreement in evidence confidence.",
    )

    # ── Evidence Hygiene (Step 8.1) ──────────────────────────────────────────
    evidence_blocklist: List[str] = Field(
        default=["download_log", "download_failed", "download_success", "Metadata/summary"],
        description="Blocklisted document/chunk ID substrings dropped at retrieval time.",
    )

    # ── Verification Agent settings (Step 8.2) ───────────────────────────────
    verification_enabled: bool = Field(
        default=True,
        description="Enable VerificationAgent self-verifying post-processing.",
    )
    query_latency_budget_ms: int = Field(
        default=12000,
        description="Hard latency budget in ms per query.",
    )
    verification_w_evidence: float = Field(
        default=0.4,
        description="Weight of evidence_confidence in final_confidence score.",
    )
    verification_w_faithfulness: float = Field(
        default=0.6,
        description="Weight of faithfulness_score in final_confidence score.",
    )
    verification_threshold_high: float = Field(
        default=0.75,
        description="Threshold for HIGH confidence tier.",
    )
    verification_threshold_medium: float = Field(
        default=0.50,
        description="Threshold for MEDIUM confidence tier.",
    )
    verification_threshold_low: float = Field(
        default=0.50,
        description="Threshold for LOW confidence tier (triggers retry).",
    )
    verification_max_retries: int = Field(
        default=2,
        description="Maximum bounded retries (2 retries = 3 attempts total).",
    )
    early_stop_delta: float = Field(
        default=0.05,
        description="Early stopping confidence change threshold between retries.",
    )
    verification_single_pass_prompt: str = Field(
        default=(
            "You are a medical fact-checker. You will be given an ANSWER and CITED EVIDENCE.\n"
            "Your task:\n"
            "1. Evaluate up to 4 atomic factual claims in the ANSWER against the CITED EVIDENCE.\n"
            "2. For each claim, determine if the CITED EVIDENCE SUPPORTS, CONTRADICTS, or DOES NOT MENTION the claim.\n"
            "   Use 'refusal_valid' ONLY if the claim states evidence is insufficient/missing and the evidence indeed lacks the info.\n"
            "3. Return ONLY a valid JSON array of objects. Do NOT echo claim text or evidence snippets in the output.\n"
            "   Keys for each object MUST be:\n"
            '   - "verdict": "supported" | "contradicted" | "not_mentioned" | "refusal_valid"\n'
            '   - "explanation": ONE-SENTENCE string (<= 15 words)\n\n'
            "CITED EVIDENCE:\n{evidence_text}\n\n"
            "ANSWER:\n{answer_text}"
        ),
        description="Single-pass prompt template combining claim extraction and faithfulness check.",
    )
    # ── Step 9 Router & Agent Settings ───────────────────────────────────────
    router_rule_first_enabled: bool = Field(
        default=True,
        description="Enable fast CPU rule-first routing before LLM fallback.",
    )
    router_llm_fallback_enabled: bool = Field(
        default=True,
        description="Enable LLM classification fallback when rules are inconclusive.",
    )
    router_relational_keywords: List[str] = Field(
        default=[
            "which drugs", "what drugs", "drugs treat", "what tests", "lab test for",
            "interactions", "side effects of", "causes of", "treats", "mapped to",
            "relationship between", "mechanism of action"
        ],
        description="Keywords indicating a graph-first knowledge_graph intent.",
    )
    router_out_of_scope_keywords: List[str] = Field(
        default=[
            "poem", "haiku", "sing", "code", "python", "weather", "recipe",
            "joke", "capital of", "who wrote", "sports", "football"
        ],
        description="Keywords indicating an out_of_scope non-medical query.",
    )
    router_llm_classification_prompt: str = Field(
        default=(
            "Classify the following query into exactly ONE route from: "
            "[medical_query, knowledge_graph, report, out_of_scope]. "
            "Respond ONLY with the single route string.\n\n"
            "QUERY: {query}"
        ),
        description="LLM single-line classification prompt template.",
    )
    uncertainty_disclosure: str = Field(
        default=(
            "⚠️ I found limited or conflicting evidence for this topic. "
            "The information below may be incomplete or uncertain. "
            "Please consult a healthcare professional for definitive guidance.\n\n"
        ),
        description="Prepend header for uncertain answers after retries.",
    )
    contradiction_warning: str = Field(
        default="Note: Some statements could not be fully verified against the retrieved evidence.",
        description="Warning note when contradictions are detected.",
    )

    # ── Step 10 Report & Private Store Settings ──────────────────────────────
    private_store_dir: Path = Field(
        default=PROJECT_ROOT / "private_store",
        description="Root directory for isolated encrypted per-user private stores.",
    )
    ocr_confidence_threshold: float = Field(
        default=0.75,
        description="Confidence threshold below which OCR extracted fields are flagged needs_review.",
    )
    unit_conversion_factors: Dict[str, float] = Field(
        default={
            "creatinine_mg/dl->umol/l": 88.4,
            "creatinine_mg/dl->µmol/l": 88.4,
            "glucose_mg/dl->mmol/l": 0.0555,
            "hemoglobin_g/dl->g/l": 10.0,
            "hemoglobin_g/dl->g/dl": 1.0,
            "potassium_mmol/l->mmol/l": 1.0,
            "potassium_meq/l->mmol/l": 1.0,
            "sodium_mmol/l->mmol/l": 1.0,
            "sodium_meq/l->mmol/l": 1.0,
            "platelet_10^9/l->10^9/l": 1.0,
            "wbc_10^9/l->10^9/l": 1.0,
        },
        description="Explicit conversion factors for unit normalization.",
    )

    # ── Step 11 FastAPI API & Security Settings ──────────────────────────────
    jwt_secret_key: Optional[str] = Field(
        default=None,
        validation_alias="MEDGRAPH_JWT_SECRET",
        description="JWT secret key. If unset, a random per-process key is generated with a loud warning.",
    )

    # ── Multimodal/VLM Settings ──────────────────────────────────────────────
    vlm_model_path: Optional[str] = Field(
        default=None,
        validation_alias="MEDGRAPH_VLM_MODEL_PATH",
        description="Path to Vision-Language Model (GGUF or HuggingFace). If unset, VLM analysis is disabled.",
    )
    vlm_model_type: str = Field(
        default="llava-med",
        description="VLM model type: 'llava-med', 'med-flamingo', 'gpt4v', 'custom'.",
    )
    vlm_max_tokens: int = Field(
        default=1024,
        description="Maximum tokens for VLM generation.",
    )
    vlm_temperature: float = Field(
        default=0.1,
        description="Temperature for VLM generation (low for medical accuracy).",
    )
    vlm_device: str = Field(
        default="cuda",
        description="Device for VLM inference: 'cuda' or 'cpu'.",
    )
    enable_dicom_support: bool = Field(
        default=True,
        description="Enable DICOM medical image format support.",
    )
    enable_ocr_fallback: bool = Field(
        default=True,
        description="Enable OCR fallback for text extraction from images.",
    )
    ocr_engine: str = Field(
        default="easyocr",
        description="OCR engine: 'easyocr' or 'pytesseract'.",
    )

    jwt_algorithm: str = Field(
        default="HS256",
        description="JWT signature algorithm.",
    )
    jwt_expire_minutes: int = Field(
        default=60,
        description="JWT access token expiration time in minutes.",
    )
    max_upload_mb: int = Field(
        default=20,
        description="Maximum allowed multipart upload size in megabytes.",
    )
    demo_users: Dict[str, str] = Field(
        default={
            # sha256 hash of 'password123'
            "demo_user": "ef92b778bafe771e89245b89ecbc08a44a4e166c06659911881f383d4473e94f",
            "admin": "ef92b778bafe771e89245b89ecbc08a44a4e166c06659911881f383d4473e94f",
        },
        description="Demo username -> sha256(password) lookup table.",
    )

    def get_effective_jwt_secret(self) -> str:
        """Return MEDGRAPH_JWT_SECRET or generate a loud-warning per-process random key."""
        if self.jwt_secret_key:
            return self.jwt_secret_key
        if not hasattr(self, "_generated_random_jwt_secret"):
            import secrets
            logger.warning(
                "⚠️ [SECURITY WARNING] MEDGRAPH_JWT_SECRET environment variable is UNSET! "
                "Generating a random per-process secret key. JWT tokens will NOT survive server restarts!"
            )
            object.__setattr__(self, "_generated_random_jwt_secret", secrets.token_hex(32))
        return getattr(self, "_generated_random_jwt_secret")

    # ── Logging ──────────────────────────────────────────────────────────────
    log_level: str = Field(
        default="INFO",
        description="Python logging level for the backend.",
    )

    @field_validator("embed_device")
    @classmethod
    def _enforce_cpu(cls, v: str) -> str:
        """GPU must remain reserved for the future LLM (Step 7+)."""
        if v.lower().startswith("cuda"):
            raise ValueError(
                "embed_device must be 'cpu'. GPU is reserved for the LLM. "
                "Set MEDGRAPH_EMBED_DEVICE=cpu or omit the variable."
            )
        return v.lower()


# ---------------------------------------------------------------------------
# Module-level singleton — import this everywhere
# ---------------------------------------------------------------------------
settings = Settings()

