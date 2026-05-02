"""IO helpers — load a JSON-dumped trust diagnostics artifact back into
a typed ``TrustShapedEpisodeRecord``.

The Runner emits diagnostics via ``trust_diagnostics_path``:

    {
      "seed": 42,
      "diagnostics": { ... TrustShapedEpisodeRecord.to_dict() ... }
    }

This module reverses that — useful for fleet aggregation over a
directory of saved runs without re-simulating.
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


def episode_record_from_dict(payload: Dict[str, Any]) -> TrustShapedEpisodeRecord:
    """Reconstruct a :class:`TrustShapedEpisodeRecord` from its ``to_dict()``."""
    n_steps = int(payload["n_steps"])
    M = int(payload["M"])
    aggregation = RolloutAggregation(payload["aggregation"])

    def f64(key: str, fallback_shape: Tuple[int, ...]) -> np.ndarray:
        if key in payload and payload[key] is not None:
            return np.asarray(payload[key], dtype=np.float64)
        return np.zeros(fallback_shape, dtype=np.float64)

    def i64(key: str, fallback_shape: Tuple[int, ...]) -> np.ndarray:
        if key in payload and payload[key] is not None:
            return np.asarray(payload[key], dtype=np.int64)
        return np.zeros(fallback_shape, dtype=np.int64)

    def b(key: str, fallback_shape: Tuple[int, ...]) -> np.ndarray:
        if key in payload and payload[key] is not None:
            return np.asarray(payload[key], dtype=bool)
        return np.zeros(fallback_shape, dtype=bool)

    return TrustShapedEpisodeRecord(
        n_steps=n_steps,
        M=M,
        aggregation=aggregation,
        per_step_weights=f64("per_step_weights", (n_steps, M)),
        per_step_costs=f64("per_step_costs", (n_steps, M)),
        per_step_residuals=f64("per_step_residuals", (n_steps, M)),
        per_step_ema_mean=f64("per_step_ema_mean", (n_steps, M)),
        per_step_ema_std=f64("per_step_ema_std", (n_steps, M)),
        per_step_bcvf_total=f64("per_step_bcvf_total", (n_steps,)),
        per_step_deadband_active_count=i64(
            "per_step_deadband_active_count", (n_steps,)
        ),
        per_step_deadband_fired=b("per_step_deadband_fired", (n_steps,)),
        per_step_is_excluded=b("per_step_is_excluded", (n_steps, M)),
        per_step_gate_activations=i64(
            "per_step_gate_activations", (n_steps,)
        ),
        per_step_v2_state=list(payload.get("per_step_v2_state") or []),
        per_step_v2_signal=f64("per_step_v2_signal", (n_steps,)),
        per_step_consec_suspect=i64(
            "per_step_consec_suspect", (n_steps, M)
        ),
        per_step_consec_ok=i64(
            "per_step_consec_ok", (n_steps, M)
        ),
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
