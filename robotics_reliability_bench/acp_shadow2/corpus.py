"""Phase-2 real-scenario corpus (physical-safety shadow validation).

Provenance labels (milestone §5): scenarios are drawn from the repository's own
``tests/test_safety.py`` ``TrajectoryValidator`` fixtures (INTEGRATION_TEST) and
supplemented with AUTHORED_DETERMINISTIC cases for the required families the
fixtures do not cover. There is NO real-sensor data in this repo, so nothing is
labeled RECORDED_DATA; no scenario is described as real-sensor evidence.

Each candidate is a joint-space trajectory (positions per point, optional
velocities/accelerations/ee-pose) + obstacles/human, with a human-known
``ground_truth_safe`` label. The real ``TrajectoryValidator`` produces the
*measured* verdict; the corpus label is what a reviewer expects.

Trajectories are stored as plain lists (JSON-serializable); the harness builds
``TrajectoryPoint`` objects at run time. Deterministic — no RNG.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional


class Provenance:
    INTEGRATION_TEST = "INTEGRATION_TEST"
    SIMULATOR_SCENARIO = "SIMULATOR_SCENARIO"
    RECORDED_DATA = "RECORDED_DATA"
    AUTHORED_DETERMINISTIC = "AUTHORED_DETERMINISTIC"
    SYNTHETIC_UNIT = "SYNTHETIC_UNIT"


@dataclass(frozen=True)
class PhysCandidate:
    id: str
    positions: List[List[float]]                 # per trajectory point (n joints)
    velocities: Optional[List[List[float]]] = None
    accelerations: Optional[List[List[float]]] = None
    ee_pose: Optional[List[float]] = None        # [x,y,z,roll,pitch,yaw] on last pt
    coherence: float = 1.0
    obstacles: List[List[float]] = field(default_factory=list)  # [x,y,z,radius]
    human: Optional[List[float]] = None          # [x,y,z]
    freshness_s: float = 0.01
    abstract_safety: Optional[float] = None      # legacy conflict safety_score
    ground_truth_safe: bool = True
    safe_fallback: bool = False


@dataclass(frozen=True)
class PhysScenario:
    name: str
    provenance: str
    family: str              # "physical" | "abstract_vs_physical" | "authorization"
    required_case: str
    candidates: List[PhysCandidate]
    mutate: Optional[str] = None   # for authorization scenarios: "state" | "trajectory"


def _ramp(n_pts: int, step: float = 0.1):
    return [[step * i, 0.0, 0.0, 0.0, 0.0, 0.0] for i in range(n_pts)]


def build_corpus() -> List[PhysScenario]:
    s: List[PhysScenario] = []
    IT, AU = Provenance.INTEGRATION_TEST, Provenance.AUTHORED_DETERMINISTIC

    # ---- Physical family (single-candidate, ground-truth labelled) ----
    # Reproduced from tests/test_safety.py TrajectoryValidator fixtures.
    s.append(PhysScenario("safe_within_limits", IT, "physical", "clear_safe_maneuver",
        [PhysCandidate("safe", _ramp(3), ground_truth_safe=True)]))       # :743
    s.append(PhysScenario("position_limit_violation", IT, "physical", "invalid_trajectory",
        [PhysCandidate("pos", [[3.5, 0, 0, 0, 0, 0]], ground_truth_safe=False)]))  # :766
    s.append(PhysScenario("velocity_limit_breach", IT, "physical", "velocity_limit_breach",
        [PhysCandidate("vel", [[0, 0, 0, 0, 0, 0], [1.0, 0, 0, 0, 0, 0]],
                       ground_truth_safe=False)],))                        # :780 (1 rad/10ms)
    s.append(PhysScenario("obstacle_too_close", IT, "physical", "obstacle_too_close",
        [PhysCandidate("obs", _ramp(3), obstacles=[[0.5, 0.0, 0.3, 0.2]],
                       ground_truth_safe=False)]))                         # :818
    # Human placed at the default-FK end-effector location of the last point so
    # the REAL human-proximity check genuinely fires (default_fk of [0.2,0,..] ~=
    # [0.49, 0.10, 0.3]); faithful to test_safety.py:837 which asserts a
    # HUMAN_PROXIMITY collision is predicted.
    s.append(PhysScenario("human_proximity", IT, "physical", "emergency_stop_candidate",
        [PhysCandidate("hum", _ramp(3), human=[0.49, 0.10, 0.30],
                       ground_truth_safe=False)]))                         # :837

    # AUTHORED extra required cases.
    s.append(PhysScenario("acceleration_breach", AU, "physical", "acceleration_or_jerk_breach",
        [PhysCandidate("acc", _ramp(2),
                       accelerations=[[0, 0, 0, 0, 0, 0], [50.0, 0, 0, 0, 0, 0]],
                       ground_truth_safe=False)]))
    s.append(PhysScenario("emergency_stop_candidate", AU, "physical", "emergency_stop_candidate",
        [PhysCandidate("stop", [[0, 0, 0, 0, 0, 0]] * 3,
                       velocities=[[0, 0, 0, 0, 0, 0]] * 3,
                       ground_truth_safe=True, safe_fallback=True)]))
    s.append(PhysScenario("recovery_maneuver", AU, "physical", "recovery_maneuver",
        [PhysCandidate("recover", _ramp(4, step=0.02), ground_truth_safe=True)]))
    s.append(PhysScenario("all_candidates_unsafe", AU, "physical", "all_candidates_unsafe",
        [PhysCandidate("u1", [[3.5, 0, 0, 0, 0, 0]], ground_truth_safe=False),
         PhysCandidate("u2", [[0, 0, 0, 0, 0, 0], [1.0, 0, 0, 0, 0, 0]],
                       ground_truth_safe=False)]))
    s.append(PhysScenario("missing_physical_evidence", AU, "physical", "missing_physical_evidence",
        [PhysCandidate("empty", [], ground_truth_safe=False)]))
    s.append(PhysScenario("stale_perception_state", AU, "physical", "stale_perception_state",
        [PhysCandidate("stale", _ramp(3), freshness_s=5.0, ground_truth_safe=False)]))
    s.append(PhysScenario("planner_constraint_disagreement", AU, "physical",
        "planner_constraint_disagreement",
        [PhysCandidate("planner_pick", [[0, 0, 0, 0, 0, 0], [1.0, 0, 0, 0, 0, 0]],
                       ground_truth_safe=False),          # planner would emit this fast move
         PhysCandidate("safe_alt", _ramp(3, step=0.05), ground_truth_safe=True)]))

    # ---- Abstract-vs-physical family (conflict-resolution connection) ----
    # Each candidate carries BOTH the legacy abstract safety_score AND a real
    # physical trajectory; we measure whether they agree.
    s.append(PhysScenario("abstract_safe_physically_unsafe", AU, "abstract_vs_physical",
        "abstract_score_disagrees_with_physical",
        [PhysCandidate("hi_abstract", [[0, 0, 0, 0, 0, 0], [1.0, 0, 0, 0, 0, 0]],
                       abstract_safety=0.9, ground_truth_safe=False)]))
    s.append(PhysScenario("abstract_unsafe_physically_safe", AU, "abstract_vs_physical",
        "abstract_score_disagrees_with_physical",
        [PhysCandidate("lo_abstract", _ramp(3), abstract_safety=0.4,
                       ground_truth_safe=True)]))
    s.append(PhysScenario("abstract_physical_agree_safe", AU, "abstract_vs_physical",
        "abstract_score_disagrees_with_physical",
        [PhysCandidate("agree_safe", _ramp(3), abstract_safety=0.9,
                       ground_truth_safe=True)]))

    # ---- Authorization family ----
    s.append(PhysScenario("state_changes_before_commit", AU, "authorization",
        "state_changes_between_evaluation_and_commit",
        [PhysCandidate("auth_s", _ramp(3), ground_truth_safe=True)], mutate="state"))
    s.append(PhysScenario("modified_trajectory_after_auth", AU, "authorization",
        "modified_trajectory_after_authorization",
        [PhysCandidate("auth_t", _ramp(3), ground_truth_safe=True)], mutate="trajectory"))

    return s
