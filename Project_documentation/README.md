# Project_documentation

Centralized home for **legacy and project-level documentation** in `rasaha/symbolu`.

> **Status: Stage 1 — inventory & plan only.** This directory currently contains
> only the migration planning artifacts. **No existing documentation has been
> moved, renamed, deleted, or rewritten.** The actual relocation of documents
> (Stage 2) happens only after the migration manifest here has been independently
> audited and approved.

## What lives here

| File | Purpose |
|---|---|
| [`MIGRATION_MANIFEST.md`](MIGRATION_MANIFEST.md) | Authoritative Stage-1 manifest: inventory totals, logical module map, exclusions, duplicate/ambiguity analysis, reference-repair points, and the G1–G12 verification record. |
| [`manifests/`](manifests/) | Full per-file classification tables, split by logical module, plus the exclusion accounting files. |

## Scope

### Active package documentation — stays put
Documentation under `packages/**` (capabilities, products, providers, runtime,
tooling, risk_authority, governance-provider-framework, governance-contracts)
**remains authoritative and colocated with its packages**. It is out of scope for
this migration and is never relocated here. See
[`manifests/EXCLUDED_packages.md`](manifests/EXCLUDED_packages.md).

### Hybrid LLM material — explicitly outside this migration
The active Hybrid-LLM lineage — neural-model training, KV-cache / CTM integration
research, quantization (INT4/FP8), phase/attention research, Varṇa
symbolic-representation research, and the Symbol-U theory corpus — is **excluded
by semantics, not merely by path**. It is not moved and not indexed here. The
explicit boundary and full file list are in
[`manifests/EXCLUDED_hybrid_llm.md`](manifests/EXCLUDED_hybrid_llm.md).

Note: material is **not** treated as Hybrid-LLM merely because a directory name
contains "hybrid" (e.g. `agentic/hybrid_handover/**` is governance research and
stays a migration candidate), nor is it treated as legacy merely because it sits
outside a folder named `Hybrid_LLM`.

### Project_documentation — the intended centralized home
`Project_documentation/**` is intended to become the centralized home for:

- legacy project documentation,
- historical architecture,
- legacy experiments,
- superseded designs, and
- project-level documentation that does not belong to an active package.

It will be organized by **logical module** (see the module map in the manifest),
not by a blind copy of today's physical directory layout. Category subdirectories
(`architecture/`, `specifications/`, `design/`, `guides/`, `experiments/`,
`validation/`, `audits/`, `migration/`, `historical/`) are created **only where
repository evidence justifies them** — empty category directories are not created.

### Legacy code — untouched
Legacy implementation directories (source code, tests, benchmarks) remain
**untouched** during this phase. Where a legacy module's detailed documentation is
eventually centralized here, the intended end-state leaves a small
navigation/developer stub `README.md` next to the code. No such change is made in
Stage 1.

## Stage boundary

Stage 1 produces the manifest for audit. It does **not** authorize Stage 2. Read
[`MIGRATION_MANIFEST.md`](MIGRATION_MANIFEST.md) for the complete plan and the
`STAGE_1_READY_FOR_AUDIT` decision record.
