# E1 latest-state (T4) transfer-failure error-structure analysis

**Mechanical conclusion (frozen rule): `T4_ERROR_ANALYSIS_INCONCLUSIVE`.**
**Always preserved: `ORIGINAL_BINDINGSLOTS_NEURAL_ROUTING_UNRESOLVED` · `KDA_VALIDATION_BLOCKED`.**
No transfer-validation verdict is emitted; the merged **`E1_TEMPORAL_TRANSFER_PARTIAL`** verdict is
unchanged. T5 predecessor/successor is explicitly outside this conclusion.

Zero new training: per-query T4 predictions were recovered by **deterministic replay** of the frozen E1
for each reserved seed 6140–6144 — **param hash byte-identical** to the committed `e1_param_sha256` for
all 5 seeds (verified) — then inference on the identical committed T4 episodes. The classification
categories and the mechanical conclusion rule were **frozen before** any aggregate was read
(`t4_error_spec.py` / `T4_ERROR_CLASSIFICATION_SPEC.md`).

## Result — the failure is NOT cleanly "latest-selection"; it is abstention-heavy and mixed
Across 5 seeds (750 T4 queries), **294 end-to-end failures** (predicted index ≠ latest record index):

| failure category | share |
|---|---|
| `NULL_OR_ABSTAIN` (null key chosen despite a matching memory) | **0.779** |
| `RIGHT_ENTITY_WRONG_OLDER_STEP` | 0.170 |
| `WRONG_ENTITY` | 0.051 |
| `INVALID_OR_OTHER` | 0.000 |

Under the frozen rule (≥70% one category, or ≥80% combined latest+entity), **no category qualifies**
(abstention has no bucket; latest+entity combined = 0.221) → **`INCONCLUSIVE`**. This is the faithful
mechanical output; the rule was not changed after seeing the data.

## Supplementary instrumentation (per the INCONCLUSIVE recommendation; NOT part of the frozen conclusion)
The frozen conclusion is on the **end-to-end** decision (null included). Separating the abstention
decision from the key-ranking decision that the T4 gate actually measured (addressing, null-excluded):

- **Abstention rate over all T4 queries: 0.305** — the frozen model abstains on ~30% of latest-state
  queries (far more than on at-step T3), the single largest failure driver.
- **Addressing-only failures (null-excluded): 158** (≈ the committed T4 addressing gap, 1−0.789).
  Among these: **right-entity/wrong-older 0.506, wrong-entity 0.494** — a ~50/50 split, i.e. even the
  pure key-ranking errors are **half entity-retrieval degradation** on latest queries, not purely
  latest-selection.
- **At-step control:** for **92%** of failures, an explicit at-step query for the same target record is
  retrieved correctly — the record is *findable*; the "latest" predicate specifically degrades
  behaviour (abstain, older step, or lose the entity).
- Correct-latest record rank: mean **1.49**, median **1.0**; a **different same-entity record outranked
  the target 32%** of the time; failures **increase with events-per-entity** (2→3→4).

## Interpretation (bounded; causality not inferred from aggregate accuracy alone)
The evidence **refutes the simple hypothesis** that T4 fails purely because latest-selection is
unlearned. The dominant end-to-end driver is **over-abstention on latest queries**, and even among
non-abstained addressing errors the split is ~50/50 latest-selection vs entity-retrieval degradation.
The at-step control shows the target is findable given an explicit step, so the "latest" predicate is
the locus of difficulty — but it manifests through **three coupled decisions** (abstain-vs-answer,
entity match, and within-entity latest ranking), not one.

## Decision recommendation (from the mechanical INCONCLUSIVE)
Per the frozen mapping, INCONCLUSIVE → **identify the minimum additional instrumentation needed; do NOT
run a new experiment.** Concretely, before any capacity or order-aware arm, a future analysis/protocol
should **decouple and separately gate the three decisions** — (1) null-gating / abstention on temporal
queries, (2) entity retrieval under a predicate token, (3) within-entity latest ranking — e.g. by
logging the null-margin, the entity-match rank, and the same-entity latest rank per query, and extending
the classification rule with an abstention-dominated bucket. The present data does **not** cleanly
justify either a pure capacity arm or a pure order-aware arm; if the program continues, the
`E0` vs capacity-only vs order-aware experiment remains the appropriate design, but it should also
address the abstention interaction surfaced here. Anything further requires its own preregistration and
authorization; nothing is started.

## Integrity
Replay byte-identical (5/5 param hashes match committed); no model/seed/gate/metric/verdict changed;
frozen `abc.json` unchanged; the merged temporal verdict and all prior evidence stand.
