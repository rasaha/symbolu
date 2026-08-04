"""Stable public facade for the independent Cloud Scaling Controller package.

:class:`CloudScalingController` is the recommended entry point: it accepts a
validated :class:`ScalingObservation`, invokes the *unmodified* low-level
:class:`~ugence_cloud_scaling_controller.controller.Controller`, and maps the result
into a deterministic, JSON-serializable :class:`ScalingRecommendation`.

Boundary guarantees (see docs/BOUNDARIES.md):
  * Advisory-only: every recommendation carries ``advisory_only=True`` and
    ``actuation_performed=False``. This facade never actuates infrastructure, never
    calls a cloud API, never opens a network listener, and never invokes an optional
    :class:`~ugence_cloud_scaling_controller.contracts.ScalingExecutor`.
  * Validation runs in this facade *before* the control algorithm; the algorithm is
    never altered to implement validation.
"""

from __future__ import annotations

from typing import Any, Dict, List, Mapping, Optional, Union

import numpy as np

from .config import InfraControllerConfig
from .controller import Controller, ActionResult
from .contracts import (
    SCHEMA_VERSION,
    NONDETERMINISTIC_FIELDS,
    ContractError,
    ScalingObservation,
    ScalingRecommendation,
    normalize_observation,
)
from .version import __version__

ObservationLike = Union[ScalingObservation, Mapping[str, Any]]


def _jsonable(value: Any) -> Any:
    """Coerce numpy scalars/arrays to plain Python types for stable serialization."""
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, dict):
        return {k: _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    return value


def _component_breakdown(result: ActionResult) -> Dict[str, Any]:
    """Structured, JSON-safe breakdown of the controller's internal components."""
    from dataclasses import asdict

    return {
        "plasticity": _jsonable(asdict(result.plasticity)),
        "gain": _jsonable(asdict(result.gain)),
        "damping": _jsonable(asdict(result.damping)),
        "coherence": _jsonable(asdict(result.coherence)),
    }


class CloudScalingController:
    """Advisory scaling recommendation engine (stable package facade).

    Usage::

        from ugence_cloud_scaling_controller import (
            CloudScalingController, ScalingObservation,
        )

        ctrl = CloudScalingController()
        rec = ctrl.recommend(ScalingObservation(
            metrics={"cpu": 0.82, "latency_p99": 0.65},
            current_replicas=5,
            phase="peak",
        ))
        print(rec.recommendation, rec.replica_delta)
        print(rec.to_json(indent=2))
    """

    def __init__(self, config: Optional[InfraControllerConfig] = None):
        self._controller = Controller(config)

    @property
    def config(self) -> InfraControllerConfig:
        return self._controller.config

    @property
    def controller(self) -> Controller:
        """Access the underlying low-level controller (compatibility API)."""
        return self._controller

    @property
    def bootstrapped(self) -> bool:
        return self._controller.bootstrapped

    def bootstrap(self, historical_snapshots: List[Mapping[str, float]]) -> None:
        """Pre-learn baselines from historical normalized metric snapshots."""
        self._controller.bootstrap([dict(s) for s in historical_snapshots])

    def reset(self) -> None:
        """Reset all controller state (independent instances never share state)."""
        self._controller.reset()

    def recommend(self, observation: ObservationLike) -> ScalingRecommendation:
        """Evaluate one observation and return an advisory recommendation.

        Accepts a :class:`ScalingObservation` or a plain mapping (parsed JSON).
        Validates/normalizes the input (fail-closed), then runs the unmodified
        control algorithm.
        """
        if isinstance(observation, ScalingObservation):
            obs = normalize_observation(observation)
        elif isinstance(observation, Mapping):
            obs = normalize_observation(ScalingObservation.from_dict(observation))
        else:  # pragma: no cover - defensive
            raise ContractError(
                "observation must be a ScalingObservation or a mapping"
            )

        result = self._controller.step(
            metrics=dict(obs.metrics),
            current_replicas=obs.current_replicas,
            deploy_active=obs.deploy_active,
            phase=obs.phase,
            recent_pod_restarts=obs.recent_pod_restarts,
        )
        return self._to_recommendation(obs, result)

    def _to_recommendation(
        self, obs: ScalingObservation, result: ActionResult
    ) -> ScalingRecommendation:
        recommended = obs.current_replicas + int(result.replica_delta)
        determinism = {
            "scope": "decision-deterministic",
            "identity_bootstrapped": bool(self._controller.bootstrapped),
            "nondeterministic_fields": list(NONDETERMINISTIC_FIELDS),
            "note": (
                "Decision fields (recommendation, replica_delta, recommended_replicas, "
                "action_score, pressure, component_breakdown) are deterministic for a "
                "fixed config + input sequence. identity_deviation is a diagnostic "
                "derived from an unseeded identity baseline and varies between fresh "
                "controllers before deterministic bootstrap."
            ),
        }
        return ScalingRecommendation(
            schema_version=SCHEMA_VERSION,
            correlation_id=obs.correlation_id,
            recommendation=result.recommendation,
            replica_delta=int(result.replica_delta),
            current_replicas=obs.current_replicas,
            recommended_replicas=recommended,
            action_score=float(result.action_score),
            pressure=float(result.pressure),
            component_breakdown=_component_breakdown(result),
            identity_deviation=float(result.identity_deviation),
            explanation=result.explain(),
            controller_step=int(result.step),
            metrics_snapshot=_jsonable(dict(result.metrics_snapshot)),
            determinism=determinism,
            advisory_only=True,
            actuation_performed=False,
        )


def evaluate(
    observation: ObservationLike,
    config: Optional[InfraControllerConfig] = None,
) -> ScalingRecommendation:
    """One-shot convenience: build a controller, evaluate a single observation.

    Note: a fresh controller carries no learned state; for a running series use a
    persistent :class:`CloudScalingController` instance.
    """
    return CloudScalingController(config).recommend(observation)


__all__ = [
    "CloudScalingController",
    "evaluate",
    "__version__",
]
