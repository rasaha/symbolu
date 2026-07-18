# PRE-REGISTRATION (DESIGN) — Primitive-Sequence Recovery (Realization-Factored)

**Status:** DESIGN draft. No implementation, no data, no run, no freeze. Frozen-on-commit applies to the artifact list only once a run is approved. Stage A not used, not modified.

**Supersedes** the English-only lexical-recovery framing. Built directly on the current ontology and `CANONICAL_PRIMITIVE_REPRESENTATION.md`.

**Excludes (by construction):** operators, polarity/intensity, coordinates, phonetics, stored relation `R`, semantic edge labels, hidden algebra. The only ontology is: **word → ordered varṇas → ordered opaque primitive atoms (`P*`)**; connectives are decode-time realization artifacts.

---

## 0. Why realization-factored
By the relabeling-invariance theorem (`CANONICAL_PRIMITIVE_REPRESENTATION.md` §3), the real-vs-scrambled assignment contrast is **invisible on the canonical `P*` alone** and becomes testable **only through a realization** that attaches content to the atoms. A single realization (e.g. English glosses) cannot separate an *ontological* effect from an artifact of that rendering. This design therefore **varies the realization** and reports only the **cross-realization-invariant** signal.

## 1. Scientific estimand
The component of the real-vs-scrambled meaning-ranking advantage that is **invariant across independent realizations** of the primitive atoms — i.e. the part of any recovered signal attributable to the **assignment** (`τ: Σ → P`) rather than to a particular content rendering.

## 2. Hypotheses
- **H0:** for every realization `R_j`, the real assignment gives no more ranking signal than scrambled (`Δ_j ≤ 0`); OR any positive `Δ_j` is not shared across realizations.
- **H1:** `Δ_j > 0` **for all** `R_j` — the real assignment beats scramble **invariantly** across renderings.

## 3. Ontology vs realization (fixed separation)
- **Ontology (frozen):** canonical primitive sequence `τ*(w) ∈ P*` — opaque atoms, order only.
- **Realization layer (declared, NOT ontology):** `m ≥ 3` independent, pre-frozen content-attachments `R₁,…,R_m`, each mapping every atom → a content object. Recommended, deliberately diverse to avoid a shared bias:
  - `R₁` = English gloss set;
  - `R₂` = original Sanskrit vṛtti term (transliterated);
  - `R₃` = a **language-neutral concept ID** (e.g. WordNet synset / Wikidata Q-ID);
  - `R₄` = an independent English **paraphrase** (different lexical choices);
  - `R₅` = a **third-language** gloss.

## 4. Task (independent / dependent variables)
- **IV (primary):** assignment — real `τ` vs scrambled `τ' = π∘τ` (`N_scram` seeds). **IV (secondary):** order preserved vs shuffled.
- **DV:** ranking of the word's true meaning `M(w)` among `K` matched distractors, scored by **Mean Reciprocal Rank (MRR)** (primary) and top-1 (secondary), under a fixed meaning-blind realizer.

## 5. Per-realization procedure
For each realization `R_j` and each assignment (real / scrambled):
1. render the atom sequence via `R_j` (no learned connectives; a fixed template or the concept-ID list);
2. embed with a frozen, meaning-blind encoder `g` (deterministic; for `R₃` use a graph/definition-based similarity);
3. rank `C(w) = {M(w)} ∪ 7 matched distractors} ` by similarity to the rendered sequence;
4. `MRR_real^{(j)}`, `MRR_scram^{(j)}`; `Δ_j = MRR_real^{(j)} − \bar{MRR}_scram^{(j)}`.

## 6. Frozen inputs (sha256 before analysis)
Assignment `τ` (the varṇa→atom table); word list `W` (`N ≥ 100`, single meaning-language, clean coverage) with ground-truth meanings `M`; the `m` realizations `R_j`; encoder(s) `g` + versions; distractor pool + matching rule (`K = 8`, matched on frequency/length/category); scramble seeds + `N_scram = 1000`; CV/bootstrap seeds; decision rule.

## 7. Controls & nulls
- **Assignment scramble** (primary null) — within each `R_j` (this is where scramble has teeth, since content is attached).
- **Order scramble** (secondary) — tests the "ordered" clause; only meaningful with an order-sensitive rendering/encoder.
- **Coherence control** — a "coherent-but-wrong" rendering, to check the encoder is not merely rewarding natural-phrase coherence.
- **Sanity** — random encoder → chance; identical-table → `Δ ≈ 0`.
- **Non-independence (Galton)** — family-aware bootstrap (resample shared-varṇa / etymological families, not words).

## 8. Statistics
Per realization: paired Wilcoxon on `MRR_real − \bar{MRR}_scram`; scramble-percentile gate (real > 95th pct); family-aware bootstrap 90% CI on `Δ_j`. **Confirmatory statistic = the cross-realization-invariant signal**, `Δ_min = min_j Δ_j` (equivalently: require the per-`j` positive verdict to hold for all `j`).

## 9. Decision labels
- **ONTOLOGICAL_SIGNAL** — `Δ_j > 0` (p<0.05, scramble-pct>95, CI lower>0) under **every** realization `R_j`. The assignment advantage survives re-rendering ⇒ a property of the representation, not the words used to render it.
- **REALIZATION_ARTIFACT** — `Δ_j > 0` for **some but not all** `R_j`. The signal depends on the specific rendering (e.g. English embedding geometry), not the ontology.
- **NO_SIGNAL** — `Δ_j ≤ 0` for all `R_j`.
- **REALIZER_DEPENDENT** — per-`j` verdict flips across *encoders within a realization* (encoder idiosyncrasy) → non-confirmation.
- **INCONCLUSIVE_LOW_POWER** — CIs span 0 with wide bounds.

## 10. Interpretation rules
- **English-only positive is NOT sufficient** — a positive under `R₁` alone is at most `REALIZATION_ARTIFACT`; ONTOLOGICAL_SIGNAL requires invariance across all `R_j`.
- **English-only NO_SIGNAL remains relevant but not final** — the prior English-gloss recovery null (`RESULTS_ACOUSTIC_SIGNAL.md`) is evidence within `R₁`; if no signal appears in *any* realization, that corroborates it, but the confirmatory claim is the cross-realization one.
- `REALIZATION_ARTIFACT` and `REALIZER_DEPENDENT` are **negatives**, never partial wins.

## 11. What it proves / does not
- **ONTOLOGICAL_SIGNAL** ⇒ the real varṇa→atom **assignment** carries meaning-ranking information invariant across renderings, beyond random assignments — a property of the representation. It does **not** prove the glosses are "correct," nor composition, nor any metaphysics.
- Any negative ⇒ under these realizations/encoders/word set/power, no realization-invariant signal beyond chance.

## 12. Prohibited researcher degrees of freedom
No post-hoc choice of realization, encoder, distractor set, or metric; no dropping words after seeing ranks; no reporting without family-aware resampling; no relabeling `REALIZATION_ARTIFACT`/`REALIZER_DEPENDENT` as partial success; no privileging `R₁` (English).

## 13. Hidden assumptions (carried, per prior critique)
Embedding similarity ≈ recoverable meaning; single well-defined meaning per word; concept-ID/definition similarity is a fair `R₃`; distractor difficulty comparable; family definition for resampling; "meaning-blind" encoders have no residual co-occurrence leakage; a bag/template rendering only weakly tests the "ordered" clause (order likely `ORDER_NULL`).

> structure, not validated meaning.
