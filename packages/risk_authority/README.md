# Ugence Risk Authority (`ugence-risk-authority`)

Executable governance authority kernel. This independently packaged module turns
an **approved governance decision** into **cryptographically bound, scoped,
time-bound, revocable runtime authority**, and enforces that authority at the
exact point of action.

> Your GRC system tells you what your AI policy is. Ugence makes it executable.

This distribution implements the **RA-1 → RA-4** vertical slice of the Ugence
Risk Authority Architecture Specification (v1.1) — the authority *spine*:

```
WorkflowIR
   ↓
RiskDecisionCase
   ↓
ControlResult            (non-compensatory)
   ↓
Decision Authority       (delegation-monotone)
   ↓
Signed RiskAuthorizationEnvelope   (Ed25519, scope ⊆ decision)
   ↓
Canonical Action         (deterministic digest)
   ↓
ActionGate               (bounded, offline, no LLM)
   ↓
ALLOW / DENY
```

TAP + Control Assurance, revocation/epoch propagation, Context Minimization,
Third-Party Gateway, Trajectory Control, ACP and Reconciliation (RA-5 → RA-8)
are defined here **as contracts** and layer onto this spine incrementally. The
package integrates existing governance components (ActionGate, TAP, PWC) through
the ports in `risk_authority.integrations` and never imports their
application-specific policy logic.

**Reference implementations vs. canonical kernels.** To stay a stdlib-only leaf
this slice ships *reference* implementations behind ports rather than importing
the shipped Ugence packages: `ReferenceActionGate` behind `ActionGatePort`, and
`ReferenceDecisionAuthority` behind `DecisionAuthorityPort`. The **canonical
production binding-decision authority is the separately shipped
`ugence-decision-authority` kernel** (`packages/capabilities/decision-authority`),
and exact-action enforcement is owned by `ugence-actiongate-provider`. A
production deployment adapts those kernels onto the ports here — through the
contract, without `risk_authority` importing them. The in-package
`ReferenceDecisionAuthority` is a proving stand-in and must not be mistaken for
the canonical kernel.

## Design invariants (enforced + tested)

| Invariant | Where | Test |
|---|---|---|
| **Fail closed** — UNKNOWN / MISSING / STALE never become approval | `domain.controls`, `services.risk_engine` | `unit/test_scope_and_controls.py`, `adversarial/test_deny_matrix.py` |
| **Non-compensatory** — no PASS compensates a FAIL/STALE | `domain.controls.required_controls_satisfied` | `unit/test_scope_and_controls.py` |
| **Delegation monotonicity** — `IssuedAuthority ⊆ DelegatedAuthority` | `domain.authority`, `services.decision_authority` | `contract/test_authority_delegation.py` |
| **Envelope monotonicity** — `Scope_envelope ⊆ Scope_decision` | `services.envelope_issuer.validate_envelope_subset` | `contract/test_envelope_monotonicity.py` |
| **Policy immutability** — decisions bind an exact WorkflowIR digest | `domain.workflow_ir`, `domain.decision` | `contract/test_serialization_determinism.py` |
| **Payload binding** — executed action digest == authorized digest | `domain.actions` | `adversarial/test_deny_matrix.py` |
| **Time binding** — expired envelope/decision cannot execute | `services.envelope_verifier` | `integration/test_phase1_exit.py` |
| **Revocability** — epoch advance / targeted revoke invalidates authority | `services.revocation` | `adversarial/test_deny_matrix.py` |
| **Tenant isolation** — no cross-tenant resolution | `persistence.in_memory` (keys are `(tenant, id)`) | `adversarial/test_deny_matrix.py` |
| **Determinism** — one canonical serialization for every digest/signature | `crypto.canonical` | `unit/test_canonical_and_hashing.py` |

## Package layout

```
src/risk_authority/
  domain/         immutable typed artifacts + the RiskDecisionCase state machine
  services/       risk engine, reference decision authority (+ port), envelope issuer/verifier, revocation
  crypto/         canonical serialization, sha-256 hashing, pure-Python Ed25519, key ring
  integrations/   ActionGate / TAP / PWC ports (+ reference ActionGate matching engine)
  persistence/    repository contracts, in-memory reference, Postgres skeleton + DDL
  api/            transport-neutral schemas, application facade, optional FastAPI routes
  observability/  governance-event bus, metrics
tests/            unit · contract · integration · adversarial
```

## Quick start

```python
from datetime import datetime, timezone
from risk_authority.api import (RiskAuthorityApplication, CreateCaseRequest,
    EvaluateRequest, ControlResultInput, DecisionRequest, IssueEnvelopeRequest,
    AuthorizeActionRequest)
# ...build an ACTIVE WorkflowIR, an AuthorityGrant and a signing key, then:
# create_case -> evaluate -> issue_decision -> issue_envelope -> authorize_action
```

See `tests/scenario.py` for the complete finance refund-review example and
`tests/integration/test_phase1_exit.py` for the architecture acceptance table.

## Why pure-Python Ed25519?

To keep this a **stdlib-only leaf** — the conformance suite installs the single
wheel into a clean `--no-index` venv with zero third-party packages, exactly
like the other Ugence governance leaves. `crypto.signing` is a correct RFC 8032
reference (validated against the RFC test vectors); production issuance/verification
should be backed by a vetted library and an HSM/KMS. The `SigningKey` / `VerifyKey`
surface is shaped so that backend can be swapped without touching callers.

## Non-executing evaluation seam (v0.2.0)

`RiskEvaluationSeam` (`risk_authority.api`) lets an external domain integration obtain a
canonical risk outcome for a neutral `SubjectRiskEvaluationRequest` and **stop at the risk
decision** — it never issues an envelope or invokes ActionGate. The request carries only
subject facts + correlation context; policy, controls, keys, evaluator identity, clock and
revocation come from the trusted composition root. `RiskEvaluationSeam.production(...)` fails
closed on any reference-grade or missing dependency; `RiskEvaluationSeam.reference(...)` is a
labelled conformance seam. A `RISK_PASSED` result is *not* authorization
(`executable = authorization_performed = envelope_issued = False`). See
[`docs/architecture/RISK_AUTHORITY_EVALUATION_SEAM.md`](../../../docs/architecture/RISK_AUTHORITY_EVALUATION_SEAM.md).

**Production containment (defect (h)).** In `production_mode=True`, `RiskAuthorityApplication`
now **requires** an explicit production-authoritative `decision_authority` — `None` and the
in-package reference ruler both **fail closed at construction** (no reference fallback in
production). `issue_envelope` and `authorize_action` also **fail closed in production** with a
typed `ProductionContainmentError`: envelope issuance and production ActionGate authorization are
**Phase 5** and are not implemented — production Risk Authority integration stops at a
non-executable `RiskDecision`. Reference/conformance mode (`production_mode=False`) retains the
full flow. This is a breaking production-construction change; see the ADR's migration note.

## Neutral v2 subject-context contracts (v0.3.0)

An **additive, versioned** contract layer (`risk_authority.integrations`) that makes the
Phase-4 ADR's neutral subject facts expressible and integrity-bound **without adding any
execution authority**. Three frozen, closed, schema-tagged objects plus one pure validator:

| Object | Schema tag | Carries |
|---|---|---|
| `SubjectContext` | `risk-subject-context-1` | neutral subject facts only — environment, region, zone, compute group, resource class, action type, magnitude before/after, asserted-at and validity window. **No** tenant id, subject id, evidence references, policy, control status, keys, envelopes or execution instructions. |
| `SubjectBinding` | `risk-subject-binding-1` | binding anchors only — tenant, subject id/type (**derived** from the outer request), `recommendation_digest`, `context_digest`. |
| `SubjectRiskEvaluationRequestV2` | `risk-subject-evaluation-request-2` | the v1 outer request plus the raw inspectable `subject_context` and an explicit outer `recommendation_digest`. |

`validate_subject_binding(request)` is a **pure, deterministic, fail-closed** function: it
re-validates the closed context, recomputes `context_digest` from the **raw** context,
reconstructs `SubjectBinding` **exclusively** from authoritative outer request fields,
recomputes `subject_digest`, and requires equality with the carried commitment. An altered
raw context paired with a stale `subject_digest` fails deterministically. It resolves no
policy, evaluates no risk, issues no envelope, calls no ActionGate, mints no credential and
performs no execution — its `SubjectBindingValidation` result is an integrity finding whose
every authority flag is fixed `False`.

### Exact security guarantee — integrity, not authenticity

`validate_subject_binding` proves **internal canonical consistency** between the supplied
context, the outer binding fields and the carried digests. It does **not** prove that those
caller-supplied facts or `recommendation_digest` originate from an authentic Cloud Scaling
recommendation. Source authenticity must be established by the future Cloud Scaling adapter,
by reconstructing the actual `CapacityActionRecommendation`, recomputing `rec.digest()` and
requiring equality **before** the request may enter trusted evaluation. RA-5 and the
evaluation seam provide their own, separate evidence-admission and tenant/scope checks.

It detects **inconsistent or partial tampering** — an altered field left paired with a stale
digest. It does **not** detect a *fully self-consistent fabricated request*: a caller who
recomputes `context_digest`, `subject_digest` and `request_digest` produces an internally
consistent object by construction, and the structural validator accepts it (this is asserted
by an explicit test). This layer therefore does **not** provide recommendation authenticity,
provenance verification, cross-tenant authorization, trusted evidence admission, or replay
prevention against a caller capable of recomputing every digest.

### Ordering — what exists where, as of v0.4.0

| # | Step | Where |
|---|---|---|
| 1 | reconstruct the real `CapacityActionRecommendation` | Cloud Scaling adapter — **not built** |
| 2 | independently recompute `rec.digest()` | Cloud Scaling adapter — **not built** |
| 3 | require equality with the outer `recommendation_digest` | Cloud Scaling adapter — **not built** |
| 4 | run `validate_subject_binding` | Phase 4A contract layer, **wired into the seam** in Phase 4B |
| 5 | subject-aware policy resolution over the validated context | Phase 4B seam |
| 6 | trusted evidence (RA-5) + the existing RA evaluation path | Phase 4B seam |
| 7 | widen `SUPPORTED_REQUEST_SCHEMA_VERSIONS` to admit v2 | Phase 4B, same atomic change as step 4 |

**Steps 1–3 remain absent.** No placeholder authenticator and no permissive resolver was
introduced — an absent check stays visibly absent. Admitting a v2 request therefore still
does **not** establish that a recommendation is authentic.

**Schema-tagged canonical hashing (honest description).** Digests use the existing
`crypto.canonical.to_canonical_obj` / `canonical_bytes` and `crypto.hashing.digest` — a
**bare SHA-256** over canonical bytes. No new hashing primitive and no cryptographic domain
prefix are introduced. Separation between the three digests comes from each object embedding
its own fixed `schema_version` inside its own canonical form, **plus** strict validation:
a digest under one schema tag is never automatically accepted in another semantic slot.

**Backward compatibility.** `risk-subject-evaluation-request-1` is untouched and remains
byte-for-byte compatible: v1 construction, `to_dict`, `from_dict` and digests are unchanged,
v1 requests acquire **no** serialized `subject_context` or `recommendation_digest` field, and
no automatic v1↔v2 conversion exists (v2 is a successor class, not a subclass).

**Timestamp handling (deliberate v2 hardening).** The v2 contract layer requires explicit
tz-aware UTC and rejects both naive datetimes and non-zero offsets, rather than normalizing
them the way `crypto.canonical` and the v1 `evaluation_time` path do. This is an approved
v2-only hardening: **v1 behavior is unchanged**, so the same field is handled leniently on
v1 and strictly on v2 by design.

> **ADR correction, owner-approved and applied.** ADR §5.3 requires Risk Authority to
> reconstruct `SubjectBinding` from `{outer tenant_id, outer subject_id, subject_type,
> recommendation_digest, recomputed context_digest}` before policy resolution, but the
> originally merged ADR's illustrated v2 request carried no `recommendation_digest`: the
> value's only home there was *inside* `SubjectBinding`, it was absent from
> `evidence_references`, and it cannot be recovered from `subject_digest` or
> `idempotency_key` (both one-way SHA-256 outputs). RA-side reconstruction was therefore
> impossible as illustrated. The explicit outer `recommendation_digest` field on v2 is the
> narrowest versioned correction, and the ADR has been amended to match (see its
> "Amendment 1" note). The corrected §5.3 worked request digest is
> `sha256:cd6dc88a…`, which supersedes the obsolete `sha256:b1973925…` **for the v2 worked
> request only**. The `context_digest` (`sha256:9af3f626…`), `subject_digest`
> (`sha256:eb4526a6…`) and tamper-demonstration fixtures are unchanged and still reproduce
> byte-for-byte. All four, plus the corrected request digest, are pinned as test fixtures
> and re-asserted from the installed wheel.

## Validated v2 seam admission (v0.4.0)

Phase 4B activates the v2 contract at `RiskEvaluationSeam` — **behind** mandatory binding
validation and subject-aware policy resolution. It remains non-executing, and it does **not**
establish that a Cloud Scaling recommendation is authentic.

### Load-bearing order (production v2)

`RiskEvaluationSeam.evaluate` dispatches on the real request type and, for a v2 request,
clears these gates in exactly this order before anything downstream exists:

1. confirm the canonical v2 contract type (structural — not a schema string, not duck typing);
2. confirm the v2 schema identifier is supported **for that request class**;
3. reject a caller-supplied `evaluation_time` on the trusted production path;
4. validate the closed `SubjectContext`;
5. recompute `context_digest`;
6. reconstruct `SubjectBinding` from the authoritative **outer** request fields;
7. recompute `subject_digest`;
8. require every carried/recomputed binding to match;
9. only then invoke **subject-aware** policy resolution;
10. only then invoke trusted evidence resolution and the remaining existing RA path.

No policy resolver, evidence resolver, clock-dependent evaluation or Decision Authority
operation observes an unvalidated v2 context. This is proven with counting spies that assert
an **empty** downstream call log on every rejection path, not by reading the source.

### Subject-aware resolver boundary

v2 requires an explicit successor port, `SubjectAwarePolicyResolverPort`:

```python
class MyResolver:
    is_production_authoritative = True
    is_subject_context_aware = True          # declared capability

    def resolve_with_subject_context(self, *, tenant_id, purpose, domain, risk_class,
                                     requested_scope, subject_context,
                                     evidence_references, now): ...
```

* **v1 is untouched** — it keeps using `PolicyResolverPort.resolve(...)`, so every existing
  resolver keeps working. A subject-aware resolver may implement both and serve both.
* **v2 requires the successor method** — `is_subject_aware_policy_resolver()` requires *both*
  the declared flag *and* the method to exist. Neither alone is enough.
* **No v2 fallback** to a v1-only resolver: a v2 request against one fails closed with
  `NOT_EVALUATED(NO_AUTHORITATIVE_POLICY)` and reason code `resolver:not_subject_context_aware`.
* **No introspection.** Capability is declared, never inferred — no signature inspection, no
  permissive `**kwargs` probe. This is why a successor *method* was chosen over an added
  keyword (ADR §5.6 left both open): a resolver accepting `**kwargs` would have silently
  accepted a v2 request while dropping the subject context entirely.
* Reference components stay visibly non-authoritative: `ReferenceSubjectAwarePolicyResolver`
  is `is_production_authoritative = False` and is refused by `RiskEvaluationSeam.production`.

The resolver receives only **validated neutral** facts — the context object the validator
re-validated and reconciled. Outer authoritative identity, requested scope, trusted evidence,
policy and the risk decision stay distinct: `tenant_id` and `evidence_references` are passed
as their own arguments, `subject_id` is not passed at all, and `SubjectContext` carries no
identity. Risk Authority imports no Cloud Scaling type and hardcodes no cloud-scaling enum.

### Evaluation-time authority

| Path | Caller-supplied `evaluation_time` |
|---|---|
| v1 (any mode) | honored, exactly as before — **unchanged** |
| v2, labelled reference seam | honored (ADR §10: the only place an explicit clock may be injected) |
| **v2, trusted production seam** | **rejected fail-closed**: `NOT_EVALUATED(CALLER_SUPPLIED_EVALUATION_TIME)` |

It is never silently ignored and never becomes the authoritative clock. The rejection record
is stamped with the **trusted** clock, so a caller cannot influence even the timestamp of its
own rejection. Rejection happens at gate 3 — before any policy or evidence resolution.

`CALLER_SUPPLIED_EVALUATION_TIME` is a new, owner-ratified member of
`SubjectRiskNonDecisionReason`. It was minted rather than reused because no existing member
described the condition: the subject is valid and the schema is supported, so reusing
`INVALID_SUBJECT` or `UNSUPPORTED_SCHEMA_VERSION` would have misattributed the rejection in
the audit record. The addition is purely additive — no member was renamed or removed.

### Schema admission and the masquerade rule

`SUPPORTED_REQUEST_SCHEMA_VERSIONS` now declares **both** `…-request-1` and `…-request-2`.
That union is not the admission rule: the seam gates on the **(request class, schema tag)
pair**, so each canonical class admits only its own tag. A **v1-class object carrying the v2
tag** is therefore still refused with `NOT_EVALUATED(UNSUPPORTED_SCHEMA_VERSION)` even though
its tag is now a supported value. Unknown and future tags continue to fail closed the same
typed way, and anything that is neither canonical class still raises `SeamConfigurationError`
at the type boundary.

### What admission does *not* mean

Admitting a v2 request proves **binding integrity**, never source authenticity. A fully
self-consistent, structurally forged v2 request — foreign tenant, someone else's workload, a
`recommendation_digest` corresponding to no recommendation that ever existed — **passes**
binding validation, because every digest can be recomputed by its author. This is asserted
by name in the adversarial suite rather than glossed over.

What still holds for such a request is containment: it terminates at a **non-executable**
`SubjectRiskDecision` with every execution flag structurally `False`, no envelope, no
ActionGate, no credential, no actuation. Establishing authenticity remains the future Cloud
Scaling adapter's responsibility (steps 1–3 above).

### Not in this release

No Cloud Scaling adapter, no execution envelope, no ActionGate call, no provider or
Kubernetes invocation, no credential issuance, no effect verification, and no Phase 5/6
behavior. The ADR's **D-4** purpose/domain identifiers remain **proposed, not owner-ratified**,
so none are frozen into Risk Authority; Phase 4B is entirely domain-neutral and D-4 stays an
explicit blocker for the adapter.

## Verify the distribution

```
python packages/risk_authority/verify_risk_authority_distribution.py
```

## Scope note

RA-1 → RA-4 deliberately **excludes** trajectory control, ACP, reconciliation,
Context Minimization, full PWC ingestion and GRC dashboards. Their contracts are
present; their runtimes are layered after the authority spine is proven
(spec §35 roadmap, user brief §25).

**Known follow-up (documented, not yet closed).** The `Scope` carries authority
dimensions the reference ActionGate does not yet enforce at runtime because the
canonical action model has no corresponding field: `jurisdictions`,
`max_autonomy_level`, and per-resource (`target_id`) constraints. These bound
issuance (they participate in delegation/envelope monotonicity) but are not
matched against a presented action. Closing this requires extending
`CanonicalAction` (a deliberate, separately-reviewed change) and is tracked as a
follow-up rather than done in the authority-spine slice.
