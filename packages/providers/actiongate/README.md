# ugence-actiongate-provider

**ActionGate** is an **action-governance provider**: given a proposed action and its
authority, policy, risk, evidence, and decision context, it evaluates whether the
action is **authorized, authorized-with-constraints, denied, or indeterminate**, and
returns a structured authorization result. ActionGate implements the neutral
`ActionGovernanceProvider` contract from the Ugence Governance Provider Framework and
participates in the **authorization** control plane only.

ActionGate owns **no dispatch and no execution authority**. It never dispatches,
executes, observes, reconciles, or compensates an action; it never calls an
enterprise tool or an external-execution port; and it is an independent **peer** of
TAP (neither imports the other).

## The most important invariant

> Authorization is **never** execution, and uncertainty or infrastructure failure is
> **never** promoted to *authorized*.

Unknown/unmapped native outcomes, malformed results, timeouts, unavailability,
configuration errors, and protocol mismatches all map to **INDETERMINATE** (or raise
a classified framework `ProviderError`, which the framework control-plane adapter
normalizes to `INDETERMINATE`) — never to `AUTHORIZED`. `DENIED` and `INDETERMINATE`
never dispatch. This is a release gate, enforced by
`tests/authority/test_outcome_safety.py`.

## Install

```bash
pip install ugence-actiongate-provider
# with the kernel-bound control-plane integration:
pip install "ugence-actiongate-provider[decision-authority]"
```

Core depends only on `ugence-governance-provider-framework`. The default in-process
provider path is minimal and network-free.

## Quickstart

```python
from ugence_governance_provider_framework.api import ActionGovernanceRequest
from ugence_actiongate_provider.configuration import build_actiongate_provider
from ugence_actiongate_provider.core import ActionGateEngine

provider = build_actiongate_provider(ActionGateEngine())
provider.initialize()
result = provider.authorize(ActionGovernanceRequest("read_report", actor="alice"))
print(result.outcome.value)  # AUTHORIZED
# ActionGate stops here — an authorization outcome is NOT a dispatch.
```

## CLI

```bash
python -m ugence_actiongate_provider version   # distribution + implementation identity
python -m ugence_actiongate_provider verify    # authorization-boundary invariants -> PASS/FAIL
python -m ugence_actiongate_provider demo       # offline: authorized / constrained / denied / indeterminate
```

## Compatibility

The legacy `actiongate_provider` namespace is preserved as a **logic-free
compatibility facade** that re-exports the identical objects from this package
(object identity preserved). The legacy `dgm-actiongate-provider` distribution is a
compatibility shell that depends on this wheel. See `MIGRATION.md`.

**Not production certified.** Packaging verification is not a production
certification; see `docs/KNOWN_LIMITATIONS.md`.
