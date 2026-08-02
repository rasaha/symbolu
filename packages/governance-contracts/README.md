# ugence-governance-contracts

The canonical, neutral, reusable **governance contract layer** for Ugence — a
**leaf** package that capabilities and the provider framework depend on, so they
never have to depend on each other.

- **Distribution:** `ugence-governance-contracts`
- **Namespace:** `ugence_governance_contracts`
- **Version:** 0.1.0 · **Contract version:** 1.0.0
- **Dependencies:** Python standard library only (no third-party, no other Ugence package)
- **Typing:** fully type-annotated; ships a PEP 561 `py.typed` marker
- **Ownership / maturity:** extracted verbatim from the frozen `governance_providers`
  contract core; stable, synthetic-neutral, no semantic change.
- **Public API snapshot:** `public_api.json` (machine-readable; asserted equal to the
  installed package by `tests/packaging/test_public_api.py`).

## What's in it

The provider-neutral contracts that describe *what a governance provider is asked
and what it returns*, independent of any concrete implementation:

| Group | Symbols |
|---|---|
| Requests / results | `ActionGovernanceRequest/Result`, `AssertionGovernanceRequest/Result`, `ExecutionDispatchRequest/Result`, `ExecutionObservation` |
| Authority / effect | `ActionGovernanceOutcome`, `AssertionCoverage`, `ExecutionBusinessOutcome` |
| Provider protocols | `Provider`, `BaseProvider`, `ActionGovernanceProvider`, `AssertionGovernanceProvider`, `ExternalExecutionProvider` |
| Provider metadata | `ProviderKind`, `ProviderDescriptor`, `ProviderCapabilities`, `ProviderCompatibility`, `ProviderHealth` |
| Lifecycle | `ProviderLifecycleState` |
| Errors | `FailureClass`, `ProviderError` (+8 subclasses) |

## Authority boundary

These are neutral **contracts**, not authority. The meaning of each result
(advisory vs binding, authorization vs clearance vs execution) is owned by the
capability that produces it. This package changes **no** authority boundary:
assertion governance stays advisory, action governance authorizes, execution stays
separate, and no result becomes "more binding" by living here.

## Install & use

```bash
python -m build packages/governance-contracts
pip install dist/ugence_governance_contracts-0.1.0-py3-none-any.whl   # no index needed
```

```python
from ugence_governance_contracts.api import (
    ActionGovernanceRequest, ActionGovernanceOutcome, ProviderKind)

req = ActionGovernanceRequest(action_type="deploy", actor="agent://x")
```

Independent-distribution proof:

```bash
python packages/governance-contracts/verify_governance_contracts_distribution.py
```

## Compatibility paths

The neutral contracts previously lived in `governance_providers`. Those paths still
resolve to the **same objects** (identity preserved), now through a two-hop
compatibility bridge: the `governance_providers` namespace aliases the Governance
Provider Framework's submodules, and the framework's `errors`/`lifecycle`/
`metadata`/`contracts.*` modules re-export from this package. Verified by
`tests/compatibility/test_legacy_compat.py` importing the real legacy paths and
asserting object identity:

| Legacy (compatibility period) | Canonical |
|---|---|
| `from governance_providers.api import ActionGovernanceRequest` | `from ugence_governance_contracts.api import ActionGovernanceRequest` |
| `from governance_providers.contracts import Provider` | `from ugence_governance_contracts.contracts import Provider` |
| `from governance_providers.errors import FailureClass` | `from ugence_governance_contracts.errors import FailureClass` |
| `from governance_providers.metadata import ProviderKind` | `from ugence_governance_contracts.metadata import ProviderKind` |

Removal/review target: `governance_providers` 0.2.0. See `MIGRATION.md`.

## Known limitations / deferred

This phase is a **physical** extraction only. Known platform-contract gaps
(missing `tenant_id`/`environment_id`, no standard error *envelope*, no
idempotency/expiry *contract*, fragmented CER/audit shapes) are **documented, not
implemented** — see
`docs/migrations/governance_contracts/CONTRACT_GAPS_AND_EVOLUTION_PLAN.md`. A
versioned contract-evolution phase owns those.
