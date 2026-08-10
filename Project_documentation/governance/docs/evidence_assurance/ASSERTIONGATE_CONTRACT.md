# EvidenceAssurance → AssertionGate Contract (Phase 14)

*`evidence_assurance/adapter.py`. This is the **only** coupling between the two components. It exists
to keep the boundary honest: EvidenceAssurance establishes the **evidence state**; AssertionGate
decides **delivery**. The adapter carries the disposition across, applying the one piece of context
EvidenceAssurance does not own — the decision's risk tier.*

## The contract

1. **EvidenceAssurance emits a disposition**, one of the eleven `EvidenceState` values, plus the
   `DELIVERY_EFFECT` it implies (`taxonomy.py`) and reason codes.
2. **The adapter finalizes delivery** by applying risk escalation: for a `high`/`critical`-risk
   decision, a soft withhold (`INSUFFICIENT` / `DEPENDENT` / `STALE`, whose default effect is
   `QUALIFY` / `INDETERMINATE`) is raised to `ESCALATE`. Nothing else is re-derived.
3. **AssertionGate stays thin.** `thin_assertion_gate` routes purely on the delivery decision —
   surface / caveat / escalate / withhold — with **no evidence logic of its own**. The evidence state
   was already established upstream; the gate does not re-open it. This is the point of the split.

```
case ──EvidenceAssurance.assess──▶ AssuranceResult(state, delivery_effect, codes)
                                        │
                                   adapter.to_delivery(·, risk_class)   ← risk tier applied here
                                        │
                                        ▼
                            DeliveryDecision(delivery ∈ {ALLOW,QUALIFY,REJECT,ESCALATE,INDETERMINATE})
                                        │
                              thin_assertion_gate(·)   ← no evidence logic, pure routing
```

## Delivery mapping

| EvidenceState | default effect | high/critical-risk override |
|---|---|---|
| `VERIFIED` | ALLOW | — |
| `VERIFIED_WITH_LIMITATIONS` | QUALIFY | — |
| `DEPENDENT` | QUALIFY | **ESCALATE** |
| `STALE` | QUALIFY | **ESCALATE** |
| `INSUFFICIENT` | INDETERMINATE | **ESCALATE** |
| `CONFLICTED` | ESCALATE | — |
| `AUTHORITY_MISMATCH` | ESCALATE | — |
| `MISALIGNED` | REJECT | — |
| `REJECT_EVIDENCE_STATE` | REJECT | — |
| `INDETERMINATE` | INDETERMINATE | — |
| `ESCALATE` | ESCALATE | — |

Only `ALLOW` and `QUALIFY` surface the claim as supported. `DEPENDENT`/`STALE`/`INSUFFICIENT` are the
soft withholds that risk escalates.

## Measured (ea_corpus_v1_1, full path case → disposition → delivery)

- **Delivery-level escape: 0** — the thin gate never surfaces a claim as supported when the gold
  delivery withholds it (REJECT / INDETERMINATE / ESCALATE). This is the safety invariant the contract
  must preserve, and it holds end-to-end, not only at the disposition layer.
- **Delivery exact accuracy: 0.808** vs gold delivery. Every mismatch is conservative:
  - `REJECT ← gold ESCALATE` / `REJECT ← gold QUALIFY|ALLOW` — over-withholding (the 15 NLI-noise
    false-blocks plus high-risk cases refused rather than escalated). Safe direction.
  - `ESCALATE|INDETERMINATE ← gold REJECT` (79 cases) — the correlated-failure boundary: the trap is
    routed to human review or "cannot decide" rather than named a hard reject. Still withheld, still
    zero escape.
- **No mismatch surfaces a withheld claim.** There is no cell where the adapter delivers `ALLOW`/
  `QUALIFY` against a gold withhold.

## Why the gate stays thin — and why that matters

If AssertionGate had to re-derive independence, provenance, or alignment, the correlated-failure logic
would be duplicated in two places and could drift. The contract localizes all evidence reasoning in
EvidenceAssurance and leaves AssertionGate a pure policy router. The test suite asserts the thin gate
takes no path that depends on evidence internals — only on the `DeliveryDecision`.
