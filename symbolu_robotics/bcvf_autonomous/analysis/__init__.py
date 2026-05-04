"""BCVF Autonomous post-hoc analysis harness — fleet-scale aggregation
over per-episode trust diagnostic records.

Usage:

    from glob import glob
    from symbolu_robotics.bcvf_autonomous.analysis import (
        load_episode_from_json, aggregate_fleet,
    )

    records, ids, classifications, metas = [], [], [], []
    for i, path in enumerate(sorted(glob("trips/*.json"))):
        rec, meta = load_episode_from_json(path)
        records.append(rec)
        ids.append(meta.get("trip_id", f"trip_{i}"))
        classifications.append(meta.get("outcome"))
        metas.append(meta)

    fleet = aggregate_fleet(records, ids, classifications, metas)
    print(fleet.argmax_flips_per_step)
    for nv in fleet.near_vetoes:
        print(nv)

See ``DESIGN.md`` for the full motivation and SOTIF-flow rationale.
"""

from __future__ import annotations

from .episode import EpisodeSummary, summarize_episode
from .fleet import FleetSummary, aggregate_fleet
from .flips import (
    ArgmaxFlip,
    V2StateFlip,
    find_argmax_flips,
    find_v2_state_flips,
)
from .io import episode_record_from_dict, load_episode_from_json
from .near_veto import NearVeto, find_near_vetoes
from .streaming import (
    Alert,
    AlertRule,
    StreamingFleetMonitor,
    WindowedFleetSummary,
)

__all__ = [
    "Alert",
    "AlertRule",
    "ArgmaxFlip",
    "EpisodeSummary",
    "FleetSummary",
    "NearVeto",
    "StreamingFleetMonitor",
    "V2StateFlip",
    "WindowedFleetSummary",
    "aggregate_fleet",
    "episode_record_from_dict",
    "find_argmax_flips",
    "find_near_vetoes",
    "find_v2_state_flips",
    "load_episode_from_json",
    "summarize_episode",
]
