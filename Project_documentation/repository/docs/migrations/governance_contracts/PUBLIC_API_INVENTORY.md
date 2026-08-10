# Governance Contracts — Public API Inventory (C1/§9)

Produced before movement. Every migrated symbol, its legacy path, canonical
replacement, stability, and compatibility requirement. All symbols are
`PUBLIC_STABLE` (they are the frozen `governance_providers` contract surface).
The two lifecycle mechanics are `CAPABILITY_INTERNAL` (framework-only; kept on the
full namespace, excluded from the curated `api`).

Legacy path prefix: `governance_providers` (`.api`, `.contracts`, `.errors`,
`.lifecycle`, `.metadata`, and the deep `contracts.{base,action,assertion,execution}`).
Canonical: `ugence_governance_contracts` (`.api` + full namespace).

| Symbol | Type | Legacy path | Canonical path | Stability | Serialization-sensitive | Compat requirement |
|---|---|---|---|---|---|---|
| `Provider` | protocol | `governance_providers.contracts` | `…api` | PUBLIC_STABLE | no | identity re-export |
| `BaseProvider` | class | `governance_providers.contracts` | `…api` | PUBLIC_STABLE | no | identity re-export |
| `ActionGovernanceRequest` | dataclass | `…contracts.action` | `…api` | PUBLIC_STABLE | **yes** | fields/defaults frozen |
| `ActionGovernanceResult` | dataclass | `…contracts.action` | `…api` | PUBLIC_STABLE | **yes** | fields/defaults frozen |
| `ActionGovernanceProvider` | protocol | `…contracts.action` | `…api` | PUBLIC_STABLE | no | identity re-export |
| `ActionGovernanceOutcome` | enum | `…contracts.action` | `…api` | PUBLIC_STABLE | **yes** | values frozen |
| `AssertionGovernanceRequest` | dataclass | `…contracts.assertion` | `…api` | PUBLIC_STABLE | **yes** | fields/defaults frozen |
| `AssertionGovernanceResult` | dataclass | `…contracts.assertion` | `…api` | PUBLIC_STABLE | **yes** | fields + `is_supported` frozen |
| `AssertionGovernanceProvider` | protocol | `…contracts.assertion` | `…api` | PUBLIC_STABLE | no | identity re-export |
| `AssertionCoverage` | enum | `…contracts.assertion` | `…api` | PUBLIC_STABLE | **yes** | values frozen |
| `ExecutionDispatchRequest` | dataclass | `…contracts.execution` | `…api` | PUBLIC_STABLE | **yes** | fields/defaults frozen |
| `ExecutionDispatchResult` | dataclass | `…contracts.execution` | `…api` | PUBLIC_STABLE | **yes** | fields/defaults frozen |
| `ExecutionObservation` | dataclass | `…contracts.execution` | `…api` | PUBLIC_STABLE | **yes** | fields/defaults frozen |
| `ExternalExecutionProvider` | protocol | `…contracts.execution` | `…api` | PUBLIC_STABLE | no | identity re-export |
| `ExecutionBusinessOutcome` | enum | `…contracts.execution` | `…api` | PUBLIC_STABLE | **yes** | values frozen |
| `ProviderKind` | enum | `governance_providers.metadata` | `…api` | PUBLIC_STABLE | **yes** | values frozen |
| `ProviderCapabilities` | dataclass | `…metadata` | `…api` | PUBLIC_STABLE | **yes** | fields frozen |
| `ProviderCompatibility` | dataclass | `…metadata` | `…api` | PUBLIC_STABLE | **yes** | fields frozen |
| `ProviderDescriptor` | dataclass | `…metadata` | `…api` | PUBLIC_STABLE | **yes** | fields frozen |
| `ProviderHealth` | dataclass | `…metadata` | `…api` | PUBLIC_STABLE | **yes** | fields frozen |
| `ProviderLifecycleState` | enum | `governance_providers.lifecycle` | `…api` | PUBLIC_STABLE | **yes** | values frozen |
| `is_legal_transition` | function | `…lifecycle` | full namespace only | CAPABILITY_INTERNAL | no | not in curated api |
| `assert_transition` | function | `…lifecycle` | full namespace only | CAPABILITY_INTERNAL | no | not in curated api |
| `FailureClass` | enum | `governance_providers.errors` | `…api` | PUBLIC_STABLE | **yes** | values frozen |
| `ProviderError` (+8 subclasses) | exception | `…errors` | `…api` | PUBLIC_STABLE | **yes** | `failure_class` frozen |
| `CONTRACT_VERSION` | constant | `governance_providers` (`version`) | `…api` | PUBLIC_STABLE | no | value `"1.0.0"` frozen |

**Compatibility guarantee:** every legacy `governance_providers.*` contract import
resolves to the **same object** as its canonical counterpart (verified by
`tests/compatibility/test_legacy_compat.py`), so no public symbol disappears and
`governance_providers.api`'s frozen snapshot hash (`98dd0264…`) is unchanged.
