# ugence-agent-value-readiness

> **⚠️ Experimental, internal, advisory, non-financial.**
> The **contract shapes** (GV-3R-a), the **deterministic readiness determination
> evaluator** (GV-3R-b), and the **fail-closed trusted orchestration boundary**
> around that evaluator (GV-3R-c) for the Agent Value Readiness engine of Ugence
> Value Intelligence — **not** a deployment authority, **not** a Policy
> Authority, **not** a metric-evaluation engine, and **not** a customer-facing
> module.
> - **No deployment authorization** — a determination is *advisory*, consumed by
>   a separate human/deployment-governance process.
> - **No evidence admission or verification, no benchmark resolution, no
>   metric-to-threshold calculation.** The evaluator consumes gate statuses
>   recorded by an upstream evaluator; it does not compute them. Whether those
>   statuses are *trusted* is the configured gate verifier's answer, never this
>   package's.
> - **No money, currency, cost, benefit, or ROI** anywhere.
> - **Nothing is trusted by default.** Used standalone, the evaluator treats
>   lifecycle labels, digests, condition approvals and gate statuses as
>   structural caller inputs. Used through `assess_readiness`, each becomes the
>   responsibility of a configured trust boundary that **denies** when absent.
> - **No allow-all or "testing" verifier ships** — that absence is the boundary.
> - **Benchmark registry, evidence/TAP verification, condition enforcement and
>   RA-owned subject/system binding remain deferred.**

The vocabulary for assessing whether an agent is ready for an intended outcome:

```
PreROIReadiness = f(Intelligence, Capabilities, Adoption
                    | Geography, Domain, IntendedOutcome)
```

Intelligence, Capability, and Adoption are **non-financial leading indicators**.
This package implements **M-3R.1 (GV-3R-a, contract shapes)**, **M-3R.2
(GV-3R-b, the determination evaluator)** and, additively, **GV-3R-c — trusted
readiness orchestration** around that evaluator, per the UVI ADR
(`docs/architecture/ADR_UGENCE_VALUE_INTELLIGENCE_GV2C_GV2E_GV3R.md`, §5–§10,
§19, §20, §23) and the shared Policy Authority ADR
(`docs/architecture/ADR_UGENCE_POLICY_AUTHORITY.md`, §5, §10.4). Policy
**issuance, signing, approval verification, registration and revocation** stay
with the shared Ugence Policy Authority; this package only **consumes** its
public trusted-resolution service.

- **Distribution:** `ugence-agent-value-readiness`
- **Namespace:** `ugence_agent_value_readiness`
- **Version:** 0.3.0
- **Depends on:** stdlib **+ `ugence-governance-contracts>=0.2.0`** (evidence vocabulary) **+ `ugence-uvi-policy-contracts>=0.1.0`** (policy/context shapes) **+ `ugence-policy-authority>=0.1.0`** (public trusted policy resolution only) — never `governed-value`, and never an authority internal.
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
| **Orchestration (GV-3R-c)** | `assess_readiness`, `ReadinessAssessmentRequest`, `ReadinessAssessmentOutcome`, `ReadinessAssessmentTrace`, `ReadinessAssessmentDisposition`, `READINESS_ORCHESTRATOR_VERSION` |
| **Orchestration verification** | `GateVerificationRequest`, `GateResultVerification`, `GateVerificationSummary`, `ConditionVerificationRequest`, `ConditionSetVerification`, `ConditionVerificationSummary` |
| **Orchestration codes** | `ReadinessAssessmentStatus`, `ReadinessInputVerificationStatus`, `ReadinessTrustGapCode`, `ReadinessTrustAdvisoryState` |
| **Injected trust boundaries** | `ReadinessPolicyResolver`, `GateResultVerifier`, `ConditionSetVerifier` (protocols); `DenyAllReadinessPolicyResolver`, `DenyAllGateResultVerifier`, `DenyAllConditionSetVerifier` (production defaults); `PolicyAuthorityReadinessPolicyResolver` (adapter onto the shared authority) |
| Errors | `ReadinessContractError`, `ReadinessEvaluationError`, `ReadinessAssessmentError` |

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
| `R0` | governing context/policy invalid: policy not bound to the context, bound reference is a different policy, policy not `APPROVED_ACTIVE`, or not effective at `evaluation_time` | `NOT_ASSESSABLE` |
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

**`R0` is the ADR §6 precondition (§7 row 0)** and precedes every gate rule. It
is the single canonical detection point for four conditions, any of which means
the assessment is not governed by a valid policy:

1. the `AssessmentContext` binds **no** readiness-policy reference;
2. the bound reference is **not** the supplied policy — compared with the merged
   `PolicyReference` equality, covering policy id, family, version, content
   digest, scope and tenant together (no partial or floating match);
3. the policy's `metadata.lifecycle_state` is not `APPROVED_ACTIVE`;
4. `metadata.is_effective_at(evaluation_time)` is false (half-open
   `effective_from <= t < effective_to`).

A definite mandatory `FAIL` dominates other *gate-level* uncertainty, but it
never overrides an invalid governing context or policy. Under `R0` "no headline
is asserted" (ADR §6): the determination carries **no** gate results and its
derived blocking/indeterminate id sets stay empty, while the trace still reports
the full gate inventory and every failure **diagnostically** — visible for
audit, never converted into a readiness headline.

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

**The sharpest form of the trust limitation (standalone use):** because the
`ReadinessPolicy` is then a caller-supplied, unverified artifact, a permissive
policy yields a permissive answer — in the limit, a policy declaring no gates has nothing to fail. The
evaluator proves conformance *to the supplied policy*, never that the policy is
the authentic, authority-issued one. The `R0` binding, lifecycle and
effective-period checks are a **structural read of caller-supplied contracts**
at the evaluation time: they do not authenticate, sign, resolve or approve the
policy, and they do not verify a `content_digest` against a registry-resolved
body — matching digests only proves the context and the supplied policy claim
the same identity. An `APPROVED_ACTIVE` label remains a caller assertion. None
of this replaces Policy Authority or registry resolution — **that gap is what
GV-3R-c closes**, by requiring the exact policy to resolve through the shared
authority's public trusted-resolution service before any gate is even looked at.
A permissive *policy* still yields a permissive answer; what GV-3R-c adds is the
proof that the policy is the authentic, authority-issued one.

## The orchestration boundary (GV-3R-c)

```python
from ugence_agent_value_readiness.api import assess_readiness

outcome = assess_readiness(
    request,                                # carries no classification, no policy body
    policy_resolver=configured_resolver,    # omit -> DENY
    gate_verifier=configured_gate_verifier, # omit -> DENY
    condition_verifier=configured_verifier, # omit -> DENY
)
outcome.status            # EVALUATED | NOT_EVALUATED
outcome.classification    # the GV-3R-b tier, or None when nothing was evaluated
outcome.trust_gap_codes   # stable, typed, ordered — every gap is explicit
outcome.dispositions      # what happened to each standing GV-3R-b advisory
outcome.authorizes_deployment   # permanently False
```

`assess_readiness` **adds no second classification algorithm.** It resolves,
verifies, sanitizes, then calls the one ratified `evaluate_readiness` exactly
once over a freshly built case. An automated test proves no module outside the
evaluator names a `ReadinessClassification` member or builds a
`ReadinessEvaluationResult`.

### The four stages, and what each failure means

| Stage | Establishes | On failure |
|---|---|---|
| 1 — policy resolution | the exact `ReadinessPolicy` resolved through the configured shared Policy Authority boundary at `evaluation_time` | `NOT_EVALUATED`; **no** later stage runs, no verifier is called, no classification exists |
| 2 — gate verification | each gate result was attested under its complete binding | that result is **absent** for the evaluator |
| 3 — condition verification | each compensating control was attested for its exact concern | that control provides **no coverage** |
| 4 — evaluation | one `evaluate_readiness` call over sanitized input | an advisory determination + deterministic trace |

**Policy-resolution failure dominates all gate information.** Under it the
outcome preserves **no usable policy material** — no issuance-record reference,
no resolved-policy digest — only the typed gap codes and the reference the
caller already holds.

### What resolution must prove before anything else runs

Resolution status is `RESOLVED`; a policy **and** issuance record are present;
the artifact is a `ReadinessPolicy`; its complete `PolicyReference` (family, id,
version, content digest, scope, tenant) equals the requested one; the requested
reference's tenant identity is the assessed tenant; the `AssessmentContext`
binds exactly this reference; the resolved policy governs the requested target;
the resolution's `as_of` **is** the requested evaluation instant; the answer is
not historical; and — as defence in depth — the resolved artifact's own metadata
is still `APPROVED_ACTIVE` and effective at that instant. Each of those is
rechecked by the orchestrator itself, so a lax resolver cannot get a mismatched
policy admitted.

### Sanitization and precedence

Sanitization is **subtraction, never substitution**. An unverified result is
absent — not `PASS`, not `INDETERMINATE`, not a caller-flavoured hint — and the
merged GV-3R-b precedence is untouched:

| Supplied input | Effect on the classification |
|---|---|
| verified mandatory `FAIL` | dominates missing/unverified required gates ⇒ `NOT_READY` |
| unverified `FAIL` | none — the gate is absent, so the case is incomplete |
| unverified `PASS` | none — it cannot unlock any tier |
| unverified `INDETERMINATE` | none |
| missing or unverified **required** gate | `NOT_ASSESSABLE`, unless a verified mandatory `FAIL` already proves `NOT_READY` |
| unverified **advisory** result | never blocks and never elevates |
| production-only gate under `PILOT` | diagnostic, as before |
| duplicate, wrong-policy, wrong-target, unknown or tampered gate | every copy rejected with a stable gap code — never silently accepted |
| verified active condition over its exact compensable concern | coverage ⇒ `READY_WITH_CONDITIONS` |
| unverified, proposed, expired, revoked, satisfied, future-effective or elapsed condition | no coverage |
| condition over a mandatory concern | refused — a mandatory failure is never waivable (D-6) |

Input order never affects the classification, the reason codes, the trace or any
digest: inputs are processed in canonical id order and gap codes are emitted in
enum declaration order.

### Verifier contracts

A `GateResultVerifier` is asked about **one** gate result under its complete
binding — tenant, subject, `AssessmentContext` digest, requested target, policy
reference, the gate **as resolved** (not the caller's copy), its canonical
digest, the claimed status, and the evaluation instant. It answers with a stable
`ReadinessInputVerificationStatus`: `VERIFIED`, `NO_VERIFIER_CONFIGURED`,
`EVIDENCE_NOT_VERIFIED`, `BENCHMARK_NOT_RESOLVED`,
`THRESHOLD_EVALUATION_NOT_VERIFIED`, `APPROVAL_NOT_VERIFIED`,
`REFERENCE_MISMATCH` or `VERIFIER_ERROR` — never a free-form reason.

The orchestrator then **rechecks every coordinate the verifier returned** and
rejects a duck-typed object outright. A `VERIFIED` answer must also cover what
the gate actually relies on: the cited evidence, the threshold evaluation, and a
referenced benchmark's resolution. Evidence and benchmark authenticity are the
**gate verifier's** responsibility, never the orchestrator's.

A `ConditionSetVerifier` is asked about one control covering one exact concern,
and must independently establish its identity and canonical digest, its approval
authority and approval evidence, its owner/monitoring obligations, its status,
its window, and — because the merged `ConditionSet` carries no tenant field —
its tenant, subject and context binding. Coverage additionally requires the gate
to be `CONDITIONAL`, the policy to mark it `conditionally_compensable`, and the
control to be active at the evaluation instant under the half-open interval.

### Deny by default

Omitting a resolver or a verifier is not "unchecked", it is **denied**:
`DenyAllReadinessPolicyResolver`, `DenyAllGateResultVerifier` and
`DenyAllConditionSetVerifier` are the production defaults, and they take no
constructor argument that could relax them. A verifier that raises, times out,
or returns a malformed object produces a stable fail-closed gap — never an
acceptance, and never a fallback to caller metadata. **No allow-all, permissive
or "testing" verifier exists in this distribution**; a test that needs one
writes it inside its own test module, where it can never ship.

Supplying a real resolver or verifier is a **composition-root trust decision**.
A lax implementation is still constrained: because every returned coordinate is
rechecked, it can only weaken the claim about the input it was asked about — it
can never get a mismatched policy, gate, condition, tenant, subject, context,
target or instant admitted.

### Trust-advisory reconciliation

The standalone evaluator is right to emit its advisories: it genuinely cannot
verify an external trust boundary. GV-3R-c never deletes or contradicts one — it
states, per advisory, which configured boundary closed it:

| GV-3R-b advisory | Disposition under a fully configured assessment |
|---|---|
| `POLICY_AUTHENTICITY_NOT_VERIFIED` | `RESOLVED_BY_POLICY_RESOLUTION` |
| `GATE_STATUS_STRUCTURALLY_SUPPLIED` (incl. evidence + benchmark authenticity) | `RESOLVED_BY_GATE_VERIFICATION` |
| `CONDITION_APPROVAL_AUTHENTICITY_NOT_VERIFIED` | `RESOLVED_BY_CONDITION_VERIFICATION` |
| `CONDITION_SCOPE_NOT_TENANT_BOUND` | `RESOLVED_BY_CONDITION_VERIFICATION` |
| `ADVISORY_ONLY_NOT_DEPLOYMENT_AUTHORIZATION` | `OUT_OF_SCOPE` — a permanent boundary |
| `EVIDENCE_CLASSIFICATION_PRESERVED` | `OUT_OF_SCOPE` — a permanent guarantee |
| `READINESS_IS_LEADING_INDICATOR_ONLY` | `OUT_OF_SCOPE` |
| `COMPOSITE_CARRIED_NOT_USED_IN_SELECTION` | `OUT_OF_SCOPE` |

Each of the first four is `RESOLVED_BY_…` only when **every** input of its kind
was verified: one unverified gate result or control leaves the corresponding
advisory `UNRESOLVED`, with a detail naming how many were refused.
**Benchmark and evidence authenticity stay unresolved unless the configured gate
verifier proves them.** No advisory is ever marked resolved because a caller
supplied a boolean or a structurally complete record.

### The outcome envelope

The trace reports what the **authority** answered
(`policy_resolution_status` / `policy_resolution_reason`) and, separately,
whether the **orchestrator accepted** it after its own rechecks
(`policy_resolution_accepted`). A legitimately resolved policy this assessment
still had to refuse — a context binding a different policy, an ungoverned
target, an `as_of` that is not the evaluation instant — is therefore never
readable as an accepted one. Acceptance and policy material are the same fact
stated twice: an accepted trace must carry the issuance-record reference and
resolved-policy digest, an unaccepted one must carry neither, and only an
accepted trace can back an `EVALUATED` outcome.

`NOT_EVALUATED` carries **no** evaluation result and **no** classification — the
constructor rejects one — and must name at least one trust gap. `EVALUATED`
carries exactly one `ReadinessEvaluationResult` whose assessment id, tenant,
subject, context digest, policy reference, target and instant all agree with the
trace. The trace has **no classification field at all**, so a trace/evaluation
mismatch is unrepresentable rather than merely rejected; the summaries,
dispositions and gap codes are read-only views, not settable fields.

The outcome is **not signed**: a signed readiness determination requires a
separately ratified authority owner. Constructing an outcome by hand is possible
and proves **nothing** — exactly as a hand-assembled `PolicyResolution` proves
nothing about the shared Policy Authority. Only `assess_readiness` performs
orchestration.

### The evaluator stays independently usable

Nothing above is required to use GV-3R-b. `evaluate_readiness` needs no
resolver, no verifier, no authority wiring and no runtime configuration; the
`contracts` and `evaluation` subpackages import no authority module at all, and
an automated boundary test enforces that.

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
pip install --find-links dist ugence-agent-value-readiness   # resolves the contract leaves + the shared authority
```

Independent-distribution proof (builds all four wheels, installs `--no-index`):

```bash
python packages/capabilities/agent-value-readiness/verify_agent_value_readiness_distribution.py
```

Independent adversarial probes (public API only, no shared test fixtures):

```bash
python packages/capabilities/agent-value-readiness/adversarial_probes.py
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

Deployment authorization; policy signing, approval, issuance and revocation
(owned by the shared Ugence Policy Authority, consumed here through its public
resolution service only); the **benchmark registry** and benchmark-value
governance; **TAP/evidence verification** implementations (GV-3R-c defines the
verifier seam and ships only its deny-all default — it implements no verifier);
machine-evaluable threshold semantics and metric-to-threshold calculation;
structured successor/supersession references; **condition runtime enforcement**;
`SubjectContext`/`AssessedSystemBinding` (RA-owned, PR #1425); a durable event
bus or **signed** determination record; forecasting, realization-probability
modeling, attributed/verified return, financial valuation, and `governed-value`
integration.
