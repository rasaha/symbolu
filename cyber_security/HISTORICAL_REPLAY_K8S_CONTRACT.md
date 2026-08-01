# Historical-Replay Contract — Kubernetes / Infrastructure-Agent (narrow target)

**Scope:** one narrowly-scoped workflow — Kubernetes / infrastructure-agent
high-consequence actions. This is a **contract + tested reference adapter**, not a
vendor integration claim and not live enforcement. Reference implementation:
`composite_threat_detector/replay.py::K8sAuditReplayAdapter`; example fixture:
`composite_threat_detector/evaluation/fixtures/k8s_replay_example.jsonl`.

Broad enterprise replay is out of scope. Named source systems other than the two
implemented reference adapters (`kubernetes_audit`, `generic_normalized`) are
`CONTRACT ONLY` in `HISTORICAL_REPLAY_CONTRACT`.

## 1. Source-field mapping specification

| K8s audit field | Normalized CTD field | Required? |
|-----------------|----------------------|-----------|
| `auditID` | `event_id` | required |
| `requestReceivedTimestamp` | `timestamp` | required |
| `objectRef.namespace` | `tenant_id` (**tenant = namespace**) | required |
| `user.username` | `actor` (**redacted**) | required |
| `verb` + `objectRef.resource` | `operation` + `capability` | required |
| `annotations["ctd/workflow"]` | `workflow_id` | optional (preferred) |
| `objectRef.name` | `workflow_id` / `correlation_id` | optional (fallback) |
| `sourceIPs` | `destination` (**redacted**) | optional |
| `stage` | (dropped, reported) | optional |

### Capability mapping (high-consequence verbs only)

| verb(s) | resource contains | capability |
|---------|-------------------|------------|
| get/list/watch | secret | `credential.read` |
| create/update/patch | secret | `data.write` |
| delete/deletecollection | (any) | `data.delete` |
| create/update/patch | rolebinding / clusterrolebinding | `privilege.grant` |
| delete/patch | networkpolic… | `network.egress` |
| create/patch | service | `network.egress` |
| delete/patch | flowschema | `monitoring.disable` |

Unmapped verbs/resources produce **no capability** and are reported as
`unmapped_capability` — they are never coerced into a threat fragment.

## 2. Required vs optional fields

**Required:** `auditID`, `requestReceivedTimestamp`, `objectRef.namespace`,
`user.username`, `verb`, `objectRef.resource`. A missing `objectRef.namespace`
causes rejection (no tenant ⇒ no cross-tenant mixing).
**Optional:** workflow annotation, `objectRef.name`, `sourceIPs`, `stage`.

## 3. Redaction & synthetic substitution

`user.username` and `sourceIPs` are replaced by stable synthetic tokens
(`redacted:<hash>`), never dropped silently. Substitution is deterministic so the
same source value maps to the same token across a replay.

## 4. Tenant isolation

Tenant = namespace. Events without a namespace are rejected. Assembly keys are
tenant-scoped downstream, so no cross-namespace linkage can occur.

## 5. Ordering

Normalized events carry `timestamp` (from `requestReceivedTimestamp`) and a
`sequence_id` derived from the audit id. The analyzer's ordering model resolves
`ORDERED / PARTIALLY_ORDERED / AMBIGUOUS_ORDER / CONFLICTING_ORDER`; strict-order
recipes are not satisfied under ambiguity unless the recipe permits it.

## 6. Unmapped-field reporting

Every source field not in the mapping is recorded in `dropped_fields`; every
unmapped verb/resource increments `unmapped_capability`. Nothing is silently
discarded.

## 7. Missing-context behavior

An event with no workflow annotation and no `objectRef.name` is normalized but
flagged `missing_context` (grouping falls back to namespace). Missing context is
reported, never invented.

## 8. Replay input schema

One sanitized K8s audit event per JSON line (JSONL). See the example fixture. A
real replay supplies sanitized, redacted audit events from a single namespace
scope per file.

## 9. Example sanitized fixture

`evaluation/fixtures/k8s_replay_example.jsonl` — a payments-namespace sequence
(get secret → delete → patch networkpolicy) that assembles a
credential+data+egress capability, plus benign and rejected (anonymous, no
namespace) events.

## 10. Data-quality report template

`replay.data_quality_report(adapter, raw_events)` emits: `total_raw_events`,
`normalized`, `rejected`, `unmapped_capability`, `missing_context`,
`distinct_tenants`, and `dropped_field_counts`. Evidence label:
`Measured — synthetic behavioral corpus` (on synthetic input) or
`Measured — historical replay` (only when run on actual sanitized data).

## Evidence discipline

Running this adapter on synthetic fixtures is `Measured — synthetic behavioral
corpus`. It becomes `Measured — historical replay` **only** when executed on real
sanitized enterprise audit data — which is `REQUIRES ENTERPRISE DATA` and has not
been run in this phase.
