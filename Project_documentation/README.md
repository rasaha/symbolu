# Project_documentation

Centralized home for **legacy and project-level documentation** in `rasaha/symbolu`.

> **Phase 2 complete.** Legacy/project Markdown documentation has been relocated
> here from across the repository. Content was preserved verbatim except for
> relocation-driven link/path repairs. See
> [`manifests/PHASE2_LEDGER.md`](manifests/PHASE2_LEDGER.md) for the authoritative
> per-file relocation record and [`MIGRATION_MANIFEST.md`](MIGRATION_MANIFEST.md)
> for the full plan and verification.

## Navigation — where documentation lives now

| Module | Documentation home | Docs | Legacy code location | Active package replacement |
|---|---|---:|---|---|
| **repository** | `Project_documentation/repository/` | 648 | (various root-level docs) | — |
| **agentic_framework** | `Project_documentation/agentic_framework/` | 259 | agentic/, agent_runtime_migration/, agent_runtime_v2/, agentic_framework_review/ | — |
| **symbolu_core** | `Project_documentation/symbolu_core/` | 13 | symbolu_core/ | — |
| **control_plane** | `Project_documentation/control_plane/` | 104 | acp/, ACP/, ai_control_plane_v3/, control_plane/, control_plane_shadow/, cloud_controller/ | — |
| **governance** | `Project_documentation/governance/` | 363 | actiongate_provider/, decision_governance/, assertion_governance/, execution_gate/, evidence_*/, *_pilot/, cer-adjacent governance dirs | packages/governance-*, packages/providers/* |
| **action_gate_cyber** | `Project_documentation/action_gate_cyber/` | 79 | cyber_security/ | — |
| **cer** | `Project_documentation/cer/` | 45 | cer_v0_1/, cer_v0_2/, cer_v0_3/, cer_public_draft/, cer_open_standard/ | — |
| **ai_hiring** | `Project_documentation/ai_hiring/` | 43 | ai_hiring/ (facade; canonical code extracted to packages/products/ai-hiring) | packages/products/ai-hiring |
| **truth_assurance_pipeline** | `Project_documentation/truth_assurance_pipeline/` | 116 | truth_assurance_pipeline/, tap_provider/ (facade) | packages/providers/tap |
| **autonomous_robotics** | `Project_documentation/autonomous_robotics/` | 34 | symbolu_robotics/, robotics_reliability_bench/ | — |
| **model_selection** | `Project_documentation/model_selection/` | 17 | model_selection_experiment/, model_selection_pilot/ | — |
| **simulator** | `Project_documentation/simulator/` | 17 | simulator/ | — |
| **trading** | `Project_documentation/trading/` | 2 | trading/, trading2/ | — |

`repository/` holds cross-cutting platform documentation (strategy, architecture,
audits, migrations, status, roadmaps) that is not owned by a single module.

## Boundaries (not migrated — remain colocated)

| Boundary | Rule |
|---|---|
| `packages/**` | ACTIVE_PACKAGE — package-local docs stay with their package |
| `apps/**` | ACTIVE_APP — app-local docs stay with the app |
| `products/**` | ACTIVE_PRODUCT — product-local docs stay with the product |
| Hybrid-LLM / model research | Excluded by semantics (neural training, KV/CTM, quantization, phase/attention, Varṇa symbolic research). Not moved. See [`manifests/EXCLUDED_hybrid_llm.md`](manifests/EXCLUDED_hybrid_llm.md) |
| `.github/**`, tooling metadata | Infrastructure — kept in place |

## Deviations & deferrals

- **Justified deviations:** a small set of docs referenced by CI/operational
  consumers by exact path were intentionally kept at their canonical location
  (e.g. `ONTOLOGY_FREEZE_CONTRACT.md`). Listed in
  [`manifests/PHASE2_LEDGER.md`](manifests/PHASE2_LEDGER.md).
- **Deferred (REVIEW_REQUIRED):** ambiguous legacy docs (including the `symbolu/`
  compat-shim duplicates and mixed governance/neural experiments) were left in
  place pending human adjudication. See
  [`manifests/REVIEW_REQUIRED.md`](manifests/REVIEW_REQUIRED.md).

## Preservation guarantee

This was a relocation, not a rewrite. Documents — including obsolete, superseded,
duplicate, and historical ones — were moved as-is. No prose was rewritten, no
documents merged or deduplicated, no historical content deleted.

## Artifacts

| File | Purpose |
|---|---|
| [`MIGRATION_MANIFEST.md`](MIGRATION_MANIFEST.md) | Stage-1 plan + Phase-2 execution record and verification gates |
| [`manifests/PHASE2_LEDGER.md`](manifests/PHASE2_LEDGER.md) | Authoritative per-file relocation ledger |
| [`manifests/`](manifests/) | Per-module classification tables and exclusion accounting |
