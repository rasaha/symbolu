# ADR — Cloud Scaling: Risk Authority Integration (Phase 4)

**Status:** **PROPOSED** (design-only draft; no runtime adapter, no package, no production behavior). Owner decisions D-1…D-7 were ratified on 2026-08-13 (see §20) and are folded into this design; the *design* is ratified, its *implementation* remains gated (see the final sequencing rule).
**Date:** 2026-08-13
**Package (approved name, NOT created here — D-3):** `ugence-cloud-scaling-risk-integration` at `packages/integration/cloud-scaling-risk-integration/`
**Depends on (design intent):** `ugence-cloud-scaling-controller >= 0.4.0` (Phase 3 recommendation contracts) · `ugence-risk-authority >= 0.2.0` (the PR-1 evaluation seam), with a future, RA-owned `ugence-risk-authority` minor bump for the v2 subject-context contract (D-2)
**Scope:** Define the canonical Phase-4 adapter design, the canonical **risk-subject projection**, and the RA-owned strict **v2 neutral subject-context contract** at the design/schema level only. Phase 4 stops at a non-executable risk decision. Envelope issuance / ActionGate / provider execution are **Phase 5**; effect verification / recommendation learning are **Phase 6** — both explicitly excluded.

> **Ratified owner decisions (2026-08-13):** **D-2 approved** — a strict, versioned, canonical, digest-bound, RA-owned *neutral subject-context* contract (§5.2), **not** an unrestricted generic attribute map; **D-1 (digest-only) rejected**. D-3 package name approved. D-4 purpose/domain constants proposed but their final identifiers are marked for ratification during review. D-5 primary input = `CapacityActionRecommendation` + its digest-bound embedded evidence; `RecommendationAbstention` propagates as a typed non-evaluation and never enters risk evaluation as a recommendation. D-6 idempotency = canonical `tenant + subject + recommendation digest + evaluation purpose + schema version` (never timestamps alone). D-7 documentation-tense cleanups are recorded separately and are out of scope for this ADR.

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

Per **D-5**, the **primary input is `CapacityActionRecommendation` together with its digest-bound embedded evidence** (forecast / cost / topology / state / constraint / policy digests are re-derived and rebound by the recommendation's own `__post_init__`). The adapter reconstructs/re-validates it via `from_dict` (strict, unknown-field-rejecting, digest-rebinding).

`RecommendationAbstention` is also an accepted input but is **not** a recommendation: it **propagates as a typed non-evaluation** (§11) and **must never enter risk evaluation as a recommendation** — the adapter does not project it into a `SubjectRiskEvaluationRequest` and does not call the seam for it.

The adapter accepts **no** other inbound fields: it never accepts a caller-supplied risk class, policy id, control result, evidence body, decision, envelope, or executable flag — there is no parameter for any of them.

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
| 14 | correlation id | `forecast.correlation_id` | `correlation_id` | ✅ |
| 14a | idempotency key (D-6) | canonical `tenant_id` + `subject_id` + `recommendation.digest()` + evaluation purpose + request `schema_version` (digest of that tuple; **never timestamps alone**) | `idempotency_key` | ✅ |
| 15 | risk class | *(absent — advisory)* | `requested_risk_class = None` (RA classifies) | ✅ |
| 16 | purpose / domain id | canonical constants (adapter) | `requested_purpose="cloud_scaling.capacity_action"`, `requested_domain="cloud_scaling"` | ✅ |
| 17 | evidence references | derived digests (12,13, state) | `evidence_references` | ✅ |

Emitted request (design intent): `subject_type="cloud_scaling.capacity_action"`, `requested_scope=Scope(purposes=("cloud_scaling.capacity_action",))` (**minimal — never overloaded** with topology), `evidence_references=(forecast_evidence_digest, cost_evidence_digest[, topology_digest], canonical_state_digest)`, all executable flags fixed `False` by the `SubjectRiskDecision` contract.

Under the ratified decision the ❌/⚠️ rows (#4–#13) are **not** left digest-only: they are carried in the strict RA-owned **v2 neutral subject-context** (§5.2), which makes them individually visible to policy resolution while remaining domain-neutral and non-authoritative. Digest-only anchoring (D-1) is rejected because it cannot expose those facts to `PolicyResolverPort` (see §8, §20).

### 5.2 Canonical v2 neutral subject-context contract (`SubjectContext`) — RA-owned

**Owned by Risk Authority**, added to `risk_authority.integrations.evaluation_contracts` (schema `risk-subject-context-1`), embedded in a new request schema `risk-subject-evaluation-request-2`. The Cloud Scaling adapter may **populate** it but may **not** define the meaning of authority or select policy. It is a strict, closed, frozen, canonical, digest-bound contract — **not** a generic `Mapping[str,str]`. It carries only *neutral subject facts* that policy resolution legitimately needs; the adapter maps scaling semantics onto neutral slots (capacity→`magnitude_before/after`, cluster→`compute_group`, action→`action_type`).

Proposed fields (explicit canonical types; final names ratified in review — D-4):

| Field | Type | Neutral meaning | Populated from (scaling) | Missing-vs-named |
|---|---|---|---|---|
| `schema_version` | `str` (mandatory, `= "risk-subject-context-1"`) | contract version | constant | — |
| `tenant_id` | `str` (required, non-empty) | tenant | `subject.tenant_id` | required |
| `environment` | `Optional[str]` | deployment environment | `subject.environment` | `None` ≠ `""` |
| `region` | `Optional[str]` | geographic locality | `subject.region` | `None` ≠ `""` |
| `zone` | `Optional[str]` | finer locality | `subject.zone` | `None` ≠ `""` |
| `compute_group` | `Optional[str]` | compute domain / cluster | `subject.cluster` | `None` ≠ `""` |
| `resource_class` | `Optional[str]` | resource / capacity class | `subject.resource_id` / plan `role` | `None` ≠ `""` |
| `action_type` | `str` (required, controlled neutral vocabulary) | proposed action kind | `ActionKind` (`no_change`/`scale_up`/`scale_down`/`coordinated`) | required |
| `magnitude_before` | `Optional[int]` (int units; not bool/float) | current quantity | `ResourceChange.current_capacity` | `None` ≠ `0` |
| `magnitude_after` | `Optional[int]` (int units; not bool/float) | target quantity | `ResourceChange.proposed_capacity` | `None` ≠ `0` |
| `subject_asserted_at` | `datetime` (canonical RFC3339 UTC) | when the subject fact was asserted | `recommendation_time` | required |
| `subject_valid_from` | `datetime` (canonical RFC3339 UTC) | validity-window start | `recommendation_time` | required |
| `subject_valid_until` | `datetime` (canonical RFC3339 UTC) | validity-window end | `recommendation_time + validity_seconds` | required |
| `evidence_references` | `tuple[str, ...]` (opaque, non-empty strings) | applicable evidence references | forecast/cost/topology/state digests | required (may be empty tuple) |

`SubjectContext` requirements (design):
- strict constructor / `from_dict` parity; **unknown fields rejected**; non-canonical values rejected (int fields reject `bool`/`float`; timestamps must parse at `%Y-%m-%dT%H:%M:%S.%fZ`; strings non-empty when present);
- **distinguishes missing (`None`) from named** — never coerces `None`→`""`/`0`, and both states produce distinct digests;
- deterministic `sha256:` `context_digest = digest(to_canonical_obj(context))`;
- **binds into `subject_digest`** (the projection folds `context_digest` and the full recommendation fact dict into `subject_digest`) and thereby into `request_digest = SubjectRiskEvaluationRequest.digest()`;
- **replay safety:** `tenant_id` + `subject_id` + the validity window bound in-context; RA's authoritative binding re-check rejects cross-tenant, cross-subject and cross-scope reuse and rejects use outside `[subject_valid_from, subject_valid_until]`;
- **exposes no** caller-selected policy, **no** caller-authored control status, and contains **no** key, decision, envelope, authorization, or execution instruction — the field set is closed and excludes them structurally;
- **non-executable** (request-side context only; the `SubjectRiskDecision` keeps every executable flag `False`);
- **domain-neutral** at the RA boundary (neutral field names; RA never learns the word "capacity").

### 5.3 Policy-resolver access (design)

`risk-subject-evaluation-request-2` adds an **optional** `subject_context: Optional[SubjectContext]`. `PolicyResolverPort` gains a **backward-compatible** widening so the resolver may inspect `subject_context` (e.g., an added keyword `subject_context: Optional[SubjectContext] = None`, or a `resolve` successor); v1 resolvers that ignore it keep working. This is an additive, versioned RA-side change (§16) — **not implemented in this PR**.

## 6. Required subject and scope dimensions

**Required (fail closed if missing):** `workload_id` (→ `subject_id`), `tenant_id`, `recommendation_id`, `recommendation_time`, `validity_seconds`, the selected plan's `action_kind`, and at least one `ResourceChange` with `current_capacity` / `proposed_capacity`, plus `forecast_evidence_digest`. **Scope-bound:** the fact dict binds `{tenant_id, environment, cluster, region, resource_id, workload_id}`; **missing scope is distinct from a named scope** — an absent `environment` is encoded as an explicit `null` sentinel in the fact dict (never omitted and never coerced to `""`), so `subject_digest` differs between "no environment" and "environment = ''".

## 7. Recommendation and evidence digest binding

- `subject_digest` is derived from the fact dict, which itself carries `recommendation_digest = rec.digest()` and each evidence digest (forecast / cost / topology / state / constraint / policy). **Any change to any input digest changes `subject_digest`** (acceptance invariant).
- The adapter independently recomputes `rec.digest()` from the reconstructed recommendation and requires equality with the carried value before projecting → **digest mismatch fails closed**, no seam call.

## 8. Policy-resolution request semantics

The adapter **never selects policy**. It calls `seam.evaluate(request)`; the seam calls the trusted `PolicyResolverPort.resolve(tenant_id, purpose, domain, risk_class, requested_scope, now)`. If no authoritative policy exists → `NOT_EVALUATED(NO_AUTHORITATIVE_POLICY)`; if multiple claim authority → ambiguity → fail closed. The resolver is production-authoritative (`is_production_authoritative = True`) or the production seam refuses to construct.

> **Why v1 is insufficient, and how v2 resolves it.** In `risk-subject-evaluation-request-1`, `PolicyResolverPort.resolve(...)` receives only `(tenant, purpose, domain, risk_class, requested_scope, now)`. Fields #4–#13 (environment, cluster, region, resource/capacity class, action type, current/target capacity, recommendation timestamp, validity window, evidence references) can be bound losslessly inside `subject_digest` **but are not individually visible to the resolver**, so scaling-risk policy cannot *route* on them unless they are stuffed into `requested_scope` — which this design **refuses** ("do not silently overload unrelated fields"). **Digest-only anchoring (D-1) is therefore rejected.** The ratified resolution (**D-2**) is the strict RA-owned **v2 `SubjectContext`** (§5.2): a resolver reading `risk-subject-evaluation-request-2` inspects those neutral facts directly. The adapter populates the context; it never selects policy.

## 9. Evidence-reference semantics

The projection carries only **opaque evidence references** (digest strings) in `evidence_references`. It never carries evidence bodies, control results, or a `PASS`/`FAIL` claim. RA-5's `TrustedControlEvidenceResolverPort` resolves those references to candidate records, which then pass the *existing* `EvidenceAdmissionPort` → `ControlAssurancePort` gates. Absent/failed resolution ⇒ required controls resolve to `MISSING` ⇒ the non-compensatory gate fails closed to `DENY`/`ESCALATE`. **The adapter cannot promote evidence to trusted status.**

## 10. Time and validity semantics

- All timestamps canonical RFC3339 UTC at `%Y-%m-%dT%H:%M:%S.%fZ`.
- The recommendation is already temporally self-consistent (its `__post_init__` enforces `forecast_cutoff ≤ recommendation_time`, `forecast_for == cutoff + horizon`, validity ≤ forecast horizon, non-future state/topology/cost).
- The adapter additionally re-checks the **recommendation validity window** `[recommendation_time, recommendation_time + validity_seconds]` against `now`: an **expired** recommendation (or one whose validity extends beyond forecast validity) yields a typed non-evaluation and **never reaches** risk evaluation.
- `evaluation_time` on the request is left `None`; the seam supplies the authoritative clock. The recommendation timestamp/validity live in the fact dict (risk-relevant, digest-bound).

## 11. Typed abstention and fail-closed behavior

Per **D-5**, a `RecommendationAbstention` input ⇒ the adapter **does not project it and does not call the seam**; it returns a typed `PROJECTION_ABSTAINED_UPSTREAM` outcome (proposed) carrying the abstention's subject + reason + available input digests. An abstention **must never enter risk evaluation as a recommendation**, and a controller abstention **never becomes a risk approval**. Every non-nominal case (§12) is fail-closed and typed; none returns an ALLOW-family disposition.

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
- Consumes **already-merged** contracts: controller `0.4.0`, risk-authority `0.2.0`.
- **v2 subject-context migration (D-2), RA-owned, additive, versioned, backward-compatible:**
  - New `SubjectContext` (schema `risk-subject-context-1`) and new request schema `risk-subject-evaluation-request-2` with an **optional** `subject_context` field.
  - **v1 preserved:** `risk-subject-evaluation-request-1` requests remain valid and continue to validate/round-trip unchanged; a v2 request with `subject_context = None` is behaviorally equivalent to v1. `SUPPORTED_REQUEST_SCHEMA_VERSIONS` becomes `{…-1, …-2}`.
  - `PolicyResolverPort` widening is additive (optional keyword / successor method) so existing resolvers keep working — a **bounded, documented migration**, not a breaking change.
  - Requires a **versioned `ugence-risk-authority` minor bump** (e.g. `0.2.0 → 0.3.0`) owned by Risk Authority; **not implemented in this PR**.
- Frozen identifiers/schemas/digests are not changed without a versioned migration; the v1 contract's frozen digest behavior is untouched.

## 17. Test and acceptance matrix (for the implementation phase, when authorized)

**Negative/adversarial tests ≥ 2× happy-path.** Independent tests for: caller-supplied `PASS` has no path; forged / duck-typed recommendation; digest mismatch; missing tenant / subject; cross-tenant & cross-scope reuse; missing-vs-named scope; stale / future / expired recommendation; validity beyond forecast horizon; unsupported schema; unknown fields; contradictory / missing / untrusted evidence (→ deny/escalate, never pass); no authoritative / ambiguous policy; unavailable Risk Authority; reconstruction failure; direct-construction-vs-`from_dict`; installed-wheel behavior; and **sentinel tests** proving envelope issuance, ActionGate, and provider execution are never invoked and every executable flag stays `False`. Happy path: a valid recommendation over admitted trusted evidence yields a non-executable `RISK_PASSED` and nothing more.

## 18. Relationship to RA-5

Phase 4 is a **consumer** of the RA-5 boundary, not a re-implementation of it. The projection supplies only *subject facts + opaque evidence references*; RA-5 (`EvidenceAdmissionPort` / `ControlAssurancePort` / `TrustedEvidenceIngressPort`, merged in `ugence-risk-authority-evidence-runtime 0.1.0`) performs trusted admission and non-compensatory control assurance. The RA-5 invariant — *a caller-asserted `PASS` cannot mint authority* — is preserved because the adapter has no channel to assert one. Phase 4 depends on RA-5 being merged and verified (it is).

## 19. Explicit Phase 5 and Phase 6 exclusions

Phase 4 performs **no** envelope issuance, **no** ActionGate authorization, **no** provider/cloud execution or actuation (Phase 5), and **no** effect verification or recommendation learning (Phase 6). These remain fail-closed and are not implemented, imported, or wired by this design.

## 20. Owner decisions — ratified 2026-08-13 (design ratified; implementation gated)

- **D-1 — Digest-only projection-anchoring: REJECTED.** Carrying the scaling facts only inside `subject_digest` cannot expose environment/cluster/region/resource-class/action-type/current-target-capacity/validity to `PolicyResolverPort`, so scaling-risk policy could not route on risk-relevant facts. Rejected in favor of D-2.
- **D-2 — Strict, versioned, RA-owned v2 neutral subject-context: APPROVED (with constraints).** Adopt the strict `SubjectContext` contract in §5.2 — **not** an unrestricted generic `subject_attributes` map. It must: remain domain-neutral at the RA boundary; use explicit canonical types and validation; reject unknown/non-canonical fields; distinguish missing from named values; bind all subject context into `subject_digest` and `request_digest`; prevent cross-tenant, cross-subject and cross-scope replay; expose no caller-selected policy and no caller-authored control status; contain no key/decision/envelope/authorization/execution instruction; remain non-executable; require a versioned Risk Authority contract change; preserve v1 backward compatibility (or document a bounded migration — see §16); and be **owned by Risk Authority, not Cloud Scaling**. The adapter may populate it but may not define authority or select policy. **Not implemented in this PR.**
- **D-3 — Package name: APPROVED** — `packages/integration/cloud-scaling-risk-integration/` (dist `ugence-cloud-scaling-risk-integration`).
- **D-4 — Canonical purpose/domain constants: PROPOSED, final identifiers to be ratified in review.** Proposed `requested_purpose = "cloud_scaling.capacity_action"`, `requested_domain = "cloud_scaling"`, `subject_type = "cloud_scaling.capacity_action"`, `action_type ∈ {no_change, scale_up, scale_down, coordinated}`. These strings are **marked for ratification during review** and are not frozen by this ADR.
- **D-5 — Primary input: APPROVED** — `CapacityActionRecommendation` **plus its digest-bound embedded evidence** is the primary input (§4). `RecommendationAbstention` propagates as a **typed non-evaluation** (§11) and **must never enter risk evaluation as a recommendation**. (`CapacityDecisionEvidence` is not the primary input.)
- **D-6 — Idempotency: APPROVED** — the idempotency key is a digest of canonical `tenant_id + subject_id + recommendation.digest() + evaluation purpose + request schema_version`. **Timestamps alone must not** define idempotency (§5.1, row 14a).
- **D-7 — Documentation-tense cleanup: OUT OF SCOPE for this PR.** The Phase-3 ADR header still reads "PROPOSED" though merged (#1421), and the seam's `TrustedControlEvidenceResolverPort` docstring still says RA-5 "will implement" though RA-5 is merged (#1408). These are **recorded separately** and **must not expand this ADR PR**.

Residual items for the implementation phase (not blockers to ratifying this design): the exact `PolicyResolverPort` widening shape (optional keyword vs successor method), and the final `ugence-risk-authority` version number for the v2 bump.

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
- The v1 limitation (§8) is resolved by a strict, RA-owned, versioned **v2 subject-context** (§5.2) rather than papered over by overloading `Scope` — the facts policy resolution needs become first-class and canonically typed, while the RA boundary stays domain-neutral and non-authoritative.
- No runtime adapter, package, v2 RA contract, or Phase 5/6 behavior is created by this ADR. Implementation is gated on: RA-5 merged & verified (done), this ADR ratified, the v2 subject-context contract approved and versioned by Risk Authority, and D-4's final identifiers ratified in review.
