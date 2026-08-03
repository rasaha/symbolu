# ugence-tap-provider

**TAP** is an **assertion-governance provider**: given a material assertion and
supplied evidence references, it evaluates whether the assertion is **supported,
unsupported, constrained, or indeterminate**, and returns a structured,
component-level result. TAP implements the neutral
`AssertionGovernanceProvider` contract from the Ugence Governance Provider
Framework and integrates into the **assessment / recommendation** workflow only.

TAP owns **no authorization and no execution authority**. It never authorizes,
dispatches, executes, reconciles, or compensates an action; it never touches an
action control-plane or external-execution port; and it is an independent **peer**
of ActionGate (neither imports the other).

## The most important invariant

> Uncertainty or infrastructure failure is **never** promoted to *supported*.

Unknown/malformed outcomes, missing evidence, timeouts, unavailability, protocol
mismatches, and result-validation failures all map to **INDETERMINATE** (or, with
`fail_safe=False`, raise a classified framework `ProviderError`) — never to
`SUPPORTED`. This is a release gate, enforced by
`tests/authority/test_outcome_safety.py`.

## Install

```bash
pip install ugence-tap-provider
# with the kernel-bound assessment integration:
pip install "ugence-tap-provider[decision-authority]"
```

Core depends only on `ugence-governance-provider-framework`. The default
in-process provider path is minimal and network-free.

## Quickstart

```python
from ugence_governance_provider_framework.api import AssertionGovernanceRequest
from ugence_tap_provider.configuration import build_tap_provider
from ugence_tap_provider.core import TapEngine

provider = build_tap_provider(TapEngine())
provider.initialize()
result = provider.evaluate(
    AssertionGovernanceRequest("Team shipped the feature", evidence_refs=("e1",)))
print(result.coverage.value, result.evidence_coverage)  # SUPPORTED 1.0
```

## CLI

```bash
python -m ugence_tap_provider version   # distribution + implementation identity
python -m ugence_tap_provider verify    # safety/governance invariants -> PASS/FAIL
python -m ugence_tap_provider demo       # offline: supported / constrained / indeterminate
```

## Compatibility

The legacy `tap_provider` namespace is preserved as a **logic-free compatibility
facade** that re-exports the identical objects from this package (object identity
preserved). The legacy `dgm-tap-provider` distribution is a compatibility shell
that depends on this wheel. See `MIGRATION.md`.

**Not production certified.** Packaging verification is not a production
certification; see `docs/KNOWN_LIMITATIONS.md`.
