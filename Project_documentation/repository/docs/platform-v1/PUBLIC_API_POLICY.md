# Platform v1.0 — Public API Policy

## Public surfaces

The frozen public API of each core component is exactly:

- `decision_governance.api` — the governance kernel public surface (contracts,
  services, ports, audit, identity, policy, repositories, vocabulary, errors).
- `governance_providers.api` — neutral provider contracts, registry, resolution,
  configuration, adapters, observability, errors, lifecycle, metadata.
- `actiongate_provider.api` — the ActionGate provider surface.
- `tap_provider.api` — the TAP provider surface.

Canonical snapshots live in `platform/api-snapshots/<module>.json`; their hashes
are recorded in `platform/PLATFORM_FREEZE_V1.json`.

## What is public vs internal

- **Public:** every symbol re-exported from a `*.api` module — its name, kind,
  function/method signatures, protocol methods, enum values, dataclass/model
  fields, documented exception types, and version values.
- **Internal:** everything not re-exported through a `*.api` module, including
  deeper module paths. Consumers must import only from the `*.api` surfaces.
  (Note: the historical `ai_hiring` consumer imports several kernel modules
  directly; migrating it to `decision_governance.api` is tracked in the AI-Hiring
  re-entry baseline and is APPLICATION_LOCAL work.)

## Compatibility guarantees

- **Removed / renamed symbol, removed enum value, removed field, new *required*
  field or parameter, changed protocol method, changed exception bases** →
  BREAKING (MAJOR); fails `platform_freeze` verification unless the platform major
  is advanced.
- **New symbol, new optional field/parameter, new enum value, new protocol
  method, backward-compatible observability** → ADDITIVE (MINOR).
- **Docstring/behaviour-preserving internal change** → PATCH.

The `platform_freeze.compat` checker enforces this against the stored snapshots.
