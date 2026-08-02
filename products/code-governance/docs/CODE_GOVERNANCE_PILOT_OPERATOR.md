# Pilot Operator

> `PilotOperator` is the deployable coordinator for a bounded, read-only,
> shadow-only Code Governance pilot. It reuses the durable store, read-only
> adapters, pilot runner, reviewer-feedback models, metrics, and report exporter —
> it duplicates none of them and adds no authority.

## What it does

Validates a bounded deployment config, runs a security + readiness preflight,
drives an explicit lifecycle (DRAFT→READY→ACTIVE→PAUSED/STOPPING→COMPLETED/ABORTED),
runs bounded read-only evaluations, maintains a reviewer queue, records curated
feedback, accumulates operator metrics, supports a durable kill switch, recovers
across restarts without external calls, and closes out with an offline-verifiable
report.

## What it never does

Issue a binding decision · create ActionGate authority · override a DecisionRecord ·
execute or dispatch · mutate GitHub · alter policy · request write permissions ·
persist a credential. `execution_status()` is always `DISABLED`.

## Opening an operator

```python
op = open_pilot_operator(config, service=durable_service, registry=registry,
                         profile=clearance_profile, routing=routing,
                         credential_resolver=env_resolver)
```

The operator requires a durable `CodeGovernanceService`. See the runbook for the
full command set.
