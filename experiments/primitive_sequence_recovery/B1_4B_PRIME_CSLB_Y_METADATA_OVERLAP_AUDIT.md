# B1.4b′ — CSLB Y Metadata Overlap Audit

**Status:** Metadata overlap audit (docs-only). **Concept labels only. No Y matrix, no decoder, no F-3 scoring,
no freeze.**
**Governed by:** `B1_4B_PRIME_Y_ACQUISITION_AND_OVERLAP_AUDIT_PLAN.md` (`e1cefc0`),
`B1_4B_PRIME_LAYER3_DECODER_Y_DESIGN.md`, `stage_a_prime_coverage.py` (`8d4b097`, read-only).
**No meaning validated. Original B1.4b remains blocked. Track B remains blocked. Structure, not validated
meaning.**

---

## 1. Purpose

This audit was approved to acquire **CSLB concept labels / metadata only** and test whether they overlap
sufficiently with **Stage A′-decomposable concepts** to make CSLB an eligible `Y` source for a future B1.4b′.
It builds no `Y` matrix, trains no decoder, and scores nothing. Its single deliverable is an
eligibility decision on CSLB coverage overlap.

---

## 2. Source acquisition

- **Source name:** CSLB (Centre for Speech, Language and the Brain) **concept property norms**.
- **Version / date:** Devereux, Tyler, Geertzen & Randall (2014), *Behavior Research Methods*.
- **Official distribution:** `https://cslb.psychol.cam.ac.uk/propnorms`.
- **License / access status:** **Registration / agreement-gated.** In this environment the official portal
  returned **HTTP 403 Forbidden**, and the open-access article page (PMC4237904) also returned **HTTP 403**;
  neither exposed a directly-retrievable concept-list file. The dataset is obtainable only by completing the
  CSLB access agreement on the Cambridge portal — an **operator action** not performable here.
- **Citation / provenance:** Devereux, B. J., Tyler, L. K., Geertzen, J., & Randall, B. (2014). *The Centre for
  Speech, Language and the Brain (CSLB) concept property norms.* Behavior Research Methods, 46(4), 1119–1127.
- **Only concept labels used?** **No concept labels could be obtained.** Nothing beyond published bibliographic
  metadata was retrieved; **no concept names, no attribute values** were acquired.

Published dataset sizes (**ESTIMATED from the literature — NOT obtained/verified here**): ~638 concepts,
~5,929 features. These are cited for context only and were **not** used to compute any overlap.

---

## 3. Concept-list handling

- **How labels were normalized:** **N/A — no labels were obtained**, so none were normalized.
- **How multiword concepts were treated:** N/A (no list to process).
- **Ambiguous labels excluded or retained:** N/A (no list to process).
- **`Y` values / matrix:** **none constructed.** No attribute values were accessed. **No fabricated or
  placeholder concept list was created** — inventing concepts to force an overlap count would be fabrication and
  is explicitly refused.

---

## 4. Stage A′ overlap method

- **Intended method (defined, NOT executed):** normalize each CSLB concept label → run it through the existing
  Stage A′ module (`stage_a_prime_coverage.normalize`, `A_PRIME_EN`, **read-only**) → count `flag == full`
  (0 unsupported units) → tally usable attributes.
- **Not executed:** the Stage A′ decomposition was **not run on any CSLB concept**, because **no CSLB concept
  labels were obtained**. Running it on an invented list would be meaningless and dishonest, so it was not done.
- The Stage A′ module was **not modified** and its tests remain **11/11 PASS**; it was simply not fed any real
  CSLB input.

---

## 5. Eligibility threshold

Pre-registered requirement: **≥ 100 usable Stage A′-decomposable CSLB concepts** for B1.4b′ prep. This
threshold **cannot be evaluated**, because the CSLB concept list was not available to count against.

---

## 6. Results

| Quantity | Value |
|---|---|
| CSLB concepts obtained | **0** (portal + open-access both 403; registration-gated) |
| Concepts normalized | 0 (nothing to normalize) |
| Fully decomposable by Stage A′ | **uncomputable** (no concept list) |
| Unsupported-unit failures | uncomputable |
| Exclusions | uncomputable |
| Retained concepts | uncomputable |
| ≥100 threshold met? | **cannot be determined** |

Published estimate (~638 concepts) is **not** a count obtained here and is **not** used as an overlap number.

---

## 7. Decision

**`Y_SOURCE_METADATA_UNAVAILABLE`.**

The CSLB concept list could not be acquired in this environment (official portal and open-access article both
returned HTTP 403; the dataset is registration/agreement-gated). No concept labels were obtained, so the
Stage A′ overlap count and the ≥100 eligibility threshold are **uncomputable**. No fabricated list was
substituted. (Not `Y_SOURCE_OVERLAP_AUDIT_PASS` / `Y_SOURCE_COVERAGE_TOO_THIN` — both require an actual overlap
count, which does not exist; not `Y_SOURCE_REJECTED_LEAKAGE_RISK` — CSLB is human-produced, not gloss-derived;
not `Y_SOURCE_OVERLAP_INCONCLUSIVE` — the cause is specifically unavailability, not ambiguity.)

---

## 8. Next gate

- **Preferred:** a human **operator completes the CSLB access agreement** on the Cambridge portal and places the
  **concept-list file (labels + attribute schema only, no obligation to import values yet)** into the repo;
  this audit is then re-run to compute the real Stage A′ overlap. Requires separate approval to import the file.
- **Alternative (separate approval):** attempt **McRae feature-production norms** metadata next — it is more
  commonly redistributed openly, so its concept list may be retrievable where CSLB's is gated.
- **No semantic run follows automatically.** Even a subsequent `Y_SOURCE_OVERLAP_AUDIT_PASS` would only unlock
  freeze-package **planning**, never an evidence run without further explicit approval. The expected downstream
  outcome remains `F_COLLAPSES_TO_PHONOLOGY → ⊥` regardless (Stage A′ is phonology-derived).

**Sources consulted (metadata only):**
[CSLB propnorms portal](https://cslb.psychol.cam.ac.uk/propnorms) ·
[Devereux et al. 2014 (PMC4237904)](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC4237904/) ·
[Springer / Behavior Research Methods](https://link.springer.com/article/10.3758/s13428-013-0420-4) ·
[PubMed 24356992](https://pubmed.ncbi.nlm.nih.gov/24356992/)

---

## 9. Boundary statement

> CSLB Y metadata overlap audit completed. Concept labels only. No Y matrix created. No semantic validation
> performed. No evidence freeze declared. Original B1.4b remains blocked. Track B remains blocked. Structure,
> not validated meaning.
