# Architecture

`ugence-policy-workflow-compiler` is a deterministic tooling product. It takes a
reviewed, structured governance policy pack and compiles it into a
governed-workflow intermediate representation (IR) plus an assurance package. It
makes no binding decision, approves nothing, authorizes nothing, and executes
nothing.

## Layered structure

The package is organized into cooperating layers, each with a single
responsibility:

- **`models/`** — The object model. Twenty frozen pydantic object categories
  (`extra='forbid'`) plus the policy-pack lifecycle. Predicates are declarative
  (`fact_key` + `Comparator` + `value`), never executable Python.
- **`validation/`** — Structured, fail-closed validation. Produces diagnostics
  with explicit severities and enforces authority boundaries.
- **`compiler/`** — Workflow IR synthesis, the data-driven capability registry,
  assurance generation, the audit schema, and release/packaging.
- **`diff/`** — Exact, object-level structural comparison between two packs or
  compiled packages, with an impact summary.
- **`approval/`** — The `HumanApprovalRecord` model and digest binding.
- **`serialization/`** — Canonical JSON (sorted keys) used everywhere a digest
  or reproducible artifact is produced.
- **verification** (`scripts/`) — Distribution and determinism verifiers that
  confirm reproducibility and packaging guarantees.

The public API is a single curated module, `ugence_policy_workflow_compiler.api`
(71 names), frozen in `artifacts/public_api.json`.

## The five-stage pipeline

Compilation proceeds through discrete, ordered stages. Each stage consumes the
output of the prior stage; a stage that emits a blocking diagnostic halts the
pipeline (fail-closed).

1. **Stage 1 — Ingest / bind.** Load the structured policy pack and its
   lifecycle status. Only a pack in the `APPROVED` state may compile.
2. **Stage 2 — Model checks.** Validate object shape, frozen-model constraints,
   references, and provenance presence. Objects with no provenance are
   `PROPOSED_ONLY` / `REVIEW_REQUIRED` and are excluded from synthesis.
3. **Stage 3 — Precursor validation and synthesis.** First, run structured
   validation (duplicate ids, dangling references, missing authority, approval
   ordering, segregation-of-duties contradictions, and so on). Any diagnostic at
   `REVIEW_REQUIRED`, `ERROR`, or `FATAL` blocks compilation. If validation
   passes, **synthesize the workflow IR**: content-addressed nodes and ordered
   edges. Synthesis only emits capabilities the policy actually requires.
   Authority-boundary violations are `FATAL` here.
4. **Stage 4 — Assurance generation.** Produce deterministic test
   *specifications* across fourteen categories and build a coverage matrix.
   Compilation fails (`INCOMPLETE_COVERAGE`) if any required object lacks
   coverage.
5. **Stage 5 — Approval binding and release.** Bind the human approval record to
   the pack's structural digest, assemble the canonical compiled package, and
   record release metadata separately from the logical digest.

## Data flow

```
policy pack (APPROVED)
    -> model checks + provenance gating
    -> structured validation (fail-closed)
    -> workflow IR synthesis (content-addressed nodes, ordered edges)
    -> assurance test specs + coverage matrix
    -> approval binding (structural digest)
    -> canonical compiled package (10 JSON files)
```

The compiled package is a set of canonical JSON files: `manifest.json`,
`policy_pack.json`, `workflow_ir.json`, `capability_manifest.json`,
`assurance_manifest.json`, `coverage_matrix.json`, `audit_schema.json`,
`approval_record.json`, `validation_report.json`, and `structural_digest.json`.

## Design invariants

- Determinism end to end: identical approved input plus identical compiler
  version yields an identical *logical* package digest.
- Fail-closed: blocking diagnostics stop compilation; severity is never silently
  reclassified.
- No fabrication: the compiler never invents provenance and never approves its
  own output.
- Metadata-only capability resolution: an optional installation probe never
  imports a provider.
