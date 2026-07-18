# B1.4b′ — McRae-Derived Source Check (cardiffnlp/trait-concept-datasets)

**Status:** Source check (docs-only). **Concept labels only. No Y matrix, no decoder, no F-3 scoring, no
freeze. Source data NOT imported into the repo.**
**Governed by:** `B1_4B_PRIME_MCRAE_Y_METADATA_OVERLAP_AUDIT.md` (`478f373`),
`B1_4B_PRIME_Y_ACQUISITION_AND_OVERLAP_AUDIT_PLAN.md`, `stage_a_prime_coverage.py` (`8d4b097`, read-only).
**No meaning validated. Original B1.4b remains blocked. Track B remains blocked. Structure, not validated
meaning.**

---

## 1. Purpose

The operator asked to check a specific candidate source — **`github.com/cardiffnlp/trait-concept-datasets`** —
as a possible route to McRae concept metadata after the authoritative McRae hosts were egress-blocked
(`478f373`). This check evaluates the source's **provenance**, extracts **concept labels only**, and runs an
**indicative Stage A′ decomposition** on them. It builds no `Y` matrix, imports no data into the repo, and
scores nothing.

---

## 2. Source acquisition

- **Repository:** `cardiffnlp/trait-concept-datasets` (cloned read-only to a scratch dir, not imported).
- **What it is:** datasets of **trait-concept pairs** for 5 trait types (**colours, components, materials,
  size & shape, tactile**), in English and Spanish, **derived from** the McRae (2005) and CSLB (2014) norms.
- **Paper / provenance:** Anderson & Camacho-Collados (2022), *Assessing the Limits of the Distributional
  Hypothesis…*, *SEM 2022 (ACL). The McRae CSVs **preserve the original McRae 2005 column schema**
  (`Concept, Feature, WB_Label, Prod_Freq, KF, BNC, Familiarity, Length_Letters, Num_Feats_Tax, …`), confirming
  genuine McRae derivation.
- **License / access status:** repository is publicly clonable (`git clone` succeeded). **No `LICENSE` file at
  the repo root** → redistribution/reuse terms are **unclear** (a real caveat; the underlying McRae/CSLB norms
  carry their own access terms).
- **Provenance verdict:** **derivation provenance is CLEAR** (documented, cited, reputable lab, original schema
  preserved) — so this is **not** an "unclear-provenance mirror." But it is a **DERIVED SUBSET**, not the
  authoritative McRae feature-production norms.
- **Only concept labels used?** **Yes** — only the `Concept` column was read (union across the `en-mcrae-*`
  files). No feature/attribute values were used to build anything; no data was committed to the repo.

---

## 3. Concept-list handling

- **How labels were normalized:** lowercased; whitespace stripped; union/dedupe across the McRae single- and
  multi-label trait CSVs.
- **How multiword concepts were treated:** the source uses disambiguation tags like `bat_(animal)`,
  `bin_(waste)` — these decompose **partial** under Stage A′ (the `_ ( )` characters are unsupported). A
  **pre-declared** rule to strip `_(...)` disambiguation suffixes would recover them; they were **retained
  as-is** (not stripped) for this indicative check, and reported honestly as partial.
- **Ambiguous labels excluded or retained:** retained as-is (22 disambiguation-tagged entries), flagged.
- **`Y` values / matrix:** **none constructed.** No fabrication; no import into the repo.

---

## 4. Stage A′ overlap method

Existing Stage A′ module used **read-only** (`stage_a_prime_coverage.normalize`, `A_PRIME_EN`); code untouched,
tests **11/11 PASS**. Each genuine McRae concept label was decomposed; `full` = 0 unsupported units.

---

## 5. Eligibility threshold

Pre-registered requirement: **≥ 100 usable Stage A′-decomposable concepts**. This threshold is evaluated below
against the **genuine McRae-derived concept labels** obtained here.

---

## 6. Results

| Quantity | Value |
|---|---|
| Genuine McRae-derived concepts obtained | **523** (union across `en-mcrae-*` trait files) |
| Concepts normalized | 523 |
| **Fully decomposable by Stage A′** | **501 (95.8%)** |
| Partial (unsupported units) | 22 — **all disambiguation tags** (`_`, `(`, `)`); would be full after a pre-declared tag-strip rule |
| Empty / failed | 0 |
| ≥100 usable decomposable concepts? | **YES — 501 ≥ 100** (≈ full ~100% after tag-stripping) |

**Interpretation:** genuine McRae concrete-noun concepts decompose under Stage A′-EN at ~96% (≈100% with a
tag-strip rule), comfortably exceeding the ≥100-concept floor. This is a **strong indicative concept-overlap
result** — the McRae concept inventory is well-covered by Stage A′.

---

## 7. Decision

**`Y_SOURCE_OVERLAP_INCONCLUSIVE`** (with a **positive concept-overlap sub-result**).

Reasoning, held honestly:

- **The concept-overlap sub-question passes strongly** — 523 genuine McRae concepts, 501 fully decomposable
  (≥100), from a provenance-clear source. Stage A′ coverage of the McRae concept inventory is **not** in doubt.
- **But source-as-`Y` is not established**, so a full `Y_SOURCE_OVERLAP_AUDIT_PASS` would overclaim:
  1. this is a **derived trait-subset**, not the **authoritative** McRae feature-production norms;
  2. the repo has **no LICENSE** → redistribution/reuse terms unclear (cannot freeze/verify a reproducible `Y`
     from it);
  3. its attribute schema is **5 trait types**, not McRae's full ~2,526-feature norms — adopting a trait-based
     `Y` would be a **separate design decision** with its own admissibility check.
- Not `Y_SOURCE_METADATA_UNAVAILABLE` — concept labels **were** genuinely obtained here (unlike the
  authoritative-host attempt). Not `Y_SOURCE_REJECTED_LEAKAGE_RISK` — McRae is human-produced, not
  gloss-derived. Not `COVERAGE_TOO_THIN` — coverage is ample.

---

## 8. Next gate

- **To convert to a real PASS:** obtain the **authoritative McRae feature-production norms** (attribute values +
  license) — operator-provided file preferred, since the authoritative hosts are egress-blocked here. The
  concept-overlap is already demonstrated; what remains is a **license-clear authoritative attribute matrix**.
- **Or:** an explicit operator decision to adopt a **trait-based `Y`** (the 5 trait types) as the target — which
  would require its own admissibility memo (is a 5-way trait target a legitimate attribute `Y`?), and a
  license resolution for the cardiffnlp data.
- **Or:** provide authoritative **CSLB** (still the preferred source) as a license-clear file.
- **No semantic run follows automatically.** Even a subsequent pass unlocks only freeze-package **planning**.
  Expected downstream outcome remains `F_COLLAPSES_TO_PHONOLOGY → ⊥` (Stage A′ is phonology-derived).

**Source consulted:** [cardiffnlp/trait-concept-datasets](https://github.com/cardiffnlp/trait-concept-datasets)
(Anderson & Camacho-Collados, *SEM 2022; derived from McRae 2005 & CSLB 2014).

---

## 9. Boundary statement

> McRae-derived (cardiffnlp) source check completed. Concept labels only. No Y matrix created. No source data
> imported. No semantic validation performed. No evidence freeze declared. Original B1.4b remains blocked. Track
> B remains blocked. Structure, not validated meaning.
