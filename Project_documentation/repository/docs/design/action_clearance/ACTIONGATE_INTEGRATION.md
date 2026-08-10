# ActionGate Integration

## What Action Clearance consumes

A **minimal authorization projection** derived from the frozen `ActionGovernanceResult`
(`ugence_governance_contracts.contracts.action`), plus stable references — **not** the full result object
absorbed into the core, and **not** ActionGate policy, Decision-Authority logic, or the provider-framework
adapter.

Projection fields (all in `AuthorizationContext`, [`REQUEST_CONTRACT.md`](REQUEST_CONTRACT.md)):

| From `ActionGovernanceResult` | Used for |
|---|---|
| `outcome` | eligibility gate (only `AUTHORIZED` / `AUTHORIZED_WITH_CONSTRAINTS`) |
| `constraints` | constraint intersection (§Monotonicity) |
| `obligations` | carried into `effective_obligations` |
| `expiry` | bounds `clearance.valid_until` |
| `authority_basis` | audit linkage |
| `fingerprint` | `authorization_result_fingerprint` — binds the exact authorization |
| `reason_codes` | referenced, not re-emitted |

Why a projection and not the full object: the core stays a leaf that speaks the neutral seam; carrying a
reference + fingerprint (rather than re-deriving) proves identity without coupling to ActionGate
internals. The full `ActionGovernanceResult`, CER, and original `ActionGovernanceRequest` remain
available to the Workflow Service for audit; the core needs only the projection + fingerprints.

## The proven chain

```text
ActionGate authorization (ActionGovernanceResult: AUTHORIZED / AUTHORIZED_WITH_CONSTRAINTS)
  → exact action identity (authorized_action_fingerprint)
    → ClearanceRequest (AuthorizationContext + ActionIdentity)
      → ClearanceResult
```

At no step is the action silently changed: `authorized_action_fingerprint` and
`authorization_result_fingerprint` are carried verbatim and re-verified.

## Does ActionGate invoke Action Clearance?

**No.** As in the live composition, a **Workflow/composition layer invokes both** — ActionGate to
authorize, then Action Clearance to clear. ActionGate has no import of, or reference to, Action
Clearance; Action Clearance has no import of ActionGate policy. The two are orthogonal layers, both must
pass — the model already proven in `symbolu_robotics/.../cloud/composition.py`.

## Mismatch behavior (fail closed)

| Change detected between authorization and clearance | Result |
|---|---|
| changed parameters | `BLOCK` + `ACTION_FINGERPRINT_MISMATCH` |
| changed target | `BLOCK` + `TARGET_MISMATCH` |
| changed artifact | `BLOCK` + `ACTION_FINGERPRINT_MISMATCH` (profile: `GITHUB_HEAD_SHA_CHANGED` / `GITHUB_MERGE_TREE_MISMATCH`) |
| changed operation | `BLOCK` + `ACTION_FINGERPRINT_MISMATCH` |
| changed actor | `BLOCK` + `ACTOR_INVALID` / `SUBJECT_MISMATCH` |
| changed policy reference | `BLOCK` + `POLICY_VERSION_REJECTED` |
| changed expiration (past) | `BLOCK` + `AUTHORIZATION_EXPIRED` + `UPSTREAM_REAUTHORIZATION_REQUIRED` |

## Denials are never clearable

`DENIED` / `INDETERMINATE` / `EXPIRED` outcomes are **not** eligible inputs. Presenting one is a
`NON_RETRYABLE_ERROR` (the request asserts an authorization that does not exist) — never silently
converted into a `HOLD`/`BLOCK` *result* that could be mistaken for "re-checkable". Action Clearance
clears existing authorizations; it does not re-adjudicate denials.
