# Decision Authority — file map (before → after)

Pure relocation via `git mv` (history preserved). All internal imports are relative, so
**no import statements were edited** for the move; the only source edit is the conformance
kit's kernel-type module-prefix check (identity-path adjustment, both prefixes accepted).

## Canonical kernel (moved)

`decision_governance/<x>`  →  `packages/capabilities/decision-authority/src/ugence_decision_authority/<x>`

| Subpackage | Contents |
|---|---|
| `api/` | public interface: `services`, `contracts`, `ports`, `repositories`, `vocabulary`, `audit`, `identity`, `policy`, `errors`, `common` |
| `actions/` | `action_request`, `cer`, `authorization`, `action_mapping`, `control_plane`, `lifecycle`, `status`, `validation` |
| `decisions/` | `case`, `decision`, `authority`, `override`, `recommendation`, `review`, `subject`, `lifecycle`, `status`, `validation` |
| `audit/` | `event`, `events`, `namespace`, `repository`, `service` |
| `execution/` | `execution_intent`, `execution_attempt`, `execution_record`, `reconciliation`, `compensation`, `external_system`, `lifecycle`, `status`, `validation` |
| `identity/` | `actor`, `provider` |
| `policy/` | `access` |
| `ports/` | `linked_record` |
| `repositories/` | `action_request_repository`, `decision_case_repository`, `execution_repository` |
| `services/` | 14 governance services + 3 authz helpers |
| `conformance/` | domain-conformance kit (11 modules) |
| top-level | `base.py`, `common.py`, `errors.py`, `vocabulary.py`, `surface.py`, `version.py`, `__init__.py` |

Kernel `.py` files after move: **95** (7616 LOC); the 6 test files moved to the package
`tests/` root.

## Tests (moved + adapted)

`decision_governance/tests/*` → `packages/capabilities/decision-authority/tests/*`

- Behavior/surface guards kept, retargeted to the canonical namespace:
  `test_public_surface`, `test_frozen_vocabulary`, `test_compatibility`.
- Layout/packaging guards rewritten for the new layout: `test_platform_boundaries`,
  `test_kernel_packaging`, `test_distribution_packaging`.
- Added: `test_legacy_compatibility` (legacy↔canonical object identity).

## New files

- `packages/capabilities/decision-authority/{pyproject.toml, README.md, CHANGELOG.md, MIGRATION.md, verify_decision_authority_distribution.py}`
- `decision_governance/__init__.py` — logic-free compatibility shim (the ONLY remaining file in the legacy namespace).

## Modified (outside the kernel)

- `conftest.py` — add canonical `src` to the source-checkout path list.
- `packaging/decision-governance/{pyproject.toml, README.md}` — compatibility distribution.
- `platform/PLATFORM_FREEZE_V1.json` — structural re-baseline (2 fields).
- Consumer tests hard-coding the old module name: `ai_hiring/tests/test_direct_kernel_adoption.py`,
  `domains/procurement/tests/{test_cross_domain_conformance,test_procurement_domain}.py`
  (accept the canonical prefix; legacy prefix retained).

## Excluded (NOT moved — out of scope)

`domains/{hiring,procurement}`, `ai_hiring`, `applications/`, console, providers
(`governance_providers`, `tap_provider`, `actiongate_provider`), ACP, StoryGraph, Agent
Runtime, Model Selection, the AI Control Plane / orchestrator, product compositions,
research modules — none was moved. They import the kernel; that alone is not grounds to move.
