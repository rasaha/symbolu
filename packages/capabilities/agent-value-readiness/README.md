# ugence-agent-value-readiness

> **⚠️ Experimental, internal, contracts-only, non-financial.**
> These are the **contract shapes** for the Agent Value Readiness engine of
> Ugence Value Intelligence — **not** the evaluator, **not** a deployment
> authority, and **not** a customer-facing module.
> - **No readiness evaluation, precedence calculus, or tier selection.**
> - **No deployment authorization** — a determination is *advisory*, consumed by
>   a separate human/deployment-governance process.
> - **No money, currency, cost, benefit, or ROI** anywhere.
> - **Caller-provided artifacts are not authority-verified.** Lifecycle labels,
>   digests, condition approvals, and gate statuses are structural inputs;
>   verifying them is Policy-Authority / GV-3R-b work.
> - **Policy Authority and richer RA-owned subject/system binding are deferred.**

The vocabulary for assessing whether an agent is ready for an intended outcome:

```
PreROIReadiness = f(Intelligence, Capabilities, Adoption
                    | Geography, Domain, IntendedOutcome)
```

Intelligence, Capability, and Adoption are **non-financial leading indicators**.
This is milestone **M-3R.1 (GV-3R-a)** of the UVI ADR
(`docs/architecture/ADR_UGENCE_VALUE_INTELLIGENCE_GV2C_GV2E_GV3R.md`, §5–§10, §20).
Evaluation — the precedence calculus, tier selection, authority resolution — is
**GV-3R-b (M-3R.2)** and is out of scope here.

- **Distribution:** `ugence-agent-value-readiness`
- **Namespace:** `ugence_agent_value_readiness`
- **Version:** 0.2.0 (adds the GV-3R-b evaluator; GV-3R-a contract shapes unchanged)
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
| Error | `ReadinessContractError` |

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

## Precedence representation (inputs/outputs only)

GV-3R-a can *represent* the ratified precedence — invalid context ⇒
`NOT_ASSESSABLE`; applicable mandatory `FAIL` ⇒ `NOT_READY` (FAIL dominates an
unrelated `INDETERMINATE`); applicable mandatory `INDETERMINATE` ⇒
`NOT_ASSESSABLE`; all applicable mandatory `PASS` ⇒ conditional-resolution — via
its gate results, `blocking_gate_ids`, and `indeterminate_gate_ids`. **Selecting**
the classification from those inputs is **GV-3R-b**.

## Install & use

```bash
python -m build packages/capabilities/agent-value-readiness
pip install --find-links dist ugence-agent-value-readiness   # resolves the two contract leaves
```

Independent-distribution proof (builds all three wheels, installs `--no-index`):

```bash
python packages/capabilities/agent-value-readiness/verify_agent_value_readiness_distribution.py
```

## GV-3R-b — deterministic readiness evaluator (0.2.0)

The single canonical entry point:

```python
from ugence_agent_value_readiness.api import evaluate_readiness, ReadinessEvaluationCase
result = evaluate_readiness(case, evaluation_time=<tz-aware datetime>)
result.classification            # the selected ReadinessClassification (advisory)
result.determination             # the full AgentValueReadinessDetermination
result.trace                     # deterministic EvaluationTrace (rule + reason codes)
```

`evaluate_readiness(case, *, evaluation_time)` **selects** one advisory
classification — the caller supplies **no** classification (`ReadinessEvaluationCase`
has no such field). It is:

- **Advisory & non-authoritative.** It authorizes no deployment, verifies no
  evidence, resolves no benchmark, calculates no metric-to-threshold, checks no
  policy authenticity, and performs no attribution. It consumes `GateResult.status`
  as **structurally supplied, authority-unverified** input — it is a
  *determination evaluator over supplied gate results*, not a metric-evaluation
  engine. Every result carries advisory reason codes (policy-authenticity /
  condition-approval not verified, evidence retains its source classification,
  not a deployment authorization) and preserves every MetricClaim's evidence
  axes (never upgrades REPORTED→OBSERVED, UNATTESTED→ATTESTED, etc.).
- **Non-financial.** No money/ROI/forecast. An `AdvisoryComposite`, if present,
  is validated and **carried through unchanged but never consulted** for the tier
  (a test proves min↔max score leaves the classification and rule unchanged).
- **Fail-closed & complete.** The authoritative gate inventory is derived from the
  supplied `ReadinessPolicy` body; every applicable **MANDATORY** and **CONDITIONAL**
  gate must have exactly one `GateResult` — a missing one yields `NOT_ASSESSABLE`
  (never a silent PASS), and a caller cannot omit a difficult gate. Structural
  malformations (cross-tenant, a gate bound to another policy, an embedded
  `PolicyGate` that doesn't match the policy's gate, a duplicate/mismatched-target
  gate, a policy body that doesn't match its reference) raise
  `ReadinessEvaluationError`.
- **Deterministic.** Identical inputs + `evaluation_time` produce an identical
  classification, ordered reason codes, gate sets, and digest; outputs are
  canonically ordered by stable id and never depend on input order.
  `evaluation_time` is a mandatory, timezone-aware keyword — the system clock is
  never read.

**Decision ordering (fail-closed):** a definite applicable **mandatory FAIL**
dominates ⇒ `NOT_READY` (even if another required gate is missing — supplying it
can't make it ready); else a missing applicable required gate ⇒ `NOT_ASSESSABLE`;
else an applicable mandatory **INDETERMINATE** ⇒ `NOT_ASSESSABLE`; else conditional
resolution. An unresolved applicable **CONDITIONAL** concern (FAIL/INDETERMINATE)
is compensable **only if** `PolicyGate.conditionally_compensable is True` **and** an
active (`is_active_at(evaluation_time)`) `ConditionSet` references that exact gate;
otherwise ⇒ `NOT_READY`. **PILOT** ⇒ `PILOT_READY` when all applicable mandatory
PASS and every unresolved conditional concern is compensable+covered (covering
conditions are carried as bounded pilot controls; there is no
`PILOT_READY_WITH_CONDITIONS`, and production-only gates stay diagnostic).
**PRODUCTION** ⇒ `READY_WITH_CONDITIONS` when compensated conditional concerns
remain, else `DEPLOYMENT_READY` (no unresolved concern, no open active condition;
historical `SATISFIED` conditions retained only when their gate now PASSES).

**Honest limitation:** the merged contracts express Intelligence/Capability/Adoption
requirements *through gates*, not a separate policy flag — so the evaluator does
**not** invent a standalone "Intelligence required" rule; a missing indicator
manifests through the gate that depends on it (as a missing/indeterminate/failed
`GateResult`). Indicator results are carried through unchanged.

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

The readiness evaluator (GV-3R-b), precedence/tier selection, deployment
authorization, Policy Authority, policy/benchmark registry, evidence admission or
verification, `SubjectContext`/`AssessedSystemBinding` (RA-owned, PR #1425),
forecasting, realization-probability modeling, attributed/verified ROI, financial
valuation, `governed-value` integration, and `ConditionSet` runtime enforcement.
