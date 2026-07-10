# B1.8 — Semantic-Overlap Confound Audit + Preregistered Fix (docs-only)

**Status:** diagnostic + design recommendation. **Docs-only. Results are NOT changed, NOT re-scored, NOT
tuned.** The B1.8 ratings-freeze and aggregate stand as recorded. This audit examines *why* the
`KCPR_SELECTED_POLE vs SCRAMBLED_SELECTED_POLE` specificity lean (+0.29, exploratory) does not survive
inspection, and specifies a stronger control for any future run.

**B1.4b′ remains `NULL_RETURN_BOTTOM`.** Original B1.4b blocked; Track B blocked. Structure, not validated meaning.

---

## 1. The problem (why the scramble is a weak negative control)

`SCRAMBLED_SELECTED_POLE` derives its content by a **seeded derangement over varṇa keys** — each varṇa's facet
is replaced by a *different* varṇa's same-pole facet. This guarantees the content is *not the target varṇa's*,
but it does **not** guarantee the content is **semantically distant** from the target. The varṇa pole-facet pool
is a small set of broadly-applicable psychological/spiritual concepts (effort, escapism, withdrawal, clinging,
clarity, release, inertia, attachment, …). Many of these are apt for many targets. So a "random" facet is
frequently **coincidentally target-relevant**, and the negative control collapses toward the authentic arm in
relevance. When authentic and scrambled are *both* plausible for the target, `specificity_to_target` cannot
distinguish them — the contrast is confounded and underpowered. (Operator's framing: *if "dread" and "fear" are
treated as equivalent content, the scramble carries the same meaning and there is nothing to differentiate.*)

## 2. Lexical-overlap diagnostic (computed from the frozen scaffolds; reproducible, no model)

Content-word overlap between `TARGET_TEXT + CONTEXT_TEXT` and each arm's facet texts (stopword-filtered):

| item | target | decision | \|C\| | authentic∩C | scrambled∩C | note |
|---|---|---|---|---|---|---|
| b18-01 | bridge | liberating | 16 | 0 | 1 | scr ≥ auth |
| b18-02 | lantern | binding | 9 | 0 | 0 | tie (0/0) |
| b18-03 | grief | binding | 6 | 0 | 0 | tie (0/0) |
| b18-04 | longing | liberating | 9 | 0 | 0 | tie (0/0) |
| b18-05 | justice | liberating | 10 | 1 | 1 | scr ≥ auth |
| b18-06 | balance | binding | 12 | 0 | 0 | tie (0/0) |
| **b18-07** | **lotus** | liberating | 8 | **3** | 0 | **authentic context-echo** |
| b18-08 | sacred | binding | 9 | 2 | 2 | scr ≥ auth |
| b18-09 | Lumen | liberating | 10 | 0 | 0 | tie (0/0) |
| b18-10 | Nova | binding | 10 | 1 | 0 | auth > scr |
| b18-11 | wonder | liberating | 10 | 1 | 2 | scr ≥ auth |
| **b18-12** | **dread** | binding | 10 | **0** | **0** | **semantic (not lexical) confound** |

**Reads:**
- **Authentic out-overlaps scrambled lexically in only 2/12 items** (lotus 3>0, Nova 1>0); strongly in **one**
  (`lotus`). So the +0.29 specificity lean is **not** primarily a lexical-echo effect — except for `lotus`,
  whose authentic `sa` facet ("**clarity; peace; release**; mokṣa…") literally restates the context ("contemplative
  **clarity**, **release**, and **peace**"). That single context-echo (partly circular: the context was authored
  with *liberating* cues, and `sa`'s liberating pole uses those same words) inflated the biggest "win."
- **`dread` is the decisive counter-example, and it is invisible to lexical overlap (0/0).** The scrambled facet
  "escapism; premature static withdrawal; inert" is *semantically* the apt description of "trapped, rigid,
  unable to move," so the **random** control scored *higher* on specificity than authentic ("peevishness /
  irritability," a poor fit for dread). Lexical matching cannot detect this; **semantic distance can.**

**Conclusion:** the confound is **semantic, not lexical.** The current derangement controls varṇa identity but
not semantic distance, so scrambled facets are often coincidentally target-aligned. Averaged over 23 pairs the
authentic-vs-scrambled specificity difference nets to a small +0.29 — noise around a semantic-coincidence
effect, consistent with the composite being a wash (11–10). Seeing the text **deflates** the specificity signal.

## 3. Recommended preregistered control: semantic-distance-constrained scramble

For any future (powered) run, replace the plain derangement with a **semantic-distance-constrained** negative
control, frozen before generation:

1. **Embed every varṇa pole-facet** (and each `TARGET_TEXT + CONTEXT_TEXT`) with a fixed sentence-embedding
   model (e.g. `all-MiniLM-L6-v2`, hash-pinned).
2. **Constrained derangement:** map each varṇa `v` → a varṇa `w` (same pole) such that `w`'s facet is
   **embedding-FAR** from *both* (a) `v`'s authentic facet and (b) the item's `TARGET_TEXT + CONTEXT_TEXT`,
   above a **preregistered distance floor** `τ` (e.g. cosine distance ≥ 0.5), with no fixed points. If no
   assignment satisfies `τ` for an item, mark it `REFUSE_UNSEPARABLE` and exclude it (do not relax `τ` post-hoc).
3. **Freeze** the constrained mapping, `τ`, the embedding-model hash, and the per-item distances **before**
   generation. This makes the scramble a *genuine* semantic negative control: authentic content is now the word's
   own facet, scrambled content is guaranteed semantically distant.
4. **Covary the residual overlap:** record, per output, the lexical and semantic overlap between
   `TARGET_TEXT+CONTEXT_TEXT` and the rendered facets, and include it as a **nuisance regressor** in the
   analysis, so any surviving `specificity_to_target` effect is adjusted for context↔facet overlap.
5. **Optional matched-distance arm:** a second control whose facets are held at a *fixed* distance band from the
   target (neither very near nor very far), to separate "authentic > distant" from "near > far."

**Interpretation under the fix:** only if `KCPR_SELECTED_POLE` beats a **semantically-distant** scramble on
`specificity_to_target`, *after* covarying overlap, would authentic varṇa content show target-appropriateness
beyond coincidence. If it does not, the specificity thread is closed as a semantic-coincidence artifact.

## 4. Honest bearing on the B1.8 result (unchanged)

This audit **does not alter** the recorded B1.8 outcome: context-resolved Symbol-U was no better than its
scramble on the composite (11–10), **no better than the unresolved both-poles dump** (−0.002; Layer-1 added
nothing), and **worse than plain/generic/semantic baselines**. The one apparent bright spot —
`specificity_to_target` +0.29 — is, on inspection, a **context/semantic-overlap artifact** (lotus lexical echo;
dread semantic coincidence favoring the scramble), not evidence of word-specific varṇa meaning. The proper next
step is **not** to run the powered test as previously designed, but to first adopt the semantic-distance-
constrained control above; otherwise the primary endpoint measures overlap, not meaning.

## 4b. Post-hoc "clean-subset" flip — and why it does NOT rescue B1.8 (circular selection)

A follow-up asked whether restricting the primary contrast to items with a *valid* (semantically distant)
scramble would flip the result. Using an embedding distance `d = 1 − cos(target+context, facet-aggregate)` and a
"clean" cut `d_scram − d_auth > margin`, the paired `KCPR_SELECTED_POLE vs SCRAMBLED_SELECTED_POLE` result
(all figures **exploratory, post-hoc**):

| clean cut | items | composite (win-rate, mean_diff) | specificity (win-rate, mean_diff) |
|---|---|---|---|
| ALL | 12 | 0.478, +0.08 | 0.522, +0.29 |
| `d_scr − d_auth > 0` | 8 | 0.533, +0.13 | 0.533, +0.36 |
| `> 0.03` | 6 | 0.545, +0.16 | 0.545, +0.46 |
| `> 0.06` | 4 | 0.625, +0.26 | 0.625, **+0.67** |

**Directionally, authentic improves as the clean-control margin tightens.** But this is **post-hoc and not
confirmatory**, and — more importantly — **the selection rule is circular:**

- `d_auth < d_scram` selects items where the **authentic facet content is already closer** to the
  target/context than the scrambled facet content.
- `specificity_to_target` then measures whether the **output** is more target-specific.
- Because the output is generated **from the selected input facets**, this mostly says *"more target-relevant
  input yields more target-specific output."*
- That is true for **any** content source and does **not** establish that the varṇa mapping carries meaning.
  The specificity flip is expected under this selection whether or not the hypothesis is true.

**Non-circular summary (measured over all 12 items, no selection):**
- Mean `d_auth = 0.744`; mean `d_scram = 0.770`.
- Authentic closer in **8/12** items.
- Approximate lean: **~0.026 cosine distance** (8/12, sign-test p ≈ 0.19).
- Interpretation: **weak, non-significant, consistent with the B1.4b′ null.**

**Conclusion:**
- The post-hoc flip **does not rescue B1.8.** It is partly a circular selection artifact and is non-significant
  even at the tightest cut (composite 5–3; specificity 5–1 of 6 decisive).
- It shows concretely **why B1.8's scramble control was not semantically distance-controlled**, and it motivates
  a **prospective, generation-free** B1.9 design (`B1_9_CONTENT_LEVEL_SEMANTIC_DISTANCE_PREREG.md`) that measures
  the mapping directly and **forbids** selecting the analysis subset with a variable upstream of the outcome.
- **B1.8 remains null/negative for broad generation utility.** The `specificity_to_target` thread remains
  **exploratory and methodologically unresolved — not evidence.** B1.4b′ remains `NULL_RETURN_BOTTOM`.

## 5. Guardrails

Docs-only. Results not changed, not re-scored, not tuned. No generation run; no evidence freeze; no judging; no
ratings change; no `GENUTILITY_*`; no semantic-truth claim; no ontology; no Sanskrit privilege. **B1.4b′ remains
`NULL_RETURN_BOTTOM`**; original B1.4b blocked; Track B blocked. Structure, not validated meaning.

---

## Final report

- **File created:** `experiments/primitive_sequence_recovery/B1_8_SEMANTIC_OVERLAP_CONFOUND_AUDIT.md` (docs-only).
- **Commit hash:** recorded on the commit below.
- **Finding:** the `SCRAMBLED_SELECTED_POLE` control is not semantically distance-controlled; scrambled facets
  are frequently coincidentally target-aligned. Lexical overlap flags only `lotus` (context-echo); the decisive
  case `dread` is a *semantic* coincidence invisible to lexical measures. The +0.29 specificity lean is an
  overlap artifact, not meaning.
- **Recommendation:** a preregistered semantic-distance-constrained scramble (embedding-based constrained
  derangement with a frozen distance floor `τ`, overlap covaried, matched-distance option) before any powered run.
- **Results changed / re-scored / tuned?** No.
- **B1.4b′ remains `NULL_RETURN_BOTTOM`.**

B1.8 semantic-overlap confound audit documented docs-only. No results changed. No re-scoring. No tuning. No
generation run. No evidence freeze. No judging. No GENUTILITY terminal label. B1.4b′ remains NULL_RETURN_BOTTOM.
Original B1.4b remains blocked. Track B remains blocked. Structure, not validated meaning.
