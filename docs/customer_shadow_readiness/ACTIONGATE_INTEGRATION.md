# Real ActionGate Integration (M2)

*`customer_shadow_readiness/adapters/real_action_gate.py`. Resolves Gap 0: a validated **read-only**
invocation of the actual frozen ActionGate decision engine, replacing the pilot's `action_shadow_v1`
heuristic in this track's differential study. The pilot itself is unchanged.*

## The real decision engine (documented)

`action_gate_ref.gate.evaluate(envelope, signed_policy, *, evidence, approvals, now, used_nonces,
algorithm_id, identity_profile) -> dict`. Returns `{outcome, dispositive_rules, applied_constraints,
action_hash, policy_hash, state_trace, terminal, reason, hash_algorithm_id}`. Outcome ∈ {`ALLOW`,
`ALLOW_WITH_CONSTRAINTS`, `DENY`, `ESCALATE_TO_HUMAN`, `REQUEST_MORE_EVIDENCE`, `SIMULATE_AND_RETRY`}.
Raises `GateError` on malformed input.

## How the adapter obtains valid inputs

The real gate requires cryptographically signed policy, attested envelope, evidence, and approvals. The
adapter uses the reference package's **own read-only test builders** (`tests/helpers`) to construct
valid scaffolding — the only way to obtain a valid signed policy without minting real keys. Input
*presence* is driven by the pilot action proposal so the gate reaches a genuine decision:

- pilot `action_type` → canonical operation (`OP_MAP`; unmapped → `EXTERNAL_COMMS`, a high-consequence
  conservative default);
- `authority_granted` present → dual-control approvals attached; absent → no approvals;
- backup + signed-artifact evidence always attached (the gate then applies its own sufficiency checks).

The adapter does **not** re-implement any gate logic; it constructs inputs and forwards to the frozen
`evaluate`.

## Outcome → pilot shadow vocabulary (and the semantic loss it exposes)

| Real outcome | Pilot shadow disposition | Semantic loss |
|---|---|---|
| `ALLOW` | PERMIT | none |
| `ALLOW_WITH_CONSTRAINTS` | CONSTRAIN | **applied_constraints lost** |
| `DENY` | BLOCK | none |
| `ESCALATE_TO_HUMAN` | ESCALATE | none |
| `REQUEST_MORE_EVIDENCE` | INDETERMINATE | **evidence-request semantics collapsed** |
| `SIMULATE_AND_RETRY` | CONSTRAIN | **simulation-retry semantics collapsed** |

Three of the six real outcomes **cannot be represented** in the pilot's four-value shadow vocabulary.
The adapter records this as `semantic_loss` per the contract discipline — the differential study (M3)
quantifies how often it occurs. Both the real outcome (`source_repr`) and the mapped disposition
(`transformed_repr`) are preserved.

## Fail-closed guarantees

- `GateError` / malformed input → `shadow_disposition = BLOCK`, `real_outcome = GATE_ERROR`,
  `semantic_loss = [gate_error_fail_closed]` — a gate fault never yields a permissive outcome.
- An unmapped `action_type` maps to a high-consequence canonical operation (`EXTERNAL_COMMS`), not to a
  benign default — unknown actions are treated conservatively.
- Determinism: a fixed clock (`NOW`) and the reference builders make every evaluation reproducible.

## What this does not do

The real gate **decides**; the pilot **never executes**. This adapter is read-only and shadow-only:
it produces a disposition for comparison and audit, never an enforced authorization or an external
action. It is used only inside this readiness track's differential study — the frozen pilot's
`action_shadow_v1` remains byte-identical.
