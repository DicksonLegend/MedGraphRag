# Compute, Latency, and Cost Comparison Table

> **Note on Confidence Intervals & Metrics:** Retrieval rows report median latency with 95% bootstrap confidence intervals (1,000 resamples, seed 42). End-to-end rows report medians from formal ablation artifacts. Queries/hour is the primary throughput metric; Acc(ans) per CPU-process-second is reported as a secondary efficiency metric.

| Method / Mode | Stage | Device | Median Lat (ms) [95% CI] | IQR (ms) | Peak RSS | VRAM | LLM Calls | CPU-s | Queries/Hr | Acc(Ans) | WAR | Refusal | Acc / CPU-process-s |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Retrieval Baselines (N=50, k=10)** | | | | | | | | | | | | | |
| BM25-RAG (pool-200) | Retrieval | CPU | 55.1 [52.74, 56.47] | 8.2 | 3002 MB | 0 MB | 0 | 0.0551s | 65,335.8 | --- | --- | --- | --- |
| Dense-RAG | Retrieval | CPU | 30.1 [29.36, 30.98] | 3.4 | 3002 MB | 0 MB | 0 | 0.0301s | 119,601.3 | --- | --- | --- | --- |
| Hybrid-RRF | Retrieval | CPU | 55.4 [53.47, 56.9] | 7.6 | 3002 MB | 0 MB | 0 | 0.0554s | 64,981.9 | --- | --- | --- | --- |
| Graph-Only | Retrieval | CPU | 278.9 [270.27, 296.02] | 55.0 | 3002 MB | 0 MB | 0 | 0.2789s | 12,907.9 | --- | --- | --- | --- |
| MedGraphRAG (ours) | Retrieval | CPU | 455.7 [388.37, 495.82] | 179.7 | 3002 MB | 0 MB | 0 | 0.4557s | 7,899.9 | --- | --- | --- | --- |
| **End-to-End Generation & Verification (N=50, T=0.0)** | | | | | | | | | | | | | |
| M1: Evidence-Only Verification (beta=1.0) | End-to-End | GPU+CPU | 15166.3 *(reported)* | 3210.5 | 8950 MB | 4710 MB | 2 | 1.66s | 237.4 | 66.7% | 2.0% | 98.0% | **40.16** |
| M2: Graph-Only Verification (beta=0.0) | End-to-End | GPU+CPU | 8591.5 *(reported)* | 2140.2 | 8950 MB | 4710 MB | 1 | 0.76s | 419.0 | 56.2% | 42.0% | 8.0% | **74.01** |
| M3: Combined Verification (beta=0.7) | End-to-End | GPU+CPU | 15120.0 *(reported)* | 3190.8 | 8950 MB | 4710 MB | 2 | 1.96s | 238.1 | 50.0% | 4.0% | 96.0% | **25.51** |
| M4: Hybrid Reranker + Combined Verification (beta=0.7, gamma=0.15) | End-to-End | GPU+CPU | 15249.9 *(reported)* | 3250.0 | 8950 MB | 4710 MB | 2 | 1.99s | 236.1 | 60.0% | 4.0% | 94.0% | **30.15** |

### Methodological Notes & Hygiene Disclosures
1. **Scale N=500 Latency Status:** Pre-fix watchdog/restart-contaminated; excluded from final compute comparison; to be replaced after resumed N=500 run.
2. **BM25 Median vs Mean Discrepancy:** In `step17_baselines.json`, BM25-RAG (pool-200) mean latency was reported at 704.8 ms due to occasional text-loading/garbage-collection tail outliers. This table reports median (55.1 ms) and IQR (8.2 ms), which are robust to outliers and reflect steady-state throughput.
3. **Cost-of-Safety & Reranking:** Hybrid reranking improves combined-mode Acc(ans) from M3=50.0% to M4=60.0% while preserving WAR=4.0%. Compared with M1, M4 trades lower refusal/greater graph corroboration for slightly lower answered accuracy at N=50; N=500 will determine stability.
4. **Cold-Start Amortization:** One-time pipeline loading takes **18.66s**, amortizing to just **0.037s/query at N=500** and **0.0019s/query in production (N=10,000)**.