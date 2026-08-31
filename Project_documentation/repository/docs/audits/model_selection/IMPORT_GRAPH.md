# Model Selection — Import Graph & Dependency Direction

Captured directly by grepping `import`/`from` statements at commit `66066e99`.

## 1. What the Model Selection code depends on (outbound)

| Package | External (non-stdlib, non-self) imports | Verdict |
|---|---|---|
| `execution_gate/` | **none** — Python stdlib + intra-package only | Cleanly isolated |
| `model_selection_experiment/` | **none** — stdlib + intra-package only | Cleanly isolated |
| `model_selection_pilot/` | **none** cross-package — stdlib `urllib`, lazy `import boto3` (only if Bedrock creds); no Anthropic/OpenAI SDK (raw `urllib`) | Isolated (provider adapters use stdlib transport) |
| `model_selection_reconciliation/` | `model_selection_experiment` (read-only: `.policy`, `.metrics`, `.simulator`, `.variants`) | Depends only on the experiment package |

No Model Selection package imports Governance Contracts, Governance Provider Framework, Decision
Authority, TAP, ActionGate, control plane, Hybrid LLM, applications, domains, or any concrete provider
SDK. The capability is **dependency-light and correctly at the bottom of the stack**.

## 2. What depends on Model Selection (inbound / consumers)

| Consumer | Imports | Nature |
|---|---|---|
| `control_plane/adapters.py` | `execution_gate.{gate,model,policy,registry,states}` | Orchestrator adapter — wraps eligibility + selection |
| `control_plane_shadow/adapters/execution_gate_adapter.py` | `execution_gate` | Shadow adapter (eligibility) |
| `control_plane_shadow/adapters/model_policy_adapter.py` | `model_selection_experiment.policy` (`route`) | Shadow adapter (selection); intersects with eligible set, emits `MODEL.SELECTED_MODEL_NOT_ELIGIBLE` rather than override |
| `execution_gate_shadow/{runner,records,metrics,adapters,dry_run}.py` | `execution_gate.{gate,model,states}` | Shadow prediction/observation harness (predict uses gate only; no feedback to prediction) |
| `governed_inference_pilot/adapters/execution_gate.py` | `execution_gate.gate` (frozen) | Read-only eligibility adapter |
| `governed_inference_pilot/adapters/model_policy.py` | (re-implements selection) | Second live selection implementation |

## 3. Dependency direction verdict

```
   [ applications / control_plane / control_plane_shadow / *_shadow / governed_inference_pilot ]
                              │  (import)
                              ▼
        [ execution_gate ]   ◄──(read-only)── [ model_selection_reconciliation ]
                              ▲
                              │  (independent copy — NOT imported)
        [ model_selection_experiment ]  ── consumed by control_plane_shadow
        [ model_selection_pilot ]       ── no consumers
```

- **Direction is correct.** Consumers (orchestration, shadow harnesses, pilots) depend on Model
  Selection; Model Selection depends on nothing above it. There is **no** upward coupling to
  applications, control plane, or runtime — no dependency inversion to unwind before migration.
- **No port abstraction is required for the migration** on dependency grounds: `execution_gate` is
  already a leaf. `ExecutableRegistry`/`ModelRecord` already act as the provider-metadata port
  (consumers supply `Candidate` metadata; the gate never calls a provider).
- **The one structural defect is horizontal, not vertical:** the capability is *duplicated* across
  `execution_gate`, `model_selection_experiment`, `model_selection_pilot`,
  `model_selection_reconciliation`, and `governed_inference_pilot/adapters` — four-to-five copies of the
  same two-stage logic that do **not** import one another (except reconciliation→experiment). See
  `DUPLICATION_MATRIX.md`.

## 4. Freeze/ownership note

`platform_freeze/version.py` `CORE_TREES` = `(decision_governance, governance_providers,
actiongate_provider, tap_provider)`. Model Selection is **not** a frozen core tree and holds **no**
platform public-API snapshot, so no dependency-direction rule in `platform_freeze` governs it today.
`execution_gate/frozen/replay_v1` is a self-contained replay freeze internal to the capability.
