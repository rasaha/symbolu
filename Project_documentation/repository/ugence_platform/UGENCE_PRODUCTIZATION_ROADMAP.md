# Ugence AI Control Plane — Productization Roadmap
### Internal / data-room document — not for first investor contact

> **Terminology update — Ugence Decision Governance (2026-08-01).** Per
> [`Project_documentation/repository/docs/architecture/ADR_UGENCE_DECISION_GOVERNANCE_TERMINOLOGY_AND_BOUNDARIES.md`](../docs/architecture/ADR_UGENCE_DECISION_GOVERNANCE_TERMINOLOGY_AND_BOUNDARIES.md):
> the canonical **umbrella** is **Ugence Decision Governance**; the **AI Control Plane** named in this
> title is the **optional, bypassable** administration & coordination layer, not the umbrella and not a
> universal authority. The "Decision Governance kernel" listed below is the **Decision Authority**
> capability (`decision_governance` package, name unchanged). **Model Selection** is a distinct
> capability, separate from Hybrid LLM. Documentation-only; nothing is renamed.

*Purpose: answer the question every investor asks after the first look — "what
exactly must be built, in what order, by whom, and in how many months?" — and derive
the pre-seed round size **bottom-up** rather than by convention.*

> **How to use this document.** It converts the implemented, internally-validated
> modules (see the Ugence Technical Evidence Catalogue) into one enterprise-
> deployable v1 product over an **18-month** plan. Every cost figure marked
> **⟨assumption⟩** is an illustrative placeholder to be replaced with a real quote
> before circulation. The round size is the *output* of the model in §8, not an
> input.

---

## 1 · Starting point — current reusable components

What already exists and can be reused, versus what must be built to make it a
product. (Maturity labels per the Technical Evidence Catalogue.)

| Component | Reuse status | What is proven today |
|---|---|---|
| **ActionGate** | Reusable core | Deterministic action authorization; 274 tests; 27/27 red-team blocked; Kubernetes surface |
| **Autonomous Control Plane (ACP)** | Reusable core | Operational-safety clearance; runtime-independent; cross-domain; shadow-only against fixtures |
| **Decision Governance kernel** | Reusable core | Version-frozen kernel (v1.0.0); AI-advisory/human-binding separation; identity-preserving |
| **Agent Runtime + CER contract** | Reusable core | Canonical Execution Request; identical identity across 3 real runtimes; 1,550+ tests |
| **Truth Assurance Platform (TAP)** | Partial (prototype) | Claim/scope/evidence layers prototyped on synthetic data; one layer only |
| **Context Minimization** | Reusable accelerator | Authorization-preserving compression; cross-model; frozen benchmark |
| **KVPro** | Reusable accelerator | int4_protected codec on real GPUs; ~1.8× net density |
| **Model Selection policy** | Reusable accelerator | Governed selection; passes pre-registered criteria (synthetic) |

**Read:** the *reasoning/governance mechanisms exist*. What does **not** yet exist is
the connective tissue that makes them one operable product: shared services, a
console, connectors, durable persistence, identity, and the fully-wired
decision→action→execution→reconciliation loop against live systems.

---

## 2 · Integration gaps (what must be built)

The gaps between "modules that pass tests" and "one product a customer runs":

1. **The live governed loop.** Decision Governance → CER → ActionGate → ACP →
   execution → reconciliation is proven *in parts and on fixtures*; it is not wired
   end-to-end against a live execution target. **(Highest priority.)**
2. **Shared identity & multi-tenancy.** Today: static identity stand-ins, single-host
   stores. Needed: multi-tenant identity, organization isolation, real approver
   identity.
3. **Durable, tamper-evident persistence.** Today: in-memory repositories, reference
   HMAC signing. Needed: durable append-only audit with a real hash-chain and key
   custody.
4. **Unified control surface.** No admin console today. Needed: one console for
   policy, review queues, findings, and audit reconstruction. *(Sequenced as the
   Governed Agent Studio in §11.)*
5. **Standard external APIs & canonical contracts.** Internal contracts exist (CER);
   needed: stable public APIs and versioned contracts across modules.
6. **Connectors.** Needed: two runtime connectors (native + one third-party adapter,
   both partly demonstrated) and one governed execution-target connector (Kubernetes).
7. **Deployment modes as product features.** Shadow / recommendation / enforcement
   exist conceptually; needed as first-class, per-control configuration.
8. **Security & observability.** External security review, access control,
   logging/metrics/tracing, deployment tooling.

---

## 3 · Shared platform services required

The services all modules will depend on (the bulk of "product consolidation"):

- **Identity & tenancy** — multi-tenant identity, org isolation, RBAC for operators,
  approver identity binding.
- **Policy service** — author/version/publish policies and rubrics with segregation
  of duties.
- **Evidence & audit service** — durable, tamper-evident, replayable records;
  reconstruction API.
- **Canonical contract layer** — CER + decision identities exposed as stable APIs.
- **Console** — operator UI for policy, review, findings, audit reconstruction.
- **Connector framework** — runtime adapters + execution-target adapters.

---

## 4 · v1 scope — ships vs deferred

| Ships in enterprise-deployable v1 | Deferred (post-v1 / domain packages) |
|---|---|
| Multi-tenant identity + org isolation | Additional systems-of-record connectors (ATS, HRIS, claims, finance) |
| Durable, tamper-evident audit | Autonomous Runtime (robotics) productization |
| Secure public APIs + canonical contracts | PSE and other adjacent IP |
| Two runtime connectors | Broad multi-cloud execution targets (AWS, GCP, Terraform) beyond Kubernetes |
| One enterprise identity integration | TAP hardened beyond first prototype layer (staged in) |
| One governed execution-target connector (Kubernetes) | Model Selection as a separately-sold product |
| Shadow + controlled enforcement for selected actions | Full regulated-industry certification |
| Console (policy · review · findings · audit) | |

**v1 anchors on the infrastructure-agent wedge** (Kubernetes execution target). TAP
enters v1 in a limited, staged form; Decision Governance ships with the hiring
reference plus one live infrastructure workflow.

---

## 5 · Quarterly milestones (18 months = 6 quarters)

| Quarter | Theme | Exit criteria |
|---|---|---|
| **Q1** | Foundations | Shared identity/tenancy scaffold; persistence + tamper-evident audit backend; API contracts frozen; team core hired |
| **Q2** | Live governed loop | End-to-end Decision→CER→ActionGate→ACP→execution→reconciliation wired against Kubernetes in shadow |
| **Q3** | Console + connectors | Operator console v1; two runtime connectors; enterprise identity integration; first design-partner in shadow |
| **Q4** | Enterprise readiness | External security review; observability/deployment tooling; controlled enforcement for selected actions; 1st pilot findings report |
| **Q5** | Pilot scale + enforcement | 2–3 paid pilots running; first shadow→enforcement conversion; second-domain kernel reuse demonstrated |
| **Q6** | v1 GA + proof | Enterprise-deployable v1 GA; ≥1 paid enforcement deployment; measured false-positive/false-block + audit-reconstruction results |

*The Governed Agent Studio and the durable-execution engine beneath it are sequenced
separately in §11; that sequence is engineering-ordered and is not mapped onto these
quarters here.*

---

## 6 · Staffing plan & ramp

Small team focused on converting existing technology into a deployable product.

| Role | Start | Active months (of 18) |
|---|---|---|
| Founder (product + architecture) | M1 | 18 |
| Founding product / platform eng lead | M1 | 18 |
| Enterprise integration engineer #1 | M2 | 17 |
| Product designer / frontend (console) | M3 | 16 |
| Security & compliance lead (fractional ≈0.5 FTE) | M4 | 15 |
| Enterprise integration engineer #2 | M5 | 14 |
| Founding enterprise GTM / design-partner lead | M7 | 12 |

---

## 7 · Pilot dependencies

- **v1 loop wired** (Q2) before any enforcement; shadow can begin once identity +
  audit + one runtime connector exist (late Q2/Q3).
- **Design partner:** a GCC/enterprise with a Kubernetes-acting agent and an
  identified sponsor + approval group.
- **Access:** read-only telemetry (Prometheus/cluster state) for shadow; scoped
  credentials for controlled enforcement.
- **Data processing / security sign-off** from the partner before enforcement mode.

---

## 8 · Bottom-up budget → round size

> **All figures ⟨assumption⟩ — replace with real quotes (Hyderabad market, actual
> cloud/GPU usage, real vendor bids).** FX ⟨assumption⟩ ≈ ₹83 / US$1. The round size
> is the model's output.

### 8a · Payroll (fully-loaded, 18 months)

| Role | ⟨assumption⟩ ₹/month | Active mo | Total (₹L) |
|---|---:|---:|---:|
| Founder | 2.0 | 18 | 36.0 |
| Product / platform eng lead | 3.3 | 18 | 59.4 |
| Integration engineer #1 | 2.1 | 17 | 35.7 |
| Integration engineer #2 | 2.1 | 14 | 29.4 |
| Product designer / frontend | 1.9 | 16 | 30.4 |
| Security & compliance (0.5 FTE) | 1.25 | 15 | 18.8 |
| GTM / design-partner lead | 2.5 | 12 | 30.0 |
| **Payroll subtotal** | | | **≈ ₹239.7L (₹2.40 Cr · ~$289K)** |

### 8b · Non-payroll (18 months)

| Category | ⟨assumption⟩ Total (₹L) |
|---|---:|
| Cloud + GPU (dev, KVPro benchmarking, pilot infra) | 36 |
| External security review / pen-test | 15 |
| Legal / IP / patents / incorporation | 20 |
| Pilot integration & travel (2–3 partners) | 15 |
| Tools / SaaS / infra | 10 |
| GTM / marketing / events | 10 |
| **Non-payroll subtotal** | **≈ ₹106L (~$128K)** |

### 8c · Total and round size

| Line | ₹ | US$ |
|---|---:|---:|
| Payroll subtotal | 2.40 Cr | ~$289K |
| Non-payroll subtotal | 1.06 Cr | ~$128K |
| **Subtotal** | **3.46 Cr** | **~$417K** |
| Contingency (15%) | 0.52 Cr | ~$63K |
| **18-month total** | **≈ 3.98 Cr** | **≈ $480K** |

**Working-estimate pre-seed raise: ≈ ₹5 Cr (~US$600K)** — the 18-month total plus
buffer, sized to reach the **first paid enforcement deployment** with runway to
spare rather than to the next unfinished prototype.

> **This is a working estimate, not a confirmed raise.** Every §8 input is an
> ⟨assumption⟩. The final amount will be set once Hyderabad hiring, cloud/GPU
> infrastructure, security/compliance, and legal/IP costs are replaced with current
> quotes. Directionally reasonable; not yet validated.

**Allocation vs the first-look 55 / 25 / 20 split** (sanity check, at ₹5 Cr):
Product consolidation ~₹2.75 Cr · Enterprise readiness ~₹1.25 Cr · Commercial
validation ~₹1.0 Cr — consistent, since product-role payroll dominates.

---

## 9 · Product acceptance criteria (v1 "done")

v1 is complete when, for the Kubernetes infrastructure-agent wedge:

1. A proposed agent action flows Decision→CER→ActionGate→ACP→execution→reconciliation
   **end-to-end against a live target**, with each stage recorded.
2. Multi-tenant identity + org isolation enforced; approvals bound to real approver
   identity.
3. Audit records are durable, tamper-evident, and reconstruct a complete decision
   chain on demand.
4. Shadow, recommendation, and enforcement modes are per-control configurable.
5. Two runtime connectors + one Kubernetes execution-target connector operate in a
   customer environment.
6. An external security review is passed at an agreed bar.
7. ≥1 paid pilot has produced a findings report; ≥1 control has run in enforcement.

---

## 10 · Risks & contingency

- **Integration underestimated** — the live loop (Q2) is the critical path; slip here
  cascades. *Mitigation:* wire the thinnest end-to-end path first; harden later.
- **Pilot access latency** — enterprise security sign-off can be slow. *Mitigation:*
  start shadow (read-only) early; sequence enforcement after trust is built.
- **Hiring in a competitive market** — *Mitigation:* fractional security/compliance;
  contractors for surge; stagger starts (see §6).
- **Scope creep into new domains** — *Mitigation:* v1 is Kubernetes-only; all other
  systems-of-record are explicitly deferred (§4).
- **Cost assumptions** — every figure in §8 is ⟨assumption⟩; the round should be
  re-derived once real quotes land.

---

## 11 · Governed Agent Studio and durable execution

> **Scope note.** This section sequences the Governed Agent Studio and the durable
> execution engine beneath it. It is an engineering sequencing record, not a budget
> input: it adds no line to §8 and re-derives no figure in §8c. Each item carries its
> own status row; GAS-1 through GAS-4 are implemented and merged, GAS-5 is deferred by
> owner ruling, GAS-6 is gated, GAS-7 is scoped and ruled with no step entered. Nothing
> in it is piloted or certified. Evidence labels
> follow the repository convention — `[V]` verified against
> this repository, `[I]` inferred, `[R]` requires owner ratification, `[G]` gap.
>
> **Why this section is here rather than in the research roadmap.** `[V]`
> `Project_documentation/repository/roadmap/IMPLEMENTATION_ROADMAP.md` is the
> Symbol-U *scientific* execution plan (Milestones A–G, "documentation only",
> "Stage A untouched"); it names no Ugence capability. Product delivery sequencing
> belongs here.

### 11.0 Ratified frame (owner, this programme)

These are settled and are not reopened by any item below.

| # | Ratified decision |
|---|---|
| GAS-R1 | **DBOS is the initial standalone durable-execution engine**, and is a **candidate** until every row of the durability and failure matrix in `docs/architecture/ADR_DBOS_DURABLE_EXECUTION_INTEGRATION.md` has passing evidence. |
| GAS-R2 | **Temporal is the future regulated-enterprise adapter.** The execution adapter must make that swap possible without touching Workflow IR, governance state or receipts. |
| GAS-R3 | **React Flow is the Ugence-owned studio canvas**, added as a feature inside `apps/ugence-governance-studio`. No third app; no Langflow fork. |
| GAS-R4 | **Langflow is an import source only.** Its exported JSON is untrusted input: validate, never execute, compile to Workflow IR. The import itself is **deferred and customer-gated** (GAS-5 ruling, §11.3); this frame binds any future adapter. |
| GAS-R5 | **Workflow IR and governance state are always owned by Ugence.** The engine owns scheduling and recovery only; Agent Runtime owns proposal binding, the governance hook, budgets, checkpoints and receipts. The engine is never the source of truth for governance state. |
| GAS-R6 | **The governance hook runs inside the durable step.** The engine executes Agent Runtime transitions; Agent Runtime calls the hook before any provider invocation, so a retry can never replay a consequential call without re-clearing it. |

### 11.1 Sequence

Items run in order. Each states its entry criteria, its exit criteria, and the
**maturity label it may claim on completion** — drawn from the Appendix B stage
vocabulary in `docs/UGENCE_ENTERPRISE_AI_GOVERNANCE_CAPABILITY_PIPELINE.md` §B.2.
No item may claim a label above the one listed, and no item may claim
*Pilot-validated* or *Production-certified* at all within this section.

#### GAS-1 · DBOS integration ADR and failure matrix — **documents only**

| | |
|---|---|
| **Entry** | This section ratified; the five owner decisions in §11.3 ruled. |
| **Work** | `docs/architecture/ADR_DBOS_DURABLE_EXECUTION_INTEGRATION.md`: ownership boundary, the execution-adapter Protocols, the store mapping, hook-inside-step semantics, the Temporal replacement contract, and the complete durability and failure matrix. |
| **Exit** | The ADR is committed; every matrix row names an expected fail-closed behaviour **and** the evidence artefact that would prove it; no row is left as prose without an evidence column. |
| **Label on completion** | **Contract-only.** A committed ADR authorizes implementation; it is not implementation. |

#### GAS-2 · Execution adapter and DBOS-backed stores for Agent Runtime

| | |
|---|---|
| **Entry** | GAS-1 committed. A local Postgres is available in CI. |
| **Work** | The neutral `DurableExecutionAdapter` Protocols in a new integration package; a DBOS-backed implementation; Postgres-backed `CheckpointStore`, `RuntimeEventStore` and `RuntimeStateStore` behind the existing Agent Runtime Protocols `[V]` (`packages/runtime/agent-runtime/src/ugence_agent_runtime/persistence/interfaces.py`). Every matrix row from GAS-1 lands as an executing test. |
| **Exit** | Every GAS-1 matrix row has a passing CI test against a real local Postgres, including the crash, duplicate-delivery, expiry, revocation, Postgres-unavailable, budget-contention, long-pause, version-change and clock-skew rows. `packages/runtime/agent-runtime` gains **no** new import `[V]` — the adapter depends on the runtime, never the reverse. |
| **Status (2026-09-05)** | **Implemented; all eleven matrix rows green in CI** against a real PostgreSQL (durable-execution-ci job 101257085510 on `fe6f1591`: matrix 29 passed, no row skipped; Agent Runtime byte-unchanged, 364 passed). Owner ruled **OD-3 `RATIFY`**: DBOS is **ratified as the initial engine**. Not pilot-validated, not production-certified. Evidence: ADR §8A and §9. |
| **Label on completion** | **Core implemented** for the adapter package; **DBOS moves from *candidate* to *ratified as the initial engine*** at this exit and at no earlier point (GAS-R1). Agent Runtime's own "not distributed-safe, not exactly-once" statements `[V]` (`packages/runtime/agent-runtime/README.md:36`) are revised only for the properties the matrix actually proves, and only in the adapter's README. |

#### GAS-3 · Production `GovernanceHook` adapter from `GovernedExecutionDecision`

| | |
|---|---|
| **Entry** | GAS-2 exit met. |
| **Work** | A hook adapter that composes Risk Authority, Decision Authority and ActionGate through `RiskAuthorityCompositionEngine.compose` `[V]` (`packages/integration/risk-authority-runtime/.../composition.py:62`) and projects the resulting `GovernedExecutionDecision` `[V]` (`.../contracts.py:339`) onto `GovernanceEvaluation` `[V]` (`.../agent_runtime/governance/interfaces.py`). The adapter binds `proposal_fingerprint` and `correlation_reference` and mints nothing. |
| **Exit** | Only three hooks existed before this item `[V]` (`Unconfigured`, `AllowAll`, deprecated `Noop`); a fourth exists, is fail-closed on every non-`GRANT` disposition, and passes an adversarial suite proving `HOLD`/`ESCALATE`/`BLOCK` can never widen to `CLEAR`. `AllowAllGovernanceHook` remains non-default. |
| **Status (2026-09-05)** | **Implemented.** `packages/integration/agent-runtime-governance` 0.1.0, 68 passed; the ADR §8 matrix re-run with the production hook is 12 passed. Evidence: ADR §8B. |
| **Label on completion** | **Core implemented.** Not pilot-validated: `production_mode` still raises `ProductionContainmentError` in Risk Authority `[V]` (`packages/risk_authority/src/risk_authority/domain/errors.py:19`), and `HOLD`, `DEFER`, `ESCALATE` and `MANUAL_REVIEW` still have no sink `[G]`. |

#### GAS-4 · Studio v1 — six screens on React Flow

Constitution → Policy → Authority → Simulate → Publish → Observe, built in that order
inside `apps/ugence-governance-studio`.

| | |
|---|---|
| **Entry** | GAS-3 exit met. The screen-to-type audit (`apps/ugence-governance-studio/docs/GOVERNED_AGENT_STUDIO_V1_SCREEN_AUDIT.md`) accepted. |
| **Work** | An additive `governance_studio.api.v2` contract alongside the frozen `governance_studio.api.v1` `[V]` (`apps/ugence-governance-studio/contracts/openapi.json`); the studio backend as **thin orchestration only** over the existing packages; the six screens against frozen fixtures. |
| **Exit** | `v1` byte-frozen and still passing its freeze test `[V]` (`backend/tests/test_freeze.py`); every `v2` route delegates to a package entry point with no re-implemented governance logic; no route grants, authorizes or executes; determinism tests pass for all six screens. |
| **Status (2026-09-05)** | **Backend and all six screens implemented.** Frontend suite 197 passed (was 150), ten verifier gates green, `reactflow` the only new dependency; v1's contract, generated client and 17-operation allowlist byte-identical. The three review gaps (simulate mode threading, publish release binding, bounded clearance record) were closed in PR #1609. Langflow import is deferred (GAS-5, §11.3). Previously: **backend implemented; no screen shipped.** 12 additive v2 routes across the six screens; backend suite 175 passed (was 142). `contracts/openapi.json` is byte-identical and its freeze test passes unmodified. SD-1 allowlist and SD-2 operation-id guard are enforced by tests. Evidence: `apps/ugence-governance-studio/docs/GOVERNED_AGENT_STUDIO_V1_SCREEN_AUDIT.md`. |
| **Label on completion** | **Core implemented** for the studio feature. The studio's own posture — synthetic data, planning only, no execution or permission granting `[V]` (the frozen OpenAPI description) — is preserved verbatim for `v2`. |

#### GAS-5 · Langflow importer — **deferred, customer-gated (ruled 2026-09-05)**

| | |
|---|---|
| **Status (2026-09-05)** | **Removed from the current implementation sequence and from MVP scope** by owner ruling `DEFER_LANGFLOW_CUSTOMER_GATED` (§11.3). Langflow is preserved only as a possible future import adapter. No audit, importer, endpoint, dependency or implementation exists or is scheduled `[V]` (`langflow_import_implemented: False` in the studio's maturity flags; no `/policy/from-langflow` route in `contracts/openapi_v2.json`). React Flow remains the Ugence-owned authoring surface (GAS-R3). |
| **Entry** | A demonstrated customer or design-partner need **and** a new owner ruling. Not entered on schedule, and not entered by GAS-4's exit alone. |
| **Work** | A one-way importer: parse exported Langflow JSON, validate against a strict allowlist schema, reject anything unmapped, compile the accepted subset to Workflow IR v2 through `compile_policy_pack` `[V]` (`packages/tooling/policy-workflow-compiler/.../compiler.py:222`). |
| **Exit** | An adversarial corpus of malformed, oversized, cyclic, deeply nested and code-bearing Langflow exports is refused with typed errors and zero evaluation; the importer executes nothing from the file and imports no Langflow package; unmapped node types refuse rather than degrade. |
| **Label on completion** | **Core implemented** for the importer. It confers no maturity on the imported graph, which enters as an ordinary unapproved policy pack. |

#### GAS-6 · Temporal adapter — **gated, later**

| | |
|---|---|
| **Entry** | GAS-2 exit met **and** an owner ruling authorizing the second engine, taken on evidence of a regulated-enterprise requirement that DBOS does not meet. Not entered on schedule. |
| **Work** | A second implementation of the same `DurableExecutionAdapter` Protocols. |
| **Exit** | The complete GAS-1 matrix passes against Temporal **with no change** to Workflow IR, governance state, receipts, or any file under `packages/runtime/agent-runtime` (GAS-R2) — that no-change property is the exit criterion, verified by diff. |
| **Label on completion** | **Contract-only** until its matrix passes; **Core implemented** thereafter. |

#### GAS-7 · Human review and durable resume — **HR-A to HR-E implemented; HE-1 to HE-5 await ruling**

| | |
|---|---|
| **Entry** | Owner rulings HR-1 to HR-5 in `docs/architecture/ADR_UGENCE_HUMAN_REVIEW_DURABLE_RESUME_SCOPING.md` — **met 2026-09-05**. Each step HR-A to HR-E is entered only by its own implementation prompt. |
| **Work** | Compose what exists and mint nothing: a production `GovernanceInputSource` that reads the approval ledger and the authority directory, binds an approval to the proposal fingerprint, and consumes it exactly once before the engine advances (HR-A); a bounded resume in the DBOS adapter (HR-B); a review service that lists the queue and records a human decision under IdP identity and the eligibility port (HR-C); Review Queue and Run Detail screens under SD-1 and SD-2 (HR-D); one audit reference joining proposal, approval, consumption and resumed evaluation (HR-E). |
| **Exit** | The eleven-row failure matrix in that ADR §4 is green against a real PostgreSQL and a real SQLite ledger: duplicate decisions, stale approvals, expiry, revocation, wrong approver, correlation mismatch, crash before and after decision persistence, duplicate resume signals, clearance change before resumed execution, and bounded resume. Matrix row 9 of the DBOS ADR is rewritten to actually resume. |
| **Status (2026-09-05)** | **HR-A implemented** (`packages/integration/governed-review` 0.1.0, `REFERENCE_GRADE_SHADOW_ONLY`): the production `GovernanceInputSource` binds approvals to the proposal fingerprint, raises the request on park, consumes exactly once before the engine advances, and releases only the Decision Authority HOLD it satisfied; ESCALATE only. Failure-matrix rows 2, 3, 6, 8 and 10 pass inside the real DBOS adapter against a real PostgreSQL with the real SQLite ledger. **HR-B implemented** (durable-execution): the adapter's `resume` is bounded to one quantum per durable step via `continue_workflow`; DBOS §8 row 9 now resumes for real and a three-task chain proves one task per step; the full §8 matrix, the production-hook re-run and the governed-review rows stay green. **HR-C implemented** (`packages/integration/governed-review-service` 0.1.0, `REFERENCE_GRADE_SHADOW_ONLY`, `IDENTITY_PROOF` `PRESENTED_UNPROVEN`): `ReviewService` lists the ESCALATE queue joined to the durable checkpoint, renders a run, records a GRANT or REJECT by a presented approver through the ledger's eligibility port, and then delivers the adapter signal and the bounded resume for that instance only; rows 1 and 5 pass at unit level and rows 5, 7, 8 and 9 pass inside the real DBOS adapter against a real PostgreSQL; the five audited routes exist over FastAPI as an optional extra. No identity provider exists. **HR-D implemented** (studio): Review Queue and Run Detail screens under `/studio/review` with five v2 relay routes over a review-service client whose five-route allowlist is enforced before a socket opens (HR-1); the decision is relayed verbatim, an unreachable service is a gap and never an empty queue, a HOLD is never presented as awaiting a human, and fingerprints and `valid_until` are shown as history; the SD-2 prohibition, console allowlist, v1 byte-freeze and frontend verb scan pass unchanged; `human_review_implemented` is `True` and `authentication_implemented` stays `False`. **HR-E implemented, contract only** (`governed-review` 0.2.0, `LINKAGE_MATURITY` `CONTRACT_ONLY`): `ReviewLinkage` joins proposal fingerprint, approval id, consumption id, park, decision signal, resume and the two sealed evaluations across the approval ledger, the durable event log and the checkpoint journal by id, refuses any join the stores do not support, digests deterministically and projects onto G4's `EvidenceReference`/`AuditReference`; the unified ledger D-4 named now exists as `control-plane-root` 0.1.0 (#1617), and whether a linkage is appended to it is owner decision HE-1 (ADR §5a, with HE-2 to HE-5). No store changed; clearance receipts untouched. The GAS-7 sequence is complete at its stated ceiling. Before HR-A the path was fail-closed in the restrictive direction and has no sink in the permissive one `[V]` (`agent-runtime-governance/.../__init__.py:76-80`): no production `GovernanceInputSource` exists, `resume_workflow` takes only an instance id, the approval ledger is imported by nothing on the path, and no studio, console or client surface lists a queue or records a decision. Evidence: the ADR §2 path map and `apps/ugence-governance-studio/docs/HUMAN_REVIEW_SCREEN_API_AUDIT.md`. |
| **Label on completion** | **Core implemented, reference-grade, shadow-only** at best: the approval ledger and directory are `REFERENCE_GRADE_SHADOW_ONLY`, the runtime invokes fixture providers, no credential broker or IdP integration exists. Pilot validation and production certification are not reachable from this item. |

### 11.2 Non-goals for this whole sequence

No live execution against real systems. No credentials — the Credential Broker
(cloud-scaling Phase 5X) remains unbuilt `[V]` (Appendix B §B.6 ¶2) and nothing here
substitutes for it. No generic LLM, prompt or API canvas nodes. No research-only
package in the product. No hosted multi-tenancy. No claim of pilot validation or
production certification, on any item, at any exit above.

### 11.3 Owner decisions — ruled 2026-09-05

All below are ruled and recorded at source. GAS-1 through GAS-4 are complete and
merged; GAS-5 is deferred; GAS-6 remains gated; GAS-7 is ruled and not entered.

| # | Ruling | Recorded in |
|---|---|---|
| OD-1 | `REQUIRE_SINGLE_TRANSACTION` — atomic commit is a **DBOS ratification gate**; if DBOS cannot provide it, GAS-2 stops and reports rather than accepting a residual | `ADR_DBOS_DURABLE_EXECUTION_INTEGRATION.md` §9 |
| OD-2 | `COEXIST_WITH_BOUNDARY` — governance stores keep their ratified SQLite; DBOS and the three Agent Runtime stores share Postgres behind a documented consistency boundary | same, §9 |
| OD-3 | **`RATIFY`** (2026-09-05) — the CI-verified matrix promotes DBOS from *candidate* to *ratified as the initial engine*; `DBOS_ENGINE_STATUS = "RATIFIED"` | same, §8A and §9 |
| SD-1 | `EXPLICIT_PUBLIC_ALLOWLIST` — the studio boundary widens only by a per-package public-entry-point allowlist; the architecture test is retained | `apps/ugence-governance-studio/docs/GOVERNED_AGENT_STUDIO_V1_SCREEN_AUDIT.md` |
| SD-2 | `NON_AUTHORITY_STUDIO` — the studio never issues, activates, revokes, grants, authorizes, clears or executes | same |
| HR-1 | **`DISPLAY_AND_TRANSMIT`** (2026-09-05) — the studio renders the review queue and run detail and relays a verbatim human decision to a separate review service; it holds no identity, consumes nothing, signals nothing, resumes nothing | `ADR_UGENCE_HUMAN_REVIEW_DURABLE_RESUME_SCOPING.md` §5; `HUMAN_REVIEW_SCREEN_API_AUDIT.md` |
| HR-2 | **`NEW_PACKAGE_GOVERNED_REVIEW`** — `packages/integration/governed-review` owns the production `GovernanceInputSource`, the consume-then-advance order and the review service | same, §5 |
| HR-3 | **`RATIFY_FINGERPRINT_BINDING`** — approvals bind to the proposal fingerprint with `consumer_ref=<instance_id>:<task_id>`; consume in the SQLite ledger, then advance in Postgres; same-holder `ALREADY_CONSUMED` is satisfied | same, §3 and §5 |
| HR-4 | **`BARE_RUNTIME_BOUNDED_ADAPTER`** — the runtime's resume stays bare and unexposed; the DBOS adapter moves to `continue_workflow`, one quantum per durable step, re-running the DBOS §8 matrix | same, §5 |
| HR-5 | **`ESCALATE_ONLY`** — only ESCALATE enters the review queue; HOLD is released by upstream authority change only; no new disposition | same, §5 |
| GAS-5 | **`DEFER_LANGFLOW_CUSTOMER_GATED`** (2026-09-05) — Langflow import is removed from the current sequence and MVP scope; preserved only as a possible future import adapter, requiring a demonstrated customer or design-partner need and a new owner ruling. No audit, importer, endpoint, dependency or implementation now. React Flow remains the Ugence-owned authoring surface | this section, GAS-5 and GAS-R4; `GOVERNED_AGENT_STUDIO_V1_SCREEN_AUDIT.md` |


---

*Companion to the Ugence AI Control Plane — Investor First Look and the Ugence
Technical Evidence Catalogue. Internal / data-room use.*
