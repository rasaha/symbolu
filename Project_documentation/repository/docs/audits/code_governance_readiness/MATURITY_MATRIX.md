# Maturity Matrix — Code Governance

> Documentation only. Machine-readable form: `maturity_matrix.json`. Verified at commit `3ec11e4e`.
> Classifications: PRODUCTION_SHAPED · IMPLEMENTED · PARTIAL_PROTOTYPE · SHADOW_ONLY · SIMULATED ·
> DOCUMENTED_ONLY · PLANNED · MISSING. **Passing synthetic tests is not production readiness.**

| Component | Maturity | Evidence (verified) |
|---|---|---|
| Governance Provider Framework | **IMPLEMENTED** | 84 tests pass; register/resolve/adapt/conformance/observability; owns no authority |
| Governance Contracts | **IMPLEMENTED** | 45 tests pass; three neutral families; stdlib-only leaf |
| TAP | **PARTIAL_PROTOTYPE** | `tap_provider` 38 tests pass; `truth_assurance_pipeline` E1–E5 deterministic on **synthetic** data; E6/E7 docs-only; no real-model evidence at scale |
| Decision Authority | **IMPLEMENTED** (frozen kernel) | 79 tests pass; `DecisionRecord`/CER/`ActionRequest`/`Override`/`ExecutionIntent`; **repositories in-memory (no durable DB)** |
| ActionGate | **IMPLEMENTED** | `actiongate_provider` 30 tests pass; shadow-validated against fixtures |
| ACP | **SHADOW_ONLY** | design-first; never enforcing; robotics/K8s/db domains only; **no GitHub domain**; `CLEAR/HOLD`; no durable clearance ref |
| StoryGraph | **IMPLEMENTED** | 316 tests pass; advisory only; own tenant-isolated registry; real hash-chained `durable_audit` |
| Evidence subsystem | **PARTIAL_PROTOTYPE** | content-hash + source provenance present; **no durable store**; no validator-identity binding; no quarantine/admissibility; no head-SHA invalidation |
| Durable audit store | **PARTIAL_PROTOTYPE** | real hash-chained SQLite in StoryGraph + `agentic/ledger` (reference-grade); decision kernel audit in-memory, chaining field reserved/unused; no unified backend |
| Workflow infrastructure | **PLANNED** | no durable engine as code; `agent_runtime_v2` docs-only; `agent_runtime_migration` in-memory; `control_plane` single-request/mock |
| GitHub Evidence Connector | **MISSING** | no GitHub ingestion code |
| GitHub Execution Provider | **MISSING** | only the framework `DeterministicExecutionProvider` test-double exists |
| Repository policy engine | **DOCUMENTED_ONLY** | `POLICY_PACK_GOVERNED_WORKFLOW_COMPILER_SPEC.md`; StoryGraph policypack compiler is domain-specific |
| Identity integration | **PARTIAL_PROTOTYPE** | DA `ActorIdentity`/`ActorType` + `authenticate()`; no enterprise OIDC/SSO; no GitHub identity mapping; SoD off by default |
| Code Governance UI | **DOCUMENTED_ONLY** | `Project_documentation/control_plane/ACP/UGENCE_UNIFIED_CONSOLE_PLAN.md`; no PR check-run UI |
| Competitive Code Adjudication | **MISSING** | no patch-pair capability; reusable analogues only (model-selection `Selection`, `comparative_governance_benchmark`, `StoryVerdict`, `reviewer_ready_pilot` `AdjudicationResult`) |
| Deployment Governance | **DOCUMENTED_ONLY** | MVP3; reuses ACP+ActionGate K8s surface (shadow); no provenance/digest binding |

## Reading the matrix

- The **governance authority spine** (Contracts, GPF, Decision Authority, ActionGate, StoryGraph) is
  **IMPLEMENTED** — the architecture the design composes exists and passes tests.
- The **execution-time and persistence layers** (ACP, durable audit, workflow infra, evidence store)
  are **SHADOW_ONLY / PARTIAL / PLANNED** — these are the prerequisites for *enforced* merge (MVP 1C).
- The **GitHub-specific pieces** (connector, execution provider) and **Competitive Adjudication** are
  **MISSING** by design — they are the net-new work, not gaps in the platform.
