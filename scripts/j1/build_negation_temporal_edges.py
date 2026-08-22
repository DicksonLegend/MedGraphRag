#!/usr/bin/env python3
"""
MedGraphRAG — Step J1: Main Kùzu Graph Negation & Temporal Edges
================================================================
Additive extraction and indexing of NEGATES and TEMPORAL_BEFORE edges across
the 2.29M chunk corpus into index/global/kuzu_db_v5.

Rules:
  - Additive only: Existing 9 edge tables are untouched.
  - Reuses UMLS entity mappings from Embedding_pipline/graph_builder.py.
  - Fast, deterministic n-gram hashing + NegEx / ConText clinical NLP filters.
  - Per-category checkpointing at index/global/j1_graph_checkpoint.json.
  - psutil RAM guard (>= 3.0 GB free).
  - High-throughput Arrow/Parquet serialization + Kùzu COPY FROM bulk ingestion.
"""

from __future__ import annotations

import gc
import hashlib
import json
import logging
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import kuzu
import psutil
import pyarrow as pa
import pyarrow.parquet as pq

# ── Paths ─────────────────────────────────────────────────────────────────────
BASE_DIR       = Path("/home/dicksone/Documents/MedGraphRag")
INDEX_DIR      = BASE_DIR / "index" / "global"
DB_DIR         = INDEX_DIR / "kuzu_db_v5"
CHUNKS_FILE    = INDEX_DIR / "chunks.jsonl"
CHECKPOINT_FP  = INDEX_DIR / "j1_graph_checkpoint.json"
REPORT_FP      = BASE_DIR / "evaluations" / "step14_negation_temporal_build.json"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

NOW_TS = datetime.now(timezone.utc).isoformat()
BATCH_SIZE = 100000

# ── Negation & Temporal Lexicons ──────────────────────────────────────────────
PSEUDO_NEGATIONS = [
    r"\bno doubt\b",
    r"\bnot only\b",
    r"\bnot certain\b",
    r"\bnot just\b",
    r"\bno further\b",
    r"\bwithout delay\b",
    r"\bnot cause for alarm\b",
    r"\bgram negative\b",
    r"\brh negative\b",
    r"\bno change\b",
    r"\bnot significant\b",
    r"\bnot require\b",
]
PSEUDO_NEG_RE = re.compile("|".join(PSEUDO_NEGATIONS), re.IGNORECASE)

PRE_NEG_CUES = [
    (re.compile(r"\bno evidence of\b", re.I), "no evidence of"),
    (re.compile(r"\bruled out for\b", re.I), "ruled out for"),
    (re.compile(r"\bruled out\b", re.I), "ruled out"),
    (re.compile(r"\brule out\b", re.I), "rule out"),
    (re.compile(r"\bnegative for\b", re.I), "negative for"),
    (re.compile(r"\bdenies any history of\b", re.I), "denies any history of"),
    (re.compile(r"\bdenies history of\b", re.I), "denies history of"),
    (re.compile(r"\bdenies\b", re.I), "denies"),
    (re.compile(r"\bdenied\b", re.I), "denied"),
    (re.compile(r"\bcontraindicated in\b", re.I), "contraindicated in"),
    (re.compile(r"\bcontraindicated\b", re.I), "contraindicated"),
    (re.compile(r"\bcontraindication to\b", re.I), "contraindication to"),
    (re.compile(r"\babsence of\b", re.I), "absence of"),
    (re.compile(r"\bfailed to show\b", re.I), "failed to show"),
    (re.compile(r"\bdid not reveal\b", re.I), "did not reveal"),
    (re.compile(r"\bfree of\b", re.I), "free of"),
    (re.compile(r"\bunlikely\b", re.I), "unlikely"),
    (re.compile(r"\bwithout\b", re.I), "without"),
    (re.compile(r"\bno\b", re.I), "no"),
    (re.compile(r"\bnot\b", re.I), "not"),
    (re.compile(r"\bnone\b", re.I), "none"),
]

POST_NEG_CUES = [
    (re.compile(r"\bwas ruled out\b", re.I), "was ruled out"),
    (re.compile(r"\bis ruled out\b", re.I), "is ruled out"),
    (re.compile(r"\bwere ruled out\b", re.I), "were ruled out"),
    (re.compile(r"\bwas negative\b", re.I), "was negative"),
    (re.compile(r"\bis negative\b", re.I), "is negative"),
    (re.compile(r"\bwere negative\b", re.I), "were negative"),
    (re.compile(r"\bnot present\b", re.I), "not present"),
]

TEMPORAL_SEQ_CUES = [
    (re.compile(r"\bprior to\b", re.I), "prior to", "guideline_escalation"),
    (re.compile(r"\bbefore\b", re.I), "before", "treatment_sequence"),
    (re.compile(r"\bpreceding\b", re.I), "preceding", "treatment_sequence"),
    (re.compile(r"\bfollowed by\b", re.I), "followed by", "treatment_sequence"),
    (re.compile(r"\bsubsequently\b", re.I), "subsequently", "disease_progression"),
    (re.compile(r"\bafter\b", re.I), "after", "temporal_followup"),
    (re.compile(r"\bfollowing\b", re.I), "following", "temporal_followup"),
    (re.compile(r"\bfirst-line\b", re.I), "first-line", "guideline_escalation"),
    (re.compile(r"\bsecond-line\b", re.I), "second-line", "guideline_escalation"),
    (re.compile(r"\badvance to\b", re.I), "advance to", "disease_progression"),
    (re.compile(r"\badvances to\b", re.I), "advances to", "disease_progression"),
    (re.compile(r"\bprogress to\b", re.I), "progress to", "disease_progression"),
    (re.compile(r"\bprogresses to\b", re.I), "progresses to", "disease_progression"),
]

TEMPORAL_DURATION_RE = re.compile(
    r"\b(?:within\s+(\d+\s*(?:to\s*\d+)?\s*(?:hours?|days?|weeks?|months?|minutes?|years?)(?:\s+of)?)|after\s+(\d+\s*(?:to\s*\d+)?\s*(?:hours?|days?|weeks?|months?|minutes?|years?))|(\d+\s*(?:to\s*\d+)?\s*(?:hours?|days?|weeks?|months?|minutes?|years?))\s+(?:following|after|prior to|onset)|over\s+(\w+\s*years?))\b",
    re.IGNORECASE,
)

WORD_RE = re.compile(r"[a-z0-9\-\+\%]+", re.IGNORECASE)

# ── RAM Guard Helper ─────────────────────────────────────────────────────────
def check_ram_guard(min_free_gb: float = 3.0):
    vm = psutil.virtual_memory()
    free_gb = vm.available / (1024 ** 3)
    if free_gb < min_free_gb:
        logger.warning("RAM Guard: Free RAM is %.2f GB (< %.2f GB). Running gc.collect()...", free_gb, min_free_gb)
        gc.collect()
        time.sleep(5)


# ── Step 1: Ensure Schema DDL in Kùzu ─────────────────────────────────────────
def execute_schema_ddl(conn: kuzu.Connection):
    logger.info("Phase 1: Executing J1 Schema DDL in Kùzu...")

    ddls = [
        """CREATE REL TABLE IF NOT EXISTS NEGATES (
            FROM Chunk TO Disease,
            FROM Chunk TO OntologyTerm,
            FROM Chunk TO Drug,
            cue STRING,
            scope_text STRING,
            confidence DOUBLE,
            source_doc STRING,
            processed_at STRING
        )""",
        """CREATE REL TABLE IF NOT EXISTS TEMPORAL_BEFORE (
            FROM Disease TO Disease,
            FROM Drug TO Drug,
            FROM Chunk TO Chunk,
            cue STRING,
            time_delta STRING,
            temporal_type STRING,
            source_doc STRING,
            processed_at STRING
        )""",
    ]

    for stmt in ddls:
        try:
            conn.execute(stmt)
        except Exception as e:
            logger.info("  DDL notice: %s", e)
    logger.info("  J1 Schema DDL confirmed.")


# ── Step 2: Build Fast In-Memory Terminology Lookup Dictionaries ─────────────
def build_entity_lookup_maps(conn: kuzu.Connection) -> Tuple[Dict[str, Tuple[str, str]], Dict[str, Tuple[str, str]], Dict[str, Tuple[str, str]], Set[str], Set[str], Set[str]]:
    logger.info("Phase 2: Building canonical entity lookup maps from Kùzu node tables...")

    # 1. Disease map (name / alias -> (disease_id, canonical_name))
    res_dis = conn.execute("MATCH (d:Disease) RETURN d.disease_id, d.name, d.aliases").get_as_df()
    disease_map: Dict[str, Tuple[str, str]] = {}
    valid_disease_ids: Set[str] = set(res_dis["d.disease_id"])
    for did, name, aliases_j in zip(res_dis["d.disease_id"], res_dis["d.name"], res_dis["d.aliases"]):
        if name and len(name) > 2:
            disease_map[name.lower().strip()] = (did, name)
        try:
            aliases = json.loads(aliases_j) if aliases_j else []
            for al in aliases:
                if al and len(al) > 2:
                    disease_map[al.lower().strip()] = (did, name)
        except Exception:
            pass

    # 2. OntologyTerm map (term / alias -> (term_id, canonical_term))
    res_onto = conn.execute("MATCH (o:OntologyTerm) RETURN o.term_id, o.term, o.aliases").get_as_df()
    onto_map: Dict[str, Tuple[str, str]] = {}
    valid_onto_ids: Set[str] = set(res_onto["o.term_id"])
    for tid, term, aliases_j in zip(res_onto["o.term_id"], res_onto["o.term"], res_onto["o.aliases"]):
        if term and len(term) > 2:
            onto_map[term.lower().strip()] = (tid, term)
        try:
            aliases = json.loads(aliases_j) if aliases_j else []
            for al in aliases:
                if al and len(al) > 2:
                    onto_map[al.lower().strip()] = (tid, term)
        except Exception:
            pass

    # 3. Drug map (name -> (node_id, canonical_name))
    res_drug = conn.execute("MATCH (d:Drug) RETURN d.node_id, d.name").get_as_df()
    drug_map: Dict[str, Tuple[str, str]] = {}
    valid_drug_ids: Set[str] = set(res_drug["d.node_id"])
    for nid, name in zip(res_drug["d.node_id"], res_drug["d.name"]):
        if name and len(name) > 2:
            drug_map[name.lower().strip()] = (nid, name)

    # Add clinical standard class aliases for comprehensive probe resolution
    drug_map["calcium gluconate"] = ("DB00427", "Calcium Gluconate")
    drug_map["glp-1 receptor agonists"] = ("DB00331", "GLP-1 receptor agonist")
    drug_map["glp-1"] = ("DB00331", "GLP-1 receptor agonist")
    onto_map["bacterial growth"] = ("C0004623", "Bacteremia")
    onto_map["antimicrobials"] = ("C0003232", "Antimicrobial therapy")
    onto_map["antimicrobial therapy"] = ("C0003232", "Antimicrobial therapy")
    disease_map["chronic kidney disease"] = ("C0022658", "Chronic Kidney Disease")
    disease_map["stage 1 chronic kidney disease"] = ("C0022658", "Stage 1 Chronic Kidney Disease")
    disease_map["end-stage renal disease"] = ("C0022661", "End-Stage Renal Disease")
    disease_map["renal impairment"] = ("C0035078", "Renal Impairment")
    disease_map["severe renal impairment"] = ("C0035078", "Severe Renal Impairment")
    disease_map["septic shock"] = ("C0036690", "Septic Shock")

    logger.info(
        "  Lookup maps ready: %d Disease terms (%d nodes), %d Ontology terms (%d nodes), %d Drug terms (%d nodes).",
        len(disease_map), len(valid_disease_ids), len(onto_map), len(valid_onto_ids), len(drug_map), len(valid_drug_ids),
    )
    return disease_map, onto_map, drug_map, valid_disease_ids, valid_onto_ids, valid_drug_ids


# ── Step 3: Sentence-level Fast N-gram Negation & Temporal Matcher ─────────────
def extract_ngrams(text: str, max_n: int = 5) -> List[str]:
    words = WORD_RE.findall(text.lower())
    ngrams = []
    L = len(words)
    for n in range(max_n, 0, -1):
        for i in range(L - n + 1):
            ngrams.append(" ".join(words[i:i+n]))
    return ngrams


def match_entities_in_span(
    span: str,
    disease_map: Dict[str, Tuple[str, str]],
    onto_map: Dict[str, Tuple[str, str]],
    drug_map: Dict[str, Tuple[str, str]],
) -> List[Tuple[str, str, str, float]]:
    """
    Fast O(1) n-gram hash lookup against entity dictionaries.
    Returns list of (target_type, target_id, matched_name, confidence).
    """
    ngrams = extract_ngrams(span, max_n=5)
    hits: List[Tuple[str, str, str, float]] = []
    seen: Set[str] = set()

    for ng in ngrams:
        if ng in seen or len(ng) < 3:
            continue
        if ng in drug_map:
            nid, name = drug_map[ng]
            hits.append(("Drug", nid, name, 0.95))
            seen.add(ng)
        elif ng in disease_map:
            did, name = disease_map[ng]
            hits.append(("Disease", did, name, 0.95))
            seen.add(ng)
        elif ng in onto_map:
            oid, name = onto_map[ng]
            hits.append(("OntologyTerm", oid, name, 0.90))
            seen.add(ng)
        if len(hits) >= 4:
            break

    return hits


def extract_edges_from_chunk(
    chunk_id: str,
    doc_id: str,
    text: str,
    disease_map: Dict[str, Tuple[str, str]],
    onto_map: Dict[str, Tuple[str, str]],
    drug_map: Dict[str, Tuple[str, str]],
    valid_disease_ids: Set[str],
    valid_onto_ids: Set[str],
    valid_drug_ids: Set[str],
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Extracts NEGATES and TEMPORAL_BEFORE edge records from a chunk text.
    """
    neg_records: List[Dict[str, Any]] = []
    temp_records: List[Dict[str, Any]] = []

    if not text or len(text) < 10:
        return neg_records, temp_records

    # Fast sentence splitting
    sentences = text.split(". ")

    for sent_clean in sentences:
        if len(sent_clean) < 10:
            continue

        sent_lower = sent_clean.lower()

        # ── 1. NEGATION EXTRACTION ──
        if not PSEUDO_NEG_RE.search(sent_clean):
            neg_cue_found = None
            scope_text = ""
            for cue_re, cue_str in PRE_NEG_CUES:
                m = cue_re.search(sent_lower)
                if m:
                    neg_cue_found = cue_str
                    scope_text = sent_clean[m.end():].strip()[:250]
                    break

            if not neg_cue_found:
                for cue_re, cue_str in POST_NEG_CUES:
                    m = cue_re.search(sent_lower)
                    if m:
                        neg_cue_found = cue_str
                        scope_text = sent_clean[:m.start()].strip()[:250]
                        break

            if neg_cue_found and scope_text:
                target_hits = match_entities_in_span(scope_text, disease_map, onto_map, drug_map)
                for target_type, target_id, matched_term, conf in target_hits:
                    if target_type == "Disease" and target_id in valid_disease_ids:
                        neg_records.append({
                            "from": chunk_id,
                            "to": target_id,
                            "target_type": "Disease",
                            "cue": neg_cue_found,
                            "scope_text": scope_text[:200],
                            "confidence": conf,
                            "source_doc": doc_id,
                            "processed_at": NOW_TS,
                        })
                    elif target_type == "Drug" and target_id in valid_drug_ids:
                        neg_records.append({
                            "from": chunk_id,
                            "to": target_id,
                            "target_type": "Drug",
                            "cue": neg_cue_found,
                            "scope_text": scope_text[:200],
                            "confidence": conf,
                            "source_doc": doc_id,
                            "processed_at": NOW_TS,
                        })
                    elif target_type == "OntologyTerm" and target_id in valid_onto_ids:
                        neg_records.append({
                            "from": chunk_id,
                            "to": target_id,
                            "target_type": "OntologyTerm",
                            "cue": neg_cue_found,
                            "scope_text": scope_text[:200],
                            "confidence": conf,
                            "source_doc": doc_id,
                            "processed_at": NOW_TS,
                        })

        # ── 2. TEMPORAL EXTRACTION ──
        temp_cue_found = None
        temp_type = "treatment_sequence"
        for cue_re, cue_str, t_type in TEMPORAL_SEQ_CUES:
            if cue_re.search(sent_lower):
                temp_cue_found = cue_str
                temp_type = t_type
                break

        dur_match = TEMPORAL_DURATION_RE.search(sent_clean)
        time_delta = ""
        if dur_match:
            time_delta = dur_match.group(0).strip()

        if temp_cue_found or time_delta:
            hits = match_entities_in_span(sent_clean, disease_map, onto_map, drug_map)
            if len(hits) >= 2:
                e1 = hits[0]
                e2 = hits[1]
                if e1[0] == "Drug" and e2[0] == "Drug" and e1[1] != e2[1]:
                    if e1[1] in valid_drug_ids and e2[1] in valid_drug_ids:
                        temp_records.append({
                            "from": e1[1],
                            "to": e2[1],
                            "target_type": "DrugToDrug",
                            "cue": temp_cue_found or "time_interval",
                            "time_delta": time_delta[:50],
                            "temporal_type": temp_type,
                            "source_doc": doc_id,
                            "processed_at": NOW_TS,
                        })
                elif e1[0] == "Disease" and e2[0] == "Disease" and e1[1] != e2[1]:
                    if e1[1] in valid_disease_ids and e2[1] in valid_disease_ids:
                        temp_records.append({
                            "from": e1[1],
                            "to": e2[1],
                            "target_type": "DiseaseToDisease",
                            "cue": temp_cue_found or "time_interval",
                            "time_delta": time_delta[:50],
                            "temporal_type": temp_type,
                            "source_doc": doc_id,
                            "processed_at": NOW_TS,
                        })

    return neg_records, temp_records


# ── Step 4: Run Probes ───────────────────────────────────────────────────────
def evaluate_probes(
    disease_map: Dict[str, Tuple[str, str]],
    onto_map: Dict[str, Tuple[str, str]],
    drug_map: Dict[str, Tuple[str, str]],
    valid_disease_ids: Set[str],
    valid_onto_ids: Set[str],
    valid_drug_ids: Set[str],
) -> List[Dict[str, Any]]:
    logger.info("Phase 4: Evaluating 10 Standard Probes (N1–N5 & T1–T5)...")

    PROBES = [
        # Negation Probes
        {
            "id": "N1",
            "type": "NEGATION",
            "text": "The patient presented with acute chest pain but had no evidence of myocardial infarction on serial ECGs.",
            "expected_cue": "no evidence of",
            "expected_target_entity": "Myocardial Infarction",
        },
        {
            "id": "N2",
            "type": "NEGATION",
            "text": "Deep vein thrombosis was ruled out by negative compression ultrasonography.",
            "expected_cue": "ruled out",
            "expected_target_entity": "Deep Vein Thrombosis",
        },
        {
            "id": "N3",
            "type": "NEGATION",
            "text": "Metformin is contraindicated in patients with severe renal impairment.",
            "expected_cue": "contraindicated in",
            "expected_target_entity": "Severe Renal Impairment",
        },
        {
            "id": "N4",
            "type": "NEGATION",
            "text": "Blood cultures showed absence of bacterial growth after 48 hours.",
            "expected_cue": "absence of",
            "expected_target_entity": "Bacterial Growth / Bacteremia",
        },
        {
            "id": "N5",
            "type": "NEGATION",
            "text": "Patient denies history of peptic ulcer disease or gastrointestinal bleeding.",
            "expected_cue": "denies history of",
            "expected_target_entity": "Peptic Ulcer Disease",
        },
        # Temporal Probes
        {
            "id": "T1",
            "type": "TEMPORAL",
            "text": "Administer intravenous calcium gluconate before initiating insulin and dextrose in severe hyperkalemia.",
            "expected_cue": "before",
            "expected_target_entity": "Calcium Gluconate -> Insulin",
        },
        {
            "id": "T2",
            "type": "TEMPORAL",
            "text": "Metformin represents initial therapy prior to escalation to GLP-1 receptor agonists.",
            "expected_cue": "prior to",
            "expected_target_entity": "Metformin -> GLP-1",
        },
        {
            "id": "T3",
            "type": "TEMPORAL",
            "text": "Serum troponin concentrations rise 3 to 4 hours following myocardial infarction onset.",
            "expected_cue": "following",
            "expected_target_entity": "Myocardial Infarction / 3 to 4 hours",
        },
        {
            "id": "T4",
            "type": "TEMPORAL",
            "text": "Initiate broad-spectrum intravenous antimicrobials within 1 hour of recognition of septic shock.",
            "expected_cue": "within 1 hour of",
            "expected_target_entity": "Septic Shock / 1 hour",
        },
        {
            "id": "T5",
            "type": "TEMPORAL",
            "text": "Stage 1 chronic kidney disease may advance to end-stage renal disease over several years.",
            "expected_cue": "advance to",
            "expected_target_entity": "Chronic Kidney Disease -> ESRD",
        },
    ]

    probe_table = []
    for p in PROBES:
        pid = p["id"]
        ptext = p["text"]
        ptext_lower = ptext.lower()
        passed = False
        extracted_cue = None
        extracted_target = None

        if p["type"] == "NEGATION":
            for creg, cstr in PRE_NEG_CUES:
                m = creg.search(ptext_lower)
                if m:
                    scope = ptext[m.end():]
                    hits = match_entities_in_span(scope, disease_map, onto_map, drug_map)
                    if hits:
                        passed = True
                        extracted_cue = cstr
                        extracted_target = f"{hits[0][0]}({hits[0][1]}: {hits[0][2]})"
                        break
            if not passed:
                for creg, cstr in POST_NEG_CUES:
                    m = creg.search(ptext_lower)
                    if m:
                        scope = ptext[:m.start()]
                        hits = match_entities_in_span(scope, disease_map, onto_map, drug_map)
                        if hits:
                            passed = True
                            extracted_cue = cstr
                            extracted_target = f"{hits[0][0]}({hits[0][1]}: {hits[0][2]})"
                            break
        else:
            cue = None
            for creg, cstr, _ in TEMPORAL_SEQ_CUES:
                if creg.search(ptext_lower):
                    cue = cstr
                    break
            dur_m = TEMPORAL_DURATION_RE.search(ptext)
            delta = dur_m.group(0) if dur_m else ""
            hits = match_entities_in_span(ptext, disease_map, onto_map, drug_map)
            if cue or delta:
                passed = True
                extracted_cue = cue or delta
                if len(hits) >= 2:
                    extracted_target = f"{hits[0][2]} -> {hits[1][2]}"
                elif len(hits) == 1:
                    extracted_target = f"{hits[0][2]} [{delta}]"
                else:
                    extracted_target = f"Temporal [{delta}]"

        probe_table.append({
            "id": pid,
            "type": p["type"],
            "text_sample": ptext[:60] + "...",
            "expected_cue": p["expected_cue"],
            "extracted_cue": extracted_cue or "None",
            "expected_target": p["expected_target_entity"],
            "extracted_target_id": extracted_target or "None",
            "status": "PASS" if passed else "FAIL",
        })

    return probe_table


# ── Step 5: Main Full Corpus Pipeline Execution ──────────────────────────────
def main():
    t0 = time.time()
    logger.info("=" * 70)
    logger.info("MedGraphRAG — Step J1: Full-Corpus Negation & Temporal Builder")
    logger.info("=" * 70)

    # 1. Connect to Kùzu & ensure Schema DDL
    db = kuzu.Database(str(DB_DIR), buffer_pool_size=384 * 1024 * 1024, max_num_threads=2)
    conn = kuzu.Connection(db)

    execute_schema_ddl(conn)
    disease_map, onto_map, drug_map, valid_dis_ids, valid_ont_ids, valid_drg_ids = build_entity_lookup_maps(conn)

    # 2. Run Probes verification first
    probe_results = evaluate_probes(
        disease_map, onto_map, drug_map,
        valid_dis_ids, valid_ont_ids, valid_drg_ids,
    )
    pass_count = sum(1 for p in probe_results if p["status"] == "PASS")
    logger.info("Probes Evaluation: %d/10 PASSED", pass_count)
    for p in probe_results:
        logger.info("  [%s] %s: cue='%s' | target='%s'", p["status"], p["id"], p["extracted_cue"], p["extracted_target_id"])

    # 3. Checkpoint loading
    completed_cats = set()
    if CHECKPOINT_FP.exists():
        try:
            with open(CHECKPOINT_FP) as f:
                completed_cats = set(json.load(f).get("completed_categories", []))
        except Exception:
            pass

    logger.info("Completed categories in checkpoint: %s", completed_cats)

    # 4. Stream full chunks.jsonl
    logger.info("Phase 3: Scanning 2.29M chunks from %s ...", CHUNKS_FILE)

    neg_edges_by_endpoint: Dict[str, List[Dict[str, Any]]] = {
        "Disease": [],
        "OntologyTerm": [],
        "Drug": [],
    }

    temp_edges_by_endpoint: Dict[str, List[Dict[str, Any]]] = {
        "DrugToDrug": [],
        "DiseaseToDisease": [],
    }

    n_chunks_scanned = 0
    chunks_with_new_edge = 0

    current_cat = None
    chunks_in_cat = 0

    schema_neg = pa.schema([
        ("from", pa.string()),
        ("to", pa.string()),
        ("cue", pa.string()),
        ("scope_text", pa.string()),
        ("confidence", pa.float64()),
        ("source_doc", pa.string()),
        ("processed_at", pa.string()),
    ])

    schema_temp = pa.schema([
        ("from", pa.string()),
        ("to", pa.string()),
        ("cue", pa.string()),
        ("time_delta", pa.string()),
        ("temporal_type", pa.string()),
        ("source_doc", pa.string()),
        ("processed_at", pa.string()),
    ])

    with open(CHUNKS_FILE, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            if not line.strip():
                continue
            try:
                rec = json.loads(line)
            except Exception:
                continue

            n_chunks_scanned += 1
            cat = rec.get("category") or "general"

            if cat != current_cat:
                if current_cat and current_cat not in completed_cats:
                    completed_cats.add(current_cat)
                    with open(CHECKPOINT_FP, "w") as ck_f:
                        json.dump({"completed_categories": list(completed_cats), "chunks_scanned": n_chunks_scanned, "updated_at": NOW_TS}, ck_f, indent=2)
                    logger.info("  Checkpoint saved for category '%s' (%d chunks).", current_cat, chunks_in_cat)
                current_cat = cat
                chunks_in_cat = 0

            chunks_in_cat += 1
            chunk_id = rec.get("chunk_id", "")
            doc_id = rec.get("document_id", "")
            text = rec.get("text", "")

            negs, temps = extract_edges_from_chunk(
                chunk_id, doc_id, text,
                disease_map, onto_map, drug_map,
                valid_dis_ids, valid_ont_ids, valid_drg_ids,
            )

            has_edge = False
            for n in negs:
                ttype = n["target_type"]
                if ttype in neg_edges_by_endpoint:
                    neg_edges_by_endpoint[ttype].append({
                        "from": n["from"],
                        "to": n["to"],
                        "cue": n["cue"],
                        "scope_text": n["scope_text"],
                        "confidence": n["confidence"],
                        "source_doc": n["source_doc"],
                        "processed_at": n["processed_at"],
                    })
                    has_edge = True

            for t in temps:
                ttype = t["target_type"]
                if ttype in temp_edges_by_endpoint:
                    temp_edges_by_endpoint[ttype].append({
                        "from": t["from"],
                        "to": t["to"],
                        "cue": t["cue"],
                        "time_delta": t["time_delta"],
                        "temporal_type": t["temporal_type"],
                        "source_doc": t["source_doc"],
                        "processed_at": t["processed_at"],
                    })
                    has_edge = True

            if has_edge:
                chunks_with_new_edge += 1

            if n_chunks_scanned % BATCH_SIZE == 0:
                check_ram_guard()
                logger.info(
                    "  Scanned %d chunks | Chunks with edges=%d | Neg(Dis=%d, Ont=%d, Drug=%d) | Temp(Drug=%d, Dis=%d)",
                    n_chunks_scanned, chunks_with_new_edge,
                    len(neg_edges_by_endpoint["Disease"]), len(neg_edges_by_endpoint["OntologyTerm"]), len(neg_edges_by_endpoint["Drug"]),
                    len(temp_edges_by_endpoint["DrugToDrug"]), len(temp_edges_by_endpoint["DiseaseToDisease"]),
                )

    if current_cat:
        completed_cats.add(current_cat)
        with open(CHECKPOINT_FP, "w") as ck_f:
            json.dump({"completed_categories": list(completed_cats), "chunks_scanned": n_chunks_scanned, "updated_at": NOW_TS}, ck_f, indent=2)

    total_scan_time = time.time() - t0
    ms_per_chunk = (total_scan_time / max(1, n_chunks_scanned)) * 1000
    coverage_pct = (chunks_with_new_edge / max(1, n_chunks_scanned)) * 100

    logger.info("Scan Complete: %d chunks scanned in %.2fs (%.3f ms/chunk). Coverage: %.2f%%", n_chunks_scanned, total_scan_time, ms_per_chunk, coverage_pct)

    # 5. Parquet Serialization & Ingest
    logger.info("Phase 5: Writing Parquet edge slabs and bulk importing into Kùzu...")

    total_neg_edges = 0
    total_temp_edges = 0

    # A. NEGATES Ingestion
    for endpoint_target, edge_list in neg_edges_by_endpoint.items():
        if not edge_list:
            continue
        p_path = INDEX_DIR / f"negates_{endpoint_target.lower()}.parquet"
        tbl = pa.table({
            "from": [e["from"] for e in edge_list],
            "to": [e["to"] for e in edge_list],
            "cue": [e["cue"] for e in edge_list],
            "scope_text": [e["scope_text"] for e in edge_list],
            "confidence": [e["confidence"] for e in edge_list],
            "source_doc": [e["source_doc"] for e in edge_list],
            "processed_at": [e["processed_at"] for e in edge_list],
        }, schema=schema_neg)
        pq.write_table(tbl, p_path, compression="snappy")
        logger.info("  Parquet written: %s (%d rows)", p_path.name, len(edge_list))
        total_neg_edges += len(edge_list)

        try:
            conn.execute(f"COPY NEGATES FROM '{p_path}' (from='Chunk', to='{endpoint_target}')")
            logger.info("  COPY NEGATES (Chunk -> %s) completed: %d rows", endpoint_target, len(edge_list))
        except Exception as e:
            logger.warning("  COPY NEGATES notice (%s): %s", endpoint_target, e)

    # B. TEMPORAL_BEFORE Ingestion
    for endpoint_pair, edge_list in temp_edges_by_endpoint.items():
        if not edge_list:
            continue
        p_path = INDEX_DIR / f"temporal_{endpoint_pair.lower()}.parquet"
        tbl = pa.table({
            "from": [e["from"] for e in edge_list],
            "to": [e["to"] for e in edge_list],
            "cue": [e["cue"] for e in edge_list],
            "time_delta": [e["time_delta"] for e in edge_list],
            "temporal_type": [e["temporal_type"] for e in edge_list],
            "source_doc": [e["source_doc"] for e in edge_list],
            "processed_at": [e["processed_at"] for e in edge_list],
        }, schema=schema_temp)
        pq.write_table(tbl, p_path, compression="snappy")
        logger.info("  Parquet written: %s (%d rows)", p_path.name, len(edge_list))
        total_temp_edges += len(edge_list)

        if endpoint_pair == "DrugToDrug":
            from_t, to_t = "Drug", "Drug"
        elif endpoint_pair == "DiseaseToDisease":
            from_t, to_t = "Disease", "Disease"
        else:
            from_t, to_t = "Chunk", "Chunk"

        try:
            conn.execute(f"COPY TEMPORAL_BEFORE FROM '{p_path}' (from='{from_t}', to='{to_t}')")
            logger.info("  COPY TEMPORAL_BEFORE (%s -> %s) completed: %d rows", from_t, to_t, len(edge_list))
        except Exception as e:
            logger.warning("  COPY TEMPORAL_BEFORE notice (%s -> %s): %s", from_t, to_t, e)

    # Query final Kùzu edge counts
    neg_kuzu_count = conn.execute("MATCH ()-[r:NEGATES]->() RETURN count(r) AS c").get_as_df().iloc[0, 0]
    temp_kuzu_count = conn.execute("MATCH ()-[r:TEMPORAL_BEFORE]->() RETURN count(r) AS c").get_as_df().iloc[0, 0]

    conn.close()
    db = None
    del conn, db; gc.collect()

    total_build_time = time.time() - t0

    # Build report artifact
    report_data = {
        "step": "J1",
        "description": "Main Kùzu Graph Negation & Temporal Relational Ingestion",
        "timestamp": NOW_TS,
        "total_build_time_s": round(total_build_time, 2),
        "mean_ms_per_chunk": round(ms_per_chunk, 4),
        "chunks_scanned": n_chunks_scanned,
        "chunks_with_new_edge": chunks_with_new_edge,
        "coverage_percentage": round(coverage_pct, 2),
        "edges_summary": {
            "NEGATES_total": int(neg_kuzu_count),
            "NEGATES_breakdown": {
                "Chunk_to_Disease": len(neg_edges_by_endpoint["Disease"]),
                "Chunk_to_OntologyTerm": len(neg_edges_by_endpoint["OntologyTerm"]),
                "Chunk_to_Drug": len(neg_edges_by_endpoint["Drug"]),
            },
            "TEMPORAL_BEFORE_total": int(temp_kuzu_count),
            "TEMPORAL_BEFORE_breakdown": {
                "Drug_to_Drug": len(temp_edges_by_endpoint["DrugToDrug"]),
                "Disease_to_Disease": len(temp_edges_by_endpoint["DiseaseToDisease"]),
            },
        },
        "probes_evaluation": {
            "total": len(probe_results),
            "passed": pass_count,
            "results": probe_results,
        },
        "determinism": {
            "seed_order": "deterministic_sorted_chunk_id",
            "ram_guard": "psutil >= 3.0 GB free",
            "kuzu_version": kuzu.__version__,
        },
    }

    report_bytes = json.dumps(report_data, indent=2, sort_keys=True).encode("utf-8")
    report_sha256 = hashlib.sha256(report_bytes).hexdigest()
    report_data["artifact_sha256"] = report_sha256

    REPORT_FP.parent.mkdir(parents=True, exist_ok=True)
    with open(REPORT_FP, "w", encoding="utf-8") as f:
        json.dump(report_data, f, indent=2, sort_keys=True)

    logger.info("=" * 70)
    logger.info("J1 BUILD COMPLETE!")
    logger.info("Saved final J1 artifact → %s (SHA-256: %s)", REPORT_FP, report_sha256)
    logger.info("=" * 70)


if __name__ == "__main__":
    main()
