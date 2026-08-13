# ADR — Cloud Scaling: Risk Authority Integration (Phase 4)

**Status:** **PROPOSED — owner decisions recorded; independent audit corrections incorporated; pending final ratification** (design-only draft; no runtime adapter, no package, no production behavior). Owner decisions D-1…D-7 are recorded (§20); implementation remains gated (see the final sequencing rule).
**Date:** 2026-08-13
**Package (approved name, NOT created here — D-3):** `ugence-cloud-scaling-risk-integration` at `packages/integration/cloud-scaling-risk-integration/`
**Depends on (design intent):** `ugence-cloud-scaling-controller >= 0.4.0` (Phase 3 recommendation contracts) · `ugence-risk-authority >= 0.2.0` (the PR-1 evaluation seam), with a future, RA-owned `ugence-risk-authority` minor bump for the v2 subject-context contract (D-2)
**Scope:** Define the canonical Phase-4 adapter design, the canonical **risk-subject projection**, and the RA-owned strict **v2 neutral subject-context contract** at the design/schema level only. Phase 4 stops at a non-executable risk decision. Envelope issuance / ActionGate / provider execution are **Phase 5**; effect verification / recommendation learning are **Phase 6** — both explicitly excluded.

> **Recorded owner decisions (2026-08-13), independent-audit corrections incorporated:** **D-2 approved** — a strict, versioned, canonical, digest-bound, RA-owned *neutral subject-context* contract (§5.2), **not** an unrestricted generic attribute map, with `tenant_id` and `evidence_references` kept authoritative on the outer request (§5.1); **D-1 (digest-only) rejected**. D-3 package name approved. D-4 purpose/domain constants proposed but their final identifiers are marked for ratification during review. D-5 primary input = `CapacityActionRecommendation` + its digest-bound embedded evidence; `RecommendationAbstention` propagates as a typed non-evaluation and never enters risk evaluation as a recommendation. D-6 idempotency = canonical `tenant + subject + recommendation digest + evaluation purpose + schema version` (never timestamps alone). D-7 documentation-tense cleanups are recorded separately and are out of scope for this ADR.

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
- **Package role (D-3 approved).** `cloud-scaling-risk-integration` is intentionally an **integration/projection** package: it projects a controller recommendation into the neutral RA request and calls the seam. It **owns no runtime and no authority** — it holds no policy, no control catalog, no keys, no clock, and no execution surface; it neither issues envelopes nor invokes ActionGate. The `-integration` suffix (vs the `-runtime` suffix used by RA-4.5/RA-5 composition packages) reflects that it is a thin one-way projection adapter, not a composition runtime. The name is approved; no substantive reason to change it.

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

A design-only projection type, **`CapacityRiskSubjectProjection`** (proposed, schema `cloud-scaling-risk-subject-projection-1`), owned by the adapter package. It performs **one** authoritative digest-binding chain in which every risk-relevant fact has a **single source-of-truth object**. The neutral subject facts are deliberately carried at two layers of the request — as the raw `subject_context` (so the resolver can read them) **and**, transitively, inside `subject_digest` via `SubjectBinding.context_digest`. This is a **deliberate layered commitment to one immutable object**, not two independently-supplied representations: Risk Authority recomputes and reconciles the layers **before policy resolution** (§5.3), so the raw context and its committed digest cannot disagree without failing closed. The full normative chain, pseudocode, a worked canonical example and a tamper demonstration are in **§5.3**; the summary is:

1. Build a **curated, closed `SubjectContext`** (§5.2) from approved neutral subject facts only — the adapter never passes the controller's raw `to_canonical_dict()` into the RA canonicalizer (§5.3, §14).
2. Canonicalize it with the named **Risk Authority canonicalizer** (`risk_authority.crypto.canonical.to_canonical_obj` / `canonical_bytes`) and compute a schema-tagged **`context_digest`** (§5.3, §5.4).
3. Build a **fixed `SubjectBinding` object** (schema `risk-subject-binding-1`) containing only binding anchors — schema tag, tenant + subject identity (**derived** from the outer request), recommendation digest, context digest — and compute **`subject_digest = digest(SubjectBinding)`**.
4. Bind `subject_digest` and the **outer** request fields (tenant, evidence references, purpose/domain, subject id, request schema version) into the versioned **`request_digest`** (schema `risk-subject-evaluation-request-2`).

The chain is **canonical, deterministic, schema-tagged, digest-bound, versioned, tenant- and scope-bound, strict about missing fields, non-authoritative**, and **structurally incapable** of embedding policy, control results, keys, decisions, envelopes, or execution instructions. Each risk-relevant fact has a **single source-of-truth object** (neutral facts → `SubjectContext`; tenant identity and evidence references → the outer request); where a value also appears as a binding anchor (tenant, subject id) or as a layered commitment (the context), the extra copy is **derived/recomputed and reconciled by RA before policy resolution** (§5.3), never an independent second source (§5.5).

### 5.1 Field mapping (recommendation → neutral request)

Each fact has exactly **one** canonical home. "Hashed via" names the single object whose `context_digest`/`subject_digest`/`request_digest` covers it (§5.3).

| # | Risk-relevant field | Source (`CapacityActionRecommendation`) | Single canonical home | Hashed via |
|---|---|---|---|---|
| 1 | recommendation digest | `.digest()` (`evidence_digest`, `sha256:`) | `SubjectBinding.recommendation_digest` | `subject_digest` |
| 2 | subject / workload id | `.subject.workload_id` | **outer** `subject_id` (sole authority); `SubjectBinding.subject_id` **derived** from it (not in `SubjectContext`) | `request_digest` + `subject_digest` |
| 3 | tenant | `.subject.tenant_id` | **outer** `tenant_id` (authoritative) + `SubjectBinding.tenant_id` (binding anchor) | `request_digest` + `subject_digest` |
| 4 | environment | `.subject.environment` | `SubjectContext.environment` | `context_digest` |
| 5 | cluster | `.subject.cluster` | `SubjectContext.compute_group` | `context_digest` |
| 6 | region | `.subject.region` | `SubjectContext.region` | `context_digest` |
| 7 | resource / capacity class | `.subject.resource_id`, plan `role` | `SubjectContext.resource_class` | `context_digest` |
| 8 | proposed action type | `.selected_plan.action_kind` | `SubjectContext.action_type` | `context_digest` |
| 9 | current & target capacity | plan `ResourceChange.current_capacity` / `.proposed_capacity` | `SubjectContext.magnitude_before` / `magnitude_after` | `context_digest` |
| 10 | validity window | `.recommendation_time` + `.validity_seconds` | `SubjectContext.subject_valid_from` / `subject_valid_until` (adapter re-checks vs `now`, §10) | `context_digest` |
| 11 | recommendation timestamp | `.recommendation_time` | `SubjectContext.subject_asserted_at` (outer `evaluation_time` stays `None`, §10) | `context_digest` |
| 12 | forecast-evidence digest | `.forecast_evidence_digest()` | **outer** `evidence_references[]` (opaque) | `request_digest` |
| 13 | dependency / cost evidence digest | `.cost_evidence_digest()`, `.topology_digest()`, `.canonical_state_digest()` | **outer** `evidence_references[]` (opaque) | `request_digest` |
| 14 | correlation id | `forecast.correlation_id` | outer `correlation_id` | `request_digest` |
| 14a | idempotency key (D-6) | digest of canonical `tenant_id` + `subject_id` + `recommendation.digest()` + evaluation purpose + request `schema_version` (**never timestamps alone**) | outer `idempotency_key` | `request_digest` |
| 15 | risk class | *(absent — advisory)* | outer `requested_risk_class = None` (RA classifies) | `request_digest` |
| 16 | purpose / domain id | canonical constants (adapter) | outer `requested_purpose` / `requested_domain` (D-4) | `request_digest` |

Note the deliberate split (F2): **tenant**, **subject identity** and **evidence references** live on the **outer request**, which is their sole authoritative source; `SubjectContext` holds only *neutral subject facts* (#4–#11) and **not** tenant, subject id, or evidence references. `SubjectBinding.tenant_id` and `SubjectBinding.subject_id` are binding anchors **derived from the outer request** (not second sources of truth) and are recomputed/reconciled by RA before policy resolution (§5.3). Emitted request: `subject_type="cloud_scaling.capacity_action"`, `requested_scope=Scope(purposes=("cloud_scaling.capacity_action",))` (**minimal — never overloaded** with topology), all executable flags fixed `False` by the `SubjectRiskDecision` contract.

Under the ratified decision (D-2) the neutral facts #4–#11 are carried in the strict RA-owned **v2 `SubjectContext`** (§5.2), individually visible to policy resolution while remaining domain-neutral and non-authoritative. Digest-only anchoring (D-1) is rejected because it cannot expose those facts to `PolicyResolverPort` (see §8, §20).

### 5.2 Canonical v2 neutral subject-context contract (`SubjectContext`) — RA-owned

**Owned by Risk Authority**, added to `risk_authority.integrations.evaluation_contracts` (schema `risk-subject-context-1`), embedded in a new request schema `risk-subject-evaluation-request-2`. The Cloud Scaling adapter may **populate** it but may **not** define the meaning of authority or select policy. It is a strict, closed, frozen, canonical, digest-bound contract — **not** a generic `Mapping[str,str]`. It carries only *neutral subject facts* that policy resolution legitimately needs; the adapter maps scaling semantics onto neutral slots (capacity→`magnitude_before/after`, cluster→`compute_group`, action→`action_type`).

Proposed fields (explicit canonical types; final names ratified in review — D-4):

`SubjectContext` carries **only neutral subject facts**. It **does not** carry `tenant_id`, `subject_id`, or `evidence_references` — tenant and subject identity and evidence references are authoritative on the **outer** request (F2); the outer `subject_id` is subject identity's **sole** source. The `schema_version` string is the object's fixed **schema tag** (§5.4).

| Field | Type | Neutral meaning | Populated from (scaling) | Missing-vs-named |
|---|---|---|---|---|
| `schema_version` | `str` (mandatory, fixed `= "risk-subject-context-1"`) | contract + schema tag | constant | — |
| `environment` | `Optional[str]` | deployment environment | `subject.environment` | `None` ≠ `""` |
| `region` | `Optional[str]` | geographic locality | `subject.region` | `None` ≠ `""` |
| `zone` | `Optional[str]` | finer locality | `subject.zone` | `None` ≠ `""` |
| `compute_group` | `Optional[str]` | compute domain / cluster | `subject.cluster` | `None` ≠ `""` |
| `resource_class` | `Optional[str]` | resource / capacity class | `subject.resource_id` / plan `role` | `None` ≠ `""` |
| `action_type` | `str` (required; canonical enum string) | proposed action kind | `ActionKind` value (`no_change`/`scale_up`/`scale_down`/`coordinated`) | required |
| `magnitude_before` | `Optional[int]` (canonical integer; `bool`/`float` rejected) | current quantity | `ResourceChange.current_capacity` | `None` ≠ `0` |
| `magnitude_after` | `Optional[int]` (canonical integer; `bool`/`float` rejected) | target quantity | `ResourceChange.proposed_capacity` | `None` ≠ `0` |
| `subject_asserted_at` | `datetime` → canonical UTC `%Y-%m-%dT%H:%M:%S.%fZ` | when the subject fact was asserted | `recommendation_time` | required |
| `subject_valid_from` | `datetime` → canonical UTC `%Y-%m-%dT%H:%M:%S.%fZ` | validity-window start | `recommendation_time` | required |
| `subject_valid_until` | `datetime` → canonical UTC `%Y-%m-%dT%H:%M:%S.%fZ` | validity-window end | `recommendation_time + validity_seconds` | required |

**Canonical encoding rules (F3), enforced by the RA canonicalizer (§5.4):**
- **integers** are canonical integers; `bool` and `float` are rejected (`to_canonical_obj` raises on `float` by construction);
- **enums** (`action_type`) are their canonical string values;
- **timestamps** are normalized-UTC in the exact format the RA canonicalizer already emits (`%Y-%m-%dT%H:%M:%S.%fZ`);
- **missing optional values** are the explicit sentinel `null` and are **distinct** from any named value — `None` is never coerced to `""`/`0`, and the two states yield **different** `context_digest`s;
- **no floats** appear in the canonical context; **no exponent-form or representation-dependent decimal strings** are used;
- confidence scores, forecast coverage, ratios, `timing_seconds` and similar floating-point analytics are **excluded** from `SubjectContext`. They are risk-relevant only as *evidence*, so they are bound through typed evidence artifacts and their digests via the outer `evidence_references` (§9) — never as neutral subject facts. (Should a future revision need one as a subject fact, it must first define one exact fixed-scale integer/decimal-string representation; none is defined here.)

`SubjectContext` further requires (design):
- strict constructor / `from_dict` parity; **unknown fields rejected**; non-canonical values rejected;
- deterministic schema-tagged **`context_digest = digest(to_canonical_obj(context))`** (`sha256:`) — the context's canonical identity. The context is the **single source of truth** for its neutral facts; it is committed once as `context_digest` and additionally carried raw in the request as a **layered commitment to the same immutable object** that RA reconciles before policy resolution (§5.3, F1);
- **exposes no** caller-selected policy, **no** caller-authored control status; contains **no** key, decision, envelope, authorization, or execution instruction — the field set is closed and excludes them structurally;
- **non-executable** (request-side context only; the `SubjectRiskDecision` keeps every executable flag `False`);
- **domain-neutral** at the RA boundary (neutral field names; RA never learns the word "capacity").

### 5.3 The one authoritative digest-binding chain (normative)

Three canonical objects, three **schema-tagged** digests. Neutral facts live in **one** source-of-truth object (`SubjectContext`); binding anchors (tenant, subject id) are **derived** from the outer request; the context is additionally carried raw as a **layered commitment** RA reconciles before policy resolution (below).

```
# All canonicalization/hashing uses the Risk Authority primitives (§5.4):
#   canon  = risk_authority.crypto.canonical.to_canonical_obj / canonical_bytes
#   digest = risk_authority.crypto.hashing.digest   # -> "sha256:" + hex(sha256(canonical_bytes(x)))

# (1) curated, closed neutral context — neutral subject facts ONLY (no tenant, no subject_id,
#     no evidence refs). Built field-by-field by the adapter; the controller's raw
#     to_canonical_dict() is NEVER passed in (§5.4, §14).
context = SubjectContext(
    schema_version   = "risk-subject-context-1",     # fixed schema tag
    environment      = rec.subject.environment,       # None stays null (missing != named)
    region           = rec.subject.region,
    zone             = rec.subject.zone,
    compute_group    = rec.subject.cluster,
    resource_class   = rec.subject.resource_id,
    action_type      = rec.selected_plan.action_kind.value,   # canonical enum string
    magnitude_before = change.current_capacity,       # canonical int
    magnitude_after  = change.proposed_capacity,      # canonical int
    subject_asserted_at = rec.recommendation_time,    # -> canonical UTC
    subject_valid_from  = rec.recommendation_time,
    subject_valid_until = rec.recommendation_time + timedelta(seconds=rec.validity_seconds),
)
context_digest = digest(context)                      # schema tag: risk-subject-context-1

# (2) fixed subject-binding object — binding anchors ONLY, all DERIVED from the outer request.
binding = SubjectBinding(
    schema_version        = "risk-subject-binding-1", # fixed schema tag
    tenant_id             = outer_tenant_id,          # derived from the outer request (sole authority)
    subject_id            = outer_subject_id,         # derived from the outer request (sole authority)
    subject_type          = "cloud_scaling.capacity_action",
    recommendation_digest = rec.digest(),             # the controller-established source digest (§7)
    context_digest        = context_digest,
)
subject_digest = digest(binding)                      # schema tag: risk-subject-binding-1

# (3) versioned request — outer authority for tenant, subject id, evidence refs, purpose/domain.
request = SubjectRiskEvaluationRequest_v2(
    schema_version      = "risk-subject-evaluation-request-2",   # fixed schema tag
    tenant_id           = outer_tenant_id,            # AUTHORITATIVE tenant identity
    subject_id          = outer_subject_id,           # AUTHORITATIVE subject identity (sole source)
    subject_type        = "cloud_scaling.capacity_action",
    subject_digest      = subject_digest,             # binds (1)+(2)
    requested_purpose   = "cloud_scaling.capacity_action",       # D-4 (to ratify)
    requested_domain    = "cloud_scaling",                        # D-4 (to ratify)
    requested_risk_class= None,                       # RA classifies
    requested_scope     = Scope(purposes=("cloud_scaling.capacity_action",)),
    evidence_references = (rec.forecast_evidence_digest(),
                           rec.cost_evidence_digest(),
                           rec.topology_digest(),      # omitted when None
                           rec.canonical_state_digest()),          # AUTHORITATIVE evidence refs
    subject_context     = context,                    # raw, inspectable by the resolver (§5.6)
    correlation_id      = rec.forecast_evidence.forecast.correlation_id,
    idempotency_key     = digest({"tenant_id": outer_tenant_id, "subject_id": outer_subject_id,
                                  "recommendation_digest": rec.digest(),
                                  "purpose": "cloud_scaling.capacity_action",
                                  "schema_version": "risk-subject-evaluation-request-2"}),  # D-6
    evaluation_time     = None,                       # never caller-populated (§10)
)
request_digest = digest(request)                      # schema tag: risk-subject-evaluation-request-2
```

**RA validation before policy resolution (normative).** The request carries the neutral facts at two layers — raw `subject_context` and, transitively, `subject_digest` (via `SubjectBinding.context_digest`) — as a deliberate **layered commitment to one immutable object**. Before **any** policy resolution, Risk Authority MUST, in order:
1. validate the supplied `subject_context` (strict schema, closed field set, canonical encoding — §5.2);
2. **recompute** `context_digest' = digest(subject_context)` from the supplied raw context;
3. **reconstruct** `SubjectBinding` from `{outer tenant_id, outer subject_id, subject_type, recommendation_digest, context_digest'}` and **recompute** `subject_digest' = digest(SubjectBinding)`;
4. require `subject_digest' == request.subject_digest` (which entails `context_digest' == SubjectBinding.context_digest`).

Any inequality — including a raw `subject_context` altered while `subject_digest` is left stale — is a **fail-closed non-decision** (`NOT_EVALUATED`, never PASS/ALLOW) **before the resolver reads a single fact**. The resolver therefore only ever routes on facts whose digest RA has re-derived and bound; the two layers cannot disagree without failing closed.

**Binding-anchor derivation (F2).** `binding.tenant_id` and `binding.subject_id` are **derived** from the outer request (its sole authoritative fields) and reconstructed from it in step 3; `request.tenant_id` / `request.subject_id` are the only sources. There is no independent third copy — `SubjectContext` carries neither — so identity cannot silently disagree.

**Worked canonical example** (compact JSON, sorted keys, from the RA canonicalizer; reproducible byte-for-byte):

`SubjectContext` canonical form (**no `subject_id`**) →
```json
{"action_type":"scale_up","compute_group":"cluster-7","environment":"prod","magnitude_after":9,"magnitude_before":6,"region":"eu-west-1","resource_class":"web","schema_version":"risk-subject-context-1","subject_asserted_at":"2026-08-13T04:00:00.000000Z","subject_valid_from":"2026-08-13T04:00:00.000000Z","subject_valid_until":"2026-08-13T04:15:00.000000Z","zone":null}
```
`context_digest = sha256:9af3f626a08e888a2916215a59c965e221179388ba3987cbbc6b2e0e64cfdbb0`

`SubjectBinding` canonical form (`tenant_id` / `subject_id` **derived** from the outer request; illustrative `recommendation_digest = sha256:1111…1111`) →
```json
{"context_digest":"sha256:9af3f626a08e888a2916215a59c965e221179388ba3987cbbc6b2e0e64cfdbb0","recommendation_digest":"sha256:1111111111111111111111111111111111111111111111111111111111111111","schema_version":"risk-subject-binding-1","subject_id":"wl-checkout-api","subject_type":"cloud_scaling.capacity_action","tenant_id":"tnt-acme"}
```
`subject_digest = sha256:eb4526a6679470e603bbc757cde7cfac9c7b2258256eaecef729e356a1df6c38`

`SubjectRiskEvaluationRequest_v2` canonical form (`evidence_references` illustrative; `idempotency_key` per D-6) →
```json
{"correlation_id":"corr-42","evaluation_time":null,"evidence_references":["sha256:aaa","sha256:bbb","sha256:ccc","sha256:ddd"],"idempotency_key":"sha256:42aaa799941a6661c39c3dbe45ea7e7b2ecfcc5d617a9fc09ee32cbbe8959dd0","requested_domain":"cloud_scaling","requested_purpose":"cloud_scaling.capacity_action","requested_risk_class":null,"requested_scope":{"actors":[],"data_allow":[],"data_deny":[],"destinations":[],"jurisdictions":[],"max_autonomy_level":0,"max_transaction_minor_units":null,"models":[],"purposes":["cloud_scaling.capacity_action"],"tools_allow":[],"tools_deny":[]},"schema_version":"risk-subject-evaluation-request-2","subject_context":{"action_type":"scale_up","compute_group":"cluster-7","environment":"prod","magnitude_after":9,"magnitude_before":6,"region":"eu-west-1","resource_class":"web","schema_version":"risk-subject-context-1","subject_asserted_at":"2026-08-13T04:00:00.000000Z","subject_valid_from":"2026-08-13T04:00:00.000000Z","subject_valid_until":"2026-08-13T04:15:00.000000Z","zone":null},"subject_digest":"sha256:eb4526a6679470e603bbc757cde7cfac9c7b2258256eaecef729e356a1df6c38","subject_id":"wl-checkout-api","subject_type":"cloud_scaling.capacity_action","tenant_id":"tnt-acme"}
```
`request_digest = sha256:b1973925e2cb80dcd69e993a1cc8d9f2743cb3b4e799f6772e88909ddd77bd0a`

**Tamper demonstration — altered raw context with a stale digest fails before policy resolution.** Suppose the raw `subject_context` is altered `environment: "prod" → "staging"` while the committed `subject_digest` is left stale. RA's **step 2** recomputes `context_digest' = sha256:7d0c44ea7a501417f3cb0f454ceaa70eabbc4c65587d547066470d2796e88164` (≠ the `sha256:9af3f626…dbb0` bound inside the stale `subject_digest`). **Step 3** reconstructs the binding with `context_digest'` and recomputes `subject_digest' = sha256:24875cdc6ff29904bd83ad012b62fae93f97ca2531703ee261c0de8cd6744ab9`, which **≠** the carried `subject_digest = sha256:eb4526a6…6c38`. **Step 4** therefore fails closed (`NOT_EVALUATED`) **before the resolver reads any fact** — the resolver never routes on the altered `staging` value. (Verified against the RA canonicalizer.)

Two independent implementers using the RA canonicalizer over the same curated inputs produce these exact digests.

### 5.4 Authoritative canonicalizer and schema-tagged canonical hashing (F4, F5)

- **Phase 4 uses the Risk Authority canonicalization rules for the newly versioned RA contracts.** `SubjectContext`, `SubjectBinding` and `SubjectRiskEvaluationRequest_v2` are canonicalized with `risk_authority.crypto.canonical.to_canonical_obj` / `canonical_bytes` (compact JSON, sorted keys, NFC-normalized strings, UTC timestamps, **floats rejected**) and digested with `risk_authority.crypto.hashing.digest` (`sha256:` prefix). This **hashing primitive is not modified** by this docs-only task.
- **Controller canonical serialization** (`content_digest(...)` in the cloud-scaling controller) establishes the **source `recommendation_digest`** only. It does **not** define the canonical representation of `SubjectContext`, `SubjectBinding`, or the RA request — those are RA-owned and RA-canonicalized.
- **Schema-tagged canonical hashing (honest description).** The RA digest primitive is a **bare SHA-256 over canonical bytes** (`sha256_hex(canonical_bytes(x))`, `hashing.py`) — it is **not** a cryptographic domain-separated hash (no domain-prefix / keyed construction, unlike the controller's `content_digest`, which prepends a `NAMESPACE \x1f domain \x1f schema_version` preimage, `serialization.py`). Separation here is achieved by each object carrying a fixed **`schema_version` tag** — `risk-subject-context-1`, `risk-subject-binding-1`, `risk-subject-evaluation-request-2` — as a field **inside its own canonical form** (consistent with existing RA contracts, which embed `schema_version` per contract). A digest computed under one schema tag will not equal, and must not be accepted in the slot of, a digest under another; this is enforced by the embedded `schema_version` **plus strict validation** (a consumer checks the expected `schema_version` before trusting a digest), **not** by the hash construction. Different `schema_version` values yield different canonical bytes and different digests. *(A future hardening could adopt a `content_digest`-style domain-prefixed preimage for these RA contracts; that is an RA-owned primitive change, out of scope here.)*

### 5.5 Why a nested RA-owned `SubjectContext` (not a flattened v2) (F9)

A simpler alternative is to flatten the neutral facts directly onto `risk-subject-evaluation-request-2`. The nested, separately-schema'd `SubjectContext` is preferred because it is:
- a **reusable neutral boundary** — a subject-facts contract other domains can populate without inventing per-domain request fields;
- a **separately versioned, closed schema** — subject-fact evolution (`risk-subject-context-1 → -2`) is independent of request-routing evolution;
- **independently digestible** — `context_digest` is a stable, self-contained identity, reusable across future domains **without an arbitrary attribute map**;
- a clean **separation of concerns** — subject facts (context) are distinct from request routing (tenant, purpose/domain) and from admitted-evidence references, each with one authoritative home.

This is consistent with existing RA precedent: `Scope` is already a nested, closed, canonically-embedded contract inside `SubjectRiskEvaluationRequest`, and every neutral RA contract carries its own `schema_version` and digest. **Cost, acknowledged:** one additional schema and one additional digest boundary to define, version, and validate. That cost is accepted; in return, **every fact has a single source-of-truth object** — neutral facts in `SubjectContext`, tenant identity, subject identity and evidence references on the outer request. The context appears at two *layers* (raw + `context_digest` via `subject_digest`) as a deliberate layered commitment RA reconciles before policy resolution (§5.3); the binding anchors (tenant, subject id) are **derived** from the outer request, not independent copies. There is no independent duplicate representation of tenant, subject identity, or evidence references to disagree.

### 5.6 Policy-resolver access (design)

`risk-subject-evaluation-request-2` adds an **optional** `subject_context: Optional[SubjectContext]`. `PolicyResolverPort` gains a **backward-compatible** widening so the resolver may inspect `subject_context` (e.g., an added keyword `subject_context: Optional[SubjectContext] = None`, or a `resolve` successor); v1 resolvers that ignore it keep working. This is an additive, versioned RA-side change (§16) — **not implemented in this PR**.

## 6. Required subject and scope dimensions

**Required (fail closed if missing):** outer `tenant_id`; outer `subject_id` (`workload_id`); `recommendation_id`; `recommendation_time`; `validity_seconds`; the selected plan's `action_kind`; at least one `ResourceChange` with `current_capacity` / `proposed_capacity`; and `forecast_evidence_digest` (outer `evidence_references`). **Where they live:** neutral subject facts (`environment`, `region`, `zone`, `compute_group`, `resource_class`, `action_type`, `magnitude_before/after`, validity window) in `SubjectContext`; tenant identity, **subject identity**, and evidence references on the **outer request** (their sole authoritative source). **Missing is distinct from named** — an absent optional (e.g. `environment`) is the explicit sentinel `null` inside `SubjectContext` (never omitted, never coerced to `""`), so `context_digest` (and thus `subject_digest`) differs between "no environment" and "environment = ''".

## 7. Recommendation and evidence digest binding

- `subject_digest = digest(SubjectBinding)`, and `SubjectBinding` carries `recommendation_digest = rec.digest()` and `context_digest`. The evidence digests (forecast / cost / topology / state) live in the **outer** `evidence_references`, bound by `request_digest`. **Any change to the recommendation digest, any neutral subject fact, or any evidence reference changes `subject_digest` or `request_digest`** (acceptance invariant); each fact has a single source-of-truth object, so a change is reflected deterministically.
- The adapter independently recomputes `rec.digest()` from the reconstructed recommendation and requires equality with the value placed in `SubjectBinding` before projecting → a **recommendation-digest mismatch fails closed**, no seam call. Independently, **Risk Authority recomputes `context_digest` from the supplied raw `subject_context`, reconstructs `SubjectBinding`, and recomputes `subject_digest`, requiring equality with the carried `subject_digest` before policy resolution** (§5.3); any mismatch is a fail-closed non-decision (§12).

## 8. Policy-resolution request semantics

The adapter **never selects policy**. It calls `seam.evaluate(request)`; the seam calls the trusted `PolicyResolverPort.resolve(tenant_id, purpose, domain, risk_class, requested_scope, now)`. If no authoritative policy exists → `NOT_EVALUATED(NO_AUTHORITATIVE_POLICY)`; if multiple claim authority → ambiguity → fail closed. The resolver is production-authoritative (`is_production_authoritative = True`) or the production seam refuses to construct.

> **Why v1 is insufficient, and how v2 resolves it.** In `risk-subject-evaluation-request-1`, `PolicyResolverPort.resolve(...)` receives only `(tenant, purpose, domain, risk_class, requested_scope, now)`. The neutral subject facts #4–#11 (environment, cluster, region, resource/capacity class, action type, current/target capacity, recommendation timestamp, validity window) could be bound losslessly inside `subject_digest` **but would not be individually visible to the resolver**, so scaling-risk policy cannot *route* on them unless they are stuffed into `requested_scope` — which this design **refuses** ("do not silently overload unrelated fields"). **Digest-only anchoring (D-1) is therefore rejected.** The ratified resolution (**D-2**) is the strict RA-owned **v2 `SubjectContext`** (§5.2), which the resolver reads directly on `risk-subject-evaluation-request-2` (§5.6). The adapter populates the context; it never selects policy.

## 9. Evidence-reference semantics

The projection carries only **opaque evidence references** (digest strings) in `evidence_references`. It never carries evidence bodies, control results, or a `PASS`/`FAIL` claim. RA-5's `TrustedControlEvidenceResolverPort` resolves those references to candidate records, which then pass the *existing* `EvidenceAdmissionPort` → `ControlAssurancePort` gates. Absent/failed resolution ⇒ required controls resolve to `MISSING` ⇒ the non-compensatory gate fails closed to `DENY`/`ESCALATE`. **The adapter cannot promote evidence to trusted status.**

## 10. Time and validity semantics

- All timestamps canonical RFC3339 UTC at `%Y-%m-%dT%H:%M:%S.%fZ`.
- The recommendation is already temporally self-consistent (its `__post_init__` enforces `forecast_cutoff ≤ recommendation_time`, `forecast_for == cutoff + horizon`, validity ≤ forecast horizon, non-future state/topology/cost).
- The adapter additionally re-checks the **recommendation validity window** `[recommendation_time, recommendation_time + validity_seconds]` against `now`: an **expired** recommendation (or one whose validity extends beyond forecast validity) yields a typed non-evaluation and **never reaches** risk evaluation.
- The recommendation timestamp and validity window live in `SubjectContext` (`subject_asserted_at` / `subject_valid_from` / `subject_valid_until`) — risk-relevant, digest-bound.

**Evaluation-time authority (F6):**
- The Phase-4 adapter **must never populate a caller-controlled `evaluation_time`**; it leaves the request's `evaluation_time = None`.
- **Production** evaluation uses **Risk Authority's injected trusted clock** as the sole evaluation-time authority.
- The future v2 trusted production path **must reject (fail closed) any caller-supplied evaluation time** — a non-`None` `evaluation_time` on a trusted production request is a fail-closed non-decision (`NOT_EVALUATED`, §12), never silently ignored and never a source of authority. **Trusted production time comes only from Risk Authority's injected clock.**
- **Reference/test-mode** time injection is the **only** place an explicit clock may be supplied, and it is **explicitly separated** from production authority (the labelled reference seam only) — it can never be produced by the production factory, exactly as the merged v1 seam already separates reference from production. **No v1 code is changed by this PR.**

## 11. Typed abstention and fail-closed behavior

Per **D-5**, a `RecommendationAbstention` input ⇒ the adapter **does not project it and does not call the seam**; it returns a typed `PROJECTION_ABSTAINED_UPSTREAM` outcome (proposed) carrying the abstention's subject + reason + available input digests. An abstention **must never enter risk evaluation as a recommendation**, and a controller abstention **never becomes a risk approval**. Every non-nominal case (§12) is fail-closed and typed; none returns an ALLOW-family disposition.

## 12. Risk-decision output semantics & failure behavior

The adapter returns the seam's `SubjectRiskDecision` unchanged (or, for pre-seam failures, a typed adapter outcome). Every case below is **non-executing** and **never falls through to approval**:

Every case below **fails closed** to a typed non-decision (or a deny/escalate) and **may never become `PASS`, `ALLOW`, an authorization envelope, or executable authority**:

| Failure case | Outcome |
|---|---|
| controller abstention | adapter `PROJECTION_ABSTAINED_UPSTREAM` (no seam call) |
| malformed recommendation | `from_dict` `RecommendationError` → fail closed, no seam call |
| **unsupported schema version** (context / binding / request) | fail-closed non-decision (`NOT_EVALUATED(UNSUPPORTED_SCHEMA_VERSION)`) |
| **unknown field** (any of the three canonical objects) | strict `from_dict` rejects → fail closed, no seam call |
| **non-canonical value** (float, exponent/representation-dependent decimal string, non-UTC/mis-formatted timestamp, empty required string, `bool` for an int) | canonicalizer/validator rejects → fail closed, no seam call |
| **layered-commitment mismatch** (RA recompute of `context_digest`/`subject_digest` from the raw `subject_context` ≠ carried `subject_digest`; e.g. altered raw context with a stale digest) | fail-closed non-decision **before policy resolution** (§5.3), no authority |
| **binding-anchor mismatch** (reconstructed `SubjectBinding` from outer `tenant_id`/`subject_id` ≠ carried `subject_digest`) | fail-closed non-decision, no authority |
| recommendation-digest mismatch | adapter re-check fails → fail closed, no seam call |
| expired recommendation / beyond forecast validity | adapter validity re-check → typed non-evaluation (no seam call) |
| missing required scope / ambiguous subject | `SubjectError` / strict projection → fail closed |
| missing applicable / no authoritative policy | seam `NOT_EVALUATED(NO_AUTHORITATIVE_POLICY)` |
| ambiguous / expired policy | seam `NOT_EVALUATED(AMBIGUOUS_POLICY / EXPIRED_POLICY)` |
| missing / untrusted / **stale** / contradictory evidence | RA-5 admission → controls `MISSING`/untrusted/stale → `RISK_DENIED` / `RISK_ESCALATED` (never PASS) |
| **caller-supplied evaluation time on a trusted production path** | **rejected (fail-closed non-decision)** — never ignored; trusted time comes only from RA's injected clock (§10) |
| unavailable Risk Authority / evaluator | seam `NOT_EVALUATED(AUTHORITY_UNAVAILABLE / EVALUATOR_UNAVAILABLE)` |
| reconstruction failure | fail closed, no seam call |

A `RISK_PASSED` / `RISK_PASSED_WITH_CONDITIONS` can arise **only** from RA's non-compensatory gate over admitted, trusted evidence — never from any adapter-side field, and never from any failure case above.

## 13. Non-executable invariants

Every `SubjectRiskDecision` returned has `authorization_performed = envelope_issued = actiongate_invoked = actuation_performed = effect_verified = executable = False` (fixed by the RA contract's `__post_init__`). `RISK_PASSED` is **not** ActionGate authorization and carries no executable capability. The adapter never touches `issue_envelope` / `authorize_action`; the production seam structurally cannot reach them (PR-1 containment).

## 14. Serialization and reconstruction requirements

For `SubjectContext`, `SubjectBinding`, `SubjectRiskEvaluationRequest_v2` and any adapter outcome type: strict constructor / `from_dict` parity; unknown fields rejected; mandatory `schema_version`; canonical JSON; deterministic `sha256:` digest; **no floats** and no exponent/representation-dependent decimal strings; canonical RFC3339 UTC timestamps; nested digest re-validation on reconstruction; exact tenant/subject/scope binding; frozen/immutable records; round-trip digest stability; explicit authority flags fixed `False`. On every reconstruction, and — for a production request — **before policy resolution** (§5.3), RA recomputes `context_digest` from the raw `subject_context`, reconstructs `SubjectBinding` from the outer request's identity fields, recomputes `subject_digest`, and rejects any mismatch (fail-closed).

**Curated-object rule (F3).** The adapter **must build a curated neutral object** containing only the approved `SubjectContext` fields, populated field-by-field, and hand *that* to the RA canonicalizer. It **must never pass the controller's raw `to_canonical_dict()`** (or any other controller-serialized blob) into the RA canonicalizer — doing so would import unapproved fields and float-valued analytics and break domain neutrality and float-rejection. The controller's serialization is used **only** to establish the source `recommendation_digest` (§5.4).

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
  - New `SubjectContext` (schema `risk-subject-context-1`), new `SubjectBinding` (schema `risk-subject-binding-1`), and new request schema `risk-subject-evaluation-request-2` with an **optional** `subject_context` field — three schema-tagged digests (§5.4).
  - **v1 preserved:** `risk-subject-evaluation-request-1` requests remain valid and continue to validate/round-trip unchanged; a v2 request with `subject_context = None` is behaviorally equivalent to v1. `SUPPORTED_REQUEST_SCHEMA_VERSIONS` becomes `{…-1, …-2}`.
  - `PolicyResolverPort` widening is additive (optional keyword / successor method) so existing resolvers keep working — a **bounded, documented migration**, not a breaking change.
  - Requires a **versioned `ugence-risk-authority` minor bump** (e.g. `0.2.0 → 0.3.0`) owned by Risk Authority; **not implemented in this PR**.
- Frozen identifiers/schemas/digests are not changed without a versioned migration; the v1 contract's frozen digest behavior is untouched.

## 17. Test and acceptance matrix (for the implementation phase, when authorized)

**Negative/adversarial tests ≥ 2× happy-path.** Independent tests for: caller-supplied `PASS` has no path; forged / duck-typed recommendation; recommendation-digest mismatch; **layered-commitment mismatch** (RA recompute of `context_digest`/`subject_digest` from the raw `subject_context` ≠ carried `subject_digest` — e.g. **altered raw context with a stale digest fails before policy resolution**, §5.3 tamper fixture); **binding-anchor mismatch** (reconstructed binding from outer `tenant_id`/`subject_id` ≠ carried `subject_digest`); **schema-tag substitution** (a `context_digest` presented in a `subject_digest` slot, or a cross-schema digest reuse) is rejected; missing tenant / subject; cross-tenant & cross-scope reuse; missing-vs-named optional (`None` ≠ `""`/`0` yields distinct digests); **non-canonical value** rejection (float, exponent/representation-dependent decimal string, mis-formatted/non-UTC timestamp, `bool`-for-int); stale / future / expired recommendation; validity beyond forecast horizon; unsupported schema; unknown fields (each of the three canonical objects); **caller-supplied `evaluation_time` on a trusted production path rejected (fail-closed)**; contradictory / missing / untrusted / stale evidence (→ deny/escalate, never pass); no authoritative / ambiguous policy; unavailable Risk Authority; reconstruction failure; direct-construction-vs-`from_dict`; **worked-example digest reproducibility** (§5.3 fixtures); installed-wheel behavior; and **sentinel tests** proving envelope issuance, ActionGate, and provider execution are never invoked and every executable flag stays `False`. Happy path: a valid recommendation over admitted trusted evidence yields a non-executable `RISK_PASSED` and nothing more.

## 18. Relationship to RA-5

Phase 4 is a **consumer** of the RA-5 boundary, not a re-implementation of it. The projection supplies only *subject facts + opaque evidence references*; RA-5 (`EvidenceAdmissionPort` / `ControlAssurancePort` / `TrustedEvidenceIngressPort`, merged in `ugence-risk-authority-evidence-runtime 0.1.0`) performs trusted admission and non-compensatory control assurance. The RA-5 invariant — *a caller-asserted `PASS` cannot mint authority* — is preserved because the adapter has no channel to assert one. Phase 4 depends on RA-5 being merged and verified (it is).

## 19. Explicit Phase 5 and Phase 6 exclusions

Phase 4 performs **no** envelope issuance, **no** ActionGate authorization, **no** provider/cloud execution or actuation (Phase 5), and **no** effect verification or recommendation learning (Phase 6). These remain fail-closed and are not implemented, imported, or wired by this design.

## 20. Owner decisions — recorded 2026-08-13; audit corrections incorporated; pending final ratification (implementation gated)

- **D-1 — Digest-only projection-anchoring: REJECTED.** Carrying the scaling facts only inside `subject_digest` cannot expose environment/cluster/region/resource-class/action-type/current-target-capacity/validity to `PolicyResolverPort`, so scaling-risk policy could not route on risk-relevant facts. Rejected in favor of D-2.
- **D-2 — Strict, versioned, RA-owned v2 neutral subject-context: APPROVED (with constraints; audit-corrected).** Adopt the strict `SubjectContext` contract in §5.2 — **not** an unrestricted generic `subject_attributes` map. It must: remain domain-neutral at the RA boundary; use explicit canonical types and validation; reject unknown/non-canonical fields; distinguish missing from named values; be bound through the **single authoritative digest chain** (§5.3) — `context_digest → SubjectBinding → subject_digest → request_digest`, each fact with a single source-of-truth object, the raw context carried as a **layered commitment RA recomputes and reconciles before policy resolution** (never an independent second source); prevent cross-tenant, cross-subject and cross-scope replay; expose no caller-selected policy and no caller-authored control status; contain no key/decision/envelope/authorization/execution instruction; remain non-executable; require a versioned Risk Authority contract change; preserve v1 backward compatibility as a bounded migration (§16); and be **owned by Risk Authority, not Cloud Scaling**. **Audit corrections incorporated (second-round):** `tenant_id`, `subject_id` and `evidence_references` are **not carried in `SubjectContext`** — identity and evidence references are authoritative on the outer request, with binding anchors **derived** and RA-recomputed before policy resolution (§5.1, §5.3, F1/F2); the RA digest is described honestly as **schema-tagged canonical hashing** over a bare SHA-256 primitive (§5.4, F4/F5); caller-supplied `evaluation_time` on a trusted production path is **fail-closed rejected** (§10, F6); the nested-context choice is justified against a flattened v2 (§5.5, F9). The adapter may populate the context but may not define authority or select policy. **Not implemented in this PR.**
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
- **One authoritative digest chain** (§5.3): each fact has a single source-of-truth object; the raw `subject_context` is a **layered commitment** RA recomputes (`context_digest`, then `SubjectBinding` → `subject_digest`) and reconciles against the carried `subject_digest` **before policy resolution**; any mismatch — including altered raw context with a stale digest — fails closed before the resolver reads a fact. Each of `risk-subject-context-1` / `risk-subject-binding-1` / `risk-subject-evaluation-request-2` is **schema-tagged**; a digest under one tag must not be accepted in another's slot (enforced by `schema_version` + validation, not by the bare SHA-256 primitive).
- `subject_id` and `tenant_id` are authoritative on the **outer request only**; `SubjectContext` carries neither. `SubjectBinding.tenant_id` / `SubjectBinding.subject_id` are **derived** from the outer request and RA-recomputed — no independent third copy exists to disagree.
- Caller-supplied `evaluation_time` on a trusted production path is **fail-closed rejected**; trusted production time comes only from RA's injected clock.
- Adapter **never** passes the controller's raw `to_canonical_dict()` to the RA canonicalizer; it builds a curated neutral object.
- Cross-tenant and cross-scope reuse **fails closed**; missing scope ≠ named scope; missing optional (`None`) ≠ named value.
- Expired or invalid recommendations **cannot reach** risk evaluation; controller abstentions **never become** risk approvals.
- `RISK_PASSED` remains **non-executable**; every `executable / envelope / actiongate / actuation / effect` flag remains `False`.
- **No** envelope issuance, **no** ActionGate invocation, **no** provider execution, **no** effect verification.
- Negative tests are **≥ 2×** happy-path tests when implementation begins.

## Consequences

- Cloud Scaling gains a safe, auditable, non-executing risk-decision path; the controller stays an advisory leaf.
- The v1 limitation (§8) is resolved by a strict, RA-owned, versioned **v2 subject-context** (§5.2) rather than papered over by overloading `Scope` — the facts policy resolution needs become first-class and canonically typed, while the RA boundary stays domain-neutral and non-authoritative.
- No runtime adapter, package, v2 RA contract, or Phase 5/6 behavior is created by this ADR. Implementation is gated on: RA-5 merged & verified (done), this ADR ratified, the v2 subject-context contract approved and versioned by Risk Authority, and D-4's final identifiers ratified in review.
