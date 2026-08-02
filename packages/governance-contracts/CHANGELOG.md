# Changelog — ugence-governance-contracts

## [Unreleased] — package hardening (audit follow-up, no contract change)

Bounded packaging/CI/typing/documentation hardening from the live audit
(`docs/GOVERNANCE_CONTRACTS_LIVE_AUDIT.md`). **No contract field, enum value,
default, serialization, or authority meaning changed.**

### Added
- Scoped CI workflow `.github/workflows/governance-contracts-ci.yml` (package
  suite + GPF compatibility surface, isolated wheel install, platform-freeze).
- PEP 561 `py.typed` marker (shipped in the wheel via package-data) — the leaf is
  fully type-annotated.
- Machine-readable `public_api.json` + `tests/packaging/test_public_api.py`
  asserting the documented API equals the actual package surface.

### Changed
- `verify_governance_contracts_distribution.py` now also asserts `py.typed` ships
  in the wheel and is installed.
- README: note typing support, the public-API snapshot, and the precise (two-hop)
  legacy-compatibility mechanism.

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
