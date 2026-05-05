"""IO helpers — load a JSON-dumped trust diagnostics artifact back into
a typed ``TrustShapedEpisodeRecord``.

The Runner emits diagnostics via ``trust_diagnostics_path``:

    {
      "seed": 42,
      "diagnostics": { ... TrustShapedEpisodeRecord.to_dict() ... }
    }

This module reverses that — useful for fleet aggregation over a
directory of saved runs without re-simulating. Validation is
strict by design: a SOTIF / recall-triage tool reading thousands
of trip JSONs needs corruption to fail loudly, not silently
produce all-zero records.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Tuple, Union

import numpy as np

from ..trust_diagnostics import (
    RolloutAggregation,
    TrustShapedEpisodeRecord,
)


# Every key produced by :meth:`TrustShapedEpisodeRecord.to_dict` must
# be present in the loaded payload. Missing or None values raise
# ``ValueError`` — silent zero-fill is unsafe for SOTIF triage.
_REQUIRED_KEYS: Tuple[str, ...] = (
    "n_steps",
    "M",
    "aggregation",
    "per_step_weights",
    "per_step_costs",
    "per_step_residuals",
    "per_step_ema_mean",
    "per_step_ema_std",
    "per_step_bcvf_total",
    "per_step_deadband_active_count",
    "per_step_deadband_fired",
    "per_step_is_excluded",
    "per_step_gate_activations",
    "per_step_v2_state",
    "per_step_v2_signal",
    "per_step_consec_suspect",
    "per_step_consec_ok",
)


def _check_shape(
    name: str, arr: np.ndarray, expected: Tuple[int, ...],
) -> None:
    # Audit-fix (replay framework Finding 4): a zero-step
    # record's per_step arrays serialise as ``[]`` (an empty
    # nested list collapses to a 1-D empty), which round-trips
    # back as shape ``(0,)`` not the expected ``(0, M)``. A
    # zero-step episode is a real recall-investigation case
    # (collision in initial state, validation failure before the
    # first step) that the framework documents as bundle-able.
    # When the expected shape's first axis is 0, we accept any
    # 0-element array regardless of rank.
    if expected and expected[0] == 0 and arr.size == 0:
        return
    if arr.shape != expected:
        raise ValueError(
            f"{name} shape {arr.shape} does not match expected {expected}"
        )


def episode_record_from_dict(payload: Dict[str, Any]) -> TrustShapedEpisodeRecord:
    """Reconstruct a :class:`TrustShapedEpisodeRecord` from its ``to_dict()``.

    Raises ``ValueError`` when required keys are missing, when array
    shapes don't match the claimed ``(n_steps, M)``, or when the
    ``v2_state`` list length disagrees with ``n_steps``. The intent
    is to fail loudly on corrupted artifacts so downstream fleet
    aggregation never reports a vacuous "everything looks fine"
    summary on bad data.
    """
    if not isinstance(payload, dict):
        raise ValueError(
            f"episode_record_from_dict expects a dict; got {type(payload).__name__}"
        )

    missing = [
        k for k in _REQUIRED_KEYS
        if k not in payload or payload[k] is None
    ]
    if missing:
        raise ValueError(
            f"episode_record dict missing required keys: {missing}"
        )

    n_steps = int(payload["n_steps"])
    M = int(payload["M"])
    if n_steps < 0 or M < 0:
        raise ValueError(
            f"n_steps and M must be non-negative; got n_steps={n_steps}, M={M}"
        )
    aggregation = RolloutAggregation(payload["aggregation"])

    per_step_weights = np.asarray(payload["per_step_weights"], dtype=np.float64)
    per_step_costs = np.asarray(payload["per_step_costs"], dtype=np.float64)
    per_step_residuals = np.asarray(payload["per_step_residuals"], dtype=np.float64)
    per_step_ema_mean = np.asarray(payload["per_step_ema_mean"], dtype=np.float64)
    per_step_ema_std = np.asarray(payload["per_step_ema_std"], dtype=np.float64)
    per_step_bcvf_total = np.asarray(payload["per_step_bcvf_total"], dtype=np.float64)
    per_step_deadband_active_count = np.asarray(
        payload["per_step_deadband_active_count"], dtype=np.int64,
    )
    per_step_deadband_fired = np.asarray(
        payload["per_step_deadband_fired"], dtype=bool,
    )
    per_step_is_excluded = np.asarray(
        payload["per_step_is_excluded"], dtype=bool,
    )
    per_step_gate_activations = np.asarray(
        payload["per_step_gate_activations"], dtype=np.int64,
    )
    per_step_v2_state = list(payload["per_step_v2_state"])
    per_step_v2_signal = np.asarray(payload["per_step_v2_signal"], dtype=np.float64)
    per_step_consec_suspect = np.asarray(
        payload["per_step_consec_suspect"], dtype=np.int64,
    )
    per_step_consec_ok = np.asarray(payload["per_step_consec_ok"], dtype=np.int64)

    _check_shape("per_step_weights", per_step_weights, (n_steps, M))
    _check_shape("per_step_costs", per_step_costs, (n_steps, M))
    _check_shape("per_step_residuals", per_step_residuals, (n_steps, M))
    _check_shape("per_step_ema_mean", per_step_ema_mean, (n_steps, M))
    _check_shape("per_step_ema_std", per_step_ema_std, (n_steps, M))
    _check_shape("per_step_bcvf_total", per_step_bcvf_total, (n_steps,))
    _check_shape(
        "per_step_deadband_active_count",
        per_step_deadband_active_count, (n_steps,),
    )
    _check_shape(
        "per_step_deadband_fired", per_step_deadband_fired, (n_steps,),
    )
    _check_shape("per_step_is_excluded", per_step_is_excluded, (n_steps, M))
    _check_shape(
        "per_step_gate_activations", per_step_gate_activations, (n_steps,),
    )
    _check_shape("per_step_v2_signal", per_step_v2_signal, (n_steps,))
    _check_shape(
        "per_step_consec_suspect", per_step_consec_suspect, (n_steps, M),
    )
    _check_shape(
        "per_step_consec_ok", per_step_consec_ok, (n_steps, M),
    )
    if len(per_step_v2_state) != n_steps:
        raise ValueError(
            f"per_step_v2_state length {len(per_step_v2_state)} != n_steps {n_steps}"
        )

    return TrustShapedEpisodeRecord(
        n_steps=n_steps,
        M=M,
        aggregation=aggregation,
        per_step_weights=per_step_weights,
        per_step_costs=per_step_costs,
        per_step_residuals=per_step_residuals,
        per_step_ema_mean=per_step_ema_mean,
        per_step_ema_std=per_step_ema_std,
        per_step_bcvf_total=per_step_bcvf_total,
        per_step_deadband_active_count=per_step_deadband_active_count,
        per_step_deadband_fired=per_step_deadband_fired,
        per_step_is_excluded=per_step_is_excluded,
        per_step_gate_activations=per_step_gate_activations,
        per_step_v2_state=per_step_v2_state,
        per_step_v2_signal=per_step_v2_signal,
        per_step_consec_suspect=per_step_consec_suspect,
        per_step_consec_ok=per_step_consec_ok,
        exclusion_T=payload.get("exclusion_T"),
        records=[],
    )


def load_episode_from_json(
    path: Union[str, Path],
) -> Tuple[TrustShapedEpisodeRecord, Dict[str, Any]]:
    """Load a Runner-dumped diagnostics JSON.

    Returns ``(episode_record, top_level_metadata)`` where
    ``top_level_metadata`` is the JSON dict minus the
    ``"diagnostics"`` payload — typically just ``{"seed": ...}``.
    """
    p = Path(path)
    with open(p, "r", encoding="utf-8") as f:
        payload = json.load(f)
    if "diagnostics" not in payload:
        raise ValueError(
            f"{p}: expected key 'diagnostics' in JSON payload"
        )
    record = episode_record_from_dict(payload["diagnostics"])
    metadata = {k: v for k, v in payload.items() if k != "diagnostics"}
    return record, metadata
