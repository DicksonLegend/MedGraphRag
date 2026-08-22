#!/usr/bin/env python3
"""
Ingest negates_ontologyterm.parquet in batches with 1GB buffer pool.
"""
import kuzu
import pyarrow.parquet as pq
import pyarrow as pa
from pathlib import Path
import gc

INDEX_DIR = Path("/home/dicksone/Documents/MedGraphRag/index/global")
DB_DIR = INDEX_DIR / "kuzu_db_v5"
ONTO_PARQUET = INDEX_DIR / "negates_ontologyterm.parquet"

print("Reading negates_ontologyterm.parquet...")
tbl = pq.read_table(ONTO_PARQUET)
n_rows = len(tbl)
print(f"Total rows: {n_rows:,}")

# Split into 50k chunks and copy
batch_size = 50000
n_batches = (n_rows + batch_size - 1) // batch_size

for b in range(n_batches):
    start = b * batch_size
    end = min(n_rows, (b + 1) * batch_size)
    batch_tbl = tbl.slice(start, end - start)
    batch_path = INDEX_DIR / f"negates_onto_part_{b}.parquet"
    pq.write_table(batch_tbl, batch_path, compression="snappy")
    
    # Ingest with fresh connection per batch
    db = kuzu.Database(str(DB_DIR), buffer_pool_size=1024 * 1024 * 1024, max_num_threads=4)
    conn = kuzu.Connection(db)
    try:
        conn.execute(f"COPY NEGATES FROM '{batch_path}' (from='Chunk', to='OntologyTerm')")
        print(f"  Batch {b+1}/{n_batches} ({end-start:,} rows) copied successfully!")
    except Exception as e:
        print(f"  Batch {b+1} notice: {e}")
    finally:
        conn.close()
        db = None
        gc.collect()
        batch_path.unlink(missing_ok=True)

print("OntologyTerm ingestion complete!")
