"""The advisory LLM Steering Controller (deterministic routing recommendation core).

Conceptual flow (see ``ARCHITECTURE.md``)::

    REQUEST REQUIREMENTS
        -> MODEL/PROVIDER CANDIDATE DISCOVERY
        -> POLICY AND CONSTRAINT FILTERING       (hard, fail-closed, before scoring)
        -> CANDIDATE SCORING                      (soft, decomposable)
        -> ROUTING RECOMMENDATION                 (rank + tie-break)
        -> EXPLANATION AND EVIDENCE

The controller returns a :class:`SteeringResult` to a *separately governed runtime*. It
never executes a model request, loads a credential, retries, performs a fallback, or
opens a socket. ``execution_status`` is always ``NOT_EXECUTED``.
"""

from __future__ import annotations

from typing import Dict, List, Tuple

from . import evidence as ev
from .candidates import discover
from .constraints import evaluate_candidate
from .contracts import (
    CandidateScore,
    FallbackRecommendation,
    NoEligibleCandidate,
    RoutingRecommendation,
    SteeringRequest,
    SteeringResult,
    SteeringStatus,
)
from .explanation import build_explanation, no_candidate_reasons
from .policy import ROUND, RoutingPolicy
from .registry import CandidateRegistry
from .scoring import confidence_from_scores, score_eligible
from .version import POLICY_VERSION


class LLMSteeringController:
    """Deterministic, advisory routing-recommendation engine over a candidate registry."""

    def __init__(self, registry: CandidateRegistry):
        if not isinstance(registry, CandidateRegistry):
            raise TypeError("registry must be a CandidateRegistry")
        self._registry = registry

    # -- public API --------------------------------------------------------------------
    def recommend(self, request: SteeringRequest, policy: RoutingPolicy = None) -> SteeringResult:
        """Produce a routing recommendation (or a typed no-eligible-candidate outcome)."""
        policy = self._resolve_policy(request, policy)
        policy_version = policy.policy_version

        # 1. discover
        pairs = discover(self._registry, request)
        considered = len(pairs)

        # 2. hard constraint filtering (fail-closed, before scoring)
        eligible: List[Tuple] = []
        rejected_records: List[Dict] = []
        rejected_order: List[str] = []
        eligible_order: List[str] = []
        for model, provider in pairs:
            ok, constraints = evaluate_candidate(model, provider, request)
            if ok:
                eligible.append((model, provider))
                eligible_order.append(model.model_id)
            else:
                rejected_order.append(model.model_id)
                rejected_records.append({
                    "model_id": model.model_id,
                    "provider_id": model.provider_id,
                    "constraints": [c.to_dict() for c in constraints],
                    "failed": [c.name for c in constraints if not c.satisfied],
                })

        # 3/5. no eligible candidate -> typed outcome (never an arbitrary fallback)
        if not eligible:
            evidence = ev.build_evidence(self._registry, request, policy, considered,
                                         rejected_records, [])
            trace = ev.build_trace((), tuple(rejected_order), had_recommendation=False)
            reasons = no_candidate_reasons(evidence.rejected)
            decision = ev.decision_id(evidence.registry_fingerprint,
                                      evidence.request_fingerprint,
                                      evidence.policy_fingerprint, ())
            return SteeringResult(
                status=SteeringStatus.NO_ELIGIBLE_CANDIDATE.value,
                policy_version=policy_version,
                decision_id=decision,
                recommendation=None,
                evidence=evidence,
                trace=trace,
                reason="; ".join(reasons),
            )

        # 4. score eligible only
        scores = score_eligible(eligible, request, policy)

        # 6. rank + deterministic tie-break: (total desc, model_id asc, provider_id asc)
        ranked = sorted(scores, key=lambda s: (-s.total, s.model_id, s.provider_id))
        ranked_ids = tuple(s.model_id for s in ranked)
        top = ranked[0]

        confidence, conf_basis = confidence_from_scores(ranked)

        # constraint roll-up for the recommended candidate
        rec_constraints = self._constraints_for(top.model_id, request)
        satisfied = tuple(c.name for c in rec_constraints if c.satisfied)
        rejected_names = tuple(c.name for c in rec_constraints if not c.satisfied)  # empty for winner

        # fallback / escalation recommendation (advisory only)
        fallback = self._build_fallback(request, ranked, confidence)

        evidence = ev.build_evidence(self._registry, request, policy, considered,
                                     rejected_records, ranked)
        trace = ev.build_trace(tuple(eligible_order), tuple(rejected_order),
                               had_recommendation=True)
        decision = ev.decision_id(evidence.registry_fingerprint, evidence.request_fingerprint,
                                  evidence.policy_fingerprint, ranked_ids)
        explanation = build_explanation(request, policy, top, ranked,
                                        rejected_count=len(rejected_records), considered=considered)

        recommendation = RoutingRecommendation(
            decision_id=decision,
            recommended_model=top.model_id,
            recommended_provider=top.provider_id,
            ranked_alternatives=ranked_ids[1:],
            score=top,
            ranked_scores=tuple(s.to_dict() for s in ranked),
            constraints_evaluated=tuple(c.to_dict() for c in rec_constraints),
            constraints_satisfied=satisfied,
            constraints_rejected=rejected_names,
            policy_version=policy_version,
            confidence=confidence,
            confidence_basis=conf_basis,
            explanation=explanation,
            fallback=fallback,
            evidence=evidence,
            trace=trace,
        )
        return SteeringResult(
            status=SteeringStatus.RECOMMENDED.value,
            policy_version=policy_version,
            decision_id=decision,
            recommendation=recommendation,
            evidence=evidence,
            trace=trace,
            reason="recommendation produced",
        )

    def recommend_or_raise(self, request: SteeringRequest,
                           policy: RoutingPolicy = None) -> RoutingRecommendation:
        """Strict variant: raise :class:`NoEligibleCandidate` instead of returning a
        typed no-candidate outcome."""
        result = self.recommend(request, policy)
        if not result.is_recommended or result.recommendation is None:
            raise NoEligibleCandidate(result.reason or "no eligible candidate")
        return result.recommendation

    # -- helpers -----------------------------------------------------------------------
    def _resolve_policy(self, request: SteeringRequest, policy: RoutingPolicy) -> RoutingPolicy:
        pv = request.policy_version or POLICY_VERSION
        if policy is None:
            return RoutingPolicy(preference=request.quality_preference, policy_version=pv)
        # Bind the resolved policy_version so it appears in fingerprints/output.
        return RoutingPolicy(preference=policy.preference,
                             weight_overrides=dict(policy.weight_overrides or {}),
                             policy_version=policy.policy_version or pv)

    def _constraints_for(self, model_id: str, request: SteeringRequest):
        model = self._registry.model(model_id)
        provider = self._registry.provider(model.provider_id)
        _, constraints = evaluate_candidate(model, provider, request)
        return constraints

    def _build_fallback(self, request: SteeringRequest, ranked: List[CandidateScore],
                        confidence: float) -> FallbackRecommendation:
        permitted = request.fallback_permitted
        ordered = tuple(s.model_id for s in ranked[1:]) if permitted else ()
        conditions: Tuple[str, ...] = ()
        if permitted and ordered:
            conditions = (
                "Recommended model returns a hard error or times out at the runtime.",
                "Recommended provider reports unavailable at execution time.",
                "Try fallback candidates in the listed order; do not exceed policy budgets.",
            )
        elif permitted and not ordered:
            conditions = ("Only one eligible candidate; no in-policy fallback available.",)

        # Escalation is recommended (not executed) when the choice is weak or forbidden-to-fallback.
        escalation_recommended = False
        escalation_conditions: List[str] = []
        if request.escalation_permitted:
            if len(ranked) == 1 and not permitted:
                escalation_recommended = True
                escalation_conditions.append(
                    "Single eligible candidate and fallback prohibited: escalate on failure.")
            if confidence < 0.6:
                escalation_recommended = True
                escalation_conditions.append(
                    f"Low routing confidence ({round(confidence, ROUND)}): recommend human / "
                    "governance review before committing.")
        return FallbackRecommendation(
            permitted=permitted,
            ordered_candidates=ordered,
            conditions=conditions,
            escalation_recommended=escalation_recommended,
            escalation_conditions=tuple(escalation_conditions),
        )


__all__ = ["LLMSteeringController"]
