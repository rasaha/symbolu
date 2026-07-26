# H2 — AI Recommendation & Evidence Synthesis — Completion Report

Application-local, additive completion on top of the H1 baseline (`2dc80d4`). AI
Hiring can now produce a **governed, evidence-grounded recommendation package for
human review** — but cannot make or execute the hiring decision. **No frozen
platform file was modified; no frozen API changed; no ActionGate/execution behavior
added.** All new code is under `ai_hiring/` and imports the platform only through
`decision_governance.api` and `governance_providers.api`; TAP is reached solely
through the Assertion Governance Provider contract (never TAP internals).

## Status

- **Implemented:** evidence synthesis, structured hiring claims, provider-backed
  (TAP) assertion evaluation, advisory recommendation contract with uncertainty /
  insufficiency handling, a replaceable generator port, human-review packages, and
  deterministic recommendation-provenance reconstruction.
- **Tests:** **38 new H2 tests**; full AI Hiring suite **632 passed** (was 594).
- **Frozen platform:** untouched — freeze verification **PASS**; dependency-direction
  **0 violations**; kernel+framework+TAP+ActionGate+AI-Hiring **771 passed**.

## Authority invariant (preserved)

AI may summarize/synthesize evidence, identify supported/unsupported claims, generate
an advisory proposal, express uncertainty, and request evidence. AI **may not** become
the accountable decision authority, advance/reject/hire a candidate, approve its own
recommendation, bypass human review, or convert a recommendation into an executable
action. Enforced by: no binding decision status; `advisory=True` invariant on every
recommendation; human-only reviewer dispositions (`ReviewerAuthorityError` for
non-human actors); and the absence of any decide/execute method
(`test_h2_boundary.py`).

## Architecture

```mermaid
flowchart TD
    A[Application in ASSESSMENT/IN_REVIEW] --> S[EvidenceSynthesisService]
    I[(EvidenceIntakeItems - H1)] --> S
    JD[JobDefinition: rubric + required evidence] --> S
    MP[MinimizationPolicy: prohibited attrs, quarantine, bounds] --> S
    S --> P[EvidencePackage: bounded, provenance-preserving, deterministic fingerprint]
    P --> G[RecommendationGeneratorPort - deterministic reference / replaceable]
    G --> DC[Draft structured claims + advisory outcome]
    DC --> EV[ClaimAssertionEvaluator]
    EV -->|AssertionGovernanceRequest| AAI[AssertionAssessmentIntegration]
    AAI -->|evaluate| TAP[(Assertion Governance Provider = TAP / reference)]
    TAP --> AAI --> EV
    EV --> CL[HiringClaims + ClaimAssertionBindings]
    CL --> RG{H2 readiness gate}
    RG -->|missing evidence| EI[EVIDENCE_INCOMPLETE]
    RG -->|claim fails policy / provider error| AR[ASSERTION_REVIEW_REQUIRED]
    RG -->|all pass| RR[READY_FOR_HUMAN_REVIEW]
    RR --> HR[RecommendationReviewPackage] --> H[Human reviewer]
    H -->|human-only disposition| D[accept-for-consideration / reject / request-evidence / revise]
    subgraph Audit & Reconstruction (hiring-owned, hash-chained)
      X[HiringDomainAuditService] --> RC[RecommendationReconstructionService]
    end
    S --> X
    EV --> X
    RG --> X
    D --> X
    classDef frozen fill:#eef,stroke:#88a;
    class TAP,AAI frozen;
```

**Boundary:** the runtime (generator + provider) proposes and evaluates support; the
**human** decides. ActionGate/execution is out of scope (H3/H4).

## Recommendation & claim contracts

**`HiringRecommendation`** (immutable, versioned; `ai_hiring/recommendations/recommendation.py`)
carries: ids (recommendation/tenant/application), candidate subject ref, requisition &
job-definition version refs, rubric version, assessment workspace ref, advisory
`outcome`, `advisory=True` invariant, confidence + uncertainty note, structured
rationale, `material_claim_ids`, `unsupported_claim_ids`, `evidence_gaps`, the exact
`evidence_refs` + package ref, generator/provider metadata, policy refs, provenance +
correlation ids, `status`, and the supersession chain (`supersedes`/`superseded_by`).

**Statuses:** `DRAFT`, `EVIDENCE_INCOMPLETE`, `ASSERTION_REVIEW_REQUIRED`,
`READY_FOR_HUMAN_REVIEW`, `REJECTED_BY_REVIEW`, `SUPERSEDED`. **No binding decision
status exists.** **Advisory outcomes:** `RECOMMEND_ADVANCE/HOLD/DECLINE`,
`INSUFFICIENT_EVIDENCE`, `NO_RECOMMENDATION` — never a hire/accept.

**`HiringClaim`** (`ai_hiring/recommendations/claim.py`): claim id/type, normalized
proposition, candidate/application scope, competency/criterion, supporting &
contradicting evidence refs, `EvidenceSufficiency`, `AssertionOutcome` (+ provider
trace, coverage, explanation refs), confidence, generator provenance, review status,
materiality. Claim types are competency/requirement/evidence-structural only —
**no personality, demographic, medical, emotional, or protected-class inference.**

## TAP integration map

Integration lives in `ai_hiring/recommendations/tap_integration.py` and depends **only**
on `governance_providers.api`:

1. For each **material** claim, build a provider-neutral `AssertionGovernanceRequest`
   (`assertion` = proposition, `assertion_type` = claim type, `evidence_refs` = cited
   evidence, `policy_refs`, `context` = {application, criterion}, `correlation_id`).
2. Submit via `AssertionAssessmentIntegration.assess(request)` — the framework's
   app-facing seam wrapping the resolved provider (TAP, or the framework's
   deterministic reference provider in tests). **TAP internals are never imported.**
3. Store the returned `AssertionAssessment` as an immutable `ClaimAssertionBinding`
   (coverage, evidence_coverage, covered/unsupported refs, trace id, fingerprint,
   `evaluated` flag), linked to the recommendation by **correlation & causation ids** —
   audit taxonomies are *not* merged.
4. Map provider coverage → H2 `AssertionOutcome`: `SUPPORTED→SUPPORTED`,
   `CONSTRAINED→PARTIALLY_SUPPORTED`, `INDETERMINATE→UNEVALUABLE`,
   `UNSUPPORTED→UNSUPPORTED` (or `CONFLICTING` when the claim cites contradicting
   evidence). Only `SUPPORTED`/`PARTIALLY_SUPPORTED` pass the assertion policy.
5. `READY_FOR_HUMAN_REVIEW` is **blocked** when any required claim fails the policy or
   a provider error remains unresolved. Provider failure (unavailable/timeout/malformed/
   resolution) is fail-safe → `UNEVALUABLE` with the error preserved.

**TAP evaluates evidentiary support; it does not decide whether the candidate should be
hired.**

## Evidence synthesis & data minimization

`EvidenceSynthesisService` (`ai_hiring/synthesis/`) consumes only tenant-authorized
intake evidence for the target application, binds it to the correct
application/candidate/requisition/**rubric & job-definition versions**, distinguishes
DIRECT from DERIVED evidence, and detects **missing / quarantined / stale-rubric /
duplicated / conflicting** evidence. It produces a bounded `EvidencePackage` with a
deterministic fingerprint (identical normalized inputs + policy → identical
fingerprint) and records the **exact** evidence set used. **Adverse (contradicting)
evidence is always retained** — minimization truncates only non-adverse items.

Data minimization (`MinimizationPolicy`): minimum-necessary bounds (`max_items`),
field-level exclusion, tenant-prohibited attributes (defaulting to a protected-class
set), sensitive-hash quarantine, per-type allow-listing, and package size reporting.
Protected/prohibited attributes supplied to the pipeline are rejected
(`ProhibitedAttributeError`) and the pipeline never infers protected attributes. (This
expresses and enforces intent at the synthesis boundary; it does not by itself
guarantee external-data non-exposure — that depends on the configured generator
adapter.)

## Failure behavior (fail-safe)

| Condition | Behavior |
|---|---|
| Missing / quarantined evidence | `EVIDENCE_INCOMPLETE`; never review-ready |
| Stale rubric version | `StaleRubricVersionError` (synthesis blocked) |
| Tenant/scope mismatch | `CrossTenantHiringAccessError` + audited denial |
| Wrong application's package | `RecommendationGenerationError` |
| Provider resolution / TAP unavailable / timeout | claim `UNEVALUABLE`, `evaluated=False` → `ASSERTION_REVIEW_REQUIRED` |
| Malformed generator output | `GeneratorOutputInvalidError`; **no recommendation created** |
| Prohibited attribute supplied | `ProhibitedAttributeError` |
| Broken audit chain at reconstruction | `hash_chain_valid=False`, `reconstructed=False` |

No failure path silently produces a review-ready recommendation.

## Repositories & services (application-local)

Repositories (`ai_hiring/repositories/{product,recommendation}_repositories.py`):
evidence-synthesis packages (versioned), recommendations (versioned + history +
active/for-application), claims (append-only), provider-evaluation bindings
(append-only), reviewer dispositions (append-only) — tenant-agnostic storage,
immutability, duplicate prevention, deterministic ordering. Services:
`EvidenceSynthesisService`, `RecommendationGenerationService` (generation + review +
supersession), `RecommendationReconstructionService`. The legacy phase-3/4
`RecommendationService` is untouched.

## Validation report

| Check | Result |
|---|---|
| AI Hiring suite (`pytest ai_hiring`) | **632 passed** (594 baseline + 38 H2) |
| Kernel + framework + TAP + ActionGate + AI Hiring | **771 passed** |
| Platform Freeze verification | **PASS** |
| Dependency-direction | **0 violations** |
| Frozen platform files modified | **none** (diff = `ai_hiring/` + `docs/ai-hiring/`) |
| H2 import surface | `decision_governance.api` + `governance_providers.api` only; no TAP/ActionGate/vendor-SDK imports (`test_h2_boundary.py`) |

### H2 test coverage (38 tests)
supported flow · insufficient evidence · conflicting evidence · unsupported material
claim · indeterminate claim · TAP provider failure · malformed generator output ·
generator timeout · non-eligible application state · tenant isolation (synthesis /
generation / reconstruction) · wrong-application evidence · stale rubric version ·
prohibited-attribute exclusion · quarantine · adverse-evidence retention · duplicate
generation prevention · supersession · reviewer rejection · human-only authority ·
deterministic reconstruction · audit-chain verification & tamper detection · no-binding-
status · always-advisory · no-decision-authority · no-frozen-imports.

**Baseline limitations carried forward** (unchanged, pre-existing, unrelated): the
`classify_change` freeze-tooling self-test failure and the whole-repository
`_SymboluFinder` collection errors in unrelated experimental modules. The H2 green
baseline is scoped to the platform-relevant packages, **not** the whole repository.

## Completion criteria — met

- AI recommendations grounded in versioned evidence ✓ (exact `evidence_refs` +
  package fingerprint; rubric/job-def version binding).
- Every material claim evaluated through the Assertion Governance Provider ✓.
- Unsupported claims cannot become review-ready ✓ (readiness gate).
- Recommendations remain advisory ✓ (`advisory=True`; no binding status).
- Humans retain all binding decision authority ✓ (human-only dispositions; no
  decide/execute path).
- Exact recommendation reconstructable from evidence/policies/provider results/versions ✓.
- Tenant & protected-attribute boundaries enforced ✓.
- All prior + new tests pass ✓; Platform Freeze passes ✓; no frozen file changed ✓; no
  ActionGate/execution behavior added ✓.

## Deferred to H3–H6 (NOT implemented in H2)

- **H3 — Governance Integration:** run the DGM case → recommendation → **human
  decision** → review flow; overrides via DGM review tasks; ActionGate provider wiring
  begins.
- **H4 — Hiring Actions, Execution & Reconciliation:** authorize offer/rejection via
  **ActionGate**; external execution ports; reconciliation. (No execution in H2.)
- **H5 — Validation, Fairness Analysis & Shadow Pilot:** end-to-end scenarios; fairness
  **analysis only** (no certification); audit-reconstruction reporting.
- **H6 — Packaging, Documentation & Product Wrap-up.**
- Also deferred: final hiring decisions, autonomous candidate selection, offer/rejection
  execution, ActionGate integration, fairness certification, and production model
  integrations (only the replaceable generator port + deterministic reference generator
  ship in H2).
