# Code Governance MVP 1E — Implementation

> **Read-only, non-enforcing, execution disabled.** MVP 1E makes the MVP 1D
> read-only pilot capability **safely deployable and operable** against a narrowly
> allowlisted real GitHub environment. It adds a deployable `PilotOperator` with
> explicit operational controls (validate / start / pause / resume / inspect /
> stop), a credential-isolation boundary, a static read-only security inspector,
> preflight + health + readiness, structured redacted logging, operator metrics, a
> reviewer work queue, restart-safe recovery, a kill switch, stop conditions, and
> deterministic pilot closeout.
>
> There is still no GitHub write path, no write permission, no merge credential, no
> execution provider, no `ProviderKind`, no `reserve_once`, and no authoritative
> consumption ledger. `execution_status()` returns `DISABLED` in every mode.

## The operationalized pipeline

```
allowlisted tenant + repositories
  -> read-only GitHub collection (GET/HEAD only)
  -> supplied enterprise snapshots
  -> existing TrustedSignal mapping        (unchanged 1D)
  -> Action Clearance shadow evaluation    (unchanged AC public API)
  -> HumanInterventionAssessment           (unchanged 1B routing)
  -> durable pilot records                 (unchanged 1C store)
  -> reviewer queue + feedback             (NEW operational coordination)
  -> pilot metrics + reports               (offline-verifiable)
  -> EXECUTION_DISABLED
```

## Authority model (preserved)

The operator **coordinates** the existing components. It issues no binding
decision, creates no ActionGate authority, overrides no DecisionRecord, executes
nothing, alters no policy, and mutates no GitHub state. Reviewer assignment is not
approval; reviewer feedback never changes policy automatically; a successful pilot
never enables enforcement.

## The operator package

`pilot_operator/` reuses the existing durable store, GitHub read-only adapter,
snapshot adapters, pilot runner, reviewer-feedback models, metric calculator, and
report exporter — nothing is duplicated.

| Module | Responsibility |
|---|---|
| `config.py` | immutable `PilotDeploymentConfig` + fail-closed validation + value-free fingerprint |
| `security.py` | `CredentialReference`, credential-leak scanner, AST read-only inspector |
| `lifecycle.py` | lifecycle state machine + append-only `PilotRunRecord` |
| `preflight.py` | security + readiness preflight (`PilotPreflightResult`) |
| `health.py` | `PilotHealth` / `PilotReadiness` |
| `recovery.py` | restart-safe `recover_pilot` (no external call, no auto-resume) |
| `scheduler.py` | bounded candidate selection + stop-condition classification |
| `review_queue.py` | reviewer work queue over intervention assessments |
| `logging.py` | structured, redacted operator logs |
| `metrics.py` | operator-level metrics (separate from clearance-quality) |
| `events.py` | immutable security events + kill-switch state |
| `persistence.py` | durable operator records under an `op:<pilot_id>` lineage |
| `api.py` | the `PilotOperator` facade + `open_pilot_operator` |
| `cli.py` | the `cg-pilot` console entry point |

## Operator commands

`validate` · `preflight` · `start` · `pause` · `resume` · `run_once` /
`run_batch` · `inspect` · `health` / `readiness` · `review_queue` ·
`record_feedback` · `metrics` · `activate_kill_switch` / `clear_kill_switch` ·
`record_security_event` · `abort` · `closeout` · `confirm_recovery`. Every command
requires an explicit tenant, pilot id, config, and durable store. There is no
`merge`, `approve`, `execute`, `deploy`, or `reserve` command.

## Security posture

- **Read-only, structurally** — the transport permits only GET/HEAD; the operator
  has no write client. A static AST inspector (`scan_paths`) proves the
  adapter+operator boundary is free of HTTP mutation calls, direct HTTP clients,
  GitHub mutation endpoints, GraphQL mutations, write scopes, merge/approval calls,
  execution-provider imports, and `reserve_once`.
- **Credential isolation** — credentials are *referenced* (env var / external
  resolver), resolved only immediately before a read, kept in process memory, and
  never written to the store, logs, metrics, reports, fingerprints, or exceptions.
  A leak scanner proves absence across all artifacts.
- **Fail closed** — bad config, integrity failure, kill switch, or a critical
  security event stop the pilot; none enables execution or changes policy.

See `CODE_GOVERNANCE_PILOT_SECURITY.md`, `CODE_GOVERNANCE_CREDENTIAL_BOUNDARY.md`.

## Deployment

A `cg-pilot` console entry point, an example immutable config
(`examples/deployment/pilot_deployment.example.json`, placeholders only), and a
minimal non-root container (`examples/deployment/Dockerfile`) that bakes in no
credentials, exposes no listener, mounts a durable-data volume, and defaults to no
active pilot. No network-facing control API is added. See
`CODE_GOVERNANCE_PILOT_RUNBOOK.md`.

## Live vs. offline (no fabricated evidence)

The offline demo (`examples/pilot_operator_demo.py`) and all tests use fake GET-only
transports and supplied snapshots. An optional live read-only GitHub smoke is
skipped by default and only runs with `UGENCE_LIVE_GITHUB_PILOT=1` plus an explicit
allowlist and externally supplied read-only credentials. When live credentials are
unavailable the operator reports `LIVE_GITHUB_PILOT_NOT_RUN — operator readiness
verified; no live result fabricated`. This build is `IMPLEMENTED` +
`OFFLINE_VERIFIED`; it is not `LIVE_SMOKE_VERIFIED` and no `PILOT_DATA_COLLECTED`.

## Validation

- `pytest products/code-governance` — full suite green (1A–1E), with 91 new 1E
  acceptance tests + the operator demo test.
- Version bumped to **0.4.0 / MVP phase 1E**; `cg-pilot` CLI smoke passes; wheel
  builds; clean install imports; Action Clearance unchanged; platform freeze digest
  unchanged.
- Machine-readable companions in `docs/`: `pilot_deployment_config_schema.json`,
  `pilot_lifecycle_states.json`, `pilot_preflight_checks.json`,
  `pilot_health_schema.json`, `pilot_security_events.json`,
  `pilot_stop_conditions.json`, `review_queue_schema.json`,
  `operator_metrics_schema.json`, `pilot_operator_acceptance_scenarios.json`,
  `public_api.json`.

See `CODE_GOVERNANCE_MVP_1E_LIMITATIONS.md` and `CODE_GOVERNANCE_NEXT_PHASES.md`.
