"""Hard-constraint evaluation (the deterministic policy boundary).

Every constraint here is applied BEFORE any scoring. A candidate that fails any hard
constraint is disqualified and can never be restored by a high score (see
``ROUTING_POLICY_MODEL.md``). Rules are fail-closed: missing or unknown capability
metadata is treated as *unsupported*, and privacy / data-residency rules reject rather
than admit on uncertainty.

Evaluation order is fixed and documented:

    1. prohibited provider            (request policy — hard)
    2. provider not in approved set   (request policy — hard)
    3. prohibited model               (request policy — hard)
    4. model not in approved set      (request policy — hard)
    5. deprecation / retirement       (verified provider fact)
    6. required input modalities      (verified provider fact)
    7. structured-output requirement  (verified provider fact)
    8. tool-use requirement           (verified provider fact)
    9. required capabilities          (verified provider fact)
   10. context window                 (verified provider fact)
   11. privacy tier (fail-closed)     (request policy — hard)
   12. data residency (fail-closed)   (request policy — hard)
   13. cost ceiling                   (request budget — hard, when configured)
   14. latency ceiling                (request budget — hard, when configured)
"""

from __future__ import annotations

from typing import List, Tuple

from .contracts import (
    DeprecationState,
    ModelCandidate,
    PrivacyClass,
    ProviderCandidate,
    RoutingConstraint,
    SteeringRequest,
)
from .estimate import estimate_cost, estimate_latency_ms

_POLICY_HARD = "policy-hard"
_VERIFIED_FACT = "verified-provider-fact"
_REQUEST_BUDGET = "request-budget"

# Privacy classes that require fail-closed high-assurance handling.
_SENSITIVE_PRIVACY = (PrivacyClass.CONFIDENTIAL, PrivacyClass.RESTRICTED)


def evaluate_candidate(
    model: ModelCandidate,
    provider: ProviderCandidate,
    request: SteeringRequest,
) -> Tuple[bool, List[RoutingConstraint]]:
    """Evaluate all hard constraints for one candidate.

    Returns ``(eligible, constraints)`` where ``constraints`` records the outcome of
    every rule evaluated, in fixed order. ``eligible`` is True only if *every* recorded
    constraint is satisfied.
    """
    req = request
    reqs = request.requirements
    out: List[RoutingConstraint] = []

    def record(name: str, satisfied: bool, provenance: str, detail: str = "") -> None:
        out.append(RoutingConstraint(name=name, satisfied=satisfied,
                                     provenance=provenance, detail=detail))

    # 1. prohibited provider
    record("provider_not_prohibited", provider.provider_id not in req.prohibited_providers,
           _POLICY_HARD, f"provider={provider.provider_id}")
    # 2. provider approved (only enforced if an approved set was supplied)
    if req.approved_providers:
        record("provider_approved", provider.provider_id in req.approved_providers,
               _POLICY_HARD, "approved_providers set")
    # 3. prohibited model
    record("model_not_prohibited", model.model_id not in req.prohibited_models,
           _POLICY_HARD, f"model={model.model_id}")
    # 4. model approved
    if req.approved_models:
        record("model_approved", model.model_id in req.approved_models,
               _POLICY_HARD, "approved_models set")
    # 5. deprecation / retirement — a deprecated or retired candidate is disqualified
    record("not_deprecated", model.deprecation_state == DeprecationState.ACTIVE.value,
           _VERIFIED_FACT, f"deprecation_state={model.deprecation_state}")
    # 6. required input modalities (unknown metadata => unsupported)
    if reqs.required_modalities:
        missing = [m for m in reqs.required_modalities if m not in model.modalities_in]
        record("modalities_supported", not missing, _VERIFIED_FACT,
               f"missing={missing}" if missing else "all required modalities present")
    # 7. structured output
    if reqs.structured_output_required:
        record("structured_output_supported", bool(model.structured_output), _VERIFIED_FACT,
               "structured output required")
    # 8. tool use
    if reqs.tool_use_required:
        record("tool_use_supported", bool(model.tool_use), _VERIFIED_FACT, "tool use required")
    # 9. required capabilities (unknown metadata => unsupported)
    if reqs.required_capabilities:
        missing_caps = [c for c in reqs.required_capabilities if c not in model.capabilities]
        record("capabilities_supported", not missing_caps, _VERIFIED_FACT,
               f"missing={missing_caps}" if missing_caps else "all required capabilities present")
    # 10. context window — need enough declared context for the request
    needed_ctx = max(reqs.min_context_window, reqs.estimated_input_tokens)
    if needed_ctx > 0:
        record("context_window_sufficient", model.context_limit >= needed_ctx, _VERIFIED_FACT,
               f"needed={needed_ctx} limit={model.context_limit}")
    # 11. privacy tier — fail-closed for sensitive requests
    if req.privacy_classification in _SENSITIVE_PRIVACY:
        privacy_ok = (model.privacy_tier == "high") and (not provider.trains_on_data)
        record("privacy_tier_sufficient", privacy_ok, _POLICY_HARD,
               f"classification={req.privacy_classification.value} "
               f"tier={model.privacy_tier} trains_on_data={provider.trains_on_data}")
    # 12. data residency — fail-closed: candidate must serve an allowed region
    if req.data_residency:
        available = set(model.regions) | set(provider.regions)
        residency_ok = bool(available & set(req.data_residency))
        record("data_residency_satisfied", residency_ok, _POLICY_HARD,
               f"allowed={sorted(req.data_residency)} available={sorted(available)}")
    # 13. cost ceiling (hard when configured)
    if req.cost_budget is not None:
        est_cost = estimate_cost(model, reqs.estimated_input_tokens)
        record("cost_within_budget", est_cost <= req.cost_budget, _REQUEST_BUDGET,
               f"est_cost={est_cost:.6f} budget={req.cost_budget}")
    # 14. latency ceiling (hard when configured)
    if req.latency_budget_ms is not None:
        est_lat = estimate_latency_ms(model, reqs.estimated_input_tokens)
        record("latency_within_budget", est_lat <= req.latency_budget_ms, _REQUEST_BUDGET,
               f"est_latency_ms={est_lat:.1f} budget={req.latency_budget_ms}")

    eligible = all(c.satisfied for c in out)
    return eligible, out


__all__ = ["evaluate_candidate"]
