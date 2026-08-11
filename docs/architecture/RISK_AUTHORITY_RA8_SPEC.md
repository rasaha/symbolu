# Risk Authority RA-8 — Execution / Effect Reconciliation — Canonical Specification (Ratified)

> **Status:** RATIFIED — canonical, in-repo RA-8 specification.
> **Type:** DOCUMENTATION / ARCHITECTURE ONLY. This document changes no
> production code, starts no RA-8 implementation, creates no package, adds no
> port to source, adds no persistence, adds no telemetry/effect infrastructure,
> modifies no envelope / ActionGate / Agent Runtime / RA-6 / RA-7 / Decision
> Authority, implements no Third-Party Gateway or ACP, and opens no PR.
> **Verdict:** `RA8_PRECONDITIONS_RESOLVED_READY_FOR_IMPLEMENTATION` (§35).
> **Baseline:** default branch `claude/setup-symbolu-monorepo-014vhNMAoVW2Ys5RBBr3bKDF`,
> default head `620955fc` (merge of PR #1413 — RA-7). RA-1→RA-4, RA-4.5, RA-5,
> RA-6, and RA-7 are merged and treated as stable and closed. RA-8 reopens none.
> **Supersedes the discovery verdict.** The architecture-discovery companions
> (`RISK_AUTHORITY_RA8_EXECUTION_EFFECT_RECONCILIATION_PLAN.md` and the discovery
> `ADR`, verdict `RA8_ARCHITECTURE_DECISION_REQUIRED` at discovery commit
> `19b0dc33`) are now superseded discovery inputs; their five open decisions
> D-A–D-E are ratified here (§4–§8).

RA-8 is the **post-execution effect verification / reconciliation** milestone
named in the post-RA-6 roadmap bundle (`packages/risk_authority/README.md:31-33`;
RA-5 → RA-8). Every architectural claim below was re-verified against live code
at `620955fc`; file:line anchors are cited so a reviewer can confirm each one.

RA-8 answers exactly one question:

> **"After an authorized action executes, did the actual execution and resulting
> effect match what was authorized and expected — and if not, should that
> discrepancy cause future machine authority to be reassessed?"**

**RA-8 OBSERVES, CORRELATES, AND ASSESSES POST-EFFECT. RA-6 OWNS AUTHORITY
CONSEQUENCES.** RA-8 emits *evidence and a neutral reassessment signal* — never
authority. `RiskAuthorizationEnvelope` remains the sole signed machine-authority
artifact.

---

## 0. Live-code revalidation (baseline `620955fc`)

Ratification independently re-verified every load-bearing discovery fact against
live code. All held; **no repo divergence** (`RA8_RATIFICATION_BLOCKED_BY_REPO_DIVERGENCE`
does **not** apply).

| # | Discovery claim | Live-code verification (baseline `620955fc`) | Verdict |
|---|---|---|---|
| P | default head = discovery base | `620955fc` == default head == discovery base; PR #1413 merged (`merged_at 2026-08-11T09:01:47Z`, head `6af019e5`, base `e6aa6edf`); nothing landed after discovery | ✅ |
| 1 | DA owns the reconciliation kernel | `capabilities/decision-authority/.../execution/{execution_intent,execution_attempt,execution_record,reconciliation,compensation}.py`, `services/{execution,reconciliation,compensation}_service.py`, `repositories/execution_repository.py` all present | ✅ |
| 2 | `ExecutionRecord` = observed effect, never inferred | `execution_record.py:1` — *"observed external-world state, never inferred … a record is created only from an observed business outcome, never from dispatch alone"* | ✅ |
| 3 | DA reconciliation emits **no** `AuthorityReassessmentSignal` into RA-6 | zero `AuthorityReassessmentSignal` / `SignalChangeType` / `import risk_authority` hits in DA `src`; emits `AuditEventType.EXECUTION_MISMATCH_DETECTED` only (`reconciliation_service.py:212`) | ✅ |
| 4 | Agent Runtime and DA are import-isolated | `agent-runtime/tests/test_import_boundaries.py:28-29` forbids `decision_authority` / `ugence_decision_authority`; `artifacts/agent_runtime_acceptance_scenarios.json` scenario `boundary.no_decision_authority` | ✅ |
| 5 | AR `execution_reference` / `result_digest` are unpopulated placeholders | `runtime/execution_state.py:90-91` hardcodes `execution_reference=None, result_digest=None`; `models/execution_state.py:255-259` — *"neutral seams for a future Runtime Assurance / receipt consumer … never fabricated"* | ✅ |
| 6 | AR has no canonical RA envelope binding on its execution path | `models/execution_state.py` carries `authorization_reference` / `authority_scope_ref` (opaque refs) but **no `tenant_id`, no `envelope_id`**; grep of AR `src` for those two fields returns nothing | ✅ |
| 7 | A neutral effect-observation seam already exists | `governance-contracts/.../contracts/execution.py:48` `ExecutionObservation` (*"an observed business outcome"*), `:60` `ExternalExecutionProvider`, `:35` `ExecutionDispatchResult` (*"a transport result — never a business outcome"*); adapted via `governance-provider-framework/.../adapters/execution_to_external_system.py` (`ExternalExecutionPort`) | ✅ |
| 8 | No production trusted effect-source adapter | only `OfflineDeterministicExecutionAdapter` (`decision-authority/.../execution/external_system.py`) + the conformance adapter (`governance-provider-framework/.../conformance/execution.py`); no production implementer of `ExternalExecutionProvider` | ✅ |
| 9 | Third-Party Gateway is unimplemented (roadmap-only) | zero `ThirdPartyGateway` / `third_party_gateway` code hits repo-wide | ✅ |
| 10 | RA-6 `AuthorityLifecycleService` is sole lifecycle writer | `integration/risk-authority-status-runtime/.../{writer,reassessor}.py`; RA-6 unchanged since `e6aa6edf` | ✅ |
| 11 | `RiskAuthorizationEnvelope` is sole signed machine authority | `risk_authority/.../services/envelope_verifier.py:57` `verify_key.verify(envelope.signing_payload(), envelope.signature)`; issuer signs (`envelope_issuer.py:116`); zero second-authority artifacts (`ReconciliationAuthorization`/`EffectGrant`/`ReceiptToken`/`CompensationAuthority` → no hits) | ✅ |
| 12 | Compensation is an advisory proposal requiring fresh authority | `execution/compensation.py:1` — *"a governed proposal, not an auto-rollback"*; `required_authority` field; `CompensationType.GOVERNED_ACTION_REQUEST` | ✅ |
| 13 | M-1: latest-record-wins can mask an earlier unfavorable record | `reconciliation_service.py:178` `latest = records[-1]`; `:220 _compare(intent, records, latest)` keys the whole primary-outcome verdict off `latest`; the DUPLICATE_EFFECT guard (`:224-230`) only fires on **>1 distinct `external_result_id` among success-like records**, so a `FAILED`-then-`SUCCEEDED` sequence on one request resolves to the latest favorable → `RECONCILED` | ✅ **confirmed live** |

**Conclusion:** the discovery is faithful to live code. RA-8's shape (compose the
mature DA kernel from a thin sibling integration package, wire a trusted effect
source and the reconciliation→RA-6 feedback) stands, and the five open decisions
can be ratified without correction.

---

## 1. Ratified RA-8 objective

The candidate objective is **ratified verbatim**: *"After an authorized action
executes, did the actual execution and resulting effect match what was authorized
and expected — and if not, should that discrepancy cause future machine authority
to be reassessed?"*

Ratified ownership model (unchanged from the candidate):

| Actor | Responsibility |
|---|---|
| **Agent Runtime** | records the execution **attempt** / invocation facts (what provider was invoked with what action) |
| **Effect Source** | reports/observes what **actually happened** (external business outcome) |
| **Decision Authority** | performs **reconciliation semantics** (compare authorized intent vs observed effect) |
| **RA-8 integration** | **correlates** authority + attempt + observed effect + DA reconciliation, applies safe aggregation, and emits a **neutral reassessment signal** |
| **RA-6** | owns **authority consequences** (revoke / epoch / no-op) |

RA-8 **MUST NOT**: mint authority · execute compensation directly · revoke
directly · advance epoch directly · become a second Decision Authority · become
another Agent Runtime · become the Third-Party Gateway · become ACP.

---

## 2. Canonical RA-8 boundary (§9-candidate ratified)

- **RA-7 ends** at runtime execution-completion / behavior events
  (`PROVIDER_COMPLETED` / `TASK_COMPLETED`); it consumes runtime **events** only,
  never receipts, and performs no post-effect reconciliation
  (RA-7 SPEC §4 D1; enforced by `risk-authority-runtime-assurance/tests`).
- **RA-8 begins** at **trusted execution/effect observations after invocation** —
  the execution-attempt receipt (from the runtime) and the effect observation
  (from a trusted effect source).
- **RA-8 ends** at a **neutral reconciliation assessment + an optional RA-6
  reassessment signal**. It does not enact the consequence.

**Late runtime event vs true effect observation.** A trajectory escalation that
arrives after provider completion is **RA-7's** (idempotent RA-6 signal, no-op if
already revoked). An effect mismatch observed seconds/minutes later — a delayed
external receipt, a settlement/ledger mutation, a later compensation — is
**RA-8's**. No duplicate ownership: RA-7 never verifies real-world effect (no such
code exists), RA-8 never re-analyzes trajectory. RA-8 **may reference** an RA-7
assessment id as context but **must not recompute** it.

RA-8 does **not**: perform compensation · execute corrections · grant replacement
authority · choose a physical control action · perform trajectory monitoring.

---

## 3. Execution Attempt vs Effect (two artifacts, never collapsed)

| Concept | Statement | Owner | Live model |
|---|---|---|---|
| **Execution Attempt** | *"The runtime invoked provider P with authorized action X."* | **Agent Runtime** (attempt receipt) + DA `ExecutionAttempt` (transport) | AR `CanonicalExecutionState` (`provider_id`, `proposal_fingerprint`, `idempotency_key`, `attempt`) + reserved `execution_reference`/`result_digest`; DA `ExecutionAttempt` (`external_request_id`, `TransportStatus`) |
| **Effect Observation** | *"The target/external system reports that effect Y occurred."* | **Effect Source** → DA `ExecutionRecord` | governance-contracts `ExecutionObservation` → DA `ExecutionRecord` (`business_outcome`, `observed_parameters`, `finality`, `external_result_id`) |

Attempt ≠ effect is already the DA design axiom (`execution/status.py`:
*"authorization, dispatch, transport acknowledgement, and business success are
four different things"*). Domain instances (ratified, illustrative only):

| Domain | Attempt | Effect |
|---|---|---|
| Cloud | terminate instances | instance state actually `TERMINATED` |
| Trading | submit order | broker fill |
| Payment | transfer request | settlement / ledger mutation |
| Hiring | candidate-status update | ATS state |
| Robotics | actuator command | physical sensor observation |

RA-8 owns the *correlation* between the two and the reconciliation composition;
it owns neither the attempt receipt (AR) nor the raw effect (effect source).

---

## 4. Decision D-A — Effect-source / Third-Party trust model  ✅ RATIFIED: **OPTION B**

**RA-8 consumes a neutral `EffectObservationPort`; provider-specific connectors
belong to a separate connector layer ("Third-Party Gateway"), which remains
FUTURE.**

- **Neutral effect-observation contract owner:** `governance-contracts`
  (`ExecutionObservation` / `ExternalExecutionProvider`), adapted onto the DA
  kernel via `governance-provider-framework`'s `ExternalExecutionPort`. RA-8
  **reuses** this as its `EffectObservationPort`; it invents **no** new port.
- **Concrete provider connectors owner:** a separate connector layer (the
  "Third-Party Gateway"). It is **not required** for the RA-8 reference milestone
  and remains **FUTURE**. It is an evidence-source layer, **never** an authority
  component.
- **Production reference mode without a real third-party adapter:** the RA-8
  reference milestone ships against the existing offline/conformance adapter for
  tests and a **reference (conformance-grade) effect adapter**. Reference adapters
  are **allowed** at reference grade and **MUST be refused in production**
  (mirrors the ratified RA-5/RA-6/RA-7 F-1 rule: reference authenticator refused
  in production). A deployment with no trusted effect source yields
  `UNVERIFIABLE`, never `MATCHED` (§13, §27).
- **Effect-source authentication:** **authenticated / delegated ingress** — the
  DA observation-ingestion seam (`authorize_execution`: identity + tenant-bound
  access policy + `RECORD_EXTERNAL_OUTCOME`/`QUERY_EXECUTION_STATUS` permission +
  audit + intrinsic `execution_intent_id`/`external_request_id` binding). **Not**
  per-receipt cryptographic signing.
- **Sufficient for reference maturity:** authenticated ingestion + content-hash
  integrity + immutable append-only records + intrinsic binding. This is
  reference-grade, not production-attested.
- **Explicitly not claimed:** per-receipt cryptographic signing is a **FUTURE**
  hardening, not a reference precondition. **Integrity ≠ authenticity; a hash is
  not a signature** (`content_hash = canonical_hash(...)` is a SHA-256 content
  digest, not an attestation).

---

## 5. Decision D-B — Agent Runtime → Reconciliation correlation  ✅ RATIFIED

**RA-8 owns a new neutral `ExecutionCorrelation` record, minted at authorize-time
and joined to the runtime event stream — without any package importing across the
AR↔DA boundary.**

Minimum neutral correlation contract, `ExecutionCorrelation` (owned by RA-8):

| Field | Source (already available) |
|---|---|
| `tenant_id` | envelope / `GovernedExecutionDecision` context (authorize-time) |
| `workflow_instance_id` | AR `instance_id` |
| `task_id` / `action_id` | AR `task_id` / `operation` |
| `envelope_id` | `GovernedExecutionDecision.risk_authority_result.envelope_id` (`contracts.py:238`) |
| `authorized_action_digest` | `RiskAuthorityMachineResult.action_digest` (`contracts.py:239`) == AR `proposal_fingerprint` |
| `correlation_id` | `GovernedExecutionDecision.correlation_id` (`contracts.py:355`) == AR `correlation_id` — the **join key** |
| `idempotency_key` | AR `idempotency_key` |
| `provider` | AR `provider_id` |
| `attempt_id` | AR `attempt` + `idempotency_key` |
| `started_at` / `completed_at` | AR runtime events (`PROVIDER_INVOKED` / `PROVIDER_COMPLETED`) |
| `result_digest` / `execution_reference` | AR reserved seam (§11) — **the only additive AR change** |

**Answers to the D-B sub-questions:**

1. **Already in AR:** `workflow_instance_id`, `task_id`/`action_id`,
   `authorized_action_digest` (=`proposal_fingerprint`), `idempotency_key`,
   `provider` (=`provider_id`), `attempt`, `correlation_id`, authority refs.
2. **Missing in AR:** `tenant_id`, `envelope_id`, and a **populated**
   `result_digest`/`execution_reference` (currently always `None`).
3. **Can RA-8 derive the missing bindings without modifying AR?** **`tenant_id`
   and `envelope_id`: yes** — they are in hand at authorize-time on the
   `GovernedExecutionDecision`, so RA-8 mints `ExecutionCorrelation` there,
   keyed by `correlation_id`, and joins AR's post-execution event to it. AR never
   learns "tenant" or "envelope" as concepts (preserves I13).
4. **Is a tiny neutral AR seam required?** Only to populate the **already-reserved**
   `execution_reference`/`result_digest` from `ToolResult` — additive,
   backward-compatible, imports nothing (§11). The correlation itself does **not**
   depend on it; RA-8 can also derive attempt evidence from the neutral event
   stream's `execution_state_digest`. Populating the seam is **preferred** (a
   first-class attempt receipt) but **optional** for the reference milestone.
5. **Does governance-contracts already provide a suitable neutral contract?** For
   the **effect** side, yes (`ExecutionObservation`). For the **AR↔authority**
   correlation side, no — RA-8 owns `ExecutionCorrelation`.
6. **Must `envelope_id` be explicitly carried?** **Yes** — on `ExecutionCorrelation`
   and into DA `authority_ref` (§6). Never added to AR.
7. **Must DA `authority_ref` map to envelope id?** **Yes** — RA-8 constructs the
   DA `ExecutionIntent` with `authority_ref = envelope_id`.
8. **How do attempt ids correlate with DA `ExecutionIntent`/`ExecutionAttempt`?**
   RA-8 sets `ExecutionIntent.execution_idempotency_key = AR idempotency_key` and
   binds `ExecutionAttempt.external_request_id` to the effect source's external
   request; the attempt binding is enforced by `authorized_action_digest ==
   proposal_fingerprint`.

**Boundaries preserved (non-negotiable):** AR imports **neither** DA **nor** RA-8;
DA imports **neither** AR **nor** RA-8; RA-8 imports DA + RA + governance-contracts
and reads AR's neutral, duck-typed event contract (the RA-7 pattern). The new
`ExecutionCorrelation` bridge contract is **owned by RA-8**.

---

## 6. Decision D-C — Reconciliation aggregation + envelope binding  ✅ RATIFIED: **A + C**

**Safety invariant (ratified):** *A material unfavorable effect record MUST NOT be
masked by a later favorable record for the same governed execution unless an
explicit reconciliation policy defines a legitimate finality/version supersession
relation.*

- **Aggregation model = A (non-compensatory) + C (explicit finality/version
  supersession).** Any **material** mismatch / `FAILED` / `UNKNOWN` /
  `CONFLICTED` **dominates**. A later favorable record supersedes an earlier one
  **only** when it is an explicit **finality update of the same effect identity**
  (same `external_result_id`, `PARTIAL → FINAL`); a `FINAL` unfavorable record can
  **never** be superseded by a later favorable record of the same governed
  execution. Latest-wins (model D) is **rejected**; provider-specific policy
  (model E) is allowed only as an explicit, declared supersession relation, never
  as a default.
- **M-1 closure (where the fix lives).** DA `_compare` keys off `latest =
  records[-1]` and is reused by non-RA products, so DA stays reusable. **RA-8
  owns the safe aggregation** as a composition rule over
  `get_execution_records(intent_id)`: it applies non-compensatory dominance across
  the **full** record set *before* trusting any single-record verdict. Thus the
  favorable-mask hole is **closed at the RA-8 boundary** with **no** DA code change
  required; an additive hardening of DA `_compare` is a permitted FUTURE follow-up
  but is **not** an RA-8 precondition. RA-8 continues to reuse DA's duplicate
  detection (distinct `external_result_id` > 1 → `MANUAL_REVIEW`) unchanged.
- **PARTIAL → FINAL semantics.** Finality (`PENDING`/`PARTIAL`/`FINAL`) is kept
  **separate** from the match outcome (§13). A `PARTIAL` effect within policy is
  `PARTIALLY_RECONCILED`, not a mismatch; not-yet-final is never treated as
  failure.
- **Duplicate effect.** One authorized attempt → at most one accepted effect
  identity; ≥2 distinct success `external_result_id` → `DUPLICATE_EFFECT` →
  `MANUAL_REVIEW` (DA, present).
- **Conflicting external observers.** `SUCCESS`(provider) vs `FAILURE`(ledger), or
  observer-A-exists vs observer-B-absent → **`CONFLICTED`** (§14) — favorable never
  silently masks unfavorable; resolution requires explicit finality/version
  semantics, never last-writer-wins (§17).

**Envelope binding (M-2 closure).** RA-8 binds **intrinsically** to `envelope_id`
plus the action/attempt digest on the `ExecutionCorrelation` and the DA
`ExecutionIntent` (`authority_ref = envelope_id`). **Storage partitioning alone is
insufficient.** A receipt for the wrong envelope/action/attempt is rejected (§18).

---

## 7. Decision D-D — RA-6 signal category  ✅ RATIFIED: **OPTION B (add `EXECUTION_EFFECT_MISMATCH`)**

**Add a dedicated neutral `SignalChangeType.EXECUTION_EFFECT_MISMATCH` to the RA
leaf enum** (`risk_authority/domain/authority_signal.py:37`; the existing seven
categories are `EVIDENCE_INVALIDATED`, `CONTROL_CHANGED`, `POLICY_SUPERSEDED`,
`WORKFLOW_SUPERSEDED`, `MODEL_INVALIDATED`, `RUNTIME_RISK_ESCALATED`,
`TENANT_EMERGENCY_STOP` — no effect-mismatch category exists).

Justification against the ratified criteria:
- **Materially different audit semantics:** a post-effect mismatch is a distinct
  consequence class from evidence/control/policy/runtime-risk changes.
- **Distinguishes RA-7 from RA-8:** reusing `RUNTIME_RISK_ESCALATED` would conflate
  *during-execution trajectory* risk with *post-execution effect* mismatch; the
  RA-7 spec **reserves** `EXECUTION_EFFECT_MISMATCH` for RA-8 and hard-excludes it
  from RA-7 (asserted by `risk-authority-runtime-assurance/tests/test_contracts.py`).
- **Governance/observability clarity:** a dedicated category gives RA-6 a clean
  reassessment-policy hook.
- **Remains non-authority:** the neutral `AuthorityReassessmentSignal` carries no
  authority by construction; a new *category* changes no RA-6 writer behavior.

The addition is an **additive enum member** — backward-compatible; existing
consumers are unaffected and the fail-closed-on-unknown discipline is already in
place (§33). It is nonetheless a **leaf-schema touch** and therefore an
authority-adjacent, reviewed change.

**Outcome → signal mapping (ratified):**

| Reconciliation outcome | RA-6 signal? |
|---|---|
| `RECONCILED` (MATCHED) | **no signal** |
| `MISMATCHED` (material) | **`EXECUTION_EFFECT_MISMATCH`** |
| `COMPENSATION_REQUIRED` (FAILED/REJECTED/CANCELLED effect) | **`EXECUTION_EFFECT_MISMATCH`** |
| `CONFLICTED` | **signal** (reassess) |
| `PARTIALLY_RECONCILED` (NON_FINAL, within policy) | **no signal yet** |
| `INDETERMINATE` / `UNKNOWN` (finality unknown) | **no signal** (evidence stands; policy-dependent on deadline) |
| `UNVERIFIABLE` (effect source unavailable) | **policy-dependent** (default: no authority change) |

Only **material** mismatch emits (proportionate, mirrors RA-7's material-deviation
gate). Not every non-MATCHED result emits a signal.

---

## 8. Decision D-E — Package ownership / name  ✅ RATIFIED: **OPTION B**

**A new sibling integration package** that composes DA reconciliation + effect
observations + execution-attempt correlation + RA-6 signal intake. Rejected
alternatives (all code-grounded): **A** (inside DA — inverts dependency direction,
DA must stay reusable by procurement/ai-hiring), **C** (inside AR — importing DA
is hard-forbidden by test), **D** (RA leaf — would drag provider/effect/DA deps
into the stdlib-only leaf), **E** (reuse RA-7 — different milestone/boundary).

**Final name:** `packages/integration/risk-authority-execution-assurance/`
(dist `ugence-risk-authority-execution-assurance`, import
`ugence_risk_authority_execution_assurance`). Chosen over
`risk-authority-reconciliation` (DA already **owns** reconciliation; RA-8's job is
assurance/wiring, not the reconciliation compute) and `risk-authority-effect-assurance`
(*execution*-assurance parallels RA-7's *runtime*-assurance and covers both the
attempt and the effect). The name reflects responsibility, not milestone
numbering.

**Dependencies (one-way; preserves every boundary):**

```
ugence-risk-authority-execution-assurance   (RA-8 — composition owner)
  ├─► ugence-decision-authority             (reconciliation kernel)
  ├─► ugence-risk-authority-status-runtime  (RA-6 signal intake)
  ├─► ugence-risk-authority                 (neutral signal type; EXECUTION_EFFECT_MISMATCH)
  ├─► ugence-governance-contracts           (ExecutionObservation / EffectObservationPort)
  └─► ugence-governance-provider-framework  (ExternalExecutionPort adapter)   [optional]
  ··· observes agent-runtime via the neutral, duck-typed event contract (no AR dep required)
```

```
risk_authority (stdlib-only leaf) ◄─ status-runtime (RA-6) ◄─ execution-assurance (RA-8) ─► decision-authority (DA)
                                                                     │ observes ▼ neutral event contract
                                                                 agent-runtime (never imports RA or DA)
```

**Why boundaries hold:** the RA leaf stays **provider-independent** (stdlib-only);
Agent Runtime stays **concrete-governance-independent** (imports neither RA nor
DA); Decision Authority stays **reusable** (imports neither RA nor AR); RA-8 is the
sole **composition owner**.

---

## 9. Reconciliation reuse, artifacts, and ownership

RA-8 **reuses** the DA kernel and does **not** rebuild reconciliation:

| Artifact | Owner | RA-8 posture |
|---|---|---|
| `ExecutionIntent` (authorized) | DA | reuse; set `authority_ref = envelope_id`, `execution_idempotency_key = AR key` |
| `ExecutionAttempt` (transport) | DA | reuse; bind `external_request_id` |
| `ExecutionRecord` (observed effect) | DA | reuse; fed by the trusted effect source |
| `ReconciliationResult` (verdict) | DA | reuse; RA-8 applies safe aggregation over the full record set (§6) |
| `CompensationRequirement` (proposal) | DA | reuse; advisory only (§21) |
| `ExecutionObservation` / `ExternalExecutionProvider` | governance-contracts | reuse as `EffectObservationPort`; **new real adapter is FUTURE** |
| execution-attempt receipt (`execution_reference`/`result_digest`) | Agent Runtime | **new additive seam (§11)** |
| `ExecutionCorrelation` (runtime↔DA↔envelope bridge) | **RA-8** | **new (§5)** |
| `AuthorityReassessmentSignal` | RA leaf | reuse; RA-8 is a new producer |
| `SignalChangeType.EXECUTION_EFFECT_MISMATCH` | RA leaf | **new additive category (§7)** |

---

## 10. Execution-attempt ownership (§11-candidate ratified)

**Agent Runtime owns the execution-attempt receipt** ("I invoked provider P with
authorized action X and got result Y"). The reserved fields already exist
(`models/execution_state.py:255-259`). RA-8 does **not** own provider receipts or
effect correctness. If the seam is not populated, RA-8 derives attempt evidence
from the neutral event stream instead (§5 Q4). **Prefer zero AR changes if the
existing events suffice**; where a seam is added, it is the narrowest neutral,
backward-compatible addition (§11). AR must **not** own effect correctness.

## 11. The single, narrowest AR seam (additive, backward-compatible)

Populate `CanonicalExecutionState.execution_reference` / `result_digest` from
`ToolResult` (`providers/interfaces.py`). Constraints: additive (fields already
exist, default `None`); imports nothing from DA/RA (I13 preserved); never
fabricated (absent → `None`, per the existing field contract); serialization and
`state_digest` already thread the fields. AR gains a first-class attempt receipt;
it gains **no** knowledge of tenant, envelope, reconciliation, or effect
correctness. **This is the only permitted AR change, and it is optional.**

---

## 12. Effect Observation contract (minimum fields)

RA-8 **reuses** governance-contracts `ExecutionObservation`
(`business_outcome`, `observed_parameters`, `final`, `reason`, `provider_trace_id`,
`fingerprint`) → DA `ExecutionRecord` (`business_outcome`, `observed_parameters`,
`finality`, `source`, `external_result_id`, `content_hash`, `tenant_id`,
`correlation_id`). The **minimum** binding/replay/correlation/audit/compare field
set — do **not** invent a universal schema:

`observation_id · tenant_id · workflow_instance_id · envelope_id · action_id ·
attempt_id · external_request_id · external_effect_id · provider · observed_at ·
finality · effect_type · subject/resource · amount/value · result/effect digest ·
source · source_version`. Fields beyond binding + replay + correlation + audit +
effect comparison are excluded.

---

## 13. Effect finality (state ≠ outcome)

**Finality is kept separate from the match result.**

| Finality (state) | Reconciliation outcome (verdict) |
|---|---|
| `PENDING` · `PARTIAL` · `FINAL` (DA `Finality`: FINAL / NON_FINAL / UNKNOWN) | `MATCHED` · `MISMATCH` · `UNKNOWN` · `UNVERIFIABLE` · `CONFLICTED` |

A partial fill may be `PARTIAL` + `MATCHED-to-partial-policy`, or `PARTIAL` +
`MISMATCH`, **depending on policy** (§15). Not-yet-final is **never** a failure;
`UNKNOWN` finality → `INDETERMINATE`, never `MATCHED`.

## 14. Reconciliation outcome vocabulary (reuse DA; no parallel set)

RA-8 **reuses** the DA `ReconciliationStatus` vocabulary and maps to the neutral
set for audit/handoff:

| DA `ReconciliationStatus` | Neutral RA-8 term |
|---|---|
| `RECONCILED` | MATCHED |
| `MISMATCHED` | MISMATCH |
| `PARTIALLY_RECONCILED` | PARTIAL |
| `INDETERMINATE` | UNKNOWN |
| `MANUAL_REVIEW_REQUIRED` | (manual review — duplicate/ambiguous) |
| `COMPENSATION_REQUIRED` | MISMATCH (failed effect) |
| *(new, RA-8 aggregation)* `CONFLICTED` | CONFLICTED |
| *(new, RA-8 seam)* `UNVERIFIABLE` | UNVERIFIABLE (effect source unavailable) |

`CONFLICTED` and `UNVERIFIABLE` are the two additions justified by RA-8's new
seams (conflicting observers; absent effect source) and are distinct from DA
`INDETERMINATE` (finality unknown). **No outcome is named `ALLOW`, `GRANT`, or
`AUTHORIZED`** — RA-8 output is evidence/verdict, not authority. **Malformed /
unknown input MUST NOT become `MATCHED`.**

## 15. Reconciliation policy ownership

**Workflow/domain policy owns the expected effect; DA owns the generic
reconciliation semantics; RA-8 composes.** Domain-specific effect rules (expected
effect, tolerance, finality deadline, partial-acceptance, duplicate-effect
cardinality, external correlation) live in WorkflowIR / domain product policy,
carried per-intent into RA-8 — **never** in the stdlib-only RA leaf, and **not**
as global hardcoded deadlines.

## 16. Duplicate / idempotency model

One authorized attempt → **at most one accepted effect identity**, unless policy
declares an explicit legitimate multi-effect cardinality. Keys: `attempt_id` +
`idempotency_key` (attempt side) and `external_effect_id` / `external_request_id`
(effect side). RA-8 **detects duplicate real effects** (DA `DUPLICATE_EFFECT`); it
does **not** duplicate AR's idempotency ledger — **Agent Runtime prevents
duplicate attempts where possible; RA-8 detects duplicate real effects.**
Timeout-then-effect: `UNKNOWN` transport → later `query_status`/callback →
`ExecutionRecord`; never silently dropped (§27).

## 17. Conflicting receipts

Favorable evidence **MUST NOT silently mask** unfavorable evidence. On conflict
(provider `SUCCESS` vs ledger `FAILURE`; observer-A vs observer-B) the outcome is
**`CONFLICTED`** (or `MISMATCH`) **until resolution**. Supersession is permitted
**only** via explicit version/finality semantics (§6). **No last-writer-wins.**

## 18. Cross-tenant / cross-action binding (intrinsic tuple)

Intrinsic binding tuple: `(tenant_id, workflow_instance_id, envelope_id,
authorized_action_digest, attempt_id, external_request_id)` (+ optional
`provider`, effect identity). Rejection rules (evidence is discarded, never
applied): wrong tenant → reject · wrong workflow → reject · wrong envelope →
reject · wrong action digest → reject · wrong attempt → reject · old receipt on a
new attempt → reject. **Storage partitioning is not enough** — DA already enforces
tenant + `execution_intent_id` + `external_request_id` (`ExternalRequestMismatchError`);
RA-8 adds the **envelope** and **attempt-bridge** edges.

---

## 19. Receipt trust model (reference vs production)

- **Ingress:** authenticated / delegated effect ingress (DA `authorize_execution`:
  tenant-bound, permission-gated, audited, intrinsically bound).
- **Reference:** a static/conformance effect adapter is **allowed**.
- **Production:** the reference adapter is **refused** (RA-5/6/7 F-1 rule).
- **Concrete provider authentication:** delegated to the provider / Third-Party
  Gateway connector (FUTURE).
- **No per-receipt crypto** is required for the reference milestone.
- **FUTURE:** signed external receipts / attestations.
- **Documented honestly:** integrity ≠ authenticity; hash ≠ signature.

## 20. Integrity / digest model

RA-8 records **reference** existing digests rather than minting new circular ones:
`ExecutionIntent.content_hash` (authorized), `ExecutionRecord.content_hash`
(observed), `ReconciliationResult.content_hash` (verdict) — all `canonical_hash`
(SHA-256 **integrity**, not authenticity). The `ExecutionCorrelation` derives from
`envelope_id` + `authorized_action_digest` + `correlation_id` + `attempt_id`.
**`RiskAuthorizationEnvelope` is not modified** (§33). Digests bind content;
authenticity is a deployment/FUTURE concern.

---

## 21. Compensation ownership

RA-8 **detects** a mismatch and (via the reconciliation verdict + the RA-6 signal)
**recommends**. DA `ReconciliationResult`/`CompensationRequirement` may **propose**
compensation. **A compensation proposal is NOT permission.** A compensating action
must pass back through **Risk Authority → RA-4.5 → ActionGate → Agent Runtime**
with **fresh** governed authority (`CompensationType.GOVERNED_ACTION_REQUEST`,
`required_authority`). **RA-8 MUST NOT execute compensation.** A reconciliation
mismatch **must not** automatically create privileged corrective authority.

## 22. RA-6 handoff

```
material reconciliation mismatch (RA-8, safe-aggregated)
  → neutral AuthorityReassessmentSignal(EXECUTION_EFFECT_MISMATCH, target=ENVELOPE,
        evidence_refs=[reconciliation_id, execution_record_id, envelope_id])
  → AuthorityReassessmentSignalPort.submit   (RA-6 intake — reused as-is)
  → RA-6 reassessor (sole authenticated lifecycle writer) → revoke / epoch / no-op
  → next consequential action sees reassessed authority
```

RA-8 **MUST NOT** directly `revoke` · `advance_epoch` · `emergency_stop` ·
`revoke_model` · `revoke_subject`. Signal-emission mapping is §7 (MATCHED → none;
MISMATCH/CONFLICTED → signal; PARTIAL → none yet; UNKNOWN/UNVERIFIABLE →
policy-dependent; PENDING → none).

## 23. RA-7 interaction

`RA-7 ESCALATED` + `RA-8 MISMATCH` → **idempotent, restrictive** RA-6 consequences
(RA-6 dedupes; a second targeted revoke on an already-revoked envelope is a no-op).
RA-8 does **not** re-run trajectory analysis. **RA-7 NORMAL does not override RA-8
MISMATCH**, and **RA-8 MATCHED does not resurrect an envelope revoked by RA-7**
(§24).

## 24. Authority resurrection (explicit invariant)

**A later favorable reconciliation MUST NOT reactivate a revoked/superseded
envelope.** Only a newly issued envelope can restore authority. No `MATCHED →
un-revoke`; no `compensation complete → restore old authority`; no `favorable
receipt → erase an earlier lifecycle consequence`. RA-6 lifecycle transitions are
monotonic with respect to RA-8 evidence.

## 25. Persistence (no third execution ledger)

| Owner | Durable state |
|---|---|
| Agent Runtime | execution event / history (checkpoint store; intent-level) |
| Decision Authority | execution / reconciliation records (`ExecutionRepository`, append-only, immutable) |
| **RA-8 integration** | **minimal correlation / dedupe index only** |

RA-8 **reuses DA persistence** and adds **no** third canonical execution ledger.
Its own state is a thin `ExecutionCorrelation` / dedupe index — correlation,
observation tracking, dedupe — nothing more.

## 26. Audit trace (the enterprise differentiator)

```
RiskAuthorizationEnvelope (signed)      "what was allowed"
  → authorized_action_digest
  → GovernedExecutionDecision            (governed decision)
  → ExecutionAttempt + AR attempt receipt "what was attempted"
  → ExecutionRecord (observed effect)     "what actually happened"
  → ReconciliationResult (safe-aggregated) "did it match"
  → AuthorityReassessmentSignal → RA-6    "what changed because of the mismatch"
  → lifecycle consequence (revoke/epoch/no-op)
  → CompensationRequirement (proposal)
  → new compensation authority/action if freshly authorized
```

Supports: *What was allowed? What was attempted? What happened? Did it match? What
changed because of the mismatch? Was corrective action freshly authorized?* Today
the chain is reconstructible **within** DA but breaks at both ends (envelope
binding at the top, RA-6 feedback at the bottom); closing those two joins is RA-8's
central deliverable.

---

## 27. Failure semantics matrix (no failure becomes MATCHED)

| Condition | Neutral outcome |
|---|---|
| attempt missing | `UNKNOWN` / `PENDING` (no reconcile) |
| effect observation missing | `PENDING` → `UNKNOWN` (deadline, §15) |
| effect source unavailable | **`UNVERIFIABLE`**, authority unchanged |
| receipt malformed | rejected |
| receipt untrusted | rejected |
| wrong tenant / envelope / action / attempt | rejected (§18) |
| duplicate | `DUPLICATE_EFFECT` → `MANUAL_REVIEW` |
| conflict | **`CONFLICTED`** |
| stale / late observation | finality-ordered; late `FINAL` handled, never mask (§6) |
| partial effect | `PARTIALLY_RECONCILED` (finality NON_FINAL) |
| effect-source error | `UNVERIFIABLE` / `INDETERMINATE` |
| reconciliation error | fail-closed, never `MATCHED` |
| DA unavailable | assessment deferred; authority unchanged |
| RA-6 signal sink unavailable | assessment stands as evidence; queue/retry; authority unchanged; **no widen** |

**No failure may become `MATCHED` by default** (matches the RA-7 §20 matrix).

## 28. Security invariants (ratified, non-negotiable)

- **I1** `RiskAuthorizationEnvelope` remains the sole signed machine authority.
- **I2** RA-8 never mints authority.
- **I3** RA-8 never revokes directly.
- **I4** All authority consequences route through RA-6.
- **I5** `ExecutionAttempt` and `EffectObservation` are evidence, not authority.
- **I6** `ReconciliationResult` is evidence/verdict, not authority.
- **I7** Compensation recommendation is not authority.
- **I8** Compensation requires fresh authority.
- **I9** Wrong-tenant/workflow/envelope/action/attempt evidence cannot influence another execution.
- **I10** Favorable evidence cannot mask material unfavorable evidence without explicit supersession/finality policy.
- **I11** A duplicate receipt cannot create a duplicate accepted effect silently.
- **I12** `MATCHED` cannot resurrect old authority.
- **I13** Agent Runtime remains concrete-governance independent.
- **I14** Decision Authority remains reusable / does not import RA-6.
- **I15** Risk Authority leaf remains stdlib-only / provider independent.
- **I16** RA-7 remains trajectory assurance.
- **I17** ACP remains separate.
- **I18** No third execution ledger.

## 29. Threat model

| Threat | Owner | Mitigation (present / RA-8 / FUTURE) | Residual |
|---|---|---|---|
| Forged effect receipt / forged provider result | RA-8 ingress | authenticated, tenant-bound, permission-gated, audited seam (present); signed receipts (FUTURE) | provider self-report trust (deployment) |
| Receipt suppression / delay | RA-8 | `UNKNOWN`/`INDETERMINATE`, never MATCHED (present); finality deadline (RA-8 policy, §15) | delayed effects |
| Receipt replay / duplicate | DA | `external_request_id` match + `DUPLICATE_EFFECT` + idempotency ledger (present) | cross-runtime replay (RA-8 bridge) |
| Conflicting receipts | RA-8 | non-compensatory aggregation → `CONFLICTED` (§6, closes M-1) | resolution latency |
| Wrong tenant / envelope / attempt binding | RA-8 | tenant + intent + external-request (present) + envelope + attempt-bridge (RA-8) | — |
| Provider lies / partial reported as success | RA-8 + effect source | independent trusted observation via `ExecutionObservation` (needs real adapter, FUTURE) | provider is sole observer (deployment) |
| Timeout then effect happens | DA | `UNKNOWN` transport + later record (present) | reconcile timing |
| Retry causes duplicate real effect | DA + AR | idempotency key (AR) + `DUPLICATE_EFFECT` (DA); AR lacks a ledger | AR retry semantics |
| Partial effect reported as success | RA-8 | finality separate from outcome (§13) | policy tuning |
| Unfavorable-early + favorable-late | RA-8 | **M-1 non-compensatory rule (§6)** | — |
| Favorable-early + unfavorable-final | RA-8 | FINAL unfavorable cannot be superseded (§6) | — |
| Compensation abuse | DA | governed proposal, fresh authority (present) | — |
| Reconciliation DoS / signal flooding | RA-8 / deployment | bounded ingestion; dedupe by external-request/idempotency; only material mismatch emits | volume (deployment) |
| Receipt poisoning / external-transaction-id reuse | RA-8 + DA | intrinsic binding + idempotency uniqueness (present) | — |
| Effect source compromised | deployment | authenticated ingress; independent second observer (FUTURE) | trust anchor (deployment) |
| Old receipt on new authority | RA-8 | envelope + attempt-id binding (RA-8) | — |

The **provider-self-report** and **effect-source-trust** residuals are the honest
limit of any reference-grade RA-8 (§34 — no overclaim of physical-world
verification).

## 30. Future test matrix (deny-heavy; design only, not implemented)

1 matching final effect → MATCHED · 2 wrong target → MISMATCH · 3 wrong amount →
MISMATCH (`PARAM_MISMATCH`) · 4 wrong resource → MISMATCH · 5 partial legitimate →
PARTIALLY_RECONCILED · 6 partial unacceptable → MISMATCH · 7 no observation →
PENDING/UNKNOWN · 8 untrusted observation → rejected · 9 malformed observation →
rejected · 10 duplicate observation → DUPLICATE_EFFECT/MANUAL_REVIEW · 11 replay
old observation → rejected · 12 wrong tenant → rejected · 13 wrong workflow →
rejected · 14 wrong envelope → rejected · 15 wrong action digest → rejected · 16
wrong attempt id → rejected · 17 provider success + external failure → CONFLICTED
· 18 provider failure + external effect happened → CONFLICTED/MISMATCH · 19
timeout then effect → UNKNOWN transport then record · 20 retry duplicate effect →
DUPLICATE_EFFECT · 21 conflicting observers → CONFLICTED · 22 favorable cannot mask
unfavorable → M-1 assertion · 23 finality supersession only explicit · 24 delayed
final state → INDETERMINATE until FINAL · 25 effect-source unavailable →
UNVERIFIABLE · 26 reconciliation engine error → fail-closed · 27 DA unavailable →
deferred, authority unchanged · 28 RA-6 sink unavailable → evidence stands, no
widen · 29 mismatch → neutral signal · 30 RA-8 cannot revoke · 31 RA-8 cannot mint
· 32 compensation recommendation cannot execute · 33 compensation requires new
authority · 34 MATCHED cannot resurrect · 35 RA-7 unchanged · 36 RA-6 unchanged ·
37 AR remains decoupled · 38 DA reused · 39 ACP separate · 40 no second authority
artifact · 41 no third execution ledger · 42 RA leaf installs independent.

## 31. Minimum contracts

Prefer **reuse** (§9). New neutral types only where a genuine seam is missing:
`ExecutionCorrelation` (RA-8, §5), the populated AR attempt-receipt seam (AR, §11),
`SignalChangeType.EXECUTION_EFFECT_MISMATCH` (RA leaf, §7), and — only for RA-8's
new aggregation seams — the `CONFLICTED` / `UNVERIFIABLE` outcome terms (§14). For
every type: owner / producer / consumer / persistence / integrity / replay /
authority / failure semantics are specified in §9–§27. **No RA-8 contract may
grant authority** — no `ReconciliationAuthorization` / `EffectGrant` /
`ReceiptToken` / `CompensationAuthority`.

## 32. Platform value (honest differentiator)

RA-8 adds, beyond logs / APM / SIEM / workflow history / provider success logs /
audit trails: **a traceable post-execution chain connecting machine authority,
execution attempt, externally observed effect, reconciliation, and subsequent
authority reassessment** (§26). The differentiator is the **closed loop from effect
back to authority** — but **only if the effect observation is genuinely
independent/trusted**. Where the only effect source is a provider self-report, RA-8
verifies *reported* effect, **not** physical-world truth. **Do not claim** physical
truth, cryptographic attestation, instant finality, or zero-window correction
unless implemented.

## 33. Migration / compatibility (additive)

| Change | Kind | Compatibility |
|---|---|---|
| `RiskAuthorizationEnvelope` schema | **none** | envelope unchanged (§20) |
| Agent Runtime schema | populate existing reserved fields | additive; backward-compatible; optional (§11) |
| Decision Authority schema | **none required** | RA-8 wraps DA; DA hardening is a FUTURE additive follow-up (§6) |
| RA-6 signal enum | add `EXECUTION_EFFECT_MISMATCH` | additive enum member; fail-closed-on-unknown already in place (§7) |
| `authority_ref = envelope_id` | uses existing optional field | additive; no migration |

**No mass migration.** Every change is additive; no authority-critical placeholder
remains.

---

## 34. ALREADY IMPLEMENTED · TO IMPLEMENT · FUTURE · SEPARATE

**ALREADY IMPLEMENTED (reuse; do not rebuild):** RA-6 neutral signal + sole
lifecycle writer · RA-7 trajectory assurance · DA reconciliation primitives
(`ExecutionIntent`/`Attempt`/`Record`/`ReconciliationResult`) · DA compensation
proposal semantics (governed, fresh authority) · governance-contracts observation
seam (`ExecutionObservation`/`ExternalExecutionPort`) · Agent Runtime
event/idempotency fields · DA persistence + duplicate detection + authenticated
ingestion.

**RA-8 TO IMPLEMENT:** integration correlation (`ExecutionCorrelation`, §5) ·
trusted effect ingress (reference adapter; production adapter refused) · effect
observation normalization → `ExecutionRecord` · envelope/action/attempt binding
(`authority_ref = envelope_id`, §6) · safe non-compensatory aggregation + finality
supersession closing M-1 (§6) · DA reconciliation composition · neutral RA-6
handoff (`EXECUTION_EFFECT_MISMATCH`, §7/§22).

**FUTURE:** production Third-Party Gateway connectors · signed external effect
receipts / attestations · global distributed effect observation · advanced
provider-specific attestations · DA `_compare` non-compensatory hardening
(additive) · reconciliation timing/SLA model.

**SEPARATE (not RA-8):** ACP (`capabilities/action-clearance` — pre-effect
clearance) · GRC reporting/dashboards · RA-7 trajectory monitoring.

---

## 35. Architecture verdict

**`RA8_PRECONDITIONS_RESOLVED_READY_FOR_IMPLEMENTATION`.**

D-A through D-E are fully resolved: **D-A** effect-source trust = neutral
`EffectObservationPort` (OPTION B), authenticated/delegated ingress, connectors
FUTURE, reference adapter refused in production; **D-B** AR↔DA correlation =
RA-8-owned `ExecutionCorrelation` minted at authorize-time + one optional additive
AR seam, all import boundaries preserved; **D-C** aggregation = non-compensatory
(A) + explicit finality/version supersession (C), M-1 closed at the RA-8 boundary,
envelope binding wired; **D-D** RA-6 category = additive `EXECUTION_EFFECT_MISMATCH`;
**D-E** package = `risk-authority-execution-assurance` sibling integration package.
The favorable-mask issue (M-1) is architecturally closed (§6); the effect-source
maturity limit is a **documented reference boundary**, not an authority-critical
placeholder. RA-8 is a **moderate integration milestone, not another substantial
subsystem**.

*Documentation / architecture only. No production code, no RA-8 implementation, no
changes to Risk Authority / RA-6 / RA-7 / Agent Runtime / Decision Authority /
ActionGate / Third-Party Gateway / ACP, no CI, no PR, no merge.*
