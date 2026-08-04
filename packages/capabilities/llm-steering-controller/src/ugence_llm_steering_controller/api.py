"""Curated public facade for the advisory LLM Steering Controller.

Convenience entry points that assemble a registry + controller and return a
:class:`SteeringResult`. Importing this module performs no I/O.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from .contracts import SteeringRequest, SteeringResult
from .controller import LLMSteeringController
from .policy import RoutingPolicy
from .registry import CandidateRegistry


def build_controller(registry: Dict[str, Any]) -> LLMSteeringController:
    """Build a controller from a raw registry dict (metadata only)."""
    return LLMSteeringController(CandidateRegistry.from_dict(registry))


def recommend(registry: Dict[str, Any], request: Dict[str, Any],
              policy: Optional[Dict[str, Any]] = None) -> SteeringResult:
    """One-shot: recommend a route from raw dicts. Returns a :class:`SteeringResult`.

    This is a pure advisory computation — no provider is contacted and no model is
    executed.
    """
    controller = build_controller(registry)
    req = SteeringRequest.from_dict(request)
    pol = None
    if policy is not None:
        pol = RoutingPolicy(
            preference=policy.get("preference", req.quality_preference),
            weight_overrides=policy.get("weight_overrides", {}) or {},
            policy_version=policy.get("policy_version", "") or "",
        )
    return controller.recommend(req, pol)


__all__ = ["build_controller", "recommend"]
