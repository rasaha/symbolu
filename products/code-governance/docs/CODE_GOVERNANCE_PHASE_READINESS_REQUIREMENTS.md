# Code Governance Phase Readiness Requirements

**Mandatory Evidence and Stage Gates for Shadow Pilot, Enforcement Foundation, Controlled Merge Execution, and Production Rollout**

> Machine-readable companion: [`../artifacts/code_governance_phase_readiness_requirements.json`](../artifacts/code_governance_phase_readiness_requirements.json).
> This is a governance-planning standard. It defines **no runtime behavior**, adds
> **no capability**, and **enables nothing**. Execution remains `DISABLED`. No gate
> verdict in this document, and no decision record derived from it, creates
> ActionGate execution authority.

---

## Executive summary

Ugence Code Governance has completed its read-only governance, durable audit,
pilot-operation, and study-analysis foundations (MVP 1A through MVP 1F, merged
through PR #1285). Every one of those phases is **implemented and
offline-verified**; none has been exercised against a live GitHub repository, a
live enterprise signal source, or a real human reviewer.

**What has been built.** A shadow governance path for source-control changes that
reconstructs the complete governance chain (change identity → evidence records →
claim manifest → Action Clearance evaluation → explicit authorized-actor decision
→ `ContextEnvelopeRecord` → `PreparedMergeAction` → ActionGate *shadow*
evaluation), a durable hash-linked audit store with restart recovery, read-only
enterprise-signal adapters, a security-bounded pilot operator, a bounded
pilot-study framework, an offline-verifiable evidence pack, and a deterministic
enforcement-readiness verdict framework.

**What has been proven.** That this pipeline runs deterministically offline, keeps
credentials out of every durable and reported surface, keeps execution disabled,
keeps Action Clearance and the shared platform unmodified, and reconstructs its
audit chain — all under offline tests and supplied snapshots.

**What has *not* been proven.** Anything that requires live signal. No live GitHub
collection has occurred. No live enterprise-signal collection has occurred. No
real reviewer has annotated a candidate. No customer value beyond existing GitHub
and CI controls has been demonstrated. The strongest honest evidence status today
is `IMPLEMENTED_AND_OFFLINE_VERIFIED`, and the standing readiness verdict is
`INSUFFICIENT_LIVE_EVIDENCE`.

**Why live evidence is mandatory.** Completing implementation tasks proves the
architecture is *buildable*, not that the product is *ready*. Offline tests,
supplied enterprise snapshots, synthetic scenarios, and mock reviewer feedback are
deliberately excluded from the live-evidence classes because none of them can
demonstrate real-source reliability, real reviewer judgement, or real incremental
value. Mistaking architecture momentum for product readiness is precisely the
failure this document exists to prevent.

**Why enforcement remains blocked.** Enforcement — atomic authorization
reservation (`reserve_once`), an authoritative consumption ledger, a GitHub
execution provider, and merge dispatch — must not begin until a real bounded pilot
has demonstrated safety, reliability, and credible incremental value. None of
those primitives exists yet, and none may be built until Gate 3 is passed with a
`READY_FOR_ENFORCEMENT_FOUNDATION` verdict.

**Exactly what the next authorized activity is.** Provision and run a **bounded
internal live GitHub shadow pilot** (Gate 1). That is the single next step. It
requires a dedicated read-only GitHub credential, explicit bounded pilot
authorization, and at least one real human reviewer — none of which has been
supplied. Enforcement development may begin only after live operational and
reviewer evidence demonstrates safety, reliability, and incremental value beyond
existing GitHub and CI controls.

---

## Document purpose

This document is the **authoritative stage-gate standard** for deciding whether
Code Governance may proceed from its current shadow-pilot state into the remaining
phases:

1. an internal live GitHub shadow pilot;
2. an external regulated-enterprise shadow pilot;
3. Phase 2A — enforcement foundation;
4. Phase 2B — controlled GitHub merge enforcement;
5. broader production rollout.

It exists to **prevent architecture momentum from being mistaken for product
readiness.** Two principles are non-negotiable:

- **Completion of implementation tasks does not automatically authorize
  progression to the next phase.**
- **Progression requires evidence that the previous phase achieved its intended
  operational and product outcome** — not merely that its code was written and its
  offline tests pass.

### Capability classifications (never interchangeable)

Progression decisions must distinguish these seven capability classifications.
They form a strict ladder; a higher rung is **never** implied by a lower one.

| Classification | Meaning | How it is earned |
|---|---|---|
| `IMPLEMENTED` | Code exists and imports. | A merged implementation. |
| `OFFLINE_VERIFIED` | Behavior proven by offline tests, supplied snapshots, and synthetic scenarios. | Green test suite; deterministic offline demo. |
| `LIVE_GITHUB_VERIFIED` | Proven against a real GitHub repository with a real read-only credential. | A bounded internal live pilot (Gate 1). |
| `LIVE_ENTERPRISE_VERIFIED` | Proven against at least one genuinely live non-GitHub enterprise source. | An external design-partner pilot (Gate 2). |
| `HUMAN_REVIEW_VALIDATED` | Real domain reviewers annotated real candidates under a frozen protocol. | Reviewer evidence collected in a live pilot. |
| `ENFORCEMENT_READY` | Atomic authorization reservation and consumption proven safe under concurrency and crash recovery. | Phase 2A completion (Gate 4 input). |
| `PRODUCTION_READY` | A controlled-execution canary ran without duplicate, unauthorized, or unreconciled execution. | Phase 2B canary (Gate 5). |

These classifications **must not be treated as interchangeable.** In particular,
`OFFLINE_VERIFIED` is not `LIVE_GITHUB_VERIFIED`; supplied enterprise snapshots are
not `LIVE_ENTERPRISE_VERIFIED`; mock reviewer feedback is not
`HUMAN_REVIEW_VALIDATED`; and no offline classification is ever `ENFORCEMENT_READY`
or `PRODUCTION_READY`.

This ladder aligns with the existing evidence-status vocabulary in
[`pilot_readiness_verdicts.json`](pilot_readiness_verdicts.json)
(`IMPLEMENTED`, `OFFLINE_VERIFIED`, `LIVE_GITHUB_VERIFIED`,
`LIVE_ENTERPRISE_SIGNAL_VERIFIED`, `REVIEWER_FEEDBACK_COLLECTED`, `NOT_RUN`,
`INSUFFICIENT_EVIDENCE`) and with the MVP 1F enforcement-readiness verdicts in
[`CODE_GOVERNANCE_ENFORCEMENT_READINESS.md`](CODE_GOVERNANCE_ENFORCEMENT_READINESS.md).

---

## Current-state assessment

This section records the **verified** repository state at the time of writing. It
is drawn from the repository itself, not from prior summaries.

**Verified repository facts**

| Fact | Verified value |
|---|---|
| Default branch | `claude/setup-symbolu-monorepo-014vhNMAoVW2Ys5RBBr3bKDF` |
| Default HEAD | `9ccbc6d419d4b49324a6d69bca2cdd21dd87ea36` (merge of PR #1285) |
| PR #1285 merged | Yes (merged 2026-08-02) |
| Code Governance version | `0.5.0` |
| Code Governance phase | MVP `1F` |
| Action Clearance version | `0.1.0` (contract `action_clearance.v1`) |
| Execution status | `DISABLED` (`EXECUTION_ENABLED = False`) |
| Pilot-operator capability | Present (`cg-pilot` CLI: version / validate / security-scan / health / study-validate / evidence-pack-verify) |
| Pilot-study capability | Present (`pilot_study/`: manifest, candidates, annotation, analysis, calibration, adverse, checkpoints, evidence pack, readiness) |
| Platform freeze substantive digest | `d4ad77e16516e0db6bf2faf3275c8ac8351644e7561d33f157bb55b5a174a1a6` (unchanged) |

### Implemented capabilities

- MVP 1A — shadow governance workflow, exact change identity, evidence records,
  claim manifest, chain reconstruction.
- MVP 1B — Action Clearance shadow integration (`ContextEnvelopeRecord` /
  `PreparedMergeAction` / ActionGate shadow evaluation).
- MVP 1C — durable, hash-linked, append-only SQLite shadow store with restart
  recovery and audit-bundle reconstruction.
- MVP 1D — read-only enterprise-signal adapters, a read-only transport boundary,
  and a bounded shadow-pilot runner with metrics and reporting.
- MVP 1E — a deployable, security-bounded pilot operator with lifecycle controls,
  preflight, health, recovery, scheduler, review queue, kill switch, and
  observability.
- MVP 1F — a bounded pilot-study framework: study manifest + freeze + amendments,
  evidence classification, candidate selection, reviewer protocol + annotations,
  metrics analysis, calibration + replay, adverse cases, checkpoints, an
  offline-verifiable evidence pack, and a deterministic enforcement-readiness
  verdict.

### Offline-verified capabilities

All of the above are `OFFLINE_VERIFIED`: the Code Governance test suite is green
(441 passed, 2 skipped), the offline demos run deterministically, the evidence
pack verifies offline, the credential-leak scanner and read-only security
inspection pass, and the platform freeze digest is unchanged.

### Live evidence collected

**None.** No live GitHub collection, no live enterprise-signal collection, and no
real reviewer annotation has occurred.

### Live evidence not collected

- No real live GitHub pilot has run.
- No live enterprise-signal pilot has run.
- No real reviewer annotations exist (only the frozen protocol and schemas).
- No demonstrated incremental value beyond existing GitHub and CI controls.

### Current execution status

`DISABLED`. There is no GitHub write path, no checks/status write path, no
`reserve_once`, no consumption ledger, no execution provider, and no external
production database.

### Current blockers

- A dedicated read-only GitHub credential (repository-scoped, no write
  permission, resolved only through the external credential reference) is not
  supplied.
- Explicit bounded live-pilot authorization is not supplied.
- A bounded live pilot configuration (tenant, repository, branch, candidate limit,
  window, concurrency, stop conditions, frozen policy/adapter/reviewer versions) is
  not supplied.
- At least one real human reviewer is not assigned.

### Permitted next activity

Provisioning and running a **bounded internal live GitHub shadow pilot** once
Gate 1 is satisfied — and nothing beyond it.

### Prohibited next activity

Starting enforcement design (Phase 2A), implementing `reserve_once` or a
consumption ledger, creating a GitHub execution provider, enabling any GitHub
write, or claiming enterprise validation. None of these is authorized.

### Direct answers to the required current-state questions

- **Is the internal live pilot operationally ready?** The tooling is
  operationally ready and offline-verified; the pilot is **not provisioned** (no
  credential, authorization, bounded configuration, or reviewer).
- **Has the internal live pilot actually run?** No.
- **Has external enterprise value been demonstrated?** No.
- **Is enforcement design currently justified?** No.

Live validation is **not** inferred from test counts. A green suite proves the
code behaves as written offline; it says nothing about live-source reliability,
reviewer judgement, or incremental value.

---

## Remaining progression path

```
Current shadow-pilot platform
        |
        v
Gate 1 — Internal Live GitHub Pilot Readiness
        |
        v
Internal Live GitHub Shadow Pilot
        |
        v
Gate 2 — External Design-Partner Pilot Readiness
        |
        v
Regulated-Enterprise Shadow Pilot
        |
        v
Gate 3 — Phase 2A Enforcement-Foundation Readiness
        |
        v
Phase 2A — Atomic Authorization and Consumption Safety
        |
        v
Gate 4 — Phase 2B Controlled-Execution Readiness
        |
        v
Phase 2B — Exact GitHub Merge Enforcement
        |
        v
Gate 5 — Production-Rollout Readiness
        |
        v
Bounded Production Deployment
```

No execution capability is added to the current phase. Each gate is a hard stop:
its verdict must be the explicit "ready" value before the phase after it may begin.

---

## Gate 1 — Internal Live GitHub Pilot Readiness

Requirements that must all hold before the **first internal live GitHub pilot** may
run.

### Technical baseline

- all Code Governance tests green;
- all Action Clearance tests green;
- pilot-operator and pilot-study tests green;
- package build and clean install verified;
- durable-store integrity verified;
- evidence-pack verification working;
- credential-leak scanner passing;
- read-only security inspection passing;
- execution status confirmed `DISABLED`.

### Credential requirements

- a dedicated read-only GitHub credential;
- repository-scoped access;
- no use of an ambient development or MCP credential;
- no write permission;
- resolved only through an external credential reference;
- no credential value in configuration, CLI arguments, logs, reports, durable
  records, exception messages, or evidence packs.

### Scope requirements

- one explicit tenant;
- one repository;
- one branch;
- a fixed candidate limit;
- a fixed start and end date;
- a fixed concurrency limit;
- fixed stop conditions;
- a fixed policy version;
- a fixed adapter version;
- a fixed reviewer protocol.

### Human requirements

- a named pilot operator;
- at least one real human reviewer;
- a documented reviewer role;
- a frozen reviewer protocol;
- reviewer feedback that is never simulated.

### Safety requirements

- a durable kill switch;
- pause, stop, and abort conditions;
- restart that does **not** auto-resume;
- no GitHub mutation API;
- no execution provider;
- no reservation;
- no consumption ledger.

### Gate 1 verdicts

- `READY_FOR_INTERNAL_LIVE_PILOT`
- `INTERNAL_PILOT_PROVISIONING_INCOMPLETE`
- `INTERNAL_PILOT_SAFETY_BLOCKED`

---

## Internal live-pilot exit criteria

What must be demonstrated before the internal pilot is considered **complete**.

Evidence of:

- successful live read-only GitHub collection;
- exact repository and PR binding;
- exact head-SHA binding;
- stale-head behavior;
- deterministic candidate selection;
- successful durable persistence;
- successful restart recovery;
- no automatic external call on recovery;
- real reviewer packet generation;
- real reviewer annotation collection;
- a verified evidence pack;
- zero credential leaks;
- zero GitHub mutations;
- zero unexplained integrity failures;
- execution disabled throughout.

### What an internal snapshot-backed pilot does and does not prove

An internal pilot that draws non-GitHub signals from **supplied enterprise
snapshots** proves:

- GitHub integration;
- workflow operation;
- exact-change binding;
- auditability;
- operator safety.

It does **not** prove:

- enterprise-source reliability;
- regulated-customer value;
- cross-system governance value;
- readiness for enforcement.

---

## Gate 2 — External regulated-enterprise pilot readiness

Requirements that must exist before involving a design partner.

### Product readiness

- internal live pilot completed;
- internal defects resolved;
- operator runbook validated;
- credential rotation tested;
- recovery tested;
- closeout tested;
- evidence pack reviewed;
- known limitations documented.

### Customer scope

- one regulated or payment-sensitive design partner;
- one or two repositories;
- GitHub Enterprise or an equivalent supported environment;
- an explicitly approved pilot owner;
- a security, risk, compliance, or change-management stakeholder;
- a clear data-handling agreement;
- a defined pilot start and end;
- defined success and stop criteria.

### Live enterprise sources

Prefer at least one genuinely **live** non-GitHub source, such as:

- identity or access status;
- incident state;
- release freeze or change window;
- target health;
- mandatory control status.

Supplied snapshots must remain **separately classified** and must never be
reported as live enterprise evidence.

### Reviewer requirements

- real domain reviewers;
- documented reviewer authority;
- conflict-of-interest handling;
- blinded initial assessment where practical;
- no mock reviewer feedback.

### Governance requirements

- a fixed policy version;
- a fixed intervention-routing version;
- an amendment process;
- no silent policy tuning;
- clear customer data minimization;
- no automatic policy learning.

### Gate 2 verdicts

- `READY_FOR_EXTERNAL_SHADOW_PILOT`
- `EXTERNAL_PILOT_PREREQUISITES_INCOMPLETE`
- `EXTERNAL_PILOT_SECURITY_OR_DATA_BLOCKED`

---

## External pilot exit criteria

The minimum evidence needed to complete the external pilot. Report each with
numerators, denominators, missing data, evidence classes, the reviewer protocol,
and limitations.

- live GitHub evaluation count;
- live enterprise-signal evaluation count;
- supplied-snapshot evaluation count;
- reviewer-feedback coverage;
- `CLEAR` / `HOLD` / `BLOCK` / `ESCALATE` distribution;
- possible unnecessary interventions;
- possible missed interventions;
- wrong-authority findings;
- source failures;
- stale-signal rate;
- source conflicts;
- identity mismatches;
- adverse cases;
- policy defects;
- adapter defects;
- incremental value beyond GitHub and CI;
- operational reliability;
- audit reconstruction completeness;
- credential and integrity results.

**Do not impose unsupported universal accuracy thresholds.** Consistent with the
MVP 1F metrics policy, no precision / recall / accuracy figure is reported without a
defensible protocol, and every figure carries its numerator, denominator, missing
data, and evidence class.

---

## Product-value gate

Before any enforcement work, credible evidence must show that Ugence adds value
**beyond existing controls.** At least one of these must be demonstrated with
explicit evidence references:

- a governance condition missed by existing CI;
- exact-SHA approval protection not already guaranteed by existing controls;
- useful cross-system operational context;
- correct authority routing not provided by the existing workflow;
- earlier detection of a governance problem;
- reduction of unnecessary specialist review;
- stronger audit reconstruction;
- improved oversight of **explicitly identified** AI-assisted changes (never
  inferred without explicit provenance).

A duplicated GitHub rule does **not** count as unique value. When no incremental
value is demonstrated, the required verdict is:

- `PRODUCT_VALUE_NOT_PROVEN`

---

## Gate 3 — Phase 2A enforcement-foundation readiness

Phase 2A must remain **blocked** unless all mandatory requirements below are
satisfied.

### Live evidence

- external live pilot completed, or an explicitly justified equivalent;
- sufficient real reviewer evidence;
- at least some credible incremental value;
- source reliability understood;
- policy disagreements categorized;
- no unresolved serious possible false `CLEAR`;
- no unresolved integrity or credential concern.

### Architecture readiness

- exact authorized-action model stable;
- ActionGate authorization binding stable;
- Action Clearance result model stable;
- exact repository, PR, base SHA, head SHA, merge method, and expiry binding
  defined;
- durable receipt requirements documented;
- cancellation and expiry semantics defined;
- concurrency model documented;
- crash-recovery model documented.

### Governance approval

- security review completed;
- architecture review completed;
- product-value review completed;
- pilot evidence reviewed;
- explicit written approval to begin enforcement-foundation design.

### Gate 3 verdicts

- `READY_FOR_ENFORCEMENT_FOUNDATION`
- `PILOT_CALIBRATION_REQUIRED`
- `PRODUCT_VALUE_NOT_PROVEN`
- `INSUFFICIENT_LIVE_EVIDENCE`
- `SAFETY_OR_INTEGRITY_BLOCKED`

Only `READY_FOR_ENFORCEMENT_FOUNDATION` permits Phase 2A to begin. (This gate
verdict is distinct from, and stricter than, the MVP 1F
`READY_FOR_ENFORCEMENT_DESIGN` study verdict: the study verdict may authorize
*design analysis*, whereas this gate authorizes beginning the Phase 2A
enforcement-foundation implementation.)

---

## Phase 2A permitted scope

Phase 2A **may** implement:

- a durable enforcement-grade clearance receipt;
- atomic `reserve_once`;
- a one-time authorization reservation;
- an authoritative consumption ledger;
- expiry and cancellation;
- concurrency protection;
- crash recovery;
- an execution-reconciliation model;
- tamper-evident authoritative records.

Phase 2A **must not yet** implement:

- GitHub merge dispatch;
- GitHub pull-request mutation;
- deployment execution;
- a broad execution-provider framework;
- automatic enforcement rollout.

Phase 2A proves that authorization can be **reserved and consumed safely** before
any external action is added. Execution stays `DISABLED` throughout Phase 2A.

---

## Gate 4 — Phase 2B controlled-execution readiness

Requirements before creating a GitHub execution provider.

- Phase 2A completed;
- atomic reservation proven under concurrency;
- duplicate consumption impossible under tested conditions;
- crash recovery proven;
- reconciliation proven;
- authorization expiry enforced;
- cancellation enforced;
- receipt and ledger integrity verified;
- security review completed;
- threat model completed;
- a narrow GitHub credential strategy approved;
- the exact merge operation defined;
- the exact merge method bound;
- pre-dispatch live clearance required;
- post-dispatch outcome reconciliation defined;
- kill switch tested;
- rollback and incident procedure documented.

### Gate 4 verdicts

- `READY_FOR_CONTROLLED_EXECUTION`
- `ENFORCEMENT_FOUNDATION_INCOMPLETE`
- `EXECUTION_SECURITY_BLOCKED`
- `EXECUTION_RECONCILIATION_BLOCKED`

---

## Phase 2B permitted initial scope

The first controlled-execution implementation must be **narrowly bounded**:

- one tenant;
- one repository;
- one protected branch;
- explicit allowlisted PRs;
- an exact head SHA;
- one approved merge method;
- an explicit authorized actor;
- a final Action Clearance check;
- an atomic reservation before dispatch;
- immediate result reconciliation;
- a durable execution receipt;
- a kill switch;
- a canary rollout.

Prohibited initially:

- organization-wide rollout;
- multiple source-control providers;
- automatic deployments;
- arbitrary GitHub mutations;
- issue modification;
- label modification;
- reviewer assignment;
- free-form agent actions;
- bypass of branch protection.

---

## Gate 5 — Production rollout readiness

Requirements before expanding beyond a bounded enforcement canary.

- a successful controlled-execution canary;
- no duplicate execution;
- no unauthorized execution;
- no unexplained reservation inconsistency;
- reconciliation completeness;
- acceptable operational reliability;
- tested credential rotation;
- tested kill switch;
- tested disaster recovery;
- tested audit export;
- an incident-response runbook;
- a tenant-isolation review;
- a customer security review;
- a capacity and concurrency review;
- a data-retention policy;
- support ownership;
- monitoring and alerting;
- change-management approval.

### Gate 5 verdicts

- `READY_FOR_BOUNDED_PRODUCTION`
- `CONTINUE_CANARY`
- `PRODUCTION_SAFETY_BLOCKED`
- `PRODUCTION_OPERATIONS_INCOMPLETE`

---

## Mandatory stop conditions across all phases

A single, non-negotiable blocker list. Progression **must stop** for any of:

- a credential leak;
- a GitHub write outside an explicitly approved execution phase;
- an unexplained store-integrity failure;
- cross-tenant exposure;
- a manifest or policy fingerprint mismatch;
- an unresolved serious possible false `CLEAR`;
- reviewer-feedback fabrication;
- synthetic evidence reported as live;
- a supplied snapshot reported as live enterprise evidence;
- failure to bind the exact head SHA;
- inability to reconstruct the audit chain;
- an unauthorized policy change during a pilot;
- a missing kill switch;
- an execution-enabled state in a shadow phase;
- reservation or consumption ambiguity;
- duplicate-execution risk;
- missing reconciliation.

Any one of these halts progression until it is resolved and the resolution is
recorded in a phase decision record.

---

## Decision authority and sign-off

Each gate has responsible sign-off roles.

### Suggested roles

- Product owner
- Code Governance technical owner
- Security reviewer
- Pilot operator
- Customer or design-partner representative
- Domain reviewer
- Compliance or risk reviewer, where applicable
- Enforcement architecture reviewer
- Production operations owner

### Clarifications

- **Assignment is not approval.** Naming a reviewer does not constitute a passing
  verdict.
- **Reviewer feedback is not a binding `DecisionRecord`.** Reviewer annotations
  inform a gate; they do not authorize progression.
- **Technical test completion is not product approval.** A green suite is
  necessary, never sufficient.
- **A readiness verdict must identify who approved progression.** Every
  progression carries named approvers.

### Gate sign-off table

| Gate | Required approvers | Required evidence pack | Required unresolved-issue status | Permitted next activity | Prohibited next activity |
|---|---|---|---|---|---|
| Gate 1 — Internal live pilot | Code Governance technical owner; Security reviewer; Pilot operator | Offline verification report; read-only security scan; credential-boundary attestation | No open safety or credential blocker | Run bounded internal live GitHub shadow pilot | Any GitHub write; enforcement work; external customer data |
| Gate 2 — External pilot | Product owner; Security reviewer; Compliance/risk reviewer; Design-partner representative | Internal live-pilot evidence pack; runbook + recovery + rotation attestations; data-handling agreement | No open security or data blocker | Run bounded external regulated-enterprise shadow pilot | Enforcement work; automatic policy tuning; snapshot-as-live reporting |
| Gate 3 — Phase 2A | Product owner; CG technical owner; Security reviewer; Enforcement architecture reviewer | External (or justified-equivalent) live-pilot evidence pack; architecture + security + product-value reviews | No unresolved serious possible false `CLEAR`; no integrity/credential concern | Begin Phase 2A enforcement-foundation design + implementation | GitHub merge dispatch; execution-provider framework; any write |
| Gate 4 — Phase 2B | Product owner; Security reviewer; Enforcement architecture reviewer; Production operations owner | Phase 2A reservation/ledger integrity + concurrency + recovery proofs; threat model | No reconciliation or reservation ambiguity | Create bounded GitHub execution provider + controlled canary | Org-wide rollout; arbitrary mutations; branch-protection bypass |
| Gate 5 — Production | Product owner; Security reviewer; Production operations owner; Compliance/risk reviewer | Canary execution receipts; reconciliation completeness; DR + rotation + audit-export attestations | No duplicate/unauthorized execution; no reservation inconsistency | Bounded production deployment | Unbounded rollout; multi-provider expansion; automatic deployment |

---

## Readiness evidence matrix

Stable requirement IDs. A requirement is **never** marked complete without a
repository or pilot-evidence reference.

| Requirement ID | Requirement | Applicable gate | Evidence required | Evidence class | Owner | Pass condition | Failure condition | Blocking severity | Status | Evidence reference |
|---|---|---|---|---|---|---|---|---|---|---|
| G1-SEC-001 | Dedicated read-only GitHub credential, no ambient/MCP credential, resolved only via external reference | Gate 1 | Credential-boundary attestation; leak-scanner pass | `OFFLINE_VERIFIED` → attestation | Security reviewer | Read-only, repo-scoped, no value in any surface | Any write scope or value leak | BLOCKER | NOT_MET | — |
| G1-OPS-001 | Baseline green + build + clean install + durable integrity + evidence-pack verify + execution `DISABLED` | Gate 1 | Test run; freeze verifier; CLI smoke | `OFFLINE_VERIFIED` | Pilot operator | All green; digest unchanged; `DISABLED` | Any failure or execution enabled | BLOCKER | MET | Suite 441 passed/2 skipped; freeze digest `d4ad77e1…` |
| G1-OPS-002 | Bounded live configuration (tenant/repo/branch/limit/window/concurrency/stop conditions/frozen versions) | Gate 1 | Study manifest freeze | attestation | Pilot operator | Fully bounded, fail-closed | Wildcard/unbounded/missing field | BLOCKER | NOT_MET | — |
| G1-HUM-001 | Named pilot operator + at least one real human reviewer under frozen protocol | Gate 1 | Reviewer assignment; frozen protocol | `HUMAN_REVIEW_VALIDATED` (on completion) | Product owner | Real reviewer assigned; protocol frozen | No real reviewer; simulated feedback | BLOCKER | NOT_MET | — |
| G1-SAFE-001 | Durable kill switch; pause/stop/abort; no auto-resume on restart | Gate 1 | Operator safety test | `OFFLINE_VERIFIED` | Pilot operator | Kill switch + no auto-resume proven | Missing kill switch or auto-resume | BLOCKER | MET | MVP 1E operator tests |
| G2-LIVE-001 | Internal live pilot completed with live GitHub evidence | Gate 2 | Internal pilot evidence pack | `LIVE_GITHUB_VERIFIED` | Pilot operator | Live GitHub collection + verified pack | No live pilot run | BLOCKER | NOT_MET | — |
| G2-LIVE-002 | At least one genuinely live non-GitHub enterprise source | Gate 2 | Live source collection record | `LIVE_ENTERPRISE_VERIFIED` | CG technical owner | ≥1 live enterprise source, separately classified | Snapshot reported as live | BLOCKER | NOT_MET | — |
| G2-VAL-001 | Data-handling agreement + approved pilot owner + stakeholder | Gate 2 | Signed agreement | attestation | Compliance/risk reviewer | Agreement + owners in place | Missing agreement or owner | BLOCKER | NOT_MET | — |
| G3-EVID-001 | Sufficient real reviewer evidence; no unresolved serious possible false `CLEAR` | Gate 3 | Reviewer annotations; adverse-case review | `HUMAN_REVIEW_VALIDATED` | Domain reviewer | Adequate coverage; blockers resolved | Unresolved serious false `CLEAR` | BLOCKER | NOT_MET | — |
| G3-VAL-001 | Credible incremental value beyond GitHub/CI demonstrated | Gate 3 (product-value) | Value evidence references | `LIVE_*_VERIFIED` | Product owner | ≥1 value item with evidence ref | No incremental value | BLOCKER | NOT_MET | — |
| G3-ARCH-001 | Exact action / ActionGate / clearance model + receipt/expiry/concurrency/recovery documented and stable | Gate 3 | Architecture review | design review | Enforcement architecture reviewer | Reviewed + stable | Unstable or undocumented | BLOCKER | NOT_MET | — |
| G4-ATOMIC-001 | Atomic reservation proven under concurrency; duplicate consumption impossible | Gate 4 | Phase 2A concurrency proofs | `ENFORCEMENT_READY` | Enforcement architecture reviewer | No duplicate consumption under test | Any duplicate/ambiguity | BLOCKER | NOT_MET | — |
| G4-EXEC-001 | Threat model + narrow credential strategy + reconciliation defined; kill switch tested | Gate 4 | Threat model; reconciliation design | security review | Security reviewer | Reviewed + tested | Missing reconciliation or threat model | BLOCKER | NOT_MET | — |
| G5-PROD-001 | Canary ran with no duplicate/unauthorized/unreconciled execution; DR + rotation + audit export tested | Gate 5 | Canary execution receipts | `PRODUCTION_READY` | Production operations owner | Clean canary; all operational reviews pass | Any unauthorized/duplicate execution | BLOCKER | NOT_MET | — |

---

## Phase decision records

Standard template for every progression decision.

| Field | Content |
|---|---|
| Decision ID | Stable identifier (e.g. `PDR-G1-0001`) |
| Gate | Which gate this decision concerns |
| Decision date | Date of the decision |
| Current phase | Phase the product is in |
| Requested next phase | Phase requested to begin |
| Evidence reviewed | Evidence packs and references reviewed |
| Evidence status | Capability classification(s) of the evidence |
| Unresolved risks | Open risks and their severity |
| Exceptions | Any granted exceptions and their justification |
| Approvers | Named approvers per the gate sign-off table |
| Decision | One of the allowed decisions below |
| Conditions | Conditions attached to an `APPROVE_WITH_CONDITIONS` |
| Expiry or re-review date | When the decision must be revisited |
| Decision fingerprint | Domain-separated hash binding the decision inputs |

### Allowed decisions

- `APPROVE_PROGRESSION`
- `APPROVE_WITH_CONDITIONS`
- `HOLD_FOR_EVIDENCE`
- `REQUIRE_CALIBRATION`
- `REJECT_PROGRESSION`
- `SAFETY_BLOCK`

**A decision record must not itself create ActionGate execution authority.** It
records a human governance decision about *progression*; it never authorizes,
reserves, or consumes an execution.

---

## Current readiness verdict

Assessed from repository evidence at the time of writing.

- **Current capability:** `IMPLEMENTED_AND_OFFLINE_VERIFIED`
- **Current readiness:** `READY_FOR_INTERNAL_LIVE_PILOT_PROVISIONING`
- **Current blocker:** A dedicated read-only credential, explicit pilot
  authorization, a bounded live configuration, and real reviewer participation are
  not yet supplied.
- **Not currently ready for:**
  - External enterprise validation
  - Phase 2A enforcement foundation
  - Phase 2B controlled execution
  - Production rollout

This document does **not** mark `READY_FOR_ENFORCEMENT_FOUNDATION`. No qualifying
live evidence exists, so that verdict cannot honestly be reached. The strongest
supportable position today is that the tooling is ready to be *provisioned* for a
bounded internal live pilot — nothing further.
