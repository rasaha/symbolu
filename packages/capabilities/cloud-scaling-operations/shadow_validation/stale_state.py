"""Reusable stale-state evaluation.

Compares a prior and a current read of the same target to decide whether an advisory
recommendation may still be proposed. Anything other than :data:`StaleClassification.FRESH`
yields a non-actionable shadow decision — the harness never resolves staleness by acting;
it only re-reads through approved read methods.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Optional

from .contracts import StaleClassification, DeploymentObservation

_REQUIRED_FIELDS = ("resource_version", "generation", "current_replicas",
                    "observation_timestamp")


@dataclass(frozen=True)
class StaleResult:
    classification: StaleClassification
    actionable: bool
    detail: str

    def to_dict(self) -> dict:
        return {"classification": self.classification.value,
                "actionable": self.actionable, "detail": self.detail}


def snapshot(obs: DeploymentObservation, hpa_desired: Optional[int] = None) -> dict:
    """Extract the staleness-relevant fields from a deployment observation."""
    return {
        "resource_version": obs.resource_version,
        "generation": obs.generation,
        "current_replicas": obs.current_replicas,
        "observation_timestamp": obs.observation_timestamp,
        "hpa_desired": hpa_desired,
    }


class StaleStateEvaluator:
    def classify(
        self,
        current: Optional[Mapping[str, Any]],
        *,
        now: float,
        max_age: float,
        prior: Optional[Mapping[str, Any]] = None,
        namespace_available: bool = True,
    ) -> StaleResult:
        if not namespace_available:
            return StaleResult(StaleClassification.NAMESPACE_UNAVAILABLE, False,
                               "namespace unavailable")
        if current is None:
            return StaleResult(StaleClassification.RESOURCE_DISAPPEARED, False,
                               "resource disappeared between reads")
        for f in _REQUIRED_FIELDS:
            if current.get(f) is None:
                return StaleResult(StaleClassification.INCOMPLETE, False,
                                   f"missing field {f!r}")

        age = now - float(current["observation_timestamp"])
        if age < 0 or age > max_age:
            return StaleResult(StaleClassification.AGE_EXCEEDED, False,
                               f"observation age {age:.1f}s exceeds {max_age}s")

        if prior is not None:
            if current["resource_version"] != prior.get("resource_version"):
                return StaleResult(StaleClassification.RESOURCE_VERSION_CHANGED, False,
                                   "resource_version changed between reads")
            if current["generation"] != prior.get("generation"):
                return StaleResult(StaleClassification.GENERATION_CHANGED, False,
                                   "generation advanced between reads")
            if current["current_replicas"] != prior.get("current_replicas"):
                return StaleResult(StaleClassification.REPLICA_STATE_CHANGED, False,
                                   "replica count changed between reads")
            if (current.get("hpa_desired") is not None
                    and prior.get("hpa_desired") is not None
                    and current["hpa_desired"] != prior["hpa_desired"]):
                return StaleResult(StaleClassification.HPA_DESIRED_CHANGED, False,
                                   "HPA desired replicas changed between reads")

        return StaleResult(StaleClassification.FRESH, True, "fresh")


__all__ = ["StaleResult", "StaleStateEvaluator", "snapshot"]
