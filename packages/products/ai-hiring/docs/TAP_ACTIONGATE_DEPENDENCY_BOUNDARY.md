# TAP / ActionGate Dependency Boundary

TAP and ActionGate are governed **control-plane** capabilities that AI Hiring
*uses* but does not *own*. They are now independently packaged as the canonical
Ugence provider distributions **`ugence-tap-provider`** (namespace
`ugence_tap_provider`) and **`ugence-actiongate-provider`** (namespace
`ugence_actiongate_provider`). AI Hiring's optional extras and adapters target
those canonical packages. This normalization required **no product redesign**.

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

## Optional canonical adapters (isolated)

Concrete bridges to the canonical providers live **only** under
`ugence_ai_hiring/integrations/`:

| Module | Bridges | Neutral target |
|---|---|---|
| `integrations/tap_adapter.py` | `ugence_tap_provider.provider.TAPProvider` | `AssertionGovernanceProvider` → `ClaimAssertionEvaluator` |
| `integrations/actiongate_adapter.py` | `ugence_actiongate_provider.provider.ActionGateProvider` | `ActionGovernanceProvider` → `ActionAuthorizationIntegration` |

The old adapter module names remain as **compatibility import paths** — logic-free
facades that re-export the canonical adapter callables (object identity preserved):

| Compatibility path | Canonical module |
|---|---|
| `integrations/tap_legacy_adapter.py` | `integrations/tap_adapter.py` |
| `integrations/actiongate_legacy_adapter.py` | `integrations/actiongate_adapter.py` |

These adapters:

- import the canonical provider **lazily** (only when a loader/builder is called);
- are **not** imported by the core, so `import ugence_ai_hiring` never loads them;
- implement **no** adjudication/authorization logic — they only construct the
  injected provider and hand it to the core's neutral integration;
- fail closed with `ProviderUnavailable` (retained alias:
  `LegacyProviderUnavailable is ProviderUnavailable`) when the optional
  distribution is absent.

Install with the optional extras (user-facing extra names unchanged; they now
resolve the canonical distributions):

```bash
pip install "ugence-ai-hiring[tap]"          # -> ugence-tap-provider
pip install "ugence-ai-hiring[actiongate]"   # -> ugence-actiongate-provider
```

## Dependency classification

| Item | Classification |
|---|---|
| Neutral governance ports/protocols used by the core | NEUTRAL_CONTRACT |
| `tap` / `actiongate` extras | OPTIONAL_INTEGRATION |
| `ugence_tap_provider` / `ugence_actiongate_provider` inside `integrations/` (lazy) | OPTIONAL_CANONICAL_ADAPTER |
| `ugence_tap_provider` / `ugence_actiongate_provider` anywhere in the core | FORBIDDEN_CORE_DEPENDENCY (count 0) |
| Legacy `tap_provider` / `actiongate_provider` namespaces anywhere in the package | FORBIDDEN (count 0) — the core targets the canonical namespaces directly |
| Canonical providers exercised by compatibility tests when importable | TEST_ONLY |

`dgm-tap-provider` and `dgm-actiongate-provider` are **no longer AI Hiring
dependencies**. They remain valid **provider compatibility distributions** for old
deployments: installing them pulls in the canonical providers
(`ugence-tap-provider` / `ugence-actiongate-provider`) and keeps
`import tap_provider` / `import actiongate_provider` working — but AI Hiring itself
never declares them.

## Boundary is preserved

- AI Hiring core still depends only on neutral protocols (AST-verified).
- Importing `ugence_ai_hiring` (or the integration adapters) never eagerly loads a
  provider; core-only installation is fully functional.
- Missing optional providers fail explicitly and safely (`ProviderUnavailable`).
- `production_certified` remains `False`; TAP and ActionGate semantics, the
  advisory-AI / human-binding-decision boundary, and the
  authorization-vs-execution boundary are unchanged.

This normalization is a **dependency/import swap** inside the isolated adapters and
the optional extras — **no product redesign, no new hiring logic, no TAP rewrite,
no ActionGate rewrite, and no change to any governance semantic or control-plane
boundary.** It does not modify TAP or ActionGate implementation logic and does not
remove their compatibility distributions.
