# Source Provenance

`ugence-ai-hiring` was produced by **extracting** the existing `ai_hiring/`
source tree into an independent package, with mechanical import rewrites. This
document records how the extraction was done and where the provenance is
captured.

## Extraction method

The package was created by copying the `ai_hiring/` tree and applying import
rewrites:

- `ai_hiring` -> `ugence_ai_hiring`
- `decision_governance` -> `ugence_decision_authority`
- `governance_providers` -> `ugence_governance_provider_framework`

The original `ai_hiring/` tree is **preserved unchanged** in the monorepo.

## Recorded provenance

Provenance is recorded in the package's `artifacts/` directory:

- `artifacts/source_manifest.json` — per-file provenance manifest.
- `artifacts/source_hashes.json` — content hashes for the extracted files.

## File classifications

Every extracted file is classified by how it changed relative to its source:

| Classification | Count | Meaning |
| --- | --- | --- |
| `BYTE_IDENTICAL` | 121 | Copied with no changes at all. |
| `IMPORT_ONLY_CHANGE` | 180 | Only the import rewrites above were applied. |
| `SEMANTIC_EXTRACTION` | 8 | Changes beyond imports required for extraction. |
| `NEW_PACKAGING_FILE` | 4 | New files introduced for packaging. |

The large majority of files are either byte-identical or import-only changes,
which keeps behavior aligned with the original source.

## Relationship to the compatibility facade

The extraction preserves the public surface. A logic-free `ai_hiring`
compatibility facade re-exports the extracted objects, preserving object
identity and deep submodule paths. See
[PUBLIC_API_COMPATIBILITY.md](PUBLIC_API_COMPATIBILITY.md) and
[MIGRATION_FROM_AI_HIRING.md](MIGRATION_FROM_AI_HIRING.md).
