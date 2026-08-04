# Cloud Scaling Operations — Read-Only Shadow Harness

Environment-independent infrastructure for a **later** real-environment, read-only
Kubernetes shadow validation. This directory implements the harness **only**.

> **This phase established the harness, not a real validation.** All committed evidence
> is fake/local fixture evidence (`evidence_class: FAKE_LOCAL_FIXTURE`,
> `real_environment_observed: false`, `real_cluster_accessed: false`). No genuine
> Kubernetes environment was observed. Real shadow validation remains **resource
> blocked**. No infrastructure mutation occurred. Live execution remains unauthorized.

## What it does

- **Explicit config** (`config.py`) — every scope value (cluster, context, namespaces,
  kinds, names, caps, timeouts, TLS) must be supplied; production/wildcard/insecure/live
  are refused (fail closed).
- **Injected read-only clients** (`observer.py`) — no kubeconfig load, no context
  discovery, no in-cluster/cloud credential discovery, no import-time connection.
- **Hard read-only transport barrier** (`transport.py`) — only `GET/HEAD/WATCH/LIST`
  may transmit; `POST/PUT/PATCH/DELETE/DELETECOLLECTION/CONNECT` are blocked *before*
  transmission and recorded in an append-only request-method ledger.
- **Proposed-only decisions** (`session.py`, `contracts.py`) — every `ShadowDecision`
  is `execution_mode=SHADOW`, `execution_status=NOT_EXECUTED`, `proposed_only=True`.
- **Synthetic authorization scenarios** (`authorization_scenarios.py`) — 20 fail-closed
  cases; a valid one yields only `AUTHORIZED_FOR_SHADOW_PLAN`, never live execution.
- **Stale-state + HPA analysis** (`stale_state.py`, `hpa_analysis.py`).
- **Secret redaction** (`redaction.py`) and **evidence model** (`evidence.py`).
- **Integrity checks** (`integrity.py`) + top-level verifier
  `verify_cloud_scaling_operations_shadow_harness.py`.

## Commands

```
ugence-cloud-scaling-operations shadow validate-config
ugence-cloud-scaling-operations shadow inspect-harness
ugence-cloud-scaling-operations shadow run-fixture --out <dir>
ugence-cloud-scaling-operations shadow verify-fixture --dir <dir>
ugence-cloud-scaling-operations shadow mutation-canaries
ugence-cloud-scaling-operations shadow evidence-schema [--name <schema>]
```

The fixture runner prints `FAKE LOCAL SHADOW HARNESS RUN / NO REAL CLUSTER ACCESSED /
NO REAL SHADOW VALIDATION PERFORMED`. See `docs/` for the protocol, architecture,
transport boundary, evidence model, real-environment runbook, and limitations.
