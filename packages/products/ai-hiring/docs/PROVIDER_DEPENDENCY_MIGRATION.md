# Provider Dependency Migration — canonical TAP / ActionGate

This release (`ugence-ai-hiring` **0.1.0 → 0.1.1**) normalizes AI Hiring's optional
TAP and ActionGate dependencies onto the **canonical** Ugence provider
distributions. It is a **packaging / dependency-metadata change only** — no product
capability, public API, governance semantic, or behavior changed. The AI Hiring
**product version stays `0.6.x`** and `production_certified` stays `False`.

## What changed

The **user-facing extra names are unchanged**. Only what they resolve changed:

### Previous

```bash
pip install "ugence-ai-hiring[tap]"
# resolved dgm-tap-provider

pip install "ugence-ai-hiring[actiongate]"
# resolved dgm-actiongate-provider
```

### Current

```bash
pip install "ugence-ai-hiring[tap]"
# resolves ugence-tap-provider (>=0.1.0)

pip install "ugence-ai-hiring[actiongate]"
# resolves ugence-actiongate-provider (>=0.1.0)
```

`dgm-tap-provider` / `dgm-actiongate-provider` are **no longer AI Hiring
dependencies**.

## Canonical integration imports

New code should import the canonical adapter modules:

```python
from ugence_ai_hiring.integrations.tap_adapter import (
    load_tap_provider_cls,
    build_tap_provider,
    build_claim_assertion_evaluator,
)
from ugence_ai_hiring.integrations.actiongate_adapter import (
    load_actiongate_provider_cls,
    build_actiongate_provider,
    build_action_authorization_integration,
)
```

These load the canonical provider classes lazily:

```python
load_tap_provider_cls()          # -> ugence_tap_provider.provider.TAPProvider
load_actiongate_provider_cls()   # -> ugence_actiongate_provider.provider.ActionGateProvider
```

## Preserved compatibility imports

The previous adapter module names keep working unchanged — they are logic-free
facades that re-export the **same** callables (object identity preserved):

```python
from ugence_ai_hiring.integrations.tap_legacy_adapter import load_tap_provider_cls as legacy
from ugence_ai_hiring.integrations.tap_adapter import load_tap_provider_cls as canonical
assert legacy is canonical  # identical object
```

The unavailable-provider exception name is preserved as an identity-preserving
alias, so existing `except LegacyProviderUnavailable:` handlers keep working:

```python
from ugence_ai_hiring.integrations import ProviderUnavailable, LegacyProviderUnavailable
assert LegacyProviderUnavailable is ProviderUnavailable
```

## Existing deployments that still install the dgm-* wheels

No action required. Installing the compatibility distributions still works and
transparently pulls in the canonical providers:

```bash
pip install ugence-ai-hiring dgm-tap-provider dgm-actiongate-provider
# dgm-tap-provider       -> ugence-tap-provider[decision-authority]
# dgm-actiongate-provider -> ugence-actiongate-provider[decision-authority]
```

AI Hiring's canonical adapters load the canonical provider classes in this shape
too, and `import tap_provider` / `import actiongate_provider` keep resolving to the
identical canonical objects. This proves deployment compatibility — it is not
continued dependency ownership by AI Hiring.

## `version_info()` compatibility

`version_info().optional_integrations` keeps its historical keys `tap_legacy` /
`actiongate_legacy` for schema stability, but they now probe the **canonical**
namespaces (`ugence_tap_provider` / `ugence_actiongate_provider`). A later minor
release may normalize the public key names.
