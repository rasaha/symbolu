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
  persistence/    repository contracts (incl. authorizations), in-memory reference, durable SQLite store + codec, Postgres DDL
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
recommendation. Source authenticity is established **outside this package**, by the Cloud
Scaling adapter (`ugence-cloud-scaling-risk-integration`, Phase 4C), which reconstructs the
actual `CapacityActionRecommendation`, recomputes `rec.digest()` and requires equality
**before** the request may enter trusted evaluation. Risk Authority neither performs nor
verifies that check — admitting a v2 request here still proves nothing about source. RA-5
and the evaluation seam provide their own, separate evidence-admission and tenant/scope
checks.

It detects **inconsistent or partial tampering** — an altered field left paired with a stale
digest. It does **not** detect a *fully self-consistent fabricated request*: a caller who
recomputes `context_digest`, `subject_digest` and `request_digest` produces an internally
consistent object by construction, and the structural validator accepts it (this is asserted
by an explicit test). This layer therefore does **not** provide recommendation authenticity,
provenance verification, cross-tenant authorization, trusted evidence admission, or replay
prevention against a caller capable of recomputing every digest.

### Ordering — what exists where

| # | Step | Where |
|---|---|---|
| 1 | reconstruct the real `CapacityActionRecommendation` | Cloud Scaling adapter — **built** (Phase 4C, `ugence-cloud-scaling-risk-integration`) |
| 2 | independently recompute `rec.digest()` | Cloud Scaling adapter — **built** (Phase 4C) |
| 3 | require equality with the outer `recommendation_digest` | Cloud Scaling adapter — **built** (Phase 4C) |
| 4 | run `validate_subject_binding` | Phase 4A contract layer, **wired into the seam** in Phase 4B |
| 5 | subject-aware policy resolution over the validated context | Phase 4B seam |
| 6 | trusted evidence (RA-5) + the existing RA evaluation path | Phase 4B seam |
| 7 | widen `SUPPORTED_REQUEST_SCHEMA_VERSIONS` to admit v2 | Phase 4B, same atomic change as step 4 |

**Steps 1–3 now exist, and they are not in this package.** They are the Cloud Scaling
adapter's `authenticity` module: exact-type admission, strict reconstruction through the
controller's own `from_dict`, an independent `rec.digest()` recomputation, and comparison
against the independently carried `evidence_digest`. No placeholder authenticator was ever
introduced here in the interim — an absent check stayed visibly absent until the real one
was built elsewhere.

**What that does and does not buy — unchanged for Risk Authority.** Steps 1–3 run in the
adapter, on the adapter's inputs, before a request reaches this package. Risk Authority
performs no part of them and cannot tell whether they ran. Admitting a v2 request here
therefore still does **not** establish that a recommendation is authentic. Phase 4C's own
residual limits are stated in its module documentation and are not narrowed by this note:
its digest is an unkeyed content identity, not a signature; on the in-process object path
the provenance of the caller-supplied `expected_recommendation_digest` is assumed rather
than verified; and a fully self-consistent forgery still passes *Phase 4C*.

Producer authenticity — **who** produced a recommendation — is closed separately, by
`ugence-cloud-scaling-producer-attestation` (Phase 5B-0A): a signed, trust-anchored
`ProducerAttestationV2` verified against the Trusted Evidence Authority's key store. It is
not part of this package's path either: Risk Authority never mints, carries or verifies a
producer attestation, and a verified one grants nothing on its own. Policy authenticity
(that the policy a candidate binds is genuine and in force) remains open as Phase 5B-0B.

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

**Superseded at v0.10.0 by issue #1398 item 1, ruling D-B.** This table previously read
"v1 (any mode): honored, exactly as before — **unchanged**". Production v1 and v2 were being
held to different clock-authority rules in the same seam because of the order they were
built, not because a caller-controlled instant is less dangerous on v1 — it can move
validity and authorization on both. The rule below is the current one; the row it replaces is
recorded here rather than deleted, because it was ratified and a reader of the old ADR needs
to find the correction.

| Path | Caller-supplied `evaluation_time` |
|---|---|
| labelled reference seam (v1 **and** v2) | honored — the only place an explicit clock may be injected, and what keeps conformance replay deterministic |
| **trusted production seam (v1 and v2 alike)** | **rejected fail-closed**: `NOT_EVALUATED(CALLER_SUPPLIED_EVALUATION_TIME)` |

It is never silently ignored and never becomes the authoritative clock. The rejection record
is stamped with the **trusted** clock, so a caller cannot influence even the timestamp of its
own rejection. On v2 the rejection happens at gate 3 — before any policy or evidence
resolution; on v1 it happens at dispatch, before the shared evaluation path is entered.
Nothing else about v1 changed.

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

### What `subject_digest` covers (normative)

`subject_digest = digest(SubjectBinding)`, and `SubjectBinding` carries exactly
`{schema_version, tenant_id, subject_id, subject_type, recommendation_digest,
context_digest}`. It therefore
**binds the canonical subject / subject-context identity only**.

It does **not** bind the request's routing fields:

| Field | In `subject_digest`? | In `request_digest`? |
|---|---|---|
| `requested_purpose` | **No** | Yes |
| `requested_domain` | **No** | Yes |
| `requested_risk_class` | **No** | Yes |
| `requested_scope` | **No** | Yes |
| `evidence_references` | **No** | Yes |

Three consequences follow, and none of them may be softened:

* **Substituting one of these routed request fields can leave `subject_digest`
  unchanged** — substituting any single field above yields a byte-identical
  `subject_digest`; only `request_digest` moves.
* Because such a request still reconciles, binding validation passes and the
  subject-aware resolver **routes on the substituted value**.
* **subject-digest equality is not whole-request authenticity** — it is equality of the
  subject identity commitment and nothing wider.

This is not a defect — the routing fields have their own commitment in `request_digest`,
and the seam's tenant/scope checks and RA-5's binding-tuple re-check are the controls that
govern them. It is documented because any statement implying wider coverage would
overstate the guarantee.

**Phase 4B validates structural and binding integrity. Phase 4B does not authenticate a
fully self-consistent request or recommendation.** Neither `subject_digest` nor
`rec.digest()` authenticates the whole request. Recommendation authenticity is an
**adapter responsibility, and it stays one**: reconstruct the real
`CapacityActionRecommendation`, independently recompute `rec.digest()`, and require
equality before the request may enter the trusted evaluation path. That check is now
implemented — in the Cloud Scaling adapter (Phase 4C), never here — so nothing in this
package's behavior changed and nothing in this section is relaxed.

These claims are pinned by executable tests
(`tests/adversarial/test_phase4b_digest_coverage.py`), which substitute each uncovered
field, assert the subject digest does not move, and assert this section keeps saying so.

### What admission does *not* mean

Admitting a v2 request proves **binding integrity**, never source authenticity. A fully
self-consistent, structurally forged v2 request — foreign tenant, someone else's workload, a
`recommendation_digest` corresponding to no recommendation that ever existed — **passes**
binding validation, because every digest can be recomputed by its author. This is asserted
by name in the adversarial suite rather than glossed over.

What still holds for such a request is containment: it terminates at a **non-executable**
`SubjectRiskDecision` with every execution flag structurally `False`, no envelope, no
ActionGate, no credential, no actuation. Establishing authenticity is the Cloud Scaling
adapter's responsibility (steps 1–3 above), and it is discharged there, before a request
reaches this seam — not by anything described in this section.

### Not in Phase 4B

Phase 4B itself added no Cloud Scaling adapter, no execution envelope, no ActionGate call,
no provider or Kubernetes invocation, no credential issuance, no effect verification, and no
Phase 5/6 behavior. Several of those have since landed — envelope issuance in v0.6.0 and
action admission in v0.8.0 (below), and the Cloud Scaling adapter in its own packages — so
read this list as the boundary of the v0.4.0 change, not as the current state of the system.

The ADR's **D-4** purpose/domain identifiers have since been ratified and frozen, in the
Cloud Scaling contracts packages (`PURPOSE_CAPACITY_ACTION`, `CANONICAL_ACTION_TYPES`). The
part that still holds unchanged is the one that matters here: **none of them are frozen into
Risk Authority.** This package hardcodes no cloud-scaling identifier and imports no Cloud
Scaling type; the seam remains entirely domain-neutral.

## Phase 5 envelope issuance seam (v0.6.0)

`EnvelopeIssuanceSeam` (`risk_authority.api`) is the **only** place a Phase 5 envelope is
signed (ADR `docs/architecture/ADR_RISK_AUTHORITY_PHASE5_ENVELOPE_ISSUANCE_RATIFICATION.md`).
It composes what the kernel already owns — the decision repository, `EnvelopeIssuer`,
revocation epochs, the case ledger — around one new obligation: **issuance is conditioned on
injected verification, performed at the seam's own instant, and the envelope commits to what
was verified.**

The act: one clock read (`issued_at`, and `not_before` equals it); the decision found by
tenant and id and re-derived against the caller's `decision_digest`; refusal if it grants no
authority or has expired; the injected `ArtifactVerificationPort` called with that instant as
`as_of`; every required binding kind present, reporting `VERIFIED`, and carrying
`resolved_as_of` equal to the instant (`INSTANT_MISMATCH` otherwise — the ratified 5B-2 rule);
expiry capped at the decision's own; signing through an `EnvelopeSignerPort`; the verified
digests carried as `EnvelopeBindings.artifact_bindings`. Every other path is a typed
`EnvelopeIssuanceRefusal`. `EnvelopeIssuanceOutcome.executable` is a permanently-`False`
property: an envelope is authority, never execution.

| Path | Signer | Verification port | Application |
|---|---|---|---|
| `EnvelopeIssuanceSeam.production(...)` | must declare `is_production_authoritative = True`; `ReferenceEnvelopeSigner` refused | must declare `is_production_authoritative = True` | must be in production mode, standing on the durable store that holds the decision (v0.7.0); before durable persistence this meant the instance that evaluated it (D-5) |
| `EnvelopeIssuanceSeam.reference(...)` | in-memory `ReferenceEnvelopeSigner` over a `SigningKeyRecord` | any | never a production application |

Risk Authority names no domain's artifacts: the composition root declares the binding kinds
it requires, and the cloud-scaling composition package (5B-4) projects its verifiers' outcomes
onto the one word `VERIFIED`. The case-based `issue_envelope` and `authorize_action` stay
contained in production mode; production ActionGate admission is 5C and credentials are 5X.

**Not in this release:** HSM/KMS signer implementations (the port is their seam) and any
`CanonicalAction` mapping for capacity actions. Durable persistence arrived in v0.7.0
(next section), which lifts the same-instance restriction on the row above.

## Durable persistence (v0.7.0)

`ADR_RISK_AUTHORITY_DURABLE_PERSISTENCE_SCOPING.md` ratified five decisions; this release
implements them without adding a dependency (stdlib `sqlite3`).

| Decision | What ships |
|---|---|
| D-1 backend | `persistence.sqlite.SqliteRiskAuthorityStore(path)`: one file, WAL, `BEGIN IMMEDIATE` around every write, a `meta` schema row, and an append-only hash-linked `ledger_events` table with `verify_chain()`. Adapters for all seven repository ports plus `SqliteRevocationState` and `SqliteIdAllocator`. The Postgres skeleton stays as DDL documentation and still raises. |
| D-2 codec | `persistence.codec`: a strict annotation-driven decoder (`decode_dataclass`) over the package's one canonical encoder. Unknown fields, missing required fields and wrong shapes are `PersistenceStorageError`; the domain type's own validation runs on read. The envelope signature is stored beside the canonical body. `RiskDecisionCase.snapshot()` / `from_snapshot()` replay the event list and refuse a broken `prev_digest` chain (`SnapshotIntegrityError`). |
| D-3 identity | Decisions, envelopes, evidence and governance events refuse an existing id (`PersistenceConflictError`); a case re-save must be the same aggregate (identity fields equal, no events lost); grants and control results replace, as their ports specify. Ids come from a durable per-prefix counter, so a restart never re-mints one. |
| D-4 revocation | Epoch advances and revocations are appended rows; `SqliteRevocationState` rebuilds the hot-path predicate on open, so issuance, `verify_envelope` and the RA-6 lifecycle writer share one durable state. |
| D-5 posture | `production_mode=True` refuses any store that has not declared `is_production_authoritative = True`: the in-memory reference stores never do, and a `":memory:"` SQLite database does not either. Pass `persistence=SqliteRiskAuthorityStore("<file>")` to the application or to either `RiskEvaluationSeam` factory. Individual stores may not be mixed beside a bundle. |

```python
store = SqliteRiskAuthorityStore("/var/lib/ugence/risk-authority.sqlite")
app = RiskAuthorityApplication(workflow_source=..., key_record=..., clock=..., persistence=store,
                               evidence_admission=..., control_assurance=..., evidence_ingress=...,
                               decision_authority=..., production_mode=True)
```

The acceptance test (`tests/integration/test_sqlite_persistence.py`) evaluates a decision,
closes the store, reopens it under a fresh application and issues a Phase 5 envelope through
`EnvelopeIssuanceSeam` that verifies; the distribution verifier repeats it from the wheel.
Nothing in `persistence/` reads a clock: records carry their own instants and the ledger
orders by sequence.

**Gaps that survive:** multi-node consistency (single host, one writer at a time), HSM/KMS
custody, and key rotation across restarts (the key ring is built from the one injected key,
so an envelope signed under a rotated key is unverifiable after restart).

## Signing-key validity windows (v0.9.0)

Closes issue #1398 (F-G) item 2. `SigningKeyRecord` had carried `not_before` / `not_after`
since RA-1 and **nothing read them**: `KeyRing.from_records` built `{kid: verify_key}`, so
the window was discarded before any verification path could see it. An expired or
not-yet-valid key could both sign and verify.

| Where | What it does now |
|---|---|
| `KeyRing` | holds `VerificationKeyRecord` (key + window). `from_records` retains the window; a bare `VerifyKey` entry stays unbounded. |
| `KeyRing.resolve_record(kid)` | the verification-side entry point — resolves the key **with** its window. |
| `KeyRing.resolve(kid)` | retained, explicitly **raw and non-validating**: it takes no instant and so cannot enforce a window. No trust decision may use it, and a boundary test pins that nothing in the package does. |
| `EnvelopeVerifier.verify` | refuses an out-of-window key at the injected `now`, **before** checking the signature. |
| `EnvelopeIssuer.issue` | independently refuses to sign outside the window — the issuer is where the key is actually held, so it does not defer to a later check. |
| `WindowedEnvelopeSignerPort` | additive capability letting an external signer declare a window; a signer that declares none is unbounded, so no existing implementation changes. |

**The interval is half-open — `[not_before, not_after)`.** Valid at exactly `not_before`,
invalid at exactly `not_after`, so two adjacent rotation windows are never both live at the
instant they meet. An absent bound is unbounded on that side, which is why every existing
windowless key and signer in the repository behaves exactly as before.

~~**This deliberately differs from the envelope's boundary, and neither should be
"harmonized" into the other.** `RiskAuthorizationEnvelope.is_temporally_valid` is inclusive
at both ends and is **unchanged** by this work: at exactly `expires_at` an envelope is still
valid, while at exactly `not_after` a key is not. An envelope is a *grant* with a separately
ratified boundary; a key is a *credential*. The difference is asserted by an executable test
rather than left to a reader's assumption.~~

> **Superseded at 0.11.0 — the envelope now shares this shape.** The paragraph above is
> struck through rather than deleted so a reader of the older ADR finds the correction
> instead of a silent rewrite. Its reasoning was sound about *overlap* — envelopes are
> never chained, because issuance always sets `not_before` to its own issuance instant,
> so no two envelope windows ever meet — but the absence of overlap never explained why a
> security validity artifact should remain usable at its own stated expiry. Nothing
> downstream would honor it anyway: the credential broker derived a zero-width window and
> refused, and `governance_contracts.Validity` cannot construct `issued_at == expires_at`
> at all. See *Temporal rules by artifact category* below.

## Temporal rules by artifact category — 0.13.0

> **A point-in-time fact may remain valid at its final instant, but it cannot create
> authority that survives beyond that instant.**

**This supersedes the earlier "one temporal rule" claim.** That framing said every
temporal field followed a single half-open rule. It was never true — evidence and control
freshness were always inclusive, and the 0.11.0 text papered over it by listing exceptions.
Worse, that text named `AuthorityGrant` among the exceptions when it is an authorization
gate, and the amendment that followed found ninety minutes of authority reaching past
expired delegations behind exactly that misclassification. There are two categories, and
naming them is what keeps the difference legible.

### 1. Operational validity — half-open `[start, end)`

Artifacts that *authorize action*. Expired at exactly the upper bound.

| Artifact | Window | Where |
|---|---|---|
| signing key | `[not_before, not_after)` | `crypto/keys.py` |
| `RiskAuthorizationEnvelope` | `[not_before, expires_at)` | `domain/envelope.py`, `services/envelope_verifier.py` |
| `AuthorityGrant` | `[.., expires_at)` | `domain/authority.py` |
| `RiskDecision` expiry | `[.., expires_at)` | `services/envelope_issuer.py`, `api/envelope_issuance_seam.py` |
| `ActionAuthorization` expiry | `[.., expires_at)` | copied from the envelope; enforced in the credential broker |
| `CredentialGrant` validity | `[issued_at, expires_at)` | `governance_contracts.Validity` |
| `ExecutionAuthorization` | `[issued_at, expires_at)` | `cloud-scaling-operations` |

### 2. Point-in-time validity — inclusive `[start, end]`

Facts that *report an observation*. Still valid at exactly the upper bound, deliberately,
because an assertion may be true at exactly one instant.

| Fact | Window | Where |
|---|---|---|
| `SubjectContext` assertion | `[subject_valid_from, subject_valid_until]` | `api/evaluation_seam.py` |
| evidence freshness | `[.., valid_until]` | `domain/evidence.py` |
| backing-evidence freshness | `[.., valid_until]` | `domain/binding.py` |
| control-result freshness | `[.., valid_until]` | `domain/controls.py` |

A zero-width `SubjectContext` — `subject_valid_from == subject_valid_until` — is a
**ratified point-in-time contract**, not an accidental exception. It represents a subject
assertion valid at exactly one instant, and `test_context_accepts_equal_validity_bounds`
commits it deliberately.

### 3. Derived authority is capped by the earliest contributing prerequisite

This is what makes category 2 safe. A point-in-time fact may be current at its final
instant, but the authority derived from it may not outlive it.

`RiskDecision.expires_at` is the earliest of `now + ttl`, the active
`AuthorityGrant.expires_at`, and the control freshness horizon — the earliest `valid_until`
among the required controls that were *actually relied upon*, never over unrelated or
rejected results that merely appeared in the request. Evidence bounds are covered
transitively and by construction: `binding._freshness_is_monotonic` refuses any trusted
result outliving its backing evidence, so the control horizon is already no later than the
evidence floor beneath it. Prerequisites are passed as a named mapping, so the refusal can
say which one bound.

**`[G]` `SubjectContext.subject_valid_until` is a ratified member of this cap and is NOT
yet wired.** It works — a mid-window decision correctly capped at the subject bound rather
than the TTL, and a terminal-instant assertion minted nothing — but `expires_at` is inside
`decision_digest`, and every v2-seam decision carries a subject bound, so enabling it moves
**ten frozen digests** across `cloud-scaling-authorization-contracts` and
`cloud-scaling-policy-authenticity`. Those fixtures state their own purpose: *"regression
anchors: if any canonicalization, field set or binding rule moves, these fail rather than
silently re-baselining."* Re-freezing them is an owner decision, so it is reported rather
than taken.

Each hop then inherits: `EnvelopeIssuer.issue` caps the envelope by its decision — at the
service, not only at the seam — and `ActionAuthorization` copies the envelope's expiry.

### 4. No executable decision may have a zero or negative remaining window

A cap landing on `now` authorizes nothing at any instant, so the authority refuses rather
than minting a decision that is already expired. This is precisely how the two categories
meet: a subject assertion evaluated at its terminal instant is still valid (category 2) and
still mints nothing (category 4).

**`[G]` One known misattribution.** That refusal surfaces through the subject seam as
`AUTHORITY_UNAVAILABLE`, which says the evaluator principal is not entitled — wrong.
`EXPIRED_SUBJECT` would be equally wrong, since the subject is *not* expired at that
instant. A new `SubjectRiskNonDecisionReason` member is required; it is deliberately not
invented here, and `test_a_terminal_instant_subject_mints_no_executable_decision` pins the
current behavior so the gap stays visible rather than silently settling.

### Verification

Boundary conformance is behavioral, at `start − ε`, `start`, `end − ε`, `end` and
`end + ε`, with negative controls and per-mutation checks:
`tests/unit/test_temporal_boundaries.py` (envelope, five sites),
`tests/unit/test_authority_horizon.py` (grant, caps, reach), plus one suite per consuming
package. A source-text tripwire is not the normative proof: equivalent correct code can
spell a comparison many ways, so a substring assertion fails on a correct refactor while
passing on any rewrite that keeps the string.

A malformed window (`not_before >= not_after`, or a non-datetime bound) raises
`KeyWindowError` at construction rather than becoming a silently always-invalid key — a
configuration error must not hide behind a plausible-looking refusal. Note that this
release closes item 2 only; #1398's caller-supplied-clock item is separate, and the HSM/KMS
gap above is unchanged — `WindowedEnvelopeSignerPort` is a metadata and validation contract,
not an integration.

## Phase 5C action admission seam (v0.8.0)

`ADR_CLOUD_SCALING_PHASE5C_ACTION_ADMISSION_SCOPING.md` ratified five decisions; this
release implements the Risk Authority half (D-1, D-3, D-4, D-5). The D-2 mapping from a
capacity action to a `CanonicalAction` belongs to the `cloud-scaling-action-admission`
composition package — it is **built**, and it is deliberately not part of this
distribution: keeping the mapping out of Risk Authority is what leaves this package
domain-neutral.

| Decision | What ships |
|---|---|
| D-1 home | `ActionAdmissionSeam` in `risk_authority.api`, beside the issuance seam, is the only production path from an envelope to an `ActionAuthorization`. `authorize_action` stays contained in production mode. |
| D-3 identity | `authorization_id = auth.v1:sha256(tenant_id, envelope_id, action_digest)`, derived, never allocated. A new `AuthorizationRepository` port (in-memory reference; SQLite adapter in the 0.7.0 store, refuse-on-existing unless the stored action digest matches) persists every verdict. Re-admitting the same triple returns the stored verdict with `disposition = REPLAYED` and emits nothing; a stored authorization naming another action is `AUTHORIZATION_CONFLICT`. |
| D-4 posture | The seam reads its clock once, loads the envelope from the store and verifies signature, window, tenant and session binding, revocation and epoch **before** any port runs (`ENVELOPE_NOT_FOUND`, `ENVELOPE_INVALID`). `production(...)` refuses a reference-mode application, `ReferenceActionGate` and any subclass, and a port that has not declared `is_production_authoritative = True`. The port may answer `AUTHORIZED` or `DENIED` only; any other value, a result naming another id, envelope or action, or an exception is recorded as `DENIED`. |
| D-5 containment | `ActionAuthorization.expires_at` is a `datetime` equal to the envelope's; `executable` is a permanently-`False` property; `disposition` is `ADMITTED` or `REPLAYED`. Admission emits `ACTION_AUTHORIZED` or `ACTION_DENIED`. 5X credentials and an execution reservation are still required before anything runs. |

```python
seam = ActionAdmissionSeam.production(app=app, gate=production_gate, clock=clock)
outcome = seam.issue(ActionAdmissionRequest(
    tenant_id=..., envelope_id=..., action=CanonicalAction(...), session_id=...))
outcome.admitted      # True iff the verdict is AUTHORIZED
outcome.replayed      # True iff a stored verdict was returned
outcome.executable    # always False
```

**Not in this distribution:** the `cloud-scaling-action-admission` package (D-2) — since
built, and outside this package by design — plus ACP and trajectory hooks, and the F-D
scope dimensions the reference gate leaves unenforced (still open as issue #1397).

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
