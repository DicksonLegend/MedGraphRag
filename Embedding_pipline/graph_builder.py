"""
MedGraphRAG — Step 5: Kùzu Graph Builder (v2 — correct Kùzu 0.11.3 API)
=========================================================================
- Parameters: dict-style  conn.execute(query, {'key': val})
- Transactions: BEGIN TRANSACTION / COMMIT
- MERGE supported in 0.11.3
- COPY FROM parquet for 2.29M Chunk nodes
- MRDEF definitions on OntologyTerm + Disease (disease-filtered, 92 MB)
- Upsert via MERGE — one node per CUI, no PRIMARY KEY collisions
- Streaming for all UMLS files; 5k-row commits for all other writes
- LEX, NET, MRHIER skipped in v1
"""

from __future__ import annotations

import ast
import gc
import json
import logging
import os
import re
import sys
import time
import traceback
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterator, List, Optional, Set, Tuple

import kuzu
import psutil
import pyarrow as pa
import pyarrow.parquet as pq

# ── Paths ─────────────────────────────────────────────────────────────────────
BASE         = Path("/home/dicksone/Documents/MedGraphRag")
NORM_DIR     = BASE / "Datasets" / "normalized"
INDEX_DIR    = BASE / "index" / "global"
DB_DIR       = INDEX_DIR / "kuzu_db_v5"
MANIFEST     = BASE / "Embedding_pipline" / "manifest.jsonl"
IDMAP_PAR    = INDEX_DIR / "id_mapping.parquet"
CHUNKS_FILE  = INDEX_DIR / "chunks.jsonl"
CHUNKS_PAR   = INDEX_DIR / "chunks_for_kuzu.parquet"
HAS_CHUNK_PAR= INDEX_DIR / "has_chunk_edges.parquet"
LOGS_DIR     = INDEX_DIR / "logs"
GRAPH_LOG    = LOGS_DIR  / "graph_build.log"
REPORT_FILE  = INDEX_DIR / "graph_report.json"
CHECKPOINT_FP= INDEX_DIR / "graph_checkpoint.json"

UMLS_DIR   = NORM_DIR / "UMLS Output" / "META"
MRCONSO_FP = UMLS_DIR / "MRCONSO.json"
MRREL_FP   = UMLS_DIR / "MRREL.json"
MRSTY_FP   = UMLS_DIR / "MRSTY.json"
MRDEF_FP   = UMLS_DIR / "MRDEF.json"

DRUG_DIR      = NORM_DIR / "Drug_database"
DRUGBANK_FP   = DRUG_DIR / "drugbank_full_database.json"
DRUG_NAMES_FP = DRUG_DIR / "drug_names.json"
MEDDRA_FREQ_FP= DRUG_DIR / "meddra_freq.json"
MEDDRA_IND_FP = DRUG_DIR / "meddra_all_indications.json"
MEDDRA_SE_FP  = DRUG_DIR / "meddra_all_se.json"

LAB_DIR      = NORM_DIR / "Lab_rev_data"
LAB_CRIT_FP  = LAB_DIR / "Consolidated_Lab_Critical_Values_Dataset_CLEANED.json"
LAB_LOINC_FP = LAB_DIR / "41597_2026_7554_MOESM2_ESM.json"

DISEASE_DIR  = NORM_DIR / "Disease_knowledge"
MPLUS_TOPICS = DISEASE_DIR / "mplus_topics_2026-07-17.json"

# ── Config ────────────────────────────────────────────────────────────────────
BATCH_SIZE = 5000
NOW_TS     = datetime.now(timezone.utc).isoformat()
# Reconnect Kùzu every this many write ops to release dirty buffer pages.
RECONNECT_INTERVAL = 5000

# Strict 5 STYs per Rule 13
DISEASE_STYS = {
    "Disease or Syndrome", "Finding", "Sign or Symptom",
    "Neoplastic Process", "Pathologic Function",
}

SAB_PRIORITY = {"SNOMEDCT_US": 10, "NCI": 8, "MSH": 7, "ICD10CM": 6, "ICD10": 5}
DEF_SAB_PREF = {"MSH": 5, "NCI": 4, "SNOMEDCT_US": 3, "CSP": 2}

LAB_CAT_DISEASE_MAP = {
    "CBC":         ["Anemia", "Leukemia", "Thrombocytopenia"],
    "KFT":         ["Chronic Kidney Disease", "Acute Kidney Injury"],
    "LFT":         ["Liver Disease", "Hepatitis", "Cirrhosis"],
    "Chemistry":   ["Diabetes Mellitus", "Hypoglycemia"],
    "Electrolytes":["Hypokalemia", "Hyperkalemia", "Hyponatremia"],
    "Coagulation": ["Coagulopathy", "Hemophilia", "Thrombosis"],
    "Thyroid":     ["Hypothyroidism", "Hyperthyroidism"],
    "Cardiac":     ["Heart Failure", "Myocardial Infarction"],
    "Microbiology":["Sepsis", "Bacteremia", "Infection"],
    "Lipids":      ["Hyperlipidemia", "Atherosclerosis"],
    "Urinalysis":  ["Urinary Tract Infection", "Nephritis"],
}

# ── Logging ───────────────────────────────────────────────────────────────────
os.makedirs(LOGS_DIR, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.FileHandler(GRAPH_LOG), logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger(__name__)


# ── Kùzu Database Lifecycle ──────────────────────────────────────────────────
DB_KWARGS = dict(
    buffer_pool_size = 256 * 1024 * 1024,
    max_db_size      = 4 * 1024**3,
    max_num_threads  = 2,
)

def open_db():
    db = kuzu.Database(str(DB_DIR), **DB_KWARGS)
    conn = kuzu.Connection(db)
    return db, conn

def close_db(db, conn):
    try:
        conn.close()
    except Exception:
        pass
    del conn, db
    gc.collect()

# ── RAM Guard & Checkpoint Helpers ───────────────────────────────────────────
def check_ram_guard(min_free_gb: float = 3.0):
    vm = psutil.virtual_memory()
    free_gb = vm.available / (1024 ** 3)
    if free_gb < min_free_gb:
        log.warning(f"RAM Guard: Free RAM is {free_gb:.2f} GB (< {min_free_gb} GB threshold). Pausing for gc...")
        gc.collect()
        time.sleep(10)
        gc.collect()

def load_checkpoint() -> set:
    if CHECKPOINT_FP.exists():
        try:
            with open(CHECKPOINT_FP) as f:
                data = json.load(f)
                return set(data.get("completed_phases", []))
        except Exception:
            pass
    return set()

def save_checkpoint(phase_name: str):
    completed = load_checkpoint()
    completed.add(phase_name)
    with open(CHECKPOINT_FP, "w") as f:
        json.dump({"completed_phases": list(completed), "last_updated": NOW_TS}, f, indent=2)
    log.info(f"Checkpoint saved for phase: {phase_name}")


# ── Helpers ───────────────────────────────────────────────────────────────────
def uid(*parts) -> str:
    return hashlib.md5("||".join(str(p) for p in parts).encode()).hexdigest()[:16]

def safe_str(v, maxlen=2000) -> str:
    if v is None: return ""
    s = str(v).strip()
    return s[:maxlen] if len(s) > maxlen else s

def safe_float(v) -> Optional[float]:
    try:
        f = float(str(v).replace('≤','').replace('≥','').replace('<','').replace('>','').strip())
        return f
    except (ValueError, TypeError):
        return None

def txn_begin(conn):    conn.execute("BEGIN TRANSACTION")
def txn_commit(conn):
    conn.execute("COMMIT")
    try:
        conn.execute("CHECKPOINT")
    except Exception:
        pass

def stream_umls_rows(filepath: Path) -> Iterator[list]:
    with open(filepath, errors='ignore') as f:
        in_rows = False
        for line in f:
            if '"rows":' in line:
                in_rows = True
                continue
            if not in_rows:
                continue
            line = line.strip().rstrip(',')
            if not line.startswith('['):
                continue
            try:
                yield json.loads(line)
            except Exception:
                pass


# ── Phase 0: DDL ─────────────────────────────────────────────────────────────
DDL_STATEMENTS = [
    """CREATE NODE TABLE IF NOT EXISTS OntologyTerm (
        term_id      STRING,
        ontology     STRING,
        term         STRING,
        aliases      STRING,
        active       INT8,
        definition   STRING,
        source_doc   STRING,
        processed_at STRING,
        PRIMARY KEY (term_id)
    )""",
    """CREATE NODE TABLE IF NOT EXISTS Disease (
        disease_id     STRING,
        name           STRING,
        aliases        STRING,
        description    STRING,
        icd10_codes    STRING,
        url            STRING,
        definition     STRING,
        source_doc     STRING,
        source_dataset STRING,
        processed_at   STRING,
        PRIMARY KEY (disease_id)
    )""",
    """CREATE NODE TABLE IF NOT EXISTS Drug (
        node_id      STRING,
        drugbank_id  STRING,
        stitch_cid   STRING,
        name         STRING,
        description  STRING,
        drug_type    STRING,
        cas_number   STRING,
        state        STRING,
        groups       STRING,
        atc_codes    STRING,
        source_doc   STRING,
        processed_at STRING,
        PRIMARY KEY (node_id)
    )""",
    """CREATE NODE TABLE IF NOT EXISTS LabTest (
        lab_test_id  STRING,
        test_name    STRING,
        category     STRING,
        specimen     STRING,
        normal_low   DOUBLE,
        normal_high  DOUBLE,
        critical_low STRING,
        critical_high STRING,
        unit         STRING,
        age_group    STRING,
        gender       STRING,
        loinc_code   STRING,
        si_interval  STRING,
        si_unit      STRING,
        source_doc   STRING,
        processed_at STRING,
        PRIMARY KEY (lab_test_id)
    )""",
    """CREATE NODE TABLE IF NOT EXISTS Document (
        document_id    STRING,
        category       STRING,
        subcategory    STRING,
        subpath        STRING,
        title          STRING,
        language       STRING,
        source_dataset STRING,
        format         STRING,
        target         STRING,
        source_doc     STRING,
        processed_at   STRING,
        PRIMARY KEY (document_id)
    )""",
    """CREATE NODE TABLE IF NOT EXISTS Chunk (
        chunk_id     STRING,
        document_id  STRING,
        chunk_type   STRING,
        token_count  INT32,
        faiss_id     INT64,
        category     STRING,
        source_doc   STRING,
        PRIMARY KEY (chunk_id)
    )""",
    """CREATE REL TABLE IF NOT EXISTS HAS_CHUNK (
        FROM Document TO Chunk,
        source_doc   STRING,
        processed_at STRING
    )""",
    """CREATE REL TABLE IF NOT EXISTS IS_A (
        FROM OntologyTerm TO OntologyTerm,
        rel_type     STRING,
        sab          STRING,
        source_doc   STRING,
        processed_at STRING
    )""",
    """CREATE REL TABLE IF NOT EXISTS RELATED_TO (
        FROM OntologyTerm TO OntologyTerm,
        rel_type     STRING,
        rela         STRING,
        sab          STRING,
        source_doc   STRING,
        processed_at STRING
    )""",
    """CREATE REL TABLE IF NOT EXISTS DRUG_TREATS (
        FROM Drug TO Disease,
        mention_type STRING,
        meddra_term  STRING,
        source_doc   STRING,
        processed_at STRING
    )""",
    """CREATE REL TABLE IF NOT EXISTS DRUG_CAUSES (
        FROM Drug TO Disease,
        frequency_pct DOUBLE,
        meddra_type   STRING,
        meddra_term   STRING,
        source_doc    STRING,
        processed_at  STRING
    )""",
    """CREATE REL TABLE IF NOT EXISTS DRUG_CAUSES_SE (
        FROM Drug TO Disease,
        meddra_type  STRING,
        meddra_term  STRING,
        source_doc   STRING,
        processed_at STRING
    )""",
    """CREATE REL TABLE IF NOT EXISTS DISEASE_MAPPED_TO (
        FROM Disease TO OntologyTerm,
        mapping_type STRING,
        source_doc   STRING,
        processed_at STRING
    )""",
    """CREATE REL TABLE IF NOT EXISTS DOCUMENT_MENTIONS (
        FROM Document TO Disease,
        source_doc   STRING,
        processed_at STRING
    )""",
    """CREATE REL TABLE IF NOT EXISTS LABTEST_RELATED_TO (
        FROM LabTest TO Disease,
        relation_type STRING,
        source_doc    STRING,
        processed_at  STRING
    )""",
]

def run_ddl(conn):
    log.info("Phase 0: DDL")
    for stmt in DDL_STATEMENTS:
        conn.execute(stmt)
    log.info("  DDL complete — %d tables", len(DDL_STATEMENTS))


# ── Phase 1: MRSTY → disease_cui_set ─────────────────────────────────────────
def build_disease_cui_set() -> Set[str]:
    log.info("Phase 1: Building disease CUI set from MRSTY ...")
    cuis: Set[str] = set()
    for row in stream_umls_rows(MRSTY_FP):
        if len(row) >= 4 and row[3] in DISEASE_STYS:
            cuis.add(row[0])
    log.info(f"  disease_cui_set: {len(cuis):,} CUIs")
    return cuis


# ── Phase 2: MRDEF → definition_dict ─────────────────────────────────────────
def build_definition_dict(disease_cuis: Set[str]) -> Dict[str, str]:
    log.info("Phase 2: Building definition dict from MRDEF (92 MB) ...")
    defs: Dict[str, Tuple[str, int]] = {}
    for row in stream_umls_rows(MRDEF_FP):
        if len(row) < 6:
            continue
        cui  = row[0]
        sab  = row[4]
        sup  = row[6] if len(row) > 6 else 'N'
        defn = row[5]
        if sup == 'Y' or cui not in disease_cuis:
            continue
        prio = DEF_SAB_PREF.get(sab, 1)
        ex = defs.get(cui)
        if ex is None or prio > ex[1]:
            defs[cui] = (safe_str(defn, 3000), prio)
    result = {cui: v[0] for cui, v in defs.items()}
    log.info(f"  definitions: {len(result):,} CUIs with definitions")
    return result


# ── Phase 3: MRCONSO → OntologyTerm nodes ────────────────────────────────────
def build_ontology_terms(conn, disease_cuis: Set[str], def_dict: Dict[str, str]) -> int:
    log.info("Phase 3: Streaming MRCONSO → OntologyTerm nodes ...")
    staged: Dict[str, dict] = {}

    for row in stream_umls_rows(MRCONSO_FP):
        if len(row) < 15:
            continue
        cui     = row[0]
        lat     = row[1]
        ispref  = row[6]
        sab     = row[11]
        sup     = row[16] if len(row) > 16 else 'N'
        str_val = row[14]

        if sup == 'Y' or lat != 'ENG' or cui not in disease_cuis:
            continue
        if sab not in SAB_PRIORITY:
            continue

        prio = SAB_PRIORITY[sab]
        ex = staged.get(cui)
        if ex is None:
            staged[cui] = {
                "term_id":  cui, "ontology": sab, "term": str_val,
                "aliases":  [], "active": 1, "priority": prio,
            }
        else:
            if prio > ex["priority"]:
                ex["term"]     = str_val
                ex["ontology"] = sab
                ex["priority"] = prio
            elif str_val not in ex["aliases"] and str_val != ex["term"]:
                ex["aliases"].append(str_val)

    log.info(f"  Staged {len(staged):,} unique OntologyTerm nodes")

    n = 0
    txn_begin(conn)
    for node in staged.values():
        aliases_j = json.dumps(node["aliases"][:20])
        defn      = def_dict.get(node["term_id"], "")
        conn.execute(
            "MERGE (x:OntologyTerm {term_id: $term_id}) "
            "SET x.ontology=$ontology, x.term=$term, x.aliases=$aliases, "
            "x.active=$active, x.definition=$definition, "
            "x.source_doc=$source_doc, x.processed_at=$processed_at",
            {"term_id": node["term_id"], "ontology": node["ontology"],
             "term": node["term"], "aliases": aliases_j,
             "active": node["active"], "definition": defn,
             "source_doc": "UMLS Output/META/MRCONSO", "processed_at": NOW_TS}
        )
        n += 1
        if n % BATCH_SIZE == 0:
            txn_commit(conn)
            log.info(f"  OntologyTerm: {n:,} committed")
            txn_begin(conn)
    txn_commit(conn)
    del staged; gc.collect()
    log.info(f"  OntologyTerm: {n:,} nodes inserted")
    return n


# ── Phase 4: Disease nodes ────────────────────────────────────────────────────
def build_disease_nodes(conn, disease_cuis: Set[str], def_dict: Dict[str, str]) -> Tuple[int, Dict[str, str]]:
    log.info("Phase 4: Building Disease nodes ...")

    mesh_to_cui: Dict[str, str] = {}
    for row in stream_umls_rows(MRCONSO_FP):
        if len(row) < 15:
            continue
        cui = row[0]; lat = row[1]; sab = row[11]
        sup = row[16] if len(row) > 16 else 'N'
        code = row[13]
        if sup == 'Y' or lat != 'ENG' or cui not in disease_cuis:
            continue
        if sab == 'MSH' and code.startswith('D'):
            mesh_to_cui[code] = cui

    log.info(f"  MeSH→CUI map: {len(mesh_to_cui):,}")

    staged: Dict[str, dict] = {}

    def _add(cui, name, aliases_set, desc, url, src, src_ds):
        if not cui or not cui.startswith('C'): return
        if cui in staged:
            staged[cui]["aliases"] |= aliases_set
            if not staged[cui]["description"] and desc:
                staged[cui]["description"] = desc
            if not staged[cui]["url"] and url:
                staged[cui]["url"] = url
        else:
            staged[cui] = {"disease_id": cui, "name": name,
                           "aliases": aliases_set, "description": desc,
                           "icd10_codes": [], "url": url,
                           "source_doc": src, "source_dataset": src_ds}

    with open(MEDDRA_IND_FP) as f:
        doc = json.load(f)
    for row in doc.get("structured_data",[{}])[0].get("rows",[]):
        if len(row) >= 4:
            _add(str(row[1]) if row[1] else "", str(row[3]) if row[3] else "",
                 set(), "", "", "Drug_database/meddra_all_indications", "Drug_database")
    del doc; gc.collect()

    with open(MEDDRA_FREQ_FP) as f:
        doc2 = json.load(f)
    for row in doc2.get("structured_data",[{}])[0].get("rows",[]):
        if len(row) >= 10:
            _add(str(row[2]) if row[2] else "", str(row[9]) if row[9] else "",
                 set(), "", "", "Drug_database/meddra_freq", "Drug_database")
    del doc2; gc.collect()

    with open(MEDDRA_SE_FP) as f:
        doc3 = json.load(f)
    for row in doc3.get("structured_data",[{}])[0].get("rows",[]):
        if len(row) >= 6:
            _add(str(row[2]) if row[2] else "", str(row[5]) if row[5] else "",
                 set(), "", "", "Drug_database/meddra_all_se", "Drug_database")
    del doc3; gc.collect()

    with open(MPLUS_TOPICS, errors='ignore') as f:
        raw = f.read()
    try:
        body_match = re.search(r'"body":\s*"(\{.+?})",\s*"structured_data"', raw, re.DOTALL)
        if body_match:
            body_str = body_match.group(1).replace('\\"', '"').replace('\\n', '\n')
            try:
                topics_data = ast.literal_eval(body_str)
            except Exception:
                topics_data = {}
            topics = []
            if isinstance(topics_data, dict):
                ht = topics_data.get('health-topics', {})
                topics = ht.get('health-topic', []) if isinstance(ht, dict) else []
            for topic in topics:
                if not isinstance(topic, dict): continue
                if topic.get('@language','') != 'English': continue
                mesh_hdr = topic.get('mesh-heading', {})
                if not isinstance(mesh_hdr, dict): continue
                desc_raw = mesh_hdr.get('descriptor', {})
                if not isinstance(desc_raw, dict): continue
                mesh_id = desc_raw.get('@id','')
                if not mesh_id.startswith('D'): continue
                cui = mesh_to_cui.get(mesh_id)
                if not cui: continue
                summary = re.sub(r'<[^>]+>', '', str(topic.get('full-summary','') or ''))[:3000]
                _add(cui, topic.get('@title',''), set(), summary,
                     topic.get('@url',''), "Disease_knowledge/mplus_topics_2026-07-17", "Disease_knowledge")
    except Exception as e:
        log.warning(f"  mplus_topics parse warning (non-fatal): {e}")
    del raw; gc.collect()

    log.info(f"  Staged {len(staged):,} unique Disease nodes")

    n = 0
    txn_begin(conn)
    for node in staged.values():
        aliases_j = json.dumps(list(node["aliases"])[:20])
        defn      = def_dict.get(node["disease_id"], "")
        conn.execute(
            "MERGE (x:Disease {disease_id: $disease_id}) "
            "SET x.name=$name, x.aliases=$aliases, x.description=$description, "
            "x.icd10_codes=$icd10_codes, x.url=$url, x.definition=$definition, "
            "x.source_doc=$source_doc, x.source_dataset=$source_dataset, x.processed_at=$processed_at",
            {"disease_id": node["disease_id"], "name": node["name"],
             "aliases": aliases_j, "description": node["description"],
             "icd10_codes": json.dumps(node["icd10_codes"]),
             "url": node["url"], "definition": defn,
             "source_doc": node["source_doc"],
             "source_dataset": node["source_dataset"], "processed_at": NOW_TS}
        )
        n += 1
        if n % BATCH_SIZE == 0:
            txn_commit(conn)
            log.info(f"  Disease: {n:,} committed")
            txn_begin(conn)
    txn_commit(conn)
    del staged; gc.collect()
    log.info(f"  Disease: {n:,} nodes inserted")
    return n, mesh_to_cui


# ── Phase 5: Drug nodes ───────────────────────────────────────────────────────
def _load_drug_id_map() -> Dict[str, str]:
    with open(DRUG_NAMES_FP) as f:
        dn_doc = json.load(f)
    dn_sd = dn_doc.get("structured_data",[{}])[0]
    name_to_cid: Dict[str, str] = {}
    for row in dn_sd.get("rows",[]):
        if len(row) >= 2 and row[0] and row[1]:
            name_to_cid[str(row[1]).lower().strip()] = str(row[0])
    del dn_doc; gc.collect()

    with open(DRUGBANK_FP) as f:
        db_doc = json.load(f)
    body_str = (db_doc.get("text") or {}).get("body") or ""
    del db_doc; gc.collect()

    matches = re.findall(
        r"'drugbank-id':\s*(?:\[\{'@primary':\s*'true',\s*'#text':\s*'([A-Z0-9]+)'\}|'([A-Z0-9]+)').*?'name':\s*'([^']+)'",
        body_str
    )
    del body_str; gc.collect()

    drug_id_map: Dict[str, str] = {}
    for primary_dbid, simple_dbid, name in matches:
        dbid = primary_dbid or simple_dbid
        if not dbid or not dbid.startswith('DB'): continue
        cid = name_to_cid.get(name.lower().strip(), "")
        drug_id_map[dbid] = cid if cid else dbid
    del matches; gc.collect()
    log.info(f"  drug_id_map rebuilt from files: {len(drug_id_map):,} entries")
    return drug_id_map


def build_drug_nodes(drug_id_map: Dict[str, str]) -> int:
    log.info("Phase 5: Building Drug nodes ...")

    with open(DRUG_NAMES_FP) as f:
        dn_doc = json.load(f)
    dn_sd = dn_doc.get("structured_data",[{}])[0]
    name_to_cid: Dict[str, str] = {}
    for row in dn_sd.get("rows",[]):
        if len(row) >= 2 and row[0] and row[1]:
            name_to_cid[str(row[1]).lower().strip()] = str(row[0])

    with open(DRUG_DIR / "drug_atc.json") as f:
        atc_doc = json.load(f)
    cid_to_atcs: Dict[str, list] = {}
    for row in atc_doc.get("structured_data",[{}])[0].get("rows",[]):
        if len(row) >= 2 and row[0] and row[1]:
            cid_to_atcs.setdefault(str(row[0]), []).append(str(row[1]))
    del dn_doc, atc_doc; gc.collect()

    with open(DRUGBANK_FP) as f:
        db_doc = json.load(f)
    body_str = (db_doc.get("text") or {}).get("body") or ""
    del db_doc; gc.collect()

    matches = re.findall(
        r"'drugbank-id':\s*(?:\[\{'@primary':\s*'true',\s*'#text':\s*'([A-Z0-9]+)'\}|'([A-Z0-9]+)').*?'name':\s*'([^']+)'",
        body_str
    )
    del body_str; gc.collect()

    n = 0
    db, conn = open_db()
    txn_begin(conn)
    for primary_dbid, simple_dbid, name in matches:
        dbid = primary_dbid or simple_dbid
        if not dbid or not dbid.startswith('DB'): continue
        node_id = drug_id_map.get(dbid, dbid)

        conn.execute(
            "MERGE (x:Drug {node_id: $node_id}) "
            "SET x.drugbank_id=$drugbank_id, x.stitch_cid=$stitch_cid, x.name=$name, "
            "x.description='', x.drug_type='', x.cas_number='', "
            "x.state='', x.groups='[]', x.atc_codes=$atc_codes, "
            "x.source_doc=$source_doc, x.processed_at=$processed_at",
            {"node_id": node_id, "drugbank_id": dbid, "stitch_cid": node_id if node_id.startswith('CID') else "",
             "name": safe_str(name, 200),
             "atc_codes": json.dumps(cid_to_atcs.get(node_id, [])),
             "source_doc": "Drug_database/drugbank_full_database",
             "processed_at": NOW_TS}
        )
        n += 1
        if n % RECONNECT_INTERVAL == 0:
            txn_commit(conn)
            close_db(db, conn)
            log.info(f"  Drug: {n:,} committed (reconnect)")
            check_ram_guard()
            db, conn = open_db()
            txn_begin(conn)
    txn_commit(conn)
    close_db(db, conn)
    del matches; gc.collect()
    log.info(f"  Drug: {n:,} nodes inserted")
    return n


# ── Phase 6: LabTest nodes ────────────────────────────────────────────────────
def build_labtest_nodes(conn) -> int:
    log.info("Phase 6: Building LabTest nodes ...")
    n = 0

    def _insert(row, headers, source_doc, loinc="", si_int="", si_u=""):
        h = {hdr: (row[i] if i < len(row) else None) for i, hdr in enumerate(headers)}
        test_name = safe_str(h.get("Test Name","") or h.get("Component Name","") or "", 200)
        if not test_name or test_name.lower() in ('nan','none',''): return False
        specimen  = safe_str(h.get("Specimen","") or h.get("System","") or "", 200)
        age_group = safe_str(h.get("Age Group","") or "", 100)
        gender    = safe_str(h.get("Gender","") or "", 50)
        lab_id    = uid(test_name, specimen, age_group, gender, source_doc)
        conn.execute(
            "MERGE (x:LabTest {lab_test_id: $lab_test_id}) "
            "SET x.test_name=$test_name, x.category=$category, x.specimen=$specimen, "
            "x.normal_low=$normal_low, x.normal_high=$normal_high, "
            "x.critical_low=$critical_low, x.critical_high=$critical_high, "
            "x.unit=$unit, x.age_group=$age_group, x.gender=$gender, "
            "x.loinc_code=$loinc_code, x.si_interval=$si_interval, x.si_unit=$si_unit, "
            "x.source_doc=$source_doc, x.processed_at=$processed_at",
            {"lab_test_id": lab_id, "test_name": test_name,
             "category": safe_str(h.get("Category","") or h.get("Category of Lab Test","") or "", 100),
             "specimen": specimen,
             "normal_low": safe_float(h.get("Normal Low")),
             "normal_high": safe_float(h.get("Normal High")),
             "critical_low": safe_str(h.get("Critical Low","") or "", 50),
             "critical_high": safe_str(h.get("Critical High","") or "", 50),
             "unit": safe_str(h.get("Unit","") or h.get("Traditional Units","") or "", 50),
             "age_group": age_group, "gender": gender,
             "loinc_code": loinc, "si_interval": si_int, "si_unit": si_u,
             "source_doc": source_doc, "processed_at": NOW_TS}
        )
        return True

    for fp, extra_fn in [(LAB_CRIT_FP, lambda r: ()), (LAB_LOINC_FP, lambda r: (safe_str(r[0] if r else ""), safe_str(r[12] if len(r)>12 else ""), safe_str(r[13] if len(r)>13 else "")))]:
        with open(fp) as f:
            doc = json.load(f)
        sd = doc.get("structured_data",[{}])[0]
        hdrs = sd.get("headers",[])
        src  = f"Lab_rev_data/{fp.stem}"
        txn_begin(conn)
        for row in sd.get("rows",[]):
            extra = extra_fn(row) if fp == LAB_LOINC_FP else ()
            if fp == LAB_LOINC_FP:
                loinc, si_int, si_u = extra
            else:
                loinc = si_int = si_u = ""
            if _insert(row, hdrs, src, loinc, si_int, si_u):
                n += 1
                if n % BATCH_SIZE == 0:
                    txn_commit(conn)
                    txn_begin(conn)
        txn_commit(conn)
        del doc; gc.collect()

    log.info(f"  LabTest: {n:,} nodes inserted")
    return n


# ── Phase 7: Document nodes ───────────────────────────────────────────────────
def build_document_nodes(conn) -> int:
    log.info("Phase 7: Building Document nodes from manifest ...")
    n = 0
    seen_hashes: Set[str] = set()
    seen_ids: Set[str] = set()
    txn_begin(conn)
    with open(MANIFEST) as f:
        for line in f:
            rec = json.loads(line)
            target = rec.get("target", "")
            if target == "none":
                continue
            doc_id = rec["document_id"]
            file_hash = rec.get("file_hash_sha256") or rec.get("sha256") or doc_id
            if file_hash in seen_hashes or doc_id in seen_ids:
                continue
            seen_hashes.add(file_hash)
            seen_ids.add(doc_id)

            conn.execute(
                "MERGE (x:Document {document_id: $document_id}) "
                "SET x.category=$category, x.subcategory=$subcategory, x.subpath=$subpath, "
                "x.title=$title, x.language=$language, x.source_dataset=$source_dataset, "
                "x.format=$format, x.target=$target, "
                "x.source_doc=$source_doc, x.processed_at=$processed_at",
                {"document_id": doc_id,
                 "category": rec.get("category",""), "subcategory": rec.get("subcategory",""),
                 "subpath": rec.get("subpath",""), "title": safe_str(rec.get("title",""),500),
                 "language": rec.get("language","en"), "source_dataset": rec.get("source",""),
                 "format": rec.get("format",""), "target": target,
                 "source_doc": doc_id, "processed_at": NOW_TS}
            )
            n += 1
            if n % BATCH_SIZE == 0:
                txn_commit(conn)
                log.info(f"  Document: {n:,} committed")
                txn_begin(conn)
    txn_commit(conn)
    log.info(f"  Document: {n:,} nodes inserted (deduped)")
    return n


# ── Phase 8: Chunk nodes via COPY FROM parquet ────────────────────────────────
def build_chunk_parquet_and_copy(conn) -> int:
    log.info("Phase 8: Building chunks_for_kuzu.parquet ...")

    schema = pa.schema([
        ("chunk_id",    pa.string()),
        ("document_id", pa.string()),
        ("chunk_type",  pa.string()),
        ("token_count", pa.int32()),
        ("faiss_id",    pa.int64()),
        ("category",    pa.string()),
        ("source_doc",  pa.string()),
    ])

    if not CHUNKS_PAR.exists():
        writer = pq.ParquetWriter(str(CHUNKS_PAR), schema, compression='snappy')
        pf = pq.ParquetFile(IDMAP_PAR)
        n = 0
        for batch in pf.iter_batches(batch_size=50000):
            check_ram_guard()
            pydict = batch.to_pydict()
            n_rows = len(pydict["chunk_id"])
            slab = {
                "chunk_id":    pydict["chunk_id"],
                "document_id": pydict["document_id"],
                "chunk_type":  pydict["chunk_type"],
                "token_count": [int(x) for x in pydict["token_count"]],
                "faiss_id":    [int(x) for x in pydict["faiss_id"]],
                "category":    pydict["category"],
                "source_doc":  pydict["document_id"],
            }
            tbl = pa.table(slab, schema=schema)
            writer.write_table(tbl)
            n += n_rows
            log.info(f"  Parquet slab: {n:,} rows written")
            del slab, tbl, pydict, batch; gc.collect()

        writer.close()
    else:
        log.info("  chunks_for_kuzu.parquet already exists on disk — resuming directly to COPY FROM")
        n = 2294038

    sz_mb = CHUNKS_PAR.stat().st_size / (1024 ** 2)
    log.info(f"  chunks_for_kuzu.parquet: {n:,} rows | {sz_mb:.1f} MB")
    log.info("  COPY FROM parquet → Chunk table ...")
    conn.execute(f"COPY Chunk FROM '{CHUNKS_PAR}'")
    log.info(f"  Chunk: {n:,} nodes loaded via COPY FROM")
    return n


# ── Phase 9: MRREL → IS_A + RELATED_TO edges ─────────────────────────────────
IS_A_RELS = {'PAR', 'CHD', 'RB', 'RN'}
REL_RELS  = {'RO', 'SY'}

def build_umls_edges(disease_cuis: Set[str]) -> Tuple[int, int]:
    """Stream MRREL → IS_A + RELATED_TO edges with reconnect every RECONNECT_INTERVAL."""
    log.info("Phase 9: Streaming MRREL → IS_A + RELATED_TO edges ...")
    n_isa = 0; n_rel = 0
    SRC = "UMLS Output/META/MRREL"
    SAB_PRIORITY = {'SNOMEDCT_US', 'MSH', 'NCI', 'ICD10CM', 'MTHICD9', 'LNC', 'CPT', 'RXNORM'}
    batch: list = []   # accumulate (type, tuple) pairs
    ops_since_reconnect = 0
    db, conn = open_db()

    def flush_batch():
        nonlocal n_isa, n_rel, ops_since_reconnect, db, conn
        if not batch: return
        txn_begin(conn)
        for kind, data in batch:
            try:
                if kind == 'isa':
                    cui1, cui2, rel, sab = data
                    conn.execute(
                        "MATCH (a:OntologyTerm {term_id:$c1}), (b:OntologyTerm {term_id:$c2}) "
                        "CREATE (a)-[:IS_A {rel_type:$rel, sab:$sab, source_doc:$src, processed_at:$ts}]->(b)",
                        {"c1":cui1,"c2":cui2,"rel":rel,"sab":sab,"src":SRC,"ts":NOW_TS})
                    n_isa += 1
                else:
                    cui1, cui2, rel, rela, sab = data
                    conn.execute(
                        "MATCH (a:OntologyTerm {term_id:$c1}), (b:OntologyTerm {term_id:$c2}) "
                        "CREATE (a)-[:RELATED_TO {rel_type:$rel, rela:$rela, sab:$sab, source_doc:$src, processed_at:$ts}]->(b)",
                        {"c1":cui1,"c2":cui2,"rel":rel,"rela":rela,"sab":sab,"src":SRC,"ts":NOW_TS})
                    n_rel += 1
            except Exception:
                pass
        txn_commit(conn)
        ops_since_reconnect += len(batch)
        batch.clear()
        # Reconnect to release Kùzu's dirty buffer pages
        if ops_since_reconnect >= RECONNECT_INTERVAL:
            close_db(db, conn)
            log.info(f"  UMLS edges: IS_A={n_isa:,}  RELATED_TO={n_rel:,}  (reconnect)")
            check_ram_guard()
            db, conn = open_db()
            ops_since_reconnect = 0

    for row in stream_umls_rows(MRREL_FP):
        if len(row) < 11: continue
        cui1 = row[0]; rel = row[3]; cui2 = row[4]
        rela = row[7] if len(row) > 7 else ""
        sab  = row[10]
        sup  = row[14] if len(row) > 14 else 'N'
        if sup == 'Y': continue
        if cui1 not in disease_cuis or cui2 not in disease_cuis: continue
        if sab not in SAB_PRIORITY: continue
        if rel in IS_A_RELS:
            batch.append(('isa', (cui1, cui2, rel, sab)))
        elif rel in REL_RELS:
            batch.append(('rel', (cui1, cui2, rel, safe_str(rela,50), sab)))
        if len(batch) >= BATCH_SIZE:
            flush_batch()

    flush_batch()
    close_db(db, conn)
    log.info(f"  IS_A: {n_isa:,} | RELATED_TO: {n_rel:,}")
    return n_isa, n_rel


# ── Phase 10: Drug edges ──────────────────────────────────────────────────────
def build_drug_edges(drug_id_map: Dict[str, str]) -> Tuple[int, int, int]:
    """Build DRUG_TREATS / DRUG_CAUSES / DRUG_CAUSES_SE with reconnect."""
    log.info("Phase 10: Building DRUG_TREATS / DRUG_CAUSES / DRUG_CAUSES_SE edges ...")

    cid_to_nid = {v: v for v in drug_id_map.values() if v.startswith("CID")}
    def get_nid(stitch_cid: str) -> str:
        return cid_to_nid.get(str(stitch_cid), "")

    def _insert_edges(rows, min_cols, cid_col, cui_col, edge_query, edge_args_fn, label):
        """Generic edge inserter with reconnect every RECONNECT_INTERVAL."""
        n = 0
        ops_since_reconnect = 0
        db, conn = open_db()
        txn_begin(conn)
        for row in rows:
            if len(row) < min_cols: continue
            nid = get_nid(str(row[cid_col]) if row[cid_col] else "")
            cui = str(row[cui_col]) if row[cui_col] else ""
            if not nid or not cui.startswith('C'): continue
            try:
                conn.execute(edge_query, edge_args_fn(nid, cui, row))
                n += 1
                ops_since_reconnect += 1
            except Exception: pass
            if ops_since_reconnect >= RECONNECT_INTERVAL:
                txn_commit(conn)
                close_db(db, conn)
                log.info(f"  {label}: {n:,} (reconnect)")
                check_ram_guard()
                db, conn = open_db()
                txn_begin(conn)
                ops_since_reconnect = 0
        txn_commit(conn)
        close_db(db, conn)
        return n

    # DRUG_TREATS
    with open(MEDDRA_IND_FP) as f:
        doc = json.load(f)
    rows_treats = doc.get("structured_data",[{}])[0].get("rows",[])
    n_treats = _insert_edges(
        rows_treats, 4, 0, 1,
        "MATCH (d:Drug {node_id:$nid}),(dis:Disease {disease_id:$cui}) "
        "CREATE (d)-[:DRUG_TREATS {mention_type:$mt, meddra_term:$term, source_doc:$src, processed_at:$ts}]->(dis)",
        lambda nid, cui, r: {"nid":nid,"cui":cui,"mt":safe_str(r[2],50),"term":safe_str(r[3],200),
                             "src":"Drug_database/meddra_all_indications","ts":NOW_TS},
        "DRUG_TREATS"
    )
    del doc, rows_treats; gc.collect()

    # DRUG_CAUSES
    with open(MEDDRA_FREQ_FP) as f:
        doc2 = json.load(f)
    rows_causes = doc2.get("structured_data",[{}])[0].get("rows",[])
    n_causes = _insert_edges(
        rows_causes, 10, 0, 2,
        "MATCH (d:Drug {node_id:$nid}),(dis:Disease {disease_id:$cui}) "
        "CREATE (d)-[:DRUG_CAUSES {frequency_pct:$freq, meddra_type:$mt, meddra_term:$term, source_doc:$src, processed_at:$ts}]->(dis)",
        lambda nid, cui, r: {"nid":nid,"cui":cui,"freq":safe_float(r[5]),"mt":safe_str(r[7],50),"term":safe_str(r[9],200),
                             "src":"Drug_database/meddra_freq","ts":NOW_TS},
        "DRUG_CAUSES"
    )
    del doc2, rows_causes; gc.collect()

    # DRUG_CAUSES_SE
    with open(MEDDRA_SE_FP) as f:
        doc3 = json.load(f)
    rows_se = doc3.get("structured_data",[{}])[0].get("rows",[])
    n_se = _insert_edges(
        rows_se, 6, 0, 2,
        "MATCH (d:Drug {node_id:$nid}),(dis:Disease {disease_id:$cui}) "
        "CREATE (d)-[:DRUG_CAUSES_SE {meddra_type:$mt, meddra_term:$term, source_doc:$src, processed_at:$ts}]->(dis)",
        lambda nid, cui, r: {"nid":nid,"cui":cui,"mt":safe_str(r[3],50),"term":safe_str(r[5],200),
                             "src":"Drug_database/meddra_all_se","ts":NOW_TS},
        "DRUG_CAUSES_SE"
    )
    del doc3, rows_se; gc.collect()

    log.info(f"  DRUG_TREATS:{n_treats:,} | DRUG_CAUSES:{n_causes:,} | DRUG_CAUSES_SE:{n_se:,}")
    return n_treats, n_causes, n_se


# ── Phase 11: HAS_CHUNK edges ─────────────────────────────────────────────────
def build_has_chunk_edges() -> int:
    """Build 2.29M HAS_CHUNK edges via parquet COPY FROM (instant, zero memory overhead)."""
    log.info("Phase 11: Building HAS_CHUNK edges via COPY FROM parquet ...")
    
    if not HAS_CHUNK_PAR.exists():
        log.info("  Generating has_chunk_edges.parquet ...")
        imap = pq.read_table(IDMAP_PAR, columns=["chunk_id", "document_id"])
        n_rows = len(imap)
        tbl = pa.table({
            "from": imap["document_id"],
            "to":   imap["chunk_id"],
            "source_doc": imap["document_id"],
            "processed_at": [NOW_TS] * n_rows
        })
        pq.write_table(tbl, HAS_CHUNK_PAR, compression="snappy")
        del imap, tbl; gc.collect()

    db, conn = open_db()
    
    # Ensure fresh load if partial rows exist
    try:
        c = conn.execute("MATCH ()-[r:HAS_CHUNK]->() RETURN count(r) AS c").get_as_df().iloc[0,0]
    except Exception:
        c = 0

    if c < 2294038:
        log.info(f"  Existing HAS_CHUNK edges: {c:,}. Re-creating HAS_CHUNK table for clean COPY FROM...")
        conn.execute("DROP TABLE HAS_CHUNK")
        conn.execute("CREATE REL TABLE HAS_CHUNK (FROM Document TO Chunk, source_doc STRING, processed_at STRING)")
        log.info(f"  Executing COPY HAS_CHUNK FROM '{HAS_CHUNK_PAR}' ...")
        t0 = time.time()
        conn.execute(f"COPY HAS_CHUNK FROM '{HAS_CHUNK_PAR}'")
        elapsed = time.time() - t0
        c = conn.execute("MATCH ()-[r:HAS_CHUNK]->() RETURN count(r) AS c").get_as_df().iloc[0,0]
        log.info(f"  COPY HAS_CHUNK COMPLETE: {c:,} edges loaded in {elapsed:.2f}s!")

    close_db(db, conn)
    return c


# ── Phase 12: DISEASE_MAPPED_TO edges ────────────────────────────────────────
def build_disease_mapped_edges() -> int:
    """Build DISEASE_MAPPED_TO edges with reconnect."""
    log.info("Phase 12: Building DISEASE_MAPPED_TO edges ...")
    db, conn = open_db()
    res = conn.execute("MATCH (d:Disease) RETURN d.disease_id").get_as_df()
    disease_ids = res["d.disease_id"].tolist() if "d.disease_id" in res.columns else []
    close_db(db, conn)
    n = 0; ops = 0
    db, conn = open_db()
    txn_begin(conn)
    for cui in disease_ids:
        try:
            conn.execute(
                "MATCH (d:Disease {disease_id:$cui}),(o:OntologyTerm {term_id:$cui}) "
                "CREATE (d)-[:DISEASE_MAPPED_TO {mapping_type:'UMLS_CUI', source_doc:'UMLS Output/META/MRCONSO', processed_at:$ts}]->(o)",
                {"cui":cui,"ts":NOW_TS})
            n += 1; ops += 1
        except Exception: pass
        if ops >= RECONNECT_INTERVAL:
            txn_commit(conn); close_db(db, conn)
            check_ram_guard()
            db, conn = open_db(); txn_begin(conn); ops = 0
    txn_commit(conn); close_db(db, conn)
    log.info(f"  DISEASE_MAPPED_TO: {n:,} edges")
    return n


# ── Phase 13: DOCUMENT_MENTIONS edges ────────────────────────────────────────
def build_document_mentions_edges() -> int:
    """Build DOCUMENT_MENTIONS edges with reconnect."""
    log.info("Phase 13: Building DOCUMENT_MENTIONS edges ...")
    db, conn = open_db()
    res = conn.execute("MATCH (d:Disease) RETURN d.disease_id, d.name").get_as_df()
    close_db(db, conn)
    if "d.disease_id" not in res.columns: return 0
    name_to_did = {name.lower(): did for did, name in zip(res["d.disease_id"].tolist(), res["d.name"].tolist()) if name}

    n = 0; ops = 0
    db, conn = open_db()
    txn_begin(conn)
    with open(MANIFEST) as f:
        for line in f:
            rec = json.loads(line)
            doc_id  = rec["document_id"]
            subpath = rec.get("subpath","").replace("_"," ").lower()
            for name, did in name_to_did.items():
                if name and name in subpath:
                    try:
                        conn.execute(
                            "MATCH (doc:Document {document_id:$doc}),(d:Disease {disease_id:$did}) "
                            "CREATE (doc)-[:DOCUMENT_MENTIONS {source_doc:$doc, processed_at:$ts}]->(d)",
                            {"doc":doc_id,"did":did,"ts":NOW_TS})
                        n += 1; ops += 1
                    except Exception: pass
                    if ops >= RECONNECT_INTERVAL:
                        txn_commit(conn); close_db(db, conn)
                        check_ram_guard()
                        db, conn = open_db(); txn_begin(conn); ops = 0
    txn_commit(conn); close_db(db, conn)
    log.info(f"  DOCUMENT_MENTIONS: {n:,} edges")
    return n


# ── Phase 14: LABTEST_RELATED_TO edges ───────────────────────────────────────
def build_labtest_edges() -> int:
    """Build LABTEST_RELATED_TO edges with reconnect."""
    log.info("Phase 14: Building LABTEST_RELATED_TO edges ...")
    db, conn = open_db()
    res_d = conn.execute("MATCH (d:Disease) RETURN d.disease_id, d.name").get_as_df()
    if "d.disease_id" not in res_d.columns:
        close_db(db, conn); return 0
    disease_by_name = {name: did for did, name in zip(res_d["d.disease_id"].tolist(), res_d["d.name"].tolist()) if name}

    res_l = conn.execute("MATCH (lt:LabTest) RETURN lt.lab_test_id, lt.category").get_as_df()
    close_db(db, conn)
    if "lt.lab_test_id" not in res_l.columns: return 0

    n = 0; ops = 0
    db, conn = open_db()
    txn_begin(conn)
    for lab_id, cat in zip(res_l["lt.lab_test_id"].tolist(), res_l["lt.category"].tolist()):
        for dname in LAB_CAT_DISEASE_MAP.get(cat, []):
            did = disease_by_name.get(dname)
            if not did: continue
            try:
                conn.execute(
                    "MATCH (lt:LabTest {lab_test_id:$lid}),(d:Disease {disease_id:$did}) "
                    "CREATE (lt)-[:LABTEST_RELATED_TO {relation_type:'diagnostic_marker', source_doc:'Lab_rev_data', processed_at:$ts}]->(d)",
                    {"lid":lab_id,"did":did,"ts":NOW_TS})
                n += 1; ops += 1
            except Exception: pass
            if ops >= RECONNECT_INTERVAL:
                txn_commit(conn); close_db(db, conn)
                check_ram_guard()
                db, conn = open_db(); txn_begin(conn); ops = 0
    txn_commit(conn); close_db(db, conn)
    log.info(f"  LABTEST_RELATED_TO: {n:,} edges")
    return n


# ── Phase 15: Report ──────────────────────────────────────────────────────────
def generate_report(conn, counts: dict) -> dict:
    log.info("Phase 15: Generating report ...")

    COUNT_Q = [
        ("OntologyTerm",      "MATCH (n:OntologyTerm) RETURN count(n) AS c"),
        ("Disease",           "MATCH (n:Disease) RETURN count(n) AS c"),
        ("Drug",              "MATCH (n:Drug) RETURN count(n) AS c"),
        ("LabTest",           "MATCH (n:LabTest) RETURN count(n) AS c"),
        ("Document",          "MATCH (n:Document) RETURN count(n) AS c"),
        ("Chunk",             "MATCH (n:Chunk) RETURN count(n) AS c"),
        ("IS_A",              "MATCH ()-[r:IS_A]->() RETURN count(r) AS c"),
        ("RELATED_TO",        "MATCH ()-[r:RELATED_TO]->() RETURN count(r) AS c"),
        ("DRUG_TREATS",       "MATCH ()-[r:DRUG_TREATS]->() RETURN count(r) AS c"),
        ("DRUG_CAUSES",       "MATCH ()-[r:DRUG_CAUSES]->() RETURN count(r) AS c"),
        ("DRUG_CAUSES_SE",    "MATCH ()-[r:DRUG_CAUSES_SE]->() RETURN count(r) AS c"),
        ("HAS_CHUNK",         "MATCH ()-[r:HAS_CHUNK]->() RETURN count(r) AS c"),
        ("DISEASE_MAPPED_TO", "MATCH ()-[r:DISEASE_MAPPED_TO]->() RETURN count(r) AS c"),
        ("DOCUMENT_MENTIONS", "MATCH ()-[r:DOCUMENT_MENTIONS]->() RETURN count(r) AS c"),
        ("LABTEST_RELATED_TO","MATCH ()-[r:LABTEST_RELATED_TO]->() RETURN count(r) AS c"),
    ]

    SAMPLE_Q = [
        ("OntologyTerm", "MATCH (n:OntologyTerm) RETURN n.term_id, n.ontology, n.term, n.definition LIMIT 5"),
        ("Disease",      "MATCH (n:Disease) RETURN n.disease_id, n.name, n.url, n.definition LIMIT 5"),
        ("Drug",         "MATCH (n:Drug) RETURN n.node_id, n.name, n.drug_type, n.groups LIMIT 5"),
        ("LabTest",      "MATCH (n:LabTest) RETURN n.test_name, n.category, n.normal_low, n.critical_high, n.unit LIMIT 5"),
        ("Document",     "MATCH (n:Document) RETURN n.document_id, n.category, n.target LIMIT 5"),
    ]

    EDGE_Q = [
        ("IS_A",        "MATCH (a:OntologyTerm)-[r:IS_A]->(b:OntologyTerm) RETURN a.term, r.rel_type, b.term LIMIT 5"),
        ("DRUG_TREATS", "MATCH (d:Drug)-[r:DRUG_TREATS]->(dis:Disease) RETURN d.name, r.meddra_term, dis.name LIMIT 5"),
    ]

    print("\n" + "="*70)
    print("NODE / EDGE COUNTS")
    print("="*70)
    node_edge_counts = {}
    for label, q in COUNT_Q:
        try:
            df = conn.execute(q).get_as_df()
            val = int(df.iloc[0, 0]) if len(df) > 0 else 0
        except Exception as e:
            val = f"ERR:{e}"
        node_edge_counts[label] = val
        print(f"  {label:<25}: {val:>12,}" if isinstance(val, int) else f"  {label:<25}: {val}")

    print("\n" + "="*70)
    print("5-ROW NODE SAMPLES")
    print("="*70)
    for label, q in SAMPLE_Q:
        try:
            df = conn.execute(q).get_as_df()
            print(f"\n{label}:")
            print(df.to_string(index=False, max_colwidth=55))
        except Exception as e:
            print(f"  {label}: ERROR — {e}")

    print("\n" + "="*70)
    print("EDGE SAMPLES")
    print("="*70)
    for label, q in EDGE_Q:
        try:
            df = conn.execute(q).get_as_df()
            print(f"\n{label}:")
            print(df.to_string(index=False, max_colwidth=55))
        except Exception as e:
            print(f"  {label}: ERROR — {e}")

    # kuzu_db_v5 is a single file; add WAL size if present
    db_size_mb = DB_DIR.stat().st_size / 1024**2 if DB_DIR.exists() else 0
    wal_path = DB_DIR.parent / (DB_DIR.name + ".wal")
    if wal_path.exists():
        db_size_mb += wal_path.stat().st_size / 1024**2
    print(f"\nKùzu DB size: {db_size_mb:.1f} MB at {DB_DIR}")

    report = {
        "status": "COMPLETE",
        "build_time_s": counts.get("build_time_s"),
        "kuzu_db_path": str(DB_DIR),
        "kuzu_db_size_mb": round(db_size_mb, 1),
        "node_edge_counts": node_edge_counts,
        "processed_at": NOW_TS,
    }
    with open(REPORT_FILE, "w") as f:
        json.dump(report, f, indent=2)
    log.info(f"Report saved → {REPORT_FILE}")
    return report


# ── MAIN ──────────────────────────────────────────────────────────────────────
def main():
    t0 = time.time()
    log.info("=" * 60)
    log.info("MedGraphRAG Step 5: Kùzu Graph Build (v3 — reconnect-per-batch)")
    log.info("=" * 60)

    completed_phases = load_checkpoint()

    # Only clean DB if no checkpoint exists
    if not completed_phases and DB_DIR.exists():
        import shutil
        if DB_DIR.is_dir():
            shutil.rmtree(str(DB_DIR))
        else:
            DB_DIR.unlink()

    try:
        # ── Node phases: each opens/closes DB internally or via open_db()
        if "ddl" not in completed_phases:
            db, conn = open_db()
            run_ddl(conn)
            close_db(db, conn)
            save_checkpoint("ddl")

        disease_cuis = build_disease_cui_set()

        if "ontology_terms" not in completed_phases:
            def_dict = build_definition_dict(disease_cuis)
            db, conn = open_db()
            n_onto   = build_ontology_terms(conn, disease_cuis, def_dict)
            close_db(db, conn)
            del def_dict; gc.collect()
            save_checkpoint("ontology_terms")

        if "disease_nodes" not in completed_phases:
            def_dict = build_definition_dict(disease_cuis)
            db, conn = open_db()
            n_disease, mesh_to_cui = build_disease_nodes(conn, disease_cuis, def_dict)
            close_db(db, conn)
            del def_dict; gc.collect()
            save_checkpoint("disease_nodes")

        # Always build drug_id_map from source files (cheap, no Kùzu)
        drug_id_map = _load_drug_id_map()

        if "drug_nodes" not in completed_phases:
            n_drug = build_drug_nodes(drug_id_map)   # manages its own db/conn
            save_checkpoint("drug_nodes")

        if "labtest_nodes" not in completed_phases:
            db, conn = open_db()
            n_lab = build_labtest_nodes(conn)
            close_db(db, conn)
            save_checkpoint("labtest_nodes")

        if "document_nodes" not in completed_phases:
            db, conn = open_db()
            n_doc = build_document_nodes(conn)
            close_db(db, conn)
            save_checkpoint("document_nodes")

        if "chunk_nodes" not in completed_phases:
            db, conn = open_db()
            n_chunk = build_chunk_parquet_and_copy(conn)
            close_db(db, conn)
            save_checkpoint("chunk_nodes")

        # ── Edge phases: each manages its own db/conn with reconnect
        if "umls_edges" not in completed_phases:
            n_isa, n_rel = build_umls_edges(disease_cuis)  # manages own conn
            save_checkpoint("umls_edges")
        del disease_cuis; gc.collect()

        if "drug_edges" not in completed_phases:
            n_treats, n_causes, n_se = build_drug_edges(drug_id_map)  # manages own conn
            save_checkpoint("drug_edges")

        if "has_chunk_edges" not in completed_phases:
            n_has_chunk = build_has_chunk_edges()  # manages own conn
            save_checkpoint("has_chunk_edges")

        if "disease_mapped_edges" not in completed_phases:
            n_mapped = build_disease_mapped_edges()  # manages own conn
            save_checkpoint("disease_mapped_edges")

        if "document_mentions_edges" not in completed_phases:
            n_mentions = build_document_mentions_edges()  # manages own conn
            save_checkpoint("document_mentions_edges")

        if "labtest_edges" not in completed_phases:
            n_labrel = build_labtest_edges()  # manages own conn
            save_checkpoint("labtest_edges")

        # ── Report
        elapsed = time.time() - t0
        counts = {"build_time_s": round(elapsed, 1)}
        db, conn = open_db()
        generate_report(conn, counts)
        close_db(db, conn)

        log.info("=" * 60)
        log.info(f"GRAPH BUILD COMPLETE in {elapsed/60:.1f} min")
        log.info("=" * 60)

    except Exception:
        log.error(traceback.format_exc())
        raise


if __name__ == "__main__":
    main()
