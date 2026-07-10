# B1.9 — Content-Level Semantic-Distance Test (PREREGISTRATION, docs-only)

**Status:** preregistration / design spec. **Generation-free, judge-free.** No test run. No B1.8 result changed,
re-scored, or tuned. No terminal result label.

**Readiness label: `B1_9_CONTENT_DISTANCE_PREREG_READY`.** (Execution-only labels in §12 are reserved and must
**not** be emitted by this commit.)

**B1.4b′ remains `NULL_RETURN_BOTTOM`.** Original B1.4b blocked; Track B blocked. No ontology, no Sanskrit
privilege, no semantic-truth claim. Structure, not validated meaning.

---

## 1. Purpose

A **generation-free, judge-free, content-level** test of whether a word's **own** varṇa facets are systematically
closer, in embedding space, to the target word/context than **distance-matched random/control** varṇa facets.
This strips away the generation and judging layers that added noise and confounds in B1.6/B1.8, and tests the
mapping *directly*.

## 2. Motivation

B1.8 showed (a) broad generation utility is null/negative, (b) the LLM generation + judging pipeline adds noise,
and (c) the scrambled facet control can be **accidentally semantically close** to the target, confounding the
`specificity_to_target` endpoint. A post-hoc "clean-subset" flip looked authentic-favoring but was a **circular
selection artifact** (selecting `d_auth < d_scram` self-fulfills a specificity win). The underlying non-circular
signal was a weak ~0.026 cosine lean (8/12 authentic-closer). B1.9 measures that signal prospectively, cleanly,
and cheaply — before any generation layer.

## 3. Primary question

Are **authentic** word→varṇa facet aggregates closer (in embedding space) to the target word/context than
**pre-registered random/control** varṇa facet aggregates?

## 4. Primary endpoint

`delta_distance = d_control − d_auth`, where
- `d_auth = dist(rep(target/context), aggregate(authentic varṇa facets))`
- `d_control = dist(rep(target/context), aggregate(control varṇa facets))`
- `dist = 1 − cosine_similarity`; **positive `delta_distance` favors the authentic mapping.**

**Primary statistic:** mean paired `delta_distance` across items (paired per item; per control family).

## 5. Primary contrast

Authentic varṇa facet aggregate **vs** distance-matched random/control varṇa facet aggregate (per item).

## 6. Anti-circularity rule (mandatory)

- **Do NOT** select the analysis subset using `d_auth < d_control` (or any function of `d_auth`).
- **Do NOT** filter items based on authentic being closer, before or after computing the outcome.
- If semantic-distance constraints are used, **constrain only the control pool prospectively** — sample controls
  to a preregistered distance band **relative to the target**, **without** referencing whether authentic is
  closer for that item.
- Prefer a **fixed item set** and **fixed control sampling** decided **before** any outcome is computed. The
  item set is frozen; no item is added or dropped based on its outcome.

## 7. Design requirements

- **No generation. No LLM judges. No human judges. No output ratings. No prompt evaluation.**
- Item set: the frozen B1.8 targets/contexts **or** a larger preregistered word list (frozen before run). A
  larger list (e.g. 60–200 words spanning strata) is preferred for power; it must be frozen with hashes.
- **Pinned embedding model** (e.g. `sentence-transformers/all-MiniLM-L6-v2`, hash-pinned) and **pinned
  preprocessing** (tokenization/normalization, stopword policy, facet-aggregation rule: mean-of-facet-embeddings
  vs concatenation — chosen and frozen in advance).
- **Fixed random seeds**; **fixed number of controls per item** (`K`, preregistered).
- **Freeze all inclusion/exclusion criteria before running.** If, under a prospective distance constraint on the
  control pool (§6), an item has **no valid control**, mark it **`REFUSE_UNSEPARABLE` before outcome analysis**
  and exclude it — never relax the constraint or drop/keep an item based on its observed authentic-vs-control
  outcome.
- Analysis by **bootstrap / permutation / sign-test**; report **effect size + confidence interval**.
- Include the negative controls of §8.

## 8. Controls (facet aggregates compared to authentic)

1. **Same-polarity random varṇa facet control** — random other varṇas' facets, same selected pole.
2. **Same-plane random varṇa facet control** — random facets drawn within the same sphere/plane.
3. **Frequency/length-matched facet control** — matched on token length / word frequency where available.
4. **Completely random facet control** — any pole, any varṇa.
5. **Permuted target labels** — shuffle target↔facet-set assignment across items (null distribution).
6. **Random word/context decoy** — authentic facets vs an unrelated word/context (upper-bound sanity that the
   metric can detect gross mismatch).

## 9. Preprocessing (frozen before run)

- Freeze **all** target texts, context texts, facet texts, tokenizer/normalization rules, stopword policy,
  facet-aggregation rule, and the embedding-model hash **before** running.
- **Do NOT** manually remove synonyms/near-synonyms after seeing outcomes.
- **Do NOT** tune thresholds, `K`, distance bands, or the aggregation rule after seeing outcomes.

## 10. Statistical plan

- **Primary statistic:** mean paired `delta_distance` (authentic vs same-polarity control, control family 1).
- **Secondary:** sign count (authentic-closer vs control-closer) with an exact sign test.
- **Bootstrap CI** over items (fixed seed, preregistered iterations).
- **Permutation test** over item↔control assignment (control 5) to build the null.
- Report **exact p-values** where feasible, and **effect size** (mean `delta_distance` + CI) per control family.
- **Report results for ALL control families (1–6), not only the most favorable one.**
- **Define the success threshold before execution** (e.g. mean `delta_distance ≥ δ*` with permutation
  p < preregistered α, robust across control families 1–4). `δ*` and α are fixed in the freeze.
- **No terminal ontology label** under any outcome.

## 11. Expected prior (stated low)

Low prior, based on:
- **B1.4b′ `NULL_RETURN_BOTTOM`** (primitive attributions carry no recoverable meaning);
- **B1.8 broad generation utility null/negative**;
- the observed **non-circular** B1.8 content-level lean of only **~0.026 cosine distance** and **8/12**
  authentic-closer (non-significant, p ≈ 0.19).
Honest expectation: **null or near-null.** B1.9 is run because it is the *correct, cheap, non-circular* test —
not because a positive is expected.

## 12. Interpretation rules

- **Null** (`delta_distance ≈ 0`, threshold not met): mapping-level content proximity **not supported**; B1.4b′
  reinforced.
- **Small positive** (weak, some controls): evidence only of a **weak embedding-proximity bias** — **not**
  ontology, **not** semantic truth, **not** generation utility.
- **Strong positive and robust across controls 1–4:** justifies a **later, separately-preregistered** generation
  test — but still **no** ontology or Sanskrit-privilege claim.
- **Under no outcome** emit `ONTOLOGICAL_SIGNAL` or `GENUTILITY_*`.

**Result labels (future execution only; NOT emitted here):**
`B1_9_CONTENT_DISTANCE_NOT_RUN` (default until run); after execution one of
`B1_9_CONTENT_DISTANCE_NULL`, `B1_9_CONTENT_DISTANCE_WEAK_EXPLORATORY`,
`B1_9_CONTENT_DISTANCE_ROBUST_PROSPECTIVE`. **This commit uses only `B1_9_CONTENT_DISTANCE_PREREG_READY`.**

## 13. Guardrails

- **No test run.** No embeddings computed here (beyond reproducing the already-pasted B1.8 diagnostic numbers in
  the audit). **No result label beyond prereg readiness.** No generation. No judging. **No raw `run_out/` data
  committed.** No ontology claim; no semantic-truth claim; no Sanskrit privilege.
- **B1.4b′ remains `NULL_RETURN_BOTTOM`**; original B1.4b blocked; Track B blocked. Structure, not validated
  meaning.

---

## Final report

- **Files created/modified:** created `experiments/primitive_sequence_recovery/B1_9_CONTENT_LEVEL_SEMANTIC_DISTANCE_PREREG.md`;
  updated `experiments/primitive_sequence_recovery/B1_8_SEMANTIC_OVERLAP_CONFOUND_AUDIT.md` (§4b flip-analysis +
  circular-selection warning). No B1.8 results/ratings modified.
- **Commit hash:** recorded on the commit below.
- **Readiness label:** `B1_9_CONTENT_DISTANCE_PREREG_READY`.
- **B1.8 results changed?** No — only the audit doc gained an interpretive section; ratings/aggregate untouched.
- **B1.9 run?** No — preregistered only.
- **Raw `run_out/` data committed?** No.
- **`GENUTILITY_*` or ontology label emitted?** No.
- **B1.4b′ remains `NULL_RETURN_BOTTOM`.**

B1.8 flip-analysis recorded as post-hoc circular-selection diagnostic. B1.9 content-level semantic-distance
preregistration ready, not run. No raw run_out data committed. No generation. No judging. No GENUTILITY terminal
label. B1.4b′ remains NULL_RETURN_BOTTOM. Original B1.4b remains blocked. Track B remains blocked. Structure, not
validated meaning.
