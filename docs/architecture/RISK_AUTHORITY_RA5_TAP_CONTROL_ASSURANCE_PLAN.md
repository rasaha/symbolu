# Risk Authority RA-5 — TAP + Control Assurance: Architecture Discovery & Integration Design

> **Status:** DISCOVERY COMPANION — superseded on *verdict* by the ratified
> canonical spec, retained for long-form rationale and code-location evidence.
> **CANONICAL DESIGN:** `RISK_AUTHORITY_RA5_SPEC.md` governs in any conflict.
> This document's verdict `RA5_READY_WITH_PRECONDITIONS` and its §22
> preconditions have been **resolved and ratified** in that spec (see its §1
> resolution ledger). The analysis below is unchanged and accurate; only the
> open-precondition status is superseded.
> **Type:** DESIGN / DISCOVERY ONLY — no production code, no RA-5 package, no PR.
> **Architecture verdict (superseded):** `RA5_READY_WITH_PRECONDITIONS` (see §22);
> now `RA5_PRECONDITIONS_RESOLVED_READY_FOR_IMPLEMENTATION` per the canonical spec.
> **Baseline:** default branch head `143f9f3f` (merge of PR #1402). RA-1→RA-4 (#1396)
> and RA-4.5 (#1402) are merged and treated as stable. This document changes no
> production code and reopens neither the RA-1→RA-4 authority spine nor the
> RA-4.5 governance-composition architecture.

This document is the RA-5 milestone's architecture-discovery output. It establishes
**what RA-5 (TAP + Control Assurance) means**, **which existing components own which
responsibility**, and **how Risk Authority should consume trustworthy evidence and
control-assurance results without becoming the evidence authority itself or
duplicating any existing component**. It stops before implementation.

---

## 1. Provenance (independently established)

| Fact | Value |
|---|---|
| Default branch | `claude/setup-symbolu-monorepo-014vhNMAoVW2Ys5RBBr3bKDF` |
| Default HEAD | `143f9f3f515c68e71c3647085e3c7d5a7630c26a` (Merge PR #1402) |
| Working tree | clean at discovery time |
| RA-1→RA-4 (PR #1396) | **merged** into default; merge commit `59bb4f27` in ancestry |
| RA-4.5 (PR #1402) | **merged** into default; merge commit `143f9f3f` (current HEAD) |
| #1405 (RA-4.5 architecture correction, docs) | **closed, not merged** — content folded into #1402's `docs/architecture/RISK_AUTHORITY_RA45_*` files |
| #1406 (RA-4.5 semantic-parity audit, docs) | **closed, not merged** — folded in as `RISK_AUTHORITY_RA45_PHASE1_PARITY_AUDIT.md` |
| #1407 (RA-4.5 adapter plan, docs) | **closed, not merged** — present as `RISK_AUTHORITY_RA45_ADAPTER_PLAN.md`, marked SUPERSEDED |

`#1405/#1406/#1407` are **not needed as separate code baselines**: they were
documentation-only, their content is present in the tree via #1402, and none is a
prerequisite branch for RA-5.

Architecture docs introduced/finalized through #1402 (read before this design):
`docs/architecture/RISK_AUTHORITY_RA45_GOVERNANCE_COMPOSITION_PLAN.md`,
`ADR_RISK_AUTHORITY_RA45_GOVERNANCE_COMPOSITION.md`,
`RISK_AUTHORITY_RA45_ADAPTER_PLAN.md` (SUPERSEDED),
`RISK_AUTHORITY_RA45_IMPLEMENTATION_REPORT.md`,
`RISK_AUTHORITY_RA45_PHASE1_PARITY_AUDIT.md`.

---

## 2. The authoritative RA-5 definition (and a spec-provenance caveat)

### 2.1 Where RA-5 is defined

The consolidated **"Ugence Risk Authority Architecture Specification (v1.1)"** is
**cited throughout the code but is not committed to this repository**. It is
referenced by `packages/risk_authority/README.md:11` ("implements the RA-1 → RA-4
vertical slice of the Ugence Risk Authority Architecture Specification (v1.1)") and
by section citations (`spec §9`, `spec §10`, `spec §35 roadmap`, `user brief §25`)
in code docstrings, but no file bearing that content exists in-repo (independently
confirmed by exhaustive title/section/format search). **This is a precondition
item, not a blocker** (§22).

In the **absence** of the consolidated spec, RA-5's authoritative in-repo definition
is the union of these committed artifacts:

- **`packages/risk_authority/README.md:31-36`** — "TAP + Control Assurance,
  revocation/epoch propagation, Context Minimization, Third-Party Gateway,
  Trajectory Control, ACP and Reconciliation (**RA-5 → RA-8**) are defined here **as
  contracts** and layer onto this spine incrementally."
- **`packages/risk_authority/src/risk_authority/integrations/tap.py:1-8`** — the
  RA-5 **evidence-admission** contract: "TAP-compatible evidence-admission contract
  (spec §9, roadmap RA-5)… enforces the fail-closed admissibility rule
  (**provenance / integrity / freshness**) … before the full TAP provider is wired
  in at RA-5."
- **`packages/risk_authority/src/risk_authority/domain/evidence.py:1-6`** — the RA-5
  invariant: "Only *admissible* evidence may back a passing control … the admission
  decision itself is a contract (TAP-compatible) consumed from `integrations.tap`
  and layered in RA-5."
- **`docs/architecture/RISK_AUTHORITY_RA45_GOVERNANCE_COMPOSITION_PLAN.md:648-653`**
  — negative-scope fence: RA-4.5 "is **not** a vehicle for RA-5+, TAP expansion,
  Control Assurance…". RA-5 is explicitly *upstream* of RA-4.5.

### 2.2 RA-5 objective (reconstructed from the authoritative in-repo contracts)

> **RA-5 makes the control basis of Risk Authority trustworthy.** It replaces the
> current caller-asserted control status with a **trusted, evidence-derived
> `ControlResult`**, produced by (a) admitting raw evidence through a
> TAP-compatible evidence-admission seam (provenance/integrity/freshness) and (b)
> evaluating admitted evidence against each required control through a
> Control-Assurance seam — **without Risk Authority becoming the evidence authority
> or the evidence-scoring engine, and without minting any new machine authority.**

| RA-5 facet | Definition (from in-repo contracts) |
|---|---|
| **Objective** | Establish a trustworthy evidence → admitted-evidence → trusted `ControlResult` path feeding the *existing* non-compensatory control gate; close the "caller manufactures ControlResult" trust gap (§5). |
| **Inputs** | Raw evidence artifacts + provenance metadata (from producers/TAP); required-control set (already resolved by RA from WorkflowIR); case/policy/workflow binding context. |
| **Outputs** | (1) `ADMITTED`/rejected evidence records (`EvidenceState`); (2) trusted `ControlResult`s (`ControlStatus`) bound to the exact case/policy/workflow/tenant; (3) audit events. **No authorization artifact.** |
| **Required invariants** | Fail-closed admission (`tap.py:33-38`); non-compensatory control satisfaction preserved (`controls.py:68-109`); freshness never coerced to PASS (`controls.py:42-51`); tenant/policy/workflow/case binding of every trusted result (new — §8); RA remains the sole authority mint (unchanged). |
| **Dependencies** | RA-1→RA-4 spine (#1396, merged); an evidence-admission provider *or* metadata port; a control-assurance evaluator. Independent of RA-4.5 (which sits downstream). |
| **Explicit non-goals** | Trajectory Control, ACP, Reconciliation, Context Minimization, full PWC ingestion, GRC dashboards (RA-6→RA-8; `README.md:110-113`); runtime evidence revocation of already-issued envelopes (RA-6/RA-7 / authority-epoch seam — §15). |
| **Acceptance criteria** | The RA-5 adversarial matrix in §20 passes fail-closed on the production path; RA-1→RA-4's 97-test baseline and RA-4.5's 77-test composition suite remain green; RA stays a stdlib-only leaf. |

### 2.3 Document conflicts

No two in-repo documents **disagree** about RA-5; the only defect is **incompleteness**
(the consolidated spec is absent) plus a **naming/role collision** around the word
"TAP" (§3.1). Because there is no contradiction to adjudicate, the verdict is
`RA5_READY_WITH_PRECONDITIONS`, not `RA5_SPEC_AMBIGUOUS`.

---

## 3. Existing components — what already exists and what it owns

### 3.1 "TAP" — three distinct things; the name collides

| Artifact | Path | Nature | RA-5 relevance |
|---|---|---|---|
| **`ugence-tap-provider`** | `packages/providers/tap/` (`ugence_tap_provider`) | **Canonical, mature** package (src/, tests, CI `tap-provider-package-ci.yml`, Beta). An **assertion-governance provider** — a *peer of ActionGate*. | Candidate **Control-Assurance evaluator**, *not* the evidence-admission pipeline. |
| `tap_provider/` | `tap_provider/` | Logic-free compatibility facade re-exporting the canonical package. | none |
| `truth_assurance_pipeline/` | `truth_assurance_pipeline/` | Research corpus (TAP-E1…E7) over **synthetic** data; self-described as not production-ready. | Research lineage only. |

**What `ugence-tap-provider` owns** (`docs/ASSERTION_GOVERNANCE_BOUNDARY.md:3-4`):
"evaluating whether a material assertion is **supported, unsupported, constrained,
or indeterminate** relative to supplied evidence." Its result vocabulary is
`TapOutcome` = {SUPPORTED, UNSUPPORTED, CONSTRAINED, INDETERMINATE, UNKNOWN}
(`core/__init__.py:56-68`). It computes an evidence-coverage ratio, emits
constraints/obligations/reason-codes, and produces a **SHA-256 content fingerprint**
(not a signature).

**What `ugence-tap-provider` explicitly does NOT own** (`provider.py:5-8`,
`__init__.py:16-19`): it does not authorize, dispatch, execute, reconcile, or
compensate; it never imports/invokes ActionGate; it makes no business decision. And
critically for RA-5:
- It **does not admit evidence** — it *scores assertion support* over
  **caller-supplied** evidence references. There is no provenance/integrity gate.
- It has **no freshness/revocation model** — `evaluate()` takes no `now`;
  `effective_period` is a non-evaluated free-text string.
- Tenant/workflow are not first-class; they ride in a free-form `context` map.
  Uncertainty is fail-safe to `INDETERMINATE`, never promoted to `SUPPORTED`.

**Consequence (the key TAP finding).** The productized component literally named
"TAP" fills the **evidence-satisfies-claim** role (i.e. it is the natural
**Control-Assurance** engine), **not** the **evidence-admission** role that RA-5's
"TAP" (spec §9: provenance/integrity/freshness) requires. The **evidence-admission
role currently has no productized owner** — only RA's reference stub (§3.3). RA-5
must not resolve this by building a *second* assertion engine or a *second*
authority; it must name which existing component fills which role (§22 precondition).

### 3.2 "Control Assurance" — no standalone package; the rule already lives in RA

There is **no** standalone Control-Assurance package. The **live** capability that
answers "is this required control satisfied?" is already inside the RA leaf:
- `packages/risk_authority/src/risk_authority/domain/controls.py` — the
  non-compensatory satisfaction rule (`required_controls_satisfied`,
  `unsatisfied_controls`, per-control grouping that prevents a later `PASS` masking
  a `FAIL`).
- `packages/risk_authority/src/risk_authority/services/risk_engine.py` — the
  evaluator that maps unsatisfied controls to `DENY`/`ESCALATE` fail-closed.

The proper-noun "Control Assurance" in the roadmap is **contract-only** (RA-5). The
four root evidence directories (`evidence_assurance/`, `evidence_obligation/`,
`minimal_evidence_policy/`, `claim_integrity/`) are **frozen research eval
harnesses** (no `pyproject.toml`, not under `packages/`, mirrored under `docs/`) —
lineage, not the platform answer. **RA-5 must not spawn a new package merely because
the roadmap uses the words "Control Assurance."**

### 3.3 Risk Authority's current control/evidence model

- **`ControlResult`** (`domain/controls.py:28-51`): `control_id`, `status`,
  `evidence_ids`, `evaluated_at`, `valid_until`, `reason`. **No tenant, no
  case_id, no workflow/policy digest, no producer/engine identity.**
- **`ControlEvidenceRecord`** (`domain/evidence.py:26-46`): `evidence_id`,
  `tenant_id`, `type`, `subject_id`, `issuer`, `created_at`, `valid_until`,
  `digest`, `admission`, `provenance`. Binds tenant + subject + validity, but **no
  policy/workflow/case binding.**
- **`EvidenceAdmissionPort` / `ReferenceEvidenceAdmission`** (`integrations/tap.py`)
  — a fail-closed admitter (`ADMITTED` + current) — **defined and exported but
  invoked nowhere** in `services/` or `api/` (verified). The admission seam exists;
  it is not yet in the decision path.
- **State machine** (`domain/enums.py:73-90`, `domain/risk_case.py:26-42`) already
  contains `EVIDENCE_PENDING → EVIDENCE_COMPLETE → CONTROL_EVALUATED` — the RA-5
  states are **pre-provisioned**.

---

## 4. Ownership matrix

The matrix names each responsibility to its single owner. "TAP (admission)" and
"Control Assurance" are the two RA-5 seams; the rest are unchanged from RA-1→RA-4.5.

| Component | Answers / owns | Must **not** own |
|---|---|---|
| **TAP — evidence admission** (RA-5 seam; owner TBD, §22) | "Is this evidence **admissible/trustworthy**?" — provenance, integrity (digest), freshness/validity window → `EvidenceState.ADMITTED` or reject. | Whether evidence *satisfies a control*; any authorization; control status; scope; signing of machine authority. |
| **Control Assurance** (RA-5 seam; evaluator = adapted `ugence-tap-provider` or new adapter) | "Does the **admitted evidence satisfy control C**?" → a trusted `ControlResult` (`ControlStatus`), bound to case/policy/workflow/tenant. | Evidence admission (consumes already-admitted evidence); the non-compensatory *aggregation rule* (RA owns it); authority; scope; envelope. |
| **Risk Authority** (`ugence-risk-authority`, merged) | "Given the mandatory controls and their **trusted** results, what **machine authority** may exist?" Non-compensatory aggregation, decision, signed `RiskAuthorizationEnvelope`, scope monotonicity, expiry, revocation/epoch, exact-action enforcement. | Admitting evidence; scoring evidence-vs-claim; organizational veto; action-policy veto. |
| **Decision Authority** (`ugence-decision-authority`) | "Does **organizational/human governance** veto/hold?" (`ADVANCE/HOLD/REJECT` → veto). | Manufacturing/widening/refreshing RA authority; scope; evidence; controls. |
| **ActionGate** (`ugence-actiongate-provider`) | "Does **action policy** further restrict/veto?" (`ALLOW/DENY/UNKNOWN` → veto/tighten). | Manufacturing/widening RA authority; evidence admission; control evaluation. |
| **RA-4.5 composition** (`ugence-risk-authority-runtime`, merged) | Fold DA + AG **additive vetoes** onto the RA machine result → single fail-closed `GovernedExecutionDecision`; F1 effective-action recheck. | Minting/re-minting authority; adding control evidence; anything upstream of envelope issuance (RA-5 is upstream — §17). |

**Non-blur rule.** TAP admits (trust of the *artifact*). Control Assurance evaluates
(does the *admitted artifact* satisfy the *control*). Risk Authority aggregates
non-compensatorily and mints authority. DA and AG only subtract. These four trust
questions must never collapse into one another.

---

## 5. The current trust gap

Today (`api/dependencies.py:206-273`, `api/schemas.py:47-56`):

```
caller supplies ControlResultInput{control_id, status:str, evidence_ids}
        ↓   (RA stamps evaluated_at=now; NO admission, NO evaluation)
ControlResult persisted per (tenant, case)
        ↓   (case walked CONTROL_EVALUATED with actor="control-assurance" — a LABEL only)
RiskEngine.evaluate trusts the caller-asserted status
        ↓
Decision Authority + signed envelope
```

- The **caller manufactures the control status**. The `EVIDENCE_PENDING →
  EVIDENCE_COMPLETE → CONTROL_EVALUATED` transitions are stamped with no real
  admission or assurance behind them; `actor="control-assurance"` is aspirational.
- The **`EvidenceAdmissionPort` is never invoked**; `evidence_ids` are opaque
  strings copied through.
- The **F-A audit fix** (`issue_decision` re-derives the recommendation from the
  case's *persisted* control state, `dependencies.py:301-315`) prevents a *second,
  permissive* evaluation at decision time — but the **origin** of the control status
  is still the caller. F-A closed the "swap ALLOW at decision time" hole; it did not
  make the control status evidence-derived.

**This is acceptable and intended for RA-1→RA-4 reference/conformance mode** (tests
inject known results). It is **not** acceptable for production machine authority.

**The RA-5 target path** (proven consistent with the existing contracts):

```
raw evidence + provenance
        ↓  TAP evidence admission (provenance / integrity / freshness)   [spec §9]
admitted evidence  (EvidenceState.ADMITTED, digest-bound, validity window)
        ↓  Control Assurance (does admitted evidence satisfy control C?) [spec §10]
trusted ControlResult  (bound to tenant / policy / workflow / case / control / time)
        ↓  Risk Authority: existing non-compensatory gate + decision
signed RiskAuthorizationEnvelope   (RA is still the sole mint)
        ↓  RA-4.5 composition → Decision Authority veto → ActionGate veto
exact-action eligibility
```

RA consumes a **trusted `ControlResult`**; it does **not** admit or score evidence
itself.

---

## 6. Proposed production flow (full path)

```
producers / connectors ──► raw evidence + provenance metadata
                                   │
                    (RA-5) TAP evidence-admission provider  ── behind EvidenceAdmissionPort
                                   │  admit ⇔ provenance ok ∧ integrity(digest) ok ∧ fresh(now)
                                   ▼
                         AdmittedEvidence (EvidenceState.ADMITTED)
                                   │
                    (RA-5) Control-Assurance evaluator       ── behind (new) ControlAssurancePort
                                   │  per required control C: admitted evidence ⊨ C ?
                                   ▼
                         trusted ControlResult  (case/policy/workflow/tenant/control/time bound)
                                   │
        ┌──────────────────────── ugence-risk-authority (unchanged spine) ───────────────────────┐
        │  required_controls_satisfied (non-compensatory)  →  RiskEngine  →  Decision Authority   │
        │  →  EnvelopeIssuer  →  signed RiskAuthorizationEnvelope  (Scope_env ⊆ Scope_decision)   │
        └───────────────────────────────────────────────────────────────────────────────────────┘
                                   │  (envelope is the SOLE machine-execution authority)
                                   ▼
        ugence-risk-authority-runtime (RA-4.5, unchanged) — additive governance composition
        FinalAuthority ≤ RiskAuthority ;  FinalScope ⊆ RiskAuthorityScope
                                   │
             Decision Authority veto ──► ActionGate veto ──► F1 effective-action recheck
                                   ▼
                         GovernedExecutionDecision → exact-action eligibility
```

The RA-5 seams live **entirely upstream of envelope issuance**. Everything from the
signed envelope onward (RA-4.5 composition, DA veto, AG veto) is unchanged.

---

## 7. Trust bindings (required)

Every trusted control result must be **intrinsically bound** so a valid result from
another tenant/case/policy/workflow **fails closed** — storage-partition isolation
(the current `(tenant, case)` dict key in `persistence/in_memory.py:79-89`) is
**not** sufficient, because the `ControlResult` object itself carries no binding and
would be accepted if presented under the wrong key.

| Binding dimension | Where it must appear | Current status |
|---|---|---|
| `tenant_id` | AdmittedEvidence ✅, trusted ControlResult ❌→**add** | evidence has it; ControlResult lacks it |
| `risk_case_id` | trusted ControlResult ❌→**add** | absent |
| `workflow_ir_digest` | AdmittedEvidence ❌→**add**, ControlResult ❌→**add** | RA binds it on the case/decision, not on evidence/result |
| `policy_digest` | AdmittedEvidence ❌→**add**, ControlResult ❌→**add** | (policy digest == WorkflowIR digest today) |
| `control_id` | ControlResult ✅ | present |
| `subject/actor/model` | AdmittedEvidence `subject_id` ✅ | present on evidence |
| `evidence_ids` | ControlResult ✅ | present (opaque today) |
| `evaluation timestamp` | ControlResult `evaluated_at` ✅ | present |
| `freshness window` | AdmittedEvidence `valid_until` ✅, ControlResult `valid_until` ✅ | present |
| `assurance engine/version` | trusted ControlResult ❌→**add** | absent (needed to attribute trust) |

**Binding relation to enforce (RA-5):**

```
trusted ControlResult R is usable for case K  ⇔
    R.tenant_id        == K.tenant_id
  ∧ R.risk_case_id     == K.case_id
  ∧ R.workflow_ir_digest == K.workflow_ir_digest
  ∧ R.policy_digest    == K.policy_digest
  ∧ R.control_id       ∈ K.required_controls
  ∧ every e ∈ R.evidence_ids is ADMITTED under (K.tenant_id, same policy/workflow)
  ∧ R.is_current(now)  ∧ every backing evidence is_current(now)
Otherwise ⇒ MISSING/STALE ⇒ fail closed (never PASS).
```

---

## 8. Proposed contracts (conceptual — NOT implemented here)

For each: **owner / producer / consumer / authority significance / fail-closed
behavior**. These extend existing shapes; they avoid duplicating RA's envelope.

| Contract | Shape (conceptual) | Owner / Producer / Consumer | Authority significance | Fail-closed |
|---|---|---|---|---|
| **AdmittedEvidence** (extend existing `ControlEvidenceRecord`) | add `workflow_ir_digest`, `policy_digest`; keep `evidence_id, tenant_id, subject_id, issuer, created_at, valid_until, digest, admission, provenance` | Owner: RA domain. Producer: TAP admission provider (behind `EvidenceAdmissionPort`). Consumer: Control-Assurance evaluator. | None (not authority) — it gates whether evidence *may back* a passing control. | not `ADMITTED` or not current ⇒ unusable ⇒ control MISSING/STALE. |
| **EvidenceAdmissionPort** (exists) | `is_admissible(evidence, *, now) -> bool` | Owner: RA (`integrations/tap.py`). Producer of impl: RA-5 integration package. | None. | any exception/unavailable ⇒ inadmissible. |
| **ControlAssuranceRequest** (new) | `tenant_id, risk_case_id, workflow_ir_digest, policy_digest, control_id, subject_id, admitted_evidence: tuple[AdmittedEvidence], now` | Owner: RA (new port module). Producer: RA facade. Consumer: Control-Assurance evaluator. | None (request). | malformed ⇒ evaluator returns UNKNOWN. |
| **ControlAssuranceResult** (new) | `control_id, status: ControlStatus, evidence_ids, evaluated_at, valid_until, reason, engine_id, engine_version` + the §7 bindings | Owner: RA domain. Producer: Control-Assurance evaluator. Consumer: RA `RiskEngine`. | **High** — becomes the trusted `ControlResult` the non-compensatory gate consumes. | any non-`PASS`/`NOT_APPLICABLE` (incl. UNKNOWN/ERROR) ⇒ unsatisfied. |
| **ControlAssurancePort** (new) | `evaluate(ControlAssuranceRequest) -> ControlAssuranceResult` | Owner: RA (`integrations`). Producer of impl: RA-5 integration package (adapting `ugence-tap-provider` or a dedicated evaluator). | Mediates trust. | port error/unavailable ⇒ UNKNOWN ⇒ fail closed. |
| **EvidenceBinding** (new, thin) | `(tenant_id, risk_case_id, workflow_ir_digest, policy_digest)` value object | Owner: RA domain. Producer/Consumer: both seams. | Enforces §7 relation; a mismatch ⇒ reject. | mismatch ⇒ result treated as MISSING. |

RA-5 introduces **no** new signed/authorization artifact. The signed
`RiskAuthorizationEnvelope` remains the sole machine-execution authority (do not
duplicate it).

---

## 9. State transitions (minimal — existing states suffice)

The RA state machine **already** models the RA-5 lifecycle
(`domain/enums.py:79-81`, `domain/risk_case.py:29-32`):
`CONTROLS_RESOLVED → EVIDENCE_PENDING → EVIDENCE_COMPLETE → CONTROL_EVALUATED →
AUTHORITY_REVIEW`. **RA-5 needs no new states.** It changes only *what must be true*
to take those transitions:

- `EVIDENCE_PENDING → EVIDENCE_COMPLETE`: gated on **all required controls' evidence
  admitted** through `EvidenceAdmissionPort` (today: stamped unconditionally).
- `EVIDENCE_COMPLETE → CONTROL_EVALUATED`: gated on a **real** Control-Assurance
  evaluation via `ControlAssurancePort` producing trusted `ControlResult`s (today:
  stamped with `actor="control-assurance"` but no evaluation).

No transition may be taken on missing/stale/unadmitted evidence — the guard fails
closed and the case cannot reach `AUTHORITY_REVIEW`, so no authority can be minted.

---

## 10. Freshness / time

- **Freshness is policy-driven, not a hardcoded constant.** Validity windows already
  live on `ControlEvidenceRecord.valid_until` and `ControlResult.valid_until`; RA-5
  populates them from policy/producer metadata, never from an invented duration.
- **A `PASS` past its window is reported `STALE`** (`controls.py:42-51`) and can
  never satisfy a control — this is preserved.
- **Freshness monotonicity invariant (RA-5):**
  `freshness(ControlResult) ≤ min(freshness of its admitted backing evidence)`.
  A control result must not outlive the evidence it was derived from; a new
  policy/workflow digest invalidates reuse of an old result (§11).
- Evidence-admission determines admissibility at `now`; a stale-at-issuance
  evidence record is inadmissible → control MISSING/STALE → fail closed.

---

## 11. Policy / workflow binding

RA already treats the **WorkflowIR digest as the immutable policy digest** and binds
decisions to it (`README.md:58`; `RiskEvaluation.workflow_ir_digest`,
`risk_engine.py:34`). RA-5 must preserve:

- Evidence/results evaluated under **policy A cannot satisfy a control under policy
  B** — enforce by carrying `policy_digest`/`workflow_ir_digest` on AdmittedEvidence
  and trusted ControlResult and checking equality against the case (§7).
- Evidence for **WorkflowIR X cannot satisfy WorkflowIR Y** — same mechanism.

**Where validation belongs:** *both* seams, consistently (duplicate checks are
acceptable if consistent; a missing check is not). The Control-Assurance evaluator
binds `policy_digest`/`workflow_ir_digest` into each result; RA re-checks the
binding against the case before the result feeds the gate. RA's re-check is the
authoritative one (defense in depth).

---

## 12. Tenant isolation

Tenant identity must be **part of the trust binding**, not merely a storage
partition. RA-5 cross-tenant adversarial cases (all must fail closed):

| Case | Required outcome | Mechanism |
|---|---|---|
| Tenant A evidence → Tenant B control eval | reject (inadmissible for B) | `AdmittedEvidence.tenant_id` ≠ request tenant |
| Tenant A admitted artifact → Tenant B risk case | reject | §7 binding relation |
| Tenant A ControlResult → Tenant B RiskDecision | MISSING ⇒ DENY | `ControlResult.tenant_id`/`risk_case_id` mismatch |
| Tenant A policy digest → Tenant B evidence eval | reject | `policy_digest` mismatch |

---

## 13. Evidence replay / duplicates

Replay is **not** always wrong. Legitimate reuse: one admitted evidence artifact may
back **multiple controls** and **multiple results within the same
(tenant, case, policy, workflow)** context and while it remains current.

Illegitimate replay (must fail closed): the **same result reused across a different
case/policy/workflow/tenant** (blocked by §7), or **stale reuse** (blocked by §10).

- Reuse identity = the §7 binding tuple + `evidence_ids` + freshness — no separate
  nonce is required for reuse control (RA's *envelope* already owns nonce/session
  replay at the authority layer; do not duplicate it at the evidence layer).
- **Duplicate `ControlResult`s remain fail-closed (F-E preserved):** RA groups all
  results per control id and a single non-satisfying duplicate governs
  (`controls.py:54-109`). RA-5 must not regress this — the trusted producer may emit
  at most the intended results, and RA's grouping still governs if duplicates arrive.

---

## 14. Revocation / invalidation seam

Admitted evidence or an assurance result can later become invalid (source
compromised, evaluator revoked, policy updated, data found corrupt, assurance key
revoked). RA-5's responsibility boundary:

- **In RA-5 scope:** *pre-issuance* invalidation — inadmissible/stale/revoked
  evidence at evaluation time simply fails the control (fail closed), so no envelope
  is minted.
- **Out of RA-5 scope (identify the seam, don't build it):** invalidation of
  evidence **after** an envelope was already issued on it. That is an
  **authority-epoch / revocation** concern already owned by RA
  (`services/revocation.py`, `RiskCaseState.REVOKED/EXPIRED/SUPERSEDED`,
  `AUTHORITY_EPOCH_ADVANCED`) and elaborated in **RA-6/RA-7** (continuous assurance
  / runtime revocation). RA-5 should expose the hook (an invalidation signal that
  *triggers* RA revocation) but must not implement continuous runtime revocation.

---

## 15. Crypto / provenance ownership

Different trust roots for different properties — do **not** sign every internal
object:

| Property | Protected by | Signer / root |
|---|---|---|
| Evidence **integrity** | content digest (`ControlEvidenceRecord.digest`); `ugence-tap-provider` SHA-256 fingerprints | producer/TAP (hash, not signature) |
| Evidence **admission** | fail-closed admission decision over provenance/integrity/freshness | TAP admission provider |
| Control **evaluation** | deterministic evaluator output + `engine_id/engine_version` attribution | Control-Assurance evaluator |
| **Machine authorization** | Ed25519-signed `RiskAuthorizationEnvelope` | **Risk Authority only** (`crypto/signing.py`) |

RA-5 adds **hash-binding** (digests) and **evaluator attribution**, not new
signatures. Machine-authority signing stays exclusively with RA. (Production
signing/HSM for RA remains a separate, already-documented concern; RA-5 does not
change it.)

---

## 16. Package / integration boundary

Mirror the RA-4.5 pattern — **dependency inversion, RA stays a stdlib-only leaf**
(`packages/risk_authority/pyproject.toml:24` `dependencies = []`):

```
ugence-risk-authority (leaf)         defines EvidenceAdmissionPort (exists) + ControlAssurancePort (new)
        ▲
        │ one-way import (runtime → RA), never the reverse
        │
ugence-risk-authority-evidence-runtime (NEW integration package, RA-5)
        │  implements the ports using…
        ▼
ugence-tap-provider  +  evidence-admission provider (TBD)
```

- RA declares the ports; a **new integration package** (proposed name
  `ugence-risk-authority-evidence-runtime`, sibling of the RA-4.5
  `ugence-risk-authority-runtime`) implements them against the concrete providers.
  **Do not** add TAP/provider dependencies into `ugence-risk-authority`.
- The Control-Assurance evaluator plugs in behind `ControlAssurancePort`; propose a
  second port only because admission and evaluation are genuinely distinct trust
  questions (§4) — not for convenience.
- The RA-4.5 runtime package is **not** modified: RA-5 is upstream of the envelope
  it consumes.

---

## 17. RA-4.5 compatibility (unchanged invariants)

RA-5 is strictly **upstream of machine-authority issuance**; the RA-4.5
governance-composition invariants hold unchanged **by construction**:

- `FinalAuthority ≤ RiskAuthority`, `FinalScope ⊆ RiskAuthorityScope`
  (`composition.py:31-38`) — governance inputs remain subtract-only; RA-5 changes
  only *whether/what scope RA issues*, never the composition.
- The runtime package still consumes an **already-signed envelope** and only
  **wraps** it (`risk_authority_enforcer.py`; `GovernedExecutionDecision` carries no
  signature). RA-5 can only *tighten* issuance (fewer/narrower envelopes); it can
  never widen composition.
- **Boundary caveat (must observe):** RA-5 must **not** be wired as an additive
  governance veto inside RA-4.5 — that would violate "no upstream permissive result
  upgrades RA" and the RA-4.5 non-goal fence
  (`RISK_AUTHORITY_RA45_GOVERNANCE_COMPOSITION_PLAN.md:648-653`). RA-5 attaches at
  the **envelope-issuance** boundary inside `ugence-risk-authority`.

---

## 18. Failure semantics (fail-closed table)

No ambiguous state may mint authority. Distinguish `DENY` (authority denied),
`ERROR_NON_EXECUTABLE` (infra/consistency failure), and `HOLD/PENDING`
(awaiting input) — none of which is executable.

| Condition | Control-level result | RA outcome |
|---|---|---|
| TAP (admission) unavailable | evidence unusable ⇒ MISSING | DENY (fail closed) |
| TAP rejects evidence (bad provenance/integrity) | MISSING/STALE | DENY |
| Evidence malformed | inadmissible ⇒ MISSING | DENY |
| Evidence stale (past window) | STALE | DENY |
| Control Assurance unavailable | UNKNOWN | DENY / non-executable |
| Control Assurance ERROR | UNKNOWN | ERROR_NON_EXECUTABLE (no authority) |
| Control FAIL | FAIL | DENY (non-compensatory) |
| Control UNKNOWN | UNKNOWN | ESCALATE/DENY (never PASS) |
| Missing mandatory control | MISSING | DENY |
| Policy-digest mismatch | binding reject ⇒ MISSING | DENY |
| Workflow-digest mismatch | binding reject ⇒ MISSING | DENY |
| Tenant mismatch | binding reject ⇒ MISSING | DENY |
| Duplicate conflict (FAIL alongside PASS) | governed by non-satisfying duplicate ⇒ FAIL | DENY (F-E) |
| Unsupported schema/version | reject | ERROR_NON_EXECUTABLE |
| Evidence still `EVIDENCE_PENDING` | — | HOLD (non-executable) |

---

## 19. Non-compensatory semantics (preserved)

RA-5 must **not** introduce weighted averaging, confidence compensation, majority
vote, or "high evidence score offsets a failed mandatory control." The existing
rule governs:

- `C1 PASS, C2 FAIL, C3 PASS ⇒ DENY` (a single unsatisfied required control governs,
  `controls.py:82-109`; `risk_engine.py:63-86`).
- missing / stale / unadmitted / wrong-tenant / wrong-policy / tampered / duplicate
  evidence ⇒ the affected control is not `PASS` ⇒ DENY/non-executable (§18).

`ugence-tap-provider` emits an `evidence_coverage` **ratio** and a `CONSTRAINED`
partial-support outcome — RA-5 must map those to a **binary** `ControlStatus`
fail-closed (anything short of full support ⇒ **not** `PASS`), never let a coverage
score compensate. This mapping is a required design rule if that provider is adopted
as the evaluator.

---

## 20. Adversarial test plan (design only — not implemented)

Production-path (not reference-only) adversarial matrix:

| # | Scenario | Expected |
|---|---|---|
| 1 | valid admitted evidence + all mandatory controls PASS | authority may proceed (GRANT after RA-4.5) |
| 2 | one mandatory control FAIL | DENY |
| 3 | one mandatory control MISSING | DENY |
| 4 | stale evidence backing a PASS | DENY / non-executable |
| 5 | unadmitted evidence (never through TAP) | DENY |
| 6 | wrong-tenant evidence/result | DENY (binding) |
| 7 | wrong policy digest | DENY |
| 8 | wrong workflow digest | DENY |
| 9 | tampered evidence (digest mismatch) | DENY |
| 10 | duplicate FAIL alongside PASS (same control) | DENY (F-E) |
| 11 | TAP admission unavailable | fail closed (DENY) |
| 12 | Control Assurance unavailable/ERROR | fail closed (DENY / ERROR_NON_EXECUTABLE) |
| 13 | caller-forged PASS (no admitted evidence / no assurance) | **cannot produce authority** (closes §5 gap) |
| 14 | replay: same result reused across a different case | DENY (binding) |
| 15 | `CONSTRAINED`/partial coverage from evaluator | **not PASS** ⇒ DENY (no compensation) |
| 16 | evidence invalidated after admission but before issuance | DENY |
| 17 | regression: RA-1→RA-4 (97) + RA-4.5 (77) suites | still green |

Cases 13 and 17 are the RA-5 acceptance anchors: the forged-PASS path must be
closed, and no existing guarantee may regress.

---

## 21. Maturity boundary — what RA-5 does and does NOT establish

**RA-5 establishes:** a trustworthy evidence-admission + control-assurance path
producing trusted, bound, fail-closed `ControlResult`s consumed by the existing RA
non-compensatory gate; an invalidation *hook* into RA revocation.

**RA-5 does NOT establish (RA-6→RA-8 / separate):** full continuous assurance,
runtime evidence revocation of live envelopes, Trajectory Control, ACP,
Reconciliation, Context Minimization, GRC dashboards, cloud-scaling integration.
Do not claim these.

---

## 22. Preconditions (the gate before RA-5 implementation)

The verdict is `RA5_READY_WITH_PRECONDITIONS`. The architecture is coherent and
designable; the following **decision/documentation** preconditions must be resolved
first (none is a code blocker, none requires reopening RA-1→RA-4.5):

1. **Ratify an RA-5 specification in-repo.** The consolidated "Architecture
   Specification v1.1" is cited but absent (§2.1). Commit an authoritative RA-5
   section (objective/inputs/outputs/invariants/dependencies/non-goals/acceptance) —
   this document is the candidate; it must be reviewed and blessed, or the external
   spec committed.
2. **Settle the TAP role/naming.** Decide the **evidence-admission** owner (§3.1):
   adopt/build an admission provider behind `EvidenceAdmissionPort`, and explicitly
   record that `ugence-tap-provider` (assertion-support scorer) is a candidate
   **Control-Assurance evaluator**, *not* the admission pipeline. Resolve the
   "TAP" name collision (assertion-governance provider vs. spec-§9 admission vs. the
   research `truth_assurance_pipeline`).
3. **Fix the Control-Assurance boundary.** Confirm RA keeps the non-compensatory
   *aggregation rule*; RA-5 supplies only a *trusted producer* of `ControlResult`
   behind a new `ControlAssurancePort` (§4, §8). If `ugence-tap-provider` is the
   evaluator, ratify the coverage→binary fail-closed mapping (§19).
4. **Add trust-binding fields** (§7) to `ControlResult`/`ControlEvidenceRecord`
   (tenant, case, policy/workflow digest, engine attribution) — a domain change to
   `ugence-risk-authority`, separately reviewed.
5. **Confirm reference/conformance compatibility** (§23 of this milestone; migration
   below): preserve reference-mode `ControlResult` injection for isolated tests while
   introducing the production trusted-adapter path.

---

## 23. Migration / backward compatibility

Mirror the RA-4.5 lesson (reference vs. production):

1. **Preserve** the current reference/conformance path (caller-supplied
   `ControlResultInput`) for isolated, stdlib-only tests — the 97-test RA baseline
   must not break.
2. **Introduce** a production-only trusted adapter path: the RA-5 integration
   package feeds trusted `ControlResult`s (via the ports) instead of caller
   assertions.
3. **Deprecate** the unsafe public assumption that a caller-asserted `PASS` is
   trustworthy in production — document that reference injection is
   conformance-only, exactly as RA-4.5 distinguished reference `DecisionAuthority`
   from the canonical kernel.

---

## 24. Deferred items (remain separate)

- **#1397 (F-D)** — resource/jurisdiction/autonomy enforcement: **separate.** RA-5
  does not require it (evidence/control trust is orthogonal to action-dimension
  enforcement).
- **#1403 (F2)** — harden `GovernedExecutionDecision` against inconsistent manual
  construction: **separate** (RA-4.5 DTO hardening, downstream of RA-5).
- **#1404 (RT-1)** — require `CanonicalAction` for executable RA-4.5 composition
  paths: **separate** (composition-layer, downstream of RA-5).

None is pulled into RA-5. No RA-5 dependency on any of them was found.

---

## 25. Architecture verdict

**`RA5_READY_WITH_PRECONDITIONS`.**

Rationale against the readiness gate:

| Gate criterion | Assessment |
|---|---|
| Authoritative RA-5 requirements clear | **Partial** — role/intent coherent from in-code contracts; consolidated spec absent (precondition 1). |
| TAP ownership clear | **Partial** — productized "TAP" is assertion-support, not admission; admission role unowned (precondition 2). |
| Control Assurance ownership clear | **Yes, with a decision** — rule stays in RA; trusted producer via new port (precondition 3). |
| No duplicate authority component required | **Yes** — RA-5 mints nothing; envelope stays the sole authority. |
| Production integration fail-closed | **Yes** — port pattern + fail-closed table (§18). |
| Dependency architecture feasible | **Yes** — mirrors RA-4.5; RA stays a stdlib-only leaf (§16). |
| F-A / F-E preservable | **Yes** — RA-5 *reinforces* F-A (removes caller-asserted status); F-E untouched. |

Not `RA5_READY_TO_DESIGN` (spec absent + TAP naming/role unsettled), not
`RA5_BLOCKED_BY_OVERLAP` (no forced duplication; deferred items not required), not
`RA5_SPEC_AMBIGUOUS` (no document contradicts another; the defect is incompleteness,
resolvable by the §22 preconditions).

---

## 26. Explicit confirmations

- No production code changed by this document (docs-only).
- No RA-5 implementation started; no RA-5 package created.
- No RA-4.5 (`ugence-risk-authority-runtime`) code changed.
- No F-D (#1397) / F2 (#1403) / RT-1 (#1404) fix folded in.
- RA-1→RA-4 authority spine and RA-4.5 governance-composition architecture unchanged
  and not reopened.
- No PR opened.
