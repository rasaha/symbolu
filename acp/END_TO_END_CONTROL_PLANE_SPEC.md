# End-to-End AI Control Plane Spec (V2.2 §1, §7)

The complete Ugence AI Control Plane as one integrated system: three frozen,
independent infrastructure layers executing sequentially on one enterprise
Kubernetes operation, in shadow mode. Code:
`robotics_reliability_bench/acp_control_plane/`.

## The pipeline

```
 Original Context
        │
        ▼
 ┌──────────────────────────┐
 │  Context Minimization    │  actiongate_context_ablation.compressor.compress (REAL, frozen)
 │  removes filler/history/ │  protect_fn preserves ActionGate- AND ACP-critical spans
 │  redundant/stale spans   │
 └──────────────────────────┘
        │  Reduced Context
        ▼
 ┌──────────────────────────┐
 │  LLM stage (reader)      │  deterministic offline reader (repo MockReader mechanism)
 │  reads proposed action   │  reads ONLY surviving spans -> KubernetesOperation
 │  from reduced context    │  fail-closed INSUFFICIENT_CONTEXT if a critical span is gone
 └──────────────────────────┘
        │  Proposed Action
        ▼
 ┌──────────────────────────┐
 │  ActionGate              │  action_gate_ref.gate.evaluate + action_gateway_k8s.policy (REAL)
 │  "is this authorized?"   │  real envelope/policy/evidence/approvals/action-hash
 └──────────────────────────┘
        │  Authorized?
        ▼
 ┌──────────────────────────┐
 │  ACP                     │  frozen ACP core + real cloud_controller (REAL)
 │  "operationally safe?"   │  readiness/blast/capacity/freeze/rollback
 └──────────────────────────┘
        │  Operational Safety
        ▼
 Hypothetical Execution   (eligible iff BOTH pass; never actually executed — shadow)
```

## Contract

- **No layer bypasses another.** The action ActionGate + ACP evaluate is exactly
  the action the reader derived from the reduced context (enforced by
  `verify_chain`). ACP only runs on an action that reached it; execution
  eligibility requires passing every layer.
- **No layer duplicates another.** Context Minimization does not authorize or
  judge operational safety; ActionGate does not compute readiness; ACP does not
  authorize. See `RESPONSIBILITY_MATRIX.md` (0 duplicated-logic, 0 ownership
  violations — source-scanned).
- **No layer is authoritative.** All shadow-only. The compressor is a
  preprocessing step; ActionGate and ACP are observers here; nothing executes.

## Stage I/O

| stage | input | output | frozen source |
|---|---|---|---|
| Context Minimization | `Context` (spans) + `protect_fn` + signed policy | surviving span ids + metrics | `compressor.compress` |
| LLM reader | reduced surviving spans | `KubernetesOperation` or `INSUFFICIENT_CONTEXT` | deterministic reader |
| ActionGate | proposed action → envelope + policy + evidence | outcome + action_hash + dispositive rules | `gate.evaluate` |
| ACP | same action → `CloudWorldState` + `CloudActionCandidate` | recommendation + evidence + trace | frozen core + `cloud_controller` |
| composition | ActionGate outcome + ACP result (bound) | one of 8 classes | V2.1 `compose` |
| chain | context digest + action hash + candidate identity | execution identity or mismatch | `verify_chain` |

## End-to-end outcome classes

The two front-end statuses — `INSUFFICIENT_CONTEXT` (reader fail-closed) and
`CONTEXT_IDENTITY_MISMATCH` (chain broken) — plus the eight V2.1 composition
classes carried through (`AUTHORIZED_AND_OPERATIONALLY_SAFE`,
`BLOCKED_BY_AUTHORIZATION`, `HELD_BY_OPERATIONAL_SAFETY`, `BLOCKED_BY_BOTH`,
`REQUEST_MORE_EVIDENCE`, `REQUEST_FRESH_OPERATIONAL_STATE`,
`COMPOSITION_IDENTITY_MISMATCH`, `SHADOW_ERROR`).

## Why this is the strongest evidence

Each layer was built and validated independently (Context Minimization; ActionGate;
ACP V1/V2/V2.1). V2.2 shows they compose into **one system** with clean ownership,
one bound identity from context to hypothetical execution, and **zero downstream
change from compression** — the compressed context produces the identical action,
authorization, and operational verdict as the full context.
