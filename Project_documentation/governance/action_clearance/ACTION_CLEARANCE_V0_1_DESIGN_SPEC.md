# Action Clearance — v0.1 Capability Design Specification

**Status:** PROPOSED · design-only. **Contract/policy version:** `action_clearance.v1` ·
**Proposed distribution version:** `0.1.0`.

**Phase discipline.** This is a documentation, contract-design, authority-boundary, trust-model,
packaging-plan, and implementation-readiness phase **only**. It creates no package, moves no source,
changes no runtime behavior, adds no `ProviderKind`, and modifies no frozen contract or freeze artifact.
The next action after this spec is a **decision** on the P0 items in §33, not code.

**Default branch:** `claude/setup-symbolu-monorepo-014vhNMAoVW2Ys5RBBr3bKDF` @ `3d9f73c9`
(*Merge PR #1274 — Code Governance implementation-readiness audit*; the prior audit HEAD `3ec11e4e`
has advanced — PRs #1274 and #1275 are both integrated).
**Design branch:** `claude/action-clearance-v0-1-design-9u4745` (environment-mandated; the prompt's
proposed `claude/action-clearance-v0-1-design` is the intent, the suffixed name is authoritative —
see §5 and the completion report).

**Authoritative source hierarchy** (highest first): (1) live repository contracts & public APIs;
(2) the merged Action Clearance product-core audit (`docs/audits/action_clearance/`, PR #1275);
(3) the merged Code Governance implementation-readiness audit
(`docs/audits/code_governance_readiness/`, PR #1274); (4) `UGENCE_CODE_GOVERNANCE_DESIGN_SPEC.md`
(v0.2); (5) the console clearance implementation as behavioral reference; (6) the robotics Autonomous
Control Plane as an **engineering-pattern reference only**; (7) general architectural inference,
marked as such. Prose in this spec never overrides a live frozen contract.

---

## The one invariant

> **Action Clearance may preserve, narrow, defer, escalate, or block an existing authorization.
> It may never create authority, broaden authorization, replace ActionGate, dispatch execution,
> or own the authoritative consumption ledger.**

Everything below is a consequence of this sentence.

---

## 0. What Action Clearance is (and what the audit found)

Action Clearance is a **new, neutral, deterministic capability** that answers exactly one question:

> Given an existing exact-action authorization and a set of trusted current-state signals, is that
> exact action **clear to execute at this evaluation time**?

The Action Clearance product-core audit (PR #1275) reached the verdict **ACP NOT READY — do not
package** and enumerated the reasons: (R1) the authority definition is unresolved — the robotics V1
core *mints* a `ControlAuthorization` grant while the cloud/console framing never authorizes; (R2)
there is no stable request/result contract — three divergent shapes exist; (R3) there is no single
product core — the discipline is split across robotics, console, and the Decision-Authority freshness
seam; (R5) any source move breaks the robotics V1 freeze digest. This spec is the **resolution phase**
for those findings. It does not migrate any code; it *defines the capability the audit said did not yet
exist*, resolves the authority ambiguity in favor of **clear-only**, and specifies a single neutral
contract family so a future implementation can begin cleanly.

**Terminology fact (from the audit).** "Action Clearance Protocol" appears nowhere in the repository;
"ACP" everywhere expands to **Autonomous Control Plane**. This spec therefore establishes *Action
Clearance* as a distinct capability name and forbids the bare acronym "ACP" in all new technical
surfaces (§5).

Full detail for every section below lives in the companion set under
[`docs/design/action_clearance/`](docs/design/action_clearance/). This document is the spine; each
`§` cross-references its companion.

---

## 1. Verified starting point

| Item | Value |
|---|---|
| `DEFAULT_BRANCH` | `claude/setup-symbolu-monorepo-014vhNMAoVW2Ys5RBBr3bKDF` |
| `DEFAULT_HEAD` | `3d9f73c9b244f058b63a1666ce389a0fbebf8376` (*Merge PR #1274*) |
| `WORKTREE_STATUS` | clean at start |
| `PYTHON_VERSION` | 3.11.15 (Linux) |
| `ENVIRONMENT` | git repo; `pytest`/`pydantic`/`numpy` pip-installed to run the baseline (no repo file changed) |
| `CODE_GOVERNANCE_AUDIT_STATUS` | **integrated** — PR #1274 merged (default HEAD) |
| `ACTION_CLEARANCE_AUDIT_STATUS` | **integrated** — PR #1275 merged (`89aa0a3c`, ancestor of default) |
| `RELATED_OPEN_PRS` | none touch Action Clearance or attempt to package `symbolu_robotics/autonomous_control_plane` |
| `RELATED_RECENT_BRANCHES` | `claude/acp-product-core-separation-audit-qrwlxv` (audit, merged); no competing design/impl/package branch |

Both prerequisites are satisfied: PR #1275 (ACP product-core audit) is integrated, and the Code
Governance readiness audit (PR #1274) is integrated. The design proceeds. Baseline reproduction and
freeze verification are in §36 and [`docs/design/action_clearance/EXECUTIVE_SUMMARY.md`](../../repository/docs/design/action_clearance/EXECUTIVE_SUMMARY.md).

---

## 2–3. Source hierarchy & reproduced baseline

The evidence hierarchy is stated in the header. Guardrails observed: the robotics Autonomous Control
Plane does **not** define governance-authority semantics here; AI-Control-Plane product docs do **not**
define the canonical package API; console-specific types do **not** become neutral contracts
automatically; proposed prose never overrides live frozen contracts.

Baseline reproduced green at `3d9f73c9` with only the three documented pre-existing failures (2 in
`platform_freeze/tests` freeze-tooling; 1 in `bounded_shadow_pilot` ground-truth) — none Action-Clearance
attributable. Platform-freeze substantive digest `d4ad77e1…a174a1a6` unchanged; robotics local freeze
combined digest `8f8660e293308cf94c983a26a2ae69c9` verified byte-accurate (all 13 modules). See §36.

---

## 5. Terminology (permanent naming policy)

| Aspect | Value |
|---|---|
| Technical capability | **Action Clearance** |
| Python namespace | `ugence_action_clearance` |
| Distribution | `ugence-action-clearance` |
| Package directory | `packages/capabilities/action-clearance` |
| Contract/policy version | `action_clearance.v1` |

Bare **"ACP"** is prohibited in package names, import paths, public class names, public type names,
reason-code prefixes, persistent record names, and new technical documentation headings. Existing
robotics code retains "Autonomous Control Plane" and its compatibility surface unchanged. The new
capability must **not** alias, re-export, or claim object identity with
`symbolu_robotics.autonomous_control_plane`. Full acronym-collision policy:
[`TERMINOLOGY_AND_NAMING.md`](../../repository/docs/design/action_clearance/TERMINOLOGY_AND_NAMING.md).

---

## 6. Authority model

```text
Authorized actor + Decision Authority
        ↓ binding DecisionRecord
ContextEnvelopeRecord (CER)
        ↓ governance context
ActionGate
        ↓ exact-action authorization (ActionGovernanceResult)
Action Clearance
        ↓ immediate execution clearance (ClearanceResult)
Execution provider + execution/idempotency ledger
        ↓ dispatch, observation, reconciliation, authoritative consumption
```

- **Decision Authority** owns actor authority, binding-decision validation, `DecisionRecord`,
  segregation of duties, override/supersession. It does **not** own live execution readiness.
- **ActionGate** owns exact-action authorization, policy constraints, requested-parameter validation,
  the authorization result, and authorization expiry/obligations where defined. It does **not** own
  current-target or operational-state evaluation.
- **Action Clearance** owns deterministic evaluation of trusted current-state signals, immediate
  executability of an *existing* authorization, a short-lived clearance result, fail-closed handling of
  stale/missing/conflicting/untrusted signals, and narrowing/holding/escalation/blocking. It does
  **not** own original decision authority, creation of authorization, permission broadening, provider
  routing, workflow state, execution dispatch, external-system source-of-truth state, or the
  authoritative one-time-use ledger.
- **Execution provider + execution ledger** own atomic one-time dispatch protection, idempotency
  reservation, execution, observation, reconciliation, and authoritative consumption state.

Prohibited responsibility transfers and the resolution of the robotics "authorize vs clear" ambiguity
(resolved to **clear-only**): [`AUTHORITY_BOUNDARY.md`](../../repository/docs/design/action_clearance/AUTHORITY_BOUNDARY.md).

---

## 7. Monotonicity invariant

> **Clearance permissions ⊆ ActionGate-authorized permissions.**

Action Clearance must never add an action, add a target, expand parameters, extend authorization
expiry, remove an upstream obligation, replace the authorized actor, change the authorized artifact,
substitute an execution method, or convert an ActionGate denial into an executable result.

Deterministic constraint intersection:
- Compatible: `effective_constraints = authorization_constraints ∩ clearance_constraints` (clearance
  may only add restrictions, i.e. narrow).
- Direct conflict: `CONSTRAINT_CONFLICT` → **block or escalate** (default `ESCALATE`).
- Missing interpretation rule: **fail closed** (never silently union).

Detail and worked examples: [`MONOTONICITY_AND_CONSTRAINTS.md`](../../repository/docs/design/action_clearance/MONOTONICITY_AND_CONSTRAINTS.md).

---

## 8. The served world

Neutral core, domain-specific profiles. The core is domain-agnostic; it holds **no** GitHub,
Kubernetes, database, robotics, incident-platform, or identity-provider client. Profiles/adapters may
serve GitHub merges, deployments, database operations, agent-tool execution, financial operations, and
robotics operations.

**First supported profile: the GitHub exact-merge clearance profile** (§23). Deployment and other
domains are later profiles. Served-world detail: [`PACKAGE_BOUNDARY.md`](../../repository/docs/design/action_clearance/PACKAGE_BOUNDARY.md)
and [`PROFILE_EXTENSIBILITY.md`](../../repository/docs/design/action_clearance/PROFILE_EXTENSIBILITY.md).

---

## 9–11. Signals: evidence vs current state, model, ownership

**TAP evidence** supports claims used *before* the binding decision (tests passed, scan passed, review
completed, policy assessment satisfied). **Action Clearance signals** represent current operational
facts evaluated *after* authorization and *immediately before* execution (authorization not expired,
actor active, exact artifact still matches, required checks still valid, no active freeze/incident,
target available, policy version still accepted, action not already consumed). Action Clearance does
**not** re-adjudicate TAP evidence unless a policy explicitly requires freshness validation of an
evidence-derived signal.

The neutral signal model (`TrustedSignal`) is tenant-bound, subject-bound, time-bound,
source-identified, integrity-verifiable, freshness-evaluable, deterministic after normalization,
serializable, and immutable after creation. Missing mandatory signals **fail closed**. Action Clearance
**receives** signals; it never fetches external state directly. Field-level model, required-vs-adapter
split, and every missing/stale/expired/contradictory/untrusted/mismatch case:
[`TRUSTED_SIGNAL_MODEL.md`](../../repository/docs/design/action_clearance/TRUSTED_SIGNAL_MODEL.md). Per-signal
authoritative owner and receive/validate/evaluate/reference relationship:
[`SIGNAL_OWNERSHIP_MATRIX.md`](../../repository/docs/design/action_clearance/SIGNAL_OWNERSHIP_MATRIX.md).

---

## 12–13. Request, result, and receipt contracts

- **`ClearanceRequest`** binds the authorization context, the exact action identity, the trusted-signal
  bundle, and the clearance-policy context. It carries **no credentials and no executable provider
  commands**. Identity is grouped to avoid duplication:
  `AuthorizationContext` · `ActionIdentity` · `SignalBundle` · `ClearancePolicyContext`.
  Full field table and grouping rationale: [`REQUEST_CONTRACT.md`](../../repository/docs/design/action_clearance/REQUEST_CONTRACT.md).
- **`ClearanceResult`** is the deterministic evaluator output. **`ClearanceReceipt`** is the durable
  product record persisted by the caller/workflow layer around a `ClearanceResult`. The evaluator
  generates **no** nondeterministic UUID and reads **no** system clock.
  Identity strategy: **caller-supplied `request_id` + content-addressed `result_fingerprint`**;
  `result_id = "acr_" + result_fingerprint`. Full field tables:
  [`RESULT_AND_RECEIPT_CONTRACT.md`](../../repository/docs/design/action_clearance/RESULT_AND_RECEIPT_CONTRACT.md).

Machine-readable schemas: [`action_clearance_request.schema.json`](docs/design/action_clearance/action_clearance_request.schema.json),
[`action_clearance_result.schema.json`](docs/design/action_clearance/action_clearance_result.schema.json),
[`trusted_signal.schema.json`](docs/design/action_clearance/trusted_signal.schema.json).

---

## 14–15. Status & reason semantics

**Four top-level statuses:** `CLEAR`, `HOLD`, `BLOCK`, `ESCALATE`. The finer conditions the prompt
raises — `STALE`, `EXPIRED`, `INCOMPLETE`, `CONFLICT`, `UNTRUSTED` — are **reason codes**, not statuses.
Programming errors and malformed contracts are **exceptions**. `DENY` is **not** used (ActionGate owns
authorization denial); a `BLOCK` explicitly means *execution is not clear under current operational
conditions; the underlying authorization is neither broadened nor replaced.*

Status combination is least-permissive-wins with precedence `BLOCK > ESCALATE > HOLD > CLEAR`. Per
status: whether execution is permitted, retry allowed, a fresh request required, human review required,
upstream reauthorization required, and whether the authorization remains valid — all tabulated in
[`STATUS_AND_REASON_SEMANTICS.md`](../../repository/docs/design/action_clearance/STATUS_AND_REASON_SEMANTICS.md).

Reason codes are a curated closed catalog (UPPER_SNAKE, no `ACP`/`AC_` prefix, aligned with Decision
Authority's governed-catalog discipline). Each code is classified `CORE_NEUTRAL` / `PROFILE_SPECIFIC` /
`ADAPTER_SPECIFIC` / `WORKFLOW_ONLY` / `UNNECESSARY`. Existing ActionGate/Decision-Authority codes are
**referenced, not duplicated**. Full catalog and classification:
[`STATUS_AND_REASON_SEMANTICS.md`](../../repository/docs/design/action_clearance/STATUS_AND_REASON_SEMANTICS.md).

---

## 16–17. Time, freshness, determinism, fingerprints

Evaluation time is **caller-supplied**; the core contains no `datetime.now()`. Windows:
`clearance.valid_until ≤ authorization.expires_at` and
`clearance.valid_until ≤ min(required-signal valid_until)`. Clearance may shorten but never extend
authorization validity. A required signal with no trustworthy validity bound → **fail closed**. Clock
skew, boundary-at-exact-expiry, and stale-signal policy: [`TIME_AND_FRESHNESS.md`](../../repository/docs/design/action_clearance/TIME_AND_FRESHNESS.md).

The evaluator is deterministic. Canonical serialization (sorted keys, compact separators, UTF-8,
`allow_nan=false`, normalized `-0.0`, ordered reason codes) feeds four SHA-256, domain-separated
fingerprints — `action_fingerprint`, `request_fingerprint`, `signal_bundle_fingerprint`,
`result_fingerprint` — mirroring the repository's `identity.py`/`canonical_hash`/`fingerprint` pattern
under a new `action_clearance` domain tag (never `acp`). No random values, implicit clock reads,
network calls, env reads, mutable global policy, unordered reason output, or unstable map serialization.
Inclusion/exclusion sets and the semantic-equivalence harness design:
[`DETERMINISM_AND_FINGERPRINTS.md`](../../repository/docs/design/action_clearance/DETERMINISM_AND_FINGERPRINTS.md).

---

## 18–19. Persistence, one-time-use, and replay

The core persists **nothing**. The **Workflow Service** persists the `ClearanceReceipt`. The
**execution/idempotency ledger** (today the Decision-Authority execution repositories) persists
reservation, consumption, dispatch, and observation. Content-addressed fingerprints link the layers.
Detail: [`PERSISTENCE_BOUNDARY.md`](../../repository/docs/design/action_clearance/PERSISTENCE_BOUNDARY.md).

One-time-use is **downstream**. The authoritative replay key binds at least
`tenant · authorization_ref · action_fingerprint · target · operation`. Action Clearance receives
prior-consumption as a trusted signal (`ALREADY_CONSUMED`) but never atomically owns consumption. Two
concurrent dispatches sharing one valid clearance → the ledger's atomic reservation lets **exactly one**
proceed; the other observes `DUPLICATE`. Handoff and race semantics:
[`ONE_TIME_USE_AND_REPLAY.md`](../../repository/docs/design/action_clearance/ONE_TIME_USE_AND_REPLAY.md).

---

## 20–21. ActionGate, Decision Authority, and CER integration

Action Clearance consumes a **minimal authorization projection** derived from the frozen
`ActionGovernanceResult` (`outcome`, `constraints`, `obligations`, `expiry`, `fingerprint`,
`authority_basis`) plus stable references — it does not absorb ActionGate policy, Decision-Authority
logic, or the provider-framework adapter. Only `AUTHORIZED` / `AUTHORIZED_WITH_CONSTRAINTS` are eligible
inputs; `DENIED` / `INDETERMINATE` / `EXPIRED` are **never** reinterpreted as clearable. Mismatch of
parameters/target/artifact/operation/actor/policy-ref/expiration → fail-closed `BLOCK`.
[`ACTIONGATE_INTEGRATION.md`](../../repository/docs/design/action_clearance/ACTIONGATE_INTEGRATION.md).

For reconstructability the request carries references — `DecisionRecord` id, `cer_id`, CER
`content_hash`, `policy_refs`, authorized-actor basis, override/supersession refs. `DecisionRecord` and
CER live in `ugence_decision_authority`, so Action Clearance references them by **id/hash only** and
never imports Decision Authority. It does **not** revalidate segregation of duties (unless a
current-state actor signal requires it) and creates **no** duplicate decision record.
[`DECISION_AND_CER_INTEGRATION.md`](../../repository/docs/design/action_clearance/DECISION_AND_CER_INTEGRATION.md).

---

## 22. GPF relationship

**Action Clearance is a directly-invoked capability.** Signal adapters are product/integration
adapters. **No new `ProviderKind` is added** (the three peers — `ASSERTION_GOVERNANCE`,
`ACTION_GOVERNANCE`, `EXTERNAL_EXECUTION` — are unchanged). Adapters are registered and resolved by the
product/workflow layer, not by GPF, and GPF is given no authority over clearance.
[`GPF_RELATIONSHIP.md`](../../repository/docs/design/action_clearance/GPF_RELATIONSHIP.md).

---

## 23–24. GitHub merge profile & profile extensibility

The first product profile binds repository/org/installation identity, PR identity, base SHA, head SHA,
merge method, expected merge-tree, merge-group SHA (where applicable), target branch, required checks,
approval state, actor state, policy version, active-freeze state, active-incident state, and
authorization-consumption state — matching the Code Governance v0.2 artifact-binding set (§4.6 of
`UGENCE_CODE_GOVERNANCE_DESIGN_SPEC.md`). **MVP supports direct-merge and squash**; **rebase is
deferred** (no deterministic pre-merge exact-tree binding in MVP); **merge queue** authorizes the queue
entry, then clears the *exact merge-group artifact* — the original PR clearance never auto-authorizes a
changed merge-group. [`GITHUB_MERGE_PROFILE.md`](../../repository/docs/design/action_clearance/GITHUB_MERGE_PROFILE.md),
schema [`github_merge_profile.schema.json`](docs/design/action_clearance/github_merge_profile.schema.json).
Profiles add required signal types, profile reason codes, target identity, and profile policy — and may
only **narrow**, never broaden or subclass authority semantics:
[`PROFILE_EXTENSIBILITY.md`](../../repository/docs/design/action_clearance/PROFILE_EXTENSIBILITY.md).

---

## 25–26. Package boundary & existing-implementation disposition

Proposed (not created) layout under `packages/capabilities/action-clearance/` with
`src/ugence_action_clearance/{__init__,api,request,result,signals,policy,evaluator,reason_codes,fingerprint,errors,version}.py`
and `tests/`. Public API is curated and each symbol classified
`CORE_PUBLIC` / `PROFILE_PUBLIC` / `INTERNAL` / `ADAPTER_ONLY` / `UNNECESSARY`. Dependency direction is
downward only: recommended single optional dependency on `ugence-governance-contracts>=0.1.0` (to speak
the neutral `ActionGovernance*`/`EXPIRED` seam) with a stdlib-only-leaf fallback; **never** upward on
Code Governance, robotics, console API, execution providers, incident clients, identity clients,
workflow engines, Model Selection, or Hybrid LLM. [`PACKAGE_BOUNDARY.md`](../../repository/docs/design/action_clearance/PACKAGE_BOUNDARY.md).

Disposition of existing implementations — robotics Autonomous Control Plane:
`SEPARATE_CAPABILITY` · `NOT_A_SOURCE_MOVE` · `NO_COMPATIBILITY_ALIAS` · `LOCAL_FREEZE_UNCHANGED`
(reusable only as engineering-pattern evidence; grant-minting authority **not** reused); console
clearance: `BEHAVIORAL_REFERENCE` · `POTENTIAL_FUTURE_CONSUMER` · `NOT_AUTOMATIC_CANONICAL_SOURCE`
(preserve *Authorize → Clear → Record*); database `acp_db` adapter: future **profile/adapter**, no
runtime migration now. [`EXISTING_IMPLEMENTATION_DISPOSITION.md`](../../repository/docs/design/action_clearance/EXISTING_IMPLEMENTATION_DISPOSITION.md).

---

## 27. Security invariants & threat model

Eighteen mandatory security invariants (existing authorization required; exact action-identity match;
no broadening; fresh/trusted required signals; tenant+subject match; missing-mandatory fails closed;
clearance lifetime ≤ authorization/signal lifetime; deterministic + fingerprinted; no direct
external-state access, credentials, dispatch, or consumption in the core; execution atomically reserves
one-time use; stale/superseded clearance must not execute; new action fingerprint or changed
authorization requires new clearance; profile constraints may only narrow). Threat model covers replay,
TOCTOU, stale/forged signals, tenant confusion, source impersonation, action/target substitution,
policy downgrade, clock manipulation, duplicate dispatch, clearance reuse, missing receipt, incomplete
chain, and fail-open exception handling. [`SECURITY_INVARIANTS.md`](../../repository/docs/design/action_clearance/SECURITY_INVARIANTS.md),
[`THREAT_MODEL.md`](../../repository/docs/design/action_clearance/THREAT_MODEL.md).

---

## 28–29. State machine & failure handling

Evaluation flow: `REQUESTED → VALIDATING_AUTHORIZATION → VALIDATING_ACTION_IDENTITY →
VALIDATING_SIGNALS → EVALUATING_POLICY → (CLEAR | HOLD | BLOCK | ESCALATE)`. Durable receipt states:
`ISSUED → (EXPIRED | SUPERSEDED | REVOKED_BY_UPSTREAM_CHANGE)`. Authoritative execution-consumption
state is **not** inside the receipt. [`STATE_MACHINE.md`](../../repository/docs/design/action_clearance/STATE_MACHINE.md).

Failures are classified `RESULT` / `RETRYABLE_ERROR` / `NON_RETRYABLE_ERROR` / `ESCALATION` /
`UPSTREAM_REAUTHORIZATION_REQUIRED`. Expected operational problems produce fail-closed *results*;
programming errors and malformed contracts raise typed *exceptions*.
[`STATUS_AND_REASON_SEMANTICS.md`](../../repository/docs/design/action_clearance/STATUS_AND_REASON_SEMANTICS.md) §Failure-handling.

---

## 30. Acceptance scenarios

A deterministic 25-row behavioral matrix (valid→CLEAR; ActionGate-denied→no evaluation;
expiry/mismatch/freeze/incident/actor/signal/policy/consumption cases; validity shortened by signal
expiry; identical-request→identical fingerprint; reason-order-independent fingerprint; no widening; new
head SHA / regenerated merge group → new clearance; expired-before-dispatch → no dispatch; concurrent
dispatch → one reservation; superseded authorization → old clearance unusable). Narrative:
[`ACCEPTANCE_SCENARIOS.md`](../../repository/docs/design/action_clearance/ACCEPTANCE_SCENARIOS.md); machine-readable:
[`acceptance_scenarios.json`](docs/design/action_clearance/acceptance_scenarios.json).

---

## 31. Implementation sequence

Phases **A–I**: (A) package skeleton; (B) neutral contracts + deterministic evaluator; (C) in-memory
reference adapters; (D) ActionGate integration, shadow only; (E) durable receipts; (F) GitHub profile,
shadow; (G) execution-ledger integration (one-time reservation, replay protection); (H) Code Governance
enforced direct+squash merge; (I) merge queue + rebase. Each phase lists prerequisites, package
ownership, contracts, tests, acceptance criteria, rollback, and evidence tier. **Not executed here.**
[`IMPLEMENTATION_SEQUENCE.md`](../../repository/docs/design/action_clearance/IMPLEMENTATION_SEQUENCE.md).

---

## 32. Versioning

Proposed distribution version `0.1.0`; contract/policy version `action_clearance.v1` — design proposals,
not implementation facts. Compatibility policy for request/result schema, reason codes, signal types,
profile versions, and fingerprint algorithms; **no** compatibility promise to any existing robotics
import. [`VERSIONING.md`](../../repository/docs/design/action_clearance/VERSIONING.md).

---

## 33. Risks & open decisions

Ranked P0/P1/P2 and classed `DESIGN_BLOCKER` / `IMPLEMENTATION_PREREQUISITE` / `PILOT_RISK` /
`PRODUCTION_RISK` / `FUTURE_ENHANCEMENT`. The audit's three MIGRATION_BLOCKERs are **resolved by this
spec** (authority = clear-only; one contract family; neutral core + GitHub profile). Remaining P0/P1
implementation-prerequisites concern signal provenance, receipt persistence ownership, one-time-use
race handling, and the execution-ledger dependency. [`RISK_REGISTER.md`](../../repository/docs/design/action_clearance/RISK_REGISTER.md),
[`OPEN_QUESTIONS.md`](../../repository/docs/design/action_clearance/OPEN_QUESTIONS.md),
[`ROLLBACK.md`](../../repository/docs/design/action_clearance/ROLLBACK.md), machine-readable
[`design_decisions.json`](docs/design/action_clearance/design_decisions.json).

**Prerequisite closure (follow-on phase).** The four implementation-prerequisites above (signal
provenance, receipt persistence, receipt lifecycle, atomic one-time reservation) are closed at the
interface/contract level in the companion set under
[`docs/design/action_clearance_prerequisites/`](docs/design/action_clearance_prerequisites/) — see its
[`PREREQUISITE_CLOSURE_REPORT.md`](../../repository/docs/design/action_clearance_prerequisites/PREREQUISITE_CLOSURE_REPORT.md)
and machine-readable
[`implementation_gate.json`](docs/design/action_clearance_prerequisites/implementation_gate.json). That
phase concludes the package core may begin while durable atomic execution infrastructure remains an
enforcement prerequisite.

---

## 34–36. Deliverables, machine-readable rules, validation

The full companion set and six machine-readable artifacts live under
[`docs/design/action_clearance/`](docs/design/action_clearance/). All JSON is valid and marked
`status: PROPOSED`, `version: action_clearance.design.v0.1`; the schemas are **design artifacts, not
committed runtime contracts**. Validation results (terminology, doc-links, dependency-direction,
platform freeze, robotics local freeze, baseline tests, JSON validation, git status) are recorded in
[`EXECUTIVE_SUMMARY.md`](../../repository/docs/design/action_clearance/EXECUTIVE_SUMMARY.md) §Validation. The diff for
this phase contains only `ACTION_CLEARANCE_V0_1_DESIGN_SPEC.md`, `docs/design/action_clearance/**`, and
a single cross-reference line in `UGENCE_CODE_GOVERNANCE_DESIGN_SPEC.md` — no runtime file, no package,
no neutral-contract change, no `ProviderKind`, no compatibility shim, no robotics import change.

---

## Verdict

See [`EXECUTIVE_SUMMARY.md`](../../repository/docs/design/action_clearance/EXECUTIVE_SUMMARY.md) for the single verdict
line and the completion report.
