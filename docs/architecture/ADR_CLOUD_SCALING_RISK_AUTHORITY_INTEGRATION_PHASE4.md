# ADR — Cloud Scaling: Risk Authority Integration (Phase 4)

**Status:** **PROPOSED** (design-only draft; no runtime adapter, no package, no production behavior). Requires owner ratification before any Phase-4 implementation begins.
**Date:** 2026-08-13
**Package (proposed, NOT created here):** `ugence-cloud-scaling-risk-integration` (new leaf integration sibling under `packages/integration/`)
**Depends on (design intent):** `ugence-cloud-scaling-controller >= 0.4.0` (Phase 3 recommendation contracts) · `ugence-risk-authority >= 0.2.0` (the PR-1 evaluation seam)
**Scope:** Define the canonical Phase-4 adapter design and the canonical **risk-subject projection** contract at the design/schema level only. Phase 4 stops at a non-executable risk decision. Envelope issuance / ActionGate / provider execution are **Phase 5**; effect verification / recommendation learning are **Phase 6** — both explicitly excluded.

> This ADR is a design artifact. It creates no runtime package, publishes no distribution, and changes no production behavior. Where it names types, methods, or fields as *proposed*, those are design proposals subject to the owner decisions in §20 — not committed contracts. The only committed contracts it references are those already merged on the default branch and cited by file.

---

## Repository evidence used (verified at default-branch tip `d52a0234`)

All contract shapes below were read from source on the default branch, not from prior summaries.

- **Source (Cloud Scaling, advisory leaf):**
  - `CapacityActionRecommendation` — `packages/capabilities/cloud-scaling-controller/src/ugence_cloud_scaling_controller/planning/recommendation.py` (schema `capacity-action-recommendation-1`; controller `0.4.0`, merged via #1421). Immutable, self-revalidating, `advisory_only = shadow_only = True`, `authority_class = ADVISORY`, `execution_capability = NONE`, `actuation_performed = authorization_performed = effect_verified = False`.
  - `RecommendationAbstention` (schema `capacity-recommendation-abstention-1`) and `RecommendationAbstentionReason` — same file; first-class typed abstention.
  - `CapacitySubject` — `.../canonical/identity.py`: `workload_id: str` (required) + optional `tenant_id, resource_id, environment, cluster, region, zone`.
  - `CandidateActionPlan` / `ActionKind` — `.../planning/candidates.py`: `ActionKind ∈ {NO_CHANGE, SCALE_UP, SCALE_DOWN, COORDINATED}`; each `ResourceChange` carries `subject, current_capacity: int, proposed_capacity: int, role`.
  - `CapacityDecisionEvidence` (schema `capacity-evidence-1`) — `.../canonical/evidence.py`: alternative/legacy advisory evidence artifact (`current_replicas`, `recommended_replicas`, `replica_delta`, …); digest is "an *identity*, never a signature, authorization, risk verdict, control-satisfaction claim, or execution permission … suitable for a future, separately governed Risk Authority integration package to reference as a stable identity."
  - Recommendation digests available: `.digest()` (the `evidence_digest`, `sha256:…`), `.forecast_evidence_digest()`, `.canonical_state_digest()`, `.topology_digest()` (optional), `.cost_evidence_digest()`, `.constraint_digest()`, `.policy_digest()`; validity via `.validity_interval() -> (recommendation_time, validity_seconds)`; `correlation_id` on `forecast_evidence.forecast`.
  - The controller package has **no** `risk_authority` import (verified); `canonical/__init__.py` only *mentions* "a future, separately governed risk-authority" digest in prose.
- **Target (Risk Authority, stdlib-only leaf, `0.2.0`):**
  - `SubjectRiskEvaluationRequest`, `SubjectRiskDecision`, `SubjectRiskDisposition`, `SubjectRiskNonDecisionReason`, `PolicyResolverPort`, `TrustedControlEvidenceResolverPort` — `packages/risk_authority/src/risk_authority/integrations/evaluation_contracts.py` (request schema `risk-subject-evaluation-request-1`, result schema `risk-subject-decision-1`).
  - `RiskEvaluationSeam.production(...)` / `.reference(...)` / `.evaluate(request) -> SubjectRiskDecision` — `.../api/evaluation_seam.py`. Composes `create_case → evaluate_with_evidence (production) / evaluate (reference) → issue_decision` and **stops**; "never calls `issue_envelope` or `authorize_action`." `.production(...)` fails closed on any reference-grade dependency and refuses `ReferenceDecisionAuthority` (defect (h)).
  - `Scope` — `.../domain/scope.py`: `purposes, tools_allow, tools_deny, data_allow, data_deny, destinations, jurisdictions, models, actors, max_autonomy_level, max_transaction_minor_units`.
  - `RiskOutcome ∈ {ALLOW, ALLOW_WITH_CONDITIONS, ESCALATE, DENY}`; `RiskClass ∈ {LOW, MEDIUM, HIGH, CRITICAL}`.
  - Seam prerequisite doc: `docs/architecture/RISK_AUTHORITY_EVALUATION_SEAM.md` (PR-1, ships in `0.2.0`).
- **RA-5 (merged, verified):** `ugence-risk-authority-evidence-runtime 0.1.0` — `EvidenceAdmissionPort` / `ControlAssurancePort` / `TrustedEvidenceIngressPort` production implementations behind the seam; canonical RA-5 spec `docs/architecture/RISK_AUTHORITY_RA5_SPEC.md` (merged via #1408). Invariant: a caller-asserted `PASS` cannot produce production authority.
- **Prior ADRs:** `ADR_CLOUD_SCALING_..._PHASE1/2/3.md` — Phase 3 roadmap line (verbatim): "**Phase 4** — Risk Authority integration."; "**Phase 5** — ActionGate authorization and provider execution."; "**Phase 6** — effect verification and recommendation learning."

---

## 1. Purpose and non-goals

**Purpose.** Give the Cloud Scaling Controller a *one-way, non-executing* path to obtain a canonical Risk Authority decision for a proposed capacity action, by projecting the controller's advisory `CapacityActionRecommendation` into the neutral `SubjectRiskEvaluationRequest` and calling `RiskEvaluationSeam.evaluate(...)`. Phase 4 delivers **only** a `SubjectRiskDecision` (`RISK_PASSED` / `RISK_PASSED_WITH_CONDITIONS` / `RISK_DENIED` / `RISK_ESCALATED` / typed `NOT_EVALUATED`) and stops.

**Non-goals.** Phase 4 does **not**: author or select scaling-risk policy; supply control results or admitted evidence; issue an authorization envelope; invoke ActionGate; authorize or perform any provider/cloud/Kubernetes action; verify a post-execution effect; or learn from outcomes. It adds no execution capability anywhere and mints no authority.

## 2. Package placement and dependency direction

- **New leaf integration sibling** at `packages/integration/cloud-scaling-risk-integration/`, distribution `ugence-cloud-scaling-risk-integration`, src `src/ugence_cloud_scaling_risk_integration/` + `py.typed`, dynamic version via `<pkg>.version.__version__`, `setuptools.build_meta`, `requires-python >= 3.10` — mirroring the RA-4.5 / RA-5 integration-package convention.
- **One-way dependencies only:** the adapter imports `ugence-cloud-scaling-controller` (for `CapacityActionRecommendation` / `RecommendationAbstention`) and `ugence-risk-authority` (for the seam + neutral contracts). **Neither** imports the adapter. The controller **remains a leaf and gains no `risk_authority` import**; `ugence-risk-authority` **remains a stdlib-only leaf**.
- The exact distribution name (`-integration` vs the existing `-runtime` suffix) is an owner decision (§20, D-3).

```
ugence-cloud-scaling-controller (leaf, advisory)  ─┐
                                                    ├─►  ugence-cloud-scaling-risk-integration (Phase 4 adapter)  ─►  RiskEvaluationSeam
ugence-risk-authority (leaf, stdlib-only) ──────────┘        (projection + seam call; STOPS at SubjectRiskDecision)      │
                                                                                                                         └─► RA-5 admission/assurance (already merged)
```

## 3. Trust boundaries and ownership

| Concern | Owner |
|---|---|
| Scaling-risk **policy**, the **control catalog**, evidence **requirements** | **Risk Authority** (`PolicyResolverPort`, resolved inside the trusted composition root) |
| **Admission / assurance** of evidence (trust, provenance, freshness, non-compensatory control status) | **RA-5** (`EvidenceAdmissionPort` / `ControlAssurancePort` / `TrustedEvidenceIngressPort`) |
| Producing the advisory **recommendation** and its digests | **Cloud Scaling Controller** (leaf) |
| **Projection** of the recommendation into the neutral subject + calling the seam | **Phase-4 adapter** (this package) |
| Envelope / ActionGate / execution / effect | **Phase 5–6** (out of scope; fail closed) |

The adapter is **non-authoritative**: it selects no policy, admits no evidence, and carries nothing authority-bearing. It is a pure, deterministic transform + a single seam call.

## 4. Exact input contract from Cloud Scaling

The adapter accepts exactly one of the controller's *validated, immutable* Phase-3 outputs:

- `CapacityActionRecommendation` — the proposed action to risk-evaluate; or
- `RecommendationAbstention` — the controller declined to recommend (typed).

Both are reconstructed/re-validated via their own `from_dict` (strict, unknown-field-rejecting, digest-rebinding `__post_init__`). The adapter accepts **no** other inbound fields: it never accepts a caller-supplied risk class, policy id, control result, evidence body, decision, envelope, or executable flag — there is no parameter for any of them.

## 5. Canonical risk-subject projection (the core Phase-4 contract)

A design-only projection type, **`CapacityRiskSubjectProjection`** (proposed, schema `cloud-scaling-risk-subject-projection-1`), owned by the adapter package:

1. Takes a validated `CapacityActionRecommendation`.
2. Builds a **canonical risk-subject fact dict** — a sorted, string-keyed mapping of every risk-relevant field (§6), with integers as integers, no non-canonical floats (capacities and deltas are integer capacity units; any ratio is carried as a decimal string, never a float), and RFC3339 UTC timestamps at the repository-standard precision (`%Y-%m-%dT%H:%M:%S.%fZ`).
3. Computes **`subject_digest = digest(fact_dict)`** using the RA canonical convention (`to_canonical_obj` + `sha256:` `digest`), so the projection is deterministic and digest-bound.
4. Emits a `SubjectRiskEvaluationRequest` (§ mapping below) whose `subject_digest` equals that value.

The projection is **lossless for all risk-relevant fields** (they all enter the fact dict and thus `subject_digest`), **canonical, deterministic, digest-bound, versioned, tenant- and scope-bound, strict about missing fields, non-authoritative**, and **structurally incapable** of embedding policy, control results, keys, decisions, envelopes, or execution instructions — the neutral request has no field for any of them.

### 5.1 Field mapping (recommendation → neutral request)

| # | Risk-relevant field | Source (`CapacityActionRecommendation`) | Neutral-request destination | Native? |
|---|---|---|---|---|
| 1 | recommendation digest | `.digest()` (`evidence_digest`, `sha256:`) | `subject_digest` (anchor) | ✅ |
| 2 | subject / workload id | `.subject.workload_id` | `subject_id` | ✅ |
| 3 | tenant | `.subject.tenant_id` (optional in source) | `tenant_id` (**required non-empty**) | ⚠️ strictness gap |
| 4 | environment | `.subject.environment` | *(fact dict → `subject_digest` only)* | ❌ no resolver-visible field |
| 5 | cluster | `.subject.cluster` | *(fact dict → `subject_digest` only)* | ❌ |
| 6 | region | `.subject.region` | *(fact dict → `subject_digest` only)* | ❌ |
| 7 | resource / capacity class | `.subject.resource_id`, plan `role` | *(fact dict → `subject_digest` only)* | ❌ |
| 8 | proposed action type | `.selected_plan.action_kind` | *(fact dict → `subject_digest` only)* | ❌ |
| 9 | current & target capacity | plan `ResourceChange.current_capacity` / `.proposed_capacity` | *(fact dict → `subject_digest` only)* | ❌ |
| 10 | validity window | `.recommendation_time` + `.validity_seconds` | *(fact dict → `subject_digest`)*; adapter re-checks vs `now` | ❌ no explicit window field |
| 11 | recommendation timestamp | `.recommendation_time` | *(fact dict)*; `evaluation_time` left `None` (RA clock) | ⚠️ semantic overlap only |
| 12 | forecast-evidence digest | `.forecast_evidence_digest()` | `evidence_references[]` (opaque) | ⚠️ typed→opaque |
| 13 | dependency / cost evidence digest | `.cost_evidence_digest()`, `.topology_digest()` | `evidence_references[]` (opaque) | ⚠️ typed→opaque |
| 14 | correlation / idempotency id | `forecast.correlation_id`; `.recommendation_id` | `correlation_id`; `idempotency_key` | ✅ |
| 15 | risk class | *(absent — advisory)* | `requested_risk_class = None` (RA classifies) | ✅ |
| 16 | purpose / domain id | canonical constants (adapter) | `requested_purpose="cloud_scaling.capacity_action"`, `requested_domain="cloud_scaling"` | ✅ |
| 17 | evidence references | derived digests (12,13, state) | `evidence_references` | ✅ |

Emitted request (design intent): `subject_type="cloud_scaling.capacity_action"`, `requested_scope=Scope(purposes=("cloud_scaling.capacity_action",))` (**minimal — never overloaded** with topology), `evidence_references=(forecast_evidence_digest, cost_evidence_digest[, topology_digest], canonical_state_digest)`, all executable flags fixed `False` by the `SubjectRiskDecision` contract.

## 6. Required subject and scope dimensions

**Required (fail closed if missing):** `workload_id` (→ `subject_id`), `tenant_id`, `recommendation_id`, `recommendation_time`, `validity_seconds`, the selected plan's `action_kind`, and at least one `ResourceChange` with `current_capacity` / `proposed_capacity`, plus `forecast_evidence_digest`. **Scope-bound:** the fact dict binds `{tenant_id, environment, cluster, region, resource_id, workload_id}`; **missing scope is distinct from a named scope** — an absent `environment` is encoded as an explicit `null` sentinel in the fact dict (never omitted and never coerced to `""`), so `subject_digest` differs between "no environment" and "environment = ''".

## 7. Recommendation and evidence digest binding

- `subject_digest` is derived from the fact dict, which itself carries `recommendation_digest = rec.digest()` and each evidence digest (forecast / cost / topology / state / constraint / policy). **Any change to any input digest changes `subject_digest`** (acceptance invariant).
- The adapter independently recomputes `rec.digest()` from the reconstructed recommendation and requires equality with the carried value before projecting → **digest mismatch fails closed**, no seam call.

## 8. Policy-resolution request semantics

The adapter **never selects policy**. It calls `seam.evaluate(request)`; the seam calls the trusted `PolicyResolverPort.resolve(tenant_id, purpose, domain, risk_class, requested_scope, now)`. If no authoritative policy exists → `NOT_EVALUATED(NO_AUTHORITATIVE_POLICY)`; if multiple claim authority → ambiguity → fail closed. The resolver is production-authoritative (`is_production_authoritative = True`) or the production seam refuses to construct.

> **Contract gap (see §20 D-1/D-2).** `PolicyResolverPort.resolve(...)` receives only `(tenant, purpose, domain, risk_class, requested_scope, now)`. Fields #4–#10 (environment, cluster, region, resource/capacity class, action type, current/target capacity, validity window) are bound losslessly inside `subject_digest` **but are not individually visible to the resolver**, so scaling-risk policy cannot *route* on them unless they are placed in `requested_scope` — which this design **refuses** ("do not silently overload unrelated fields"). This is the single material contract gap; §20 records the two resolutions.

## 9. Evidence-reference semantics

The projection carries only **opaque evidence references** (digest strings) in `evidence_references`. It never carries evidence bodies, control results, or a `PASS`/`FAIL` claim. RA-5's `TrustedControlEvidenceResolverPort` resolves those references to candidate records, which then pass the *existing* `EvidenceAdmissionPort` → `ControlAssurancePort` gates. Absent/failed resolution ⇒ required controls resolve to `MISSING` ⇒ the non-compensatory gate fails closed to `DENY`/`ESCALATE`. **The adapter cannot promote evidence to trusted status.**

## 10. Time and validity semantics

- All timestamps canonical RFC3339 UTC at `%Y-%m-%dT%H:%M:%S.%fZ`.
- The recommendation is already temporally self-consistent (its `__post_init__` enforces `forecast_cutoff ≤ recommendation_time`, `forecast_for == cutoff + horizon`, validity ≤ forecast horizon, non-future state/topology/cost).
- The adapter additionally re-checks the **recommendation validity window** `[recommendation_time, recommendation_time + validity_seconds]` against `now`: an **expired** recommendation (or one whose validity extends beyond forecast validity) yields a typed non-evaluation and **never reaches** risk evaluation.
- `evaluation_time` on the request is left `None`; the seam supplies the authoritative clock. The recommendation timestamp/validity live in the fact dict (risk-relevant, digest-bound).

## 11. Typed abstention and fail-closed behavior

`RecommendationAbstention` input ⇒ the adapter **does not call the seam**; it returns a typed `PROJECTION_ABSTAINED_UPSTREAM` outcome (proposed) carrying the abstention's subject + reason + available input digests. A controller abstention **never becomes a risk approval**. Every non-nominal case (§12) is fail-closed and typed; none returns an ALLOW-family disposition.

## 12. Risk-decision output semantics & failure behavior

The adapter returns the seam's `SubjectRiskDecision` unchanged (or, for pre-seam failures, a typed adapter outcome). Every case below is **non-executing** and **never falls through to approval**:

| Failure case | Outcome |
|---|---|
| controller abstention | adapter `PROJECTION_ABSTAINED_UPSTREAM` (no seam call) |
| malformed recommendation | `from_dict` `RecommendationError` → fail closed, no seam call |
| digest mismatch | adapter re-check fails → fail closed, no seam call |
| expired recommendation / beyond forecast validity | adapter validity re-check → typed non-evaluation (no seam call) |
| missing required scope / ambiguous subject | `SubjectError` / strict projection → fail closed |
| no authoritative policy | seam `NOT_EVALUATED(NO_AUTHORITATIVE_POLICY)` |
| ambiguous / expired policy | seam `NOT_EVALUATED(AMBIGUOUS_POLICY / EXPIRED_POLICY)` |
| missing / untrusted / contradictory evidence | RA-5 admission → controls `MISSING`/untrusted → `RISK_DENIED` / `RISK_ESCALATED` (never PASS) |
| unavailable Risk Authority / evaluator | seam `NOT_EVALUATED(AUTHORITY_UNAVAILABLE / EVALUATOR_UNAVAILABLE)` |
| unsupported schema | seam `NOT_EVALUATED(UNSUPPORTED_SCHEMA_VERSION)` |
| reconstruction failure | fail closed, no seam call |

A `RISK_PASSED` / `RISK_PASSED_WITH_CONDITIONS` can arise **only** from RA's non-compensatory gate over admitted, trusted evidence — never from any adapter-side field.

## 13. Non-executable invariants

Every `SubjectRiskDecision` returned has `authorization_performed = envelope_issued = actiongate_invoked = actuation_performed = effect_verified = executable = False` (fixed by the RA contract's `__post_init__`). `RISK_PASSED` is **not** ActionGate authorization and carries no executable capability. The adapter never touches `issue_envelope` / `authorize_action`; the production seam structurally cannot reach them (PR-1 containment).

## 14. Serialization and reconstruction requirements

For the projection contract and any adapter outcome type: strict constructor / `from_dict` parity; unknown fields rejected; mandatory `schema_version`; canonical JSON; deterministic `sha256:` digest; no non-canonical floats; canonical RFC3339 UTC timestamps; nested digest re-validation on reconstruction; exact tenant/subject/scope binding; frozen/immutable records; round-trip digest stability; explicit authority flags fixed `False`. A reconstructed projection recomputes `subject_digest` and rejects a mismatch.

## 15. Threat model

| Threat | Mitigation |
|---|---|
| Caller forges a `PASS` / supplies control results | No field exists; RA-5 admission is the only path to control satisfaction |
| Caller injects policy / risk class / envelope | No field exists in `SubjectRiskEvaluationRequest` |
| Digest-swap (pair a recommendation with another's digest) | Recommendation `__post_init__` rebinds every input digest; adapter recomputes `rec.digest()` |
| Cross-tenant / cross-scope replay | `tenant_id` + scope bound into `subject_digest`; RA-5 binding tuple re-check; seam `TENANT_SCOPE_MISMATCH` |
| Stale / expired recommendation replay | adapter validity-window re-check vs `now` (fail closed) |
| Scope-injection via overloaded fields | `requested_scope` is minimal; topology dims live only in `subject_digest`, never in scope |
| Action-type / capacity spoofing | bound into `subject_digest`; any change alters the digest |
| Downstream execution reach | non-executing seam; sentinel tests assert envelope/ActionGate never invoked |

## 16. Compatibility and versioning

- Projection schema `cloud-scaling-risk-subject-projection-1`; adapter distribution starts at `0.1.0`.
- Consumes **already-merged** contracts: controller `0.4.0`, risk-authority `0.2.0`. **No change** to either frozen contract is required by §20 D-1. §20 D-2 (a `risk-subject-evaluation-request-2` extension) would be a *coordinated, RA-owned, versioned migration* — out of Phase-4 scope and gated on owner approval.
- Frozen identifiers/schemas/digests are not changed without a versioned migration.

## 17. Test and acceptance matrix (for the implementation phase, when authorized)

**Negative/adversarial tests ≥ 2× happy-path.** Independent tests for: caller-supplied `PASS` has no path; forged / duck-typed recommendation; digest mismatch; missing tenant / subject; cross-tenant & cross-scope reuse; missing-vs-named scope; stale / future / expired recommendation; validity beyond forecast horizon; unsupported schema; unknown fields; contradictory / missing / untrusted evidence (→ deny/escalate, never pass); no authoritative / ambiguous policy; unavailable Risk Authority; reconstruction failure; direct-construction-vs-`from_dict`; installed-wheel behavior; and **sentinel tests** proving envelope issuance, ActionGate, and provider execution are never invoked and every executable flag stays `False`. Happy path: a valid recommendation over admitted trusted evidence yields a non-executable `RISK_PASSED` and nothing more.

## 18. Relationship to RA-5

Phase 4 is a **consumer** of the RA-5 boundary, not a re-implementation of it. The projection supplies only *subject facts + opaque evidence references*; RA-5 (`EvidenceAdmissionPort` / `ControlAssurancePort` / `TrustedEvidenceIngressPort`, merged in `ugence-risk-authority-evidence-runtime 0.1.0`) performs trusted admission and non-compensatory control assurance. The RA-5 invariant — *a caller-asserted `PASS` cannot mint authority* — is preserved because the adapter has no channel to assert one. Phase 4 depends on RA-5 being merged and verified (it is).

## 19. Explicit Phase 5 and Phase 6 exclusions

Phase 4 performs **no** envelope issuance, **no** ActionGate authorization, **no** provider/cloud execution or actuation (Phase 5), and **no** effect verification or recommendation learning (Phase 6). These remain fail-closed and are not implemented, imported, or wired by this design.

## 20. Open implementation details requiring owner approval

- **D-1 — Projection-anchoring (no contract change) [recommended default].** Ship Phase 4 against the *unchanged, frozen* `risk-subject-evaluation-request-1`: carry the scaling topology/action/validity dimensions only inside `subject_digest` + canonical purpose/domain, and constrain scaling-risk policy to route on `(tenant, purpose, domain, risk_class, scope)`. **Consequence:** policy cannot vary by environment/region/action/capacity at resolve time. Non-executing and fail-closed are fully preserved.
- **D-2 — Versioned RA-side extension (only if policy must route on those dimensions).** A coordinated, RA-owned bump to `risk-subject-evaluation-request-2` adding an *optional, additive, strict* `subject_attributes: Mapping[str,str]` (canonical, sorted) + explicit `subject_valid_from` / `subject_valid_until`, and widening `PolicyResolverPort.resolve(...)` to receive them. This touches the seam contract merged in PR #1423 and is **out of Phase-4-design scope**; it needs explicit owner approval and its own versioned migration before implementation.
- **D-3 — Package name.** `ugence-cloud-scaling-risk-integration` vs the existing `-runtime` suffix convention (`ugence-cloud-scaling-risk-authority-runtime`).
- **D-4 — Canonical `requested_purpose` / `requested_domain` / `subject_type` string constants** (proposed: `"cloud_scaling.capacity_action"` / `"cloud_scaling"`).
- **D-5 — Primary input artifact.** `CapacityActionRecommendation` (recommended) vs `CapacityDecisionEvidence`; and whether both are accepted.
- **D-6 — Idempotency key composition** (`recommendation_id` alone vs `recommendation_id` + `subject_digest`).
- **D-7 — Note for maintainers:** the Phase 3 ADR header still reads "PROPOSED (not merged)" while its code is merged (#1421, controller `0.4.0`); and the seam's `TrustedControlEvidenceResolverPort` docstring still says RA-5 "will implement" though RA-5 is merged. Neither blocks Phase 4; both are documentation-tense items for owner cleanup.

---

## Acceptance invariants (this ADR requires, before Phase-4 implementation is accepted)

- Controller package has **no** Risk Authority import; adapter has **one-way** dependencies only.
- Adapter **cannot author or select policy**; caller **cannot supply control results** or authority-bearing artifacts.
- An input-digest change **alters the projection digest**.
- Cross-tenant and cross-scope reuse **fails closed**; missing scope ≠ named scope.
- Expired or invalid recommendations **cannot reach** risk evaluation; controller abstentions **never become** risk approvals.
- `RISK_PASSED` remains **non-executable**; every `executable / envelope / actiongate / actuation / effect` flag remains `False`.
- **No** envelope issuance, **no** ActionGate invocation, **no** provider execution, **no** effect verification.
- Negative tests are **≥ 2×** happy-path tests when implementation begins.

## Consequences

- Cloud Scaling gains a safe, auditable, non-executing risk-decision path; the controller stays an advisory leaf.
- One material contract gap (§8/§20) is surfaced explicitly rather than papered over by overloading `Scope`.
- No runtime adapter, package, or Phase 5/6 behavior is created by this ADR. Implementation is gated on: RA-5 merged & verified (done), this ADR ratified, the projection contract approved, and D-1…D-6 resolved.
