# DECIDE-AI Applicability Mapping — MedGateRAG

**Reference:** Vasey et al. (2022). *DECIDE-AI: New reporting guidance for
clinical trials evaluating artificial intelligence interventions.*
Nature Medicine 28, 924–933. doi:10.1038/s41591-022-01772-9

**Assessment date:** 2026-09-02
**Assessors:** MedGateRAG development team
**System:** MedGateRAG v2.0.0 — offline hybrid GraphRAG clinical decision support

---

## DECIDE-AI Applicability Checklist

DECIDE-AI applies to AI systems evaluated in clinical settings via prospective
studies with human participants. For each item, we record applicability and the
rationale.

| Item | DECIDE-AI Criterion | Applicable? | Rationale / Evidence |
|------|--------------------|-------------|----------------------|
| D1 | Clearly describe the AI system and its intended use | **Yes** | System described in §2 (Methods). Intended use: offline decision support for licensed clinicians. |
| D2 | Describe the context of care | **Partial** | No prospective clinical context yet; evaluation is retrospective (MedQA-US benchmark). Clinical translation roadmap (§4.2) describes intended context. |
| D3 | Describe the target population | **Partial** | Benchmark population (MedQA-US board-style questions). Real patient population not yet defined; Phase 2 pilot will establish IRB-approved protocol. |
| D4 | Report on the AI system integration in the care pathway | **N/A** | No integration study conducted; system is pre-deployment. Roadmap Phase 1 defines read-only, single-clinician deployment. |
| D5 | Report on adherence and any workarounds | **N/A** | No clinical trial conducted. |
| D6 | Describe early performance signals | **Yes** | WAR ≤ 10% constraint operationalises safety. M2 safe-operating-point: Acc(ans) = 60.8%, WAR = 8.0% at N=500. |
| D7 | Report on the safety event detection process | **Partial** | Structured refusals act as safety events. F1 cross-modal discrepancy guardrail (100% pass rate, 5/5 tests) provides safety alerting. No adverse event reporting system in place. |
| D8 | Describe unintended consequences | **Yes** | §4.3 (Limitations) documents: high refusal rate (79–84%), benchmark-vs-real-query gap, quantisation effects. |
| D9 | Describe interactions between humans and AI | **Partial** | Structured refusals designed for clinician oversight. Phase 2 will include audit log review. |
| D10 | Report on equity and fairness | **N/A** | MedQA-US demographic distribution not characterised. Phase 2 must include subgroup analysis. |
| D11 | Describe data used for in-context learning | **Yes** | FAISS index contents documented (Embedding_pipeline, UMLS corpus). Private user data isolated per AES-256-GCM encrypted store. |
| D12 | Report on explainability and interpretability | **Yes** | All responses include evidence citations [E#] linked to source chunks. Refusals cite missing evidence. |
| D13 | Describe deployment considerations | **Yes** | Consumer hardware spec (Ryzen 7 7840HS, RTX 3050 6GB) documented. Cold-start 18.7s, steady-state <500ms. |
| D14 | Report on monitoring and governance | **Partial** | Security audit (SECURITY_AUDIT.md) completed; 13/13 findings resolved. Ongoing monitoring plan not yet established. |

---

## Summary Judgement

MedGateRAG is **pre-deployment** and does not yet meet DECIDE-AI requirements
for a full prospective reporting statement. The items above mark where the
system is ready (D1, D6, D12, D13) and where gaps must be addressed before
clinical trial registration (D2, D3, D7, D10).

The Clinical Translation Roadmap (§4.2 of manuscript) provides the phased
pathway to meet all DECIDE-AI items by Phase 2.

---

## Action Items Before Phase 2 Pilot

- [ ] Define target patient population (inclusion/exclusion criteria)
- [ ] Establish IRB protocol (retrospective exemption + prospective approval)
- [ ] Implement adverse event / disagreement logging pipeline
- [ ] Conduct fairness audit across demographic subgroups in MedQA-US
- [ ] Appoint clinical governance committee for model updates
