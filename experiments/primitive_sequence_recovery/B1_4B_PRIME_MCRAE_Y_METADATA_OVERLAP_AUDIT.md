# B1.4b′ — McRae Y Metadata Overlap Audit

**Status:** Metadata overlap audit (docs-only). **Concept labels only. No Y matrix, no decoder, no F-3 scoring,
no freeze.**
**Governed by:** `B1_4B_PRIME_Y_ACQUISITION_AND_OVERLAP_AUDIT_PLAN.md` (`e1cefc0`),
`B1_4B_PRIME_CSLB_Y_METADATA_OVERLAP_AUDIT.md` (`9081411`), `stage_a_prime_coverage.py` (`8d4b097`, read-only).
**No meaning validated. Original B1.4b remains blocked. Track B remains blocked. Structure, not validated
meaning.**

---

## 1. Purpose

This audit was approved to acquire **McRae concept labels / metadata only** and test whether they overlap
sufficiently with **Stage A′-decomposable concepts** to make McRae an eligible `Y` source for a future B1.4b′.
It builds no `Y` matrix, trains no decoder, and scores nothing. Its single deliverable is an eligibility
decision on McRae coverage overlap.

---

## 2. Source acquisition

- **Source name:** McRae **semantic feature production norms**.
- **Version / date:** McRae, Cree, Seidenberg & McNorgan (2005), *Behavior Research Methods*, 37(4), 547–559.
  541 concrete English nouns; ~2,526 features.
- **Official distribution:** historically via `www.psychonomic.org/archive` (Psychonomic Society archive) and
  the journal supplementary; McRae-lab Excel files.
- **License / access status:** **Not retrievable in this environment.** The authoritative hosts are blocked by
  the environment's outbound network policy: the Springer article, PMC, and the aggregator page
  (aginglexicon.github.io) all returned **HTTP 403** via the proxy; `osf.io` was unreachable (000). The only
  reachable external channel is `raw.githubusercontent.com` (200), which for McRae exposes **third-party
  mirrors of unclear provenance/license only** — not the authoritative file.
- **Citation / provenance:** McRae, K., Cree, G. S., Seidenberg, M. S., & McNorgan, C. (2005). *Semantic
  feature production norms for a large set of living and nonliving things.* Behavior Research Methods, 37(4),
  547–559.
- **Only concept labels used?** **No concept labels could be obtained** from an authoritative source. Nothing
  beyond published bibliographic metadata was retrieved; **no concept names, no feature values** were acquired.

Published size (**ESTIMATED from the literature — NOT obtained/verified here**): 541 concepts, ~2,526 features.
Cited for context only; **not** used to compute any overlap.

---

## 3. Concept-list handling

- **How labels were normalized:** **N/A — no authoritative labels were obtained**, so none were normalized.
- **How multiword concepts were treated:** N/A (no list to process).
- **Ambiguous labels excluded or retained:** N/A (no list to process).
- **`Y` values / matrix:** **none constructed.** No feature values were accessed. **No fabricated or
  placeholder concept list was created**, and **no unauthoritative GitHub mirror was scraped** (explicitly
  prohibited; provenance/faithfulness to the exact 541-concept list is unverifiable). Both are refused.

---

## 4. Stage A′ overlap method

- **Intended method (defined, NOT executed):** normalize each McRae concept label → run it through the existing
  Stage A′ module (`stage_a_prime_coverage.normalize`, `A_PRIME_EN`, **read-only**) → count `flag == full`
  (0 unsupported units) → tally usable features.
- **Not executed:** the Stage A′ decomposition was **not run on any McRae concept**, because **no authoritative
  McRae concept labels were obtained**. Running it on a fabricated or unverified-mirror list would be
  meaningless and against the stated constraints, so it was not done.
- The Stage A′ module was **not modified** and its tests remain **11/11 PASS**; it was fed no real McRae input.

---

## 5. Eligibility threshold

Pre-registered requirement: **≥ 100 usable Stage A′-decomposable McRae concepts** for B1.4b′ prep. This
threshold **cannot be evaluated**, because the McRae concept list was not available (from an authoritative
source) to count against.

---

## 6. Results

| Quantity | Value |
|---|---|
| McRae concepts obtained (authoritative) | **0** (authoritative hosts proxy-blocked; only unclear-provenance mirrors reachable) |
| Concepts normalized | 0 (nothing to normalize) |
| Fully decomposable by Stage A′ | **uncomputable** (no concept list) |
| Unsupported-unit failures | uncomputable |
| Exclusions | uncomputable |
| Retained concepts | uncomputable |
| ≥100 threshold met? | **cannot be determined** |

Published estimate (541 concepts) is **not** a count obtained here and is **not** used as an overlap number.

**Environment note:** this is an **egress limitation**, not a claim that the data does not exist. McRae (2005)
is a real, widely-used dataset; it is simply not retrievable from an authoritative source in this sandbox
(authoritative hosts return 403/000; only unauthoritative mirrors are reachable, which are barred by the task
constraints).

---

## 7. Decision

**`Y_SOURCE_METADATA_UNAVAILABLE`.**

The authoritative McRae concept list could not be acquired in this environment (Springer / PMC / aggregator all
proxy-403; `osf.io` unreachable; only unclear-provenance GitHub mirrors reachable, which are prohibited). No
concept labels were obtained, so the Stage A′ overlap count and the ≥100 eligibility threshold are
**uncomputable**. No fabricated list and no unauthoritative mirror were used. (Not
`Y_SOURCE_OVERLAP_AUDIT_PASS` / `Y_SOURCE_COVERAGE_TOO_THIN` — both require a real overlap count, which does not
exist; not `Y_SOURCE_REJECTED_LEAKAGE_RISK` — McRae is human-produced, not gloss-derived; not
`Y_SOURCE_OVERLAP_INCONCLUSIVE` — the cause is specifically unavailability, not ambiguity.)

This is the **second** candidate (after CSLB `9081411`) to return `Y_SOURCE_METADATA_UNAVAILABLE` for the same
underlying reason: the sandbox's network policy blocks the authoritative dataset hosts.

---

## 8. Next gate

- **Preferred (most robust):** a human **operator provides an authoritative concept-list file** — from their
  own licensed/official download of **CSLB** (preferred source) or **McRae** — placed into the repo. This audit
  is then re-run to compute the real Stage A′ overlap. Requires separate approval to import the file. Because
  two egress attempts have now failed identically, operator-provided files are the reliable path.
- **Alternative (separate approval):** attempt **Binder (2016)** metadata next — but note the same egress
  policy will likely block its authoritative host too; expect a probable third `Y_SOURCE_METADATA_UNAVAILABLE`
  unless it is reachable.
- **No semantic run follows automatically.** Even a subsequent `Y_SOURCE_OVERLAP_AUDIT_PASS` would only unlock
  freeze-package **planning**, never an evidence run without further explicit approval. The expected downstream
  outcome remains `F_COLLAPSES_TO_PHONOLOGY → ⊥` regardless (Stage A′ is phonology-derived).

**Sources consulted (metadata only):**
[McRae et al. 2005 (Springer BF03192726)](https://link.springer.com/article/10.3758/BF03192726) ·
[PubMed 16629288](https://pubmed.ncbi.nlm.nih.gov/16629288/) ·
[The Aging Lexicon — Norms](https://aginglexicon.github.io/menu/norms.html) ·
[Semantic Scholar record](https://www.semanticscholar.org/paper/Semantic-feature-production-norms-for-a-large-set-McRae-Cree/b2c04cc369b8f08f399d5fb95ddc884d52cfebd2)

---

## 9. Boundary statement

> McRae Y metadata overlap audit completed. Concept labels only. No Y matrix created. No semantic validation
> performed. No evidence freeze declared. Original B1.4b remains blocked. Track B remains blocked. Structure,
> not validated meaning.
