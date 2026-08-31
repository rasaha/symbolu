# Agent Runtime — Recovery

Recovery reconstructs runtime coordination state from persisted records after a
restart. It is deliberately conservative and makes **no external call**.

## Invariants

1. Recovery reconstructs state **only** from persisted runtime records.
2. Recovery performs **no** external provider call automatically.
3. Recovery performs **no** governance call automatically.
4. Previously `RUNNING` work returns in a state requiring **explicit continuation**
   (the task is re-armed to `READY`; the workflow becomes `PAUSED`).
5. `COMPLETED` work does not rerun.
6. `CANCELLED` work does not restart.
7. A runtime-identity / version mismatch is **reported** (`config_mismatch=True`),
   not silently accepted.
8. Checkpoint corruption **fails closed** (`RecoveryError`).
9. Recovery never fabricates provider success.

## API

```python
result = recover_runtime(runtime, instance_id, definition)
# -> RuntimeRecoveryResult(instance, resumed_from_status,
#                          requires_continuation, config_mismatch, notes)
```

`recover_runtime` loads the latest checkpoint from the configured `state_store`
(or `checkpoint_store`), verifies its digest, rebuilds the `WorkflowInstance` from the
caller-supplied `definition`, and returns it. It does **not** drive the workflow —
continuation is an explicit `resume_workflow` call afterward.

## Why the caller supplies the definition

Checkpoints store coordination state, not the full task graph (which may contain code
references, argument schemas, or product data the runtime should not persist). The
caller re-supplies the original `WorkflowDefinition`; recovery cross-checks it against
the checkpoint (`workflow_id` match, known task ids) and fails closed on mismatch.

## Determinism

Recovery reads no clock and makes no network or disk call beyond the injected store.
Given the same persisted checkpoint and definition, it always returns the same
reconstructed instance.

## Multi-workflow (portfolio) recovery (H22-C)

`recover_portfolio(...)` reconstructs a whole H22-B portfolio and its scheduler
fairness/aging/dependency/failure/cancellation state from a durable `PortfolioCheckpoint`,
composing the **same** per-instance `recover_runtime` contract above — it adds no new external
call. It is side-effect free (provider = 0, governance = 0, advancement = 0, auto-resume = 0),
cross-binds each referenced runtime checkpoint by digest (without requiring writer runtime-version
equality — origin provenance, so upgrades recover), and returns a `PortfolioRecoveryResult` that
`requires_continuation`. A recovered mid-flight workflow is continued for bounded advancement via
`continue_workflow` (the bounded, non-draining analogue of `resume_workflow`). See
[`AGENT_RUNTIME_H22C_DURABILITY.md`](AGENT_RUNTIME_H22C_DURABILITY.md).
