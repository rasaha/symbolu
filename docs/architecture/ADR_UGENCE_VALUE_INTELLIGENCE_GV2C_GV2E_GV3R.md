# ADR — Ugence Value Intelligence: Governed Assessment Context, Evidence & Benchmark Contracts, and Pre-ROI Readiness (GV-2C / GV-2E / GV-3R)

## 1. Status, date, scope, decision owners

- **Status:** PROPOSED — architecture ratified in direction (owner rulings D-1…D-18 recorded); **design-only**, pending final ratification and separately-reviewed implementation phases.
- **Date:** 2026-08-13.
- **Scope:** milestones **GV-2C** (governed assessment context), **GV-2E** (evidence & benchmark contracts), **GV-3R** (Pre-ROI agent–outcome readiness) of the **Ugence Value Intelligence** capability. This ADR defines contracts, ownership, invariants and boundaries **only**. It introduces **no runtime code, no contracts, no packages, no authority, and no behavior**, and changes **no** existing package.
- **Decision owners:** Ugence architecture owners for Value Intelligence, Policy Authority, Risk Authority, Decision Authority, Agent Runtime, and Runtime Assurance. Unresolved items requiring an owner ruling are listed in §26.
- **Amendments:**
  **2026-09-09** — **D-14 ratified and §26.2 closed.** The RA-owned canonical `SubjectContext` merged (design PR #1425, 2026-08-13; implementation PR #1432, 2026-08-17), and the owner has ratified that **UVI does not adopt it**: `canonical_subject_context_ref` stays a permanently opaque token, on the three grounds recorded at D-14 (capacity-shaped fact set with no model/prompt/tool identity; §21's prohibition on a UVI arrow at an authority package; unfrozen D-4 identifiers). This **closes** §26.2 — a settled boundary, not a deferral. No contract, package, symbol, digest or classification changes; D-1 … D-13 and D-15 … D-18 are unchanged.
  **2026-09-09** — **§26.3, §26.8 and §26.9 resolved (four rulings).** (a) `CONTRACT_VERSION` stays **`1.0.0`** — it versions the provider-contract surface, which the frozen fixtures and an import scan show unchanged; the inert `api_snapshot_hash` is deleted rather than wired, and no evidence-axis resequencing is authorized. (b) A policy requirement may name `SourceBasis.SYNTHETIC` **only** paired with `EvidenceUsageScope.EVALUATION_ONLY`, refused at construction. (c) `EvidenceStatusView` **must carry `usage_scope`** — basis-only is a lossy projection that cannot preserve D-9. (d) **`SystemManifest` is placed in `governance-contracts`** with **opaque ref+digest** workflow/policy bindings, never `PolicyReference`; no new package and no competing assessed-system contract. §20 and §16 updated. Rulings (b), (c) and (d) were implemented under the pre-implementation impact record at [`UVI_S26_RULINGS_IMPLEMENTATION_IMPACT.md`](UVI_S26_RULINGS_IMPLEMENTATION_IMPACT.md) and **merged 2026-09-09 in PR #1732 (`6ef1f724`)**: `SystemManifest` at `packages/governance-contracts/src/ugence_governance_contracts/contracts/system_identity.py:459` and `ComponentEvidenceRequirement.required_usage_scope` at `packages/uvi-policy-contracts/src/ugence_uvi_policy_contracts/contracts/policies.py:279`. §26.4 and §26.7 remain open, but **not** on the ground recorded here at the time. A read-only audit of the merged tree (2026-09-09) found that ground — *their subjects do not exist* — **wrong for both**. §26.7's placement question is already settled in code; §26.4's two producer candidates and both symbols of its third clause exist, leaving only an ownership decision. Both items now carry corrected grounds below, and **neither acquires an owner by this correction**.
  **2026-09-09** — **§26.10 resolved: a governed-threshold-evaluation leaf is commissioned.** Owner ruling. Deterministic metric-to-threshold evaluation gets a **shared, non-authoritative** owner (§25 **M-GTE.1**) that consumes verified evidence receipts, issued policy coordinates and resolved benchmark values but may neither verify source evidence nor resolve a `BenchmarkReference` — the latter stays **exclusively** with `benchmark-registry-authority`. A conforming `GateResultVerifier` **composes** the three independently owned legs (§25 **M-GVR.1**) and **may not ship until all three are releasable**, which requires `benchmark-registry-authority` at `0.3.0` with the D-38(i) review and D-32(4)'s external cryptographic audit complete. `readiness-comparison` is **not** promoted and stays `RESEARCH_ONLY` / `REQUESTER_ASSERTED`. §20 gains the ownership rows and §25 the two milestones; **nothing is built**, no existing package's ownership moves, and no semantic boundary changes. Separately ruled the same day: **Studio Simulate wiring is deferred** until §26.10 is resolved in implementation and the whole chain is releasable, with the Studio Simulate / front-door workstream named as the future consumer — it owns the wiring, not readiness semantics or verification — and `agent-value-readiness` expressly **not** declared a terminal leaf (it reaches users through UVI per §4 and D-18; the package stays an internal engine).
  **2026-09-09** — *(superseded the same day by the resolution entry above; retained as the record of how the question was framed)* **§26.10 opened: the gate-verifier seam and the threshold-evaluation ownership gap.** `GateResultVerifier` carries three obligations and only evidence verification has an authoritative owner; benchmark resolution waits on `benchmark-registry-authority` reaching `0.3.0`, and metric-to-threshold evaluation is assigned to no package at all (§20 now records that). Recorded default: **build no verifier and no integration leaf** until those owners exist. Consequence recorded: with the shipped deny-all, any policy with an applicable gate cannot reach a headline classification. **Who owns threshold evaluation remains an open owner ruling.** No contract, symbol or boundary changes.
  **2026-09-09** — **§26.6 closed and D-4's placement ratified.** `agent-value-readiness` moves from `packages/capabilities/agent-value-readiness` to **`packages/agent-value-readiness`**, a top-level leaf and a peer of `governed-value`, matching the tiering §21's diagram and §20's ownership table already described. Path-only: no symbol, contract, digest, dependency, version or classification changes, and the `ugence_agent_value_readiness` namespace is untouched. §26.3 and §26.4 stay open.
  **2026-08-17** — additive amendment for the ratified [`ADR_UGENCE_TRUSTED_EVIDENCE_AND_BENCHMARK_REGISTRY.md`](ADR_UGENCE_TRUSTED_EVIDENCE_AND_BENCHMARK_REGISTRY.md): the **benchmark registry** is **one shared, platform-wide Ugence Benchmark Registry** with UVI as its first consumer, and **trusted evidence verification** is owned by **TAP**, a platform-wide evidence admission/verification authority. This **resolves the §26.5 home question**, **upholds D-3** with two clarifications (see D-3's amendment note), and supplies the missing *mechanism* by which D-8's `VerificationStatus` could ever be **earned rather than asserted** — D-8's axes, D-9's synthetic restrictions, D-10's honest chain, D-11/D-12's valuation rules and D-14's assessed-system boundary are **all unchanged**. No `SystemManifest` is minted and §26.3 stays open.
  **2026-08-16** — consistency-only amendment for the ratified [`ADR_UGENCE_POLICY_AUTHORITY.md`](ADR_UGENCE_POLICY_AUTHORITY.md) (one shared, platform-wide **Ugence Policy Authority**; UVI is its **first policy-family adapter**). It resolves the §26.1 open item and **strengthens** D-1 rather than weakening it. D-1's prohibition on a UVI-specific Policy Authority **stands unchanged**; D-2 … D-18 and all readiness/evidence/valuation semantics are **unchanged**.

## 2. Purpose and non-goals

**Purpose.** Convert an agent's assessment into two clearly-separated, honestly-classified outputs: a **non-financial Pre-ROI readiness determination** (GV-3R) and, downstream and independently, a **classified financial valuation** (the existing `governed-value` kernel), both grounded in **first-class, versioned, authority-resolved policy context** (GV-2C) and **orthogonally-classified evidence** (GV-2E). The design exists to prevent the recurring failure modes catalogued across prior audits: caller-controlled policy multipliers, a single linear evidence-maturity ladder, execution mistaken for effect, effect mistaken for verified value, and mandatory governance failures averaged away by a composite score.

**Non-goals (explicitly out of this ADR and its first milestones):**
- No implementation of the Pre-ROI evaluator, forecasting, financial valuation, context/evidence contracts, or benchmark registry.
- No new customer-facing Ugence module.
- No new authority. No minting, approval, signing, issuance, or revocation of any policy.
- No change to `governed-value` 0.2.0 or to PR #1426.
- No forecasting engine (deferred) and no post-deployment observed-effect integration (deferred).

## 3. Relationship to `governed-value` 0.2.0 and PR #1426

`governed-value` 0.2.0 (PR #1426, draft) is the **independent, experimental downstream reported-value calculation kernel** — one engine of Ugence Value Intelligence (Governed Value Verification), operating over **caller-reported, unverified** inputs and honestly emitting `POST_DEPLOYMENT_VALUE / REPORTED / UNVERIFIED`. This ADR **does not modify it** and **does not depend on it for GV-2C/GV-2E/GV-3R**. Its compatibility projection onto the new evidence model is fixed in §22 (D-17). PR #1426 proceeds through its own review, independently.

## 4. One customer-facing capability and its internal engines

There is exactly **one** customer-facing capability: **Ugence Value Intelligence (UVI)**. It contains three **internal technical engines** (not products, not customer-facing modules):

1. **Agent Value Readiness** — GV-3R; non-financial leading-indicator readiness (this ADR).
2. **Value Forecasting** — deferred; opportunity/scenario/uncertainty (not this ADR).
3. **Governed Value Verification** — the existing `governed-value` kernel is its downstream calculator.

The internal packages named throughout are **technical architecture**, not additional products (D-18).

## 5. Ratified decisions D-1 … D-18

### D-1 — Policy Authority
The existing/planned **Ugence Policy Authority** owns policy **approval, signing/issuance, authorized publishers, effective periods, supersession, and revocation**. `policy-workflow-compiler` is **only a compiler** — it never approves, signs, issues, revokes, or mints policy authority. **No** UVI-specific Policy Authority and **no** new customer-facing module. Policy Authority is **not yet implemented in the repository for UVI value-policies** and is recorded here as an **explicit required dependency** (§19, §26). Reference implementations must never self-approve or self-sign UVI policies and must **fail closed** on unsigned/unapproved/expired/revoked/superseded/digest-mismatched policy artifacts.

> *Amendment (2026-08-16) — D-1 unchanged and upheld.* The "existing/planned Ugence Policy Authority" is ratified in [`ADR_UGENCE_POLICY_AUTHORITY.md`](ADR_UGENCE_POLICY_AUTHORITY.md) as **one shared, platform-wide** authority — **internal platform infrastructure, not a customer-facing module** — with **UVI policy schemas as its first policy-family adapter**. This **satisfies** D-1 as written; it grants **no** exception to it. The prohibition on a **UVI-specific** Policy Authority **remains in force**, and a UVI-owned authority package/distribution is now prohibited **by name**. The Policy Authority remains an **external platform dependency** of UVI engines: engines consume exact resolved, digest-bound policy artifacts **by value** and import **no** authority internals (§21).

### D-2 — UVI policy representation
`GeographyPolicy`, `DomainPolicy`, `IntendedOutcomePolicy`, `ValuationPolicy`, `ReadinessPolicy` are **not** forced into workflow-specific `WorkflowIR`. They live in a narrow internal **`uvi-policy-contracts`** technical package (schema + IR representation), governed by the Policy Authority. Not a customer-facing module.

### D-3 — Benchmark registry
An internal **UVI benchmark registry**: domain owners curate candidates; **Policy Authority governs admission and permitted uses**; **benchmark versions are immutable**; updates produce new versions; assessments bind exact **benchmark id + version + content digest**; expired/revoked/superseded benchmarks are **never silently substituted**; **registry resolution creates no policy authority**. Thresholds are either **immutable policy literals** (intrinsic to the signed policy) or **`BenchmarkReference`** (separately maintained, reusable, or frequently-updated data).

> *Amendment (2026-08-17) — D-3 upheld; two clarifications, no substantive change.*
> [`ADR_UGENCE_TRUSTED_EVIDENCE_AND_BENCHMARK_REGISTRY.md`](ADR_UGENCE_TRUSTED_EVIDENCE_AND_BENCHMARK_REGISTRY.md)
> ratifies D-3's substance in full — immutability, digest-bound resolution, no silent
> substitution, and "registry resolution creates no policy authority" — and adds:
> **(1) Home.** "Internal **UVI** benchmark registry" is read as *internal **platform**
> infrastructure*, **not UVI-owned**: **one shared, platform-wide Ugence Benchmark
> Registry**, with UVI as its **first consumer**. This matches §21, which already draws
> the benchmark registry as a peer of the UVI engines depending only on
> `governance-contracts`, and follows the precedent by which §26.1 was resolved. A
> UVI-specific benchmark registry is now prohibited by name.
> **(2) "Policy Authority governs admission."** Read as governing **permitted uses** —
> policy may require, reference and constrain the use of exact benchmark coordinates —
> **not** as making the Policy Authority the benchmark **approver or signer**. Benchmark
> approval is **external** to the Registry, which **verifies** approval rather than
> producing it, and the authorized **publisher/signer** is a distinct named role. The
> opposite reading would contradict
> [`ADR_UGENCE_POLICY_AUTHORITY.md`](ADR_UGENCE_POLICY_AUTHORITY.md) §6.9/§19.9/§20,
> which disclaim benchmark-value governance three times.
> **D-3 is not weakened**, and D-1…D-18 are otherwise unchanged. The Registry remains
> **DEFERRED as implementation** — no such package exists.

### D-4 — Readiness engine
Placed at **`packages/agent-value-readiness`**, an internal UVI engine. **RATIFIED 2026-09-09** (§26.6): the placement is settled, no longer provisional, and the package sits directly under `packages/` as a peer of `governed-value` — the arrangement §21's diagram already drew, in which both UVI engines stand at the same tier immediately above `governance-contracts`. It was moved out of `packages/capabilities/` in the same change. It evaluates `PreROIReadiness = f(IntelligenceFitness, CapabilityReadiness, AdoptionReadiness | GeographyPolicy, DomainPolicy, IntendedOutcomePolicy)` — **non-financial** leading indicators — and produces an **evidence-based advisory determination**. It does **not** authorize deployment, approve policy, mint runtime authority, or calculate financial ROI. Deployment/human-governance processes consume determinations; Risk Authority and ActionGate retain runtime authorization.

### D-5 — Readiness target
`ReadinessTarget ∈ {PILOT, PRODUCTION}`. Only gates applicable to the requested target determine the headline (§6). A composite score is advisory only — it may compare systems **within** a tier but can **never** change the tier. After context validity, a definite applicable mandatory `FAIL` takes precedence over an unrelated `INDETERMINATE` (§7).

### D-6 — Non-waivable mandatory gates
Mandatory gates are **non-compensatory and non-waivable**: `MANDATORY FAIL ⇒ NOT_READY`. No `ConditionSet`, waiver, compensating control, positive ROI, high composite, forecast, or human preference may convert a mandatory failure into readiness. Only concerns **explicitly classified by policy as conditionally compensable** may be governed through a `ConditionSet` (§9).

### D-7 — ConditionSet / compensating controls
`ConditionSet` (fields in §9) with `current_status ∈ {PROPOSED, APPROVED_ACTIVE, EXPIRED, REVOKED, SATISFIED}`. `READY_WITH_CONDITIONS` requires: all applicable mandatory gates `PASS`; every **permitted** unresolved concern has an `APPROVED_ACTIVE` `ConditionSet`; every required compensating control is active and evidenced; scope, monitoring, owner, expiry and revocation trigger present. A condition without an approved active control **blocks** the target; expired/revoked controls **invalidate** the conditional determination on re-evaluation.

### D-8 — Evidence model (orthogonal axes, not one ladder)
`SourceBasis ∈ {REPORTED, OBSERVED, SYNTHETIC, MIXED}`; `TransformationMethod ∈ {DIRECT, CALCULATED, MODELED}`; `AttestationStatus ∈ {UNATTESTED, ATTESTED}`; `AttributionStatus ∈ {NOT_APPLICABLE, NOT_ATTRIBUTED, PARTIALLY_ATTRIBUTED, ATTRIBUTED}`; `VerificationStatus ∈ {UNVERIFIED, VERIFICATION_FAILED, VERIFIED}`. Rules in §11–§13. Use a neutral **`MetricClaim`** for reported/observed/calculated/modeled values; reserve **`MetricObservation`** for genuinely observed claims.

### D-9 — Synthetic evidence
`SourceBasis.SYNTHETIC` is permitted **only** for pre-deployment testing/readiness/evaluation, carrying `EVALUATION_ONLY` usage scope, generator/dataset identity+version, population/domain assumptions, known domain-shift limitations, provenance, and content digest. It is **never sufficient by itself** for observed/attributed/verified realized ROI (§14).

> *Amendment (2026-09-09) — §26.8 resolved; D-9 unchanged in substance and extended to two seams.* Synthetic evidence is **not readiness-specific**, but it is restricted to pre-deployment evaluation **wherever used**. The audit found D-9 already enforced structurally on `MetricClaim` (`governance-contracts/contracts/evidence.py:453-472`: SYNTHETIC requires `usage_scope=EVALUATION_ONLY`, generator/dataset `evidence_refs` and a `content_digest`, and cannot independently support an attributed or verified realized result), and found three consumers closed by construction (`reasoning-method-governance/contracts/record.py:191` pins a `ClassVar` of `OBSERVED`; `workflow-fit-pilot/runner.py:308` hardcodes `REPORTED`; `uvi-policy-contracts/contracts/thresholds.py:37` carries no evidence axes). Two seams sat wider than D-9 and are ruled:
>
> 1. **Policy requirements.** `ComponentEvidenceRequirement` (`uvi-policy-contracts/contracts/policies.py:253`) may name `SourceBasis.SYNTHETIC` **only when it also explicitly requires `EvidenceUsageScope.EVALUATION_ONLY`**. An unpaired synthetic requirement is **invalid and must fail at contract construction**. Evaluation scope is **never** inferred from package location, caller identity or later consumer behaviour. Other source bases keep their existing rules.
> 2. **`EvidenceStatusView`.** It is **not** ratified as deliberately basis-only. While it can represent `SYNTHETIC` (`reasoning-method-governance/contracts/envelopes.py:75`) and carries no scope axis, it is a **lossy projection that cannot preserve D-9**. It **must carry `usage_scope`** and enforce the same pairing. Its sole construction path (`readiness-comparison/engine.py:274`) is updated explicitly; a missing scope is **never** silently defaulted.
>
> The enum is `EvidenceUsageScope` (members `GENERAL`, `EVALUATION_ONLY`); there is no type named `UsageScope`. Implemented under the pre-implementation impact record at [`UVI_S26_RULINGS_IMPLEMENTATION_IMPACT.md`](UVI_S26_RULINGS_IMPLEMENTATION_IMPACT.md) and merged 2026-09-09 in PR #1732 (`6ef1f724`); see `ComponentEvidenceRequirement.required_usage_scope` (`packages/uvi-policy-contracts/src/ugence_uvi_policy_contracts/contracts/policies.py:279`).

### D-10 — Execution → effect → attribution → verification
Honest chain (§17). Existing semantics are preserved and **not renamed**: `RiskAuthorizationEnvelope` = permission; Agent Runtime results = an attempt ran (not effect); `ExecutionObservation` = provider-reported outcome claim (not verified); DA `ReconciliationResult` = intent↔observation consistency (not causal attribution); Runtime-Assurance `TrajectoryAssessment` = runtime risk (not claim verification). Two **new UVI assessment contracts** — `AttributionAssessment`, `VerificationAssessment` — are defined (§17), consuming existing artifacts as inputs **without distorting their semantics**.

### D-11 — Financial valuation
`governed-value` owns `FinancialValuation`, financial calculations, and classified value/ROI outputs. Eligibility comes from approved `IntendedOutcomePolicy` and/or `ValuationPolicy` — **not** a hard-coded `VERIFIED`-effect prerequisite. Valuation may run over reported/modeled/observed/attributed/verified inputs, but the output **preserves their exact evidential meaning**; a `VERIFIED ROI` claim is admissible **only** when every policy-required component meets the required attribution and verification standards (§18).

### D-12 — Valuation evidence manifest
`ValuationEvidenceManifest` carries **component-level** classifications and evidence references for every input class (§18). Conservative headline rule: **a verified component never elevates** a reported/modeled/unattested/unattributed/unverified component; the headline classification is the **weakest required** component's classification.

### D-13 — Geography / Domain / Intended Outcome
First-class, versioned policy context — **not** caller-controlled numeric modifiers. Required determinations/references in §15.

### D-14 — Assessed system & subject context
**No second subject-context authority.** UVI mints no subject-context contract of its own — that prohibition is permanent and is the whole of what D-14 forbids. The canonical neutral subject-context work from the Risk Authority / cloud-scaling integration ADR is **merged and implemented** — designed in PR #1425 (merged 2026-08-13) and implemented in PR #1432 (merged 2026-08-17) as `SubjectContext` / `SubjectBinding` / `validate_subject_binding` in `risk_authority.integrations.evaluation_contracts`, schema `risk-subject-context-1`, shipped in `ugence-risk-authority` >= 0.3.0. **UVI does not adopt it. RATIFIED 2026-09-09: `canonical_subject_context_ref` stays a permanently opaque token** — this is a settled boundary, not a pending one, and no UVI package imports `risk_authority` or resolves such a reference. Three grounds, each independently sufficient: (a) the merged RA fact set is scaling-oriented — `action_type`, `environment`, `region`, `zone`, `compute_group`, `resource_class`, `magnitude_before`/`magnitude_after` — and carries no model, prompt, tool or agent identity, so it answers nothing readiness asks; (b) adoption would point a UVI arrow at an **authority** package, which §21's invariant forbids — every arrow points at a neutral-contract package — and which `agent-value-readiness`'s own dependency-boundary test already refuses; (c) PR #1432 deliberately left the D-4 identifier strings unfrozen, so there is nothing stable to bind to. Should UVI ever need those facts, the route is a **neutral** contract in `governance-contracts`, never a direct arrow at `risk_authority`; that would be a new decision, not the execution of this one. `AssessedSystemBinding` continues to carry `canonical_subject_context_ref` + a UVI `SystemManifest` bound by digest — both as opaque, co-required ref + digest tokens. Non-adoption does **not** license minting a competing subject-context contract; it forecloses both the arrow and the fork.

### D-15 — Contract & package placement
Boundaries fixed in §20; dependency rules in §21.

### D-16 — Policy roles
Distinguish author → approval authority → compiler → signing/issuing authority → registry/resolver → revocation owner (§19); do not conflate. Repository has a compiler but lacks approval/issuance/revocation ownership for UVI policies — recorded as dependencies on the Policy Authority.

### D-17 — Compatibility with governed-value 0.2.0
Projection fixed in §22; kernel unchanged; `DomainProfile`/`GeographyProfile` → policy-reference migration is a future, separately-reviewed breaking change.

### D-18 — Product boundary
One customer-facing capability (UVI); internal packages/engines are technical architecture, not products. PR #1426 remains independent.

## 6. Target-relative readiness state machine

Each `ReadinessGate` carries `kind ∈ {MANDATORY, CONDITIONAL, ADVISORY}` and `applicability ⊆ {PILOT, PRODUCTION}`. For a requested `ReadinessTarget`, the **applicable set** = gates whose `applicability` includes that target; all other gate results are computed and reported as **diagnostic** and can never block.

**Precondition (both targets):** if `AssessmentContext` (or any required policy/benchmark it resolves) is missing, expired, revoked, superseded, or digest-mismatched ⇒ `NOT_ASSESSABLE(context)`; no headline is asserted (diagnostic gate results may still be reported).

**Target = PILOT** (applicable set = `PILOT` gates):
- any applicable pilot-mandatory `FAIL` ⇒ `NOT_READY`;
- else any applicable pilot-mandatory `INDETERMINATE` ⇒ `NOT_ASSESSABLE`;
- else (all applicable pilot-mandatory `PASS`) ⇒ `PILOT_READY`, operated under **bounded pilot controls** (inherent scope, exposure, duration, monitoring limits — distinct from the PRODUCTION `ConditionSet` mechanism);
- production-only gate results remain **diagnostic** and can never make `PILOT_READY` unreachable.

**Target = PRODUCTION** (applicable set = `PRODUCTION` gates; pilot-safety mandatory gates are typically also production-applicable):
- any applicable production-mandatory `FAIL` ⇒ `NOT_READY`;
- else any applicable production-mandatory `INDETERMINATE` ⇒ `NOT_ASSESSABLE`;
- else all applicable mandatory `PASS` **and** every **permitted** unresolved concern covered by an `APPROVED_ACTIVE` `ConditionSet` ⇒ `READY_WITH_CONDITIONS`;
- else all applicable mandatory **and** required conditional gates `PASS`, with no unresolved active conditions ⇒ `DEPLOYMENT_READY`.

Determination ordering (strongest headline first): `NOT_ASSESSABLE > NOT_READY > {PILOT_READY, READY_WITH_CONDITIONS} > DEPLOYMENT_READY`. Invariant: `DEPLOYMENT_READY ⇒ every applicable mandatory ∪ required-conditional gate = PASS`.

## 7. Mixed FAIL / INDETERMINATE precedence

Evaluated over the **applicable mandatory set**, after context validity. A definite `FAIL` is never masked by an unrelated `INDETERMINATE`.

| # | Condition | Determination |
|---|---|---|
| 0 | context invalid / expired / revoked / superseded / digest-mismatch | `NOT_ASSESSABLE(context)` |
| 1 | ≥1 applicable-mandatory `FAIL` | `NOT_READY` (FAIL dominates INDETERMINATE) |
| 2 | no mandatory `FAIL`, ≥1 applicable-mandatory `INDETERMINATE` | `NOT_ASSESSABLE(gate)` |
| 3 | all applicable-mandatory `PASS` | → conditional / target resolution (§6, §9) |

Worked cases: `{FAIL, INDETERMINATE, PASS}` ⇒ `NOT_READY`; `{INDETERMINATE, PASS}` ⇒ `NOT_ASSESSABLE`; `{PASS, PASS}` + conditional `FAIL` with no approved active control ⇒ `NOT_READY`; `{PASS, PASS}` + conditional `FAIL` with `APPROVED_ACTIVE` control ⇒ `READY_WITH_CONDITIONS`.

## 8. Non-waivable mandatory-gate invariant (D-6)

```
MANDATORY gate FAIL  ⇒  determination = NOT_READY   (for that target)
```
No `ConditionSet`, waiver, compensating control, positive ROI, high composite score, forecast, or human preference may convert a mandatory `FAIL` into any readiness tier. `ConditionSet` governs **only** concerns that policy has explicitly classified as `CONDITIONAL` (conditionally compensable). A concern that is `MANDATORY` in the governing `DomainPolicy`/`ReadinessPolicy` is never eligible for a `ConditionSet`.

## 9. ConditionSet and compensating-control semantics (D-7)

`ConditionSet { condition_id, source_finding_or_gate, approved_mitigation_or_waiver, approving_authority, accountable_owner, scope_exposure_limit, monitoring_requirement, evidence_ref, effective_period, expiry, revocation_trigger, current_status }`, `current_status ∈ {PROPOSED, APPROVED_ACTIVE, EXPIRED, REVOKED, SATISFIED}`.

`READY_WITH_CONDITIONS` is produced **only** when **all** hold: (1) all applicable mandatory gates `PASS`; (2) every permitted unresolved concern has an `APPROVED_ACTIVE` `ConditionSet`; (3) every required compensating control is active and evidenced (`evidence_ref` present; not `EXPIRED`/`REVOKED`); (4) scope, monitoring, accountable owner, expiry, and revocation trigger are present. A conditional concern with **no** `APPROVED_ACTIVE` control is an **unmet condition** → the target drops to `NOT_READY` (never a silent `READY_WITH_CONDITIONS`). An `EXPIRED`/`REVOKED` control **invalidates** the conditional determination on re-evaluation. `ConditionSet` never applies to a `MANDATORY` concern (D-6).

## 10. Intelligence / Capability / Adoption readiness taxonomy (GV-3R)

Non-financial leading indicators, each a `MetricClaim` (§11) bound to evidence and evaluated against `GeographyPolicy`/`DomainPolicy`/`IntendedOutcomePolicy` thresholds/benchmarks.

| IntelligenceFitness (task-specific) | CapabilityReadiness | AdoptionReadiness (pre-deployment) |
|---|---|---|
| reasoning/decision quality; accuracy; reliability & consistency; confidence calibration; exception handling; uncertainty recognition; language/population/regional performance | required functional coverage; tool & integration readiness; workflow completion; execution reliability; autonomy boundaries; escalation & human fallback; security & governance readiness; observability & auditability | eligible population & workflow coverage; expected utilization; workflow suitability; user acceptance/trust readiness; training readiness; change-management readiness; expected override/rejection/abandonment; conditions for sustained use |

`AdoptionReadiness` (pre-deployment, predicted) is **distinct** from post-deployment `ObservedAdoption` (a GV-3+ evidence class); they are never merged.

## 11. SourceBasis and TransformationMethod (D-8)

Two orthogonal axes on every `MetricClaim` (resolving the prior `MODELED`/`DERIVED` overlap):

| Axis | Values | Meaning |
|---|---|---|
| `SourceBasis` | `REPORTED` · `OBSERVED` · `SYNTHETIC` · `MIXED` | where the ground inputs come from |
| `TransformationMethod` | `DIRECT` · `CALCULATED` · `MODELED` | how the value was produced from those inputs |

A model-based causal estimate over measured inputs = `(OBSERVED, MODELED)`. **`CALCULATED` and `MODELED` claims MUST cite `input_evidence_refs`.** `MIXED` source basis carries per-input basis in the manifest. `SYNTHETIC` is constrained by §14.

`MetricClaim { metric_id, value, governed_unit, source_basis, transformation_method, input_evidence_refs[], provenance_ref, window_or_horizon (AssessmentWindow | ForecastHorizon), population_slice, confidence_basis, attestation_status, attribution_status, verification_status, claim_ref? }`. `MetricObservation` is the profile of `MetricClaim` constrained to `source_basis = OBSERVED`, `transformation_method ∈ {DIRECT, CALCULATED}`, with a required `AssessmentWindow` (D-8, §13).

## 12. Attestation / Attribution / Verification separation (D-8)

Three **independent** axes; none elevates another:
- **Attestation** signs the provenance of whatever basis exists. It **never** converts `REPORTED` into `OBSERVED`, and **never** implies attribution.
- **Attribution** requires a declared **counterfactual + causal method + assumptions + evidence**. It is **not** prohibited for `MODELED` claims — causal attribution is routinely model-based. `ATTRIBUTED`/`PARTIALLY_ATTRIBUTED` require `SourceBasis ∈ {OBSERVED, MIXED}` grounding and a declared method; `REPORTED`-only / `SYNTHETIC` claims are `NOT_APPLICABLE` or `NOT_ATTRIBUTED`.
- **Verification** must bind a specifically declared **`claim_ref`** and does **not** imply attribution. `VERIFIED`/`VERIFICATION_FAILED` without a `claim_ref` are invalid. `VERIFICATION_FAILED` is terminal-negative (retained for audit; never consumed as valid).

**Caller-provided labels alone never elevate any axis** — elevation is a function of provenance + method + authority, not of a caller-supplied string.

## 13. `MetricClaim` versus `MetricObservation` (D-8)

`MetricClaim` is the neutral contract for **any** value (reported, observed, calculated, modeled). `MetricObservation` is **reserved** for genuinely observed measurements (`source_basis = OBSERVED`) and must not be used for predicted, modeled, or reported values. **Policy thresholds are policy artifacts, not metric evidence claims** — they carry no `SourceBasis`/axes and are compared *against* `MetricClaim`s by gates (a signed threshold is a `PolicyThreshold` literal or a `BenchmarkReference`, never a `MetricClaim`).

## 14. Synthetic-evidence restrictions (D-9)

`SourceBasis.SYNTHETIC` is admissible **only** for pre-deployment testing/readiness/evaluation and must carry: `usage_scope = EVALUATION_ONLY`; generator/dataset identity + version; population and domain assumptions; known domain-shift limitations; provenance; content digest. Synthetic evidence is **never** sufficient by itself to support `OBSERVED`, `ATTRIBUTED`, or `VERIFIED` **realized** ROI. Whether `SYNTHETIC` is admitted at all beyond readiness is an owner decision (§26).

## 15. Geography / Domain / Intended-Outcome policy matrices (D-13)

Each cell is a **defined value or a versioned reference**; none is a caller multiplier.

| GeographyPolicy | DomainPolicy | IntendedOutcomePolicy |
|---|---|---|
| jurisdiction & applicable regulations | governed outcome units | target outcome |
| reporting & functional currency | task & capability taxonomy | task definition |
| wage & operating-cost benchmarks (refs) | benefit & loss taxonomy | success criteria |
| language/population/regional requirements | permitted valuation methods | value function (ref) |
| residency & localization requirements | domain benchmarks (refs) | counterfactual specification |
| local counterfactual baselines | evidence & confidence requirements | measurement & observation windows |
| regional performance thresholds | consequence & criticality classification | realization lag |
| valuation-policy references | mandatory safety/fairness/quality/compliance gates | attribution method; normalization basis; required effect evidence; acceptance thresholds |

Thresholds are **immutable policy literals** when intrinsic to the signed policy (e.g. a fairness bar, a minimum-accuracy acceptance threshold decided by the policy), and **`BenchmarkReference`** when drawn from separately-maintained, reusable, or frequently-updated data (e.g. regional wage table, regulatory loss table, language-performance benchmark) (D-3).

## 16. Assessed-system binding and neutral subject-context dependency (D-14)

`AssessedSystemBinding { canonical_subject_context_ref, system_manifest_ref, system_manifest_digest, deployment_target, workflow_policy_refs[], assessment_context_refs[] }`.

`SystemManifest` binds the actually-assessed configuration: agent/system identity; model/model-set identities & versions; prompt/configuration versions & digests; tool & capability-set versions & digests; relevant workflow & policy references. **Immutable references + canonical digests** (mirroring the content-digest discipline of `risk_authority.ControlEvidenceRecord`).

**Dependency (explicit):** the canonical neutral `SubjectContext` is defined by the **RA-owned** design in PR #1425 (schema `risk-subject-context-1`, `SubjectBinding risk-subject-binding-1`), which is **merged (2026-08-13) and implemented** by PR #1432 (merged 2026-08-17) in `risk_authority.integrations.evaluation_contracts`. UVI **reuses** that contract via `canonical_subject_context_ref`; it does **not** mint a competing subject-context contract. UVI **does not adopt it** — the reference is carried as an opaque token and resolved by nothing, permanently (D-14, ratified 2026-09-09; §26.2). Because the RA v2 fact set is scaling-oriented and carries no model/prompt/tool identity — so it would not describe an assessed agent even if the arrow were permitted — the UVI `SystemManifest` is an **additive, non-competing** artifact bound by digest alongside the canonical subject context. **Ruled 2026-09-09 (§26.3):** `SystemManifest` is placed in **`governance-contracts`**, and the "relevant workflow & policy references" it binds are **platform-neutral opaque reference-and-digest pairs**, not typed `PolicyReference` — the precedent being `MetricClaim.policy_refs: tuple[str, ...]`, which already carries policy references opaquely inside the neutral leaf. The reuse boundary is confirmed: additive, non-competing, and no second assessed-system contract.

## 17. Authorization → execution evidence → effect claim → attribution → verification → valuation

Honest chain; existing modules provide inputs, not the downstream determinations (D-10).

| Step | Contract | What existing modules actually provide | New? |
|---|---|---|---|
| Authorization | `RiskAuthorizationEnvelope` (Risk Authority) | signed **permission** to act | reuse |
| ExecutionEvidence | Agent Runtime `RuntimeResult` / `ProviderAttempt` / `WorkflowAdvanceOutcome` | an attempt **ran** with an outcome — not external effect | reuse |
| EffectClaim / EffectObservation | `governance-contracts.ExecutionObservation` (`business_outcome`, `observed_parameters`, `final`, `reason`, `provider_trace_id`, `fingerprint`) | provider-**reported** outcome claim — not verified | reuse |
| **AttributionAssessment** | *new UVI contract* | DA `ReconciliationResult.status ∈ ReconciliationStatus {RECONCILED, MISMATCHED, PARTIALLY_RECONCILED, INDETERMINATE, MANUAL_REVIEW_REQUIRED, COMPENSATION_REQUIRED}` = intent↔observation **consistency** — an input, not a causal determination | **new** |
| **VerificationAssessment** | *new UVI contract* | Runtime-Assurance `TrajectoryAssessment` = runtime **risk/trajectory** — not claim-specific verification | **new** |
| **FinancialValuation** | *new, owned by `governed-value`* | no contract maps eligible effect + value policy → classified money | **new** |

`AttributionAssessment { declared_effect_claim, counterfactual_specification, causal_method, assumptions, evidence_refs[], attribution_fraction_or_result, limitations, responsible_producer }`.
`VerificationAssessment { claim_ref, verification_method, verifier_identity, independence_status, verification_evidence[], result, limitations, timestamp, expiry_or_freshness }`.

> **Source of the DA row** `[V]` (corrected 2026-09-09). `ReconciliationResult` is `packages/capabilities/decision-authority/src/ugence_decision_authority/execution/reconciliation.py:23` in `ugence-decision-authority` 1.0.0, and its `status` field takes the **six**-member `ReconciliationStatus` at `.../execution/status.py:93`, pinned exactly and in order by `packages/capabilities/decision-authority/tests/test_frozen_vocabulary.py:74-76`. This row previously named only the first three, which §26.4 recorded as an inaccuracy; the row is corrected here and the semantics it assigns are unchanged. Do not confuse this contract with the product-scoped `ReconciliationStatus` at `packages/products/ai-hiring/src/ugence_ai_hiring/hiring_decision/enums.py:134`, whose members differ (`RECONCILED`/`DEVIATION`/`PARTIAL`/`FAILED`/`UNKNOWN`) and whose own docstring scopes it to "the hiring-domain view only".

> **Source of the EffectClaim row** `[V]` (corrected 2026-09-09). `ExecutionObservation` is `packages/governance-contracts/src/ugence_governance_contracts/contracts/execution.py:48` and its fields are exactly the six now listed. This row previously named a fourth field, `external_result_id`, which that type does not have and which appears nowhere in `packages/governance-contracts/src`.
>
> **What happened, established from history rather than assumed** `[V]`. It was not a rename or a removal: `git log --all -S"external_result_id"` over `contracts/execution.py` returns **no commit**, so the field never existed on that type in any revision. Nor was it a slip for `external_request_id` on `ExecutionDispatchResult`. The field is real but belongs to a **different, downstream type** — DA `ExecutionRecord` (`packages/capabilities/decision-authority/src/ugence_decision_authority/execution/execution_record.py:33`). [`RISK_AUTHORITY_RA8_SPEC.md`](RISK_AUTHORITY_RA8_SPEC.md) line 120 carries the same four-field list against the **arrow** *governance-contracts `ExecutionObservation` → DA `ExecutionRecord`*, where the fields describe the record at the arrow's destination. This row took that list, attached all of it to the upstream type alone, and adapted `finality` → `final` (correct here) while carrying `external_result_id` across (not).
>
> **Why that field is not available here, and must not be added** `[V]`. `external_result_id` is the identifier of an outcome **DA has already recorded as observed**. `ExecutionObservation` is the provider's *reported* claim, upstream of any such record. Attaching a downstream, DA-owned effect identifier to it would promote a reported claim to a recorded effect by field name alone — exactly what **D-10** forbids ("no artifact is promoted across those boundaries by renaming", §23) and precisely the confusion this row exists to prevent. The same reasoning excludes `external_request_id`, which sits on `ExecutionDispatchResult`, documented there as "A *transport* result — never a business outcome".

**DA reconciliation is not renamed `AttributedEffect`; Runtime-Assurance observation is not renamed `VerifiedEffect`.** Their outputs are consumed as inputs by the two new assessments without distorting their semantics.

## 18. `ValuationEvidenceManifest` and mixed-input classification (D-11, D-12)

A financial result combining inputs of different evidential quality must **not** be assigned one misleading label. `ValuationEvidenceManifest` carries, **per component** (benefits; avoided losses; actual losses; residual expected losses; operating costs; investment; normalization units; counterfactual inputs; attribution inputs): `source_basis`, `transformation_method`, `attestation_status`, `attribution_status`, `verification_status`, `evidence_refs[]`; and exposes aggregate `evidence_coverage`, `attribution_coverage`, `verification_coverage`, and `missing_or_degraded_components[]`.

**Conservative headline rules:**
- The headline classification of a result is the **weakest classification among its policy-required components** (a verified component never elevates a reported/modeled/unattested/unattributed/unverified component).
- A `VERIFIED ROI` headline is admissible **only** when every `IntendedOutcomePolicy`/`ValuationPolicy`-required component is `ATTRIBUTED` (where attribution is required) **and** `VERIFIED` against its declared `claim_ref`.
- A reported or modeled calculation remains clearly classified as reported/modeled; eligibility is defined by policy (D-11), not by a hard-coded `VERIFIED`-effect prerequisite. `governed-value` 0.2.0's current `REPORTED` emission is exactly the weakest-cell case (§22).

## 19. Policy authorship / approval / compiler / issuer / registry / revocation roles (D-16)

| Role | Existing owner (repository evidence) | Status for UVI value-policies |
|---|---|---|
| Policy / domain author | humans (content) | expected; no package |
| **Approval authority** | none (Decision Authority approves decision cases, not policy artifacts) | **required dependency on Policy Authority** |
| Compiler | `tooling/policy-workflow-compiler` (policy → IR) — **not an authority** | reuse (compilation only) |
| **Signing / issuing authority** | `risk_authority` signs **envelopes** (runtime authorization), **not** policy issuance | **required dependency on Policy Authority** |
| Registry / resolver | reference resolvers exist; UVI benchmark registry to be built (D-3) | internal registry; resolution mints no authority |
| **Revocation owner** | `risk_authority` owns envelope/authority revocation, **not** policy-version revocation | **required dependency on Policy Authority** |

Reference implementations must **fail closed** on unsigned, unapproved, expired, revoked, superseded, or digest-mismatched policy artifacts and must never self-approve/self-sign.

> *Amendment (2026-08-16).* The three rows marked **required dependency on Policy Authority** are owned by the shared, platform-wide **Ugence Policy Authority** ratified in [`ADR_UGENCE_POLICY_AUTHORITY.md`](ADR_UGENCE_POLICY_AUTHORITY.md) — approval **verification** (approval itself stays external), signing/issuance, and policy-version revocation — with UVI as its first policy-family adapter. Building that authority is a **platform dependency milestone**, **not** a UVI engine milestone; UVI's milestones (§25) are unchanged.

## 20. Type-by-type package ownership (D-15)

| Type | Owner package | Rationale |
|---|---|---|
| `SourceBasis`, `TransformationMethod`, `AttestationStatus`, `AttributionStatus`, `VerificationStatus` | **governance-contracts** | neutral cross-package axes |
| `MetricClaim`, `MetricObservation`, `EvidenceReference`, `EvidenceProvenance`, `BenchmarkReference`, `AssessmentWindow`, `ForecastHorizon`, `PopulationSlice`, `ConfidenceBasis`, `AssessedSystemBinding` (references), `AssessmentContext` | **governance-contracts** | neutral seams consumed by ≥2 engines |
| `ReadinessTarget`, `GateStatus`, minimal `ReadinessDetermination` envelope | **governance-contracts** (minimal, multi-consumer only) | externally-consumed result surface |
| `AttributionAssessment`, `VerificationAssessment` (contract shapes) | **governance-contracts** (shapes); producers per §26 | neutral determinations consumed by valuation |
| `GeographyPolicy`, `DomainPolicy`, `IntendedOutcomePolicy`, `ValuationPolicy`, `ReadinessPolicy` (schema + IR) | **uvi-policy-contracts** | UVI policy schema, Policy-Authority-governed |
| `IntelligenceFitness`, `CapabilityReadiness`, `AdoptionReadiness` catalogs; `ReadinessGate`, `GateResult`, `ReadinessPolicy` machinery; `ConditionSet` handling; target-relative state machine; advisory composite logic | **agent-value-readiness** | readiness-internal taxonomy/machinery (kept local) |
| `FinancialValuation`, financial calculation, `ValuationEvidenceManifest`, classified value/ROI outputs | **governed-value** | downstream financial types |
| `BenchmarkReference` **values** | internal **benchmark registry** | governed data, not a contract |
| opportunity sizing, scenario construction, realization probability, uncertainty ranges | **deferred forecasting leaf** | out of scope |
| `SystemManifest` (final home) | **governance-contracts** — ruled 2026-09-09 (§26.3) | Beside `AssessedSystemBinding`. Workflow/policy bindings are **opaque ref + digest pairs**, never `PolicyReference`, which is what keeps it in the neutral leaf; it imports no UVI, Policy Authority, readiness, risk or execution package. Must bind the assessed composition substantively — a nominal manifest is not permitted. |
| deterministic metric-to-threshold evaluation (comparing a `MetricClaim` value against a `GovernedThreshold` under its `ComparisonOperator`) | **a shared, non-authoritative governed-threshold-evaluation leaf** — commissioned 2026-09-09 (§26.10), not yet built | It **consumes** independently verified evidence receipts, issued policy coordinates and **already-resolved** benchmark values. It may **neither** verify source evidence **nor** resolve a `BenchmarkReference`. Non-authoritative: it evaluates, it attests nothing. |
| `BenchmarkReference` **resolution** (a reference to a benchmark *value*) | **`benchmark-registry-authority`, exclusively** | Reaffirmed 2026-09-09 (§26.10). The threshold-evaluation leaf must not reproduce it, and no engine may resolve a benchmark itself. |
| the `GateResultVerifier` implementation | **a composition over the three owners above** | §26.10. It composes trusted evidence verification, benchmark resolution and governed threshold evaluation; it owns none of them and reimplements none of them. Ships only when all three are releasable. |

## 21. Dependency rules — no leaf imports another leaf's internals

```
governance-contracts        (depends on nothing)
      ▲            ▲            ▲              ▲
      │            │            │              │
uvi-policy-   agent-value-   governed-value   benchmark-registry
contracts     readiness      (0.2.0; later)   (service)
              │  └── uvi-policy-contracts (policy shapes, by value)
              └── governance-contracts
governed-value ── governance-contracts + uvi-policy-contracts   (later, optional, additive)
RA-owned SubjectContext (risk_authority, merged #1425/#1432)  ◀── referenced by governance-contracts
                                        AssessedSystemBinding as an opaque token, never resolved
                                        (D-14, ratified 2026-09-09 — no UVI arrow at an authority)
```

Invariants: **every arrow points at a neutral-contract package**; `agent-value-readiness` does **not** import `governed-value`; `governed-value` does **not** import `agent-value-readiness`; neither imports the other's internals; all cross-package communication uses neutral contracts. The benchmark registry depends only on `governance-contracts`. No leaf imports a Policy Authority internal — policies arrive as signed, digest-bound artifacts.

## 22. Compatibility boundary for `governed-value` 0.2.0 (D-17)

`governed-value` 0.2.0 and PR #1426 remain **unchanged and independent**. Compatibility projection (documentation only):

- `EvidenceStatus.REPORTED → (SourceBasis.REPORTED, TransformationMethod.DIRECT)`;
- `AuthorityStatus.UNVERIFIED → (AttestationStatus.UNATTESTED, VerificationStatus.UNVERIFIED)`;
- current effect classification `→ AttributionStatus.NOT_ATTRIBUTED`.

The kernel remains an experimental downstream calculation engine over caller-reported, unverified inputs, emitting exactly this weakest cell. Adoption of the four axes and `FinancialValuation`/`ValuationEvidenceManifest` is **additive** and behavior-preserving. Migrating its `DomainProfile`/`GeographyProfile` to policy references is a **future, separately-reviewed breaking change**, explicitly out of GV-2C/GV-2E/GV-3R.

## 23. Security and anti-gaming invariants

1. **No caller-elevated evidence.** No caller-supplied label elevates any of the five axes (D-8); elevation requires provenance + method + authority.
2. **Fail closed on policy trust.** Reference implementations fail closed on unsigned/unapproved/expired/revoked/superseded/digest-mismatched policy or benchmark artifacts (D-1, D-3, D-16); no silent substitution of an expired/revoked/superseded benchmark (D-3).
3. **Mandatory gates are non-waivable** (D-6); no control/waiver/ROI/composite/forecast/preference converts a mandatory `FAIL` into readiness.
4. **Composite is advisory** (D-5); it can never change a readiness tier.
5. **Determinations bind exact identity + digests** — `AssessedSystemBinding`/`SystemManifest` and benchmark/policy references bind ids, versions, and content digests (D-3, D-14), preventing swap/replay/misattribution.
6. **Execution ≠ effect ≠ attribution ≠ verification ≠ value** (D-10); no artifact is promoted across those boundaries by renaming.
7. **Conservative valuation headline** (D-12); a verified component never elevates a weaker required component.
8. **Synthetic is evaluation-only** (D-9); never sufficient for realized observed/attributed/verified ROI.
9. **Readiness is not authority** (D-4); the engine produces an advisory determination and mints no runtime or deployment authority.
10. **Reference producers never self-attest/self-verify/self-approve** — attestation, verification, and policy approval require the respective authority; a producer cannot elevate its own outputs.

## 24. Deferred forecasting and post-deployment integration

Deferred to separate, reviewed phases (not this ADR): the Value Forecasting engine (opportunity sizing, scenario construction, realization probability, uncertainty ranges); post-deployment `ObservedAdoption` and observed-effect integration; the producers/wiring of `AttributionAssessment` and `VerificationAssessment`; `governed-value`'s adoption of the four axes and its `DomainProfile`/`GeographyProfile` → policy-reference migration.

## 25. Small, reviewable implementation milestones

1. **M-2E.1** — evidence axes + `MetricClaim`/`MetricObservation` + `EvidenceReference`/`EvidenceProvenance` + `BenchmarkReference` + `AssessmentWindow`/`ForecastHorizon`/`PopulationSlice`/`ConfidenceBasis` **contract shapes** in `governance-contracts` (with axis-rule tests). No engine.
2. **M-2C.1** — `AssessmentContext` + `GeographyPolicy`/`DomainPolicy`/`IntendedOutcomePolicy`/`ValuationPolicy`/`ReadinessPolicy` **schemas + IR** in `uvi-policy-contracts` (envelope, effective period, supersession, revocation, digest binding; **fail-closed on untrusted artifacts**). No authority minted.
3. **M-2C.2** — internal **benchmark registry** (immutable versions, digest-bound resolution, no silent substitution); Policy-Authority-governed admission recorded as a dependency.
4. **M-3R.1** — `agent-value-readiness` contracts: `ReadinessGate`/`GateResult`/`GateStatus`/`ReadinessPolicy`/`ConditionSet` + `ReadinessTarget` + minimal `ReadinessDetermination` envelope.
5. **M-3R.2** — the **target-relative state machine + non-compensatory gate evaluator** (§6–§9), with adversarial tests (mandatory `FAIL` cannot be waived; composite cannot change tier; expired control invalidates conditional readiness).
6. **M-3R.3** — `IntelligenceFitness`/`CapabilityReadiness`/`AdoptionReadiness` catalogs + `AssessedSystemBinding` wiring; conformance/isolated-wheel verifier (mirroring `governed-value`).
7. **M-VAL.1** *(governed-value, later, additive)* — `FinancialValuation` + `ValuationEvidenceManifest` + conservative headline rules, consuming eligibility from `IntendedOutcomePolicy`/`ValuationPolicy`.
8. **M-GTE.1** *(commissioned 2026-09-09 by the §26.10 ruling; not started)* — a **shared, non-authoritative governed-threshold-evaluation leaf** owning deterministic metric-to-threshold evaluation: given a `MetricClaim` value, a `GovernedThreshold` and its `ComparisonOperator`, decide the comparison and nothing else. It **consumes** verified evidence receipts, issued policy coordinates and resolved benchmark values; it **may not** verify source evidence and **may not** resolve a `BenchmarkReference` (that stays exclusively with `benchmark-registry-authority`). Non-authoritative: it attests nothing and mints no authority. `readiness-comparison`'s comparison logic **may inform** it; that package is **not** promoted and stays `RESEARCH_ONLY` / `REQUESTER_ASSERTED`. Distribution name and placement are not fixed by the ruling and remain to be chosen.
9. **M-GVR.1** *(gated, not started)* — a conforming `GateResultVerifier` **composing** trusted evidence verification (`trusted-evidence-authority`), benchmark resolution (`benchmark-registry-authority`) and governed threshold evaluation (M-GTE.1). **No verifier and no integration leaf may ship until all three legs are releasable**, which requires `benchmark-registry-authority` to reach `0.3.0` with its required reviews complete (the D-38(i) review and D-32(4)'s external cryptographic audit).

Each milestone is independently reviewable, fails closed by default, and mints no authority.

## 26. Unresolved issues (implementation detail only — no boundary/ownership change)

1. ~~**Policy Authority for UVI value-policies**~~ — **RESOLVED (2026-08-16)** by [`ADR_UGENCE_POLICY_AUTHORITY.md`](ADR_UGENCE_POLICY_AUTHORITY.md): the **platform-wide Ugence Policy Authority** owns approval **verification**, signing/issuance, exact registration/resolution, and policy-version revocation, and **UVI is its first policy-family adapter**. It stays an **external platform dependency** of UVI engines. **Implementation has since landed**: `packages/policy-authority` (`ugence-policy-authority` 0.3.1) exists and `agent-value-readiness` consumes its public trusted-resolution service through `PolicyAuthorityReadinessPolicyResolver`. Building it was a **platform dependency milestone**, not a UVI engine milestone (D-1, D-16, §19), and the ownership boundary is unchanged: no UVI leaf imports an authority internal.
2. ~~**RA-owned `SubjectContext` dependency**~~ — **RESOLVED (2026-09-09)** by owner ratification of D-14: the contract merged (design PR #1425, 2026-08-13; implementation PR #1432, 2026-08-17, in `risk_authority.integrations.evaluation_contracts`) and **UVI does not adopt it**. `canonical_subject_context_ref` stays a permanently opaque token. Grounds are recorded at D-14: the RA fact set is capacity-shaped and carries no model/prompt/tool identity; §21 forbids a UVI arrow at an authority package; and PR #1432 left the D-4 identifier strings unfrozen. This is no longer an open issue and needs no owner action. A future need for those facts would be met by a **neutral** contract in `governance-contracts` — a new decision, not this one.
3. ~~**`SystemManifest` home**~~ — **RESOLVED (2026-09-09)** by owner ruling: **`SystemManifest` belongs in `governance-contracts`, beside `AssessedSystemBinding`**, and its workflow and policy bindings are **platform-neutral opaque reference-and-digest pairs — never `uvi_policy_contracts.PolicyReference`**. The reference identifies the external artifact; the digest immutably binds the exact artifact assessed; resolution and semantic interpretation stay outside the neutral contract. It must import no UVI, Policy Authority, readiness, risk or execution package. This is what made the placement decidable: the repository already separates the two cases — `AssessedSystemBinding` sits in the neutral leaf because every field is a platform-neutral primitive, while `AssessmentContext` sits in `uvi-policy-contracts` **because** it references `PolicyReference` (`uvi-policy-contracts/contracts/metadata.py:30`). Opaque references keep the manifest in the first case. The manifest must **substantively** bind the assessed composition — model/model-set identities and versions, prompts/configurations, tools/capability sets, workflows and relevant policies; **a nominal manifest with no meaningful component bindings is not permitted**. Confirmed non-competing and additive: the binding carries coarse identity (`system_id`, `system_version`, `configuration_id`, `configuration_digest`) while the manifest carries the composition beneath it. **No new package and no competing assessed-system contract is authorized**, which retires the third candidate the item named. Implemented under the pre-implementation impact record at [`UVI_S26_RULINGS_IMPLEMENTATION_IMPACT.md`](UVI_S26_RULINGS_IMPLEMENTATION_IMPACT.md) and **merged 2026-09-09 in PR #1732 (`6ef1f724`)** — `SystemManifest` at `packages/governance-contracts/src/ugence_governance_contracts/contracts/system_identity.py:459`.
4. **Producers of `AttributionAssessment` / `VerificationAssessment`** — a new attribution capability / DA extension, and a Runtime-Assurance extension vs new; whether `PARTIALLY_ATTRIBUTED` needs a DA reconciliation-contract extension (D-10). **Open — but blocked on an ownership decision, not on missing subjects; no owner assigned.** Grounds corrected 2026-09-09 after a read-only audit of the merged tree: this item was previously said to have no existing subject, which is **wrong**. Only the two UVI contracts are missing; **both named producer candidates already exist**, and so do both symbols in the third clause.

    **The two UVI contracts do not exist** `[V]`. `governance-contracts` 0.9.0 carries 71 curated symbols, of which the only near matches are `AssessmentWindow` and `AttributionStatus`; neither `AttributionAssessment` nor `VerificationAssessment` is among them, although §20 assigns their **shapes** to that package. Nor is there a renamed or partial implementation `[V]`: the one candidate, `AttributionEvidence` (`packages/governed-value/src/governed_value/domain/attribution.py:22`), is three scorability flags — `baseline_captured`, `holdout_or_staged`, `concurrent_changes` — and its module docstring scopes it to "purely evidentiary" signals, not the eight-field shape §17 specifies.

    **Both extension candidates are real, mature packages** `[V]`. *DA* is `ugence-decision-authority` **1.0.0** at `packages/capabilities/decision-authority`: `ReconciliationResult` (`src/ugence_decision_authority/execution/reconciliation.py:23`) is exactly the intent↔observation comparison §17 describes, carrying `status`, `mismatch_codes`, `missing_observations`, `excess_observations` and `compensation_required`. *Runtime-Assurance* is `packages/integration/risk-authority-runtime-assurance`, whose `TrajectoryAssessment` (`src/ugence_risk_authority_runtime_assurance/contracts.py:204`) is the artifact §17 names. So **"extension vs new" is answerable today on both branches**; what is absent is the decision, not the material.

    **The third clause has both its symbols, and a known cost** `[V]`. `PARTIALLY_ATTRIBUTED` is live and enforced (`packages/governance-contracts/src/ugence_governance_contracts/contracts/evidence.py:109`, with rules at `:465` refusing it for `SYNTHETIC` evidence and `:482` requiring `OBSERVED`/`MIXED` grounding plus a declared method). Its DA counterpart `PARTIALLY_RECONCILED` also exists (`packages/capabilities/decision-authority/src/ugence_decision_authority/execution/status.py:96`). Extending that contract is **not free**: `ReconciliationStatus`'s six members are pinned exactly and in order by a frozen-vocabulary ratchet (`packages/capabilities/decision-authority/tests/test_frozen_vocabulary.py:74-76`), so any extension breaks it deliberately and visibly — which is the point of the ratchet, and a cost the owner should price rather than discover.

    **The §17 inaccuracy this item flagged is now fixed** `[V]`. §17 formerly described DA `ReconciliationResult` as `{RECONCILED, MISMATCHED, PARTIALLY_RECONCILED}`; the shipped `ReconciliationStatus` has **six** members — those three plus `INDETERMINATE`, `MANUAL_REVIEW_REQUIRED` and `COMPENSATION_REQUIRED` (`packages/capabilities/decision-authority/src/ugence_decision_authority/execution/status.py:93`). §17's row and its sourced note now carry the full set, so the two sections agree. The semantics §17 assigns to the artifact are unchanged.

5. ~~**Benchmark registry home**~~ — **RESOLVED (2026-08-17)** by
   [`ADR_UGENCE_TRUSTED_EVIDENCE_AND_BENCHMARK_REGISTRY.md`](ADR_UGENCE_TRUSTED_EVIDENCE_AND_BENCHMARK_REGISTRY.md):
   **one shared, platform-wide Ugence Benchmark Registry** (internal platform
   infrastructure, not a UVI-owned leaf and not a fourth UVI engine), with **UVI as its
   first consumer**. It stays an **external platform dependency** of UVI engines.
   **Implementation has since landed**: `packages/benchmark-registry`
   (`ugence-benchmark-registry` 0.1.0, milestone BR-1 — benchmark definition contracts
   only, no registry service) and `packages/benchmark-registry-authority` exist. Building
   them was a **platform dependency milestone**, not a UVI engine milestone. **No UVI
   engine consumes either yet**, so benchmark resolution remains deferred for
   `agent-value-readiness` in fact as well as in scope. **Attestation cadence**
   (D-3) **remains open** and is tracked as DD-8 in that ADR.
6. ~~**`agent-value-readiness` placement**~~ — **RESOLVED (2026-09-09)** by owner ratification: the package is a **top-level leaf at `packages/agent-value-readiness`**, no longer under `packages/capabilities/*`, and D-4's placement is no longer provisional. Grounds: §21's dependency diagram already draws `agent-value-readiness` and `governed-value` as peers directly above `governance-contracts`, and §20 assigns them symmetric ownership as the two UVI engines; carrying one under `capabilities/` and the other at top level contradicted both for no stated reason. The move is path-only — no symbol, contract, digest, dependency, version or classification changed, and `ugence_agent_value_readiness` is unaffected.
7. **`FinancialValuation` eligibility & classification-stamping** location — `IntendedOutcomePolicy` vs a distinct `ValuationPolicy` (D-11). **Placement half RESOLVED-BY-CONSTRUCTION (recorded 2026-09-09, pending owner ratification); stamping half open, no owner assigned.** Grounds corrected after a read-only audit of the merged tree: this item was previously said to have no existing subject, which is **wrong** — both candidate homes exist and one of them was built.

    **The placement question is already settled in the repository, in favour of the distinct type** `[V]`. `ValuationPolicy` exists at `packages/uvi-policy-contracts/src/ugence_uvi_policy_contracts/contracts/policies.py:321` and owns precisely what this item asked to locate — eligibility, permitted valuation methods, required components and their evidential standard, the conservative headline-classification rule (D-12), and the missing-component behavior. `IntendedOutcomePolicy` (`policies.py:213`) did **not** absorb it: it links to it through `valuation_policy_refs`, normalized against `PolicyFamily.VALUATION` at construction, so the two are related **by reference, not merged**. §25 M-2C.1 already commissioned them as separate schemas. What this half needs is **owner ratification of what was built** `[R]`, not a fresh decision.

    **What remains open is the stamping consumer, and it is a real gap** `[G]`. Neither `FinancialValuation` nor `ValuationEvidenceManifest` is defined anywhere in the repository; `FinancialValuation` survives only as a **banned name** in boundary probes (`packages/agent-value-readiness/m3r3_adversarial_probes.py:597`). §17 names `governed-value` as `FinancialValuation`'s owner, but `governed-value` declares only `ugence-governance-contracts>=0.2.0` (`packages/governed-value/pyproject.toml`) and therefore **cannot consume `ValuationPolicy` at all** — the policy stating eligibility and the headline rule is unreachable from the package that would apply it. Closing this needs either a dependency this ADR has not authorized or a different consumer; **no owner is assigned by this correction**.

8. ~~**Whether `SourceBasis.SYNTHETIC` is admitted beyond readiness**~~ — **RESOLVED (2026-09-09)** by owner ruling: **yes, it is admitted beyond readiness, but only as evaluation-scoped.** Synthetic evidence is not readiness-specific; it is restricted to pre-deployment evaluation wherever used. D-9 (amended, above) carries the two consequences: a policy requirement may name `SourceBasis.SYNTHETIC` **only** when it also explicitly requires `EvidenceUsageScope.EVALUATION_ONLY`, refused at construction and never inferred from package location or caller identity; and `EvidenceStatusView` **must carry `usage_scope`** rather than being ratified as basis-only, because a basis-only projection cannot preserve D-9. Three other consumers were found already closed by construction and need no change. Implemented under the [impact record](UVI_S26_RULINGS_IMPLEMENTATION_IMPACT.md) and **merged 2026-09-09 in PR #1732 (`6ef1f724`)** — `ComponentEvidenceRequirement.required_usage_scope` at `packages/uvi-policy-contracts/src/ugence_uvi_policy_contracts/contracts/policies.py:279`, which refuses an unpaired synthetic requirement at construction.
9. ~~**`governance-contracts` `contract_version` bump scope**~~ — **RESOLVED (2026-09-09)** by owner ruling on the read-only audit: **`CONTRACT_VERSION = "1.0.0"` is correct and no provider-contract bump is authorized.** It versions the **provider-contract surface** (`__init__.py:20-28`), not every neutral family in the package, and that surface is unchanged. The audit established this structurally rather than from the prose note: `tests/serialization/frozen_contract_fixtures.json` pins constructor signatures for eleven provider types and `test_idempotency_and_validity_contracts.py:347` asserts the live signatures still equal that baseline — across all history the fixture shows **132 added `ctor_sig` lines and zero removed**, so no pinned provider signature has ever moved; and an AST scan shows **no provider module imports any neutral family**, so no provider dataclass can have gained a field of a G7/G8/G4/DE-5/VR-5/AE-5 type. **Sequencing is also closed**: evidence axes are correctly upstream of policy/context shapes — `uvi-policy-contracts` consumes `SourceBasis`, `BenchmarkReference` and `AssessmentWindow` from `governance-contracts`, which imports nothing from it. **No evidence-axis resequencing is authorized.** One defect is corrected under the same ruling: the permanently-null `api_snapshot_hash` field is **deleted** from the frozen fixtures rather than wired, because `tests/packaging/test_public_api.py` already owns the public-API check and a second hash mechanism is not authorized.
10. ~~**Who owns metric-to-threshold evaluation — and therefore who can supply a `GateResultVerifier`**~~ — **RESOLVED (2026-09-09)** by owner ruling: a **shared, non-authoritative governed-threshold-evaluation leaf is commissioned** to own it (§25 M-GTE.1). It consumes verified evidence receipts, issued policy coordinates and resolved benchmark values; it may neither verify source evidence nor resolve a `BenchmarkReference`, which stays **exclusively** with `benchmark-registry-authority`. A conforming `GateResultVerifier` **composes** the three independently owned legs (§25 M-GVR.1) and **may not ship until all three are releasable** — in particular not before `benchmark-registry-authority` reaches `0.3.0` with its required reviews complete. `readiness-comparison` is **not** promoted: it stays `RESEARCH_ONLY` / `REQUESTER_ASSERTED`, and only its comparison logic may inform the commissioned leaf. Nothing is built by this ruling; §20 and §25 now carry the ownership and the two milestones. The analysis that produced the question is retained below.

    **The analysis, as recorded 2026-09-09.** `GateResultVerifier` (`packages/agent-value-readiness/.../orchestration/protocols.py:71-79`) makes one implementation responsible for the claimed `GateStatus` **and** for "the supporting evidence, benchmark resolution and threshold evaluation behind it" — three obligations, of which exactly one has an authoritative owner:
    * **Evidence verification — owned.** `ugence-trusted-evidence-authority` 0.6.0 (TEV-1 + TEV-2). It is not sufficient on its own: its own README states a verified receipt establishes "not policy sufficiency", so a receipt is **not** a gate status.
    * **Benchmark resolution — owner exists, not yet releasable.** A `GovernedThreshold` is a literal *or* a `BenchmarkReference`; resolving the latter needs `ugence-benchmark-registry-authority`, at **`0.3.0rc1`, a candidate**, whose own README blocks `0.3.0` on the D-38(i) review (reviewer not yet named) **and** D-32(4)'s external cryptographic audit (outstanding). `ugence-benchmark-registry` 0.1.0 is BR-1, contracts only.
    * **Threshold evaluation — was unowned; now commissioned.** §20 assigned it to no package, which is what this item existed to resolve; the ruling commissions the leaf recorded above and in §25 M-GTE.1. The only implementation in the repository is `ugence-readiness-comparison` (`engine.py:459`), which stamps every output `REQUESTER_ASSERTED` / `RESEARCH_ONLY` and is **not approval-bearing**, so it is ineligible by construction rather than merely immature.

    **Interim default, now superseded.** Before the ruling this item recorded a
    build-nothing default. The ruling supersedes it with the same practical
    effect and a firmer basis: nothing is built now, but the owners are named
    and the release gate is explicit. An adapter written before those owners
    exist would have had to improvise two of three obligations *inside* the
    trust boundary — how a fail-closed seam becomes a bypass, which is the
    failure `ugence-agent-value-readiness`'s deny-all defaults exist to prevent.

    **Consequence, unchanged by the ruling.** With a working policy resolver and
    the shipped `DenyAllGateResultVerifier`, every supplied gate result is
    refused, so **any policy carrying at least one applicable gate cannot reach a
    headline readiness classification**. Readiness orchestration is complete and
    correct as a fail-closed boundary and is **not usable end-to-end in
    production**, and stays that way until M-GTE.1 and M-GVR.1 are delivered.
    Commissioning an owner does not shorten that; it only makes the path
    accountable.

None of items 1–9 alters the ratified ownership or semantic boundaries (D-1…D-18); they are implementation details for the milestones in §25. Item 10 was different in kind — it recorded an **ownership gap** rather than an implementation choice — and the 2026-09-09 ruling closed it by **commissioning a new owner**, which §20 and §25 now carry. It adds a package to the architecture; it changes no existing package's ownership and no semantic boundary.

---

*Design-only ADR. No runtime behavior, no authority minted, no contracts or packages created, and no change to `governed-value` 0.2.0 or PR #1426. Implementation requires separate reviewed phases.*
