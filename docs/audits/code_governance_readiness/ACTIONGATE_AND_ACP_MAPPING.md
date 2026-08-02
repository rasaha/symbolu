# ActionGate & ACP Mapping — Code Governance

> Documentation only. Authoritative source: `UGENCE_CODE_GOVERNANCE_DESIGN_SPEC.md` v0.2 (§4.4, §4.5, §4.6).
> Verified against live code at commit `3ec11e4e`.

## Part 1 — ActionGate (`ACTION_GOVERNANCE`)

### 1.1 Exact live contract fields

`ActionGovernanceRequest` (`contracts/action.py:29`): `action_type` · **`requested_parameters:
Mapping[str,str]`** · `actor` · `authority_context` · `target_resource` · `policy_refs` ·
`risk_context: Mapping[str,str]` · `evidence_refs` · `decision_refs` · `idempotency_key` ·
`correlation_id` · `authorization_expired: bool`.

`ActionGovernanceResult` (`contracts/action.py:47`): `outcome: ActionGovernanceOutcome`
(`AUTHORIZED · AUTHORIZED_WITH_CONSTRAINTS · DENIED · INDETERMINATE · EXPIRED`) · `constraints` ·
`obligations` · `expiry` · `authority_basis` · `reason_codes` · `provider_trace_id` · `fingerprint`.

**Confirmed: `ActionGovernanceResult` emits no standalone `ExactChangeAuthorization`.**

### 1.2 The exact-change product envelope (§4.4)

```
ExactChangeAuthorization (PRODUCT_INTERNAL, composed & persisted by the Workflow Service) =
      CER (content_hash, expires_at)                     # governance context (names + bindings)
    + prepared ActionGovernanceRequest                    # exact values in requested_parameters
    + ActionGovernanceResult (outcome, constraints, obligations)
    + result fingerprint
    + expiry
    + the merge-artifact binding set (§4.6)
```

This is **sufficient** to authorize an exact merge, because:
- exact values (repo, PR, head/base SHA, merge method, expected merge-tree/merge-group, required
  checks) fit in `requested_parameters: Mapping[str,str]`;
- `decision_refs`/`evidence_refs`/`policy_refs`/`idempotency_key`/`correlation_id` bind the request
  to the governance chain;
- `fingerprint` binds the result to the exact request;
- `expiry` + CER `expires_at` bound the authorization in time;
- `authorization_expired` lets the caller signal staleness.

### 1.3 What ActionGate supports today vs. what the product must add

| Requirement | Support | Where |
|---|---|---|
| bind repo/PR/SHAs/merge-method/tree/group/branch **values** | via `requested_parameters` (Mapping) | product builds the request |
| allowed GitHub API operation | `action_type` + product mapping (`ActionMapping`) | product |
| DecisionRecord reference | `decision_refs` | adapter pulls `action_request.decision_id` (`action_to_control_plane.py:81`) |
| CER hash | via product envelope + `cer.correlation_id`/policy_refs threaded by the adapter | product envelope |
| policy version | `policy_refs` (+ `ActionAuthorizationResponse.policy_versions`) | reuse |
| expiration | `expiry` / CER `expires_at` | reuse |
| **one-time / single-use** | **not a native field** | **product must enforce** (consume-once on the envelope; DA `idempotency_key` + status transitions help) |
| **replay prevention** | `idempotency_key` + fingerprint; DA execution idempotency | product + DA execution layer |
| parameter narrowing | `constraints`/`obligations`; DA subset-check in `execution_service` (`:139-145`) | reuse |
| obligation enforcement | `obligations` returned; **enforcement is the caller's** | product/ACP |
| authorization consumption | **not native** | product envelope consume-once |
| stale-authorization rejection | `EXPIRED` outcome + `authorization_expired` + CER expiry | reuse; product checks freshness |
| post-decision base-branch movement | not modeled in the contract | product invalidation trigger (re-authorize) |
| merge-queue replacement artifacts | not modeled | product derives a new authorization for the merge-group |

### 1.4 Smallest possible future contract change (if any)

None is required for MVP. If, after pilot, single-use/consumption must be **native** rather than
product-enforced, the smallest change is an **additive `ActionGovernanceResult.authorization_id` +
a consumption obligation code** owned by the ActionGate capability — additive, not a redesign.
Do **not** add a new ActionGate result contract during implementation without proving product
enforcement is insufficient.

## Part 2 — ACP (live operational clearance)

### 2.1 Maturity

**SHADOW_ONLY / design-first / partially implemented — never production, never enforcing**
(`acp/ACP_ARCHITECTURE.md:3`; `acp/ACP_PHASE1_READINESS.md:4`; `symbolu_robotics/autonomous_control_plane/cloud/outcomes.py:8-10`). The only enforcing mode is DISABLED (`control_plane/modes.py:53-63`).
Code domains: **robotics, Kubernetes/cloud, database** — **no GitHub/software-merge domain exists**.

### 2.2 Request / result surfaces (actual code)

- Digital clearance (closest analogue): request `OperationalSignals`
  (`ugence_console_api/models.py:107` — `error_budget_remaining`, `cluster_health`,
  `change_freeze_active`); result `ClearanceVerdict` (`models.py:116` — `disposition` `CLEAR/HOLD`,
  `reason_codes`, `evaluated`). Logic fail-closed (`capabilities/operational_safety.py:29`).
- Robotics/cloud core: `CanonicalActionCandidate`/`CloudActionCandidate` + `WorldState` →
  `ActionDecision` (`envelopes.py:33`) / `CloudRecommendation` (`cloud/outcomes.py:18`); composed
  with ActionGate as `CombinedOutcome` (`cloud/composition.py:60`: `PROCEED`,
  `BLOCKED_BY_AUTHORIZATION`, `PENDING_AUTHORIZATION`, `HELD_BY_ACP`).

### 2.3 "Live clearance" today

A **deterministic, fail-closed operational-safety verdict on an already-authorized action, computed
against a snapshot of environment signals, that never actuates and never mints a token.** "Live" is
aspirational: signals are passed in / mocked; no live cluster call in this environment.

### 2.4 ACP vs ActionGate (`acp/ACP_ACTIONGATE_BOUNDARY.md`)

| | ActionGate | ACP |
|---|---|---|
| Question | Is it **authorized**? | Is it **operationally safe right now**? |
| Output | verdict + (signed) token | advisory `ActionDecision`/`CLEAR/HOLD` |
| Authority | authoritative (mints token) | shadow-only (never actuates) |

Invariants: an ActionGate `DENY` is never overridden by ACP; an ACP hold cannot mint authorization.

### 2.5 MVP pre-merge check classification

| MVP check | Classification | Basis |
|---|---|---|
| authorization still valid | AVAILABLE_IN_SHADOW | `ControlAuthorization.expiry` + commit revalidation; ActionGate `EXPIRED`. ActionGate's job; shadow only; GitHub actor → adapter |
| base/head/merge-group still match | ADAPTER_REQUIRED | TOCTOU/CAS `state_binding` pattern exists (`authorization.py:115-123`, cloud `resource_version`), but GitHub SCM facts need a world-model adapter |
| required checks still pass | ADAPTER_REQUIRED | generic signal ingestion exists (`cloud_controller/signals/`); no GitHub-checks source |
| no active incident / freeze | AVAILABLE_IN_SHADOW | freeze is first-class (`change_freeze_active`); incident only proxied via health/error-budget |
| actor identity still valid | AVAILABLE_IN_SHADOW | ActionGate layer, consumed by ACP as opaque verdict; GitHub actor mapping = adapter |
| policy version still accepted | PRODUCT_POLICY_REQUIRED | version-pinning lives in the model-selection `control_plane/`; ACP `clear()` does not evaluate policy version |
| action not already executed | AVAILABLE_IN_SHADOW; durable dedup = NEW_CAPABILITY_REQUIRED | one-shot/nonce mechanisms exist; **no durable executed-action store** (audit in-memory) |

**Cross-cutting:** none are `AVAILABLE_NOW` in production terms — ACP is shadow-only everywhere and
has **no GitHub domain**, so every row additionally carries an implicit GitHub `ADAPTER_REQUIRED`.

### 2.6 Durable clearance reference

**Absent.** `ClearanceVerdict` has no id/expiry/signature; the audit store is in-memory. The
authorization grant (`ControlAuthorization`) is one-shot and short-lived with a content-hash id
(explicitly "not a signature"). A **durable, one-time, short-lived clearance reference is a new
capability** required before enforced merge (§4.5, MVP 1C). `OperationalClearanceRecord` remains
conceptual and maps onto ACP's representation only once that representation is durable.
