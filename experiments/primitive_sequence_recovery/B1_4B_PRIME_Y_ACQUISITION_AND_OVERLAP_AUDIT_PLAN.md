# B1.4b′ — Y Acquisition & Overlap-Audit Plan

**Status:** Plan only (docs-only). **No dataset acquired, none downloaded, no Y matrix built, nothing run or
scored.**
**Governed by:** `B1_4B_PRIME_LAYER3_DECODER_Y_DESIGN.md` (`08e656a`), `B1_4B_TARGET_Y_ADMISSIBILITY_AUDIT.md`,
`STAGE_A_PRIME_COVERAGE_REPORT.md` (`8d4b097`), `SYMBOL_U_L2_VALIDATION_RULEBOOK.md`.
**No meaning validated. Original B1.4b remains blocked. Track B remains blocked. Structure, not validated
meaning.**

---

## 1. Purpose

This plan specifies **how** an independent target `Y` would be selected/acquired and how its **overlap with
Stage A′-decomposable concepts** would be audited. It is a plan **only** — it does **not** acquire data, does
**not** download anything, and does **not** build a `Y` matrix. Its deliverable is an ordered acquisition
recommendation + an overlap-audit procedure + the gate that must clear before any acquisition.

---

## 2. Current state

- **Stage A′ L1 coverage success** — repo-local Sanskrit 107/107, English 92/92 fully decomposable (`8d4b097`).
- **Stage A′ L1→L2 sample trace success** — 20/20 words decomposed, F-3 computable (`af9935b`).
- **Layer-3 decoder spec ready** — `B1_4B_PRIME_LAYER3_DECODER_SPEC_READY` (`08e656a`).
- **Blocked by missing independent `Y`** — `B1_4B_PRIME_LAYER3_BLOCKED_NO_Y`.
- **Original B1.4b remains blocked** — Stage A′ is **not** substituted into it.

---

## 3. `Y` requirements

`Y` is admissible only if **all** hold:

- **Independently collected** — by a process unrelated to Symbol-U / Stage A′.
- **Human-produced where possible** — human ratings/feature production, not model output.
- **Attribute/feature based** — a profile of attributes, not a definition.
- **Not dictionary-definition matching** — not the word's gloss nor a match-to-definition score.
- **Not varṇa/gloss/vṛtti/four-sphere/polarity/KCPR derived** — no Symbol-U-internal source touches `Y`.
- **Frozen before any F-3 fitting/scoring** — `Y`, concepts, attributes, exclusions hash-locked pre-fit.
- **Matched to Stage A′-decomposable concepts** — every `Y` concept must decompose fully under Stage A′.

---

## 4. Candidate `Y` sources (to evaluate — none acquired here)

| Candidate | Type | Role |
|---|---|---|
| **McRae (2005) feature-production norms** | human-produced concept features | **primary candidate** |
| **CSLB concept property norms** | human-produced property norms | **primary candidate** |
| **Binder (2016) feature ratings** | human experiential attribute ratings | **primary candidate** |
| **SWOW / association norms** | behavioral association | **secondary / triangulation** |
| **Warriner VAD** | affective (valence/arousal/dominance) | **covariate / control ONLY** |
| **NRC-VAD / EmoLex (sentiment)** | lexical sentiment | **covariate / control ONLY** |
| **Dictionary/gloss-derived feature labels** | definitional | **REJECTED** (circular) |
| **Unconstrained LLM-generated `Y`** | model output | **REJECTED as evidence** (pilot-only at most) |

---

## 5. Source-priority recommendation

Recommended acquisition order, with rationale:

1. **CSLB or McRae feature-production norms** — human-produced, attribute-structured, and **English
   concrete-noun** inventories that best match the repo-local English concrete-object pool; largest chance of
   ≥100-concept overlap with Stage A′-decomposable words. CSLB first (larger concept/property set), McRae close
   second.
2. **Binder (2016) feature norms** — cleanest low-dimensional (~65) experiential attribute structure; excellent
   as the *attribute schema* even if concept coverage is smaller; strong triangulation/secondary primary.
3. **SWOW association norms** — **secondary** only; associations are not attributes, used to triangulate, not as
   the primary target.
4. **VAD / sentiment / frequency / concreteness** — **covariates/controls only**, never primary `Y` (they ≈ the
   sentiment/length baselines and would trivially "explain" a result).

Rationale: prioritize **human-produced, attribute-structured, concrete-noun** norms because (a) they are
non-circular, (b) they match the decomposable concept universe, and (c) they give the best shot at clearing the
≥100-concept overlap floor. Affective/sentiment norms are deliberately demoted to controls.

---

## 6. Metadata-only first step

The **first approved action** (separately gated, §12) is **metadata / concept-list acquisition only** — never a
`Y` matrix. It records, for the top-ranked source:

- **source name + version**,
- **license / access terms** (redistributable / citable, reproducible-audit-compatible),
- **concept list** (the words/concepts, for overlap counting),
- **attribute dimensions** (schema + count),
- **reliability information** (published inter-rater / split-half),
- **citation / provenance**.

**No `Y` values are constructed** at this step — concept names + attribute schema + metadata only. Attribute
*values* remain unacquired until a later, separate freeze approval.

---

## 7. Overlap audit

Given the metadata (concept list only), the overlap audit:

1. **Normalize source concept labels** — lowercase, strip determiners, split multiword entries per pre-declared
   rules (or exclude them, §default below).
2. **Run Stage A′ normalization/decomposition** — feed each concept word through `A_PRIME_EN` (English) /
   `A_PRIME_SA` (transliteration) via the existing harness (read-only; no code edits).
3. **Count fully decomposable concepts** — `flag == full`, 0 unsupported units.
4. **Count usable attributes** — attributes meeting the reliability floor and non-degeneracy.
5. **Exclude multiword/ambiguous concepts** — unless a splitting/selection rule is **pre-declared** before the
   count (no post-hoc inclusion to hit the floor).
6. **Require ≥ 100 usable Stage A′-decomposable concepts** for B1.4b′ prep — below that →
   `Y_SOURCE_COVERAGE_TOO_THIN` / `B1_4B_PRIME_STILL_BLOCKED_NO_Y`.

Output = a **counts-only eligibility report** (no `Y` values), analogous to `B1_4B_Y_COVERAGE_AUDIT.md`.

---

## 8. Freeze-package prerequisites (to be frozen LATER, not now)

Before any B1.4b′ evidence run, a pre-registration amendment must hash-freeze:

- selected `Y` source (name + version + citation),
- concept list (post-exclusion),
- attribute list (post-reliability),
- the `Y` matrix (values, once acquired under separate approval),
- preprocessing rules,
- exclusion rules,
- train/test split policy (concept-level folds, fixed seed),
- F-3 feature list + Stage A′ inventory version,
- baselines (definitions + seeds),
- probe family / capacity,
- metrics / thresholds / primary endpoint,
- hashes (per-artifact + manifest self-hash).

None of this is created here.

---

## 9. Controls and covariates

- **VAD / sentiment / frequency / concreteness** are **controls / covariates**, **not** primary `Y`.
- They are used to **test whether sentiment/lexical/length baselines explain** any apparent F-3 effect (partial
  them out; run them as baselines the decoder must beat).
- If any of them, used as `Y`, would "explain" the result, the correct label is
  `SEMANTIC_OR_SENTIMENT_BASELINE_EXPLAINS` — which is exactly why they are barred from being the primary target.

---

## 10. Invalid-source conditions

A candidate source is **rejected / blocked** if any hold:

- **`Y` is dictionary/gloss-derived** → `Y_SOURCE_REJECTED_LEAKAGE_RISK`.
- **`Y` is LLM-generated without independent human grounding** → rejected as evidence (pilot-only at most).
- **concept-list coverage below the ≥100 floor** (post Stage A′ decomposition) → `Y_SOURCE_COVERAGE_TOO_THIN`.
- **licensing prevents a reproducible audit** → blocked (cannot freeze/verify).
- **attributes too sparse** (below reliability/non-degeneracy) → coverage too thin.
- **`Y` selected after looking at F-3 outcomes** → invalid (post-hoc target; a `Y_NOT_INDEPENDENT` condition).

---

## 11. Terminal labels

- **`Y_SOURCE_METADATA_APPROVAL_READY`** — a top-ranked source is identified and ready for **metadata-only**
  acquisition approval.
- **`Y_SOURCE_ACQUISITION_REQUIRED`** — metadata/concept list must be acquired before overlap can be counted.
- **`Y_SOURCE_REJECTED_LEAKAGE_RISK`** — a candidate is gloss/definition-derived.
- **`Y_SOURCE_COVERAGE_TOO_THIN`** — overlap below the ≥100 floor.
- **`Y_SOURCE_OVERLAP_AUDIT_READY`** — metadata in hand; the overlap audit procedure is ready to run.
- **`B1_4B_PRIME_STILL_BLOCKED_NO_Y`** — no usable independent `Y` yet secured.
- **`Y_PLAN_INCONCLUSIVE`** — the plan cannot resolve the source question as specified.

**This memo emits:** `Y_SOURCE_METADATA_APPROVAL_READY` (CSLB/McRae top-ranked) **+**
`Y_SOURCE_ACQUISITION_REQUIRED` (metadata not yet in repo, download not permitted here) **+**
`B1_4B_PRIME_STILL_BLOCKED_NO_Y` (no `Y` secured). No source is acquired; no overlap counted (no metadata
present locally).

---

## 12. Recommended next gate

The next step is **explicit operator approval for metadata / concept-list acquisition of the top-ranked `Y`
source only** (CSLB first; McRae fallback; Binder as attribute-schema candidate) — concept names + attribute
schema + license, **no `Y` values**. Only after that metadata is in hand would the overlap audit (§7) run, and
only if it clears ≥100 decomposable concepts would a B1.4b′ pre-registration + `Y`-value acquisition be
considered — each under **separate** approval. **No dataset download, no full `Y` matrix, and no scoring** occur
without those separate approvals. No step is auto-triggered.

---

## 13. Boundary statement

> B1.4b′ Y acquisition and overlap-audit plan completed. No Y matrix created. No dataset acquired. No semantic
> validation performed. No evidence freeze declared. Original B1.4b remains blocked. Track B remains blocked.
> Structure, not validated meaning.
