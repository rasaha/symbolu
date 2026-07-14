# ActionGate × ACP Composition Spec (V2.1 §5)

How one **real** ActionGate authorization verdict and one **real** ACP
operational-safety verdict for the **same** identity-bound Kubernetes operation
compose into one of eight closed classes. Code:
`robotics_reliability_bench/acp_k8s_integrated/composition.py`. The two decision
schemas are **not merged** — `compose()` consumes each layer's own verdict and
never recomputes the other.

## Inputs (each from its real owner)

| input | owner | source |
|---|---|---|
| `authorization_outcome` (+ is_authorized/denied/pending) | ActionGate | real `action_gate_ref.gate.evaluate` |
| `acp_recommendation` (PROCEED/HOLD/REOBSERVE/…) | ACP | real frozen selector on cloud evidence |
| `acp_validity` (VALID/STALE/MISSING/EVALUATOR_FAILED) | ACP | real cloud evidence |
| `identity_bound` (+ reason) | binding | `KUBERNETES_OPERATION_IDENTITY_BINDING.md` |

## The eight classes

| class | when | eligible? |
|---|---|---|
| `AUTHORIZED_AND_OPERATIONALLY_SAFE` | authorized AND ACP permissive (VALID) | **yes** (hypothetically) |
| `BLOCKED_BY_AUTHORIZATION` | ActionGate `DENY` (ACP not a hard hold) | no |
| `HELD_BY_OPERATIONAL_SAFETY` | authorized, ACP hard hold on VALID evidence | no |
| `BLOCKED_BY_BOTH` | `DENY` AND ACP hard hold | no |
| `REQUEST_MORE_EVIDENCE` | gate not final (`SIMULATE_AND_RETRY` / `REQUEST_MORE_EVIDENCE` / `ESCALATE_TO_HUMAN`) | no |
| `REQUEST_FRESH_OPERATIONAL_STATE` | authorized, ACP state STALE/MISSING or REOBSERVE | no |
| `COMPOSITION_IDENTITY_MISMATCH` | layers not bound to one operation | no |
| `SHADOW_ERROR` | an evaluator failed / exception contained | no |

## Precedence (non-compensatory, top-down)

1. `COMPOSITION_IDENTITY_MISMATCH` — binding is a hard precondition. If the two
   layers are not provably about the same operation, nothing else is trustworthy.
2. `SHADOW_ERROR` — ACP `EVALUATOR_FAILED` or any contained exception. Fail closed.
3. `DENY` + ACP hard hold → `BLOCKED_BY_BOTH`.
4. `DENY` → `BLOCKED_BY_AUTHORIZATION` (authorization is final).
5. gate not final → `REQUEST_MORE_EVIDENCE` (ACP cannot authorize; gate resolves first).
6. authorized + ACP needs fresh state → `REQUEST_FRESH_OPERATIONAL_STATE`.
7. authorized + ACP hard hold → `HELD_BY_OPERATIONAL_SAFETY`.
8. authorized + ACP safe → `AUTHORIZED_AND_OPERATIONALLY_SAFE`.

## Ownership rules (invariants — §11)

- **ActionGate DENY is never overridden by ACP.** No path from `DENY` reaches
  `AUTHORIZED_AND_OPERATIONALLY_SAFE`; the only `DENY` outcomes are
  `BLOCKED_BY_AUTHORIZATION` / `BLOCKED_BY_BOTH`.
- **ACP cannot grant authorization.** `hypothetically_eligible` is true only for
  `AUTHORIZED_AND_OPERATIONALLY_SAFE`, which requires `is_authorized`. A permissive
  ACP result on a denied/pending action changes nothing.
- **ALLOW does not override an ACP hard hold.** authorized + hard hold →
  `HELD_BY_OPERATIONAL_SAFETY`, not eligible.
- **Execution is hypothetically eligible only when both layers pass.** And even
  then only *hypothetically* — ACP is shadow-only and mints no token; the real
  runtime is unchanged.

## Why the two `REQUEST_*` classes are distinct

`REQUEST_MORE_EVIDENCE` is **authorization** incomplete (ActionGate wants
simulation/approval/human review — its concern). `REQUEST_FRESH_OPERATIONAL_STATE`
is **operational** state stale (ACP cannot judge safety on old cluster state — its
concern). Keeping them separate preserves clean ownership: each layer asks for
what it — and only it — owns. `acp_was_decisive` is true for the operational-hold
and fresh-state classes.

## Distinctness from V2

V2's `cloud/composition.py` composed ACP with a **supplied** authorization token
(4 classes). V2.1 composes ACP with a **real, executed** ActionGate verdict on a
**bound** Kubernetes operation (8 classes, + identity binding + commit
revalidation). V2's module is unchanged; this is additive.
