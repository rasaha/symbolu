# Decision Authority — public API inventory

Two supported surfaces, both preserved with identical objects under the canonical namespace.

## Top-level (`__init__`) — 16 symbols

Legacy: `from decision_governance import …` · Canonical: `from ugence_decision_authority import …`

`__version__`, `DomainModel`, `GovernanceError`, `DomainValidationError`, `Clock`,
`IdFactory`, `new_id`, `utc_now`, `canonical_hash`, `ReasonCode`, `ReasonCodeSpec`,
`REASON_CODE_CATALOG`, `is_known_reason_code`, `get_reason_code_spec`, `UncertaintyLevel`,
`UncertaintyRule`.

## Stable API surface (`.api`)

`decision_governance.api` / `ugence_decision_authority.api` — the versioned, supported import
surface, re-exporting from these submodules:

| API module | Provides |
|---|---|
| `api.services` | governance services (e.g. `DecisionCaseService`) |
| `api.contracts` | record models + status/outcome/authority enums (e.g. `DecisionRecord`, `DecisionOutcome`) |
| `api.ports` | provider-neutral seams (`LinkedRecordPort`, control-plane, external-execution) |
| `api.repositories` | repository interfaces |
| `api.vocabulary` | `ReasonCode`, uncertainty vocabulary |
| `api.audit` | `AuditEventType`, `AuditService` |
| `api.identity` | actors/identity |
| `api.policy` | `Permission`, `AccessGrant` |
| `api.errors` | `GovernanceError`, `ExecutionError`, … |
| `api.common` | `canonical_hash`, clocks, id factories |

## Compatibility requirement

Every public symbol resolves to the **same object** via both namespaces (verified by
`tests/test_legacy_compatibility.py`). Serialization sensitivity: all record models —
the freeze `public_api_manifests.decision_governance.api` hash (`1b893869…`) and the
api-snapshot file are **byte-identical** before and after the move; all 29 model JSON
schemas are byte-identical; all 30 enums identical.

## Stability

Frozen at **1.0.0**. No symbol was added, removed, renamed, or made newly-public; no internal
helper was promoted to preserve an accidental import.
