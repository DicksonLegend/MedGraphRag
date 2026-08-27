# Compute, Latency, and Cost Comparison Table

> **Note on Confidence Intervals & Metrics:** Retrieval rows report median latency with 95% bootstrap confidence intervals (1,000 resamples, seed 42). End-to-end Stage B rows report primary $N=500$ evaluation performance at the **Safe Operating Threshold** (lowest $\tau$ per mode strictly satisfying $\text{WAR} \le 9.5\%$). Ungated accuracy ceilings and pilot references ($N=50$) are reported in supplementary sections.

## 1. Primary Benchmark: Scaled $N=500$ at Safe Operating Threshold (GPU, $T=0.0$, Seed 42)

| Pipeline Mode | Operating $\tau$ | Median Lat (ms) | $\text{Acc}(\text{all})$ | $\text{Acc}(\text{ans})$ | $\text{WAR}$ ($\le 9.5\%$) | Refusal Rate | Answered / Total |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **M1: Evidence-Only** ($\beta=1.0$) | $\tau=0.43$ | 12611.2 | 9.6% | 50.53% | 9.4% | 81.0% | 95/500 |
| **M2: Graph-Only** ($\beta=0.0$) | $\tau=0.80$ | 4083.4 | 12.4% | 60.78% | 8.0% | 79.6% | 102/500 |
| **M3: Combined Verification** ($\beta=0.7, \text{RRF}$) | $\tau=0.47$ | 12493.2 | 9.8% | 52.13% | 9.0% | 81.2% | 94/500 |
| **M4: Hybrid Rerank + Combined** ($\beta=0.7, \gamma=0.15$) | $\tau=0.46$ | 12667.0 | **10.0%** | **51.55%** | **9.4%** | 80.6% | **97/500** |

### Secondary Operating Points (Default $\tau=0.50$)
| Pipeline Mode | Operating $\tau$ | $\text{Acc}(\text{all})$ | $\text{Acc}(\text{ans})$ | $\text{WAR}$ | Refusal Rate | Answered / Total |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **M1: Evidence-Only** | $\tau=0.50$ | 7.8% | 51.32% | 7.4% | 84.8% | 76/500 |
| **M2: Graph-Only** | $\tau=0.50$ | 51.8% | 55.7% | 41.2% | 7.0% | 465/500 |
| **M3: Combined Verification** | $\tau=0.50$ | 8.2% | 48.81% | 8.6% | 83.2% | 84/500 |
| **M4: Hybrid Rerank + Combined** | $\tau=0.50$ | 8.8% | 53.01% | 7.8% | 83.4% | 83/500 |

### Unhedged Accuracy Ceiling (NOT a Safe Operating Point — For Reference Only)
| Pipeline Mode | Ceiling $\text{Acc}(\text{all})$ | Ceiling $\text{Acc}(\text{ans})$ | Ceiling $\text{WAR}$ | Refusal Rate |
| :--- | :---: | :---: | :---: | :---: |
| **M1: Evidence-Only** | 49.4% | 53.23% | 43.4% | 7.2% |
| **M2: Graph-Only** | 54.8% | 55.13% | 44.6% | 0.6% |
| **M3: Combined Verification** | 50.2% | 54.09% | 42.6% | 7.2% |
| **M4: Hybrid Rerank + Combined** | 48.6% | 52.48% | 44.0% | 7.4% |

---

## 2. Matched-$\tau$ Ablation Comparison (Unrewritten vs. Rewritten at Identical Operating Thresholds)

| Mode | Threshold $\tau$ | Unrewritten $\text{Acc}(\text{all})$ | Rewritten $\text{Acc}(\text{all})$ | $\Delta \text{Acc}(\text{all})$ | Unrewritten $\text{WAR}$ | Rewritten $\text{WAR}$ | $\Delta \text{WAR}$ |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **M1: Evidence-Only** | $\tau=0.40$ | 3.6% | 9.6% | **+6.00%** | 3.4% | 10.2% | +6.80% |
| | $\tau=0.45$ | 3.6% | 9.6% | **+6.00%** | 3.4% | 9.2% | +5.80% |
| | $\tau=0.50$ | 3.6% | 7.8% | **+4.20%** | 3.4% | 7.4% | +4.00% |
| **M2: Graph-Only** | $\tau=0.40$ | 50.2% | 52.4% | **+2.20%** | 38.2% | 41.2% | +3.00% |
| | $\tau=0.45$ | 50.2% | 52.4% | **+2.20%** | 38.2% | 41.2% | +3.00% |
| | $\tau=0.50$ | 50.2% | 51.8% | **+1.60%** | 38.2% | 41.2% | +3.00% |
| **M3: Combined** | $\tau=0.40$ | 5.0% | 12.4% | **+7.40%** | 4.0% | 10.8% | +6.80% |
| | $\tau=0.45$ | 5.0% | 10.8% | **+5.80%** | 4.0% | 10.2% | +6.20% |
| | $\tau=0.50$ | 5.0% | 8.2% | **+3.20%** | 4.0% | 8.6% | +4.60% |
| **M4: Hybrid Rerank** | $\tau=0.40$ | 5.4% | 12.2% | **+6.80%** | 4.0% | 10.0% | +6.00% |
| | $\tau=0.45$ | 5.4% | 10.0% | **+4.60%** | 4.0% | 9.6% | +5.60% |
| | $\tau=0.50$ | 5.4% | 8.8% | **+3.40%** | 4.0% | 7.8% | +3.80% |

---

## 3. Pilot Reference: Initial $N=50$ Baseline & Pilot

| Method / Mode | Stage | Device | Median Lat (ms) [95% CI] | Peak RSS | VRAM | LLM Calls | Acc(Ans) | WAR | Refusal |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Retrieval Baselines ($N=50, k=10$)** | | | | | | | | | |
| BM25-RAG (pool-200) | Retrieval | CPU | 55.1 [52.74, 56.47] | 3002 MB | 0 MB | 0 | --- | --- | --- |
| Dense-RAG | Retrieval | CPU | 30.1 [29.36, 30.98] | 3002 MB | 0 MB | 0 | --- | --- | --- |
| Hybrid-RRF | Retrieval | CPU | 55.4 [53.47, 56.90] | 3002 MB | 0 MB | 0 | --- | --- | --- |
| Graph-Only | Retrieval | CPU | 278.9 [270.27, 296.02] | 3002 MB | 0 MB | 0 | --- | --- | --- |
| MedGraphRAG (ours) | Retrieval | CPU | 455.7 [388.37, 495.82] | 3002 MB | 0 MB | 0 | --- | --- | --- |
| **Generation Pilot ($N=50$, With Query Rewriter)** | | | | | | | | | |
| M3: Combined Verification ($\beta=0.7$) | End-to-End | GPU | 13009.6 | 3200 MB | 4710 MB | 2 | 87.5% | 2.0% | 84.0% |
| M4: Hybrid Rerank ($\beta=0.7, \gamma=0.15$) | End-to-End | GPU | 13377.7 | 3200 MB | 4710 MB | 2 | 85.7% | 2.0% | 86.0% |

### Methodological Notes & Device Invariance
1. **Device Invariance:** Device-invariance was proven pre-rewrite with 100.0% exact match between GPU and CPU runs on identical prompts. The Qwen2.5-7B query rewriter is deterministic ($T=0.0$).
2. **Cold-Start Amortization:** One-time pipeline loading takes **18.66s**, amortizing to just **0.037s/query at N=500** and **0.0019s/query in production (N=10,000)**.
