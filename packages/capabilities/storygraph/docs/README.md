# StoryGraph Documentation

Canonical index for all StoryGraph-owned documentation. StoryGraph is an
**advisory** sequence-risk analyzer (package `ugence_storygraph`, distribution
`ugence-storygraph`). Every StoryGraph-owned document is reachable from here; the
per-document ownership + wheel-shipping table is in
[`DOCUMENT_OWNERSHIP.md`](./DOCUMENT_OWNERSHIP.md).

## Canonical reading order

1. **Overview** — [`architecture/CAPABILITY_OVERVIEW.md`](./architecture/CAPABILITY_OVERVIEW.md) and the package [`../README.md`](../README.md)
2. **Current specification** — [`architecture/`](./architecture/)
3. **Public API** — [`api/README.md`](./api/README.md)
4. **Policy Packs** — [`policy-packs/`](./policy-packs/)
5. **Replay** — [`replay/`](./replay/)
6. **Validation** — [`validation/`](./validation/)
7. **Evaluation & historical evidence** — [`evaluation/`](./evaluation/)
8. **Limitations** — [`limitations/KNOWN_LIMITATIONS.md`](./limitations/KNOWN_LIMITATIONS.md)

## Categories

| Category | Location | Purpose |
|---|---|---|
| **Architecture & core semantics** | [`architecture/`](./architecture/) | Capability overview + the current specs: `COMPOSITE_THREAT_DETECTION_SPEC.md`, `STORY_GRAPH_SPEC.md`, `STORY_GRAPH_PARTIAL_MATCH_SPEC.md`, `LINKAGE_SCHEMA.md`, `RECIPE_SCHEMA.md` |
| **Public API** | [`api/`](./api/) | Supported `ugence_storygraph.api` surface + stability/compatibility pointers |
| **Policy Packs** | [`policy-packs/`](./policy-packs/) | `ENTERPRISE_STORY_POLICY_PACK.md` — reference Policy Pack (policy-as-code) |
| **Replay** | [`replay/`](./replay/) | Historical-replay contract + readiness checklist + sanitized report; the shipped intake schema/templates live in the package at `../src/ugence_storygraph/replay_intake/` |
| **Validation** | [`validation/`](./validation/) | Partial-match, adversarial, and verification/validation reports |
| **Evaluation** | [`evaluation/`](./evaluation/) | Evaluation plan, split audit, evidence ledger, shadow-pilot template |
| **Evaluation — historical** | [`evaluation/historical/`](./evaluation/historical/) | Prior official evaluation reports (`PHASE3_FINAL_EVALUATION_REPORT.md`), preserved verbatim |
| **Reference** | [`reference/`](./reference/) | `MIGRATION_NOTES.md` — prototype→v2 history |
| **Limitations** | [`limitations/`](./limitations/) | Advisory-authority boundary, synthetic-only scope, known-pattern-only |

## Current specification

The authoritative behavior specs are in [`architecture/`](./architecture/):
`COMPOSITE_THREAT_DETECTION_SPEC.md` (the analyzer contract) and
`STORY_GRAPH_SPEC.md` / `STORY_GRAPH_PARTIAL_MATCH_SPEC.md` (matcher semantics),
with `LINKAGE_SCHEMA.md` and `RECIPE_SCHEMA.md` for the data model.

## Where things live

| Artifact | Location |
|---|---|
| Package front-matter | [`../README.md`](../README.md), [`../CHANGELOG.md`](../CHANGELOG.md), [`../MIGRATION.md`](../MIGRATION.md) |
| Runtime schemas (ship in wheel) | `../src/ugence_storygraph/policypack/schemas/`, `../src/ugence_storygraph/replay_intake/` |
| Runtime fixtures (ship in wheel) | `../src/ugence_storygraph/policypack/fixtures/`, `../src/ugence_storygraph/evaluation/fixtures/` |
| Runnable examples | [`../examples/`](../examples/) |
| **Package migration evidence (repository-only)** | [`../../../../docs/migrations/storygraph/`](../../../../docs/migrations/storygraph/) — BASELINE, API_INVENTORY, FILE_MAP, IMPORT_GRAPH, migration report. **Deliberately kept at the repository level, not shipped in the wheel.** |
| Evidence artifacts | `evaluation/STORY_GRAPH_EVIDENCE_LEDGER.md` + `evaluation/historical/` |

## What ships in the wheel vs repository-only

- **Ships (runtime):** the package README, JSON schemas, Policy Pack fixtures,
  replay-intake schema/templates, and the `examples/`. See
  [`DOCUMENT_OWNERSHIP.md`](./DOCUMENT_OWNERSHIP.md) for the exact list, proven by
  `../verify_storygraph_distribution.py`.
- **Repository-only (not shipped):** everything under `docs/` (architecture,
  evaluation, validation, historical evidence, limitations), and the repo-level
  migration evidence under `docs/migrations/storygraph/`.

## Legacy-name & compatibility guidance

The package was previously `composite_threat_detector` under
`cyber_security/composite_threat_detector/`. Legacy imports still resolve via a
compatibility redirect but are **deprecated**:

| Legacy (deprecated) | Canonical |
|---|---|
| `import composite_threat_detector` | `import ugence_storygraph` |
| `from composite_threat_detector.storygraph import …` | `from ugence_storygraph.storygraph import …` |
| `python -m composite_threat_detector.cli …` | `python -m ugence_storygraph.cli …` (or `ugence-storygraph …`) |

Frozen internal identifiers (`ctd.storygraph/…`, `ctd.storygraph.matcher/…`,
`ctd.witness.tiebreak/…`, …) are **semantic/version identifiers, not filesystem
names**, and are intentionally unchanged. See [`../MIGRATION.md`](../MIGRATION.md).
