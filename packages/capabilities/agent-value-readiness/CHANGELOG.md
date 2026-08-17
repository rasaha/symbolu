# Changelog — ugence-agent-value-readiness

## [0.3.0] — Trusted Readiness Orchestration

**Additive integration capability, not a roadmap milestone.** A fail-closed
**trust boundary around** the merged GV-3R-b evaluator. Minor bump because this
is a material new capability on top of a merged 0.2.0; every 0.2.0 symbol keeps
its shape and behaviour, so existing callers are unaffected and the standalone
evaluator is untouched.

### What this is, and what it is not
- It implements requirements that are **already ratified**: UVI ADR **D-1**,
  **D-16**, **§19** and **§23.2** (fail closed on unsigned / unapproved /
  expired / revoked / superseded / digest-mismatched policy artifacts), and
  shared Policy Authority ADR **§5** and **§10.4**. It defines **no new
  milestone**.
- It **does not define a new readiness classification** and **does not replace
  or alter GV-3R-b**: the ratified precedence is untouched and the tier is still
  selected by exactly one function, called exactly once.
- It sits operationally **between** the deterministic evaluator (M-3R.2) and
  future **M-3R.3** integration work. **M-3R.3 still owns** the
  `IntelligenceFitness` / `CapabilityReadiness` / `AdoptionReadiness` catalogs
  and `AssessedSystemBinding` wiring; **neither is implemented here, and that
  milestone remains open.**
- The output remains **advisory** and **never authorizes deployment**.

### Version identity
`EVALUATOR_FORMULA_VERSION` **stays `GV-3R-b.3`** — the classification algorithm
did not change. `READINESS_ORCHESTRATOR_VERSION` is
**`ugence.readiness-orchestration/v0.1`**: a platform-neutral capability
identifier that names no ADR milestone and asserts no roadmap position. The
`GV3RC_` prefix on `ReadinessTrustGapCode` values is retained as a **frozen
opaque token** — it participates in canonical trace digests, so renaming it
would change published behaviour to make a cosmetic point; it carries no
milestone meaning. No other package is touched: `governance-contracts`,
`uvi-policy-contracts`, `ugence-policy-authority` and `governed-value` are all
unchanged, and **no ADR is modified**.

### Added — the single canonical orchestration entry point
- `assess_readiness(request, *, policy_resolver=None, gate_verifier=None,
  condition_verifier=None)` — resolves, verifies, sanitizes, then calls the one
  ratified `evaluate_readiness` **exactly once** over a freshly built case. It
  never accepts, recomputes or second-guesses a classification.
- `ReadinessAssessmentRequest` — the immutable input. It carries the assessment
  id, `AssessmentContext`, exact readiness `PolicyReference`, requested target,
  mandatory timezone-aware `evaluation_time`, gate results, conditions, the
  three indicator families, an optional advisory composite and
  evidence/window references — and deliberately **no** classification, **no**
  caller-supplied trust boolean, **no** policy lifecycle conclusion, **no**
  deployment authorization, **no** financial field, **no** system-clock default
  and **no policy body**, so nothing can disagree with the resolved policy.
- `ReadinessAssessmentOutcome` / `ReadinessAssessmentTrace` /
  `GateVerificationSummary` / `ConditionVerificationSummary` /
  `ReadinessAssessmentDisposition` — the advisory outcome and its deterministic
  provenance trace. `authorizes_deployment` is a permanently-`False` **property**,
  not a field; the outcome is **unsigned**.
- Stable enums: `ReadinessAssessmentStatus`, `ReadinessInputVerificationStatus`,
  `ReadinessTrustGapCode`, `ReadinessTrustAdvisoryState`. Codes are emitted in
  enum declaration order, never input order.
- Injected trust boundaries: the `ReadinessPolicyResolver` /
  `GateResultVerifier` / `ConditionSetVerifier` protocols, their
  `DenyAll…` production defaults, and
  `PolicyAuthorityReadinessPolicyResolver` — a thin adapter onto the shared
  authority's **public** `resolve_policy`.
- `GateVerificationRequest` / `GateResultVerification` /
  `ConditionVerificationRequest` / `ConditionSetVerification` — the complete
  binding handed to a verifier and the answer it returns. A non-`VERIFIED`
  answer structurally **cannot** carry a verified status or a satisfied
  supporting-verification flag.
- `ReadinessAssessmentError` (subclasses `ReadinessContractError`).

### Dependency
- Adds `ugence-policy-authority>=0.1.0`, **public API only**. Four automated
  boundary tests enforce it: no authority internal (`…core`, `…adapters`) is
  named; only the `orchestration` subpackage may import the authority at all;
  the `contracts` and `evaluation` subpackages stay authority-free so the
  evaluator remains independently usable; and the authority imports no engine.
  No signature, approval, revocation, registry, canonicalization or lifecycle
  logic is reproduced here, and no `PolicyResolution` / `PolicyReference` /
  lifecycle / digest type is duplicated.

### Fail-closed behaviour
- **Production defaults deny.** No resolver ⇒ `NOT_EVALUATED`. No gate verifier
  ⇒ no gate result can influence the classification. No condition verifier ⇒ no
  control provides coverage.
- **Policy-resolution failure dominates all gate information**: no verifier is
  called, `evaluate_readiness` never runs, no classification or determination is
  produced, and the failure outcome preserves **no usable policy material**.
- Resolution is independently rechecked after the fact: resolved status, policy
  and issuance record present, artifact is a `ReadinessPolicy`, complete
  `PolicyReference` equality, tenant binding, context binding, target governed,
  `as_of` equals the evaluation instant, historical answers refused, and — as
  defence in depth — the resolved artifact still `APPROVED_ACTIVE` and effective.
  What the **authority** answered and whether the **orchestrator accepted** it
  are reported as two separate trace facts (`policy_resolution_status` /
  `policy_resolution_reason` versus `policy_resolution_accepted`), so a resolved
  answer this assessment refused can never be read as an accepted one; only an
  accepted resolution may carry policy material, and only an accepted trace can
  back an `EVALUATED` outcome.
- A verifier object without a callable verification method is recorded as a gap
  **up front**, exactly as a malformed resolver is, so a broken composition root
  is never quieter than an absent one.
- A verifier exception, malformed return or duck-typed object produces a stable
  fail-closed gap. Nothing ever falls back to caller metadata, and no shared
  state is mutated.
- **No allow-all, permissive or "testing" verifier ships** in the wheel or the
  public API; an AST test and the isolated wheel verifier both assert it.

### Sanitization and precedence (GV-3R-b algorithm unchanged)
Sanitization is **subtraction, never substitution**. An unverified result is
*absent*, so a verified mandatory `FAIL` still dominates missing or unverified
required gates (`NOT_READY`), an unverified `PASS`/`FAIL`/`INDETERMINATE`
influences nothing, a missing verified required gate is `NOT_ASSESSABLE`,
unverified advisory results neither block nor elevate, production-only gates
stay diagnostic for `PILOT`, and duplicate / wrong-policy / wrong-target /
unknown / tampered gates are rejected with stable codes rather than silently
accepted. Input order cannot change the classification, reasons, trace or digest.

### Conditions
A control compensates only when the resolved policy marks the exact concern
`CONDITIONAL` **and** `conditionally_compensable`, the control is active at the
evaluation instant under the merged half-open interval, and the configured
verifier attests its identity, canonical digest, source-gate reference, approval
authority, approval evidence, owner/monitoring obligations, status, window and —
because the merged `ConditionSet` has no tenant field — its tenant, subject and
context binding. A mandatory concern remains non-waivable (D-6). Rejected
controls stay visible in the trace with a stable reason. No runtime enforcement
is implemented.

### Indicators and evidence
Intelligence, Capability and Adoption remain distinct and diagnostic; **no**
global "all three families required" heuristic was reintroduced; indicator
absence alone never blocks a gate-complete policy; supplied indicators keep
their exact tenant / subject / context binding; `MetricClaim` evidence axes are
carried through unchanged with no `REPORTED→OBSERVED`, `OBSERVED→ATTRIBUTED` or
`ATTRIBUTED→VERIFIED` elevation; and neither a favourable indicator nor a
maximal composite can rescue a mandatory failure.

### Trust-advisory reconciliation
Every standing GV-3R-b advisory receives an explicit disposition —
`RESOLVED_BY_POLICY_RESOLUTION`, `RESOLVED_BY_GATE_VERIFICATION`,
`RESOLVED_BY_CONDITION_VERIFICATION`, `UNRESOLVED`, or `OUT_OF_SCOPE` for a
permanent boundary. Nothing is marked resolved because a caller supplied a
boolean or a structurally complete record, and **benchmark/evidence authenticity
stays `UNRESOLVED` unless the configured gate verifier proves it**.

### Tests
154 new tests (245 → **399**), all public-API, across policy resolution, gate
verification, condition verification, indicator/evidence honesty, the outcome
envelope and disposition, and determinism/immutability — plus an AST scan
proving no wall clock, randomness, uuid, environment, network or mutable module
global exists anywhere in the package. A new **39-probe** from-scratch
adversarial harness (`adversarial_probes.py`) attacks the public API with no
shared fixtures. The isolated multi-wheel `--no-index` verifier now builds four
wheels and proves the orchestration boundary, its deny-by-default posture and
the absence of any permissive verifier from the installed distribution.

### Not implemented (deliberate)
**Milestone M-3R.3 is untouched and remains open**: no `IntelligenceFitness` /
`CapabilityReadiness` / `AdoptionReadiness` catalog and no
`AssessedSystemBinding` wiring is introduced. Also absent: benchmark registry,
TAP/evidence verification implementations, structured successor references,
deployment authorization, condition runtime enforcement, signed readiness
determinations (a separately ratified authority owner is required), forecasting
and financial valuation.

## [0.2.0] — context-binding precedence correction (pre-merge, still 0.2.0/unreleased)

Completes ADR §6 precondition row 0. Package version stays **0.2.0**; the
evaluator formula constant advances **`GV-3R-b.2` → `GV-3R-b.3`** because
evaluator precedence changed. No dependency version or `CONTRACT_VERSION` moves,
and no ADR is touched.

### Context-to-policy binding is an R0 precondition
`GV3RB_READINESS_POLICY_NOT_BOUND_TO_CONTEXT` and
`GV3RB_READINESS_POLICY_REF_CONTEXT_MISMATCH` previously ran in the later
incomplete-input rule (`R2`), so a mandatory `FAIL` under a context that did not
bind the evaluated policy produced `NOT_READY` — a gate-derived headline
asserted from a context that does not govern that policy. Both conditions now
run inside `GV3RB_R0_POLICY_PRECONDITION`, alongside the lifecycle and
effective-period checks, as a **single canonical detection path** (they are not
evaluated twice).

- An absent binding, or a bound reference whose `PolicyReference` identity
  (policy id, family, version, content digest, scope, tenant) is not the
  supplied policy's, now yields `NOT_ASSESSABLE` via `R0` **before** any gate
  precedence. Merged identity-comparison semantics are reused; no partial or
  floating reference matching was introduced.
- The established `R0` output convention applies unchanged: no gate headline is
  asserted (`determination.gate_results == ()`, derived blocking/indeterminate
  id sets empty) while the trace still carries mandatory failures, missing gates
  and other diagnostics for audit. Diagnostic trace data never changes the `R0`
  classification.
- Combined `R0` failures (binding + lifecycle, binding + expiry, mismatch +
  not-yet-effective, and all three plus a mandatory `FAIL`) each retain every
  independently detectable reason, in stable declaration-driven order, with
  input ordering unable to change the result, trace or digest.
- Correctly bound cases are unaffected: mandatory `FAIL` → `NOT_READY`,
  mandatory `INDETERMINATE` → its own rule, missing required gate → the
  incomplete-input rule, and the PILOT / `READY_WITH_CONDITIONS` /
  `DEPLOYMENT_READY` paths are unchanged.
- These remain **structural reads of caller-supplied contracts**: they do not
  authenticate a policy, verify its digest against a registry-resolved body, or
  replace Policy Authority. All standing trust advisories are preserved and
  `authorizes_deployment` stays permanently `False`.

### Tests
28 new tests (217 → **245**), all public-API, covering every binding-gap ×
gate-state combination, each individually constructible identity-component
mismatch (id, version, digest, scope/tenant — a family mismatch is already
unconstructible on `AssessmentContext`), combined `R0` failures, the
valid-binding regression matrix, and determinism/composite inertness under `R0`.
The isolated multi-wheel `--no-index` verifier proves the binding precedence
from a built wheel.

## [0.2.0] — closure-audit corrections (pre-merge, still 0.2.0/unreleased)

Two blocking findings from the GV-3R-b closure audit, corrected before merge.
The package version stays **0.2.0** (nothing was ever released); the evaluator
formula constant advances **`GV-3R-b.1` → `GV-3R-b.2`** because it identifies
exact evaluator behaviour and that behaviour changed. No other package, and no
ADR, is touched.

### RA-01 — readiness requirements are policy/gate-driven (semantic fix)
`GV-3R-b.1` required at least one `IntelligenceFitnessResult`,
`CapabilityReadinessResult` **and** `AdoptionReadinessResult` applicable to the
requested target, or the case was `NOT_ASSESSABLE`. That requirement is **not in
the ratified sources**: ADR §6 defines the applicable set over
`ReadinessPolicy.gates`; §6's precondition list and §7's precedence table
contain no indicator clause; `ReadinessPolicy` has no field able to declare a
required indicator family; and the merged `AgentValueReadinessDetermination`
defaults all three indicator tuples to `()` and never references them in its
consistency guard. The rule blocked valid indicator-sparse policies with no
opt-out while being satisfiable by a single failing advisory claim.

- **Removed** reason codes `GV3RB_INTELLIGENCE_RESULT_MISSING`,
  `GV3RB_CAPABILITY_RESULT_MISSING`, `GV3RB_ADOPTION_RESULT_MISSING` and the
  presence check behind them. No replacement presence heuristic was added.
- Requirements surface **only** through an applicable `PolicyGate` and its
  `GateResult`. Gate-inventory completeness, mandatory-FAIL dominance,
  fail-closed omission handling and every other invariant are unchanged.
- Supplied indicator records remain fully structurally validated (tenant,
  subject, context, claim binding, uniqueness, immutability) and are carried
  through as diagnostics that never change a tier.

### AUD-01 — policy lifecycle and effective period are precondition row 0
`GV-3R-b.1` never read the governing policy's metadata, so an expired, REVOKED,
SUPERSEDED, DRAFT or not-yet-effective `ReadinessPolicy` produced
`DEPLOYMENT_READY` — a fail-open against ADR §6's precondition, §7 row 0, and
§23's fail-closed requirement. The context binder's `as_of` could not cover it:
a context bound while the policy was valid still evaluated ready long after
expiry.

- **Added** rule `GV3RB_R0_POLICY_PRECONDITION` and reason codes
  `GV3RB_READINESS_POLICY_NOT_APPROVED_ACTIVE` /
  `GV3RB_READINESS_POLICY_NOT_EFFECTIVE_AT_EVALUATION_TIME`.
- Uses the merged `PolicyLifecycleState` enum and
  `PolicyArtifactMetadata.is_effective_at` — neither state machine nor
  effective-period arithmetic is duplicated. Half-open
  `effective_from <= evaluation_time < effective_to` preserved; the explicit,
  timezone-aware `evaluation_time` remains the only time input.
- `R0` precedes all gate rules: an invalid governing policy dominates a
  mandatory `FAIL`. Under `R0` "no headline is asserted" (ADR §6), so the
  determination carries **no** gate results while the trace still reports the
  complete gate inventory and every failure diagnostically.
- This is a **structural read of caller-supplied metadata**. It does not
  authenticate, sign, resolve or approve the policy and does not replace Policy
  Authority or registry resolution; all standing trust advisories are preserved.

### Tests
39 new tests (178 → **217**) covering the full RA-01 acceptance matrix, every
non-`APPROVED_ACTIVE` lifecycle state the merged package defines
(`DRAFT`/`EXPIRED`/`REVOKED`/`SUPERSEDED`), all six effective-period boundary
cases, bound-while-valid-then-expired, precondition-vs-mandatory-FAIL
precedence, and determinism/composite-inertness under `R0`. The isolated
multi-wheel `--no-index` verifier proves both corrections from a built wheel.

## [0.2.0] — GV-3R-b: deterministic readiness-determination evaluator

**Additive.** Milestone **M-3R.2** of the UVI ADR
(`docs/architecture/ADR_UGENCE_VALUE_INTELLIGENCE_GV2C_GV2E_GV3R.md`, §6–§9).
Minor bump because this is a material new capability on top of a merged 0.1.0;
every 0.1.0 symbol keeps its shape and behaviour, so existing callers are
unaffected. **No other package is touched** — `governance-contracts`,
`uvi-policy-contracts` and `governed-value` are unchanged.

The determination stays **advisory, non-financial and fail-closed**: it is not a
deployment authorization, not a Policy Authority, and it verifies no evidence.

### Added
- `evaluate_readiness(case, *, evaluation_time)` — the **single canonical
  entry point** that selects one `ReadinessClassification` from a complete
  applicable gate set. `evaluation_time` is mandatory, keyword-only and must be
  timezone-aware; the **system clock is never read**.
- `ReadinessEvaluationCase` — the immutable input. It carries the bound
  `AssessmentContext`, the complete `ReadinessPolicy` **by value**, its exact
  `PolicyReference`, the requested target, the Intelligence/Capability/Adoption
  results, the `GateResult` tuple, `ConditionSet` records, an optional
  `AdvisoryComposite`, and evidence/window references — and deliberately **no
  classification field**. Rejects self-contradictory inputs with a typed
  `ReadinessEvaluationError`: a gate bound to another policy, a gate absent from
  the supplied policy, a redefined `PolicyGate`, duplicate gate/condition/result
  ids, a gate evaluated for another target, cross-tenant/subject binding, or a
  policy reference that is not the supplied policy's. `canonical_input_digest()`
  is order-independent.
- `ReadinessEvaluationResult` / `ReadinessEvaluationTrace` / `ConditionDecision`
  — the advisory determination plus a deterministic, explanatory-only trace
  (evaluator id, formula version, selected rule, applicable and diagnostic gate
  ids, missing required gates, mandatory failures and indeterminates, unresolved
  conditional concerns, per-condition accept/reject decisions, assessability
  gaps, reason and advisory codes, input digest and reference set).
  `authorizes_deployment` is permanently `False`.
- Stable code enums: `ReadinessRuleId` (R1–R8), `ReadinessReasonCode`,
  `ReadinessAdvisoryCode`, `ConditionDecisionCode`. Codes are emitted in enum
  declaration order, never input order.

### Determination algorithm (first matching rule wins)
1. any applicable mandatory `FAIL` → `NOT_READY`
2. a structural assessability gap → `NOT_ASSESSABLE`
3. an applicable mandatory `INDETERMINATE` with no `FAIL` → `NOT_ASSESSABLE`
4. an unresolved conditional concern that is not compensable → `NOT_READY`
5. a compensable concern without active coverage → `NOT_READY`
6. PILOT, everything above satisfied → `PILOT_READY` (carries its bounded pilot
   controls; the enum has no `PILOT_READY_WITH_CONDITIONS` tier)
7. PRODUCTION with concerns fully covered → `READY_WITH_CONDITIONS`
8. PRODUCTION with nothing unresolved and no open active condition →
   `DEPLOYMENT_READY`

`R1` precedes `R2` because ADR §8/D-6 make a mandatory `FAIL` unconditional and
`AgentValueReadinessDetermination` structurally rejects any other classification
while a blocking gate is present; the gaps are still reported in the trace.

### Invariants proven by tests
- Gate-set completeness is derived from the `ReadinessPolicy`, so an omitted
  applicable mandatory or conditional gate is `NOT_ASSESSABLE`, never `PASS`.
- `{FAIL, INDETERMINATE, PASS}` ⇒ `NOT_READY`; `{INDETERMINATE, PASS}` ⇒
  `NOT_ASSESSABLE`; `{PASS, PASS}` ⇒ conditional resolution.
- `CONDITIONAL` alone is not compensable — the policy must set
  `conditionally_compensable=True`; an uncovered concern is `NOT_READY`.
- Proposed / expired / revoked / satisfied / not-yet-effective / window-ended
  controls are not coverage; the half-open interval is preserved.
- An active control over an applicable gate that is not unresolved is
  internally inconsistent → `NOT_ASSESSABLE`; a `SATISFIED` control over a
  passing gate is retained and permits `DEPLOYMENT_READY`.
- Production-only gates stay diagnostic during PILOT and never block it.
- Evidence axes are preserved exactly (`REPORTED`/`UNATTESTED`/
  `NOT_ATTRIBUTED`/`UNVERIFIED` are never upgraded); no evidence type is
  constructed anywhere in the evaluator.
- The `AdvisoryComposite` is inert: minimum vs maximum score yields an identical
  classification, rule and reason-code tuple.
- Deterministic and order-independent: reversing the input tuples leaves the
  classification, reason codes, gate sets, condition coverage, trace digest and
  determination digest unchanged.

### Not implemented (deliberate)
No evidence admission or verification, no benchmark resolution, **no
metric-to-threshold calculation** (the merged `GovernedThreshold` keeps opaque
literal/unit semantics and none are invented), no policy-authenticity or
condition-authority verification, no causal attribution, no deployment
authorization, no durable event bus or signing, no money/return/forecast.
`ConditionSet` carries no tenant/subject field, so condition **scope is not
matched** against the assessed tenant — recorded as a standing advisory.

### Also updated
Curated `api` exports, `public_api.json` (version + 10 new symbols), README,
distribution verifier (isolated multi-wheel `--no-index` proof now exercises the
evaluator), and 87 new tests.

## [0.1.0] — GV-3R-a: Agent Value Readiness contract shapes

### Pre-merge hardening (independent-audit corrections; still 0.1.0, unreleased)

Corrections to the GV-3R-a audit findings, applied before merge. No evaluator,
tier selection, authority, or financial behavior added — only stronger *local*
contract consistency. The public shape of `GateResult` and the determination
changed (acceptable for an unmerged v0.1.0; no deprecated bypass retained).

- **GV3R-F2/F4 — non-forgeable gate metadata.** `GateResult` now **embeds the
  actual immutable `PolicyGate` by value**. `gate_id`, gate kind, target
  applicability, owned threshold, `is_diagnostic`, and `is_blocking` are
  **derived** from it; the caller-settable `gate_kind`/`applicable`/`threshold_ref`/
  `benchmark_ref` fields are removed. A caller can no longer relabel a mandatory
  gate advisory, mark an applicable gate diagnostic, or swap its threshold. A
  `from_policy_gate()` factory is added for ergonomics (the direct constructor is
  already safe). `ConditionSet.is_active_at(as_of)` adds a time-aware activity
  check (`effective_from <= as_of < effective_to/expiry`).
- **GV3R-F1 — derived blocking sets + ready-class scan.** `blocking_gate_ids` /
  `indeterminate_gate_ids` are now **derived properties** computed from
  `gate_results` (removed as constructor fields). A ready classification is
  rejected if any `gate_result` is a blocking or applicable-mandatory-INDETERMINATE
  gate — an applicable mandatory failure can no longer be hidden by omission.
  Mixed FAIL/INDETERMINATE precedence compatibility is enforced (FAIL ⇒ only
  `NOT_READY`; INDETERMINATE-without-FAIL ⇒ only `NOT_ASSESSABLE`).
- **GV3R-F3/F4 — `READY_WITH_CONDITIONS` active coverage.** Requires every
  applicable unresolved CONDITIONAL concern in `gate_results` to be covered by a
  condition **active at the determination time** (`created_at`), and rejects a
  condition that covers no such concern or points at the wrong gate. Proposed/
  expired/revoked/satisfied/future-effective/expired-window conditions are not
  active coverage.
- **GV3R-F5 — `DEPLOYMENT_READY` cleanliness.** Rejects any unresolved conditional
  concern or open (active) condition; historical `SATISFIED` conditions permitted.
- **GV3R-F6 — single-policy gates.** Every `gate_result.readiness_policy_ref` must
  equal the determination's `readiness_policy_ref` (id/version/digest/tenant/family).
- **GV3R-F7 — extensibility documented.** README states the dimension enums are the
  initial shared taxonomy (domain metrics via governed `metric_id`; new dimensions
  are versioned contract evolution), and clarifies that the embedded `PolicyGate`
  prevents internal metadata contradiction but does not prove policy authenticity.
- Adversarial tests added (`tests/contract/test_determination_consistency.py`)
  covering every finding; distribution verifier extended with the F1 guard.

## [0.1.0] — GV-3R-a: Agent Value Readiness contract shapes (original)

**New internal technical leaf.** Additive to the monorepo; changes no existing
package. Implements milestone **M-3R.1** of the UVI ADR
(`docs/architecture/ADR_UGENCE_VALUE_INTELLIGENCE_GV2C_GV2E_GV3R.md`, §5–§10,
§20): the **non-financial contract shapes** for the Agent Value Readiness engine.
**Contracts only — no evaluator, no deployment authority, no money.** Evaluation
(precedence calculus, tier selection, authority resolution) is GV-3R-b (M-3R.2).

### Added
- Three distinct indicator result types — `IntelligenceFitnessResult`,
  `CapabilityReadinessResult`, `AdoptionReadinessResult` — each binding a GV-2E-a
  `MetricClaim` by value (five orthogonal evidence axes preserved, never
  elevated), tagged with a `ReadinessIndicatorClass`. Capability distinguishes
  demonstration state (`CapabilityDemonstration`), evidence sufficiency, and
  target-relative requirement class. `AdoptionReadinessResult.pre_deployment` is
  locked `True` (adoption readiness ≠ observed post-deployment adoption).
- `GateResult` — a recorded evaluation that **references** an existing
  `PolicyGate` (does not redefine one), preserving requested target, applicability
  (diagnostic vs blocking), status, threshold/benchmark and evidence references.
- `ConditionSet` — compensating-control record; only a `CONDITIONAL` concern is
  eligible (mandatory is non-waivable, D-6); `APPROVED_ACTIVE` requires complete
  authority/owner/monitoring/evidence/time; `EXPIRED`/`REVOKED` never active.
- `AdvisoryComposite` — optional, `Decimal`-only (floats rejected), explicit
  scale, declared method+version, `is_advisory` locked; can never determine a
  tier, override a mandatory failure, or be multiplied into ROI; no default
  weights.
- `AgentValueReadinessDetermination` — the advisory envelope with local
  target/classification consistency invariants (`PILOT_READY`⇒PILOT;
  `DEPLOYMENT_READY`/`READY_WITH_CONDITIONS`⇒PRODUCTION; ready classes carry no
  blocking/indeterminate gates; `NOT_READY`/`NOT_ASSESSABLE` need a reason;
  blocking/indeterminate references must point at applicable-mandatory
  FAIL/INDETERMINATE gates; cross-tenant/context binding rejected). The
  classification is a caller **input**; it is **not** computed from the gates.
- Enums: `ReadinessClassification` (5 target-relative values), `GateStatus`,
  `ConditionStatus`, `ReadinessIndicatorClass`, `CapabilityDemonstration`,
  `IntelligenceDimension`, `CapabilityDimension`, `AdoptionDimension`.
  `ReadinessContractError` (subclasses `ValueError`).
- Curated `ugence_agent_value_readiness.api`; machine-readable `public_api.json`
  + parity test; dependency-boundary test (stdlib + the two contract leaves,
  never `governed-value`); contract + immutability + anti-gaming tests; isolated
  multi-wheel `--no-index` distribution verifier; PEP 561 `py.typed`.

### Reuse (no forking)
- Depends on `ugence-governance-contracts>=0.2.0` (MetricClaim/BenchmarkReference/
  AssessmentWindow/evidence axes) and `ugence-uvi-policy-contracts>=0.1.0`
  (AssessmentContext/PolicyReference/ReadinessTarget/RequirementClass/PolicyFamily).
  `ReadinessTarget`/`RequirementClass` are **re-exported** for convenience but
  remain canonically owned by `uvi-policy-contracts`.

### Type placement
- Readiness result vocabulary (`GateStatus`, `ReadinessClassification`, the
  determination) is placed in **this leaf** rather than `governance-contracts`
  because `ReadinessTarget` is already owned by `uvi-policy-contracts` (GV-2C-a)
  and the ADR §20 "multi-consumer" precondition is not met in GV-3R-a.
  `governance-contracts` is **unchanged** (no version / `CONTRACT_VERSION` bump).
  Promotion to a neutral seam is a documented forward path for a second consumer.

### Non-goals (this milestone)
- No readiness evaluator/state machine, precedence selector, tier selection, or
  deployment authorization. No Policy Authority, signing/approval/issuance/
  revocation, registry/resolver, evidence admission/verification,
  `SubjectContext`/`AssessedSystemBinding`, forecasting, realization-probability
  modeling, attributed/verified ROI, financial valuation, `governed-value`
  integration, or `ConditionSet` runtime enforcement.
