"""Near-veto detection — predictors that came close to §6.6a exclusion
without ever crossing the threshold.

A near-veto is the SOTIF tell: a predictor whose
``consec_suspect`` reaches ``near_veto_fraction × exclusion_T`` during
the episode but is never excluded. A fleet that consistently produces
near-vetoes on the same predictor is signalling a sensor / model that
is one bad day away from a real exclusion.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import numpy as np

from ..trust_diagnostics import TrustShapedEpisodeRecord


_EXCLUSION_DISABLED_SENTINEL = -1


@dataclass
class NearVeto:
    """One predictor that came close to exclusion in one episode.

    ``metadata`` carries per-episode provenance (vehicle id, scenario,
    seed) so a fleet-scale triage tool can group near-vetoes without
    cross-referencing back through ``episode_id``.
    """

    episode_id: str
    predictor: int
    peak_tick: int
    peak_consec_suspect: int
    threshold_T: int
    peak_fraction: float
    excluded_during_episode: bool
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "episode_id": self.episode_id,
            "predictor": int(self.predictor),
            "peak_tick": int(self.peak_tick),
            "peak_consec_suspect": int(self.peak_consec_suspect),
            "threshold_T": int(self.threshold_T),
            "peak_fraction": float(self.peak_fraction),
            "excluded_during_episode": bool(self.excluded_during_episode),
            "metadata": dict(self.metadata),
        }


def find_near_vetoes(
    record: TrustShapedEpisodeRecord,
    episode_id: str = "",
    near_veto_fraction: float = 0.7,
) -> List[NearVeto]:
    """Find predictors that crested ``near_veto_fraction × exclusion_T``.

    Returns ``[]`` when exclusion was disabled (episode never had a
    valid ``exclusion_T`` recorded) or no predictor crossed the
    fraction. A predictor that was actually excluded during the
    episode is still reported (so a triage tool can correlate
    near-vetoes that escalated vs near-vetoes that didn't).
    """
    if not (0.0 < near_veto_fraction <= 1.0):
        raise ValueError(
            f"near_veto_fraction must be in (0, 1]; got {near_veto_fraction}"
        )

    T_threshold = record.exclusion_T
    if T_threshold is None or T_threshold <= 0:
        return []

    consec = record.per_step_consec_suspect
    if consec.size == 0:
        return []
    if consec.shape[1] != record.M:
        raise ValueError(
            f"per_step_consec_suspect shape mismatch: {consec.shape} vs M={record.M}"
        )

    # Mask out -1 sentinels (exclusion disabled at that tick).
    valid_mask = consec != _EXCLUSION_DISABLED_SENTINEL
    if not valid_mask.any():
        return []

    threshold_count = max(1, int(near_veto_fraction * T_threshold))
    near_vetoes: List[NearVeto] = []
    is_excluded = record.per_step_is_excluded

    for m in range(record.M):
        col = consec[:, m]
        valid_col = valid_mask[:, m]
        if not valid_col.any():
            continue
        col_masked = np.where(valid_col, col, np.iinfo(np.int64).min)
        peak = int(col_masked.max())
        if peak < threshold_count:
            continue
        peak_tick = int(np.argmax(col_masked))
        excluded = (
            bool(is_excluded[:, m].any())
            if is_excluded.shape[1] > m else False
        )
        near_vetoes.append(
            NearVeto(
                episode_id=episode_id,
                predictor=m,
                peak_tick=peak_tick,
                peak_consec_suspect=peak,
                threshold_T=int(T_threshold),
                peak_fraction=float(peak / T_threshold),
                excluded_during_episode=excluded,
            )
        )

    return near_vetoes
