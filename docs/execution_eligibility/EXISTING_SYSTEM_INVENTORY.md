# Existing System Inventory — Execution Eligibility Track

*Phase 1 deliverable. Classifies every existing model-selection component for reuse by the
new **Execution Eligibility and Model Selection Engine** (ExecutionGate + ModelPolicy).
The prior Model Selection Policy Engine experiments (V1 frozen/UNRESOLVED, V2
viability-blocked) are **read-only**; nothing below is modified.*

## Classification legend

- **REUSABLE-UNCHANGED** — can be imported/observed read-only as-is.
- **REUSABLE-WITH-ADAPTER** — the concept transfers; the new track wraps it behind a clean
  interface rather than importing the frozen code.
- **MISSING** — no existing component; the new track must build it.
- **FROZEN-READ-ONLY** — scientifically coupled to the frozen experiment; never modified.

## Inventory

| Existing component | Location | Role today | Classification | Notes for this track |
|---|---|---|---|---|
| Capability registry | `model_selection_pilot/registry.py`, `data/registry.json` | provider/model metadata + provenance | **FROZEN-READ-ONLY** (V2) / **REUSABLE-WITH-ADAPTER** (schema idea) | The new **Executable Registry** extends this idea with execution-status fields; it does not edit the frozen registry. |
| Provider adapters | `model_selection_pilot/provider.py` | Anthropic/OpenAI/Bedrock real + stub adapters | **REUSABLE-WITH-ADAPTER** | The new track defines a provider-neutral probe/inference adapter interface with deterministic mocks; real adapters wrap the same call surface. |
| Routing / policy engine | `model_selection_pilot/policy.py` (F1/F2/G), `arms.py` | eligibility (hard/technical) + utility selection | **FROZEN-READ-ONLY** | ModelPolicy in this track is the *downstream* selector; it consumes ExecutionGate output and reuses the utility idea without importing frozen code. |
| Hard quality gate | `policy.py` (min-quality gate) | eliminate models predicted below quality | **FROZEN-READ-ONLY** | The pipeline places the Hard Quality Gate *after* ExecutionGate; semantics unchanged. |
| Governance constraints | `policy.py` `hard_and_technical_filter` | approved providers, residency, modality | **REUSABLE-WITH-ADAPTER** | Re-expressed as ExecutionGate *critical* conditions (fail-closed). |
| Telemetry | `model_selection_pilot/telemetry.py` | regime-gated observed quality snapshots | **REUSABLE-WITH-ADAPTER** | ExecutionGate adds *operational* telemetry (reliability, observed latency, failure reason codes) distinct from quality telemetry. |
| Cost calculation | `model_selection_pilot/costguard.py`, `execute.py` | dry-run, cost per call, hard cap | **REUSABLE-WITH-ADAPTER** | Projected-cost check becomes an ExecutionGate condition; the spend cap is reused as a critical gate. |
| Retry / fallback logic | `model_selection_pilot/execute.py` (retry fields) | retry counting | **MISSING (as a policy)** | Baselines require explicit retry-only and fallback strategies — built new. |
| Provider health checks | — | none | **MISSING** | Built new (reliability/degradation signal + baseline). |
| Environment / reachability checks | ad-hoc probes in the V2 investigation logs | one-off proxy/billing probes | **MISSING (as a component)** | The real discoveries (proxy 403 denials, Gemini free-tier 429, model_not_found, invalid AWS/Google creds) become the **replay scenarios** — credentials/project IDs removed. |
| Quota / billing handling | ad-hoc in V2 probes | structured 429 parsing | **REUSABLE-WITH-ADAPTER** | Normalized into billing/quota reason codes (`FREE_TIER_ONLY`, `QUOTA_EXHAUSTED`, `BILLING_INACTIVE`). |
| Error classification | — | none (raw provider strings) | **MISSING** | Built new: a stable reason-code taxonomy distinct from raw provider errors. |
| Tests | `model_selection_pilot/tests/`, `model_selection_experiment/tests/` | 17 + 15 frozen behavior tests | **FROZEN-READ-ONLY** | New track ships its own test suite; frozen tests remain green and untouched. |
| Experiment artifacts | V1/V2 manifests, amendments, viability reports, execution-attempt reports | frozen record | **FROZEN-READ-ONLY** | Referenced as the evidentiary basis for replay scenarios only. |

## Reuse decisions (summary)

- **Do not import frozen implementation code.** The new `execution_gate/` package is
  self-contained and provider-neutral; where a frozen idea is reused (utility selection,
  cost cap, provenance), it is re-implemented behind a clean interface so the frozen
  experiment stays byte-stable.
- **Reuse the *evidence*, not the code.** The V1/V2 investigations produced authoritative
  real-world execution facts (which providers are proxy-reachable, which models execute,
  the exact billing/quota states). These are distilled into deterministic replay scenarios
  with all credentials and project identifiers removed.
- **Build the genuinely missing layer:** environment/reachability/credential/billing/quota
  discovery, a stable reason-code taxonomy, typed eligibility states, an executable
  registry with execution-verification lineage, and the ExecutionGate↔ModelPolicy contract.

## Real-world facts carried forward as replay evidence (credentials removed)

| Observed fact (from V2 investigation) | Normalized reason code |
|---|---|
| `api.mistral.ai`, `api.openai.com`, `dashscope*.aliyuncs.com`, `api.moonshot.*`, and other endpoints → proxy `403 CONNECT` | `NETWORK_BLOCKED` |
| `generativelanguage.googleapis.com`, `*.anthropic.com` → reachable | (reachable) |
| Anthropic `claude-3-5-haiku-20241022`, `claude-3-7-sonnet-20250219` → `model_not_found` | `MODEL_NOT_FOUND` |
| Anthropic `claude-haiku-4-5`, `claude-sonnet-4-5` → real inference OK | (execution-verified) |
| Google `gemma-4-31b-it`, `gemma-4-26b-a4b-it` → real inference OK | (execution-verified) |
| Google `gemini-2.0-flash*`, `gemini-2.5-pro` → `429 RESOURCE_EXHAUSTED`, free-tier quotas, billing inactive | `FREE_TIER_ONLY` / `QUOTA_EXHAUSTED` / `BILLING_INACTIVE` |
| Google `gemini-2.5-flash` → `404` | `MODEL_NOT_FOUND` |
| AWS credentials → `InvalidClientTokenId` | `AUTH_INVALID` |
| Google OAuth token → `invalid_token` | `AUTH_INVALID` |

These make the evaluation grounded in real multi-provider failure modes rather than only
synthetic ones.
