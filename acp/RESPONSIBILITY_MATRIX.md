# Responsibility Matrix (V2.2 §7)

Separation-of-responsibility proof for the AI Control Plane. Each layer owns a
disjoint concern; none duplicates or overrides another. Verified structurally
(source scans in `run_control_plane_bench.py` + `test_control_plane.py`):
**duplicated-logic count 0, ownership violations 0.**

| layer | owner of | inputs | outputs | authority | failure mode |
|---|---|---|---|---|---|
| **Context Minimization** | *relevance* — what the model needs to see | original context (spans) + protect_fn + signed policy | reduced context (surviving spans) | **none** — preprocessing; never authorizes, never judges safety | fail-closed: restores necessary spans / returns full original (`fell_back`); never silently drops a protected span |
| **LLM stage (reader)** | *proposal* — what action to take | reduced context | proposed `KubernetesOperation` | **none** — proposes only | `INSUFFICIENT_CONTEXT` if a critical span is gone (no action proposed) |
| **ActionGate** | *authorization* — may this be done? | proposed action → envelope, signed policy, evidence, approvals, state hash | outcome + action_hash + dispositive rules | **authorization authority** (sole) | `DENY` / non-final; never evaluates operational readiness |
| **ACP** | *operational safety* — is it safe now? | same action → `CloudWorldState` + `CloudActionCandidate` | recommendation + evidence + trace | **operational-safety evaluator** (sole) | `HOLD` / `REOBSERVE`; never authorizes |
| **Composition** | *combination* — link the verdicts | ActionGate outcome + ACP result (identity-bound) | one of 8 classes + eligibility | **none** — links, never overrides | `COMPOSITION_IDENTITY_MISMATCH` / `SHADOW_ERROR` |

## The non-duplication guarantees (structural, source-scanned)

- **Context Minimization never authorizes and never judges operational safety.**
  Its only "decision" concept is preserving the *ActionGate decision invariance*
  of the compression (it calls the gate to check it didn't corrupt the decision) —
  it does not itself grant or deny.
- **ActionGate never evaluates operational readiness.**
  `action_gate_ref/gate.py` contains no `ReadinessChecker` / capacity / freeze
  logic (asserted: `I3`).
- **ACP never authorizes.** No path makes an operation eligible unless ActionGate
  authorized it (asserted: `I4`); ACP mints no token.
- **No duplicated approval/replay/nonce ownership** (V2.1 `I9`) and **no duplicated
  operational-readiness ownership** (V2.1 `I10`) — carried forward.

## Why disjoint ownership matters

If two layers owned the same concern, one could silently override the other and
the "both must pass" guarantee would be hollow. The matrix above is disjoint by
construction: relevance ⟂ proposal ⟂ authorization ⟂ operational safety. That is
what lets the composed result be trusted — each class is attributable to exactly
one owner's verdict.
