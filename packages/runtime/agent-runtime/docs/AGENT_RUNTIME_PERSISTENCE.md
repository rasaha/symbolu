# Agent Runtime — Persistence

The runtime owns persistence **interfaces**, not a durable backend.

## Decision: Outcome B (runtime-owned interfaces + in-memory reference)

Of the options considered in the packaging plan:

- **A** — a separate neutral durable-persistence package the runtime depends on;
- **B** — the runtime defines the interfaces and ships an in-memory reference, with
  product deployments supplying durable implementations externally;
- **C** — keep an existing durable engine as a dependency.

**Outcome B was chosen.** Rationale: the legacy durable engine is not independently
packaged as a neutral distribution, and its reachable dependency graph pulls concrete
governance and robotics (`cer_v0_3 → cer_v0_1 → symbolu_robotics → numpy`). Depending
on it would re-couple the "neutral" runtime to those layers and to a heavy numeric
dependency. Owning small neutral interfaces keeps the core stdlib-only and lets any
durable backend (SQL, KV, event store) plug in behind the interface without the core
importing it.

## Interfaces

```python
class CheckpointStore(Protocol):      # append + read-latest checkpoint history
    def put(self, checkpoint) -> None: ...
    def latest(self, instance_id) -> Optional[Checkpoint]: ...

class RuntimeStateStore(Protocol):    # latest resume-point snapshot per instance
    def save(self, checkpoint) -> None: ...
    def load(self, instance_id) -> Optional[Checkpoint]: ...

class RuntimeEventStore(Protocol):    # durable event stream (opt-in)
    def append(self, instance_id, event) -> None: ...
    def events(self, instance_id) -> List[RuntimeEvent]: ...
```

Reference implementations: `InMemoryCheckpointStore`, `InMemoryRuntimeStateStore`,
`InMemoryRuntimeEventStore`. They round-trip checkpoints through their serialized form,
so tests exercise the same (de)serialization a durable backend would.

## Checkpoints

A `Checkpoint` captures: `instance_id`, `workflow_id`, `runtime_id`,
`runtime_version`, workflow `status`, per-task `{status, attempts}`, `correlation_id`,
and a SHA-256 `digest` of the payload. Checkpoints hold **no** credentials, provider
outputs, or governance authority — only coordination state needed to resume.

The digest makes a corrupted or tampered checkpoint detectable: `Checkpoint.verify()`
recomputes and compares, and recovery rejects a mismatch (fail closed).

## When checkpoints are written

The engine commits a checkpoint after each committed workflow/task transition when a
`checkpoint_store` and/or `state_store` is configured. With no store configured, the
engine still coordinates in memory and emits `CHECKPOINT_COMMITTED` events, but writes
nothing durable.
