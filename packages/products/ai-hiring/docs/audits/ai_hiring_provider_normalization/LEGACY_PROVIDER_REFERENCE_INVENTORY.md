# Legacy Provider Reference Inventory

Inventory of every TAP / ActionGate legacy-provider reference in
`packages/products/ai-hiring`, with its migration disposition. Machine-readable
companion: [`legacy_provider_reference_inventory.json`](./legacy_provider_reference_inventory.json).

Search terms: `dgm-tap-provider`, `dgm-actiongate-provider`, `tap_provider`,
`actiongate_provider`, `tap_legacy_adapter`, `actiongate_legacy_adapter`,
`LegacyProviderUnavailable`, `tap_legacy`, `actiongate_legacy`.

## Production migration surface (before → after)

| Path | Item | Before | After | Class | Disposition |
|---|---|---|---|---|---|
| `pyproject.toml` | `tap` extra | `dgm-tap-provider` | `ugence-tap-provider>=0.1.0` | OPTIONAL_EXTRA | MIGRATED |
| `pyproject.toml` | `actiongate` extra | `dgm-actiongate-provider` | `ugence-actiongate-provider>=0.1.0` | OPTIONAL_EXTRA | MIGRATED |
| `integrations/tap_adapter.py` | concrete import | — | `from ugence_tap_provider.provider import TAPProvider` (lazy) | CANONICAL_ADAPTER | ADDED |
| `integrations/actiongate_adapter.py` | concrete import | — | `from ugence_actiongate_provider.provider import ActionGateProvider` (lazy) | CANONICAL_ADAPTER | ADDED |
| `integrations/tap_legacy_adapter.py` | module | concrete adapter → `tap_provider` | logic-free facade → `tap_adapter` | COMPATIBILITY_MODULE | CONVERTED_TO_FACADE |
| `integrations/actiongate_legacy_adapter.py` | module | concrete adapter → `actiongate_provider` | logic-free facade → `actiongate_adapter` | COMPATIBILITY_MODULE | CONVERTED_TO_FACADE |
| `integrations/__init__.py` | exception | `LegacyProviderUnavailable` | `ProviderUnavailable` + identity alias `LegacyProviderUnavailable` | COMPATIBILITY_MODULE | ALIAS_ADDED |
| `version.py` | `_OPTIONAL_INTEGRATIONS['tap_legacy']` | `tap_provider` | `ugence_tap_provider` | VERSION_METADATA | MIGRATED_PROBE |
| `version.py` | `_OPTIONAL_INTEGRATIONS['actiongate_legacy']` | `actiongate_provider` | `ugence_actiongate_provider` | VERSION_METADATA | MIGRATED_PROBE |

**No production-code runtime behavior changes.** Every occurrence is a
dependency/import label or metadata probe; the adapters remain lazy, logic-free,
and dependency-injected, and the exception behavior is preserved.

## Tests, docs, verifier, CI

| Path | Class | Disposition |
|---|---|---|
| `tests/integrations/test_canonical_adapters.py` | TEST | ADDED |
| `tests/integrations/test_legacy_adapters.py` | TEST | UPDATED (probes canonical; asserts legacy-path identity) |
| `tests/packaging/test_dependency_boundaries.py` | TEST | UPDATED (canonical roots in integrations only; legacy namespaces forbidden everywhere) |
| `tests/packaging/test_provider_dependency_metadata.py` | TEST | ADDED |
| `tests/packaging/test_determinism.py` | TEST | UPDATED (`distribution_version == 0.1.1`) |
| `tests/test_h{2..6}_boundary.py`, `test_h2_generation.py` | TEST | UNCHANGED (H-phase core never imported concrete providers) |
| `docs/TAP_ACTIONGATE_DEPENDENCY_BOUNDARY.md` | DOCUMENTATION | UPDATED |
| `docs/PROVIDER_DEPENDENCY_MIGRATION.md` | DOCUMENTATION | ADDED |
| `scripts/verify_ai_hiring_distribution.py` | PACKAGING_VERIFIER | EXTENDED (clean-install matrix + METADATA audit) |
| `scripts/ai_hiring_provider_normalization_capture.py` | PACKAGING_VERIFIER | ADDED (behavioral capture) |
| `.github/workflows/ai-hiring-package-ci.yml` | CI | EXTENDED (behavioral-equivalence job; provider srcs) |

## Retained historical / external references (not owned by AI Hiring)

| Path | Class | Disposition |
|---|---|---|
| `platform/PLATFORM_FREEZE_V1.json` (`dgm-*`, provider tree hashes) | PLATFORM_FREEZE | UNCHANGED (no frozen tree touched; freeze digest identical) |
| `packaging/dgm-tap-provider`, `packaging/dgm-actiongate-provider` | EXTERNAL_CONSUMER | UNCHANGED (usable for old deployments; re-export the canonical providers) |
| `artifacts/source_manifest.json`, `artifacts/source_hashes.json` | HISTORICAL_EVIDENCE | UNCHANGED (provenance of the 0.1.0 extraction) |

## Counts

| Metric | Before | After |
|---|---|---|
| Production optional-extra references to `dgm-*` | 2 | 0 |
| Production concrete imports of the legacy `tap_provider`/`actiongate_provider` namespaces | 2 | 0 |
| Production canonical adapter modules | 0 | 2 |
| Preserved compatibility facades | 2 | 2 |
| Version-metadata probes migrated to canonical | 0 | 2 |
| `dgm-*` requirements in the final wheel METADATA | 2 | 0 |
