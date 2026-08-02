# Pilot Lifecycle

> Every transition is explicit and durably recorded. There is no automatic start
> from DRAFT and no restart of a terminal pilot. Run records are append-only.
> Machine-readable companion: `docs/pilot_lifecycle_states.json`.

## States + transitions

```
DRAFT -> READY -> ACTIVE <-> PAUSED
                    |  \          \
                    |   -> STOPPING -> COMPLETED
                    any active state -> ABORTED (operator command)
                    any state -> INTEGRITY_FAILURE (durable integrity failure)
```

Forbidden: `COMPLETED/ABORTED/INTEGRITY_FAILURE -> ACTIVE`, and direct
`DRAFT -> ACTIVE`. `start()` performs `DRAFT->READY->ACTIVE` as two recorded
transitions after a passing preflight — an operator action, never automatic.

## Run records (append-only)

Each state change is a new immutable `PilotRunRecord` snapshot (content-addressed),
never an in-place mutation. The authoritative current state after a restart is the
newest `PILOT_LIFECYCLE_EVENT` (run-record snapshots may content-dedupe identical
states). Execution status on every record is `DISABLED`.
