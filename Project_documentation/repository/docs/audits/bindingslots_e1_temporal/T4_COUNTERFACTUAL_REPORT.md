# E1 latest-state (T4) shortfall — zero-training counterfactual attribution

**Mechanical conclusion (frozen rule): `T4_SHORTFALL_MIXED`.** Value-path secondary invariant: **not
triggered** (D4 value read is perfect).
**Always preserved: `E1_TEMPORAL_TRANSFER_PARTIAL` · `ORIGINAL_BINDINGSLOTS_NEURAL_ROUTING_UNRESOLVED` ·
`KDA_VALIDATION_BLOCKED`.** No `…_VALIDATED`/`…_CONFIRMED`/`…_ELIGIBLE` emitted. T5 stays outside.

Zero new training / zero optimizer steps. All arms ran the **frozen E1** (deterministic replay; param
hashes **byte-identical** to committed for all 5 seeds) on the **exact committed T4 episodes** (reserved
seeds 6140–6144). **D0 reproduces the committed T4 addressing.** Arm definitions and the attribution
rule were frozen **before** any aggregate was read (`cf_spec.py` / `T4_COUNTERFACTUAL_PROTOCOL.md`).

## Arm results (750 T4 queries; 294 D0 failures)

| arm | correct-latest | value | recovery of D0 failures |
|---|---|---|---|
| **D0** frozen E1 (keys+null) | 0.608 | 0.623 | — (reference) |
| **D1** null-suppressed | 0.789 | 0.815 | **0.463** |
| **D2** correct-entity + null | 0.613 | 0.624 | 0.014 |
| **D3** correct-entity + null-suppressed | 0.875 | 0.892 | **0.680** |
| **D4** oracle latest → value | 1.000 | **1.000** | 1.000 |
| **D5** metadata latest-by-position | 1.000 | 1.000 | 1.000 |

**Components of the D0 shortfall:** abstention **0.463**, entity retrieval **0.218**, within-entity
latest ranking **0.320** — all ≥ 0.20, no single primary rule met → **MIXED**. `within_entity_latest_d3`
= 0.875 (below the 0.90 entity-primary bar). **D4 value-fail rate = 0.000** → the value/read path is not
implicated.

## Transition tables (D0 failure → outcome)
- **→ D1 (null-suppressed):** of 229 `NULL_OR_ABSTAIN`, **136 → correct-latest**, 63 → wrong-entity, 30 →
  older; 50 `RIGHT_ENTITY_WRONG_OLDER` stay older; 15 `WRONG_ENTITY` stay wrong-entity.
- **→ D3 (correct-entity + null-suppressed):** of 229 abstentions, **189 → correct-latest**, 40 → older;
  11 of 15 wrong-entity recover; 50 older-step remain older (unrecoverable within-entity latest failures).

## Interpretation (bounded; causality not inferred from accuracy alone)
The T4 shortfall is **genuinely mixed**, with three contributing mechanisms and a clean null result on
the fourth:
1. **Over-abstention (~46%)** — the learned null key outscores real records on uncertain latest queries;
   suppressing it alone lifts correct-latest from 0.608 to 0.789. Notably **D2 (correct-entity, null
   allowed) recovers only 1.4%**: even restricted to the correct entity, the model prefers the null key —
   abstention is a first-order driver, not a byproduct.
2. **Entity-retrieval degradation under the predicate (~22%)** — the additional recovery from D1→D3
   (restricting to the correct entity) shows wrong-entity competition on latest queries beyond abstention.
3. **Within-entity latest ranking (~32%)** — even confined to the correct entity, an **older** record
   outscores the latest in ~1/8 of all queries (D3 = 0.875); these 50 residual failures are true
   latest-ranking errors.
4. **Value/read path — not a factor** (D4 = 1.000): once the correct latest record is addressed, the
   stored value is returned correctly.

## Recommendation (from the mechanical MIXED)
A future **preregistered factorial** that separately isolates and gates **(1) null-gating/abstention,
(2) entity retrieval under a predicate token, and (3) within-entity latest ranking** — rather than a
capacity-vs-order dichotomy, since all three contribute and the value path is clean. Anything further
requires its own preregistration and authorization; **nothing is started.** T5 predecessor/successor is
explicitly outside this recommendation.

## Integrity
Byte-identical param hashes (5/5) + D0 reproduces committed T4; no optimizer step; no model/seed/gate/
prediction/verdict changed; new diagnostic evidence stored separately from prior evidence; frozen
`abc.json` unchanged; the merged `E1_TEMPORAL_TRANSFER_PARTIAL` verdict and all prior evidence stand.
