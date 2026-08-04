# Stage-1 selection decision (mechanical)

Source: `results/stage1_selection_decision.json`, `results/stage1_aggregate.json`.

## Full single-arm gate (per preregistration)

clean-stable ≥ 4/5 ∧ wins-vs-R0 ≥ 4/5 ∧ every final former causally clean ∧ collapse ≤ 1/5 ∧
routing-unclean = 0 ∧ quality ∧ distance.

| arm | clean-stable | wins vs R0 | collapse | routing-unclean | clears? |
|---|---|---|---|---|---|
| R0 | 1 | 0 | 2 | 1 | ✗ |
| O1 | 0 | 3 | 0 | 5 | ✗ |
| O2 | 0 | 2 | 0 | 4 | ✗ |
| H3 | 0 | 2 | 2 | 1 | ✗ |

**No arm clears the full gate.** No objective arm clears the objective-family subgate (step-600
causal cleanliness fails — the routing is address-independent even at 600 for most seeds), and no
handoff arm clears the handoff subgate (H3 still collapses 2/5). So the combination trigger does not
fire either.

## Decision

`selected_candidate = None`. Because interventions form but remain routing-unclean and none exceeds
R0's clean-stable count, the diagnostic sub-verdict is **`ROUTING_PURITY_NOT_RESOLVED`** (not the
generic `NO_..._SELECTED`).

No candidate is frozen; no Stage-2 holdout is run. No tuning, no best-checkpoint selection, no
outcome-based seed replacement. Deferred arms (O3, H1, H2, O1R, C1) were not run.
