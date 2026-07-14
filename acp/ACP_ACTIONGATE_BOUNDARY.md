# ACP ↔ ActionGate Boundary (V2 §3)

ACP and ActionGate are **two different control layers** that a cloud operation
must pass **both** of. This document fixes the boundary so neither reimplements
the other. Code: `symbolu_robotics/autonomous_control_plane/cloud/composition.py`.

## The two questions

| | **ActionGate** | **ACP (cloud adapter)** |
|---|---|---|
| Question | *Is this operation **authorized**?* | *Is this operation **operationally safe against live cluster state right now**?* |
| Domain | identity, authorization, integrity | operational safety, live capacity, readiness |
| Output | 6-outcome verdict + signed execution token | `ActionDecision` → `CloudRecommendation` (advisory) |
| Authority | **authoritative** (mints the token) | **shadow-only** (never actuates, never mints a token) |

## Ownership table

| concern | ActionGate-owned | ACP-owned | shared input | ordering | failure outcome | evidence source |
|---|---|---|---|---|---|---|
| caller identity / RBAC | ✅ | — | principal | AG first | `DENY` | AG envelope |
| privilege monotonicity / SoD | ✅ | — | requested scope | AG | `DENY`/`ESCALATE` | AG policy |
| approver quorum | ✅ | — | approvals | AG | `ESCALATE_TO_HUMAN` | AG envelope |
| nonce single-use | ✅ | — | nonce | AG | `DENY` | AG store |
| manifest-digest / action-hash binding | ✅ (authorization) | ✅ (revalidation of ACP's own decision) | digest | AG then ACP | `DENY` / `revalidation reject` | AG envelope / ACP `CommitRevalidator` |
| resourceVersion CAS (authz) | ✅ | — | resourceVersion | AG | `REQUEST_MORE_EVIDENCE` | AG envelope |
| **live readiness (plasticity / cooldown / rollback-watch)** | — | ✅ | cluster signals | ACP | `HOLD` | **real** `ReadinessChecker` |
| **operational blast radius (from live replicas)** | policy `MAX_BLAST_RADIUS` over a *pre-supplied fact* | ✅ (**computes** it from live state) | current/desired replicas | ACP | `HOLD` | **real** `SafetyBounds` |
| **capacity / min-availability now** | — | ✅ | available replicas | ACP | `HOLD` | live state + `SafetyConfig` |
| **freeze window active now** | policy blackout (config) | ✅ (consumes the flag) | time / windows | ACP | `HOLD` | **real** `BlackoutWindow` |
| **rollback-available now** | — | ✅ | rollback_ref | ACP | `HOLD` | candidate + live state |
| absolute replica min/max policy | ✅ (can `DENY`) | ✅ (also gates via real `PolicyEngine`) | target replicas | either | `DENY` / `HOLD` | **real** `PolicyEngine` |

The key distinction on blast radius: ActionGate's `MAX_BLAST_RADIUS` operator
evaluates a **fact supplied to it** ("affected_count = N") against a policy
ceiling — it does not look at the cluster. ACP **derives** the operational blast
radius from the **live** `CloudWorldState` (current vs desired replicas, or all
replicas for a delete) using the real `SafetyBounds` fractions. Same word, two
different computations at two different layers.

## What ACP must NOT do (and does not)

- ACP does **not** reimplement ActionGate's authorization, identity, evidence,
  nonce, or approval logic. `composition.py` imports **nothing** from ActionGate;
  it consumes the gate's already-computed verdict as an opaque
  `AuthorizationVerdict` token.
- ActionGate is **not** rebranded as ACP. It remains the authorization layer.
- An action must pass **both** layers: authorized by ActionGate **and**
  operationally safe per ACP.

## Composition (the two non-negotiable invariants, §13)

1. **An ActionGate denial is never overridden by ACP.** `DENY ⇒
   BLOCKED_BY_AUTHORIZATION` no matter how safe ACP found the operation.
2. **An ACP hold cannot mint authorization.** ACP is shadow-only; a permissive
   ACP result on a denied or pending action changes nothing.

`PROCEED` requires BOTH: an authorizing verdict (`ALLOW` /
`ALLOW_WITH_CONSTRAINTS`) AND a permissive ACP recommendation.

```
compose(DENY,               PROCEED) = BLOCKED_BY_AUTHORIZATION   # gate wins
compose(ALLOW,              HOLD)    = HELD_BY_ACP                # ACP decisive
compose(ALLOW,              PROCEED) = PROCEED                    # both pass
compose(ESCALATE_TO_HUMAN,  PROCEED) = PENDING_AUTHORIZATION      # gate not final
```

## Why both layers are necessary (the two decisive corpus cases)

- **`ag_allows_acp_holds`** — a scale the gate fully authorizes (identity, RBAC,
  nonce, digest all valid), but the **real** `ReadinessChecker` blocks it because
  a scaling action happened 30 s ago (< the 120 s cooldown). ActionGate has no
  concept of live readiness; **only ACP catches this.** ⇒ `HELD_BY_ACP`.
- **`ag_denies_acp_safe`** — an operationally perfect scale (ready, within
  bounds, rollback present) that the gate **denies** (e.g. missing approver).
  ACP finding it "safe" must not, and does not, let it through. ⇒
  `BLOCKED_BY_AUTHORIZATION`.

These two cases together prove the layers are **orthogonal**: neither subsumes
the other, so composing both is strictly safer than either alone.
