# Changelog — ugence-procurement

All notable changes to the independent Ugence Procurement distribution are recorded
here. This distribution version tracks **wheel packaging**, distinct from the
Procurement *product* version (`ugence_procurement.product.version.PRODUCT_VERSION`).

## 0.1.0 — first independent extraction

First independent, buildable, installable, testable Ugence Procurement distribution.

### Added
- Canonical package `ugence_procurement` (canonical namespace) — the single physical
  implementation of the procurement reference workflow, extracted from the monorepo
  `domains/procurement` + `applications/procurement` trees.
- Curated public API `ugence_procurement.api` (48 stable names), frozen against
  `artifacts/public_api.json`.
- `version_info()` / `product_maturity()` metadata with hard-coded
  `pilot_validated = False`, `production_certified = False`, and evidence maturity
  `REFERENCE_WORKFLOW_OFFLINE_VERIFIED`.
- CLI (`ugence-procurement` / `python -m ugence_procurement`): `version`, `verify`,
  `demo`, `report`. The demo runs a full deterministic offline lifecycle plus a
  fail-closed restricted-supplier scenario.
- Distribution verifier (`scripts/verify_procurement_distribution.py`) and behavior /
  public-API capture scripts.

### Changed
- Canonical source imports migrated from the legacy `decision_governance` namespace to
  the canonical `ugence-decision-authority` distribution (`ugence_decision_authority`).
  Import-path only; no procurement behavior changed.

### Compatibility
- Legacy `domains.procurement` and `applications.procurement` import paths preserved by
  logic-free compatibility facades (object identity preserved). `before == canonical ==
  legacy` across the frozen behavior-capture matrix.
- API compatibility classification: **MINOR** — the canonical namespace and
  `version_info()` are additive; legacy behavior is unchanged.

### Not included (deliberately)
- No ERP / marketplace / inventory / accounting / invoice / payment functionality.
- No AI scoring or autonomous purchasing.
- No production SAP Ariba / Coupa / ServiceNow / Oracle connector.
- No TAP or ActionGate dependency (deferred; see `docs/NEXT_PHASES.md`).
