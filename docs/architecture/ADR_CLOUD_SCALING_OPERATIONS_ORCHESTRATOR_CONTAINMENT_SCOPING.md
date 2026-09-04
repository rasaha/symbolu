# Cloud Scaling Operations — orchestrator containment, scoped and ratified

**Status:** ratified 2026-09-04 by the repository owner. Closes the gap named in
`ADR_CLOUD_SCALING_PHASE5D_BOUNDED_EXECUTION_SCOPING.md` ("the orchestrator loop
remains a parallel path and needs a containment ruling of its own"). Grounded on
`ADR_CLOUD_SCALING_AUTHORIZATION_PHASE5.md` §2 ("Live execution is structurally
blocked until 5X") and on 5D's D-1, which made the `BoundedExecutionSeam` the
only path from a grant to `ControlledScalingExecutor.execute` and declared the
orchestrator's auto-approve path and the CLI's authorization file reference
entries. This record authorizes no code change; it fixes what the implementation
must do.

## The question

Can the Cloud Scaling Operations orchestrator reach infrastructure mutation
outside the `BoundedExecutionSeam` today? **Yes.** The orchestrator owns a second
mutation path through `K8sActuator` that never enters
`ControlledScalingExecutor`, needs no `ExecutionAuthorization`, and discovers
cluster credentials itself. 5D's D-1 made that path "not a production path" by
declaration; nothing in code makes it so. The seam contains itself, not
operations.

All paths below are under
`packages/capabilities/cloud-scaling-operations/src/ugence_cloud_scaling_operations/`
unless stated otherwise, at Cloud Scaling Operations 0.1.2.

## What exists `[V]`

| Finding | Where |
|---|---|
| `ProductionOrchestrator.approve` delegates to `RecommendEngine.approve`, which runs a policy check and then `K8sActuator.scale`; in `SCALE_PATCH` mode that calls `patch_namespaced_deployment_scale`. No `ExecutionAuthorization`, verifier, idempotency store, audit sink or readiness check sits on that path | `orchestrator.py:447-458`; `recommend/engine.py:162,376-386`; `action/k8s_actuator.py:186-190,276-281` |
| The construction guard refuses only `auto_approve_threshold` combined with a non-`DRY_RUN` actuator. Manual approval with a `SCALE_PATCH` actuator is unguarded | `orchestrator.py:163-175` |
| `main.py` builds the actuator from YAML, accepting `scale_patch`, and runs the loop; `python -m` reaches it, though the only console script is the offline CLI | `main.py:158-165,307,331`; `pyproject.toml:59-60` |
| `K8sActuator` loads in-cluster or kubeconfig credentials on its first non-dry-run call. The injected-client executor was built to prevent exactly this and refuses without a client | `action/k8s_actuator.py:123-135`; contrast `k8s_executor.py:28-47` |
| `RollbackMonitor` is wired with `actuator.scale` as its rollback function and calls it unattended when metrics degrade | `recommend/engine.py:164-167`; `action/rollback.py:227-228,287-296` |
| `GateActuator` holds an ArgoCD bearer token in its config and POSTs through `urllib` in non-dry-run modes; it is exported from the `action` package but not wired into the engine | `action/gate_actuator.py:49-52,236-251`; `action/__init__.py:23,69` |
| The authority model and the module manifest call "recommendation → direct actuator call" and "orchestrator tick → mutation without authorization" prohibited paths that are **enforced**; the manifest lists two mutation entrypoints and omits the actuator; the capability inventory records auto-approval as present in the orchestrator and `main.py` | `docs/AUTHORITY_MODEL.md:14-24`; `module_manifest.json:30-33,48-55`; `artifacts/execution_capability_inventory.json:3-6` |

## What the existing tests prove `[V]`

- The 5D import-boundary test proves the seam never imports the orchestrator,
  the CLI, the gate executor or the Kubernetes executor, and that no upstream
  package imports the seam. It contains the seam, not operations
  (`packages/integration/cloud-scaling-bounded-execution/tests/test_import_boundary.py:28-29,56-59,92-99`).
- The 5D time-authority test proves one clock read per dispatch and that the
  executor is handed that instant. The actuator path reads `time.time` and
  sleeps between retries, untouched by it
  (`tests/test_time_authority.py:40-47`; `action/k8s_actuator.py:164,301`).
- Operations' own suite proves the auto-approve guard, import-time and dry-run
  side-effect containment, and the actuators' default `DRY_RUN` mode
  (`tests/boundaries/test_boundaries.py:58-79`;
  `tests/side_effects/test_side_effects.py:39-63`;
  `shadow_mutation_canaries.py:253-283,308-313`).
- The repository-level tests exercise approval through the actuator as
  legitimate behaviour, including `SCALE_PATCH` against a mocked API
  (`tests/cloud_controller/test_action_advanced.py:613-707`;
  `tests/cloud_controller/test_action.py:172-215`).

## Gaps `[G]`

No test asserts that `approve()` with a mutating actuator is refused, that
`K8sActuator` cannot load credentials, or that a rollback cannot mutate. The guard
inventory scores only the auto-approve construction guard and the run-once guard
for the orchestrator (`guard_inventory.json`, indices 45-48).

## Ratified decisions

| # | Decision | Ruling |
|---|---|---|
| D-1 | Where actuation is refused | `RecommendEngine` refuses a non-`DRY_RUN` `ActuatorConfig` at construction, wherever the engine is built, not only under auto-approve. `RollbackMonitor` refuses a mutating `rollback_fn`. The orchestrator's construction guard stays as a second line and is no longer the only one. |
| D-2 | Credential discovery | Kubeconfig and in-cluster loading are removed from `K8sActuator`; a client is injected or absent, mirroring `KubernetesScalingExecutor`. `GateActuator` loses its non-dry-run modes and its bearer-token field; ArgoCD access stays with the authority-gated `GateExecutor` and its injected caller. |
| D-3 | What approval means afterwards | `approve()` records the human decision and returns the recommendation with **no execution result**. Handing an approved recommendation to the 5A candidate is a later wave, not this ruling. |
| D-4 | Proof | The new guards enter the guard inventory and the gate-removal mutation sweep. A canary proves a mutating engine is refused at construction. The 5D forbidden-module set gains `ugence_cloud_scaling_operations.action.k8s_actuator`, `action.gate_actuator` and `recommend`. The repository-level actuator tests move to the refused shape. |
| D-5 | Home and version | Cloud Scaling Operations **0.2.0**, a capability removed. The `cloud-scaling-bounded-execution` pin rises to `>=0.2.0`. The module manifest, the authority model, the capability inventory and the README name `approve()` non-mutating and list no actuator as a mutation entrypoint. |

## Gaps that survive `[G]`

Operations' float clock and HMAC verifier are still carried, not replaced;
`main.py` remains a `python -m` entry whose only remaining actuator modes are
non-mutating; the handoff from an approved recommendation into the 5A candidate
is unbuilt.

## Next step

Implement D-1 … D-5 in Cloud Scaling Operations 0.2.0 with the acceptance tests
proving that a `RecommendEngine` built with a `SCALE_PATCH` actuator, a
`RollbackMonitor` built with a mutating function, and a `K8sActuator` asked to
discover credentials are each refused at construction, and that `approve()` on a
pending recommendation returns it with no execution result.
