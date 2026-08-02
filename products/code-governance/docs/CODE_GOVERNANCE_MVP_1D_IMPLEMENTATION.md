# Code Governance MVP 1D — Implementation

> **Read-only, non-enforcing, execution disabled.** MVP 1D adds read-only
> enterprise signal adapters, a bounded shadow-pilot runner, and measurable
> human-intervention quality to `ugence_code_governance` (builds on merged PRs
> #1279 / #1280 / #1281 / #1282). It is an *integration + pilot-readiness* phase:
> it lets Code Governance evaluate real or representative enterprise signals in
> read-only mode, explain when human intervention is needed, measure decision
> quality, survive source failures safely, and produce an auditable pilot report —
> **without** changing code, company systems, or governance policy.
>
> There is still no GitHub write path, no merge credential, no execution provider,
> no `reserve_once`, and no authoritative execution-consumption ledger.
> `execution_status()` returns `DISABLED` in every mode.

## The extended pipeline

```
durable Code Governance workflow
  -> read-only enterprise data adapters        (NEW: GitHub GET-only + supplied snapshots)
  -> approved, provenance-bound operational snapshots
  -> canonical Action Clearance TrustedSignals (unchanged AC public API)
  -> CLEAR / HOLD / BLOCK / ESCALATE
  -> deterministic human-intervention routing  (unchanged 1B routing)
  -> durable shadow audit                       (unchanged 1C store)
  -> pilot metrics + reviewer feedback          (NEW)
  -> EXECUTION_DISABLED
```

## Authority model (preserved)

```
enterprise source -> read-only adapter -> normalized operational snapshot
  -> TrustedSignal -> Action Clearance -> HumanInterventionAssessment
```

Adapters **produce evidence and signals**. They never approve a change, authorize
an action, decide whether a merge is allowed, modify company policy, or execute
anything. A source stating "checks passed" does not mean "merge approved"; "actor
active" does not mean "authorized for this decision"; "no incident" does not mean
"execution permitted". Adapters supply *conditions only*.

## What 1D adds

| Area | Module | Notes |
|---|---|---|
| Read-only transport boundary | `adapters/transport.py` | GET/HEAD only; host/endpoint allowlist; size/timeout/content-type/redirect bounds |
| Adapter models + protocol | `adapters/models.py`, `adapters/protocols.py` | `collect_snapshot(request) -> AdapterResult` (data only) |
| Adapter registry projection | `adapters/registry.py` | immutable, fails closed on unregistered/unapproved/over-claimed |
| GitHub read-only adapter | `adapters/github_readonly.py` | GET-only; artifact-identity verified; fact consistency classes |
| Supplied enterprise snapshots | `adapters/*_snapshot.py`, `adapters/snapshot_schemas.py` | identity / change-window / incident / target-health / control-status |
| Normalization | `adapters/normalization.py` | adapter results → existing snapshot + source projection; conflict/failure handling |
| Shadow pilot | `pilot/` | config, runner, evaluation records, reviewer feedback, metrics, offline-verifiable report |
| Pilot durable persistence | `pilot/persistence.py` | reuses the 1C store under a hash-linked `pilot:<id>` lineage |

## Read-only + credential boundary

The transport permits only GET (and HEAD when configured) and rejects every
mutating method, unapproved host, unapproved endpoint, and unapproved redirect
target, with bounded timeouts, response sizes, and content types
(`ReadOnlyBoundaryViolation` / `AdapterResponseError`). Credentials are supplied
through a resolver and used only to authenticate the outbound read; they are never
returned in a response, embedded in a fingerprint, written to the durable store,
included in an error, or logged. See `CODE_GOVERNANCE_PILOT_SECURITY_AND_PRIVACY.md`.

## Source failures fail closed

Every adapter failure is a structured `AdapterFailureCode` (timeout, rate-limit,
unauthorized, schema-invalid, identity-mismatch, artifact-mismatch, …). A failure
never becomes a positive signal: it produces a fact-free `FAILED` result, and the
missing/unknown signal makes the clearance evaluation non-CLEAR (fail closed).
Conflicting facts for the same signal type are marked unknown and recorded as
conflicts. Retries are bounded and only for safe reads; non-retryable failures
(identity mismatch, schema invalid, boundary violation) are never retried.

## Shadow pilot

`ShadowPilotRunner` drives a workflow already at `ACTION_EVALUATED` through the
*unchanged* Action Clearance shadow stage using adapter-collected signals, then
records an immutable `ShadowPilotEvaluationRecord`, persists it durably, and lets a
human record curated `PilotReviewerFeedback` (audit data only — it never changes
policy or the clearance result). `calculate_pilot_metrics` produces a deterministic
metric **profile** (not a single blended score), and `export/verify_shadow_pilot_report`
produce an offline-verifiable pilot report. A pilot is allowlist-based and a
successful pilot does **not** enable execution. See `CODE_GOVERNANCE_SHADOW_PILOT.md`,
`CODE_GOVERNANCE_PILOT_METRICS.md`, `CODE_GOVERNANCE_REVIEWER_FEEDBACK.md`.

## Public API additions

Adapters: `AdapterRequest`, `AdapterResult`, `ReadOnlyTransport`,
`FakeReadOnlyTransport`, `TransportPolicy`, `AdapterRegistryProjection`,
`GitHubReadOnlyAdapter`, `IdentitySnapshotAdapter`, `ChangeWindowSnapshotAdapter`,
`IncidentSnapshotAdapter`, `TargetHealthSnapshotAdapter`,
`ControlStatusSnapshotAdapter`, `normalize_results`.

Pilot: `ShadowPilotConfig`, `ShadowPilotRunner`, `ShadowPilotEvaluationRecord`,
`PilotReviewerFeedback`, `ShadowPilotMetrics`, `calculate_pilot_metrics`,
`evaluate_pilot_status`, `export_shadow_pilot_report`, `verify_shadow_pilot_report`,
plus `CodeGovernanceService.pilot_change_context`.

No `merge`, `approve`, `execute`, `dispatch`, `reserve_once`,
`consume_authorization`, or `write_github` is exposed. `execution_status()` stays
`DISABLED`. Version bumped to **0.3.0 / MVP phase 1D**.

## Validation

- `pytest products/code-governance` — full suite green (1A–1D), plus 93 new 1D
  acceptance tests (54 adapter + 39 pilot) and the offline demo test.
- Offline demo `examples/pilot_shadow_demo.py` (collect → clearance → intervention
  → persist → feedback → metrics → report → timeout → stale → conflict → credentials
  never persisted), asserted by `tests/test_pilot_demo.py`.
- Optional live read-only GitHub smoke is skipped by default (opt-in via
  `CG_PILOT_LIVE_GITHUB=1` + allowlist + externally-supplied read-only credentials).
- Action Clearance package unchanged; platform freeze digest unchanged; wheel
  builds as 0.3.0; clean-install import succeeds.

## What 1D deliberately does **not** do

No execution · no GitHub write operations · no GitHub App write permissions · no
merge credential · no execution provider · no `ProviderKind` · no `reserve_once` ·
no consumption ledger · no autonomous policy-learning · no reviewer feedback
changing policy automatically · no unrelated employee/company data · no
credentials/tokens/secrets in the database · no production-enforcement-readiness
claim. See `CODE_GOVERNANCE_MVP_1D_LIMITATIONS.md` and
`CODE_GOVERNANCE_NEXT_PHASES.md`.
