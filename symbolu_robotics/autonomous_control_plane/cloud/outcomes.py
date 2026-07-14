"""Cloud interpretation of the frozen ACP ``ActionDecision`` set (V2 §7).

ACP's decision enum is domain-neutral and **unchanged**. This module maps each
outcome onto a *cloud-operations meaning* — what a shadow operator would do with
the recommendation. It adds NO new decision states (that would fork the frozen
core); it only names the cloud consequence of each existing state.

Shadow-only: these are recommendations, never actuations. ACP never patches a
Deployment, and never mints an ActionGate execution token.
"""
from __future__ import annotations

from enum import Enum

from ..envelopes import ActionDecision


class CloudRecommendation(str, Enum):
    """What the ACP outcome means for a cloud operation (advisory)."""
    PROCEED = "PROCEED"                      # operationally safe now
    PROCEED_WITH_CONSTRAINTS = "PROCEED_WITH_CONSTRAINTS"  # safe, soft caveats
    REOBSERVE = "REOBSERVE"                  # refresh cluster state first
    HOLD = "HOLD"                            # do NOT apply; unsafe / no candidate


# Total, closed mapping. Robotics-motion outcomes that have no cloud analogue
# (REPLAN / DEGRADE_MODE / SAFE_STOP) collapse to the conservative HOLD — a
# shadow cloud operator never "degrades" or "safe-stops" a Deployment; it holds.
_MAP = {
    ActionDecision.EXECUTE: CloudRecommendation.PROCEED,
    ActionDecision.EXECUTE_WITH_CONSTRAINTS: CloudRecommendation.PROCEED_WITH_CONSTRAINTS,
    ActionDecision.REQUEST_MORE_OBSERVATION: CloudRecommendation.REOBSERVE,
    ActionDecision.REPLAN: CloudRecommendation.HOLD,
    ActionDecision.DEGRADE_MODE: CloudRecommendation.HOLD,
    ActionDecision.SAFE_STOP: CloudRecommendation.HOLD,
    ActionDecision.NO_SAFE_ACTION: CloudRecommendation.HOLD,
}


def cloud_recommendation(decision: ActionDecision) -> CloudRecommendation:
    """Map an ACP ``ActionDecision`` to its cloud-operations recommendation."""
    try:
        return _MAP[decision]
    except KeyError:  # pragma: no cover - closed enum, defensive
        return CloudRecommendation.HOLD


def is_permissive(rec: CloudRecommendation) -> bool:
    """Would this recommendation let an operation move forward?"""
    return rec in (CloudRecommendation.PROCEED,
                   CloudRecommendation.PROCEED_WITH_CONSTRAINTS)
