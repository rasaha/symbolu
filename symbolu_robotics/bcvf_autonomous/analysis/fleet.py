"""Fleet-scale aggregator over many EpisodeSummary rows."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

import numpy as np

from ..trust_diagnostics import TrustShapedEpisodeRecord
from .episode import EpisodeSummary, summarize_episode
from .flips import ArgmaxFlip, V2StateFlip
from .near_veto import NearVeto


@dataclass
class FleetSummary:
    """Aggregate trust-pipeline behavior across many episodes.

    Auditor-facing writers (frozen artifact emission):

    * :meth:`to_csv` — one row per episode, RFC-4180-quoted.
    * :meth:`to_markdown_report` — fleet-level narrative with
      headline aggregates, classification breakdown, per-predictor
      exclusion incidence, near-veto + V2-state-flip rosters, and a
      top-K per-episode index.
    * :meth:`to_dict` — JSON-friendly view for archive / dashboard
      ingest (unchanged from v0.3).
    """

    n_episodes: int
    n_total_steps: int
    classification_counts: Dict[str, int]
    argmax_flips_per_step: Dict[str, float]      # mean / p50 / p95 / p99
    v2_engaged_fraction: Optional[Dict[str, float]]   # None if V2 never enabled
    deadband_fired_rate: float
    per_predictor_excluded_rate: List[float]
    near_vetoes: List[NearVeto] = field(repr=False, default_factory=list)
    v2_state_flips: List[V2StateFlip] = field(repr=False, default_factory=list)
    episodes: List[EpisodeSummary] = field(repr=False, default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "n_episodes": int(self.n_episodes),
            "n_total_steps": int(self.n_total_steps),
            "classification_counts": dict(self.classification_counts),
            "argmax_flips_per_step": dict(self.argmax_flips_per_step),
            "v2_engaged_fraction": (
                None if self.v2_engaged_fraction is None
                else dict(self.v2_engaged_fraction)
            ),
            "deadband_fired_rate": float(self.deadband_fired_rate),
            "per_predictor_excluded_rate": [
                float(r) for r in self.per_predictor_excluded_rate
            ],
            "near_vetoes": [nv.to_dict() for nv in self.near_vetoes],
            "v2_state_flips": [vf.to_dict() for vf in self.v2_state_flips],
            "episodes": [ep.to_dict() for ep in self.episodes],
        }

    def to_csv(self, path: Union[str, Path]) -> Path:
        """Write the per-episode CSV to ``path``. Returns the Path."""
        from .reports import write_fleet_csv
        return write_fleet_csv(self, path)

    def to_markdown_report(
        self,
        path: Union[str, Path],
        *,
        title: str = "BCVF Fleet Summary",
        label: Optional[str] = None,
        generated_at: Optional[datetime] = None,
        top_k_episodes: int = 25,
    ) -> Path:
        """Write the regulator-friendly fleet markdown report to ``path``."""
        from .reports import write_fleet_markdown
        return write_fleet_markdown(
            self,
            path,
            title=title,
            label=label,
            generated_at=generated_at,
            top_k_episodes=top_k_episodes,
        )


def _percentiles(values: np.ndarray) -> Dict[str, float]:
    if values.size == 0:
        return {"mean": 0.0, "p50": 0.0, "p95": 0.0, "p99": 0.0}
    return {
        "mean": float(values.mean()),
        "p50": float(np.percentile(values, 50)),
        "p95": float(np.percentile(values, 95)),
        "p99": float(np.percentile(values, 99)),
    }


def aggregate_fleet(
    records: Sequence[TrustShapedEpisodeRecord],
    episode_ids: Optional[Sequence[str]] = None,
    classifications: Optional[Sequence[Optional[str]]] = None,
    metadata: Optional[Sequence[Optional[Dict[str, Any]]]] = None,
    near_veto_fraction: float = 0.7,
) -> FleetSummary:
    """Aggregate per-episode trust diagnostics into a :class:`FleetSummary`.

    Args:
        records: per-episode :class:`TrustShapedEpisodeRecord` instances.
        episode_ids: optional list aligned with ``records``; defaults
            to ``"episode_<index>"``.
        classifications: optional per-episode label (e.g.
            ``"collision"``). Used to populate ``classification_counts``.
        metadata: optional per-episode dict (scenario, vehicle id, ...).
        near_veto_fraction: passed to :func:`find_near_vetoes`.

    Per-episode summaries (``EpisodeSummary``) are collected on the
    way through; the fleet-level aggregates are computed from them
    plus the underlying records (so we don't double-detect events).
    """
    n = len(records)
    if episode_ids is None:
        episode_ids = [f"episode_{i}" for i in range(n)]
    if classifications is None:
        classifications = [None] * n
    if metadata is None:
        metadata = [None] * n
    if not (len(episode_ids) == n and len(classifications) == n
            and len(metadata) == n):
        raise ValueError(
            "episode_ids, classifications, metadata must align with records"
        )

    if n == 0:
        return FleetSummary(
            n_episodes=0,
            n_total_steps=0,
            classification_counts={},
            argmax_flips_per_step={"mean": 0.0, "p50": 0.0, "p95": 0.0, "p99": 0.0},
            v2_engaged_fraction=None,
            deadband_fired_rate=0.0,
            per_predictor_excluded_rate=[],
            near_vetoes=[],
            v2_state_flips=[],
            episodes=[],
        )

    M = max(r.M for r in records)
    episode_summaries: List[EpisodeSummary] = []
    near_vetoes_all: List[NearVeto] = []
    v2_flips_all: List[V2StateFlip] = []
    flip_rates: List[float] = []
    engaged_fractions: List[float] = []
    deadband_rates: List[float] = []
    excluded_counts = np.zeros(M, dtype=np.int64)
    n_total_steps = 0

    for record, ep_id, cls, meta in zip(
        records, episode_ids, classifications, metadata
    ):
        ep = summarize_episode(
            record,
            episode_id=ep_id,
            classification=cls,
            near_veto_fraction=near_veto_fraction,
            metadata=meta,
        )
        episode_summaries.append(ep)
        n_total_steps += ep.n_steps

        if ep.n_steps > 0:
            flip_rates.append(ep.n_argmax_flips / ep.n_steps)
        if ep.fraction_engaged is not None:
            engaged_fractions.append(ep.fraction_engaged)
        deadband_rates.append(ep.deadband_fired_rate)

        # Per-predictor exclusion incidence — pad to fleet-wide M.
        if record.per_step_is_excluded.size > 0:
            ever = record.per_step_is_excluded.any(axis=0).astype(np.int64)
            if ever.shape[0] <= M:
                excluded_counts[: ever.shape[0]] += ever

        # Reuse the events cached on the summary instead of re-running
        # the detectors. The cached events already carry the per-
        # episode metadata.
        near_vetoes_all.extend(ep.near_vetoes)
        v2_flips_all.extend(ep.v2_state_flips)

    cls_counts = Counter(
        c for c in classifications if c is not None
    )
    argmax_stats = _percentiles(np.asarray(flip_rates, dtype=np.float64))
    v2_stats = (
        None if not engaged_fractions
        else _percentiles(np.asarray(engaged_fractions, dtype=np.float64))
    )
    deadband_rate_mean = (
        float(np.mean(deadband_rates)) if deadband_rates else 0.0
    )
    per_predictor_rate = [
        float(c / n) for c in excluded_counts.tolist()
    ]

    return FleetSummary(
        n_episodes=n,
        n_total_steps=n_total_steps,
        classification_counts=dict(cls_counts),
        argmax_flips_per_step=argmax_stats,
        v2_engaged_fraction=v2_stats,
        deadband_fired_rate=deadband_rate_mean,
        per_predictor_excluded_rate=per_predictor_rate,
        near_vetoes=near_vetoes_all,
        v2_state_flips=v2_flips_all,
        episodes=episode_summaries,
    )
