# Phase 2 — Graded Relevance Rubric (IR evaluation, single scale for both assessors)

Applies to every (query, rank) row in `evaluations/phase2_grading_sheet.tsv`.
Grade ONLY on this scale: **1.0 / 0.4 / 0.0** (these exact values feed Cohen's Kappa and nDCG).

Judge the CHUNK TEXT against the QUERY — not against other chunks, not against what you
know the "correct" MedQA answer option is. A chunk that would help a clinician answer the
question scores ≥ 0.4; a chunk that essentially IS the answer scores 1.0.

---

## 1.0 — Directly answers
The chunk contains the exact clinical recommendation, diagnostic criterion, threshold,
dose, or direct answer to what the query asks.

**Anchors (real corpus rows):**
- Query P04/Q-type *"…open reduction and internal fixation of a left femur fracture…"*
  → chunk `Medical_books/MedQA/textbooks/en/Pediatrics_Nelson__c1274`: *"fixation if they have one of the following fractures: Displaced epiphyseal fractures … Open fractures Unstable fractures"* — states which fractures require fixation ⇒ **1.0**.
- A guideline chunk reading *"offer an ACE inhibitor as initial therapy for adults under 55"*
  offered against query *"ACE inhibitor hypertension treatment first line"* ⇒ **1.0**
  (this is the canonical first-line-treatment statement the query requests).
- Any chunk giving the numeric answer asked for (e.g., a lab handbook row with the exact
  reference interval when the query asks to interpret that analyte) ⇒ **1.0**.

## 0.4 — Partially relevant
Same disease / drug / anatomical system / clinical topic, genuinely related, but the chunk
does NOT contain the direct answer (background, epidemiology, an adjacent concept, a
neighbouring case, or only a fragment such as an order code).

**Anchors (real corpus rows):**
- Same P04 query → chunk `Lab_rev_data/Loinc_2.82/AccessoryFiles/ImagingDocuments/ImagingDocumentCodes__row191`:
  *"LOINC_NUM: 103398-4; LONG_COMMON_NAME: Portable XR Femur - right Single view."* — correct
  body part & modality, zero management content ⇒ **0.4**.
- Query *"A 21-year-old male … fatigue …"* (Q1) → chunk `Medical_books/MedQA/questions/US/train__c2955`:
  a different MedQA vignette (*"28-year-old … intermittent abdominal pain … constipation and diarrhea"*).
  Right genre/system-adjacent, wrong case ⇒ **0.4** (grade 0.0 only if entirely different topic).
- Query *"troponin elevation myocardial infarction diagnosis"* → a sepsis/SIRS abstract
  mentioning troponin only in passing ⇒ **0.4** at most (topic overlap without answering).

## 0.0 — Irrelevant
Wrong disease/drug/system, off-topic, or boilerplate/noise regardless of any keyword overlap.

**Anchors (real corpus rows):**
- Q1 (fatigue vignette) → chunk `Clinical_practice_guidlines/CDC_Clinical_guidlines/CDC/PDFs/Tuberculosis/mm6011__c2`:
  *"Deputy Director … MMWR Editorial and Production Staff Ronald L. Moolen…"* — pure front-matter
  boilerplate ⇒ **0.0**.
- Q5 (melena/GI bleed) → chunk `…/ad323__c47`: a page of dot-leader demographic tables
  (*"6,841 2,386 2,033 1,282 Under 18 years…"*) — statistical table noise ⇒ **0.0**.
- Q3 (postcoital bleeding) → natality/birth-rate tables (`nvsr73-02__c7`) ⇒ **0.0**
  (keyword "women" hit only).

---

## Edge rules (agree on these before grading)
1. **Boilerplate rule:** title pages, editorial boards, author lists, form templates,
   dot-leader tables ⇒ 0.0 even if the document's parent topic matches the query.
2. **Answer-option leakage:** MedQA chunks containing OTHER cases' questions/answers are
   ≤ 0.4; they become 1.0 only if the embedded case is essentially the same question.
3. **Numeric-answer rule:** if the query asks for a threshold/dose and the chunk states it,
   that is 1.0 even if surrounding prose is thin.
4. **Multi-part chunks:** grade the dominant content of the chunk, not its best sentence.
5. When torn between two grades, choose the LOWER one; log the row ID in your notes so the
   adjudication pass can revisit it.
