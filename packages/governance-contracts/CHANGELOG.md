# Changelog — ugence-governance-contracts

## [0.1.0] — canonical-package extraction

**Physical restructuring and packaging change with ZERO semantic change.** The
neutral governance contracts were extracted verbatim from `governance_providers`
into this canonical leaf package. All fields, defaults, enum values, verdict
names, serialization keys, canonical hashes, digests, equality, validation, and
authority meanings are **unchanged**.

### Added
- Canonical leaf package `ugence_governance_contracts` (stdlib-only) containing the
  provider-neutral request/result contracts, provider protocols, provider
  metadata, lifecycle states, and the error taxonomy.
- Curated `ugence_governance_contracts.api` public surface.
- `pyproject.toml` (independent wheel, zero third-party deps),
  `verify_governance_contracts_distribution.py` (clean-venv `--no-index` proof).
- Equivalence/compatibility/contract/leaf test suite.

### Changed
- `governance_providers` contract modules (`errors`, `lifecycle`, `metadata`,
  `contracts/*`) are now logic-free re-export shims importing from this package;
  `governance_providers.api` is byte-identical (api-snapshot hash unchanged).
- `dgm-provider-framework` wheel now depends on `ugence-governance-contracts`.
- Platform freeze re-baselined for the `governance_providers` core-tree hash only
  (a structural PATCH; no API or contract-semantic change).

### Deferred (documented, not implemented)
- Tenant/environment identity, standard error envelope, idempotency/expiry
  contracts, CER/audit unification — see the contract-gap evolution plan.
