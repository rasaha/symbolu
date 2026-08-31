# ADR — Cloud Scaling: Dependency- and Cost-aware Capacity Recommendations (Phase 3)

**Status:** **PROPOSED** (draft PR; not merged).
**Date:** 2026-08-12
**Package:** `packages/capabilities/cloud-scaling-controller` (`ugence-cloud-scaling-controller`), v0.3.0 → **v0.4.0**.
**Scope:** Additive, deterministic, provider-neutral, **shadow/advisory-only** capacity-action
recommendation layer built *around* the Phase-2 forecast and supplied dependency/cost/constraint
evidence. The controller's advisory authority, provider neutrality, and five-signal decision
algorithm are unchanged; Phase-2 forecasting is unchanged; recommendations never feed the live
controller and never execute, authorize, or verify an effect.

---

## Context

- **Phase 1** established a provider-neutral representation of *current* capacity state
  (`CanonicalCapacityState`), explicit normalization/projection onto the unchanged
  `ScalingObservation`, and immutable recommendation evidence (`CapacityDecisionEvidence`).
  It answered: *what is the current canonical capacity state?*
- **Phase 2** added deterministic, shadow-only forecasting + replay evaluation
  (`CapacityForecastEvidence`). It answered: *what capacity will probably be required within
  the forecast horizon?*

**Phase 3** answers the next question, still entirely in shadow / advisory mode:

> Given the forecast, service dependencies, operating constraints and cost evidence, what is
> the best capacity **action** — and why?

Example. Phase-2 forecast: *"the application may require 10 replicas within 20 minutes."*
Phase-3 recommendation: *"increase the application from 6 to 8 replicas now and increase the
database connection pool from 100 to 140; this satisfies the forecast with lower cost and less
downstream bottleneck risk than immediately going to 10 replicas."*

The naive path — let a forecast plus a cost heuristic *trigger* a scaling action, or let a
cheaper plan override a safety limit — would (a) entangle an unproven recommendation with real
authority, (b) make cost an implicit authorizer, and (c) risk moving a bottleneck onto an
unmodelled dependency. We reject it. Phase 3 is **descriptive, advisory shadow intelligence
only**.

## Decision

Add a leaf subpackage `ugence_cloud_scaling_controller.planning` (pure standard library, no new
dependency, no network / subprocess / credential / LLM, no import-time side effects) reachable
only through the explicit advisory entry point `recommend_capacity_action(...)`.

### End-to-end recommendation flow

```text
Phase-2 CapacityForecastEvidence
   +  DependencyTopology     (supplied, typed, tenant/scope-bound dependency evidence)
   +  CostBook              (supplied, exact integer-minor-unit money cost evidence)
   +  OperatingConstraints  (hard, non-compensatory limits)
   +  RecommendationPolicy  (explicit, versioned weights + thresholds; digest-bound)
        ↓  recommend_capacity_action  (deterministic, clock-free, fail-closed)
   validate + scope-bind (subject/tenant/scope) + reject future/expired inputs
        ↓
   bounded candidate generation (always includes NO_CHANGE)
        ↓
   hard-constraint filtering  (BEFORE scoring; a violation is non-compensatory)
        ↓
   dependency + cost evaluation, explicit policy scoring (coverage-first, then score)
        ↓
   CapacityActionRecommendation   (selected plan + ranked alternatives + typed rejections,
                                   self-revalidating, sha256 content-identity digest)
      OR  RecommendationAbstention  (a typed, first-class abstention)
        ↓  Phase 3 ends
```

### Canonical input and output contracts

| Concept | Type | Notes |
| --- | --- | --- |
| Forecast | `CapacityForecastEvidence` (Phase 2) | consumed, never reimplemented |
| Dependency topology | `DependencyTopology` / `DependencyEdge` / `DependencyKind` | supplied dependency *evidence*, not runtime causality |
| Cost evidence | `CostBook` / `CostEvidence` / `Money` / `CostBasis` | exact integer minor units + currency |
| Operating constraints | `OperatingConstraints` / `ConstraintViolationKind` | hard, non-compensatory limits |
| Candidate | `CandidateActionPlan` / `ResourceChange` / `ActionKind` | bounded generation; NO_CHANGE mandatory |
| Policy | `RecommendationPolicy` / `ScoreBreakdown` | explicit, versioned, digest-bound weights |
| Output | `CapacityActionRecommendation` / `EvaluatedCandidate` | self-revalidating record |
| Abstention | `RecommendationAbstention` / `RecommendationAbstentionReason` | typed, first-class |

### Dependency model

A `DependencyTopology` is **supplied evidence**: typed directed edges (`CAPACITY_BOUND`,
`THROUGHPUT_BOUND`, `INFORMATIONAL`) between canonical subjects, bound to one tenant/scope, with
an `as_of` effective time, an evidence-source identity, and a stable content digest. Construction
fails closed on self-edges, duplicate edges, conflicting edges (same pair, contradictory kind),
and cross-tenant edges. Cycles are *reported* (`has_cycle()`) so the pipeline can abstain with a
typed `DEPENDENCY_CYCLE` reason rather than crash.

A capacity-coupling edge carries supplied downstream capacity evidence
(`downstream_current_capacity`, `required_per_upstream_unit`). Phase 3 detects when scaling the
primary would transfer the bottleneck to a dependency: if the primary scales up but the
capacity-bound dependency is not raised to its required level, `bottleneck_risk = 1.0` (moved); a
coordinated plan that raises it removes the bottleneck (`0.0`). A capacity-coupling edge that
omits its evidence yields a typed `MISSING_DEPENDENCY_CAPACITY` abstention. **Structural
dependency evidence never proves runtime causality**; the recommendation explicitly discloses the
residual uncertainty.

### Cost model

Cost is an **optimization input, never an authorization mechanism**. `Money` is exact integer
minor units plus an ISO currency code (mirroring the Phase-1 `Unit.CURRENCY_MINOR` convention) —
never a float. A `CostBook` gathers per-subject `CostEvidence` (unit price, `CostBasis`, effective
interval, source) for one tenant/scope. Phase 3 performs **no provider price lookup**. It abstains
(typed) on: missing/incompatible cost evidence, expired pricing, a currency mismatch (cross-currency
comparison without exchange-rate evidence — exchange rates are out of scope for this baseline), and
an incompatible pricing basis. Cost deltas are computed exactly in minor units. A cheaper plan is
preferred **only** among plans that already meet safety and forecast-coverage requirements; a more
expensive plan may be recommended when necessary to satisfy coverage or a hard constraint, and the
additional cost is disclosed. No recommendation is described as globally optimal.

### Hard constraints versus scoring preferences

**Hard constraints** (`OperatingConstraints`) are non-compensatory and applied **before** any
weighted scoring: min/max capacity, allowed step, regional quota, cooldown / minimum change
interval, SLO and error-budget protection (which forbid scale-down), dependency capacity ceiling,
prohibited actions, and maximum permitted cost increase. A cheaper or higher-scoring candidate can
never overcome a hard-constraint violation — an infeasible candidate is removed from consideration
and recorded as a typed rejection.

**Scoring preferences** (`RecommendationPolicy`) are explicit, finite, validated, versioned, and
digest-bound weights over: forecast coverage, dependency/bottleneck risk, reliability risk, cost
delta, change magnitude/stability, uncertainty, and a hold-bias operator preference. Selection is
**coverage-first then policy score**: candidates meeting the coverage floor form the preferred tier;
the highest-scoring candidate in the active tier wins. There is no opaque model and no silently
selected weight.

### NO_CHANGE semantics

NO_CHANGE is a mandatory baseline candidate. It wins whenever current capacity already covers the
forecast (it earns the hold-bias and pays no cost/magnitude penalty), so the recommender does not
churn capacity for unnecessary scaling. It is always available as the safe fallback.

### Typed abstentions

Phase 3 abstains — a first-class, evidence-producing outcome — rather than fabricate a plan when
evidence is insufficient or contradictory. Typed reasons include: missing/expired/abstained
forecast, unsupported forecast target, insufficient forecast confidence, missing canonical
state/current capacity, subject/tenant/scope mismatch, missing/stale topology, dependency cycle,
conflicting dependency evidence, missing dependency capacity, missing/incompatible/stale cost
evidence, currency mismatch, missing constraints, quota conflict, no feasible action, ambiguous
best plan, unsupported resource type, non-finite/malformed input, future-data leakage, and
contradictory evidence. If two feasible candidates are semantically tied and the policy provides no
authoritative tie-break, the recommender returns `AMBIGUOUS_BEST_PLAN` rather than pick by list or
digest order.

### Evidence and digest model (construction safety)

Applying the Phase-2 acceptance lesson (structural binding): `CapacityActionRecommendation`
**embeds** the authoritative inputs — the forecast evidence, current canonical state, dependency
topology, cost book, operating constraints, and recommendation policy — and **derives** every
calculated claim from them. At construction *and* at `from_dict`:

- each bound digest is re-derived from the embedded object (`forecast_evidence_digest ==
  forecast_evidence.digest()`, and likewise for state/topology/cost/constraints/policy), so a
  caller cannot pair one input with another input's digest;
- the deterministic evaluation context is rebuilt and **every** evaluated candidate's feasibility,
  cost delta, and score breakdown are recomputed and compared to the stored values — a forged
  score, cost delta, feasibility flag, or fabricated/unevaluated candidate is rejected;
- the selected plan must be present among the evaluated candidates and be the unique winner under
  the same coverage-first, policy-scored selection rule (no non-winning or unevaluated selection,
  no ambiguous selection);
- NO_CHANGE must be present; subject/tenant/scope must agree across forecast, state, topology, and
  cost book; and non-finite values are rejected at every nested level.

The record is immutable (frozen), serializes deterministically (sorted keys, RFC3339-UTC times,
`sha256:` content digest), round-trips, rejects missing and surplus fields, and excludes only the
digest itself and a non-authoritative diagnostic annotation from its identity. The digest is a
**content identity/integrity** value — never a signature, an authorization, or a proof of effect.

### Temporal and multi-tenant safety

The forecast issue time (cutoff) must precede the recommendation time; the recommendation validity
window must lie within the forecast horizon; a forecast older than the operator-set validity is a
typed `EXPIRED_FORECAST`; stale cost/topology and future-dated inputs are typed abstentions; and no
cross-tenant subject/topology/pricing/policy binding is possible (exact scope equality via the
canonical subject authority; a missing tenant never equals a named tenant). The clock is injected
explicitly (`recommendation_time`); the path is deterministic.

## Boundaries (what Phase 3 is **not**)

Phase 3 may recommend actions but must not execute them. It does **not**: call any cloud/Kubernetes
API; hold provider credentials; mutate infrastructure; invoke an autoscaler; authorize its own
recommendation; import or embed Risk Authority or ActionGate; create execution receipts; or claim a
recommendation was attempted, authorized, executed, or verified. Every recommendation carries
`advisory_only = shadow_only = True` and `actuation_performed = authorization_performed =
effect_verified = False`, `authority_class = ADVISORY`, `execution_capability = NONE`.

- **Phase 4** — Risk Authority integration.
- **Phase 5** — ActionGate authorization and provider execution.
- **Phase 6** — effect verification and recommendation learning.

## Threat model and misuse cases

- *Forged evidence.* A caller hand-assembles a recommendation with a favourable score, cost, or
  feasibility. → Rejected: every derived field is recomputed from the embedded inputs at
  construction and at `from_dict`.
- *Cost-as-authorizer.* A cheaper plan is presented as overriding a safety/quota limit. → Rejected:
  hard constraints filter before scoring; a cheaper unsafe plan loses before it is scored.
- *Bottleneck laundering.* A primary-only scale-up is presented as safe while silently overloading a
  dependency. → Surfaced: `bottleneck_risk` and the dependency explanation disclose the transfer;
  missing dependency evidence abstains.
- *Temporal spoofing.* Stale embedded evidence paired with fresh top-level timestamps. → Rejected:
  the embedded forecast cutoff/horizon are re-checked against the recommendation time.
- *Execution implication.* A downstream reader treats a recommendation as an authorization. → The
  record structurally cannot claim authorization/execution/effect and says so in its fields.

## Consequences

- Additive `planning` subpackage; the five-signal decision kernel, Phase-1 canonical layer, and
  Phase-2 forecasting are byte-for-byte unchanged; the live recommendation path is unchanged.
- Distribution `ugence-cloud-scaling-controller` `0.3.0 → 0.4.0` (additive public capability).
  Consumer `ugence-cloud-scaling-operations` `0.1.1 → 0.1.2` (dependency range `>=0.3.0,<0.4 →
  >=0.4.0,<0.5`; committed shadow evidence regenerated through the canonical harness).
- Pure-stdlib; no new runtime dependency; no import-time network/socket/process/thread activity.

## Known limitations / maturity

- The recommendation policy is a deterministic **baseline** verified for implementation correctness
  only. Passing tests/CI prove implementation correctness, **not** recommendation quality.
- Forecast quality has **not** been established on production workloads
  (`PREDICTIVE_QUALITY_NOT_ESTABLISHED`).
- Recommendation economic optimality has **not** been established
  (`ECONOMIC_OPTIMALITY_NOT_ESTABLISHED`).
- Production effectiveness has **not** been established
  (`PRODUCTION_EFFECTIVENESS_NOT_ESTABLISHED`).
- No recommendation is authorized or executed by Phase 3 (`NOT_AUTHORIZED_FOR_EXECUTION`).
- Coordinated planning addresses one downstream capacity dependency at a time (bounded); the
  planning target is `RUNNING_REPLICAS` (utilization/latency targets abstain
  `UNSUPPORTED_FORECAST_TARGET` until a separately-governed capacity model is added); cross-currency
  comparison requires exchange-rate evidence that this baseline does not provide.
