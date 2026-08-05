# T4 counterfactual-diagnostic protocol (frozen before aggregate results)

Zero-new-training attribution of the T4 latest-state shortfall to its components. All arms run the
**frozen E1** (deterministic replay, param hash **byte-identical** to the committed PR #1354/#1355
evidence) on the **exact committed T4 episodes** (reserved seeds 6140–6144). **No optimizer step, no
weight change, no dataset regeneration, no change to prior predictions/evidence/verdict.** Oracle
information is **diagnostic-only** and never a deployable policy. Machine spec: `cf_spec.py`.

## Arms (identical committed T4 episodes)
- **D0** — ordinary frozen E1 (argmax over 32 keys + null). **Reference; must reproduce the committed T4
  predictions byte-for-byte.** Fail closed otherwise.
- **D1** — null-suppressed read (argmax over the 32 real keys only). Max gain from suppressing abstention.
- **D2** — correct-entity restricted (argmax over {correct-entity records, null}); uses evaluator entity
  identity (oracle).
- **D3** — correct-entity + null-suppressed (argmax over correct-entity records only). Pure within-entity
  latest ranking.
- **D4** — correct-latest oracle read (select the ground-truth latest record; return its stored value via
  the existing read path). Value/read-path check; the answer is never inserted directly.
- **D5** — correct-entity latest-by-position (metadata max position among correct-entity records; return
  its value). Upper bound of a simple explicit latest selector; **not** evidence of a learned order-aware
  mechanism.

## Permitted oracle information per arm
D0/D1: none. D2/D3: ground-truth entity identity only (not the event position or answer). D4: ground-truth
latest record index. D5: episode position metadata for the correct entity. No arm inserts the answer.

## Frozen attribution rules (fixed before any aggregate is read)
Let recovery `Dx_rec` = fraction of D0 failures that become correct-latest under Dx. Components over D0
failures: `abstention = D1_rec`; `entity = max(0, D3_rec − D1_rec)`; `latest = 1 − D3_rec`.
- `T4_SHORTFALL_PRIMARILY_ABSTENTION`: D1_rec ≥ 0.60 and (D2_rec−D1_rec) < 0.15 and (D3_rec−D1_rec) < 0.15.
- `T4_SHORTFALL_PRIMARILY_ENTITY_RETRIEVAL`: max(D2_rec,D3_rec) ≥ 0.60 and the majority of recovered
  failures originated from wrong-entity (or null→wrong-entity under D1) and within-entity latest under D3
  ≥ 0.90.
- `T4_SHORTFALL_PRIMARILY_LATEST_RANKING`: D3_rec ≥ 0.60 and D1_rec < 0.40 and, in the residual, the
  correct entity is available but the original scores rank an older record above the latest in the
  majority.
- `T4_SHORTFALL_MIXED`: ≥ 2 of {abstention, entity, latest} each ≥ 0.20 of D0 failures and no primary rule met.
- `T4_SHORTFALL_VALUE_PATH`: D4 fails on > 10% despite the correct latest record (primary only if ≥ 50%,
  else emitted as a secondary invariant).
- `T4_COUNTERFACTUAL_INCONCLUSIVE`: none of the above, or metadata insufficient, or D0 not byte-identical,
  or an oracle arm cannot be validated.

Exactly one primary conclusion is emitted. Always preserved: `E1_TEMPORAL_TRANSFER_PARTIAL`,
`ORIGINAL_BINDINGSLOTS_NEURAL_ROUTING_UNRESOLVED`, `KDA_VALIDATION_BLOCKED`. Never emitted:
`E1_TEMPORAL_TRANSFER_VALIDATED`, `E1_STRUCTURAL_TRANSFER_CONFIRMED`, `E1_FOLLOW_ON_RESEARCH_ELIGIBLE`. T5
predecessor/successor stays outside the conclusion and the recommendation.
