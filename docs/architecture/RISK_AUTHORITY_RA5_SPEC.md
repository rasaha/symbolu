# Risk Authority RA-5 — Canonical Specification (Ratified)

> **Status:** RATIFIED — canonical, in-repo RA-5 specification.
> **Type:** DOCUMENTATION / ARCHITECTURE ONLY. This document changes no
> production code, starts no RA-5 implementation, creates no package, and opens
> no PR.
> **Verdict:** `RA5_PRECONDITIONS_RESOLVED_READY_FOR_IMPLEMENTATION` (§16).
> **Baseline:** default head `143f9f3f` (merge of PR #1402). RA-1→RA-4 (#1396)
> and RA-4.5 (#1402) are merged and treated as stable and closed. RA-5 reopens
> neither the RA-1→RA-4 authority spine nor the RA-4.5 governance-composition
> architecture.

## 0. Status of this document — relationship to the discovery artifacts

This is the **single canonical RA-5 design**. It supersedes the *verdict and
open preconditions* of the two discovery artifacts while preserving their
analysis:

| Document | Role after ratification |
|---|---|
| `RISK_AUTHORITY_RA5_SPEC.md` (this file) | **Canonical.** The ratified RA-5 contract, ownership, and acceptance gate. In any conflict, this file governs. |
| `RISK_AUTHORITY_RA5_TAP_CONTROL_ASSURANCE_PLAN.md` | **Discovery companion (retained).** Long-form rationale and code-location evidence. Its verdict `RA5_READY_WITH_PRECONDITIONS` is superseded by this file's `RA5_PRECONDITIONS_RESOLVED…`; its §22 preconditions are resolved here (§1). |
| `ADR_RISK_AUTHORITY_RA5_EVIDENCE_CONTROL_ASSURANCE.md` | **Decision record (Accepted).** Records the same decisions; status moved from *Proposed/gated* to *Accepted* by this ratification. |

There is no contradiction among the three. Where the plan says "TBD /
precondition", this SPEC records the ratified answer.

Every architectural claim below was re-verified against live code at baseline
`143f9f3f` (not taken from the discovery summary alone); file:line anchors are
cited so a reviewer can confirm each one.

---

## 1. Preconditions — resolution ledger

The discovery verdict was `RA5_READY_WITH_PRECONDITIONS` with five preconditions.
This SPEC resolves each; the anchor column points to where in this document the
binding decision lives.

| # | Precondition (from discovery §22) | Resolution | Anchor |
|---|---|---|---|
| 1 | Ratify a canonical in-repo RA-5 specification | **RESOLVED** — this document is the canonical spec (purpose, MUST/MUST-NOT, inputs/outputs, invariants, acceptance). | §2 |
| 2 | Settle TAP evidence-admission ownership/naming | **RESOLVED** — Outcome **C**: a neutral **Evidence Admission** seam owns admissibility; `ugence-tap-provider` is named a **Control-Assurance evaluator candidate**, not the admission owner; "TAP" remains the conceptual umbrella. | §3 |
| 3 | Define the Control Assurance producer boundary | **RESOLVED** — new `ControlAssurancePort` owned by `risk_authority`; the non-compensatory **aggregation rule stays in RA**; RA-5 supplies only a *trusted producer* of `ControlResult`. | §4 |
| 4 | Define trust-binding fields for admitted evidence and trusted ControlResult | **RESOLVED** — canonical `AdmittedEvidence` (§6) and trusted `ControlResult` (§7) contracts with a required binding tuple and the binding relation (§8). | §6–§8 |
| 5 | Preserve reference/conformance mode and existing RA/RA-4.5 invariants | **RESOLVED** — explicit reference-vs-production mode (§12), RA-4.5 invariants held by construction (§5.4), 97+77 baseline preserved (§14). | §12, §14 |

All five are documentation/decision items; none required or received a
production-code change.

---

## 2. Ratified RA-5 definition

### 2.1 Purpose

> **RA-5 establishes a trusted evidence → trusted control result path upstream
> of Risk Authority authorization.** It replaces today's *caller-asserted*
> control status with an *evidence-derived, intrinsically bound, fail-closed*
> `ControlResult`, produced by (a) admitting raw evidence through a defined
> **evidence-admission authority** (provenance / integrity / freshness /
> context binding) and (b) evaluating admitted evidence against each required
> control through a **Control-Assurance** evaluator — **without Risk Authority
> becoming the evidence authority or the evidence-scoring engine, and without
> minting any new machine authority.**

RA-5 closes the trust gap proven in live code: `api/dependencies.py:213-220`
constructs `ControlResult(status=ControlStatus(c.status), …)` directly from
caller-supplied `EvaluateRequest.control_results`, and walks
`EVIDENCE_PENDING → EVIDENCE_COMPLETE → CONTROL_EVALUATED` with `actor=` labels
(`"control-assurance"` at `dependencies.py:241`) and **no** admission or
evaluation behind them. The `EvidenceAdmissionPort` (`integrations/tap.py`) is
defined but invoked nowhere in `services/` or `api/` (verified). This is correct
for reference/conformance mode; it is unacceptable for production authority.

### 2.2 RA-5 MUST

1. **Prevent arbitrary caller-asserted PASS from becoming trusted control
   satisfaction.** In production mode a caller-supplied status is inert; only an
   evidence-derived trusted `ControlResult` may satisfy a required control.
2. **Admit evidence through a defined evidence-admission authority** — a single
   named owner of "is this evidence admissible?" (§3), behind
   `EvidenceAdmissionPort`.
3. **Evaluate admitted evidence into trusted `ControlResult` artifacts** via a
   Control-Assurance evaluator behind `ControlAssurancePort` (§4).
4. **Intrinsically bind trusted results** to
   `tenant / risk_case / workflow_ir_digest / policy_digest / control_id / time`
   context so a valid artifact from another context fails closed (§8).
5. **Preserve non-compensatory required-control semantics** — the existing
   `required_controls_satisfied` rule (`domain/controls.py:68-109`) governs
   unchanged; no weighting, averaging, coverage-compensation, or majority vote.
6. **Fail closed** on stale, mismatched, malformed, missing, or untrusted
   evidence/results (§9).
7. **Remain upstream of `RiskAuthorizationEnvelope` issuance** — RA-5 changes
   only *whether / what scope* RA issues; the Ed25519-signed envelope stays the
   sole machine-execution authority (`crypto/signing.py`).

### 2.3 RA-5 MUST NOT

- become a second Decision Authority;
- become a downstream ActionGate;
- mint machine execution authority (no new signed/authorization artifact);
- change RA-4.5 veto composition (`FinalAuthority ≤ RiskAuthority`,
  `FinalScope ⊆ RiskAuthorityScope`);
- solve F-D / #1397 (resource/jurisdiction/autonomy enforcement);
- solve F2 / #1403 (`GovernedExecutionDecision` DTO hardening);
- solve RT-1 / #1404 (`CanonicalAction` requirement);
- implement RA-6/RA-7/RA-8 capabilities (continuous assurance, runtime
  revocation of live envelopes, Trajectory Control, ACP, Reconciliation, Context
  Minimization, GRC dashboards).

### 2.4 Inputs / outputs

| | Content |
|---|---|
| **Inputs** | Raw evidence artifacts + provenance metadata (from producers); the required-control set (already resolved by RA from WorkflowIR); the case binding tuple (tenant/case/workflow_ir_digest/policy_digest). |
| **Outputs** | (1) `AdmittedEvidence` records (`EvidenceState.ADMITTED` or a reject state); (2) trusted `ControlResult`s bound to the exact case context; (3) audit events. **No authorization artifact.** |

### 2.5 Acceptance criteria (headline)

RA-5 implementation is accepted iff the production-path adversarial matrix (§13)
passes fail-closed on every row, the caller-forged-PASS path (§13 row 2) cannot
produce authority, and the RA-1→RA-4 (97-test) and RA-4.5 (77-test) baselines
remain green with RA still a stdlib-only leaf.

---

## 3. Ratified decision — Evidence-Admission ownership & TAP naming (precondition 2)

### 3.1 The three "TAP" things (re-verified)

| Artifact | Path | Nature | Verified |
|---|---|---|---|
| `ugence-tap-provider` | `packages/providers/tap/` | **Assertion-support scorer** — a peer of ActionGate. Vocabulary `TapOutcome` = {SUPPORTED, UNSUPPORTED, CONSTRAINED, INDETERMINATE, UNKNOWN} (`core/__init__.py:56-68`); emits an `evidence_coverage` float ratio (`core/__init__.py:151-152`) and a SHA-256 `fingerprint` (hash, not signature). `evaluate()` takes only `AssertionGovernanceRequest` — **no `now`, no first-class tenant/workflow** (`provider.py:79`). | ✅ |
| `truth_assurance_pipeline/` | repo root | Synthetic research corpus; not production. | ✅ |
| RA reference admission | `integrations/tap.py` `EvidenceAdmissionPort` / `ReferenceEvidenceAdmission` | Fail-closed admitter (`ADMITTED` + current); **invoked nowhere** yet. | ✅ |

### 3.2 The decision — Outcome **C** (neutral Evidence Admission seam)

**Ratified:** the question *"Is this evidence admissible based on provenance,
integrity, freshness, tenant/context binding?"* is owned by a **neutral Evidence
Admission seam**, behind the existing `EvidenceAdmissionPort`. "TAP" is retained
as the **broader conceptual umbrella** (Truth/Trust Assurance), not the name of
the admission owner.

Rationale — chosen over the other outcomes after live-code inspection:

- **Rejected A (extend `ugence-tap-provider` to own admission):** its semantics
  are *assertion-support scoring over caller-supplied evidence references*, not
  *evidence admission*. It has no provenance gate, no freshness model
  (`evaluate()` takes no `now`), and no first-class tenant/workflow binding.
  Treating its coverage score as an admission decision would **falsely equate
  assertion-support scoring with evidence admission** — the exact trap the task
  forbids.
- **Rejected B (a brand-new admission *provider* now):** premature. RA already
  owns the admission *port* and a reference admitter; production admission is an
  *implementation* behind that port, deferred to the RA-5 integration package
  (§10). Naming a new productized provider is an implementation choice, not a
  precondition.
- **Adopted C:** the admission *contract* (`EvidenceAdmissionPort`) is the
  neutral seam; its production implementation lives in the RA-5 integration
  package and may wrap any concrete admission provider later. `ugence-tap-provider`
  is recorded as a **Control-Assurance evaluator candidate** (§4), explicitly
  **not** the admission owner.

**Non-collapse rule (ratified):** assertion-support scoring (`ugence-tap-provider`)
and evidence admission are **different trust questions** and are never merged. A
high `evidence_coverage` is *not* an admission decision.

---

## 4. Ratified decision — Control-Assurance producer boundary (precondition 3)

Three distinct questions, three owners; they never blur:

| Question | Owner | Live anchor |
|---|---|---|
| **Evidence Admission** — "May this evidence enter the assurance process?" | Evidence Admission seam behind `EvidenceAdmissionPort` (impl in RA-5 integration pkg). | `integrations/tap.py` |
| **Control Assurance** — "Does the admitted evidence satisfy mandatory control C?" | **new `ControlAssurancePort`** owned by `risk_authority`; production evaluator impl in the RA-5 integration pkg (candidate: adapted `ugence-tap-provider`). | new (§10) |
| **Risk Authority** — "Given trusted results for required controls, what machine authority may be issued?" | `ugence-risk-authority` — **keeps the non-compensatory aggregation rule** (`domain/controls.py`, `services/risk_engine.py`). | `domain/controls.py:68-109` |

**Ratified boundary:**

1. The non-compensatory **aggregation rule stays inside RA** (`required_controls_satisfied`
   / `unsatisfied_controls`). RA-5 does **not** move it out.
2. Control Assurance is a **new port owned by `risk_authority`** (a contract),
   with the concrete evaluator supplied by the RA-5 **integration package**
   (§10) — not a new standalone package spawned merely because the roadmap uses
   the words "Control Assurance", and not an evaluator embedded in the RA leaf.
3. Control Assurance produces one trusted `ControlResult` per required control
   (§7), bound to the case context; RA re-checks the binding (§8) and applies
   the unchanged aggregation gate.

**If `ugence-tap-provider` is adopted as the evaluator**, the coverage→status
mapping of §11 is mandatory (fail-closed; a `CONSTRAINED`/partial result is
**never** `PASS`).

---

## 5. Position in the pipeline & RA-4.5 compatibility

### 5.1 Ratified production flow (RA-5 seams in **bold**)

```
producers ─► raw evidence + provenance
                 │
      **Evidence Admission** (EvidenceAdmissionPort)   [provenance ∧ integrity(digest) ∧ fresh(now) ∧ context-bound]
                 │
        AdmittedEvidence (EvidenceState.ADMITTED, §6)
                 │
      **Control Assurance** (ControlAssurancePort)      [per required control C: admitted evidence ⊨ C ?]
                 │
        trusted ControlResult (§7, bound to case context)
                 │
   ┌──────── ugence-risk-authority (unchanged spine) ────────┐
   │ required_controls_satisfied (non-compensatory) → RiskEngine → EnvelopeIssuer │
   │ → Ed25519-signed RiskAuthorizationEnvelope  (Scope_env ⊆ Scope_decision)     │
   └─────────────────────────────────────────────────────────┘
                 │  (envelope = SOLE machine authority)
                 ▼
   ugence-risk-authority-runtime (RA-4.5, UNCHANGED) — additive governance composition
   DA veto ─► AG veto ─► F1 effective-action recheck ─► GovernedExecutionDecision
```

### 5.2 RA-5 is strictly upstream of envelope issuance

Everything from the signed envelope onward (RA-4.5 composition, DA veto, AG veto)
is unchanged. RA-5 attaches at the **envelope-issuance boundary inside
`ugence-risk-authority`**.

### 5.3 Boundary caveat (ratified prohibition)

RA-5 **MUST NOT** be wired as an additive governance veto inside RA-4.5 — that
would violate "no upstream permissive result upgrades RA" and the RA-4.5
non-goal fence (`RISK_AUTHORITY_RA45_GOVERNANCE_COMPOSITION_PLAN.md:648-653`).

### 5.4 RA-4.5 invariants hold by construction

`FinalAuthority ≤ RiskAuthority` and `FinalScope ⊆ RiskAuthorityScope`
(`composition.py:31-38`) remain true because RA-5 changes only *whether/what
scope RA issues* — it can only *tighten* issuance (fewer/narrower envelopes),
never widen composition. The RA-4.5 runtime package is **not modified**.

---

## 6. Canonical `AdmittedEvidence` contract (precondition 4)

Extends the existing `ControlEvidenceRecord` (`domain/evidence.py:26-46`). Each
field is classified **REQUIRED** (must be present & bound in production),
**OPTIONAL** (present when the producer supplies it), **FUTURE** (deferred, named
so it is not reinvented), or **NOT OWNED HERE** (belongs to another component).
No field exists without a stated trust purpose.

| Field | Class | Present today | Trust purpose |
|---|---|---|---|
| `schema_version` | REQUIRED | ❌ → add | Reject unknown/incompatible schema fail-closed (§9). |
| `tenant_id` | REQUIRED | ✅ | Tenant isolation is part of the binding, not just a storage partition (§8). |
| `evidence_id` | REQUIRED | ✅ | Stable identity for reference from `ControlResult.evidence_ids`. |
| `source_type` | REQUIRED | ✅ (`type`) | Provenance class; drives admission rules. |
| `source_identity` | REQUIRED | ✅ (`issuer`) | Who produced it; provenance check. |
| `subject` | REQUIRED | ✅ (`subject_id`) | Binds evidence to the actor/model/subject it concerns. |
| `risk_case_id` | OPTIONAL | ❌ | Evidence may legitimately back multiple cases in the same context (§8 reuse); when producer scopes to a case, carry it. |
| `workflow_ir_digest` | REQUIRED | ❌ → add | Evidence for WorkflowIR X may not satisfy Y (§8). |
| `policy_digest` | REQUIRED | ❌ → add | Evidence under policy A may not satisfy policy B (§8). (Today policy_digest == WorkflowIR digest; kept as two fields for future divergence.) |
| `observed_at` | REQUIRED | ✅ (`created_at`) | When the fact was observed; freshness anchor. |
| `admitted_at` | REQUIRED | ❌ → add | When admission decided; audit + monotonicity. |
| `valid_until` / freshness | REQUIRED | ✅ | Stale evidence can never back a PASS (§9). |
| `integrity_digest` | REQUIRED | ✅ (`digest`) | Tamper detection; a mismatch fails admission. |
| `provenance` | REQUIRED | ✅ | Free-form provenance map for the admission decision. |
| `admission_result` | REQUIRED | ✅ (`admission.status`) | `ADMITTED` vs reject state (`EvidenceState`). |
| `admission_reason` | REQUIRED | ✅ (`admission.reason`) | Human/audit reason for the decision. |
| `producer` / `version` | REQUIRED | ❌ → add | Attribute the admission decision to its admitter (accountability). |
| `signature` / attestation | FUTURE | ❌ | Digest suffices for RA-5 (§13); signing deferred. |
| machine-authority binding | NOT OWNED HERE | — | Belongs to `RiskAuthorizationEnvelope`. |

**Authority significance:** none directly — `AdmittedEvidence` gates whether
evidence *may back* a passing control. **Fail-closed:** not `ADMITTED`, not
current at `now`, or context mismatch ⇒ unusable ⇒ the backed control is
`MISSING`/`STALE`.

---

## 7. Canonical trusted `ControlResult` contract (precondition 4)

Today's `ControlResult` (`domain/controls.py:28-51`) carries `control_id`,
`status`, `evidence_ids`, `evaluated_at`, `valid_until`, `reason` — **no tenant,
no case, no policy/workflow digest, no evaluator identity.** The ratified trusted
contract adds the binding tuple and evaluator attribution.

| Field | Class | Present today | Trust purpose |
|---|---|---|---|
| `tenant_id` | REQUIRED | ❌ → add | Binding; cross-tenant reuse fails closed (§8). |
| `risk_case_id` | REQUIRED | ❌ → add | Binding; cross-case reuse fails closed (§8). |
| `workflow_ir_digest` | REQUIRED | ❌ → add | Binding; wrong workflow fails closed (§8). |
| `policy_digest` | REQUIRED | ❌ → add | Binding; wrong policy fails closed (§8). |
| `control_id` | REQUIRED | ✅ | Which required control this satisfies. |
| `evidence_ids` | REQUIRED | ✅ | The admitted evidence this result rests on; each must be `ADMITTED` in-context (§8). |
| `status` | REQUIRED | ✅ (`ControlStatus`) | PASS/FAIL/MISSING/STALE/UNKNOWN/NOT_APPLICABLE. |
| `evaluated_at` | REQUIRED | ✅ | When Control Assurance evaluated. |
| `valid_until` / freshness | REQUIRED | ✅ | Freshness monotonicity (§7.1); `PASS` past window → `STALE` (`controls.py:42-51`). |
| `assurance_engine` (`engine_id`) | REQUIRED | ❌ → add | Attribute the evaluation to its evaluator. |
| `assurance_version` (`engine_version`) | REQUIRED | ❌ → add | Reproducibility/attribution of the evaluation. |
| `reason` | OPTIONAL | ✅ | Audit explanation. |
| integrity/binding digest | FUTURE | ❌ | Only if transport/storage trust proves insufficient (§13); not required for RA-5. |
| signature/attestation | NOT OWNED HERE | — | Machine-authority signing stays with the envelope. |

### 7.1 Freshness monotonicity invariant

`freshness(ControlResult) ≤ min(freshness of its admitted backing evidence)`. A
result must not outlive the evidence it was derived from.

### 7.2 Extend, don't fork

**Ratified:** the existing `ControlResult` is **extended** with the fields above
(new fields default to `None`/empty), **not** forked into a parallel type. This
preserves the 97-test reference suite: reference tests that construct a
`ControlResult` without the new fields still compile and pass; production mode
requires the fields to be populated and bound (§12). No versioned split of the
type is introduced for cleanliness alone.

---

## 8. Trust bindings, replay & cross-context rules (preconditions 4)

### 8.1 Binding relation (RA authoritatively re-checks)

Storage-partition isolation (the `(tenant, case)` dict key in
`persistence/in_memory.py`) is **insufficient**, because the `ControlResult`
object itself carries no binding and would be accepted under the wrong key. The
ratified relation:

```
trusted ControlResult R is usable for case K  ⇔
    R.tenant_id           == K.tenant_id
  ∧ R.risk_case_id        == K.case_id
  ∧ R.workflow_ir_digest  == K.workflow_ir_digest
  ∧ R.policy_digest       == K.policy_digest
  ∧ R.control_id          ∈ K.required_controls
  ∧ every e ∈ R.evidence_ids is ADMITTED under (K.tenant_id, K.policy/workflow)
  ∧ R.is_current(now)  ∧  every backing evidence is_current(now)
Otherwise ⇒ MISSING/STALE ⇒ fail closed (never PASS).
```

Validation happens in **both seams** (Control Assurance binds; RA re-checks
before the gate). Duplicate consistent checks are acceptable; RA's re-check is
authoritative (defense in depth).

### 8.2 Invalid reuse (must fail closed)

| Reuse case | Outcome | Mechanism |
|---|---|---|
| Tenant A result → Tenant B case | DENY | `tenant_id` mismatch |
| Case A result → Case B | DENY | `risk_case_id` mismatch |
| workflow digest X → Y | DENY | `workflow_ir_digest` mismatch |
| policy digest A → B | DENY | `policy_digest` mismatch |
| expired/stale evidence | DENY | freshness (§7.1) |
| revoked/invalidated evidence (pre-issuance) | DENY | admission fails ⇒ control MISSING (§8.4) |
| conflicting duplicate control results | DENY | non-compensatory grouping (`controls.py:82-109`, F-E) |
| result backed by evidence never admitted | DENY | `evidence_ids` not `ADMITTED` in-context |

### 8.3 Reuse that IS allowed

Reuse is **not** inherently replay. One admitted evidence artifact may back
**multiple controls** and **multiple results within the same
(tenant, case, policy, workflow) context** while it remains current. Reuse
identity = the binding tuple + `evidence_ids` + freshness; no separate evidence
nonce is introduced (the *envelope* already owns authority-layer nonce/session
replay — do not duplicate it).

### 8.4 Revocation seam (boundary only)

- **In RA-5 scope:** *pre-issuance* invalidation — inadmissible/stale/revoked
  evidence at evaluation time fails the control (fail closed); no envelope minted.
- **Out of RA-5 scope (name the seam, don't build it):** invalidation *after* an
  envelope was issued — an authority-epoch/revocation concern already owned by RA
  (`services/revocation.py`, `RiskCaseState.REVOKED/EXPIRED/SUPERSEDED`) and
  elaborated in RA-6/RA-7. RA-5 exposes an invalidation *hook* that can *trigger*
  RA revocation; it does not implement continuous runtime revocation.

---

## 9. Ratified outcome mapping — TAP outcome → ControlStatus (precondition 3 / Phase 7)

`ugence-tap-provider` outcomes are **semantic support categories**; RA control
statuses are **satisfaction states**. There is **no existing mapping anywhere in
the repo** (verified). The ratified mapping (fail-closed, non-compensatory):

| `TapOutcome` | → `ControlStatus` | Rationale |
|---|---|---|
| `SUPPORTED` **with `evidence_coverage >= 1.0`** | `PASS` | Only unambiguous full support may satisfy a mandatory control. |
| `SUPPORTED` with coverage `< 1.0` or `None` | `UNKNOWN` (not PASS) | Partial/unquantified support is not full satisfaction. |
| `CONSTRAINED` | `UNKNOWN` (not PASS) | Partial coverage must **never** compensate a mandatory control. |
| `UNSUPPORTED` | `FAIL` | Evidence contradicts the assertion. |
| `INDETERMINATE` | `UNKNOWN` | Unresolved ⇒ never PASS. |
| `UNKNOWN` (TAP non-determination) | `UNKNOWN` | Fail-safe; never coerced to PASS. |

**Ratified rule:** *only* an unambiguous fully-supported outcome
(`SUPPORTED` ∧ `coverage >= 1.0`) may become `PASS`. The `evidence_coverage`
ratio is used **only** as this binary gate — it is **never** carried into RA as a
weight or score. This mapping is mandatory if `ugence-tap-provider` is adopted as
the evaluator; it is not ambiguous and therefore is ratified here rather than
deferred.

---

## 10. State-machine guards (Phase 10)

The RA state machine already models the RA-5 lifecycle
(`domain/risk_case.py:26-42`, `domain/enums.py:73-90`):
`CONTROLS_RESOLVED → EVIDENCE_PENDING → EVIDENCE_COMPLETE → CONTROL_EVALUATED →
AUTHORITY_REVIEW`. **RA-5 adds no new states**; it *strengthens the transition
guards* so a transition corresponds to a real trusted artifact, not an actor
label:

| Transition | Guard today | Ratified RA-5 guard (production mode) |
|---|---|---|
| `EVIDENCE_PENDING → EVIDENCE_COMPLETE` | stamped unconditionally (`dependencies.py:225-236`) | **all** required-control evidence `ADMITTED` through `EvidenceAdmissionPort` and current at `now`. |
| `EVIDENCE_COMPLETE → CONTROL_EVALUATED` | stamped with `actor="control-assurance"` label only (`dependencies.py:237-243`) | a **real** Control-Assurance evaluation via `ControlAssurancePort` produced trusted `ControlResult`s that satisfy the binding relation (§8). |

No transition may be taken on missing/stale/unadmitted evidence; the guard fails
closed and the case cannot reach `AUTHORITY_REVIEW`, so no authority can be
minted.

---

## 11. Failure semantics (Phase 8)

No ambiguous condition mints authority. Three non-executable dispositions are
distinguished: **DENY** (authority denied), **ERROR_NON_EXECUTABLE**
(infra/consistency failure), **HOLD/PENDING** (awaiting input).

| Condition | Control-level result | RA disposition |
|---|---|---|
| Admission unavailable | evidence unusable ⇒ MISSING | DENY (fail closed) |
| Admission rejects evidence (bad provenance/integrity) | MISSING/STALE | DENY |
| Evidence stale (past window) | STALE | DENY |
| Evidence malformed | inadmissible ⇒ MISSING | DENY |
| Wrong tenant | binding reject ⇒ MISSING | DENY |
| Wrong case | binding reject ⇒ MISSING | DENY |
| Wrong policy digest | binding reject ⇒ MISSING | DENY |
| Wrong workflow digest | binding reject ⇒ MISSING | DENY |
| Control Assurance unavailable | UNKNOWN | DENY / non-executable |
| Evaluator ERROR | UNKNOWN | ERROR_NON_EXECUTABLE |
| Control FAIL | FAIL | DENY (non-compensatory) |
| Control UNKNOWN | UNKNOWN | ESCALATE/DENY (never PASS) |
| Missing mandatory control | MISSING | DENY |
| Conflicting duplicate (FAIL alongside PASS) | governed by non-satisfying duplicate ⇒ FAIL | DENY (F-E) |
| Unsupported schema/version | reject | ERROR_NON_EXECUTABLE |
| Pending evidence (`EVIDENCE_PENDING`) | — | HOLD (non-executable) |

---

## 12. Reference vs production mode (Phase 11, precondition 5)

Two modes, explicitly separated (mirrors the RA-4.5 reference/kernel lesson):

| | REFERENCE / CONFORMANCE MODE | PRODUCTION MODE |
|---|---|---|
| Admission | in-memory `ReferenceEvidenceAdmission` / injected records | trusted admission required through `EvidenceAdmissionPort` |
| Control result origin | caller-supplied `ControlResultInput` (synthetic/manual fixtures) | trusted `ControlResult` from `ControlAssurancePort`; caller status is inert |
| Caller-asserted PASS | permitted (isolated tests) | **cannot produce authority** |
| Binding fields | may be unset (defaults) | **must** be populated & re-checked (§8) |

**How production mode proves it is active:** production composition is
established by injecting concrete `EvidenceAdmissionPort` and `ControlAssurancePort`
implementations (via the RA-5 integration package, §10). RA-5 must **fail closed
if production configuration is incomplete** — e.g. a case flagged production but
lacking a bound `ControlAssurancePort` result is treated as MISSING ⇒ DENY,
never falling back to the caller-asserted reference path. The reference path
remains available only in explicit conformance/test configuration and is
documented as conformance-only.

---

## 13. Crypto / attestation decision (Phase 12)

Do **not** sign every artifact. Distinct trust roots for distinct properties:

| Property | Protected by | Root | RA-5 verdict |
|---|---|---|---|
| Evidence **integrity** | content digest (`integrity_digest`); TAP SHA-256 fingerprint | producer (hash) | **Sufficient for RA-5.** |
| Evidence **admission** | fail-closed admission decision + `producer/version` attribution | admission seam | **Attribution, not signature.** Signature = FUTURE. |
| Control **evaluation** | deterministic output + `assurance_engine/version` attribution | evaluator | **Attribution, not signature.** Signature = FUTURE. |
| **Machine authorization** | Ed25519-signed `RiskAuthorizationEnvelope` | **Risk Authority only** | Unchanged; sole authority signature. |

RA-5 adds **hash-binding + attribution**, not new signatures. HSM/KMS and
per-artifact attestation are **FUTURE** (RA production-signing is a separate,
already-documented concern; RA-5 does not change it). Transport/storage trust is
assumed adequate for RA-5; if a deployment cannot assume it, a binding digest on
`ControlResult` (§7 FUTURE) is the first escalation before signatures.

---

## 14. Package / dependency architecture (Phase 9)

**Ratified:** production RA-5 integration lives in a **new sibling integration
package**, mirroring the RA-4.5 pattern (`packages/integration/risk-authority-runtime/`,
`ugence-risk-authority-runtime`, `dependencies = ["ugence-risk-authority>=0.1.0"]`):

```
packages/integration/risk-authority-evidence-runtime/   (ugence-risk-authority-evidence-runtime, NEW — RA-5)
```

Dependency inversion (no reverse cycle):

```
ugence-risk-authority (leaf, dependencies = [])   defines EvidenceAdmissionPort (exists) + ControlAssurancePort (new)
        ▲  one-way import (integration → RA), never the reverse
        │
ugence-risk-authority-evidence-runtime (NEW)      implements the ports using…
        ▼
Evidence Admission provider  +  Control-Assurance evaluator (candidate: ugence-tap-provider)
```

- `ugence-risk-authority` **remains a stdlib-only leaf** — no TAP/provider
  dependency enters it.
- The RA-4.5 runtime package is **not** modified (RA-5 is upstream of the
  envelope it consumes).
- Two ports (admission, assurance) exist because they are genuinely distinct
  trust questions (§4), not for convenience.

---

## 15. Acceptance test matrix (Phase 13 — design only)

Production-path adversarial matrix the RA-5 implementation must satisfy:

| # | Scenario | Expected |
|---|---|---|
| 1 | valid admitted evidence + all mandatory controls PASS | RA may proceed (GRANT after RA-4.5) |
| 2 | caller-forged PASS (no admitted evidence / no assurance) | **cannot produce authority** (closes §2.1 gap) |
| 3 | one mandatory control FAIL | DENY |
| 4 | one mandatory control MISSING | DENY |
| 5 | CONSTRAINED / INDETERMINATE outcome | **not PASS** ⇒ DENY (§9) |
| 6 | stale evidence backing a PASS | DENY |
| 7 | wrong tenant | DENY (binding) |
| 8 | wrong case | DENY (binding) |
| 9 | wrong policy digest | DENY (binding) |
| 10 | wrong workflow digest | DENY (binding) |
| 11 | tampered evidence (digest mismatch) | DENY |
| 12 | unadmitted evidence (never through admission) | DENY |
| 13 | duplicate FAIL alongside PASS (same control) | DENY (F-E) |
| 14 | admission unavailable | fail closed (DENY) |
| 15 | Control Assurance unavailable / ERROR | fail closed (DENY / ERROR_NON_EXECUTABLE) |
| 16 | evidence invalidated after admission, before issuance | DENY |
| 17 | replay: same result reused across a different case | DENY (binding) |
| 18 | RA-1→RA-4 (97) baseline | remains green |
| 19 | RA-4.5 (77) composition baseline | remains green |

Rows 2 and 18–19 are the acceptance anchors: the forged-PASS path is closed and
no existing guarantee regresses.

---

## 16. Final verdict

**`RA5_PRECONDITIONS_RESOLVED_READY_FOR_IMPLEMENTATION`.**

Readiness gate:

| Criterion | Status |
|---|---|
| One canonical RA-5 spec exists | ✅ this document |
| Evidence-admission ownership settled | ✅ §3 (Outcome C) |
| Control Assurance ownership settled | ✅ §4 (new port; rule stays in RA) |
| Trust-binding contracts defined | ✅ §6–§8 |
| Pass/fail mapping ratified | ✅ §9 |
| Failure semantics defined | ✅ §11 |
| Package boundary agreed | ✅ §14 |
| Production/reference mode explicit | ✅ §12 |
| No conflict with RA-4.5 | ✅ §5 |

This is a *readiness* verdict for a **future implementation milestone**; RA-5
implementation is out of scope for this ratification and remains gated on normal
review of the future code change.

---

## 17. Explicit confirmations

- No production code changed by this document (docs-only).
- No RA-5 implementation started; no RA-5 package created.
- No RA-4.5 (`ugence-risk-authority-runtime`) code changed.
- No F-D (#1397) / F2 (#1403) / RT-1 (#1404) work folded in.
- RA-1→RA-4 authority spine and RA-4.5 governance-composition architecture
  unchanged and not reopened.
- No PR opened.
