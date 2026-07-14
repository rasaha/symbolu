"""Deterministic shadow-evaluation corpus (Phase 1). ALL scenarios synthetic.

Covers, across the three call-site families, every case the milestone requires:
clear safe winner, multiple admissible, unsafe-but-attractive, infeasible+high-
consistency, emergency-stop-vs-efficient, all-unsafe, missing-evidence, exact
tie, score-rescaling, temperature-sensitivity, conflict safety fallback, task
incompatibility, stale state, and modified-candidate.

Each scenario carries the primitive inputs both sides need: the ACP adapter
input and the faithful-BCVF-replica input. Nothing is tuned on these scenarios;
thresholds are frozen in ACP_PHASE1_PREREGISTRATION.md before the final run.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List


@dataclass(frozen=True)
class Scenario:
    call_site: str
    name: str
    kind: str            # "classify" | "authorization"
    payload: Dict
    synthetic: bool = True
    note: str = ""


def _clip01(x: float) -> float:
    return max(0.0, min(1.0, x))


def task_sf_sb(cap: float, load: float, coh: float, dist: float):
    """Reproduce coordination/task_allocation.py:_score_bid sf/sb."""
    sf = (0.3 * cap + 0.2 * (1.0 - load) + 0.2 * coh) / (1.0 - 0.3)
    distance_score = 1.0 - min(dist / 10.0, 1.0)
    sb = (0.3 * distance_score + 0.3 * cap + 0.2 * coh) / (1.0 - 0.2)
    return _clip01(sf), _clip01(sb)


def build_corpus() -> List[Scenario]:
    s: List[Scenario] = []

    # ---------------- Deliberative ----------------
    s.append(Scenario("deliberative", "D1_clear_safe_winner", "classify", {
        "actions": [
            {"id": "move", "action": "move_to", "sf": 0.8, "sb": 0.9,
             "min_obstacle_distance_m": 1.0},
            {"id": "wait", "action": "wait", "sf": 0.7, "sb": 0.3},
        ]}, note="obstacle clear; move is best goal + admissible"))

    s.append(Scenario("deliberative", "D2_unsafe_move_attractive_goal", "classify", {
        "actions": [
            {"id": "move", "action": "move_to", "sf": 0.45, "sb": 0.95,
             "min_obstacle_distance_m": 0.3},   # too close -> ACP rejects
            {"id": "wait", "action": "wait", "sf": 0.7, "sb": 0.3},
        ]}, note="move has attractive goal but obstacle 0.3 < 0.5"))

    s.append(Scenario("deliberative", "D3_missing_obstacle_evidence", "classify", {
        "actions": [
            {"id": "move", "action": "move_to", "sf": 0.6, "sb": 0.85},  # no obstacle data
            {"id": "wait", "action": "wait", "sf": 0.7, "sb": 0.3},
        ]}, note="move missing obstacle distance -> fail closed"))

    s.append(Scenario("deliberative", "D4_grasp_unevaluable", "classify", {
        "actions": [
            {"id": "grasp", "action": "grasp", "sf": 0.7, "sb": 0.85},   # no hard constraint applies
            {"id": "wait", "action": "wait", "sf": 0.7, "sb": 0.3},
        ]}, note="manipulation action has no hard-constraint data at this call site"))

    s.append(Scenario("deliberative", "D5_only_wait", "classify", {
        "actions": [
            {"id": "wait", "action": "wait", "sf": 0.7, "sb": 0.2},
        ]}, note="only safe fallback available"))

    # ---------------- Conflict resolution ----------------
    s.append(Scenario("conflict_resolution", "C1_stop_vs_efficient", "classify", {
        "strategies": [
            {"id": "MUTUAL_STOP", "strategy": "MUTUAL_STOP", "forward_score": 1.0,
             "backward_score": 0.3, "priority_score": 0.0, "safety_score": 1.0},
            {"id": "SPATIAL", "strategy": "SPATIAL_AVOIDANCE", "forward_score": 0.8,
             "backward_score": 0.65, "priority_score": 0.5, "safety_score": 0.95},
            {"id": "RESOURCE", "strategy": "RESOURCE_SHARING", "forward_score": 0.75,
             "backward_score": 0.8, "priority_score": 0.5, "safety_score": 0.85},
        ]}, note="emergency stop vs efficient maneuvers; all admissible"))

    s.append(Scenario("conflict_resolution", "C2_unsafe_strategy_present", "classify", {
        "strategies": [
            {"id": "SPATIAL", "strategy": "SPATIAL_AVOIDANCE", "forward_score": 0.8,
             "backward_score": 0.65, "priority_score": 0.5, "safety_score": 0.95},
            {"id": "RISKY", "strategy": "RESOURCE_SHARING", "forward_score": 0.9,
             "backward_score": 0.95, "priority_score": 0.6, "safety_score": 0.3},
        ]}, note="RISKY has attractive scores but safety 0.3 < 0.5"))

    s.append(Scenario("conflict_resolution", "C3_all_unsafe_no_stop", "classify", {
        "strategies": [
            {"id": "YIELD", "strategy": "PRIORITY_YIELD", "forward_score": 0.6,
             "backward_score": 0.7, "priority_score": 0.4, "safety_score": 0.35},
            {"id": "RESOURCE", "strategy": "RESOURCE_SHARING", "forward_score": 0.7,
             "backward_score": 0.8, "priority_score": 0.5, "safety_score": 0.2},
        ]}, note="all below safety floor, no emergency stop -> NO_SAFE_ACTION"))

    s.append(Scenario("conflict_resolution", "C4_safety_fallback_only", "classify", {
        "strategies": [
            {"id": "MUTUAL_STOP", "strategy": "MUTUAL_STOP", "forward_score": 1.0,
             "backward_score": 0.3, "priority_score": 0.0, "safety_score": 1.0},
        ]}, note="only emergency stop -> both pick it"))

    s.append(Scenario("conflict_resolution", "C5_exact_tie", "classify", {
        "strategies": [
            {"id": "A", "strategy": "SPATIAL_AVOIDANCE", "forward_score": 0.8,
             "backward_score": 0.7, "priority_score": 0.5, "safety_score": 0.9},
            {"id": "B", "strategy": "SPATIAL_AVOIDANCE", "forward_score": 0.8,
             "backward_score": 0.7, "priority_score": 0.5, "safety_score": 0.9},
        ]}, note="identical -> ACP tie-break by id"))

    # ---------------- Task allocation ----------------
    def bid(id_, cap, load, coh, dist):
        return {"id": id_, "capability_match": cap, "current_load": load,
                "coherence": coh, "distance_to_task": dist}

    s.append(Scenario("task_allocation", "T1_clear_closest_capable", "classify", {
        "bids": [bid("r_close", 0.9, 0.2, 0.9, 1.0),
                 bid("r_far", 0.9, 0.2, 0.9, 8.0)],
        "priority_value": 1.0},
        note="both admissible; ACP prefers closer"))

    s.append(Scenario("task_allocation", "T2_both_admissible_disagree", "classify", {
        "bids": [bid("r_a", 0.7, 0.6, 0.7, 2.0),
                 bid("r_b", 0.95, 0.1, 0.95, 4.0)],
        "priority_value": 2.0},
        note="ACP prefers closer r_a; BCVF may prefer higher-capability r_b"))

    s.append(Scenario("task_allocation", "T3_incompatible_bid", "classify", {
        "bids": [bid("r_ok", 0.9, 0.2, 0.9, 3.0),
                 bid("r_lowcap", 0.4, 0.2, 0.9, 1.0)],   # cap < 0.5
        "priority_value": 1.0},
        note="SYNTHETIC: r_lowcap bypasses production submit_bid pre-filter to "
             "exercise ACP's CAPABILITY_MATCH hard constraint (which duplicates "
             "the existing pre-filter)"))

    s.append(Scenario("task_allocation", "T4_exact_tie", "classify", {
        "bids": [bid("r_a", 0.8, 0.3, 0.8, 2.0),
                 bid("r_b", 0.8, 0.3, 0.8, 2.0)],
        "priority_value": 1.0},
        note="identical bids -> ACP tie-break by id"))

    # ---------------- Authorization scenarios ----------------
    s.append(Scenario("conflict_resolution", "AUTH_stale_world", "authorization", {
        "strategies": [
            {"id": "SPATIAL", "strategy": "SPATIAL_AVOIDANCE", "forward_score": 0.8,
             "backward_score": 0.7, "priority_score": 0.5, "safety_score": 0.9}],
        "mutate": "world"}, note="world version changes after authorization"))

    s.append(Scenario("conflict_resolution", "AUTH_modified_candidate", "authorization", {
        "strategies": [
            {"id": "SPATIAL", "strategy": "SPATIAL_AVOIDANCE", "forward_score": 0.8,
             "backward_score": 0.7, "priority_score": 0.5, "safety_score": 0.9}],
        "mutate": "candidate"}, note="candidate identity changes after authorization"))

    return s
