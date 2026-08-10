# ActionGate Dependency Graph

AST import analysis over all non-test ActionGate source modules (143 import edges).
Full data: `actiongate_dependency_graph.json`.

## Edge classification

| Class | Edges | Meaning |
|---|---|---|
| `ACTIONGATE_INTERNAL` | 74 | package-relative imports within ActionGate |
| `STDLIB` | 43 | `__future__`, `dataclasses`, `enum`, `typing`, `hashlib`, `json`, `datetime` |
| `UGENCE_GOVERNANCE_FRAMEWORK` | 26 | `governance_providers.api` (legacy shim → canonical `ugence_governance_provider_framework`) |

## Key findings

- **Zero** imports of `decision_governance` / `ugence_decision_authority`,
  `tap_provider` / `ugence_tap_provider`, `ai_hiring`, `domains`, `applications`,
  `symbolu`, `agentic`, `cloud_controller`, `hybrid_llm_vnext_lab`, or any
  application code. **Zero forbidden imports.**
- The ActionGate **core** (`core.py`) imports only STDLIB — neither the framework nor
  the kernel, as required.
- The **provider/adapter layer** imports the neutral framework via
  `governance_providers.api` only. In the canonical package these 26 edges are
  rewritten to `ugence_governance_provider_framework.api`.

## Minimum canonical dependency set

| Dependency | Verdict |
|---|---|
| `ugence-governance-provider-framework` | **CORE_HARD_DEPENDENCY** — the only hard dependency (the neutral `.api` ActionGate consumes) |
| `ugence-decision-authority` | **OPTIONAL_INTEGRATION_EXTRA** (`decision-authority`) — ActionGate never imports it directly; the kernel is reached only through the framework's action control-plane adapter, so it is opt-in via `ugence-governance-provider-framework[adapters]` |
| `ugence-governance-contracts` | **TRANSITIVE_ONLY** — pulled by the framework; not imported directly |
| `decision-governance==1.0.0` (old private dep) | **REMOVE_LEGACY_DEPENDENCY** — not imported by ActionGate; dropped |
| `dgm-provider-framework==0.1.0` (old private dep) | **REPLACED** by `ugence-governance-provider-framework` |
| `ugence-tap-provider` | **FORBIDDEN** (peer independence) |
| `ugence-ai-hiring` | **FORBIDDEN** |

Remote mode uses the in-process client abstraction and adds **no** third-party HTTP
dependency, so there is no `remote` extra with third-party requirements.
