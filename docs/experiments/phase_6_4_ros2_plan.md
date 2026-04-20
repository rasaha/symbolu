# §6.4 ROS 2 Adapter — Integration Plan

**Status.** Design landed; framework-agnostic scaffold shipped.
`rclpy`-backed node plumbing and catkin/colcon build infrastructure
remain ~3 weeks of execution work per the §6.4 design-doc estimate.

## Goal

Ship a **ROS 2 companion package** that drops into a Nav2 / MoveIt /
Autoware.universe planning pipeline as a single `pip` (or
`rosdep`-resolvable) dependency, providing BCVF trust-shaping as a
ROS 2 node sitting between predictor nodes and a planner.

## Architecture

Two layers, strictly separated:

```
┌──────────────────────────────────────────────────────────────┐
│  External ROS 2 graph                                         │
│                                                               │
│  Predictor nodes ──► /predicted_trajectories (M predictors)   │
│                            │                                  │
│                            ▼                                  │
│  BCVFTrustNode (rclpy) ───► /trust_distribution               │
│                            │                                  │
│                            ▼                                  │
│  Planner (Nav2 smac / MoveIt OMPL / Autoware)                 │
└──────────────────────────────────────────────────────────────┘
                     │
                     ▼ imports via rclpy shim only when ROS 2 present
┌──────────────────────────────────────────────────────────────┐
│  symbolu_robotics.bcvf_ros2                                   │
│                                                               │
│  ros2_shim.py (imports rclpy) ──► BCVFTrustNode               │
│                        │                                      │
│                        ▼                                      │
│  core.py (pure Python) ──────► BCVFTrustBridge                │
│                        │                                      │
│                        ▼                                      │
│  symbolu_robotics.bcvf_autonomous.trust.TrustWeightComputer   │
└──────────────────────────────────────────────────────────────┘
```

**Why the split.** Testing, CI, and numerical validation all happen
on the pure-Python core (`BCVFTrustBridge`). The `rclpy` shim is
thin — message <-> dict conversion, topic pub/sub, timer-driven
step triggers. If an integrator doesn't have ROS 2 installed, the
core still works; if they do, they import the shim and get a real
ROS 2 node. Matches the §6.3 discipline where the `TrustWeightComputer`
has no MPPI dependency.

## Message schema

Two custom message types, defined first as Python dataclasses (for
framework-agnostic use) and mirrored in ROS 2 `.msg` files (once
colcon build infrastructure lands).

### `PredictedTrajectories` (subscribed)

Produced by each predictor node, aggregated by the BCVFTrustNode.

```
# Python dataclass equivalent (see messages.py)
@dataclass
class PredictedTrajectories:
    stamp: float                          # nanoseconds since epoch
    frame_id: str                         # e.g., "map" or "base_link"
    num_predictors: int                   # M
    num_rollouts: int                     # K (1 for single-hypothesis predictors)
    horizon: int                          # H
    predictor_names: List[str]            # length M
    trajectories: np.ndarray              # (K, M, H, 3) SE(2) x/y/θ
```

ROS 2 `.msg` sketch:
```
# PredictedTrajectories.msg
std_msgs/Header header
string[] predictor_names
uint16 num_rollouts
uint16 horizon
geometry_msgs/Pose2D[] trajectories   # flattened (K * M * H) row-major
```

### `TrustDistribution` (published)

The BCVF output: trust weights + diagnostics.

```
# Python dataclass
@dataclass
class TrustDistribution:
    stamp: float
    num_predictors: int
    num_rollouts: int
    predictor_names: List[str]
    weights: np.ndarray                   # (K, M)
    bcvf_total: np.ndarray                # (K,) diagnostic
    ema_mean: Optional[np.ndarray]        # (M,) or None
    ema_std: Optional[np.ndarray]         # (M,) or None
    deadband_active_count: int
    is_excluded: Optional[np.ndarray]     # (M,) bool or None
```

ROS 2 `.msg` sketch:
```
# TrustDistribution.msg
std_msgs/Header header
string[] predictor_names
uint16 num_rollouts
float64[] weights             # flattened (K * M) row-major
float64[] bcvf_total          # length K
float64[] ema_mean            # length M or empty
float64[] ema_std             # length M or empty
uint32 deadband_active_count
bool[] is_excluded            # length M or empty
```

## Node architecture (`BCVFTrustNode`)

Standard rclpy Node:

```python
# sketch — real implementation in ros2_shim.py when rclpy lands
class BCVFTrustNode(rclpy.node.Node):
    def __init__(self):
        super().__init__("bcvf_trust")
        self._bridge = BCVFTrustBridge(
            bcvf_config=self._load_bcvf_config_from_params(),
        )
        self._sub = self.create_subscription(
            PredictedTrajectories, "/predicted_trajectories",
            self._on_predicted, qos_profile=10,
        )
        self._pub = self.create_publisher(
            TrustDistribution, "/trust_distribution", qos_profile=10,
        )

    def _on_predicted(self, msg):
        trajectories = _unflatten(msg)           # (K, M, H, 3)
        result = self._bridge.compute(trajectories)
        out = _build_trust_msg(result, msg.header)
        self._pub.publish(out)
```

All the numerical work (EMA centering, deadband, exclusion, softmin)
lives in `BCVFTrustBridge.compute` — a pure-Python wrapper around
`TrustWeightComputer`. The shim only does ROS serialization.

## Launch file contracts

Two example launch files ship as part of the §6.4 execution work:

### `launch/nav2_with_bcvf.launch.py`

Nav2-compatible launch that drops BCVFTrustNode between the
`behavior_planner` and the `smac_planner` plugin. Example
subscription graph:

```
/predicted_trajectories  ←  nav2 behavior_planner (multi-hypothesis)
/trust_distribution      →  nav2 smac_planner (as a weighting input)
```

### `launch/autoware_with_bcvf.launch.py`

Autoware.universe-compatible launch wiring into the
`motion_planner` module. Autoware already runs multi-predictor
perception; the BCVF node sits between
`/perception/object_recognition/objects` (aggregated) and
`/planning/trajectory`.

Both launch files are example-only — a real integrator will adapt
them to their exact Nav2 / Autoware version. The contract is the
message shapes, not the specific topic names.

## Nav2 `smac_planner` / MoveIt `OMPL` adapter plugins

Beyond the standalone node, the design doc calls for drop-in adapter
plugins for the two most common planner stacks:

- **Nav2 `smac_planner`** — a `CriticPlugin` (part of Nav2's
  `dwb_critics` plugin system) that consumes `/trust_distribution`
  and weights the rollout-cost evaluation accordingly. The critic
  plugin API is stable across Humble → Jazzy.
- **MoveIt `OMPL`** — a `PathSimplifier` variant that consumes
  trust weights to bias the path smoothing away from low-trust
  predictor regions. More speculative than the Nav2 integration;
  flagged as V2+ if the Nav2 path proves easier.

## Acceptance

Per design doc §6.4:

- A pre-recorded rosbag plays through the integrated stack with
  per-step BCVF trace logged end-to-end.
- At least one external integrator (design partner or OSS community
  contributor) confirms the package installs and runs against their
  stack.

## Deliverables in this session vs future work

### This session (framework-agnostic scaffold)

Ships in `169dcd5`-range:

- `symbolu_robotics/bcvf_ros2/__init__.py` — package
- `symbolu_robotics/bcvf_ros2/messages.py` — Python dataclasses
  for `PredictedTrajectories` and `TrustDistribution`
- `symbolu_robotics/bcvf_ros2/core.py` — pure-Python
  `BCVFTrustBridge` that does all the numerical work. Testable
  without `rclpy`.
- `symbolu_robotics/bcvf_ros2/ros2_shim.py` — thin `rclpy` wrapper.
  Imports `rclpy` lazily so the file can be imported from a
  test environment without ROS 2 installed.
- `symbolu_robotics/bcvf_autonomous/tests/test_bcvf_ros2_core.py`
  — tests for the pure-Python bridge.

### Future work (gated on ROS 2 environment)

- `.msg` file definitions + `CMakeLists.txt` + `package.xml` for
  `colcon build` (~3 days)
- `BCVFTrustNode` rclpy implementation against real ROS 2 DDS
  middleware (~1 week)
- Nav2 `CriticPlugin` implementation (~1 week)
- Example launch files + rosbag recording + QA (~2-3 days)
- External integrator pilot (OSS contributor or design-partner
  driver-in-the-loop — ~2 weeks)

**Total:** ~3–4 weeks after the scaffold shipped here, matching the
design-doc estimate.

## Risks

- **ROS 2 Python API drift.** rclpy API has been stable across
  Humble → Iron → Jazzy but could break in later distributions.
  Mitigation: test against at least Humble and Jazzy; document
  minimum supported version.
- **Message-type compatibility with Nav2 / Autoware.** Our custom
  `PredictedTrajectories` message is new — integrators would need
  to either publish it or write a small bridge from their existing
  multi-predictor output. Mitigation: document the bridge pattern
  and ship a reference converter from standard
  `nav_msgs/Path[]` arrays.
- **DDS QoS mismatch.** BCVF wants `reliable`, `keep_last` QoS; some
  stacks default to `best_effort`. Mitigation: expose QoS as a
  node parameter, document recommended setting.

## What §6.4 is NOT

- **Not a full Nav2 / MoveIt / Autoware plugin ecosystem.** The
  first pilot is "wire BCVFTrustNode between an existing multi-
  predictor output and a planner." Deeper integrations (native
  `CriticPlugin`, `PathSimplifier`) are follow-on work.
- **Not a drop-in for every robotics platform.** ROS 2 is the
  largest gap; ROS 1 (deprecated, but in production at many sites)
  and custom non-ROS stacks remain out of scope.
- **Not a real-time guarantee on any specific compute substrate.**
  The §6.5 latency benchmark numbers apply; ROS 2 middleware adds
  more latency that a production integrator must characterize on
  their hardware.

## Next step after this session

Assign an engineer to the future-work list above. The pure-Python
core and tests shipped here mean that work is pipeline, not
numerical-risk.
