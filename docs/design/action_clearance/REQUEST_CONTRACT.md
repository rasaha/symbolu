# Request Contract — `ClearanceRequest`

Proposed public request contract. Field names follow repository conventions; live contract types
(`ActionGovernanceResult`, `ContextEnvelopeRecord`, `DecisionRecord`) are referenced by id/hash, not
embedded, because CER and `DecisionRecord` live in `ugence_decision_authority` and must not be imported
by the neutral core.

## Grouping (avoid duplicate identity representations)

The flat field list the prompt enumerates is grouped into four sub-structures so each identity appears
exactly once:

```text
ClearanceRequest
├── request_id                       # caller-supplied
├── tenant_id
├── correlation_id
├── workflow_id
├── evaluation_time                  # caller-supplied trusted time
├── authorization: AuthorizationContext
├── action: ActionIdentity
├── signals: SignalBundle
└── policy: ClearancePolicyContext
```

### `AuthorizationContext`

| Field | Required | Fingerprinted | Notes |
|---|---|---|---|
| `authorization_ref` | yes | yes | stable id of the ActionGate authorization |
| `authorization_result_fingerprint` | yes | yes | `ActionGovernanceResult.fingerprint` |
| `authorization_outcome` | yes | yes | must be `AUTHORIZED` / `AUTHORIZED_WITH_CONSTRAINTS` |
| `authorization_issued_at` | yes | yes | |
| `authorization_expires_at` | yes | yes | bounds `clearance.valid_until` |
| `authorization_constraints` | yes | yes | for intersection (§Monotonicity) |
| `authorization_obligations` | yes | yes | carried into `effective_obligations` |
| `decision_record_ref` | yes | yes | `DecisionRecord.decision_id` (audit linkage) |
| `context_envelope_ref` | yes | yes | `cer_id` |
| `context_envelope_hash` | yes | yes | CER `content_hash` |
| `authorized_actor_basis` | yes | yes | `authority_basis` projection |
| `override_ref` / `supersedes_ref` | optional | yes | override/supersession linkage |

### `ActionIdentity`

| Field | Required | Fingerprinted | Notes |
|---|---|---|---|
| `authorized_action_fingerprint` | yes | yes | the exact action authorized by ActionGate |
| `action_type` | yes | yes | neutral action type |
| `target_ref` | yes | yes | the target the action operates on |
| `operation` | yes | yes | the exact operation (e.g. `merge`) |
| `action_governance_request_ref` | optional | yes | reference/fingerprint of the `ActionGovernanceRequest` |

### `SignalBundle`

| Field | Required | Fingerprinted | Notes |
|---|---|---|---|
| `signals` | yes | yes | ordered list of `TrustedSignal` (or `trusted_signal_refs` when resolved externally) |
| `required_signal_types` | yes | yes | which types are mandatory for this request/profile |

### `ClearancePolicyContext`

| Field | Required | Fingerprinted | Notes |
|---|---|---|---|
| `policy_refs` | yes | yes | clearance policy versions |
| `required_control_refs` | yes | yes | controls that must be satisfied |
| `profile_id` | yes | yes | e.g. `github_exact_merge` |
| `max_clearance_lifetime_s` | optional | yes | policy cap on `valid_until` |
| `clock_skew_tolerance_s` | optional | yes | see [`TIME_AND_FRESHNESS.md`](TIME_AND_FRESHNESS.md) |

## Prohibited request content

The request must contain **no credentials** and **no executable provider commands**. It carries facts,
references, fingerprints, and normalized signals only. A request carrying either is a
`NON_RETRYABLE_ERROR` (malformed contract).

## Whether every field belongs directly

Grouping into `AuthorizationContext` / `ActionIdentity` / `SignalBundle` / `ClearancePolicyContext`
prevents the flat-field duplication the prompt warns about (e.g. a single `authorized_action_fingerprint`
lives in `ActionIdentity`, not repeated in the authorization block). `request_id`, `tenant_id`,
`correlation_id`, `workflow_id`, and `evaluation_time` stay at the top level because they are
cross-cutting.

Machine-readable: [`action_clearance_request.schema.json`](action_clearance_request.schema.json).
