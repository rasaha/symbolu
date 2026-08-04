"""Build human-readable + structured routing explanations."""

from __future__ import annotations

from typing import List, Tuple

from .contracts import CandidateScore, RoutingExplanation, SteeringRequest
from .policy import TIE_BREAK_RULE, RoutingPolicy, weight_preset_name


def build_explanation(
    request: SteeringRequest,
    policy: RoutingPolicy,
    top: CandidateScore,
    ranked: List[CandidateScore],
    rejected_count: int,
    considered: int,
) -> RoutingExplanation:
    preset = weight_preset_name(policy.preference)
    # Identify the two highest-weighted contributing dimensions for the winner.
    top_dims = sorted(top.weighted.items(), key=lambda kv: (-kv[1], kv[0]))[:3]
    dim_phrases = ", ".join(f"{k}={v}" for k, v in top_dims)

    reasons: List[str] = [
        f"{considered} candidate(s) considered; {rejected_count} rejected by hard "
        f"constraints; {len(ranked)} eligible and scored.",
        f"'{top.model_id}' ({top.provider_id}) ranked highest with total score "
        f"{top.total} under the '{preset}' preference preset.",
        f"Leading weighted dimensions for the recommendation: {dim_phrases}.",
    ]
    if len(ranked) > 1:
        runner = ranked[1]
        reasons.append(
            f"Runner-up '{runner.model_id}' scored {runner.total} "
            f"(margin {round(top.total - runner.total, 6)}).")
    reasons.append("Hard constraints were applied before scoring; no soft score restored "
                   "a disqualified candidate.")

    summary = (f"Recommend model '{top.model_id}' via provider '{top.provider_id}' "
               f"for task category '{request.task_category}' — advisory only, not executed.")
    return RoutingExplanation(
        summary=summary,
        reasons=tuple(reasons),
        weight_preset=preset,
        tie_break_rule=TIE_BREAK_RULE,
    )


def no_candidate_reasons(rejected: Tuple[dict, ...]) -> Tuple[str, ...]:
    """Summarize why nothing was eligible (top failing constraints)."""
    from collections import Counter

    failed = Counter()
    for r in rejected:
        for c in r.get("constraints", []):
            if not c.get("satisfied", True):
                failed[c.get("name", "unknown")] += 1
    top = [f"{name} (×{count})" for name, count in failed.most_common(5)]
    if not top:
        return ("registry contained no candidates",)
    return tuple([f"most common disqualifying constraint(s): {', '.join(top)}"])


__all__ = ["build_explanation", "no_candidate_reasons"]
