# Ugence — City-Scale Vehicle Intelligence Client Brief v2.0

## Repository Evidence Report

> **Purpose.** This report records the repository evidence used to modernize the
> client brief *UGENCE GOVERNANCE FOR CITY-SCALE VEHICLE INTELLIGENCE* from v1.1
> (attachment, dated 10 August 2026) to v2.0. It is a documentation-only artifact.
> No production code, package version, schema, contract, CI workflow, or test was
> modified. No commit, push, or pull request was created by this task.

---

## 1. Repository state at inspection

| Item | Value |
|---|---|
| Repository | `github.com/rasaha/symbolu` (Ugence / SymbolU monorepo) |
| Default branch (origin HEAD) | `claude/setup-symbolu-monorepo-014vhNMAoVW2Ys5RBBr3bKDF` |
| Default branch tip SHA | `78e8e194225172d26e90b609b5e816a316ecd48b` |
| Working branch during this task | `claude/servicenow-use-cases-rv2234` |
| Working-branch HEAD SHA | `395f86e4e747b0b28ef9f3e42fbd6fd108cf9669` |
| Relationship to default | merge-base of working HEAD and default tip **is** the default tip (`78e8e19…`); the working branch = default tip + documentation-only commits |
| `packages/` diff vs default tip | **0 files** — `packages/` is byte-identical to the default branch tip, so local inspection of `packages/` is authoritative for "merged into default" |
| Working-tree status at task start | clean (documentation deliverables for this task are added new and uncommitted) |

**Consequence for maturity claims.** Because `packages/` on the working branch is
identical to the default-branch tip, every capability described below as
implemented is genuinely merged into the default branch. Only default-branch code
is treated as implemented.

### Relevant open / draft pull requests (NOT treated as implemented)

| PR | Title | State | Bearing on this brief |
|---|---|---|---|
| #1427 | docs(uvi): ADR — Ugence Value Intelligence GV-2C / GV-2E / GV-3R (design only) | **open, draft** | Value-intelligence extensions are **DESIGN_ONLY**; excluded from implemented set |
| #1194 | Frame Ugence as the missing enterprise-AI-stack layer (v1.3) | open | Positioning context only; not a capability |
| #1386, #1343 (DilChat); #1049, #916, #682, #636, #624, #519, #1365/#1366/#1373/#1380 (research) | — | Unrelated to the governance chain in this use case |

No open or draft PR merges a new governance capability into the default branch.

---

## 2. Modules inspected and maturity classification

Maturity labels: `IMPLEMENTED_AND_CI_VERIFIED`, `IMPLEMENTED`, `PARTIAL`,
`REFERENCE_ONLY`, `DESIGN_ONLY`, `PROPOSED`, `MISSING`, `FUTURE`.
"CI-verified" means a `.github/workflows/*` workflow runs that package's own tests.

### 2.1 Governance decision chain

| Module (exact repo name) | Path | Version | Produces | Grants execution authority? | Maturity |
|---|---|---|---|---|---|
| `ugence-governance-contracts` | `packages/governance-contracts` | pkg 0.1.0 / contract 1.0.0 | Neutral contract vocabulary: `ActionGovernanceRequest/Result`, `ActionGovernanceOutcome`, `ExecutionDispatch/Observation/BusinessOutcome`, provider protocols | No — "neutral contracts, not authority" | IMPLEMENTED_AND_CI_VERIFIED |
| `ugence-decision-authority` (Decision Authority) | `packages/capabilities/decision-authority` | 1.0.0 | `DecisionCase` (canonical, immutable/versioned), `DecisionRecord`, `ContextEnvelopeRecord` (CER), authorization/reconciliation records | No — issues a **binding decision**, "a granted authorization never means the action happened"; AI is structurally barred as an authorizing principal | IMPLEMENTED_AND_CI_VERIFIED |
| `ugence-actiongate-provider` (ActionGate) | `packages/providers/actiongate` | 0.1.0 | `ActionGovernanceResult` — outcome ∈ {**AUTHORIZED, AUTHORIZED_WITH_CONSTRAINTS, DENIED, INDETERMINATE, EXPIRED**} + constraints/obligations/expiry | No — "owns no dispatch and no execution authority… Authorization is never execution"; uncertainty → INDETERMINATE, never AUTHORIZED | IMPLEMENTED_AND_CI_VERIFIED |
| `ugence-action-clearance` (Action Clearance) | `packages/capabilities/action-clearance` | 0.1.0 (contract `action_clearance.v1`) | `ClearanceResult` / `ClearanceReceiptBody` — status ∈ {**CLEAR, HOLD, BLOCK, ESCALATE**} (precedence BLOCK>ESCALATE>HOLD>CLEAR) | No — "may never create authority, broaden authorization, replace ActionGate, dispatch execution" | **IMPLEMENTED** (no CI workflow references it) |
| `ugence-risk-authority` (Risk Authority) | `packages/risk_authority` | 0.2.0 | `RiskDecision`; in reference mode a signed **Ed25519 `RiskAuthorizationEnvelope`** — the *sole* machine authority (scope ⊆ decision; non-compensatory controls) | **Conditionally** — the signed envelope is the sole machine authority; but in `production_mode=True` it **fails closed at `issue_envelope`** (production issuance unimplemented) and stops at a non-executable `RiskDecision` | IMPLEMENTED_AND_CI_VERIFIED (spine); production envelope issuance PARTIAL |
| `ugence-model-selection` → **Model Authority** | `packages/capabilities/model-selection` | 0.1.0 | Binding `ModelAuthorizationDecision` (ALLOW/DENY/HOLD/ESCALATE) + reason codes + governed fallback | Binding *model-authorization* decision; owns no invocation/routing/execution | **IMPLEMENTED** (no dedicated CI; only referenced in a PWC import-boundary job) |
| `ugence-storygraph` (StoryGraph) | `packages/capabilities/storygraph` | 2.0.0 | Advisory `Finding` (OBSERVE/ESCALATE/UNAVAILABLE) + `ADVISORY` evidence; deterministic replay digests | No — advisory only; never ALLOW/DENY | IMPLEMENTED (frozen reference; synthetic-only; no dedicated CI) |

### 2.2 Trusted evidence and control assurance

| Module | Path | Version | Produces | Authority? | Maturity |
|---|---|---|---|---|---|
| `ugence-risk-authority-evidence-runtime` (**RA-5**) | `packages/integration/risk-authority-evidence-runtime` | 0.1.0 | `AdmittedEvidence` (provenance ∧ integrity/digest ∧ freshness ∧ schema) then a trusted, bound `ControlResult` | No — strictly upstream of authority; in production a caller-supplied `PASS` is **inert** | IMPLEMENTED_AND_CI_VERIFIED (library); end-to-end production admission integration PARTIAL |
| `ugence-tap-provider` (**TAP**) | `packages/providers/tap` | 0.1.0 | Assertion-coverage outcome SUPPORTED/UNSUPPORTED/CONSTRAINED/INDETERMINATE | No — "owns NO authorization and NO execution authority"; independent peer of ActionGate; wrapped by RA-5 as its **control-/assertion-support evaluator** | IMPLEMENTED_AND_CI_VERIFIED |
| `ugence-policy-workflow-compiler` (PWC) | `packages/tooling/policy-workflow-compiler` | 0.2.0 | Deterministic governed-workflow IR + assurance manifest + capability-requirement manifest; content-addressed; human-approval record that **rejects self-approval** | No — "tooling, not a governance authority" | IMPLEMENTED_AND_CI_VERIFIED (offline; not pilot/production-certified) |
| `evidence_assurance`, `evidence_obligation`, `minimal_evidence_policy`, `assertion_governance`, `assertion_gate_robustness`, `scope_integrity` | top-level dirs (not packaged) | none | Research/eval logic for evidence disposition/obligation/assertion gating | No | **REFERENCE_ONLY** — no `pyproject.toml`, no CI; "isolated; NOT integrated into the control plane" |

### 2.3 Runtime, execution and assurance

| Module | Path | Version | Produces | Authority? | Maturity |
|---|---|---|---|---|---|
| `ugence-agent-runtime` (Agent Runtime) | `packages/runtime/agent-runtime` | **0.7.0** | `WorkflowInstance`, `CanonicalExecutionState`, `RuntimeEvent`, `ProviderAttempt`, checkpoints | No — coordinates only; default `UnconfiguredGovernanceHook` → **BLOCK**; re-checks exact-action fingerprint, fails closed on drift; "never mints execution clearance" | IMPLEMENTED_AND_CI_VERIFIED |
| `ugence-risk-authority-runtime` (RA-4.5 composition) | `packages/integration/risk-authority-runtime` | 0.1.0 | `GovernedExecutionDecision` (GRANT/DENY/HOLD/ERROR_NON_EXECUTABLE) composing RA envelope + Decision Authority + ActionGate (subtract-only) | No — RA envelope is sole issuer; DA/AG can only subtract | IMPLEMENTED_AND_CI_VERIFIED |
| `ugence-risk-authority-runtime-assurance` (**RA-7**) | `packages/integration/risk-authority-runtime-assurance` | 0.1.0 | In-flight `TrajectoryAssessment` (NORMAL/ESCALATED/UNKNOWN) + neutral `AuthorityReassessmentSignal` | No — "observes and assesses… mints nothing" | IMPLEMENTED_AND_CI_VERIFIED (reference-grade) |
| `ugence-risk-authority-execution-assurance` (**RA-8**) | `packages/integration/risk-authority-execution-assurance` | 0.1.0 | Post-effect `EffectAssuranceAssessment` (MATCHED/MISMATCH/PARTIAL/UNKNOWN/…) + neutral signal | No — evidence + reassessment signal only; "introduces no second authority artifact" | IMPLEMENTED_AND_CI_VERIFIED (reference-grade; verification bounded by effect source) |
| `ugence-risk-authority-status-runtime` (**RA-6**) | `packages/integration/risk-authority-status-runtime` | 0.1.0 | Authority-lifecycle mutation (revoke / advance epoch / expire) via sole authenticated writer; read-only status cache | No new authority — worst case is restriction | IMPLEMENTED_AND_CI_VERIFIED (reference in-memory; "operationally inert" — zero non-test write call sites) |
| `ugence-cloud-scaling-operations` | `packages/capabilities/cloud-scaling-operations` | 0.1.2 | `ExecutionReceipt`, `OutcomeRecord`/`OutcomeVerdict` given an external `ExecutionAuthorization` | No self-authorization — "installation alone does not authorize execution" | IMPLEMENTED (domain-executor reference; not live-cluster/production validated) |
| `ugence-cloud-scaling-controller` | `packages/capabilities/cloud-scaling-controller` | 0.4.0 | `ScalingRecommendation` (advisory_only) | No — "Execution capability: NONE" | IMPLEMENTED_AND_CI_VERIFIED (advisory; illustrative of recommender≠authority only) |

**Agent Runtime capability audit** (backing files under `packages/runtime/agent-runtime/src/ugence_agent_runtime/`):
durable workflow state **IMPLEMENTED**; checkpoints (hash-chained) **IMPLEMENTED**; retries/recovery **IMPLEMENTED**; concurrent execution **IMPLEMENTED** (bounded, in-process only — not distributed/exactly-once); bounded advancement **IMPLEMENTED**; scheduling/fairness (SWRR + aging) **IMPLEMENTED**; tool invocation **IMPLEMENTED**; execution-attempt telemetry **IMPLEMENTED**; event sourcing **PARTIAL** (append-only event stores exist; state recovery is checkpoint-based, no durable event-replay backend); runtime operational constraints (budget/resource/concurrency/timeout) **IMPLEMENTED** while policy authorship is intentionally external.

### 2.4 Supporting and cross-cutting modules

| Module | Path | Version | Role | Maturity |
|---|---|---|---|---|
| `ugence-context-minimization` | `packages/capabilities/context-minimization` | 0.2.0 | Extractive, fail-closed, oracle-defined context minimization + neutral `token_accounting` | IMPLEMENTED_AND_CI_VERIFIED |
| `ugence-context-minimization-token-accounting-runtime` (CM-TA1) | `packages/integration/context-minimization-token-accounting-runtime` | 0.1.0 | Per-attempt token records + budget settlement for Agent Runtime | IMPLEMENTED_AND_CI_VERIFIED (no real provider tokenizer in-package) |
| `ugence-agent-workforce-composer` | `packages/capabilities/agent-workforce-composer` | 0.2.1 | Offline team planning: eligibility, exact-optimal `AgentTeamPlan`, least-privilege `PermissionBoundProposal` | IMPLEMENTED_AND_CI_VERIFIED (offline; not pilot-validated) |
| `ugence-governed-value` (Governed Value) | `packages/governed-value` | 0.2.0 | Reported / risk-adjusted net governed value + ROI (all outputs `REPORTED`/`UNVERIFIED`) | IMPLEMENTED (experimental GV-1 kernel; no evidence/authority binding; no CI) |
| `ugence-governance-provider-framework` | `packages/governance-provider-framework` | 0.1.0 (contract 1.0.0) | Provider registry / deterministic resolution / neutral invocation | IMPLEMENTED_AND_CI_VERIFIED (subset) |
| Credential brokering | `cyber_security/action_gateway*/…/broker.py` | — | Mints per-action K8s ServiceAccount + scoped Role + single-use token the agent never holds | IMPLEMENTED (reference, in ActionGate legacy tree; **not a `packages/` module**) |
| Agent / workload identity | `Project_documentation/agentic_framework/**` | — | — | **DESIGN_ONLY** (listed as an absent "V2 gap") |
| Audit / invariance | `packages/products/ai-hiring/…/audit_completeness.py`; agent-runtime checkpoints; RA signing | — | Hash-chained accountability audit (AI Hiring, CI-verified); hash-chained durable checkpoints (Agent Runtime); Ed25519 envelope hashing (Risk Authority) | IMPLEMENTED (per-package pattern; no single "receipt-chain" package) |

---

## 3. Corrections made to the v1.1 document

| # | v1.1 concept | Repository reality | Correction in v2.0 |
|---|---|---|---|
| C1 | ActionGate returns **ALLOW / DENY / HOLD / ESCALATE** | ActionGate returns **AUTHORIZED / AUTHORIZED_WITH_CONSTRAINTS / DENIED / INDETERMINATE / EXPIRED**; uncertainty → INDETERMINATE | ActionGate authorization vocabulary corrected and separated from live-safety vocabulary |
| C2 | HOLD / ESCALATE are ActionGate outcomes | HOLD/BLOCK/ESCALATE are **Action Clearance** outcomes (CLEAR/HOLD/BLOCK/ESCALATE); ALLOW/DENY/HOLD/ESCALATE is **Model Authority**'s decision vocabulary | Disposition semantics attributed to the correct owner |
| C3 | "TAP / Evidence Validation" validates source identity, integrity, timestamps, schema (evidence admission) | **RA-5** (`risk-authority-evidence-runtime`) owns trusted evidence **admission**; **TAP** is the assertion-/control-support evaluator RA-5 wraps | Evidence admission reassigned to RA-5; TAP repositioned as the control-support evaluator |
| C4 | "Model Eligibility / Model Authorization" | Canonical capability is **Model Authority** (distribution still `ugence-model-selection`); emits a binding `ModelAuthorizationDecision` | Renamed to Model Authority; selection framed as internal optimization |
| C5 | Authority is implied by policy/evidence/decision, no single authority artifact named | The **sole machine authority is a signed Ed25519 `RiskAuthorizationEnvelope`** minted by Risk Authority; ActionGate matches the exact action to it | Added Risk Authority + the signed envelope as the single authority artifact |
| C6 | Execution "receipt" closes the loop; no assurance family | Distinct **attempt** (`ProviderAttempt`, Agent Runtime) vs **receipt** (`ExecutionReceipt`, cloud-scaling-operations) vs **effect verification** (`EffectAssuranceAssessment`, RA-8); plus RA-7 in-flight trajectory and RA-6 authority lifecycle | Added the full attempt→receipt→effect assurance loop and reassessment-signal semantics |
| C7 | DecisionCase described generically | `DecisionCase` is real, canonical, **immutable/versioned**, and carries the **Context Envelope Record (CER)** | Enriched with immutability/versioning and CER |
| C8 | Everything presented as a flat specification | Per-capability maturity varies widely | Added maturity labels to every capability |
| C9 | "Policy" as a runtime authority | Only the **Policy Workflow Compiler** (tooling) is implemented; there is **no Policy Center / Policy Authority / Policy & Compliance Center** in code | Policy compiler = implemented tooling; the Policy & Compliance Center evolution = DESIGN_ONLY/FUTURE |
| C10 | Governed value implied as measured outcome | Governed Value outputs are **REPORTED/UNVERIFIED**, experimental, no CI | Labelled reported-only and experimental |

## 4. Capabilities deliberately marked FUTURE / DESIGN_ONLY (not implemented)

- **Policy & Compliance Center / adaptive-compliance lifecycle** — strategy note `Project_documentation/Ugence_Platform/Strategy/UGENCE_FORMAL_POLICY_ASSURANCE_AND_ADAPTIVE_COMPLIANCE_STRATEGY.md` (DRAFT). Only the Policy Workflow Compiler is implemented.
- **End-to-end operational RA-5→RA-8 enforcement** — the library packages exist and are CI-verified, but are not operationally wired into a running enforcement path (RA production fails closed at envelope issuance; RA-6 has zero non-test write call sites). **PARTIAL.**
- **Ugence Value Intelligence GV-2C / GV-2E / GV-3R** — draft PR #1427, DESIGN_ONLY.
- **Document/PDF policy ingestion, OCR, and formal verification / proof-runtime equivalence** — MISSING / FUTURE.
- **Credential Broker as a `packages/` module** and **agent/workload identity** — reference broker exists in the ActionGate legacy tree only; a packaged broker and workload identity are DESIGN_ONLY / FUTURE.
- **Live-cluster / production validation** of cloud-scaling-operations, and **CI coverage** for Action Clearance, Model Authority, and Governed Value — FUTURE.

## 5. Validation and rendering results

### 5.1 Deliverables

| File | Location | Notes |
|---|---|---|
| `UGENCE_CITY_SCALE_VEHICLE_INTELLIGENCE_CLIENT_BRIEF_v2.0.pdf` | this directory | Final client-facing A4 portrait PDF (33 pages) |
| `UGENCE_CITY_SCALE_VEHICLE_INTELLIGENCE_CLIENT_BRIEF_v2.0.docx` | this directory | Editable Word document (same content model) |
| `UGENCE_CITY_SCALE_VEHICLE_INTELLIGENCE_v2.0_EVIDENCE_REPORT.md` | this directory | This report |
| `build/{build.py, content.py, diagrams.py}` | `build/` | Reproducible generators (one content model → PDF via WeasyPrint + DOCX via python-docx; 8 vector SVG diagrams) |

### 5.2 Rendering and visual QA

- **Every one of the 33 PDF pages was rendered to an image and visually inspected** (not text/XML inspection). Each of the eight diagrams was additionally rendered standalone and checked for clipping, overlap and legibility, then re-checked after correction.
- Issues found and fixed during QA: subtitle clipping in the responsibility-boundary diagram; a band-title overflow and a missing glyph in the reference-architecture diagram; label/box overlaps in the canonical-lifecycle diagram (rebalanced spacing and shortened node labels); and several sparse / lone-note pages, resolved by shrinking three tall figures and switching the body to continuous flow (headings kept with their content via `break-after:avoid`), which also removed all near-empty and orphaned-heading pages.
- **Result:** no clipped or overlapping text; no broken or split diagrams; no cropped tables or text pressed against cell borders; no orphaned headings; no near-empty pages; consistent page furniture; correct "Page X of 33" numbering; no missing glyphs; no diagram source code in the PDF.

### 5.3 Geometry, metadata and structure checks

| Check | Result |
|---|---|
| Page count | 33 |
| Page geometry | every page 595×842 pt = **A4 portrait** (verified; no landscape pages) |
| File opens / non-zero | PDF 342 KB, DOCX 1.3 MB — both open and parse |
| PDF metadata | Title, Author = "Ugence Labs", Subject, Keywords, Creator all set |
| DOCX metadata | core Title / Author = "Ugence Labs"; `<Company>Ugence Labs</Company>` present |
| PDF bookmarks (outline) | 25 (Contents + 24 sections) |
| Clickable TOC / hyperlinks | 72 link annotations; TOC page numbers resolve via `target-counter` |
| Selectable text | confirmed |
| DOCX content | 213 paragraphs, 51 tables, 8 embedded diagram images |

### 5.4 Repository documentation checks

| Check | Command | Result |
|---|---|---|
| Terminology validation | `python3 scripts/validate_terminology.py` | **PASS** (exit 0) — no regression from the added files |
| Document-link check | `python3 scripts/check_doc_links.py` | **PASS** (exit 0) — 21 links checked |

No frozen contract, package, schema, test or CI workflow was modified to satisfy any check.

### 5.5 Environment constraint (disclosed)

LibreOffice/`soffice` is present in this environment but cannot load documents
(`Error: source file could not be loaded`), so a **DOCX→PDF render via LibreOffice
was not possible**. This does not affect the client deliverable: the client PDF is
produced directly by WeasyPrint from the same content model that generates the
DOCX (not converted from the DOCX), and it is that PDF which was rendered
page-by-page and visually inspected. The DOCX embeds the identical content and the
same rasterized vector diagrams and was validated structurally (opens, tables,
images, metadata).

### 5.6 Repository-safety confirmation

Documentation-only. No production code, package version, schema, public API, test
or CI workflow was modified. No commit, push, or pull request was created. Only new
files under `Project_documentation/Ugence_Platform/UseCases/CityScaleVehicleIntelligence/`
were added; unrelated working-tree changes were preserved.
