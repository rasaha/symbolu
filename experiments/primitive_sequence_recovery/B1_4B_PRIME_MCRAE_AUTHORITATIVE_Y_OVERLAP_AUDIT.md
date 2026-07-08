# B1.4b′ — McRae **Authoritative** Y Overlap Audit

**Status:** Overlap audit (docs-only). **Concept labels only. No Y matrix built. Raw McRae data NOT committed
to the repo (per Terms of Use). No decoder, no F-3 scoring, no freeze.**
**Governed by:** `B1_4B_PRIME_Y_ACQUISITION_AND_OVERLAP_AUDIT_PLAN.md` (`e1cefc0`),
`B1_4B_PRIME_MCRAE_Y_METADATA_OVERLAP_AUDIT.md` (`478f373`), `stage_a_prime_coverage.py` (`8d4b097`, read-only).
**No meaning validated. Original B1.4b remains blocked. Track B remains blocked. Structure, not validated
meaning.**

---

## 1. Purpose

The operator provided the **authoritative** McRae norm files (from the Psychonomic Society Web Archive). This
audit uses the **concept labels only** to test whether they overlap sufficiently with **Stage A′-decomposable
concepts** for a future B1.4b′. It builds no `Y` matrix, commits no raw data, and scores nothing.

---

## 2. Source acquisition

- **Source:** McRae, Cree, Seidenberg & McNorgan (2005) semantic feature production norms — **authoritative**
  files supplied by the operator: `CONCS_brm.txt` (541 concept rows + concept statistics), plus
  `CONCS_FEATS_concstats_brm.txt`, `FEATS_brm.txt` (2,526 features), `cos_matrix_brm_IFR_*` (541×541 cosine
  matrix), and READ_ME / variable-explanation files.
- **Provenance:** Psychonomic Society Web Archive (`www.psychonomic.org/archive`), as cited by the article
  (`BF03192726`). READ_ME confirms **541 concepts** and file structure.
- **Terms of Use (respected):** the archive terms grant **non-commercial use by researchers/educators with
  citation of both the article and the retrieved norms**; **all rights remain with the authors** and
  redistribution is not granted. Accordingly this audit **does not commit the raw McRae data** into the repo —
  only **derived counts** and a few already-public example concept names are reported. Any downstream use must
  cite McRae et al. (2005) **and** the archived norms.
- **Only concept labels used?** **Yes** — only the `Concept` column of `CONCS_brm.txt` was read for this
  overlap. No feature values / `Y` matrix were constructed.

**Required citation (for any downstream use):**
McRae, K., Cree, G. S., Seidenberg, M. S., & McNorgan, C. (2005). *Semantic feature production norms for a
large set of living and nonliving things.* Behavior Research Methods, 37(4), 547–559. + the retrieved
Psychonomic Web Archive norms.

---

## 3. Concept-list handling

- **Normalization:** lowercased, whitespace-stripped; the `Concept` column (541 entries) read verbatim.
- **Disambiguation tags:** 24 concepts carry homograph sense-tags, e.g. `bat_(animal)`, `bat_(baseball)`,
  `board_(black)`, `bow_(weapon)`. Two treatments are reported: **as-is** (tags retained) and **tag-stripped**
  (a **pre-declared** rule removing a trailing `_(sense)`).
- **`Y` values / matrix:** **none constructed.** No fabrication. **Raw data not committed** (Terms of Use).

---

## 4. Stage A′ overlap method

Existing Stage A′ module used **read-only** (`stage_a_prime_coverage.normalize`, `A_PRIME_EN`); code untouched,
tests **11/11 PASS**. Each concept decomposed; `full` = 0 unsupported units.

---

## 5. Eligibility threshold

Pre-registered requirement: **≥ 100 usable Stage A′-decomposable concepts**. Evaluated against the
authoritative 541-concept list below.

---

## 6. Results

| Treatment | Concepts | Fully decomposable | Partial | Empty | ≥100 met? |
|---|---|---|---|---|---|
| **as-is** | 541 | **517 (95.6%)** | 24 (all homograph sense-tags: `_ ( )`) | 0 | **YES** |
| **tag-stripped** (pre-declared) | 541 | **541 (100.0%)** | 0 | 0 | **YES** |

- The 24 "partial" are **only** the disambiguation-tag characters (`_`, `(`, `)`); after the pre-declared
  tag-strip rule, **all 541 concepts decompose fully**.
- **Homograph / collision caveat (important):** under Stage A′ the 541 tag-stripped concepts map to **531
  distinct phoneme sequences** — **20 concepts collapse into 10 groups** that Stage A′ cannot distinguish:
  - **9 legitimate homograph sense-pairs** — same spelling, e.g. `bat_(animal)`/`bat_(baseball)`,
    `board_(black)`/`board_(wood)`, `bow_(ribbon)`/`bow_(weapon)`, `cap_(bottle)`/`cap_(hat)`, `hose`,
    `mink`, `mouse`, `pipe`, `tank` — identical phonemes → identical operators → **identical F-3**. F-3 cannot
    separate them; for a `Y` these must be excluded or explicitly treated as a within-pair confound.
  - **1 G2P-faithfulness FALSE collision** — **`cloak`/`clock` → `k-l-o-k`**. These are genuinely distinct
    words, but the **coverage-oriented** `A_PRIME_EN` G2P (built for retention, not pronunciation accuracy;
    `c→k`, coarse vowels) maps them identically. This is a real limitation of the coverage G2P — a phonetically
    accurate G2P would separate them — and it is recorded here as a known Stage A′ defect to carry into any
    B1.4b′ pre-registration.
- **Effective distinct-concept count under Stage A′: 531** — still ≫ 100.

---

## 7. Decision

**`Y_SOURCE_OVERLAP_AUDIT_PASS`.**

The **authoritative** McRae concept list (541 concepts) was obtained (operator-provided, provenance-clear,
Terms-of-Use-compliant), and Stage A′ decomposes **517 as-is / 541 tag-stripped** — far exceeding the ≥100
floor. Concept-overlap eligibility is met. (Not `Y_SOURCE_OVERLAP_INCONCLUSIVE` — unlike the derived cardiffnlp
subset, this is the authoritative list; not `Y_SOURCE_METADATA_UNAVAILABLE` — the list is in hand; not
`COVERAGE_TOO_THIN`; not `REJECTED_LEAKAGE_RISK` — McRae is human-produced, not gloss-derived.)

**Scope of this PASS:** it certifies **concept overlap only**. It is **not** semantic validation, **not** a `Y`
matrix, and **not** approval to run anything. The 20-concept homograph/collision set and the `cloak`/`clock`
G2P defect are pre-registration must-handles.

---

## 8. Next gate

`Y_SOURCE_OVERLAP_AUDIT_PASS` unlocks **freeze-package planning only** (separate approval), not a `Y` build or a
run. Before any B1.4b′ evidence run, a pre-registration must additionally fix:

1. **`Y` attribute matrix source** — the per-concept feature values (`CONCS_FEATS_concstats_brm.txt` /
   `FEATS_brm.txt`) → the attribute target; its construction is a **separate gated step** (not done here), and
   its use must cite McRae per the Terms of Use, with the **raw data kept out of the repo** unless the license
   is separately cleared for redistribution.
2. **Homograph handling** — exclude the 9 homograph pairs (or treat as a declared confound); **exclude or fix
   `cloak`/`clock`** (coverage-G2P false collision) — ideally via a phonetically accurate G2P, which is itself a
   Stage A′ revision requiring separate pre-registration.
3. **Tag-strip rule** — pre-declare the `_(sense)` normalization.
4. The full B1.4b′ decoder / baseline / endpoint / split freeze (`B1_4B_PRIME_LAYER3_DECODER_Y_DESIGN.md`).

**No semantic run follows automatically.** The expected downstream outcome remains
`F_COLLAPSES_TO_PHONOLOGY → ⊥` — a fuller, faithful phoneme substrate makes the phonological baseline *stronger*,
so this overlap PASS is a **substrate/eligibility** success, not evidence of meaning.

---

## 9. Boundary statement

> McRae authoritative Y overlap audit completed. Concept labels only. No Y matrix created. No raw data committed.
> No semantic validation performed. No evidence freeze declared. Original B1.4b remains blocked. Track B remains
> blocked. Structure, not validated meaning.
