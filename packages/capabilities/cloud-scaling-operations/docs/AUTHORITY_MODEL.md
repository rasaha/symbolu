# Authority Model

Every infrastructure change requires an immutable, external `ExecutionAuthorization`.
The recommendation engine, an approval Boolean, and a confidence score are **never**
sufficient authority.

## State transitions

```
ADVISORY_RECOMMENDATION → POLICY_AND_SAFETY_EVALUATION → HUMAN_OR_EXTERNAL_GOVERNANCE_APPROVAL
  → EXECUTION_AUTHORIZATION → READINESS_CHECK → CONTROLLED_EXECUTION → OUTCOME_AND_AUDIT
```

## Prohibited paths (enforced)

- recommendation → direct actuator call
- confidence threshold → automatic mutation
- internal auto-approval → production execution
- webhook receipt → mutation without authorization
- orchestrator tick → mutation without authorization

The orchestrator refuses `auto_approve_threshold` when it would drive a non-dry-run
actuator (hard runtime guard at construction). The supported live path is
`ControlledScalingExecutor`, which requires a separate external authorization.

## ExecutionAuthorization

Fields: `authorization_id`, `decision_id`, `recommendation_id`, `tenant_id`,
`actor_id`, `authority_source`, `issued_at`, `expires_at`, `permitted_action`,
`target_cluster`, `target_namespace`, `target_resource`, `current_replicas`,
`minimum_replicas`, `maximum_replicas`, `maximum_delta`, `reason`, `policy_version`,
`idempotency_key`, `nonce`, and optional `issuer`/`signature_algorithm`/`signature`/
`key_id`.

## Fail-closed denials

A mutation is denied when authorization is missing, expired, not-yet-valid, malformed,
for a different tenant/target/action, outside replica bounds, outside max delta,
reused with a changed request (idempotency integrity), signed by an untrusted issuer,
bound to a mismatched recommendation, or based on a stale observation. Signature
verification is pluggable (`AuthorityVerifier`); the reference verifier is a
deterministic HMAC for tests/dev — **not** a production KMS.
