# Changelog — ugence-agent-constitution

## [0.1.0] — AC-0: agent constitution contracts

**Initial release.** Creates the leaf contract package
`packages/contracts/agent-constitution` (distribution `ugence-agent-constitution`,
namespace `ugence_agent_constitution`). No existing package is modified, and
nothing outside this package imports it.

### Added — the artifacts

Six frozen, `extra="forbid"` pydantic models:

* `AgentRoleManifest` — the drafting artifact. Carries no authority
  (`carries_authority` and `is_ratified` are permanently `False` class-level
  constants, not fields). Revised by copy-on-write via `revise()`, which advances
  `draft_revision` and clears the stale digest.
* `AgentConstitution` — ratified, immutable, versioned. Carries issuer identity,
  schema version, artifact version, an optional predecessor reference, and a
  canonical content digest.
* `CapabilityRequirement` — one obligation (`MANDATORY` / `CONDITIONAL` /
  `PROHIBITED`), optionally pinning a registry entry.
* `CapabilityRegistryEntryRef` — an opaque, co-required `namespace/entry@version`
  plus digest token. This package owns no registry and resolves nothing.
* `DeveloperImplementationContract` — implementation obligations pinned to one
  constitution version.
* `ConformanceSubject` — a declared subject of a *future* assessment.
  `conformance_evaluated` is permanently `False`.

Plus the supporting reference types `ContentRef`, `ConstitutionRef`,
`PredecessorRef`, `IssuerIdentity` and the base `FrozenArtifact`.

### Added — canonical serialization and fingerprinting

`to_canonical_obj` / `dumps` / `dumps_pretty` / `loads`, semantically **identical
by value** to `ugence_policy_workflow_compiler.serialization.canonical_json`
(sorted keys, compact separators, enums by value, sets sorted, UTF-8 preserved).
Duplicated rather than imported so the package stays a leaf; the equivalence is
gated by a test that loads the compiler's module directly off disk.

SHA-256 fingerprinting as `sha256:<64 hex>` over the canonical encoding, with a
digest-bearing artifact excluding its own digest field from its own scope so
stamping is idempotent. Fingerprinting is not signing; AC-0 ships none.

### Added — deterministic, fail-closed validation

`validate_artifact()` runs a schema layer then, only on a payload that actually
constructed, a semantic layer. Three outcomes — `VALID`, `INVALID`,
`INDETERMINATE` — aggregated as `INVALID` > `INDETERMINATE` > `VALID`, with
`ValidationReport.is_usable` true for `VALID` alone. A report's outcome is always
derived from its findings, never asserted independently of them, so a report
cannot claim `VALID` while carrying an `INVALID` finding.

Twenty-eight declared finding codes, all `AC_`-namespaced and asserted to be a
closed set. Validation reads no clock, environment, filesystem or random source
and never raises for bad data.

### Added — version-compatibility rules

`schema_compatibility()` classifies a declared schema version as `SUPPORTED`,
`RETIRED` (a hard `INVALID`) or `UNRECOGNIZED` (an `INDETERMINATE`).
`succession_compatibility()` requires a successor to keep its lineage identity,
bump `artifact_version` strictly upward, and materially differ from its
predecessor. Only release `MAJOR.MINOR.PATCH` versions are ordered; pre-release
and build-metadata suffixes are refused rather than ordered.

### Added — tests

222 tests covering canonical-serialization stability, fingerprint stability and
change-on-material-edit, the required version bump, missing and ambiguous
mandatory fields, draft-is-not-a-constitution, self-ratification rejection,
property-based mutation of both the drafting and the ratified manifest
(hypothesis), negative controls proving each invariant test fails when the
invariant is inverted, and an import-boundary gate asserting the package imports
no other `ugence_*` package.

### Not in this release — and not merely unimplemented

No compiler, no capability registry, no conformance findings or verdicts, no
signing, no UI, no LLM assistance, no runtime binding, and no authority decision.
Each is reported `False` by `version_info()` and absent from the curated surface.
Not pilot-validated. Not production-certified.

The names `CapabilityRegistry`, `CapabilityDefinition`, `CapabilityManifest`,
`CompilationResult`, `AuthorityRequirement`, `GovernanceDisposition` and
`resolve_policy` belong to other packages and are not reused here; a test asserts
the surface contains none of them.
