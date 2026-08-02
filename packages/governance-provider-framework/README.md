# ugence-governance-provider-framework

The canonical, capability-neutral **Governance Provider Framework** for Ugence —
the mechanism for registering, resolving, invoking, observing, and testing
governance providers. It **owns no governance authority**.

- **Distribution:** `ugence-governance-provider-framework`
- **Namespace:** `ugence_governance_provider_framework`
- **Version:** 0.1.0 · **Contract version:** 1.0.0
- **Hard dependency:** `ugence-governance-contracts` (neutral contract leaf) + stdlib
- **Optional dependency:** `decision-governance==1.0.0` (extra `adapters`) — the
  kernel-bound adapters and the `.api` aggregator; the core works without it
- **Legacy compatibility:** namespace `governance_providers`, distribution `dgm-provider-framework`

## Authority boundary

> The Governance Provider Framework provides capability-neutral provider
> mechanics. It does not own assertion admissibility, binding-decision authority,
> exact-action authorization, operational clearance, sequence-risk judgment,
> workflow execution, or product composition.

It is not a universal router, adjudicator, policy engine, orchestrator, execution
authority, capability authority, product-composition layer, or AI Control Plane.
Coordination transfers no authority.

> Concrete providers remain separate packages and retain only the authority
> delegated by their bounded capability.

TAP (assertion evidence and admissibility), ActionGate (exact-action
authorization), and the baselines remain **separate packages** with their own
wheels; the framework never instantiates or selects a concrete provider except
through neutral registration.

## What's in it

| Group | Symbols / modules |
|---|---|
| Public API | `ugence_governance_provider_framework.api` (48 symbols; identical to the frozen `governance_providers.api`) |
| Registration & discovery | `registry.ProviderRegistry` |
| Deterministic resolution | `resolution.{resolve, ResolutionRequest, ResolutionRecord, SelectionRule}` |
| Declarative configuration | `configuration.{ProvidersConfiguration, ProviderEntry}` |
| Observability | `observability.{ProviderInvocationLog, ProviderInvocationRecord, record_invocation}` |
| Fingerprinting | `fingerprint.fingerprint` (deterministic SHA-256 over canonical JSON) |
| Versioning & compatibility | `version.{__version__, CONTRACT_VERSION, TARGET_KERNEL_MAJOR, is_contract_compatible, is_kernel_compatible}` |
| Conformance kits (public) | `conformance.{common, assertion, action, execution}` |
| Reference providers (framework validation only) | `reference.{DeterministicAssertionProvider, DeterministicActionGovernanceProvider, DeterministicExecutionProvider}` |
| Kernel-bound adapters (optional) | `adapters.{ActionGovernanceControlPlaneAdapter, ExternalExecutionAdapter, AssertionAssessmentIntegration, AssertionAssessment, AssertionLinkedRecordAdapter}` |
| Neutral contracts (re-exported) | `contracts/*`, `metadata`, `lifecycle`, `errors` → `ugence_governance_contracts` (single-sourced, not duplicated) |

## Installation

```bash
pip install ugence-governance-provider-framework            # framework (core + importable adapters)
pip install ugence-governance-provider-framework[adapters]  # + Decision Authority kernel (to invoke adapters)
```

The framework — including the canonical public API **and** the kernel-bound adapter
symbols — imports without Decision Authority installed:

```python
import ugence_governance_provider_framework                 # ok, no kernel
import ugence_governance_provider_framework.api             # ok, no kernel
from ugence_governance_provider_framework.api import (
    ProviderRegistry, resolve, ProviderDescriptor,
    ActionGovernanceControlPlaneAdapter,                    # importable without the kernel
)
```

Decision Authority is an **optional** dependency: only *invoking* a kernel-bound
adapter needs it. Without the `adapters` extra installed, invoking one raises a
precise, actionable error:

```python
adapter = ActionGovernanceControlPlaneAdapter(provider)
adapter.authorize(action_request, cer)
# ModuleNotFoundError: ... requires the optional Decision Authority dependency ...
#   pip install "ugence-governance-provider-framework[adapters]"
```

Installing the `adapters` extra restores full, byte-for-byte adapter behavior.

## Usage sketch

```python
from ugence_governance_provider_framework.registry import ProviderRegistry
from ugence_governance_provider_framework.reference import DeterministicAssertionProvider
from ugence_governance_provider_framework.resolution import resolve, ResolutionRequest
from ugence_governance_provider_framework.metadata import ProviderKind

reg = ProviderRegistry()
reg.register(DeterministicAssertionProvider().descriptor())
provider, record = resolve(reg, ResolutionRequest(kind=ProviderKind.ASSERTION_GOVERNANCE))
```

## Compatibility

The legacy `governance_providers` namespace remains available and behaves
identically (same objects, same serialization, same errors). See `MIGRATION.md`.
