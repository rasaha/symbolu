# Symbolu Robotics & Autonomous AI Tier Design

**Version**: 1.0.0
**Date**: 2025-12-24
**Status**: Design Proposal
**Parent**: Symbolu Enterprise Architecture (v2.7+)

---

## 1. Executive Summary

This document outlines the design for adapting the Symbolu ontological engine for autonomous AI systems (robotics, drones, autonomous vehicles). The architecture leverages the existing 12D ontological backbone while adding embodiment-specific modules.

### Key Principle
**Ontology-First, Compute-Light**: Use the deterministic 12D STL for real-time control loops, reserving expensive inference for deliberative planning only.

---

## 2. Architecture Overview

### 2.1 Enterprise vs Robotics Tier Comparison

```
ENTERPRISE TIERS                      ROBOTICS TIERS
┌─────────────────────┐               ┌─────────────────────┐
│ Tier 1: Search      │               │ Tier R1: Reflexive  │
│ (STL only, ~100μs)  │      →        │ (STL only, ~100μs)  │
├─────────────────────┤               ├─────────────────────┤
│ Tier 2: Chat        │               │ Tier R2: Reactive   │
│ (STL + 7B, ~500ms)  │      →        │ (STL + Edge, ~10ms) │
├─────────────────────┤               ├─────────────────────┤
│ Tier 3: Cascade     │               │ Tier R3: Deliberative│
│ (Full, ~1s)         │      →        │ (Full + Planning)   │
└─────────────────────┘               └─────────────────────┘
```

### 2.2 Robotics Control Loop Integration

```
                    ┌──────────────────────────────────────────┐
                    │           SYMBOLU ROBOTICS CORE          │
                    ├──────────────────────────────────────────┤
   Sensors ────────►│  12D Encoder  ──► Mirror Balance ──────┬─┼──► Actuators
                    │       ↑               ↑                 │ │
                    │       │          ┌────┴────┐            │ │
                    │   Chitta-Vṛtti   │ Safety  │            │ │
                    │   (p_v[v])       │ Guard   │            │ │
                    │       ↑          └────┬────┘            │ │
                    │       │               │                 │ │
                    │  ┌────┴───────────────┴────┐            │ │
                    │  │    State Estimator      │            │ │
                    │  │    (v2.7 EMA)           │            │ │
                    │  └─────────────────────────┘            │ │
                    └──────────────────────────────────────────┘
                                      ↑
                              ┌───────┴───────┐
                              │ Tier R3 only: │
                              │ Task Planner  │
                              │ (Edge/Cloud)  │
                              └───────────────┘
```

---

## 3. Directory Structure

### 3.1 Proposed Repository Layout

```
symbolu-robotics/
├── README.md
├── pyproject.toml
├── setup.py
│
├── symbolu_robotics/
│   ├── __init__.py
│   │
│   ├── core/                      # COPIED from main (shared foundation)
│   │   ├── __init__.py
│   │   ├── ontology_12d.py        # ← symbolu/ontology/backbone/
│   │   ├── mirror_pairs_12d.py    # ← symbolu/resonance/mirror_pairs_12d.py
│   │   ├── phoneme_maps.py        # ← symbolu/resonance/phoneme_maps.py
│   │   ├── chitta_vritti.py       # ← symbolu/chitta_vritti/
│   │   ├── v27_state.py           # ← symbolu/guna_modulation/v27_config.py
│   │   └── referent_classes.py    # ← symbolu/name_resonance/referent_classes.py
│   │
│   ├── encoders/                  # NEW: Sensor → 12D encoding
│   │   ├── __init__.py
│   │   ├── base_encoder.py        # Abstract base for all encoders
│   │   ├── vision_encoder.py      # Camera/LIDAR → 12D
│   │   ├── tactile_encoder.py     # Touch sensors → 12D
│   │   ├── proprioception.py      # Joint states → 12D
│   │   ├── audio_encoder.py       # Microphone → 12D
│   │   └── fusion_encoder.py      # Multi-modal fusion → 12D
│   │
│   ├── decoders/                  # NEW: 12D → Actuator commands
│   │   ├── __init__.py
│   │   ├── base_decoder.py        # Abstract base
│   │   ├── motor_decoder.py       # 12D → Joint torques/velocities
│   │   ├── gripper_decoder.py     # 12D → Grasp commands
│   │   ├── locomotion_decoder.py  # 12D → Gait parameters
│   │   └── speech_decoder.py      # 12D → Voice synthesis
│   │
│   ├── safety/                    # NEW: Real-time safety layer
│   │   ├── __init__.py
│   │   ├── constraint_monitor.py  # O12_ABSOLVING enforcement
│   │   ├── collision_guard.py     # Emergency stop logic
│   │   ├── energy_bounds.py       # Actuator limits
│   │   └── human_proximity.py     # Human-robot safety
│   │
│   ├── tiers/                     # Adapted from symbolu/engine/
│   │   ├── __init__.py
│   │   ├── base.py                # ← symbolu/engine/base.py (adapted)
│   │   ├── reflexive.py           # Tier R1: STL-only, <1ms
│   │   ├── reactive.py            # Tier R2: STL + edge model
│   │   ├── deliberative.py        # Tier R3: Full planning
│   │   └── factory.py             # Tier selection logic
│   │
│   ├── planning/                  # NEW: Task/motion planning
│   │   ├── __init__.py
│   │   ├── goal_stack.py          # O8_PURPOSE hierarchy
│   │   ├── action_primitives.py   # O3_EXECUTION library
│   │   ├── world_model.py         # O9_WITNESSES state
│   │   └── path_planner.py        # Spatial planning
│   │
│   ├── state/                     # Adapted from v2.7 state management
│   │   ├── __init__.py
│   │   ├── robot_state.py         # Full robot state vector
│   │   ├── ema_tracker.py         # ← v2.7 EMA adaptation
│   │   ├── localization.py        # O2_IDENTITY: Where am I?
│   │   └── world_state.py         # Environment representation
│   │
│   ├── comms/                     # NEW: Multi-agent coordination
│   │   ├── __init__.py
│   │   ├── swarm_protocol.py      # O10_UNIFYING: Multi-robot
│   │   ├── human_interface.py     # Natural language commands
│   │   └── ros_bridge.py          # ROS2 integration (optional)
│   │
│   └── adapters/                  # Hardware abstraction
│       ├── __init__.py
│       ├── base_adapter.py
│       ├── ros2_adapter.py        # ROS2 integration
│       ├── isaac_adapter.py       # NVIDIA Isaac Sim
│       ├── mujoco_adapter.py      # MuJoCo simulation
│       └── serial_adapter.py      # Direct microcontroller
│
├── configs/
│   ├── tier_r1_reflexive.yaml     # Reflexive tier config
│   ├── tier_r2_reactive.yaml      # Reactive tier config
│   ├── tier_r3_deliberative.yaml  # Deliberative tier config
│   ├── robots/
│   │   ├── manipulator_6dof.yaml
│   │   ├── mobile_base.yaml
│   │   ├── quadruped.yaml
│   │   └── humanoid.yaml
│   └── safety/
│       ├── industrial.yaml        # ISO 10218 compliance
│       └── collaborative.yaml     # ISO/TS 15066 compliance
│
├── examples/
│   ├── pick_and_place.py
│   ├── navigation.py
│   ├── human_handover.py
│   └── swarm_coordination.py
│
├── tests/
│   ├── test_encoders.py
│   ├── test_decoders.py
│   ├── test_safety.py
│   ├── test_tiers.py
│   └── test_integration.py
│
└── docs/
    ├── ARCHITECTURE.md
    ├── ENCODER_GUIDE.md
    ├── SAFETY_REQUIREMENTS.md
    └── HARDWARE_ADAPTERS.md
```

---

## 4. Module Classification

### 4.1 Modules to COPY (Core Ontological Engine)

These modules form the shared foundation and should be copied from the main branch:

| Source Module | Target Location | Purpose |
|---------------|-----------------|---------|
| `symbolu/ontology/backbone/` | `core/ontology_12d.py` | 12D layer definitions |
| `symbolu/resonance/mirror_pairs_12d.py` | `core/mirror_pairs_12d.py` | Astrological mirror pairs |
| `symbolu/resonance/phoneme_maps.py` | `core/phoneme_maps.py` | Phoneme → layer mapping |
| `symbolu/chitta_vritti/` | `core/chitta_vritti.py` | p_v[v] cognitive modes |
| `symbolu/guna_modulation/v27_config.py` | `core/v27_state.py` | EMA state evolution |
| `symbolu/name_resonance/referent_classes.py` | `core/referent_classes.py` | Semantic polarity detection |
| `symbolu/hybrid/router.py` (partial) | `tiers/base.py` | Core routing logic |
| `symbolu/engine/base.py` | `tiers/base.py` | Tier base class |

### 4.2 Modules to ADAPT (Modified for Robotics)

| Source Module | Adaptation Required |
|---------------|---------------------|
| `symbolu/engine/factory.py` | Add hardware adapters, tier R1/R2/R3 selection |
| `symbolu/presentation/signal_bridge.py` | Replace text output with actuator commands |
| `symbolu/hybrid/router.py` | Add sensor routing, replace query types |
| `symbolu/safety/` | Add real-time constraints, collision detection |

### 4.3 Modules to BUILD NEW

| New Module | Purpose | Priority |
|------------|---------|----------|
| `encoders/vision_encoder.py` | Camera/LIDAR → 12D | P0 |
| `encoders/proprioception.py` | Joint states → 12D | P0 |
| `decoders/motor_decoder.py` | 12D → Actuator commands | P0 |
| `safety/constraint_monitor.py` | O12_ABSOLVING enforcement | P0 |
| `safety/collision_guard.py` | Emergency stop | P0 |
| `tiers/reflexive.py` | Tier R1 implementation | P0 |
| `tiers/reactive.py` | Tier R2 implementation | P1 |
| `planning/action_primitives.py` | Atomic actions | P1 |
| `adapters/ros2_adapter.py` | ROS2 integration | P1 |
| `planning/goal_stack.py` | Task hierarchy | P2 |
| `comms/swarm_protocol.py` | Multi-robot | P2 |
| `tiers/deliberative.py` | Tier R3 implementation | P2 |

---

## 5. 12D Layer Mapping for Robotics

### 5.1 Layer Semantics

| Layer | Enterprise Meaning | Robotics Meaning | Data Type |
|-------|-------------------|------------------|-----------|
| **O1_POTENTIAL** | Dormant intent | Sensor readiness | float [0,1] |
| **O2_IDENTITY** | Self-reference | Localization (x,y,θ) | Pose |
| **O3_EXECUTION** | Action commands | Motor commands | Torques/Vel |
| **O4_STRUCTURE** | Syntax/form | Body schema/kinematics | JointConfig |
| **O5_COGNITION** | Perception | Perception processing | Features |
| **O6_AGENCY** | Autonomy level | Control mode | Enum |
| **O7_REASONING** | Logic/planning | Path/task planning | Plan |
| **O8_PURPOSE** | Goal | Goal hierarchy | GoalStack |
| **O9_WITNESSES** | Context | World model | Scene |
| **O10_UNIFYING** | Integration | Multi-agent coord | SwarmState |
| **O11_INTEGRATION** | Fusion | Sensor fusion | FusedPercept |
| **O12_ABSOLVING** | Constraints | Safety constraints | Bounds |

### 5.2 Mirror Pair Robotics Interpretation

```
O1_POTENTIAL   ↔  O7_REASONING      Sensor readiness ↔ Planning
O2_IDENTITY    ↔  O8_PURPOSE        Where am I? ↔ Where to go?
O3_EXECUTION   ↔  O9_WITNESSES      Action ↔ Observation
O4_STRUCTURE   ↔  O10_UNIFYING      Body ↔ World
O5_COGNITION   ↔  O11_INTEGRATION   Perception ↔ Fusion
O6_AGENCY      ↔  O12_ABSOLVING     Autonomy ↔ Safety
```

### 5.3 Control Loop Signal Flow

```
Sensors → [O1: Readiness] → [O5: Perception] → [O11: Fusion]
                                                     ↓
                                              [O7: Planning]
                                                     ↓
          [O3: Execution] ← [O6: Agency] ← [O8: Purpose]
                ↓
          [O12: Safety Check] → Actuators (or E-STOP)
```

---

## 6. Tier Architecture Details

### 6.1 Tier R1: Reflexive (Safety-Critical, <1ms)

**Purpose**: Immediate reactive behaviors, safety reflexes

```python
class ReflexiveTier:
    """
    Tier R1: Sub-millisecond reflexive control
    - Runs on microcontroller (ARM Cortex-M, ESP32)
    - No learning, pure deterministic
    - Always active as safety layer
    """

    def __init__(self):
        self.encoder = LightweightEncoder()  # Minimal 12D
        self.safety = CollisionGuard()
        self.reflexes = ReflexLibrary()

    def step(self, sensor_data: SensorFrame) -> ActuatorCommand:
        # O1: Readiness check
        if not self.safety.clear(sensor_data):
            return ActuatorCommand.EMERGENCY_STOP

        # O5 → O3: Direct perception-to-action
        layer_12d = self.encoder.encode(sensor_data)
        dominant = argmax(layer_12d[0:6])  # Lower layers only

        # O12: Safety constraint application
        raw_cmd = self.reflexes.lookup(dominant)
        safe_cmd = self.safety.constrain(raw_cmd)

        return safe_cmd

    # Timing budget: 100μs encoding + 50μs lookup + 50μs safety = 200μs
```

**Modules Used**:
- `core/ontology_12d.py` (lightweight subset)
- `encoders/base_encoder.py`
- `safety/collision_guard.py`
- `safety/constraint_monitor.py`

### 6.2 Tier R2: Reactive (Behavioral, <10ms)

**Purpose**: Reactive behaviors, local planning, manipulation

```python
class ReactiveTier:
    """
    Tier R2: Reactive behavioral control
    - Runs on edge compute (Jetson, RPi5)
    - EMA state tracking (v2.7)
    - Mirror pair balancing
    """

    def __init__(self):
        self.encoder = FusionEncoder()       # Full 12D
        self.mirror = MirrorBalance12D()
        self.state = EMATracker(alpha=0.1)   # v2.7
        self.behaviors = BehaviorLibrary()
        self.safety = SafetyLayer()

    def step(self, sensor_data: SensorFrame) -> ActuatorCommand:
        # O5 + O11: Perception and fusion
        layer_12d = self.encoder.encode(sensor_data)

        # v2.7 EMA state update
        layer_12d = self.state.update(layer_12d)

        # Mirror pair balancing (O1↔O7, O3↔O9, etc.)
        balanced = self.mirror.propagate(layer_12d)

        # O6: Agency check (autonomy level)
        if balanced[5] < 0.3:  # Low agency
            return self.await_command()

        # Behavior selection based on dominant layers
        behavior = self.behaviors.select(balanced)
        raw_cmd = behavior.compute(balanced, sensor_data)

        # O12: Safety constraints
        return self.safety.constrain(raw_cmd)

    # Timing: 1ms encoding + 2ms balance + 3ms behavior + 1ms safety = 7ms
```

**Modules Used**:
- `core/` (full suite)
- `encoders/fusion_encoder.py`
- `state/ema_tracker.py`
- `decoders/motor_decoder.py`
- `safety/` (full suite)

### 6.3 Tier R3: Deliberative (Planning, <100ms + async)

**Purpose**: Task planning, complex manipulation, human interaction

```python
class DeliberativeTier:
    """
    Tier R3: Deliberative planning and reasoning
    - Runs on edge GPU or cloud
    - Full Chitta-Vṛtti analysis (v2.8)
    - Task planning with goal hierarchy
    """

    def __init__(self):
        self.encoder = FusionEncoder()
        self.vritti = ChittaVrittiAnalyzer()  # v2.8
        self.planner = TaskPlanner()
        self.world_model = WorldModel()
        self.nl_interface = NaturalLanguageInterface()

    def step(self, sensor_data: SensorFrame,
             command: Optional[str] = None) -> Plan:
        # O5 + O11: Full perception
        layer_12d = self.encoder.encode(sensor_data)

        # v2.8: Cognitive mode analysis
        p_v = self.vritti.compute(layer_12d)

        # O9: Update world model
        self.world_model.update(layer_12d, sensor_data)

        # O8: Goal processing
        if command:
            goal = self.nl_interface.parse(command)
            self.planner.push_goal(goal)

        # O7: Planning
        plan = self.planner.plan(
            current_state=layer_12d,
            world=self.world_model,
            cognitive_mode=p_v
        )

        return plan  # Executed by R2/R1 tiers
```

**Modules Used**:
- All `core/` modules
- All `encoders/` modules
- `planning/` (full suite)
- `comms/human_interface.py`
- Optional: Cloud LLM for complex NL understanding

---

## 7. Sensor Encoding Specification

### 7.1 Vision Encoder

```python
class VisionEncoder(BaseEncoder):
    """
    Camera/LIDAR → 12D encoding

    Mapping:
    - Edges/shapes → O4_STRUCTURE
    - Motion vectors → O3_EXECUTION
    - Object recognition → O5_COGNITION
    - Spatial layout → O9_WITNESSES
    - Depth discontinuities → O12_ABSOLVING (obstacles)
    """

    def encode(self, frame: np.ndarray) -> np.ndarray:
        # Lightweight feature extraction (no CNN needed)
        edges = sobel_filter(frame)
        motion = optical_flow(frame, self.prev_frame)
        depth = self.depth_estimator(frame)  # or direct LIDAR

        layer_12d = np.zeros(12)
        layer_12d[3] = edge_density(edges)           # O4_STRUCTURE
        layer_12d[2] = motion_magnitude(motion)       # O3_EXECUTION
        layer_12d[4] = object_salience(frame)         # O5_COGNITION
        layer_12d[8] = spatial_entropy(depth)         # O9_WITNESSES
        layer_12d[11] = obstacle_proximity(depth)     # O12_ABSOLVING

        return normalize(layer_12d)
```

### 7.2 Proprioception Encoder

```python
class ProprioceptionEncoder(BaseEncoder):
    """
    Joint states → 12D encoding

    Mapping:
    - Joint positions → O4_STRUCTURE (body schema)
    - Joint velocities → O3_EXECUTION (motion state)
    - Joint torques → O6_AGENCY (effort level)
    - End-effector pose → O2_IDENTITY (self-localization)
    """

    def encode(self, joints: JointState) -> np.ndarray:
        layer_12d = np.zeros(12)
        layer_12d[3] = pose_deviation(joints.positions, self.home)
        layer_12d[2] = velocity_norm(joints.velocities)
        layer_12d[5] = torque_norm(joints.torques)
        layer_12d[1] = end_effector_pose(joints)

        return normalize(layer_12d)
```

---

## 8. Safety Architecture

### 8.1 Safety Layer Hierarchy

```
┌────────────────────────────────────────────────────────┐
│ Layer 0: Hardware E-STOP (always available)            │
├────────────────────────────────────────────────────────┤
│ Layer 1: Tier R1 Reflexive Safety (collision guard)    │
│          - Latency: <1ms                               │
│          - Cannot be overridden by software            │
├────────────────────────────────────────────────────────┤
│ Layer 2: Tier R2 Constraint Monitor (O12_ABSOLVING)    │
│          - Joint limits, velocity limits               │
│          - Human proximity scaling                     │
├────────────────────────────────────────────────────────┤
│ Layer 3: Tier R3 Safety Planning                       │
│          - Predictive collision avoidance              │
│          - Task-level safety constraints               │
└────────────────────────────────────────────────────────┘
```

### 8.2 O12_ABSOLVING Implementation

```python
class ConstraintMonitor:
    """
    O12_ABSOLVING: Safety constraint enforcement

    Maps directly to the ontological layer that
    "absolves" actions by ensuring they're safe.
    """

    def __init__(self, config: SafetyConfig):
        self.joint_limits = config.joint_limits
        self.velocity_limits = config.velocity_limits
        self.human_distance_threshold = config.human_distance

    def constrain(self, cmd: ActuatorCommand,
                  layer_12d: np.ndarray) -> ActuatorCommand:

        # O12 signal indicates constraint tightness
        constraint_level = layer_12d[11]

        # Scale limits by constraint level
        effective_vel_limit = self.velocity_limits * (1.0 - constraint_level)

        # Apply constraints
        cmd = self.clip_velocity(cmd, effective_vel_limit)
        cmd = self.clip_position(cmd, self.joint_limits)

        # Human proximity scaling (if detected)
        if constraint_level > 0.8:
            cmd = self.slow_motion_mode(cmd)

        return cmd
```

---

## 9. Integration Patterns

### 9.1 ROS2 Bridge

```python
class ROS2Adapter:
    """
    Bridge between Symbolu Robotics and ROS2 ecosystem
    """

    def __init__(self, node_name: str = "symbolu_robotics"):
        rclpy.init()
        self.node = rclpy.create_node(node_name)

        # Subscribers (sensors → 12D)
        self.image_sub = self.node.create_subscription(
            Image, '/camera/image', self.on_image, 10)
        self.joint_sub = self.node.create_subscription(
            JointState, '/joint_states', self.on_joints, 10)

        # Publishers (12D → actuators)
        self.cmd_pub = self.node.create_publisher(
            JointTrajectory, '/joint_trajectory', 10)

        # Symbolu tiers
        self.tier_r1 = ReflexiveTier()
        self.tier_r2 = ReactiveTier()

    def spin(self):
        while rclpy.ok():
            rclpy.spin_once(self.node)

            # Tier R1 runs at 1kHz
            cmd = self.tier_r1.step(self.current_sensors)
            self.cmd_pub.publish(cmd)
```

### 9.2 Simulation Adapter (MuJoCo)

```python
class MuJoCoAdapter:
    """
    Integration with MuJoCo physics simulation
    """

    def __init__(self, model_path: str):
        self.model = mujoco.MjModel.from_xml_path(model_path)
        self.data = mujoco.MjData(self.model)
        self.tier_r2 = ReactiveTier()

    def step(self):
        # Extract sensor data
        sensors = SensorFrame(
            joints=self.data.qpos,
            velocities=self.data.qvel,
            contacts=self.data.contact
        )

        # Get command from Symbolu
        cmd = self.tier_r2.step(sensors)

        # Apply to simulation
        self.data.ctrl[:] = cmd.torques
        mujoco.mj_step(self.model, self.data)
```

---

## 10. Performance Requirements

### 10.1 Latency Budgets

| Tier | Target Latency | Hard Deadline | Platform |
|------|----------------|---------------|----------|
| R1 Reflexive | 200μs | 1ms | Microcontroller |
| R2 Reactive | 5ms | 10ms | Edge (Jetson/RPi5) |
| R3 Deliberative | 50ms | 100ms | Edge GPU |
| R3 + Cloud | 200ms | 500ms | Cloud LLM |

### 10.2 Memory Requirements

| Tier | RAM | Storage | Notes |
|------|-----|---------|-------|
| R1 | 64KB | 256KB | Fits on STM32 |
| R2 | 512MB | 1GB | Raspberry Pi 5 |
| R3 | 4GB | 8GB | Jetson Orin Nano |

---

## 11. Development Roadmap

### Phase 1: Core (P0) - Weeks 1-4
- [ ] Set up `symbolu-robotics` repository
- [ ] Copy core modules from main branch
- [ ] Implement `ProprioceptionEncoder`
- [ ] Implement `MotorDecoder`
- [ ] Implement `ReflexiveTier`
- [ ] Implement `CollisionGuard`
- [ ] Basic MuJoCo integration test

### Phase 2: Reactive (P1) - Weeks 5-8
- [ ] Implement `VisionEncoder`
- [ ] Implement `FusionEncoder`
- [ ] Implement `ReactiveTier`
- [ ] Add v2.7 EMA state tracking
- [ ] ROS2 bridge
- [ ] Real hardware test (manipulator)

### Phase 3: Deliberative (P2) - Weeks 9-12
- [ ] Implement `DeliberativeTier`
- [ ] Task planner integration
- [ ] Natural language interface
- [ ] Multi-robot coordination
- [ ] Full demo: pick-and-place with voice commands

---

## 12. Testing Strategy

### 12.1 Unit Tests

```python
def test_proprioception_encoder():
    encoder = ProprioceptionEncoder()
    joints = JointState(positions=[0.0] * 6)
    layer_12d = encoder.encode(joints)

    assert layer_12d.shape == (12,)
    assert np.all(layer_12d >= 0.0)
    assert np.all(layer_12d <= 1.0)
    assert layer_12d[3] < 0.1  # At home, low structure deviation

def test_safety_constraint():
    monitor = ConstraintMonitor(SafetyConfig.COLLABORATIVE)
    dangerous_cmd = ActuatorCommand(velocities=[10.0] * 6)  # Too fast

    layer_12d = np.zeros(12)
    layer_12d[11] = 0.9  # High constraint (human nearby)

    safe_cmd = monitor.constrain(dangerous_cmd, layer_12d)
    assert np.all(safe_cmd.velocities < 1.0)  # Slowed down
```

### 12.2 Integration Tests

```python
def test_reflexive_tier_latency():
    tier = ReflexiveTier()
    sensor_data = generate_random_sensors()

    start = time.perf_counter_ns()
    cmd = tier.step(sensor_data)
    elapsed_us = (time.perf_counter_ns() - start) / 1000

    assert elapsed_us < 1000  # <1ms hard deadline
```

---

## 13. Open Questions

1. **Shared Core Maintenance**: How to keep `core/` in sync with main branch?
   - Option A: Git submodule
   - Option B: Periodic copy with version tracking
   - Option C: Publish `symbolu-core` as separate package

2. **Real-time Guarantees**: Should Tier R1 use real-time OS (RTOS)?
   - MicroPython vs C for microcontroller deployment

3. **Sensor Abstraction**: How generic should encoders be?
   - Per-sensor-type vs per-robot-type

4. **Cloud Fallback**: When should Tier R3 call cloud?
   - Complex NL understanding
   - Novel object recognition
   - Task planning for unseen goals

---

## 14. References

- Symbolu Enterprise Architecture: `/docs/SYMBOLU_ENGINE_ARCHITECTURE.md`
- 12D Ontological Backbone: `/symbolu/ontology/backbone/`
- Mirror Pairs (Astrological): `/symbolu/resonance/mirror_pairs_12d.py`
- v2.7 State Evolution: `/symbolu/guna_modulation/v27_config.py`
- v2.8 Chitta-Vṛtti: `/symbolu/chitta_vritti/`
- Benchmark Results: `/docs/benchmarks/ENGINE_BENCHMARK_RESULTS.md`

---

**Document Status**: Design Proposal
**Next Steps**: Review with stakeholders, finalize Phase 1 scope
**Contact**: [Architecture Team]
