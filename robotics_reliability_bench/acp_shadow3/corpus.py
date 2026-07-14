"""Phase-3 corpus: primarily real-planner-generated (live path + recorded MPC).

Provenance (milestone §5):
  LIVE_PATH_TEST_FIXTURE      — the REAL deliberative TaskPlanner.plan() is called
                                at run time through the instrumented hook.
  RECORDED_PLANNER_OUTPUT     — seeded (deterministic) MPCPlanner.plan_with_validation
                                trajectories, reconstructed for the ACP adapter.
  REPOSITORY_INTEGRATION_SCENARIO / SIMULATOR_GENERATED — none available for this
                                joint-space manipulator domain (reported as 0).
  AUTHORED_EDGE_CASE          — required violation / edge cases the two real
                                planners do not emit (both currently produce only
                                safe stub / low-speed trajectories).

Nothing is called real-sensor evidence. Scenarios store inputs; the harness
regenerates the real planner output at run time (LIVE / RECORDED) so the live
path is genuinely exercised.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional


class Prov:
    LIVE = "LIVE_PATH_TEST_FIXTURE"
    RECORDED = "RECORDED_PLANNER_OUTPUT"
    REPO = "REPOSITORY_INTEGRATION_SCENARIO"
    SIM = "SIMULATOR_GENERATED"
    AUTHORED = "AUTHORED_EDGE_CASE"


@dataclass(frozen=True)
class Scen3:
    name: str
    provenance: str
    required_case: str
    kind: str                    # "live" | "recorded_mpc" | "authored_command" | "authored_traj"
    ground_truth_safe: bool
    # live
    goal_description: str = "move to location"
    goal_pose: Optional[List[float]] = None
    state12: Optional[List[float]] = None
    proximity: Optional[List[float]] = None   # sensor proximity distances -> obstacles
    # recorded_mpc
    seed: Optional[int] = None
    mpc_obstacles: List[List[float]] = field(default_factory=list)  # [x,y,z,r]
    # authored_command
    command_velocities: Optional[List[float]] = None
    emergency_stop: bool = False
    gripper: bool = False
    q0: List[float] = field(default_factory=lambda: [0.0] * 6)
    # authored_traj
    positions: Optional[List[List[float]]] = None
    velocities: Optional[List[List[float]]] = None
    accelerations: Optional[List[List[float]]] = None
    obstacles: List[List[float]] = field(default_factory=list)
    human: Optional[List[float]] = None
    freshness_s: float = 0.01
    malformed_dims: bool = False
    evaluator_exception: bool = False
    mutate: Optional[str] = None   # "state" | "trajectory"


def build_corpus() -> List[Scen3]:
    s: List[Scen3] = []
    S12 = [0.5] * 12

    # ---- LIVE: the real deliberative planner ----
    s.append(Scen3("live_move_nominal", Prov.LIVE, "valid_nominal_trajectory", "live",
                   True, goal_description="move to location",
                   goal_pose=[0.5, 0.0, 0.3], state12=S12, proximity=[2.0] * 8))
    s.append(Scen3("live_wait_hold", Prov.LIVE, "emergency_or_hold_trajectory", "live",
                   True, goal_description="stop", state12=S12, proximity=[2.0] * 8))
    s.append(Scen3("live_grasp_unsupported", Prov.LIVE, "unsupported_command", "live",
                   True, goal_description="grasp object", state12=S12, proximity=[2.0] * 8))

    # ---- RECORDED: seeded MPC (deterministic) ----
    s.append(Scen3("recorded_mpc_clear", Prov.RECORDED, "valid_nominal_trajectory",
                   "recorded_mpc", True, seed=7, mpc_obstacles=[[2.0, 2.0, 2.0, 0.1]]))
    s.append(Scen3("recorded_mpc_obstacle", Prov.RECORDED, "obstacle_collision",
                   "recorded_mpc", True, seed=11, mpc_obstacles=[[0.3, 0.0, 0.3, 0.2]]))

    # ---- AUTHORED command (fed through the real live-path adapter + bridge) ----
    s.append(Scen3("authored_velocity_breach", Prov.AUTHORED, "velocity_violation",
                   "authored_command", False, command_velocities=[10.0, 0, 0, 0, 0, 0]))
    s.append(Scen3("authored_emergency_stop", Prov.AUTHORED, "emergency_or_hold_trajectory",
                   "authored_command", True, command_velocities=None, emergency_stop=True))
    s.append(Scen3("authored_gripper_unsupported", Prov.AUTHORED, "unsupported_command",
                   "authored_command", True, gripper=True))
    s.append(Scen3("authored_malformed_dims", Prov.AUTHORED, "malformed_trajectory",
                   "authored_command", False, command_velocities=[0.5, 0.0, 0.0],
                   malformed_dims=True))
    s.append(Scen3("authored_nonfinite", Prov.AUTHORED, "malformed_trajectory",
                   "authored_command", False, command_velocities=[float("nan"), 0, 0, 0, 0, 0]))
    s.append(Scen3("authored_missing_trajectory", Prov.AUTHORED, "missing_trajectory",
                   "authored_command", False, command_velocities=None))

    # ---- AUTHORED trajectory (direct to the real validator adapter) ----
    def ramp(n, step=0.1):
        return [[step * i, 0, 0, 0, 0, 0] for i in range(n)]
    s.append(Scen3("authored_position_violation", Prov.AUTHORED, "joint_position_violation",
                   "authored_traj", False, positions=[[3.5, 0, 0, 0, 0, 0]]))
    s.append(Scen3("authored_accel_violation", Prov.AUTHORED, "acceleration_violation",
                   "authored_traj", False, positions=ramp(2),
                   accelerations=[[0] * 6, [50.0, 0, 0, 0, 0, 0]]))
    s.append(Scen3("authored_obstacle_collision", Prov.AUTHORED, "obstacle_collision",
                   "authored_traj", False, positions=ramp(3), obstacles=[[0.5, 0.0, 0.3, 0.2]]))
    s.append(Scen3("authored_stale_state", Prov.AUTHORED, "stale_state",
                   "authored_traj", False, positions=ramp(3), freshness_s=5.0))
    s.append(Scen3("authored_evaluator_exception", Prov.AUTHORED, "evaluator_exception",
                   "authored_traj", False, positions=ramp(3), evaluator_exception=True))
    s.append(Scen3("authored_all_invalid", Prov.AUTHORED, "all_candidate_trajectories_invalid",
                   "authored_traj", False, positions=[[3.5, 0, 0, 0, 0, 0]]))

    # ---- Authorization (commit-time revalidation §7) ----
    s.append(Scen3("auth_state_change", Prov.AUTHORED, "world_state_change_after_validation",
                   "authored_command", True, command_velocities=[0.5, 0, 0, 0, 0, 0],
                   mutate="state"))
    s.append(Scen3("auth_modified_trajectory", Prov.AUTHORED, "modified_trajectory_after_validation",
                   "authored_command", True, command_velocities=[0.5, 0, 0, 0, 0, 0],
                   mutate="trajectory"))

    return s
