# API Reference

Import the public surface from `ugence_actiongate_provider.api` (26 exports).

## Provider & configuration
- `ActionGateProvider` — the `ActionGovernanceProvider` implementation (method: `authorize`, `health`, lifecycle).
- `build_actiongate_provider(engine=None, *, settings=None, invocation_log=None, transport_fail=None)` — factory.
- `ActionGateSettings` — configuration (`mode`: `in_process` | `remote`).

## Core vocabulary
- `ActionGateEngine` — deterministic reference policy engine.
- `ActionGateRequest`, `ActionGateDecision`, `ActionGateOutcome` (`ALLOW`, `ALLOW_WITH_CONSTRAINTS`, `DENY`, `UNKNOWN`).
- `ActionGateConstraint`, `ActionGateObligation`, `ConstrainedRule`.

## Clients
- `ActionGateClient` (Protocol), `InProcessActionGateClient`, `RemoteActionGateClient`.

## Mapping
- `MAPPING_VERSION` (`actiongate-map-1`), `KNOWN_CONSTRAINT_TYPES`, `KNOWN_OBLIGATION_TYPES`.

## Health, conformance, observability
- `check_health`, `ActionGateHealthReport`.
- `run_actiongate_conformance`, `ActionGateConformanceReport`.
- `ActionGateInvocationLog`, `ActionGateInvocationRecord`.

## Version
- `__version__`, `CONTRACT_VERSION`, `TARGET_KERNEL_VERSION`, `TARGET_FRAMEWORK_VERSION`.
- top-level `ugence_actiongate_provider.version_info()` → `VersionInfo` (additive helper).

The result type is the framework's neutral `ActionGovernanceResult`
(`outcome`, `constraints`, `obligations`, `expiry`, `authority_basis`, `reason_codes`,
`provider_trace_id`, `fingerprint`).
