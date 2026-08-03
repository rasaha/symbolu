# TAP / ActionGate Dependency Boundary

TAP and ActionGate are governed **control-plane** capabilities that AI Hiring
*uses* but does not *own*. They will be independently packaged in later phases.
This package is designed so that migration requires **no product redesign**.

## What the core does (and does not) do

The AI Hiring **core** interacts with the control plane **only** through neutral
governance ports/protocols:

- action authorization → `ActionGovernanceProvider` (from
  `ugence_governance_provider_framework.api`);
- claim/assertion evaluation → `AssertionGovernanceProvider`;
- control-plane / external execution → the kernel's `ActionControlPlanePort` /
  `ExternalExecutionPort`.

The concrete provider is always **dependency-injected**. The core:

- **may** construct a governed action request, call a neutral authorization port,
  and record the authorization outcome;
- **must not** implement TAP adjudication, implement ActionGate authorization
  logic, or execute an authorized enterprise action.

The default `build_in_memory_platform()` wires the framework's **deterministic,
offline** reference providers, so the core is fully verifiable with **no**
concrete TAP or ActionGate provider installed. Authorization preparation is a
separate record and service from execution.

## Optional legacy adapters (isolated)

Concrete bridges to the current providers live **only** under
`ugence_ai_hiring/integrations/`:

| Module | Bridges | Neutral target |
|---|---|---|
| `integrations/tap_legacy_adapter.py` | `tap_provider.TAPProvider` | `AssertionGovernanceProvider` → `ClaimAssertionEvaluator` |
| `integrations/actiongate_legacy_adapter.py` | `actiongate_provider.ActionGateProvider` | `ActionGovernanceProvider` → `ActionAuthorizationIntegration` |

These adapters:

- import the legacy provider **lazily** (only when a loader/builder is called);
- are **not** imported by the core, so `import ugence_ai_hiring` never loads them;
- implement **no** adjudication/authorization logic — they only construct the
  injected legacy provider and hand it to the core's neutral integration;
- fail closed with `LegacyProviderUnavailable` when the optional distribution is
  absent.

Install with the optional extras (temporary legacy-compatibility dependencies):

```bash
pip install "ugence-ai-hiring[tap]"          # -> dgm-tap-provider
pip install "ugence-ai-hiring[actiongate]"   # -> dgm-actiongate-provider
```

## Dependency classification

| Item | Classification |
|---|---|
| Neutral governance ports/protocols used by the core | NEUTRAL_CONTRACT |
| `tap` / `actiongate` extras | OPTIONAL_INTEGRATION |
| `tap_provider` / `actiongate_provider` inside `integrations/` (lazy) | LEGACY_COMPATIBILITY_DEPENDENCY |
| `tap_provider` / `actiongate_provider` anywhere in the core | FORBIDDEN_CORE_DEPENDENCY (count 0) |
| Legacy providers exercised by compatibility tests when importable | TEST_ONLY |

`dgm-tap-provider` and `dgm-actiongate-provider` are recorded as **temporary
legacy-compatibility dependencies**, not canonical ownership.

## Follow-up migration (later, bounded, dependency-only PR)

After the canonical Ugence packages are created (in their own phases), a bounded,
**dependency-only, compatibility-preserving** follow-up PR will migrate:

```
dgm-tap-provider        -> ugence-tap-provider
tap_provider            -> ugence_tap_provider
dgm-actiongate-provider -> ugence-actiongate-provider
actiongate_provider     -> ugence_actiongate_provider
```

Because the core depends only on neutral protocols and the concrete providers are
confined to the isolated `integrations/` adapters (and the `tap` / `actiongate`
extras), that migration is a dependency/import swap inside those adapters and the
extras — **no product redesign, no new hiring logic, and no change to the
advisory-AI / human-binding-decision or authorization-vs-execution boundaries.**
This PR does **not** rename or redesign TAP or ActionGate and does **not** create
their canonical packages.
