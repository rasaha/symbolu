# B1.4b — Target-`Y` Coverage Audit (counts-only)

**Status:** Counts-only coverage audit (docs-only). **No dataset downloaded, no `Y` matrix built, no F-3 run,
nothing scored, no freeze.**
**Governed by:** `B1_4B_REAL_DATA_PREP_AND_FREEZE_PLAN.md` (§5 coverage audit), `B1_4B_TARGET_Y_ADMISSIBILITY_AUDIT.md`.
**No meaning validated. Track B remains blocked. Structure, not validated meaning.**

---

## 1. Purpose

This is a **counts-only coverage audit**: it checks whether a candidate independent `Y` source has enough
concept overlap (with the varṇa-decomposable word pool), enough attribute dimensionality, and clean provenance
to justify a later, separately-approved dataset acquisition. It is **not** dataset acquisition and **not**
validation. No `Y` values are fetched; no F-3 features are computed on real concepts; nothing is scored.

---

## 2. Candidate `Y` sources checked

- **McRae et al. (2005)** semantic feature-production norms — primary candidate.
- **CSLB (Devereux et al. 2014)** concept property norms — primary candidate.
- **Binder et al. (2016)** experiential feature ratings — primary candidate.
- **SWOW (De Deyne et al. 2019)** free-association norms — secondary / triangulation.
- **Warriner et al. (2013) VAD** and lexical sentiment norms — **controls / covariates only**.
- **Repo-local candidate norm files** — searched for; **none found** (no McRae/CSLB/Binder/SWOW/Warriner or
  equivalent human feature-norm file exists in the repo).

---

## 3. Available information

**Decisive fact:** none of the external norm datasets are present in the repo, and downloading is **not
permitted** in this step. Therefore the **concept-overlap count cannot be computed locally** for any external
source. The only side of the intersection that is locally countable is the **varṇa-decomposable concept pool**
(repo-local word lists).

| Source | Concept list available locally? | Attribute metadata | Coverage-overlap count |
|---|---|---|---|
| McRae 2005 | **No** (not in repo) | est. ~541 concepts / ~2500 features (published) | **UNAVAILABLE** (needs acquisition) |
| CSLB 2014 | **No** | est. ~638 concepts / ~5900 properties (published) | **UNAVAILABLE** |
| Binder 2016 | **No** | est. ~535 words / **65 experiential dims** (published) | **UNAVAILABLE** |
| SWOW 2019 | **No** | est. ~12k cues (association, not attributes) | **UNAVAILABLE** |
| Warriner 2013 VAD / sentiment | **No** | est. ~14k words, 3 affective dims (control) | **UNAVAILABLE** |
| Repo-local norm file | **None exists** | — | — |

External sizes above are **ESTIMATED from published metadata (from knowledge, not counted here)** and are
marked as such; they are **not** verified against a local file.

**Counted (repo-local, decomposable concept pool — the other side of the intersection):**

| Repo-local word list | Concept count (counted) |
|---|---|
| `frozen/word_list.json` | **110** |
| `b1_3_revised_layer3/b1_3_concrete_object_final_primary_wordlist.json` | **53** |
| `b1_3_revised_layer3/b1_3_human_modulation_concrete_object_candidate_wordlist.json` | **92** |

These are counts of existing frozen/candidate lists only; no decomposition or F-3 extraction was run.

---

## 4. Coverage criteria (from prep-plan §5)

Applied to each source:

- **Minimum concept count** — target ≥ ~100 concepts in the `Y` ∩ decomposable intersection.
- **Decomposability into varṇas** — each concept word must yield a clean cmudict→varṇa sequence.
- **Minimum attribute dimensionality** — ≥ ~10–20 usable attribute dimensions.
- **Missingness** — per-concept / per-attribute missing rates under a pre-registered cap.
- **Reliability** — attributes meet a pre-registered reliability floor.
- **Licensing / accessibility** — redistributable / citable.
- **No dictionary/gloss leakage** — human-produced, not read off definitions.

**Which criteria are checkable now:** attribute dimensionality is *estimable* from published metadata;
decomposability is *estimable* only for the repo-local pool; **concept-overlap count, missingness, and
reliability are NOT checkable** without acquiring the concept lists.

---

## 5. Counts-only results

- **Total candidate concepts (external `Y`):** UNAVAILABLE locally for all sources (datasets not present;
  download not permitted). Published estimates: McRae ~541, CSLB ~638, Binder ~535, SWOW ~12k, Warriner ~14k —
  **estimated, not counted.**
- **Decomposable concepts (repo-local pool, counted):** `frozen/word_list.json` = **110**;
  concrete-object final = **53**; concrete-object candidate = **92**.
- **Concepts with usable `Y` (the intersection):** **NOT COUNTABLE** — requires at least the external concept
  name lists, which are absent and may not be downloaded in this step.
- **Attribute dimensions:** estimated (published): Binder **65**, CSLB ~5900 properties, McRae ~2500 features;
  all comfortably exceed the ≥10–20 floor **if** acquired — **estimated, not verified locally.**
- **Exclusions:** cannot be enumerated without the concept lists (missingness/reliability unknown).

**What is missing to complete the count:** the **concept-name lists (and attribute schemas)** of at least one
external norm set. These are absent from the repo and acquiring them is a dataset-acquisition action requiring
separate explicit approval (§9).

---

## 6. Control / covariate status

**Warriner VAD, lexical sentiment, and frequency norms are suitable ONLY as controls / covariates, not as the
primary `Y`.** VAD ≈ the sentiment baseline; using it as the primary target would guarantee
`SEMANTIC_OR_SENTIMENT_BASELINE_EXPLAINS`. They enter B1.4b only as nuisance covariates to be partialled out and
as the sentiment baseline in the suite — never as the attribute target.

---

## 7. Eligibility decision per source

- **McRae 2005** → **`Y_SOURCE_METADATA_UNAVAILABLE`** — attribute-structured and human-produced (eligible in
  principle), but the concept-overlap count cannot be computed without acquisition.
- **CSLB 2014** → **`Y_SOURCE_METADATA_UNAVAILABLE`** — same; largest property set of the three.
- **Binder 2016** → **`Y_SOURCE_METADATA_UNAVAILABLE`** — strong attribute structure (65 experiential dims),
  human-rated; overlap count still unavailable.
- **SWOW 2019** → **`Y_SOURCE_METADATA_UNAVAILABLE`** (secondary/triangulation only; associations are not an
  attribute profile, so not primary even once counted).
- **Warriner VAD / sentiment** → **`Y_SOURCE_ONLY_CONTROL_COVARIATE`**.
- **Repo-local norm file** → **none exists** (no local `Y` source to evaluate).

No source qualifies as `Y_SOURCE_ELIGIBLE_FOR_FREEZE_PLANNING` on a **counts** basis, because no
concept-overlap count could be produced. No source is `Y_SOURCE_REJECTED_LEAKAGE_RISK` (the human-produced
feature norms are not gloss-derived); the gloss-derived / unconstrained-LLM options were already excluded
upstream and are not re-litigated here.

---

## 8. Recommended primary `Y`

**No primary `Y` is currently eligible on a counts basis** — the deciding intersection count is uncomputable
without acquisition. Conditional recommendation for the *acquisition target* (to be counted under a separate
approval): pursue **Binder et al. (2016)** first — it has the cleanest, lowest-dimensional (65) human-rated
attribute structure and the best fit to an "attribute/propensity profile" target — with **CSLB** and **McRae**
as fallbacks for concept coverage. This is a recommendation of *what to count next*, not a selection of `Y` and
not an acquisition.

---

## 9. Next gate

Because no source is countably eligible, **B1.4b remains gated.** The next step is a **separate, explicit
operator approval to acquire the concept-name lists / attribute schemas** of one primary candidate (Binder
first) **solely to compute the overlap count** — itself a dataset-acquisition action that this audit does not
authorize. Ladder:

1. approve acquisition of the candidate's **concept list + attribute schema** (metadata only) →
2. compute the `Y` ∩ decomposable **overlap count** and re-run this audit →
3. if it clears the thresholds, `Y_SOURCE_ELIGIBLE_FOR_FREEZE_PLANNING` → approve full acquisition + freeze
   package →
4. only then, under further authorization, the pilot run.

If the overlap count cannot be secured, **B1.4b remains blocked** (`Y_NOT_INDEPENDENT` / `Y_TOO_COSTLY` at the
prereg level). No step is auto-triggered.

---

## 10. Boundary statement

> B1.4b Y coverage audit completed. No real Y matrix created. No real-data scoring performed. No evidence
> freeze declared. Track B remains blocked. Structure, not validated meaning.
