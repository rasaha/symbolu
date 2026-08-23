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

`to_canonical_obj` / `dumps` / `dumps_pretty` / `loads` (sorted keys, compact
separators, enums by value, sets sorted, UTF-8 preserved). This package is the
**canonical owner** of these rules for Agent Constitution contracts; the published
functions are that contract. `ugence_policy_workflow_compiler` carries a legacy copy
of the same semantics, awaiting migration onto the published contract; a
one-directional compatibility ratchet loads it off disk and asserts it still matches
this package's output, so it cannot drift before it is retired.

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

223 tests covering canonical-serialization stability, fingerprint stability and
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

### Reconciled against ratified owner decisions 1–5

The five owner decisions were ratified after this package was built and are
recorded verbatim in ADR §10. Decisions 1 (compiler), 3 (Conformance Authority
signing), 4 (`packages/contracts/` tier) and 5 (Credential Broker) are consistent
with the implementation as shipped and required no change.

Decision 2 (canonicalization) contradicted ADR §4 as originally written, which
described this package's canonical JSON as "identical by value" to the compiler's
and the comparison between them as a mutual equivalence gate. The ratified decision
makes this package the **canonical owner**, so §4 was rewritten, the
byte-comparison test was renamed to
`tests/serialization/test_canonical_json_compatibility_ratchet.py` and reframed as a
one-directional migration ratchet, and the module, README and API snapshot note were
corrected to match. **No canonicalization logic changed**: canonical output and every
fingerprint are byte-identical before and after, which the unchanged serialization
tests and the pinned digest literal hold fixed. The public surface is unchanged at 56
symbols, so the package version stays `0.1.0`.

The names `CapabilityRegistry`, `CapabilityDefinition`, `CapabilityManifest`,
`CompilationResult`, `AuthorityRequirement`, `GovernanceDisposition` and
`resolve_policy` belong to other packages and are not reused here; a test asserts
the surface contains none of them.
