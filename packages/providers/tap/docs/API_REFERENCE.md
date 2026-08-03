# API reference

Import the public surface from `ugence_tap_provider.api` (32 exports):

**Provider & configuration**
- `TAPProvider` — the `AssertionGovernanceProvider` implementation.
- `TapSettings`, `build_tap_provider(engine=None, *, settings=None, invocation_log=None, transport_fail=None)`.

**Clients** — `TapClient` (Protocol), `InProcessTapClient`, `RemoteTapClient`.

**Core vocabulary** — `TapEngine`, `TapEvaluationRequest`, `TapEvaluationResult`,
`TapOutcome`, `TapEvidenceItem`, `TapEvidenceClass`, `TapConstraint`,
`TapObligation`, `TapRule`.

**Mapping** — `map_request`, `map_result`, `indeterminate_result`,
`MAPPING_VERSION`, `KNOWN_CONSTRAINT_TYPES`, `KNOWN_OBLIGATION_TYPES`.

**Health / observability / conformance / errors** — `TapHealthReport`,
`check_health`, `TapInvocationLog`, `TapInvocationRecord`, `TapConformanceReport`,
`run_tap_conformance`, `translate_error`.

**Versions** — `__version__`, `CONTRACT_VERSION`, `TARGET_KERNEL_VERSION`,
`TARGET_FRAMEWORK_VERSION`.

Top-level module also exposes `version_info()` (structured distribution +
implementation metadata).

The `.api` surface is byte-stable across the canonical package and the legacy
`tap_provider` facade (identical objects). See
`docs/audits/tap_packaging/TAP_PUBLIC_API_BASELINE.md`.
