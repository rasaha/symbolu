"""Per-config serialisation helpers for the CalibrationSet.

The bundle stores each runtime config as a JSON-friendly dict.
Two complications the helpers handle:

* numpy arrays — converted via ``.tolist()`` on serialise,
  ``np.asarray(..., dtype=...)`` on load.
* Enum members — converted via ``.value`` on serialise,
  re-instantiated via ``Enum(value)`` on load.

Keep the per-config logic explicit (one function per config)
so a future contributor can audit which fields get the
ndarray / enum treatment without untangling generic
introspection.
"""

from __future__ import annotations

from typing import Any, Dict

import numpy as np


# --------------------------------------------------------------------------- #
# BCVFConfig
# --------------------------------------------------------------------------- #


def bcvf_config_to_dict(config) -> Dict[str, Any]:
    """Serialise a :class:`BCVFConfig` to a JSON-friendly dict.

    ``cost_order`` is an IntEnum; we serialise the enum name
    (e.g. ``"SECOND"``) rather than its int value so a future
    refactor that re-numbers the enum doesn't silently
    re-interpret existing bundles.
    """
    return {
        "lambda_c": float(config.lambda_c),
        "gate_threshold": float(config.gate_threshold),
        "gate_beta": float(config.gate_beta),
        "huber_delta": float(config.huber_delta),
        "lever_arm": float(config.lever_arm),
        "weight_matrix": np.asarray(config.weight_matrix).tolist(),
        "use_anchor_pairing": bool(config.use_anchor_pairing),
        "anchor_index": int(config.anchor_index),
        "dt": float(config.dt),
        "cost_order": str(config.cost_order.name),
    }


def bcvf_config_from_dict(payload: Dict[str, Any]):
    """Reconstruct a :class:`BCVFConfig` from its dict form.

    Round-trip validates: an unrecognised ``cost_order`` name
    raises ``KeyError`` from the enum lookup; an
    out-of-shape ``weight_matrix`` would only fail when the
    config is used (the kernel itself enforces shape), but the
    field is still typed.
    """
    from ..core import BCVFConfig, CostOrder
    return BCVFConfig(
        lambda_c=float(payload["lambda_c"]),
        gate_threshold=float(payload["gate_threshold"]),
        gate_beta=float(payload["gate_beta"]),
        huber_delta=float(payload["huber_delta"]),
        lever_arm=float(payload["lever_arm"]),
        weight_matrix=np.asarray(
            payload["weight_matrix"], dtype=np.float64
        ),
        use_anchor_pairing=bool(payload["use_anchor_pairing"]),
        anchor_index=int(payload["anchor_index"]),
        dt=float(payload["dt"]),
        cost_order=CostOrder[payload["cost_order"]],
    )


# --------------------------------------------------------------------------- #
# ConsumerV2Config
# --------------------------------------------------------------------------- #


def consumer_v2_config_to_dict(config) -> Dict[str, Any]:
    return {
        "enabled": bool(config.enabled),
        "engage_threshold": float(config.engage_threshold),
        "disengage_threshold": float(config.disengage_threshold),
        "T_engage": int(config.T_engage),
        "T_disengage": int(config.T_disengage),
    }


def consumer_v2_config_from_dict(payload: Dict[str, Any]):
    from ..trust import ConsumerV2Config
    return ConsumerV2Config(
        enabled=bool(payload["enabled"]),
        engage_threshold=float(payload["engage_threshold"]),
        disengage_threshold=float(payload["disengage_threshold"]),
        T_engage=int(payload["T_engage"]),
        T_disengage=int(payload["T_disengage"]),
    )


# --------------------------------------------------------------------------- #
# BicycleConfig
# --------------------------------------------------------------------------- #


def bicycle_config_to_dict(config) -> Dict[str, Any]:
    return {
        "wheelbase": float(config.wheelbase),
        "max_steering": float(config.max_steering),
        "max_velocity": float(config.max_velocity),
        "max_acceleration": float(config.max_acceleration),
        "dt": float(config.dt),
    }


def bicycle_config_from_dict(payload: Dict[str, Any]):
    from ..predictors.base import BicycleConfig
    return BicycleConfig(
        wheelbase=float(payload["wheelbase"]),
        max_steering=float(payload["max_steering"]),
        max_velocity=float(payload["max_velocity"]),
        max_acceleration=float(payload["max_acceleration"]),
        dt=float(payload["dt"]),
    )


# --------------------------------------------------------------------------- #
# FailureConfig
# --------------------------------------------------------------------------- #


def failure_config_to_dict(config) -> Dict[str, Any]:
    return {
        "active": bool(config.active),
        "onset_time": float(config.onset_time),
        "severity": float(config.severity),
        "ramp_duration": float(config.ramp_duration),
    }


def failure_config_from_dict(payload: Dict[str, Any]):
    from ..predictors.base import FailureConfig
    return FailureConfig(
        active=bool(payload["active"]),
        onset_time=float(payload["onset_time"]),
        severity=float(payload["severity"]),
        ramp_duration=float(payload["ramp_duration"]),
    )


# --------------------------------------------------------------------------- #
# RealTimeBudget — already has to_dict; just need a re-loader
# --------------------------------------------------------------------------- #


def realtime_budget_to_dict(config) -> Dict[str, Any]:
    return config.to_dict()


def realtime_budget_from_dict(payload: Dict[str, Any]):
    from ..realtime.budget import RealTimeBudget
    return RealTimeBudget(**payload)


# --------------------------------------------------------------------------- #
# DDSQoSProfile — already has to_dict
# --------------------------------------------------------------------------- #


def dds_qos_profile_to_dict(config) -> Dict[str, Any]:
    return config.to_dict()


def dds_qos_profile_from_dict(payload: Dict[str, Any]):
    # bcvf_ros2 is a sibling package of bcvf_autonomous, not a
    # submodule. The bcvf_autonomous.ros2 re-export shim
    # surfaces the public symbol via the autonomy-prefix path
    # the API registry uses.
    from ..ros2 import DDSQoSProfile
    return DDSQoSProfile(**payload)


# --------------------------------------------------------------------------- #
# SafetyStateMachineConfig — frozen dataclass without to_dict; field-walk
# --------------------------------------------------------------------------- #


def safety_state_config_to_dict(config) -> Dict[str, Any]:
    return {
        "rolling_window_ticks": int(config.rolling_window_ticks),
        "near_veto_consec_floor": int(config.near_veto_consec_floor),
        "near_veto_rate_threshold": float(config.near_veto_rate_threshold),
        "bcvf_active_threshold": float(config.bcvf_active_threshold),
        "bcvf_active_rate_threshold": float(
            config.bcvf_active_rate_threshold
        ),
        "exclusion_persistence_ticks": int(
            config.exclusion_persistence_ticks
        ),
        "failsafe_excluded_predictor_count": int(
            config.failsafe_excluded_predictor_count
        ),
        "t_recovery_ticks": int(config.t_recovery_ticks),
    }


def safety_state_config_from_dict(payload: Dict[str, Any]):
    from ..safety_state.machine import SafetyStateMachineConfig
    return SafetyStateMachineConfig(**payload)


# --------------------------------------------------------------------------- #
# Round-trip validation helper
# --------------------------------------------------------------------------- #


def validate_config_dict(name: str, payload: Dict[str, Any], reloader) -> None:
    """Validate a config dict by trying to reconstruct the source
    dataclass via ``reloader(payload)``. Raises
    :class:`CalibrationSetError` on any reconstruction failure
    so the bundle never silently loads a malformed embedded
    config."""
    from .errors import CalibrationSetError
    try:
        reloader(payload)
    except (KeyError, TypeError, ValueError) as exc:
        raise CalibrationSetError(
            f"embedded {name} config fails reconstruction: {exc}"
        ) from exc
