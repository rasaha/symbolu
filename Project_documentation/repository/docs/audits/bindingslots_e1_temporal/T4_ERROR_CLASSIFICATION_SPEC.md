# T4 error-classification specification (frozen before reading the aggregate)

Zero-new-training analysis of the merged temporal-transfer evidence (PR #1354). Per-query T4 predictions
are recovered by **deterministic replay** of the frozen E1 for each reserved seed 6140–6144 — accepted
**only** when the replayed model's parameter hash is **byte-identical** to the committed
`e1_param_sha256` — then inference on the committed reserved T4 episodes. No model, seed, gate, metric,
result, or verdict is altered; the merged `E1_TEMPORAL_TRANSFER_PARTIAL` verdict stands.

## Categories (each T4 query → exactly one)
1. `RIGHT_ENTITY_RIGHT_LATEST_STEP` — correct latest record (consistency check; a *failure* in this
   category would signal a bug).
2. `RIGHT_ENTITY_WRONG_OLDER_STEP` — a valid record of the **correct entity**, but not its latest state.
3. `WRONG_ENTITY` — selected record belongs to a different entity.
4. `NULL_OR_ABSTAIN` — learned null key selected despite a matching memory existing.
5. `INVALID_OR_OTHER` — anything else (with written explanation).

A T4 query is a **failure** iff predicted index ≠ target (latest) record index. Failure categories =
{2, 3, 4, 5}.

## Frozen mechanical conclusion rule (fixed before any aggregate is read)
- `T4_FAILURE_PRIMARILY_LATEST_SELECTION` — ≥ **70%** of failures are `RIGHT_ENTITY_WRONG_OLDER_STEP`.
- `T4_FAILURE_PRIMARILY_ENTITY_RETRIEVAL` — ≥ **70%** of failures are `WRONG_ENTITY`.
- `T4_FAILURE_MIXED` — neither reaches 70%, but the two together explain ≥ **80%** of failures.
- `T4_ERROR_ANALYSIS_INCONCLUSIVE` — `INVALID_OR_OTHER` > **10%** of failures, or metadata insufficient.
- `T4_ERROR_ANALYSIS_PROTOCOL_VIOLATED` — replay not byte-identical.
- `T4_ERROR_ANALYSIS_RESOURCE_BLOCKED` — required artifacts/torch unavailable.

Always preserved: `ORIGINAL_BINDINGSLOTS_NEURAL_ROUTING_UNRESOLVED`, `KDA_VALIDATION_BLOCKED`. **No
transfer-validation verdict is emitted.** T5 predecessor/successor performance is **explicitly outside**
this conclusion.

## Per-query metadata recorded
predicted vs correct entity; predicted vs correct-latest event position; predicted vs correct-latest
status; rank of the correct latest record; whether another record of the correct entity outranked it;
number of records for that entity; a within-episode at-step (T3-style) control for the target entity;
top-1 score margin. Aggregates are reported per seed and overall, plus breakdowns by events-per-entity
and by temporal distance between the latest and prior event.
