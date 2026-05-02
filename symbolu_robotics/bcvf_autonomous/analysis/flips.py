"""Argmax / V2 state flip detection over a TrustShapedEpisodeRecord."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import numpy as np

from ..trust_diagnostics import TrustShapedEpisodeRecord


@dataclass
class ArgmaxFlip:
    """One tick where ``argmax(per_step_weights)`` changed."""

    episode_id: str
    tick: int
    from_predictor: int
    to_predictor: int
    weights_before: np.ndarray  # (M,) — weights at tick - 1
    weights_after: np.ndarray   # (M,) — weights at tick

    def to_dict(self) -> Dict[str, Any]:
        return {
            "episode_id": self.episode_id,
            "tick": int(self.tick),
            "from_predictor": int(self.from_predictor),
            "to_predictor": int(self.to_predictor),
            "weights_before": self.weights_before.tolist(),
            "weights_after": self.weights_after.tolist(),
        }


@dataclass
class V2StateFlip:
    """One tick where ``v2_state`` transitioned ``UNIFORM`` ⇄ ``ENGAGED``."""

    episode_id: str
    tick: int
    from_state: str
    to_state: str
    signal: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "episode_id": self.episode_id,
            "tick": int(self.tick),
            "from_state": self.from_state,
            "to_state": self.to_state,
            "signal": float(self.signal),
        }


def find_argmax_flips(
    record: TrustShapedEpisodeRecord,
    episode_id: str = "",
) -> List[ArgmaxFlip]:
    """Locate ticks where the highest-weighted predictor changed.

    Argmax flips are the V1 chatter signal the audit explicitly
    flagged. Each flip is one tick where the trust-weighted
    consensus picked a different lead predictor than the previous
    tick. Returns an empty list when the episode is shorter than 2
    ticks.
    """
    weights = record.per_step_weights
    if weights.shape[0] < 2:
        return []
    argmax = np.argmax(weights, axis=1)
    flips: List[ArgmaxFlip] = []
    for t in range(1, len(argmax)):
        if argmax[t] != argmax[t - 1]:
            flips.append(
                ArgmaxFlip(
                    episode_id=episode_id,
                    tick=int(t),
                    from_predictor=int(argmax[t - 1]),
                    to_predictor=int(argmax[t]),
                    weights_before=weights[t - 1].copy(),
                    weights_after=weights[t].copy(),
                )
            )
    return flips


def find_v2_state_flips(
    record: TrustShapedEpisodeRecord,
    episode_id: str = "",
) -> List[V2StateFlip]:
    """Locate ticks where the V2 consumer transitioned UNIFORM ⇄ ENGAGED.

    Returns ``[]`` when V2 was disabled across the whole episode (all
    state strings empty). Initial state at tick 0 has no predecessor,
    so it is never reported as a flip.
    """
    states = record.per_step_v2_state
    if not states or all(s == "" for s in states):
        return []
    signals = record.per_step_v2_signal
    flips: List[V2StateFlip] = []
    for t in range(1, len(states)):
        if states[t] != states[t - 1] and states[t] and states[t - 1]:
            flips.append(
                V2StateFlip(
                    episode_id=episode_id,
                    tick=int(t),
                    from_state=states[t - 1],
                    to_state=states[t],
                    signal=(
                        float(signals[t]) if t < len(signals) else float("nan")
                    ),
                )
            )
    return flips
