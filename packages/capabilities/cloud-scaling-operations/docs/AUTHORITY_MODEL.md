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
- manual approval → actuator call
- rollback monitor → unattended revert
- webhook receipt → mutation without authorization
- orchestrator tick → mutation without authorization

How each is enforced, since the orchestrator containment ruling
(`docs/architecture/ADR_CLOUD_SCALING_OPERATIONS_ORCHESTRATOR_CONTAINMENT_SCOPING.md`):

- `RecommendEngine` refuses a non-`DRY_RUN` `ActuatorConfig` at construction, whichever
  loop builds it (D-1). Before the ruling only the orchestrator's `auto_approve_threshold`
  guard stood, and a manual `approve()` with a `SCALE_PATCH` actuator reached the
  Kubernetes API with no authorization. That guard remains as a second line.
- `RollbackMonitor` refuses a rollback function not declared non-mutating (D-1); a
  rollback is a second bounded action needing its own authorization.
- `K8sActuator` takes an injected client or none and loads no kubeconfig or in-cluster
  configuration; `GateActuator` has one mode, no ArgoCD URL and no bearer token (D-2).
- `ProductionOrchestrator.approve` and `RecommendEngine.approve` record the decision and
  return the recommendation with `execution_result` `None` (D-3). No policy check,
  actuator call, rollback watch or outcome record follows.
- The service entrypoint (`main.py`) refuses any `actuator.mode` but `dry_run`.

The supported live path is `ControlledScalingExecutor`, which requires a separate
external authorization and is reached only through the governed ladder
(`cloud-scaling-bounded-execution`).

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
