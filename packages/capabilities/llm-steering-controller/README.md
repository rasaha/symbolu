# Ugence LLM Steering Controller

`ugence-llm-steering-controller` — the deterministic, provider-neutral, **advisory-only**
LLM *routing* layer of the Ugence platform.

Given a request's requirements and a metadata-only candidate registry, it:

1. **discovers** model/provider candidates,
2. applies **hard policy and capability constraints** (fail-closed, *before* scoring),
3. **scores** the eligible set on decomposable dimensions, and
4. returns a ranked, explainable **routing recommendation** — to a separately governed
   runtime.

```
REQUEST REQUIREMENTS
    → MODEL/PROVIDER CANDIDATE DISCOVERY
    → POLICY AND CONSTRAINT FILTERING       (hard, fail-closed, before scoring)
    → CANDIDATE SCORING                     (soft, decomposable)
    → ROUTING RECOMMENDATION                (rank + deterministic tie-break)
    → EXPLANATION AND EVIDENCE
```

## Authority boundary

```
authority_class:                        ADVISORY
execution_capability:                   NONE
provider_invocation_capability:         NONE
credential_access:                      NONE
routing_decision_is_authority:          false
live_provider_calls_enabled_by_default: false
```

This package **recommends** model/provider routing. It does **not** execute model
requests, load provider credentials, perform retries or fallbacks, open sockets, or
replace the Agent Runtime. It contains no Hybrid LLM model internals. Every
recommendation carries `execution_status = NOT_EXECUTED` and `recommendation_only = true`.

## Install / build

```bash
python -m build packages/capabilities/llm-steering-controller
python packages/capabilities/llm-steering-controller/verify_llm_steering_controller_distribution.py
```

The core has **no runtime dependencies** (Python standard library only). Provider SDKs are
never required — not for import, recommendation, simulation, CLI fixture execution, or
verification.

## Usage

```python
from ugence_llm_steering_controller import recommend

registry = {
    "providers": [
        {"provider_id": "openai", "regions": ["us", "eu"]},
        {"provider_id": "anthropic", "regions": ["us"]},
    ],
    "models": [
        {"model_id": "gpt-fast", "provider_id": "openai", "modalities_in": ["text"],
         "context_limit": 128000, "structured_output": True, "tool_use": True,
         "cost_class": "medium", "latency_class": "fast", "quality_tier": "advanced"},
        {"model_id": "claude-premium", "provider_id": "anthropic", "modalities_in": ["text", "image"],
         "context_limit": 200000, "structured_output": True, "tool_use": True,
         "cost_class": "high", "latency_class": "medium", "quality_tier": "frontier",
         "privacy_tier": "high"},
    ],
}

result = recommend(registry, {
    "task_category": "chat",
    "quality_preference": "quality_first",
    "requirements": {"estimated_input_tokens": 5000},
})

print(result.status)                          # RECOMMENDED
print(result.recommendation.recommended_model)  # claude-premium
print(result.recommendation.execution_status)   # NOT_EXECUTED
```

## CLI (offline, non-executing)

```bash
ugence-llm-steering inspect
ugence-llm-steering validate-registry --input registry.json
ugence-llm-steering recommend --fixture fixtures/scenario_multi_eligible.json
ugence-llm-steering explain   --fixture fixtures/scenario_multi_eligible.json
ugence-llm-steering simulate  --fixture fixtures/suite.json
ugence-llm-steering verify-package
```

Every routing subcommand prints, to stderr:

```
ROUTING RECOMMENDATION ONLY
NO PROVIDER REQUEST WAS EXECUTED
```

There is deliberately no live-invocation command.

## Relationship to sibling capabilities

- **`ugence-model-selection`** is the deterministic *selection leaf* (eligibility + policy
  scoring over an *already-approved* candidate set). This controller is the *routing* layer
  above it — candidate discovery, constraint filtering, ranking, and fallback / escalation
  *recommendations*. They are complementary; this package **does not depend on**
  model-selection.
- Provider **execution** (retries, fallback dispatch, credential use) belongs to a
  separately governed runtime and lives OUTSIDE this distribution.

See `docs/` for the full architecture, authority boundary, canonical-source decision,
routing-policy model, scoring/explanation, provider-execution boundary, simulation
evidence, compatibility/migration, and limitations.

## Claims discipline

This package establishes that routing recommendations are **deterministic under fixed
inputs and policy**, that **hard constraints are enforced before scoring**, that
recommendation evidence is **reproducible**, and that the package performs **no provider
execution** and **imports without side effects**. It makes **no** claim of best
model-selection quality, production routing performance, cost savings, latency reduction,
reliability, or production readiness.
