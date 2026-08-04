# Shadow Harness Architecture

```
config.ShadowValidationConfig      explicit, immutable, fail-closed scope
        │
        ▼
allowlist.TargetAllowlist ── observer.ShadowObserver ──► injected ReadOnly* clients
        │                          │  (every read via transport.ReadOnlyTransportBarrier)
        │                          ▼
        │                  contracts.DeploymentObservation / HPA observation
        ▼                          │
session.ShadowSession ◄────────────┘
   │  advisory: ugence_cloud_scaling_controller.CloudScalingController.recommend
   │  authorization_scenarios.evaluate_shadow_authorization (local, synthetic)
   │  stale_state.StaleStateEvaluator · hpa_analysis.HpaInteractionAnalyzer
   ▼
contracts.ShadowDecision  (execution_mode=SHADOW, execution_status=NOT_EXECUTED, proposed_only=True)
   │
   ▼
evidence.* ──► FAKE_LOCAL_FIXTURE artifacts + request-method ledger + audit
   ▲
integrity.* / verify_cloud_scaling_operations_shadow_harness.py  (checks, no live executor)
shadow_mutation_canaries.py  (attacks the boundary; imports live executors on purpose)
```

## Boundary invariants

- The harness core (`shadow_validation/*.py`) imports **no** live executor
  (`executors`, `k8s_executor`, `gate_executor`, `rollback_coordinator`, `orchestrator`,
  `action`, `recommend`, `observability`, `shadow`) and performs **no** credential/context
  auto-discovery. Enforced by `integrity.scan_harness_source` and a test.
- Importing any harness module has no side effects (no socket/thread/subprocess/network/
  credential/kubeconfig). Enforced by an isolated-subprocess test and the verifier.
- The single mutation chokepoint is the transport barrier; canaries prove every
  mutation-capable operations entrypoint is blocked before transmission.
