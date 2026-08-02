# Public API Inventory (BEFORE) — governance_providers.api

**48** exported symbols (`__all__`), generated directly from the live module.
(The audit narrative says "47"; direct recollection shows **48** unique names — the
audit undercounted by one. The frozen snapshot `98dd02649e5fbb37879ef05e1b06afce1abd0cc10b5692b81974437d59f7a59b`
already covers all 48 and is the byte-identical target after migration.)

For each symbol: kind, semantic owner, current defining module, canonical defining module after relocation, serialization sensitivity. Legacy `governance_providers.api.<name>` and canonical `ugence_governance_provider_framework.api.<name>` must resolve to the **same object** (identity) where feasible; all remain importable via the shim.

| Symbol | Kind | Owner | Current module | Canonical module | Serialization |
|---|---|---|---|---|---|
| `__version__` | constant | GPF | `-` | `-` | value |
| `CONTRACT_VERSION` | constant | GPF | `-` | `-` | value |
| `ProviderKind` | enum | GC(contracts leaf, re-export) | `ugence_governance_contracts.metadata` | `ugence_governance_contracts.metadata` | value |
| `ProviderDescriptor` | dataclass | GC(contracts leaf, re-export) | `ugence_governance_contracts.metadata` | `ugence_governance_contracts.metadata` | value |
| `ProviderCapabilities` | dataclass | GC(contracts leaf, re-export) | `ugence_governance_contracts.metadata` | `ugence_governance_contracts.metadata` | value |
| `ProviderCompatibility` | dataclass | GC(contracts leaf, re-export) | `ugence_governance_contracts.metadata` | `ugence_governance_contracts.metadata` | value |
| `ProviderHealth` | dataclass | GC(contracts leaf, re-export) | `ugence_governance_contracts.metadata` | `ugence_governance_contracts.metadata` | value |
| `ProviderLifecycleState` | enum | GC(contracts leaf, re-export) | `ugence_governance_contracts.lifecycle` | `ugence_governance_contracts.lifecycle` | value |
| `Provider` | protocol | GC(contracts leaf, re-export) | `ugence_governance_contracts.contracts.base` | `ugence_governance_contracts.contracts.base` | - |
| `BaseProvider` | class | GC(contracts leaf, re-export) | `ugence_governance_contracts.contracts.base` | `ugence_governance_contracts.contracts.base` | - |
| `AssertionGovernanceProvider` | protocol | GC(contracts leaf, re-export) | `ugence_governance_contracts.contracts.assertion` | `ugence_governance_contracts.contracts.assertion` | - |
| `AssertionGovernanceRequest` | dataclass | GC(contracts leaf, re-export) | `ugence_governance_contracts.contracts.assertion` | `ugence_governance_contracts.contracts.assertion` | value |
| `AssertionGovernanceResult` | dataclass | GC(contracts leaf, re-export) | `ugence_governance_contracts.contracts.assertion` | `ugence_governance_contracts.contracts.assertion` | value |
| `AssertionCoverage` | enum | GC(contracts leaf, re-export) | `ugence_governance_contracts.contracts.assertion` | `ugence_governance_contracts.contracts.assertion` | value |
| `ActionGovernanceProvider` | protocol | GC(contracts leaf, re-export) | `ugence_governance_contracts.contracts.action` | `ugence_governance_contracts.contracts.action` | - |
| `ActionGovernanceRequest` | dataclass | GC(contracts leaf, re-export) | `ugence_governance_contracts.contracts.action` | `ugence_governance_contracts.contracts.action` | value |
| `ActionGovernanceResult` | dataclass | GC(contracts leaf, re-export) | `ugence_governance_contracts.contracts.action` | `ugence_governance_contracts.contracts.action` | value |
| `ActionGovernanceOutcome` | enum | GC(contracts leaf, re-export) | `ugence_governance_contracts.contracts.action` | `ugence_governance_contracts.contracts.action` | value |
| `ExternalExecutionProvider` | protocol | GC(contracts leaf, re-export) | `ugence_governance_contracts.contracts.execution` | `ugence_governance_contracts.contracts.execution` | - |
| `ExecutionDispatchRequest` | dataclass | GC(contracts leaf, re-export) | `ugence_governance_contracts.contracts.execution` | `ugence_governance_contracts.contracts.execution` | value |
| `ExecutionDispatchResult` | dataclass | GC(contracts leaf, re-export) | `ugence_governance_contracts.contracts.execution` | `ugence_governance_contracts.contracts.execution` | value |
| `ExecutionObservation` | dataclass | GC(contracts leaf, re-export) | `ugence_governance_contracts.contracts.execution` | `ugence_governance_contracts.contracts.execution` | value |
| `ExecutionBusinessOutcome` | enum | GC(contracts leaf, re-export) | `ugence_governance_contracts.contracts.execution` | `ugence_governance_contracts.contracts.execution` | value |
| `ProviderRegistry` | class | GPF | `governance_providers.registry` | `ugence_governance_provider_framework.registry` | - |
| `resolve` | function | GPF | `governance_providers.resolution` | `ugence_governance_provider_framework.resolution` | - |
| `ResolutionRequest` | dataclass | GPF | `governance_providers.resolution` | `ugence_governance_provider_framework.resolution` | value |
| `ResolutionRecord` | dataclass | GPF | `governance_providers.resolution` | `ugence_governance_provider_framework.resolution` | value |
| `SelectionRule` | enum | GPF | `governance_providers.resolution` | `ugence_governance_provider_framework.resolution` | value |
| `ProvidersConfiguration` | dataclass | GPF | `governance_providers.configuration` | `ugence_governance_provider_framework.configuration` | value |
| `ProviderEntry` | dataclass | GPF | `governance_providers.configuration` | `ugence_governance_provider_framework.configuration` | value |
| `ActionGovernanceControlPlaneAdapter` | class | GPF-adapter(optional/kernel-bound) | `governance_providers.adapters.action_to_control_plane` | `ugence_governance_provider_framework.adapters.action_to_control_plane` | - |
| `ExternalExecutionAdapter` | class | GPF-adapter(optional/kernel-bound) | `governance_providers.adapters.execution_to_external_system` | `ugence_governance_provider_framework.adapters.execution_to_external_system` | - |
| `AssertionAssessmentIntegration` | class | GPF-adapter(optional/kernel-bound) | `governance_providers.adapters.assertion_integration` | `ugence_governance_provider_framework.adapters.assertion_integration` | - |
| `AssertionAssessment` | dataclass | GPF-adapter(optional/kernel-bound) | `governance_providers.adapters.assertion_integration` | `ugence_governance_provider_framework.adapters.assertion_integration` | value |
| `AssertionLinkedRecordAdapter` | class | GPF-adapter(optional/kernel-bound) | `governance_providers.adapters.assertion_integration` | `ugence_governance_provider_framework.adapters.assertion_integration` | - |
| `ProviderInvocationLog` | class | GPF | `governance_providers.observability` | `ugence_governance_provider_framework.observability` | - |
| `ProviderInvocationRecord` | dataclass | GPF | `governance_providers.observability` | `ugence_governance_provider_framework.observability` | value |
| `record_invocation` | function | GPF | `governance_providers.observability` | `ugence_governance_provider_framework.observability` | - |
| `ProviderError` | exception | GC(contracts leaf, re-export) | `ugence_governance_contracts.errors` | `ugence_governance_contracts.errors` | - |
| `ProviderRegistrationError` | exception | GC(contracts leaf, re-export) | `ugence_governance_contracts.errors` | `ugence_governance_contracts.errors` | - |
| `ProviderResolutionError` | exception | GC(contracts leaf, re-export) | `ugence_governance_contracts.errors` | `ugence_governance_contracts.errors` | - |
| `ProviderCompatibilityError` | exception | GC(contracts leaf, re-export) | `ugence_governance_contracts.errors` | `ugence_governance_contracts.errors` | - |
| `ProviderConfigurationError` | exception | GC(contracts leaf, re-export) | `ugence_governance_contracts.errors` | `ugence_governance_contracts.errors` | - |
| `ProviderUnavailableError` | exception | GC(contracts leaf, re-export) | `ugence_governance_contracts.errors` | `ugence_governance_contracts.errors` | - |
| `ProviderTimeoutError` | exception | GC(contracts leaf, re-export) | `ugence_governance_contracts.errors` | `ugence_governance_contracts.errors` | - |
| `ProviderProtocolError` | exception | GC(contracts leaf, re-export) | `ugence_governance_contracts.errors` | `ugence_governance_contracts.errors` | - |
| `ProviderResultValidationError` | exception | GC(contracts leaf, re-export) | `ugence_governance_contracts.errors` | `ugence_governance_contracts.errors` | - |
| `FailureClass` | enum | GC(contracts leaf, re-export) | `ugence_governance_contracts.errors` | `ugence_governance_contracts.errors` | value |

## Ownership summary

- GC(contracts leaf, re-export): 31
- GPF: 12
- GPF-adapter(optional/kernel-bound): 5

**Compatibility requirement:** top-level + deep imports preserved; public protocols, reference implementations, registry types, errors, metadata, and conformance utilities preserved; object identity preserved across the legacy shim. No private helper is promoted to public.
