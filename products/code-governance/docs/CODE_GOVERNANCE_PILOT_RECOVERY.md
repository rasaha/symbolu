# Pilot Recovery

> The operator recovers from a process restart with **no external call** and never
> auto-resumes an ACTIVE pilot — continuation is an explicit operator action.
> Machine-readable companion (statuses): `docs/pilot_health_schema.json`.

## What recovery does

`recover_pilot(store, config)` validates the store schema, verifies store integrity
(records + event chain of the `op:<pilot_id>` lineage), loads the latest lifecycle
event + kill-switch state, identifies the last committed evaluation, and returns a
`PilotRecoveryResult`. It constructs no adapter or transport.

## Recovery statuses

`RECOVERED_READY` · `RECOVERED_ACTIVE_REQUIRES_CONFIRMATION` · `RECOVERED_PAUSED` ·
`RECOVERED_COMPLETED` · `RECOVERED_ABORTED` · `RECOVERED_INTEGRITY_FAILURE` ·
`CONFIGURATION_MISMATCH` · `STORE_INTEGRITY_FAILURE` · `NO_PRIOR_RUN`. An ACTIVE
pilot recovers as *requires confirmation* — the operator continues only after an
explicit `confirm_recovery(...)`.

## Configuration drift

If the supplied config fingerprint differs from the persisted run's fingerprint,
recovery reports `CONFIGURATION_MISMATCH`, preserves old run history, and blocks
resume until an explicit new run or approved config transition. History is never
rewritten.

## Adapter-interruption recovery

Before a request → no attempt recorded. After request starts but before result
persists → attempt state unknown (never assumed successful). After result persists
but before evaluation → recover the result; require explicit continuation. After
evaluation persists but before report update → recover the evaluation; regenerate
the deterministic report explicitly. GitHub calls are never auto-repeated.
