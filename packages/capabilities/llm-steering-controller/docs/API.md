# Public API

Import everything from the package root (`ugence_llm_steering_controller`). The machine-readable
inventory is `artifacts/llm_steering/steering_public_api_inventory.json`.

## Entry points

```python
from ugence_llm_steering_controller import recommend, build_controller, LLMSteeringController

# One-shot from raw dicts:
result = recommend(registry_dict, request_dict, policy_dict_or_None)  # -> SteeringResult

# Reusable controller:
ctrl = build_controller(registry_dict)          # -> LLMSteeringController
result = ctrl.recommend(SteeringRequest(...))   # -> SteeringResult
rec = ctrl.recommend_or_raise(SteeringRequest(...))  # -> RoutingRecommendation, raises NoEligibleCandidate
```

## Contracts

- **Inputs:** `SteeringRequest`, `TaskRequirements`, `CandidateRegistry`, `ModelCandidate`,
  `ProviderCandidate`, `RoutingPolicy`, `QualityPreference`, `PrivacyClass`, `DeprecationState`.
- **Outputs:** `SteeringResult`, `RoutingRecommendation`, `CandidateScore`, `RoutingConstraint`,
  `FallbackRecommendation`, `RoutingExplanation`, `RoutingEvidence`, `RoutingDecisionTrace`,
  `SteeringStatus`, `ExecutionStatus`.
- **Errors:** `SteeringError` (base), `ContractError`, `RegistryError`, `PolicyViolation`,
  `NoEligibleCandidate`.
- **Helpers:** `validate_registry`, `__version__`, `VERSION`, `POLICY_VERSION`, `SCHEMA_VERSION`.

Every contract has `to_dict()` and (for inputs) `from_dict()` for deterministic JSON round-tripping.

## Result shape (abridged)

```json
{
  "status": "RECOMMENDED",
  "policy_version": "steering-policy-1.0",
  "decision_id": "dec-…",
  "recommendation": {
    "recommended_model": "…", "recommended_provider": "…",
    "ranked_alternatives": ["…"],
    "score": {"total": 0.83, "components": {"…": 0.9}, "weighted": {"…": 0.9}},
    "constraints_satisfied": ["…"], "constraints_rejected": [],
    "confidence": 0.66, "confidence_basis": "…",
    "fallback": {"permitted": true, "ordered_candidates": ["…"], "escalation_recommended": false},
    "explanation": {"summary": "…", "reasons": ["…"], "tie_break_rule": "…"},
    "evidence": {"registry_fingerprint": "reg-…", "eligible_count": 3, "rejected": [], "scores": []},
    "execution_status": "NOT_EXECUTED", "recommendation_only": true
  }
}
```
