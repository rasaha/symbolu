# AI Hiring — Re-entry Baseline (as of Platform v1.0 freeze)

Documents the exact current state of AI Hiring so completion can resume against the
frozen platform without ambiguity. **No hiring features are implemented in this
phase.** Paths were resolved from the repository.

## Resolved locations

| Path | Role | State |
|---|---|---|
| `ai_hiring/` | Historical monolith: concrete domain implementations + full test suite | **553 tests passing**, v0.1.0 |
| `domains/hiring/` | Thin re-export of hiring domain vocabulary (evidence types, capability ontology, rubrics, scales) | present, no own tests (covered via `ai_hiring`) |
| `applications/ai_hiring/` | Composition root wiring `domains.hiring` + the DGM kernel | present (`platform.py`), no own tests |

`applications/hiring/` does **not** exist; the application package is
`applications/ai_hiring/`.

## Package / versioning / packaging

- `ai_hiring` version **0.1.0**. Not independently distributed — part of the root
  `symbolu` package (no `dgm-ai-hiring` wheel). `domains.hiring` and
  `applications.ai_hiring` are likewise in-repo, not separately packaged.

## Completed phases (from `ai_hiring/docs/IMPLEMENTATION_STATUS.md`)

- Phase 1 Foundation; 2 Evidence Ingestion & Normalization; 2.5 Evidence Boundary
  Hardening; 3A Capability Ontology & Rubrics; 3B Deterministic Assessment Runtime;
  4A DecisionCase Aggregate; 4B Governed Action Request & CER; 4C External Execution
  & Reconciliation; 5A/5B DGM kernel extraction. Closed out in
  `ai_hiring/docs/AI_HIRING_COMPLETION.md`.

## Existing DGM integration

- Deep and working: the hiring workflow (case → assessment linkage →
  recommendation → decision → action request → CER → authorization → execution →
  reconciliation) runs on the DGM kernel. `applications/ai_hiring/platform.py`
  composes it end-to-end in memory.
- **Surface note (RESOLVED in H0):** the consumer previously imported several kernel
  *internal* modules directly (`decision_governance.identity`, `.audit`, `.policy`,
  `.repositories`, `.actions`, `.execution`, `.services`) rather than the frozen
  `decision_governance.api` surface. **H0 migrated all consumer code to
  `decision_governance.api`** (see `H0_MIGRATION_REPORT.md` / `H0_REENTRY_STATUS.md`); only
  the tested backward-compat shims still reference internals by design
  (`H0_API_GAP_REPORT.md`).

## Existing provider integration

- **None.** Hiring does **not** use the provider framework, TAP, or ActionGate
  (`grep` confirms no `tap_provider` / `actiongate_provider` / `governance_providers`
  imports under `ai_hiring`, `domains/hiring`, `applications/ai_hiring`). Assertion
  evaluation and action authorization are done directly against the kernel, not
  through governance providers. Wiring TAP (assertion checks on hiring claims) and
  ActionGate (authorization of hiring actions) is the core re-entry opportunity.

## Public APIs

- `domains.hiring` re-exports: `EvidenceType`, `is_known_evidence_type`,
  `Capability`, `Rubric`, `RubricCapability`, `ScaleType`, `ScoringScale`,
  `EvidenceRule`.
- `applications.ai_hiring` exports: `HiringPlatform`, `build_in_memory_platform`.
- `ai_hiring` retains its historical package surface for import stability.

## Dependency direction

- `applications.ai_hiring` → {`domains.hiring`, `decision_governance`}; the reverse
  never holds. The frozen platform never imports hiring (verified by
  `platform_freeze` dependency checks).

## Placeholder markers

- Two `TODO`/placeholder markers remain in non-test hiring source (minor); no
  blocking stubs.

## Incomplete / not-yet-built (see gap analysis)

Candidate-facing product surface: job requisition/definition contracts, candidate/
application entities, evidence-collection intake, assessment workspace + structured
observations, AI recommendation *generation* (deliberately excluded to date),
offer/rejection execution workflows, and audit reconstruction reporting. Classified
in `Project_documentation/ai_hiring/docs/ai-hiring/AI_HIRING_COMPLETION_ROADMAP.md` and the gap table below is
summarised there.

## Test baseline

`python -m pytest ai_hiring` → **553 passing**. This is the AI-Hiring re-entry
baseline; the platform baseline (1006) includes it.
