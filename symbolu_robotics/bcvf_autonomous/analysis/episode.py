"""Per-episode roll-up over a TrustShapedEpisodeRecord."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import numpy as np

from ..trust_diagnostics import TrustShapedEpisodeRecord
from .flips import find_argmax_flips, find_v2_state_flips
from .near_veto import find_near_vetoes


@dataclass
class EpisodeSummary:
    """Per-episode aggregate of trust-pipeline behavior."""

    episode_id: str
    classification: Optional[str]
    n_steps: int
    M: int
    n_argmax_flips: int
    n_v2_state_flips: int
    n_near_vetoes: int
    fraction_engaged: Optional[float]   # None when V2 disabled
    excluded_ever_count: int
    mean_bcvf_total: float
    max_bcvf_total: float
    deadband_fired_rate: float
    near_veto_peak_fraction: List[float]   # (M,)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "episode_id": self.episode_id,
            "classification": self.classification,
            "n_steps": int(self.n_steps),
            "M": int(self.M),
            "n_argmax_flips": int(self.n_argmax_flips),
            "n_v2_state_flips": int(self.n_v2_state_flips),
            "n_near_vetoes": int(self.n_near_vetoes),
            "fraction_engaged": (
                None if self.fraction_engaged is None
                else float(self.fraction_engaged)
            ),
            "excluded_ever_count": int(self.excluded_ever_count),
            "mean_bcvf_total": float(self.mean_bcvf_total),
            "max_bcvf_total": float(self.max_bcvf_total),
            "deadband_fired_rate": float(self.deadband_fired_rate),
            "near_veto_peak_fraction": [
                float(v) for v in self.near_veto_peak_fraction
            ],
            "metadata": dict(self.metadata),
        }


def summarize_episode(
    record: TrustShapedEpisodeRecord,
    episode_id: str = "",
    classification: Optional[str] = None,
    near_veto_fraction: float = 0.7,
    metadata: Optional[Dict[str, Any]] = None,
) -> EpisodeSummary:
    """Roll one episode record into an :class:`EpisodeSummary`."""
    T = record.n_steps
    M = record.M

    flips = find_argmax_flips(record, episode_id)
    v2_flips = find_v2_state_flips(record, episode_id)
    near_vetoes = find_near_vetoes(
        record, episode_id, near_veto_fraction=near_veto_fraction
    )

    # Fraction engaged — defined only if V2 produced any state strings.
    states = record.per_step_v2_state
    if states and any(s in ("uniform", "engaged") for s in states):
        engaged_count = sum(1 for s in states if s == "engaged")
        labelled_count = sum(1 for s in states if s in ("uniform", "engaged"))
        fraction_engaged: Optional[float] = (
            engaged_count / labelled_count if labelled_count > 0 else 0.0
        )
    else:
        fraction_engaged = None

    excluded_ever_count = (
        int(record.per_step_is_excluded.any(axis=0).sum())
        if record.per_step_is_excluded.size > 0 else 0
    )
    bcvf = record.per_step_bcvf_total
    mean_bcvf = float(bcvf.mean()) if bcvf.size > 0 else 0.0
    max_bcvf = float(bcvf.max()) if bcvf.size > 0 else 0.0
    deadband_fired_rate = (
        float(record.per_step_deadband_fired.mean())
        if record.per_step_deadband_fired.size > 0 else 0.0
    )

    # Peak near-veto fraction per predictor (0 if exclusion disabled
    # or the predictor never advanced its consec_suspect counter).
    peak_fractions: List[float] = []
    consec = record.per_step_consec_suspect
    T_threshold = record.exclusion_T
    if (
        consec.size > 0
        and T_threshold is not None
        and T_threshold > 0
    ):
        for m in range(M):
            col = consec[:, m]
            valid = col[col >= 0]
            peak = float(valid.max()) if valid.size > 0 else 0.0
            peak_fractions.append(peak / T_threshold)
    else:
        peak_fractions = [0.0] * M

    return EpisodeSummary(
        episode_id=episode_id,
        classification=classification,
        n_steps=T,
        M=M,
        n_argmax_flips=len(flips),
        n_v2_state_flips=len(v2_flips),
        n_near_vetoes=len(near_vetoes),
        fraction_engaged=fraction_engaged,
        excluded_ever_count=excluded_ever_count,
        mean_bcvf_total=mean_bcvf,
        max_bcvf_total=max_bcvf,
        deadband_fired_rate=deadband_fired_rate,
        near_veto_peak_fraction=peak_fractions,
        metadata=dict(metadata or {}),
    )
