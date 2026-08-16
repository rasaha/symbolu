# ugence-agent-value-readiness

> **⚠️ Experimental, internal, advisory, non-financial.**
> The **contract shapes** (GV-3R-a) and the **deterministic readiness
> determination evaluator** (GV-3R-b) for the Agent Value Readiness engine of
> Ugence Value Intelligence — **not** a deployment authority, **not** a
> metric-evaluation engine, and **not** a customer-facing module.
> - **No deployment authorization** — a determination is *advisory*, consumed by
>   a separate human/deployment-governance process.
> - **No evidence admission or verification, no benchmark resolution, no
>   metric-to-threshold calculation.** The evaluator consumes gate statuses
>   recorded by an upstream evaluator; it does not compute them.
> - **No money, currency, cost, benefit, or ROI** anywhere.
> - **Caller-provided artifacts are not authority-verified.** Lifecycle labels,
>   digests, condition approvals, and gate statuses are structural inputs;
>   verifying them is Policy-Authority work.
> - **Policy Authority and richer RA-owned subject/system binding are deferred.**

The vocabulary for assessing whether an agent is ready for an intended outcome:

```
PreROIReadiness = f(Intelligence, Capabilities, Adoption
                    | Geography, Domain, IntendedOutcome)
```

Intelligence, Capability, and Adoption are **non-financial leading indicators**.
This package implements milestones **M-3R.1 (GV-3R-a, contract shapes)** and
**M-3R.2 (GV-3R-b, the determination evaluator)** of the UVI ADR
(`docs/architecture/ADR_UGENCE_VALUE_INTELLIGENCE_GV2C_GV2E_GV3R.md`, §5–§10, §20).
Authority resolution (Policy Authority, condition-approval validation) remains
out of scope.

- **Distribution:** `ugence-agent-value-readiness`
- **Namespace:** `ugence_agent_value_readiness`
- **Version:** 0.2.0
- **Depends on:** stdlib **+ `ugence-governance-contracts>=0.2.0`** (evidence vocabulary) **+ `ugence-uvi-policy-contracts>=0.1.0`** (policy/context shapes) — never `governed-value`.
- **Typing:** fully annotated; ships `py.typed`.

## What's in it

| Group | Symbols |
|---|---|
| Indicator results (distinct types) | `IntelligenceFitnessResult`, `CapabilityReadinessResult`, `AdoptionReadinessResult` |
| Gate / condition / composite | `GateResult`, `ConditionSet`, `AdvisoryComposite` |
| Determination envelope | `AgentValueReadinessDetermination` |
| Readiness enums | `ReadinessClassification`, `GateStatus`, `ConditionStatus`, `ReadinessIndicatorClass`, `CapabilityDemonstration`, `IntelligenceDimension`, `CapabilityDimension`, `AdoptionDimension` |
| Reused policy enums (re-exported) | `ReadinessTarget`, `RequirementClass` (owned by `ugence-uvi-policy-contracts`) |
| **Evaluator (GV-3R-b)** | `evaluate_readiness`, `ReadinessEvaluationCase`, `ReadinessEvaluationResult`, `ReadinessEvaluationTrace`, `ConditionDecision` |
| **Evaluator codes** | `ReadinessRuleId`, `ReadinessReasonCode`, `ReadinessAdvisoryCode`, `ConditionDecisionCode` |
| Errors | `ReadinessContractError`, `ReadinessEvaluationError` |

## The evaluator (GV-3R-b)

```python
from ugence_agent_value_readiness.api import evaluate_readiness

result = evaluate_readiness(case, evaluation_time=when)   # tz-aware, mandatory
result.classification   # ReadinessClassification, selected by the evaluator
result.rule_id          # the single precedence rule that fired
result.trace            # deterministic explanation
```

`ReadinessEvaluationCase` carries **no classification field** — the caller states
the facts, the evaluator selects the tier. `evaluation_time` is mandatory and
keyword-only; the **system clock is never read**, so an evaluation is fully
reproducible.

### Precedence (first matching rule wins)

| Rule | Condition | Classification |
|---|---|---|
| `R0` | governing policy not `APPROVED_ACTIVE`, or not effective at `evaluation_time` | `NOT_ASSESSABLE` |
| `R1` | any applicable mandatory `FAIL` | `NOT_READY` |
| `R2` | a structural assessability gap | `NOT_ASSESSABLE` |
| `R3` | an applicable mandatory `INDETERMINATE`, no `FAIL` | `NOT_ASSESSABLE` |
| `R4` | unresolved conditional concern, not compensable | `NOT_READY` |
| `R5` | compensable concern with no active covering condition | `NOT_READY` |
| `R6` | **PILOT**: all applicable mandatory `PASS`, concerns covered | `PILOT_READY` |
| `R7` | **PRODUCTION**: concerns remain, all actively covered | `READY_WITH_CONDITIONS` |
| `R8` | **PRODUCTION**: nothing unresolved, no open active condition | `DEPLOYMENT_READY` |

`{FAIL, INDETERMINATE, PASS}` ⇒ `NOT_READY`; `{INDETERMINATE, PASS}` ⇒
`NOT_ASSESSABLE`; `{PASS, PASS}` ⇒ conditional resolution. No condition,
composite, Intelligence score, Capability strength or Adoption score overrides a
mandatory failure.

**`R0` is the ADR §6 precondition (§7 row 0)** and precedes every gate rule. The
governing `ReadinessPolicy`'s own `metadata.lifecycle_state` and
`metadata.is_effective_at(evaluation_time)` are read structurally at the
explicit evaluation time (half-open `effective_from <= t < effective_to`). A
definite mandatory `FAIL` dominates other *gate-level* uncertainty, but it never
overrides an invalid governing policy. Under `R0` "no headline is asserted"
(ADR §6): the determination carries **no** gate results, while the trace still
reports the full gate inventory and every failure diagnostically.

**Why `R1` precedes `R2`.** ADR §8 / D-6 state `MANDATORY FAIL ⇒ NOT_READY`
without exception, and `AgentValueReadinessDetermination` structurally *rejects*
any other classification while a blocking gate is in the record — so reporting a
completeness gap as `NOT_ASSESSABLE` would require dropping the failure from the
record. Every assessability gap is still recorded in the trace and reason codes
when `R1` fires.

### Readiness requirements are policy/gate-driven

Applicable requirements come from **`ReadinessPolicy.gates`**. The presence of
`IntelligenceFitnessResult` / `CapabilityReadinessResult` /
`AdoptionReadinessResult` records is **not** globally mandatory: the ratified
applicable set (ADR §6) is defined over gates, `ReadinessPolicy` has no field
able to declare a required indicator family, and the merged determination
contract permits a ready classification with no indicator records at all. A
requirement for an indicator therefore surfaces through **its applicable policy
gate and that gate's `GateResult`**, never through bare tuple presence.

Supplied indicator records remain **fully structurally validated** (tenant,
subject, context binding, claim binding, uniqueness, immutability) and are
carried through as diagnostics. A failing, advisory, reported or unverified
indicator neither unlocks nor blocks a tier — the tier stays gate-driven.

### Gate-set completeness

The **`ReadinessPolicy` body is the authoritative gate inventory.** Applicable
gates are those whose `applicability` contains the requested target; every
applicable `MANDATORY` and `CONDITIONAL` gate needs exactly one `GateResult`.
A missing one is `NOT_ASSESSABLE` — **never** a silent `PASS`. A gate result
bound to another policy, naming a gate absent from the policy, embedding a
redefined `PolicyGate`, duplicated, or evaluated for another target is rejected
with a `ReadinessEvaluationError`. Missing **advisory** results never block: no
ratified field marks an advisory gate assessability-required, and none is
invented. Production-only gates stay diagnostic during a PILOT assessment.

### Conditional compensation

An unresolved applicable conditional concern (`FAIL`/`INDETERMINATE`) is covered
only when the policy sets `conditionally_compensable=True` **and** a
`ConditionSet` naming that exact gate is `APPROVED_ACTIVE` and active at
`evaluation_time` (`effective_from <= t < effective_to/expiry`). Proposed,
expired, revoked, satisfied, not-yet-effective and window-ended controls are not
coverage. `CONDITIONAL` alone never implies compensable, and an uncovered
concern is `NOT_READY` — never a silent `READY_WITH_CONDITIONS`.

`PILOT_READY` may carry active pilot controls (the enum has no separate
`PILOT_READY_WITH_CONDITIONS` tier); the bounded pilot scope, exposure and
monitoring are the ones stated on the attached conditions.

### What the evaluator does **not** do

Every result carries standing advisories saying so: the determination is
**advisory and authorizes no deployment** (`result.authorizes_deployment` is
always `False`); the **policy's authenticity is not verified**; every
**gate status is structurally supplied**, not independently verified — there is
no evidence admission, no benchmark resolution and **no metric-to-threshold
comparison** (the merged `GovernedThreshold` keeps opaque literal/unit
semantics, and none are invented); every **`MetricClaim` keeps the exact
evidence axes it arrived with** — `REPORTED`, `UNATTESTED`, `NOT_ATTRIBUTED` and
`UNVERIFIED` are never upgraded; and readiness stays a **leading indicator**,
never money or return. When conditions are used, two further advisories record
that a condition's approval authenticity is unverified and that `ConditionSet`
carries no tenant/subject field, so its scope was **not** matched against the
assessed tenant.

An `AdvisoryComposite` is validated and carried through **unchanged**, is never
consulted when selecting the tier, and is proven inert: moving its score from
scale minimum to maximum with all other inputs fixed yields an identical
classification, rule and reason-code tuple.

**The sharpest form of the trust limitation:** because the `ReadinessPolicy` is
a caller-supplied, unverified artifact, a permissive policy yields a permissive
answer — in the limit, a policy declaring no gates has nothing to fail. The
evaluator proves conformance *to the supplied policy*, never that the policy is
the authentic, authority-issued one. The `R0` lifecycle and effective-period
checks are a **structural read of the supplied metadata** at the evaluation
time: they do not authenticate, sign, resolve or approve the policy, and they do
not replace Policy Authority or registry resolution. An `APPROVED_ACTIVE` label
remains a caller assertion. Closing that gap is deferred.

## Type placement (why here, not governance-contracts)

The ADR §20 lists `ReadinessTarget` / `GateStatus` / a minimal readiness
determination as *candidate* neutral seams in `governance-contracts`
("minimal, **multi-consumer only**"). This milestone places the readiness result
vocabulary (`GateStatus`, `ReadinessClassification`, `AgentValueReadinessDetermination`)
in **this leaf** and **reuses** `ReadinessTarget`/`RequirementClass` from
`uvi-policy-contracts`, because:

1. `ReadinessTarget` is already canonically owned by `uvi-policy-contracts` on
   the merged default (GV-2C-a); splitting its sibling result enums into
   `governance-contracts` would fork the readiness vocabulary across two neutral
   packages.
2. The ADR's "multi-consumer" precondition is **not met** in GV-3R-a — the sole
   consumer of these result types is this leaf; there is no `governed-value`
   integration in this milestone.
3. `governance-contracts` is therefore **unchanged** (no version bump, no
   `CONTRACT_VERSION` change).

Promoting `GateStatus`/the determination to `governance-contracts` is a
documented forward path for when a second consumer appears.

## Structural guarantees

- **Distinct indicator families.** Intelligence, Capability, and Adoption are
  three distinct types; each carries a `ReadinessIndicatorClass`. Capability
  distinguishes *exists* / *tested* / *met the threshold* (`CapabilityDemonstration`)
  from *evidence sufficient* and *mandatory for target* — a missing critical
  capability is representable as a mandatory blocking failure, never averaged away.
- **Adoption ≠ ObservedAdoption.** `AdoptionReadinessResult.pre_deployment` is
  locked `True`; it is a *predicted* pre-deployment indicator, never
  post-deployment observed adoption, and never monetary benefit.
- **Evidence reuse without elevation.** Every indicator binds a GV-2E-a
  `MetricClaim` by value, preserving the five orthogonal evidence axes. A policy
  *requirement* never manufactures evidence, and embedding a claim never elevates
  its attestation/attribution/verification.
- **Non-forgeable gate metadata.** `GateResult` **embeds the actual immutable
  `PolicyGate` by value**; `gate_id`, gate kind, target applicability, the owned
  threshold, `is_diagnostic`, and `is_blocking` are **derived** from it — there
  are no caller-settable `gate_kind`/`applicable`/`threshold_ref` fields, so a
  caller cannot relabel a mandatory gate advisory or mark an applicable gate
  diagnostic. A non-applicable gate (`requested_target ∉ policy_gate.applicability`)
  is diagnostic and never blocking — a production-only gate can't block a PILOT
  target. (This binds the metadata *internally*; it does not prove the embedded
  `PolicyGate` is itself authority-approved — that is GV-3R-b work.)
- **Derived blocking sets.** `blocking_gate_ids` / `indeterminate_gate_ids` are
  **derived properties** of the determination, computed from `gate_results` —
  never caller-supplied summaries — so an applicable mandatory failure cannot be
  hidden by omission.
- **Non-waivable mandatory.** A `ConditionSet` may only govern a `CONDITIONAL`
  concern; `APPROVED_ACTIVE` requires complete authority/owner/monitoring/evidence/time;
  `EXPIRED`/`REVOKED` are never active. Activity at the determination time is
  checked with `is_active_at(as_of)` (`effective_from <= as_of < effective_to/expiry`).
- **Advisory composite.** Optional; `Decimal` only (floats rejected), explicit
  scale, declared method+version, `is_advisory` locked `True`. It can never
  determine or elevate a tier, override a mandatory failure, or be multiplied
  into ROI. No default weights; absent rather than fabricated.
- **Determination consistency (local only, enforced against in-record facts).**
  `PILOT_READY`⇒PILOT; `DEPLOYMENT_READY`/`READY_WITH_CONDITIONS`⇒PRODUCTION.
  Precedence compatibility: any applicable mandatory **FAIL** ⇒ only `NOT_READY`
  is consistent (FAIL dominates INDETERMINATE); an applicable mandatory
  **INDETERMINATE** with no FAIL ⇒ only `NOT_ASSESSABLE`. A **ready class is
  rejected if any `gate_result` is a blocking or applicable-mandatory-indeterminate
  gate** (scanned from `gate_results`, not a summary). `READY_WITH_CONDITIONS`
  requires every applicable unresolved CONDITIONAL concern to be covered by a
  condition **active at the determination time**, and rejects conditions that
  cover no such concern. `DEPLOYMENT_READY` rejects any unresolved conditional
  concern or open active condition (historical `SATISFIED` allowed). Every
  `gate_result` must belong to the determination's `readiness_policy_ref`
  (id/version/digest/tenant/family). `NOT_READY`/`NOT_ASSESSABLE` need a reason;
  cross-tenant/context binding and duplicates rejected. **The classification is a
  caller input — it is not *computed* from the gates here; the contract only
  rejects a classification that contradicts the record.**
- **Immutable + deterministic.** Frozen dataclasses; every sequence normalized to
  a real tuple (scalar substitutes rejected); `canonical_digest()` sha-256 stable
  under caller-list mutation; naive timestamps and blank identifiers rejected.

## Contracts versus evaluator

The contract shapes still accept a caller-supplied `classification` and only
*reject* one that contradicts their in-record facts — that local guard is
unchanged. **Selecting** the classification is `evaluate_readiness`, and it is
the single canonical path: no other public symbol produces a tier, so there is
no second calculation route that could diverge from the ratified precedence.

## Install & use

```bash
python -m build packages/capabilities/agent-value-readiness
pip install --find-links dist ugence-agent-value-readiness   # resolves the two contract leaves
```

Independent-distribution proof (builds all three wheels, installs `--no-index`):

```bash
python packages/capabilities/agent-value-readiness/verify_agent_value_readiness_distribution.py
```

## Extensibility & trust notes

- **Dimension catalog (extensibility).** `IntelligenceDimension` /
  `CapabilityDimension` / `AdoptionDimension` are the initial **shared canonical
  taxonomy**, not an exhaustive universal model. Domain-specific metrics remain
  expressible through the free-form governed `metric_id` on the embedded
  `MetricClaim` and through policy-selected metrics; adding a new canonical
  dimension is a **versioned contract evolution**, not a per-caller free-form
  field. No scoring or financial-modifier field is added.
- **What the embedded `PolicyGate` proves — and does not.** Embedding the gate
  prevents *internal* metadata contradiction (kind/applicability/threshold can't
  be forged relative to the gate). It does **not** prove the `PolicyGate` or its
  `ReadinessPolicy` is authentic, authority-approved, or registry-resolved;
  `APPROVED_ACTIVE` on a `ConditionSet` is a structurally-asserted label, not
  proof a real authority approved it; a well-formed `content_digest` is not a
  resolved-body proof. Those verifications belong to Policy Authority and
  GV-3R-b. Readiness remains **advisory**; deployment governance is separate.

## Deferred (out of scope)

Deployment authorization, Policy Authority (signing/approval/issuance/
revocation), policy and benchmark registry/resolver, evidence admission or
verification, machine-evaluable threshold semantics and metric-to-threshold
calculation, condition-authority resolution and runtime enforcement,
`SubjectContext`/`AssessedSystemBinding` (RA-owned, PR #1425), a durable event
bus or signed determination record, forecasting, realization-probability
modeling, attributed/verified return, financial valuation, and `governed-value`
integration.
