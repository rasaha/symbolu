# API Reference

Import namespace: `ugence_cloud_scaling_operations`.

## Public API
`ExecutionAuthorization`, `ExecutionRequest`, `ExecutionResult`/`ExecutionReceipt`,
`ExecutionDenied`, `ExecutionIntegrityError`, `ExecutionMode`,
`ControlledScalingExecutor`, `KubernetesScalingExecutor`, `GateExecutor`,
`RollbackCoordinator`, `ReadinessEvaluator`, `OutcomeRecorder`, `OperationsConfig`,
`TargetPolicy`, `AuthorityVerifier`, `IdempotencyStore`, `AuditSink`, `__version__`.

## ControlledScalingExecutor
`execute(request: ExecutionRequest, authorization: ExecutionAuthorization | None, *,
tenant_id, actor_id="system") -> ExecutionReceipt`. Only supported production mutation
path. DRY_RUN proposes; SHADOW observes; SIMULATION/LIVE require a verified
authorization; only LIVE mutates. Every attempt (including denials) is audited.

## GateExecutor
`sync(request, authorization, *, base_url, token="", tenant_id, trigger=True) ->
GateOutcome`. Active sync is a mutation and requires authorization + allowlisted URL +
TLS; never logs the token.

## KubernetesScalingExecutor
A `ScalingBackend` over an injected AppsV1Api-like client; verifies pre-state, detects
concurrency conflicts, applies the authorized target only.

## RollbackCoordinator
`rollback(plan: RollbackPlan, authorization: RollbackAuthorization, *, tenant_id) ->
RollbackResult`. Bounded, authorized rollback (see FAILURE_AND_ROLLBACK.md).

`ExecutionReceipt.to_dict()` / `.to_json()` produce deterministic JSON;
`.receipt_hash()` gives a stable content hash.
