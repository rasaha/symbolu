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

0. **Distant-source-word mapping control (PRIMARY — corrected control)** — control = a **different real source
   word `W′`'s OWN complete authentic varṇa-derived facet aggregate**, constructed exactly as authentic is (same
   pipeline, same register). `W′` is frozen as the item whose target/context embedding is **most distant** from
   `W`'s, selected using **target/context embeddings ONLY** (never facet embeddings or outcome distances). See
   §8c and §12d.
0′. **Out-of-pool lexicon control (SECONDARY — external register)** — control facets drawn from a frozen lexicon
   (`frozen/b1_9_out_of_pool_lexicon.json`) that reuses **NO varṇa→meaning mapping**. An extra control in a
   *different register*; **not** the main correction. See §8b for its honest register caveat.
1. **Same-polarity random varṇa facet control** — random other varṇas' facets, same selected pole.
   *(BLOCKED — resolver-free; see §12b/§12c.)*
2. **Same-plane random varṇa facet control** — random facets drawn within the same sphere/plane. *(within-pool)*
3. **Frequency/length-matched facet control** — matched on token length / word frequency where available.
   *(within-pool, length-only)*
4. **Completely random facet control** — any varṇa. *(within-pool; secondary/triangulation)*
5. **Permuted target labels** — shuffle target↔facet-set assignment across items (null distribution).
6. **Random word/context decoy** — authentic facets vs an unrelated word/context (upper-bound sanity that the
   metric can detect gross mismatch).

## 8b. Out-of-pool control — motivation and honest caveat (SECONDARY)

Controls 2–4 all draw content from the **same 25-varṇa pool**. Because that pool is a small set of broadly
applicable psychological/spiritual attributions, a within-pool "scramble" is often a **paraphrase-level
near-synonym** of the authentic facet — operator's framing: *"doctor studies medicine" is the same as "medicine
is study done by doctors"; if the scramble carries the same meaning there is nothing to differentiate.* That
biases every within-pool contrast toward NULL by construction.

The **out-of-pool lexicon control** (control 0′) addresses that by drawing control content from
`frozen/b1_9_out_of_pool_lexicon.json`, authored **independently** of the varṇa table — no entry is a varṇa
`named_attribute`, sphere gloss, binding gloss, or near-synonym of one. The control side therefore reuses **no
varṇa mapping at all.**

**Honest caveat (why this is SECONDARY, not the main correction):** the out-of-pool glosses are
**concrete/sensory/natural/craft/geometric** — a *different register* from the abstract-psychological varṇa
attributions. So a positive `delta_distance` against this control could reflect a **register difference**
(abstract vs concrete), **not** varṇa-specific meaning. The **primary** corrected control (§8c) avoids this by
keeping the control on the same varṇa-mapping construction/register as authentic. The out-of-pool result is
reported as an **extra external-register check** and must be read together with the within-pool controls (2–4):
- authentic beating the out-of-pool control **but not** the within-pool controls → **register-appropriateness,
  not varṇa specificity** (still consistent with NULL for the hypothesis);
- authentic beating **both** → a stronger (still low-level, non-ontological) content-proximity signal worth a
  separately-preregistered follow-up.

## 8c. Distant-source-word mapping control — PRIMARY (corrected control)

**Rationale.** The correct control keeps the control side on the **same varṇa-mapping construction and register**
as authentic, while guaranteeing the source is genuinely distant — so it is neither a within-pool near-synonym
(controls 2–4) nor an out-of-register lexicon gloss (control 0′). For each target `W`:

- **authentic** = `W`'s own complete varṇa-derived facet aggregate;
- **control** = a **different real source word `W′`'s own** complete authentic varṇa-derived facet aggregate;
- **`W′` selection** = the item whose **target/context** embedding is **most distant** from `W`'s, using
  **target/context embeddings ONLY** — never facet embeddings, never any outcome/`d_auth` distance (§6
  anti-circularity preserved);
- the **`W → W′` assignment is frozen before** any facet/outcome distance is computed (recorded per item as
  `source_word_id`);
- **endpoint:** `delta = distance(target/context(W), facets(W′)) − distance(target/context(W), facets(W))`;
  positive favors `W`'s own mapping (identical in form to §4).

**W′ source pool (frozen):** the B1.9 target set itself (each `W′` is another real target word with its own
varṇa mapping). *Honest limitation:* the pool is only 12 words and several contexts are thematically adjacent, so
"most distant available" may still be only moderately distant; a larger frozen vocabulary is a later extension.
This does not affect anti-circularity (selection is by target/context distance, frozen before outcomes).

All families (0, 0′, 2–6) are reported; none is cherry-picked.

## 9. Preprocessing (frozen before run)

- Freeze **all** target texts, context texts, facet texts, tokenizer/normalization rules, stopword policy,
  facet-aggregation rule, and the embedding-model hash **before** running.
- **Do NOT** manually remove synonyms/near-synonyms after seeing outcomes.
- **Do NOT** tune thresholds, `K`, distance bands, or the aggregation rule after seeing outcomes.

## 10. Statistical plan

- **Primary statistic:** mean paired `delta_distance` (authentic vs the **distant-source-word mapping control**,
  control family 0 — see §8c/§12d). The out-of-pool lexicon control (0′) is a reported **secondary**. *(Both
  supersede the earlier "same-polarity / family 1" phrasing, which is blocked under the resolver-free
  named_attribute mode.)*
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

## 12b. Runner (implemented, mock-tested — NOT run)

`run_b1_9_content_distance.py` (+ `test_run_b1_9_content_distance.py`, 27 tests). Generation-free, judge-free.
Seven frozen inputs: `frozen/b1_9_targets.json`, the v2 facet table, `frozen/b1_9_control_sampler_config.json`,
`frozen/b1_9_preprocessing_config.json`, `frozen/b1_9_embedding_config.json`, and
`frozen/b1_9_out_of_pool_lexicon.json` (the secondary out-of-pool control content). Reads **no** `run_out/`;
imports **no** generation/judging module. Label emitted: **`B1_9_CONTENT_DISTANCE_RUNNER_READY_MOCK_TESTED`** only.

Control-family status (reported in full; not cherry-picked):
`distant_source_word_mapping` **IMPLEMENTED (PRIMARY — corrected control)** — control = a different real word
W′'s OWN authentic varṇa mapping, W′ chosen most-distant by target/context embedding only, W→W′ frozen before
outcomes (§8c/§12d),
`out_of_pool_lexicon_facet` **IMPLEMENTED (SECONDARY — external register)** — control content from the frozen
out-of-pool lexicon, reuses no varṇa mapping (§8b),
`completely_random_facet` **IMPLEMENTED** (within-pool; secondary/triangulation),
`same_plane_random_varna_facet` **IMPLEMENTED** (within-pool),
`permuted_target_label` **IMPLEMENTED**, `random_word_context_decoy` **IMPLEMENTED**,
`frequency_length_matched_facet` **IMPLEMENTED_LENGTH_ONLY** (within-pool; no corpus frequencies),
`same_polarity_random_varna_facet` **BLOCKED_NOT_AVAILABLE** — a resolver-free, neutral `named_attribute` test
has no polarity dimension; reinstating poles would reintroduce the resolver confound B1.9 exists to avoid.

**Mock plumbing (fake embeddings; no model; no gate):**
```bash
python3 run_b1_9_content_distance.py --mock --out run_out/b1_9_mock   # fake numbers, plumbing only
```
**Real run (later; requires the pinned model + a B1.9 declaration):**
```bash
python3 run_b1_9_content_distance.py --decl run_out/b1_9/b1_9_DECLARED.json --out run_out/b1_9/result
```
**Declaration template** (`artifact: b1_9_content_distance_DECLARED`, `b1_9_declared: true`, `mode`,
`representation_version`, `declared_by`, `declared_at_utc`, `attestation` = the §5 exact string, plus sha256 of
each of the **seven** frozen inputs (now including `frozen/b1_9_out_of_pool_lexicon.json`) — built from
`run_b1_9_content_distance.HASH_INPUTS`). The gate refuses any B1.6/B1.8 mode, wrong representation, missing
attestation, or hash mismatch. **The real test has NOT been run.**

## 12c. Runner/prereg consistency clarification (pre-execution)

A consistency audit (before any real execution) found that §10 still names the *primary statistic* as
"authentic vs **same-polarity** control (family 1)", whereas the runner blocks that family and uses
`completely_random_facet`. This clarification resolves that, prospectively — it is **not** a post-hoc result
change (nothing has been executed):

- **B1.9 is resolver-free and does NOT perform binding/liberating pole selection.**
- Therefore **`same_polarity_random_varna_facet` is blocked/reserved** unless a future **pole-bearing variant is
  explicitly preregistered** (which would reintroduce the resolver and must be a separate prereg).
- **The primary executable control for this runner is now `distant_source_word_mapping`** (§8c/§12d) — control =
  a different real word W′'s OWN authentic varṇa mapping, W′ chosen by target/context distance only. This
  supersedes the "family 1 / same-polarity" phrasing in §10 and both interim clarifications
  (`completely_random_facet`, then `out_of_pool_lexicon_facet`). `out_of_pool_lexicon_facet` is retained as a
  **secondary external-register** control; `completely_random_facet` as a **within-pool secondary/triangulation**
  control. §10's endpoint definition is otherwise unchanged.
- **`out_of_pool_lexicon_facet`, `completely_random_facet`, `same_plane_random_varna_facet`,
  `frequency_length_matched_facet` (length-only), `permuted_target_label`, and `random_word_context_decoy`**
  remain **secondary/control-family analyses**.
- **All implemented controls must be reported** (not cherry-picked) — consistent with §10.
- This is a **pre-execution clarification, not a post-hoc result change** (nothing has been executed under the
  reopened design). B1.4b′ remains `NULL_RETURN_BOTTOM`.

### 12c-i. Reopened-fix note (in place; NOT a new B1.10 track)

Per the operator instruction to **reopen and fix B1.9 in place** (not increment to a new experiment), the runner,
the frozen sampler config, and this prereg were amended across two turns: first adding the **out-of-pool** control,
then adding the **distant-source-word mapping** control (§8c/§12d) and making it the primary; the out-of-pool
control was demoted to a reported secondary. This is the same B1.9 track — same generation-free, judge-free
embedding design, same items, same statistics — with the control content source corrected. The real test has
still **not** been run; the runner emits only `B1_9_CONTENT_DISTANCE_RUNNER_READY_MOCK_TESTED`.

## 12d. Corrected primary control — distant-source-word mapping (IMPLEMENTED, mock-tested — NOT run)

**Status update:** this control is now **implemented as the PRIMARY family** (`distant_source_word_mapping`),
mock-tested (fake embeddings) only. **No real test has been run; the prior B1.9 result record is unchanged; no
B1.10 file exists. No rescue is claimed.** It **supersedes** the out-of-pool lexicon control (§8b, now a reported
secondary).

**Why the §8b out-of-pool lexicon control is not the main correction.** It reuses no varṇa mapping (good), but its
glosses are a *different register* (concrete/sensory vs abstract-psychological), so a positive delta against it
is confounded by register (§8b already flags this). The corrected control removes that confound by keeping the
control on the **same varṇa-mapping construction** as authentic.

**Corrected control — another real word's own authentic varṇa-derived mapping, chosen distant.** For each target
word `W` (with its context):

- **authentic** = facets from `W`'s **own** varṇa mapping (unchanged);
- **control** = facets from a **different real source word `W′`'s own** authentic varṇa mapping — i.e. `W′`'s
  full varṇa-derived facet set, constructed exactly as authentic is (same pipeline, same register);
- **`W′` is selected as semantically DISTANT from `W`'s target/context**, using **only** target/context
  embedding distance — **never** facet distance (this preserves the §6 anti-circularity rule: the control choice
  never references `d_auth` or facet-space outcomes);
- **freeze the `W → W′` assignment before computing any outcome** (frozen alongside the item set and hashes);
- **endpoint:** `delta = distance(rep(W), facets(W′)) − distance(rep(W), facets(W))`; positive favors authentic,
  identical in form to §4.

**Source pool for `W′`.** A frozen word list (e.g. the B1.9 targets themselves and/or a larger frozen vocabulary
with varṇa mappings), so that `W′` is a genuine word with a genuine mapping — not a random within-pool facet
scramble and not an out-of-register lexicon gloss.

**Anti-circularity, restated for this control.** `W′` is chosen by **target/context distance only**; the facet
distances that enter the endpoint are computed **after** the `W → W′` map is frozen. Selecting a *distant word*
by context is **not** selecting on `d_auth`, so it does not self-fulfill the outcome (contrast with the B1.8
clean-subset flip, which selected on `d_auth < d_scram` and was circular).

**Implementation (this turn).** Added as family `distant_source_word_mapping` (primary) in
`run_b1_9_content_distance.py`; W→W′ frozen by `_freeze_distant_source_map` using target/context embeddings only;
per-item output records `source_word_id`. Frozen sampler config `primary_family` updated; out-of-pool demoted to
secondary. Tests (27 total) cover: primacy, W′≠W, selection-uses-target/context-only (source-inspected: no
`facet`, no `d_auth`), determinism, and `delta = d_control − d_auth`. **Mock-tested only.**

**Status.** `B1_9_CONTENT_DISTANCE_NOT_RUN` still holds; runner still emits only
`B1_9_CONTENT_DISTANCE_RUNNER_READY_MOCK_TESTED`. Any **real** run is deferred to a later turn on explicit
request. B1.4b′ remains `NULL_RETURN_BOTTOM`.

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
