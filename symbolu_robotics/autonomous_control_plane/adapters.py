"""Call-site adapters (Phase 1).

Translate the *primitive* inputs of each production BCVF call site into ACP
canonical envelopes + evaluated hard-constraint results + a frozen lexicographic
soft-order key. Adapters take plain scalars/dicts (extracted by the external
shadow harness), so this package imports NOTHING from production and never
mutates a production object.

Physical fields the call site does not provide (max_speed, max_accel,
stopping_margin_s, collision_margin_m, stability_margin) are set to the inert,
conservative placeholder ``0.0`` and listed in ``unavailable_fields``. No Phase-1
constraint or sort key reads them — the lexicographic selectors use the per-site
key below, not the margin tie-break.

Frozen soft orders (justified in ``ACP_ACTION_SELECTION_IMPLEMENTATION.md``):
* deliberative:  goal_progress ↓ , feasibility ↓
* conflict:      safety_score ↓ , efficiency(backward) ↓
* task_alloc:    distance ↑ , load ↑ , capability ↓

Standard-library only.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Dict, List, Sequence, Tuple

from . import constraint_library as clib
from .constraints import ConstraintResult
from .envelopes import ActionType, CanonicalActionCandidate
from .world_state import (CanonicalWorldState, FreshnessSummary, OperatingMode,
                          Pose, Velocity)

_UNAVAILABLE_PHYSICAL = ("max_speed", "max_accel", "stopping_margin_s",
                         "collision_margin_m", "stability_margin")


@dataclass(frozen=True)
class AdaptedSet:
    call_site: str
    world_state: CanonicalWorldState
    candidates: Tuple[CanonicalActionCandidate, ...]
    candidate_constraints: Dict[str, Tuple[ConstraintResult, ...]]
    sort_key: Callable[[CanonicalActionCandidate], tuple]
    unavailable_fields: Tuple[str, ...] = field(default_factory=tuple)


def _world(tick: int, mission_id: str, env_version: str,
           fresh_age_s: float = 0.01, n_fresh: int = 1, n_stale: int = 0,
           mode: OperatingMode = OperatingMode.AUTONOMOUS) -> CanonicalWorldState:
    return CanonicalWorldState(
        tick=tick, observation_time_s=float(tick) * 0.1, pose=Pose(0.0, 0.0),
        velocity=Velocity(), environment_version=env_version,
        mission_id=mission_id,
        freshness=FreshnessSummary(fresh_age_s, n_fresh, n_stale,
                                   all_within_budget=(n_stale == 0)),
        operating_mode=mode)


def _candidate(cid: str, action_type: ActionType, world_version: str,
               goal_progress: float, energy: float, duration: float,
               meta: Dict[str, str]) -> CanonicalActionCandidate:
    m = dict(meta)
    m["unavailable"] = ",".join(_UNAVAILABLE_PHYSICAL)
    return CanonicalActionCandidate(
        candidate_id=cid, action_type=action_type, trajectory_ref=f"{cid}:traj",
        target=meta.get("target", ""), expected_duration_s=duration,
        max_speed=0.0, max_accel=0.0, stopping_margin_s=0.0,
        collision_margin_m=0.0, stability_margin=0.0, goal_progress=goal_progress,
        energy_estimate=energy, origin_state_version=world_version, metadata=m,
        provenance=meta.get("provenance", ""))


_DELIB_TYPE = {"move_to": ActionType.MOVE, "grasp": ActionType.MANIPULATE,
               "release": ActionType.MANIPULATE, "wait": ActionType.HOLD}
_CONFLICT_TYPE = {"MUTUAL_STOP": ActionType.STOP, "PRIORITY_YIELD": ActionType.YIELD,
                  "TEMPORAL_OFFSET": ActionType.YIELD,
                  "SPATIAL_AVOIDANCE": ActionType.MOVE,
                  "RESOURCE_SHARING": ActionType.CUSTOM}


def adapt_deliberative(*, tick: int, mission_id: str, env_version: str,
                       actions: Sequence[dict]) -> AdaptedSet:
    """actions: [{id, action, goal_progress, feasibility, min_obstacle_distance_m?}]

    ``min_obstacle_distance_m`` present only for move actions that have obstacle
    data; absent => the OBSTACLE_CLEARANCE constraint fails closed (MISSING_*).
    ``wait`` maps to a safe fallback (inherently admissible).
    """
    ws = _world(tick, mission_id, env_version)
    cons = clib.deliberative_constraints()
    cands, cc = [], {}
    for a in actions:
        atype = _DELIB_TYPE.get(a["action"], ActionType.CUSTOM)
        meta = {"feasibility": repr(float(a.get("feasibility", 0.0))),
                "provenance": f"deliberative:{a['action']}"}
        if a["action"] == "wait":
            meta["safe_fallback"] = "true"
        if "min_obstacle_distance_m" in a and a["min_obstacle_distance_m"] is not None:
            meta["min_obstacle_distance_m"] = repr(float(a["min_obstacle_distance_m"]))
        c = _candidate(a["id"], atype, ws.version,
                       goal_progress=float(a.get("goal_progress", 0.0)),
                       energy=float(a.get("energy", 0.0)),
                       duration=float(a.get("duration", 1.0)), meta=meta)
        cands.append(c)
        cc[c.candidate_id] = clib.evaluate_constraint_set(c, cons, ws.version)

    def key(c: CanonicalActionCandidate):
        return (-c.goal_progress, -float(c.metadata.get("feasibility", "0.0")))

    return AdaptedSet("deliberative", ws, tuple(cands), cc, key,
                      unavailable_fields=("stopping_distance", "actuator_limits",
                                          "stability", "trajectory_validity"))


def adapt_conflict(*, tick: int, conflict_id: str, env_version: str,
                   strategies: Sequence[dict]) -> AdaptedSet:
    """strategies: [{id, strategy, forward_score, backward_score, safety_score}]"""
    ws = _world(tick, conflict_id, env_version)
    cons = clib.conflict_constraints()
    cands, cc = [], {}
    for s in strategies:
        atype = _CONFLICT_TYPE.get(s["strategy"], ActionType.CUSTOM)
        meta = {"safety_score": repr(float(s["safety_score"])),
                "feasibility": repr(float(s["forward_score"])),
                "efficiency": repr(float(s["backward_score"])),
                "provenance": f"conflict:{s['strategy']}"}
        c = _candidate(s["id"], atype, ws.version, goal_progress=float(s["backward_score"]),
                       energy=0.0, duration=1.0, meta=meta)
        cands.append(c)
        cc[c.candidate_id] = clib.evaluate_constraint_set(c, cons, ws.version)

    def key(c: CanonicalActionCandidate):
        return (-float(c.metadata.get("safety_score", "0.0")),
                -float(c.metadata.get("efficiency", "0.0")))

    return AdaptedSet("conflict_resolution", ws, tuple(cands), cc, key,
                      unavailable_fields=("collision_margin_m", "stopping_distance",
                                          "actuator_limits"))


def adapt_task_allocation(*, tick: int, task_id: str, env_version: str,
                          bids: Sequence[dict]) -> AdaptedSet:
    """bids: [{id(robot_id), capability_match, current_load, coherence, distance_to_task}]"""
    ws = _world(tick, task_id, env_version)
    cons = clib.task_allocation_constraints()
    cands, cc = [], {}
    for b in bids:
        meta = {"capability_match": repr(float(b["capability_match"])),
                "current_load": repr(float(b["current_load"])),
                "coherence": repr(float(b["coherence"])),
                "distance_to_task": repr(float(b["distance_to_task"])),
                "provenance": f"task_allocation:{b['id']}"}
        c = _candidate(b["id"], ActionType.CUSTOM, ws.version,
                       goal_progress=float(b["capability_match"]), energy=0.0,
                       duration=float(b["distance_to_task"]), meta=meta)
        cands.append(c)
        cc[c.candidate_id] = clib.evaluate_constraint_set(c, cons, ws.version)

    def key(c: CanonicalActionCandidate):
        return (float(c.metadata.get("distance_to_task", "0.0")),
                float(c.metadata.get("current_load", "0.0")),
                -float(c.metadata.get("capability_match", "0.0")))

    return AdaptedSet("task_allocation", ws, tuple(cands), cc, key,
                      unavailable_fields=("collision_margin_m", "stopping_distance",
                                          "actuator_limits", "stability"))
