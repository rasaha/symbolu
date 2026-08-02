# Enterprise Snapshot Schemas

> Non-GitHub enterprise sources are integrated in MVP 1D as **already-captured,
> supplied snapshots** — no live vendor clients (no Okta, Entra ID, ServiceNow,
> Jira, PagerDuty, Opsgenie, Datadog, Kubernetes, or cloud APIs). Machine-readable
> companion: `docs/enterprise_snapshot_schemas.json`.

## Versioned schemas

| Kind | Schema id | Canonical signal |
|---|---|---|
| identity / account validity | `code_governance.identity_snapshot.v1` | `ACTOR_STATUS` |
| change-window / freeze | `code_governance.change_window_snapshot.v1` | `CHANGE_FREEZE` |
| incident state | `code_governance.incident_snapshot.v1` | `ACTIVE_INCIDENT` |
| target health | `code_governance.target_health_snapshot.v1` | `TARGET_AVAILABILITY` |
| required control | `code_governance.control_status_snapshot.v1` | `REQUIRED_CONTROL` |

## Validation (fail closed)

Each snapshot is validated for schema version, tenant, subject, source, adapter
version, capture time, expiry, integrity digest, policy reference, and (when the
source policy requires) action binding. The following fail closed with a structured
failure code and yield no positive signal:

- unknown/newer schema version → `SOURCE_SCHEMA_INVALID`
- naive (tz-unaware) timestamp → `SOURCE_SCHEMA_INVALID`
- missing tenant/subject, malformed payload → `SOURCE_SCHEMA_INVALID`
- expired snapshot (`valid_until < collection_time`) → `SOURCE_DATA_STALE`
- cross-tenant snapshot → `SOURCE_IDENTITY_MISMATCH`
- action-binding mismatch → `ARTIFACT_IDENTITY_MISMATCH`
- tampered integrity digest → `SOURCE_SCHEMA_INVALID`

## Identity data minimization

Identity snapshots may carry ONLY governance-relevant keys: `actor_ref`,
`account_active`, `status_category`, `roles`, `groups`, `authority_scopes`. Any
other key under `facts` (salary, medical, performance content, personal contact,
unrelated demographics, …) fails closed. Stable subject references are used, never
full employee profiles. See `CODE_GOVERNANCE_PILOT_SECURITY_AND_PRIVACY.md`.

## Why supplied snapshots

Supplied snapshots let 1D integrate identity/incident/change-management/health
sources without prematurely committing to any specific vendor API or building live
clients. A future phase can add live read-only adapters behind the same read-only
transport boundary and registry.
