# Symbolu Robotics Module - Standalone Upgrade Requirements

**Date:** 2026-02-03
**Module Version:** 1.1.0
**Purpose:** Identify areas requiring upgrade BEFORE framework integration

---

## Executive Summary

The robotics module contains **45+ files with incomplete implementations** that must be addressed before integrating Phase-Quad, CTM+, PCAM, or Sentinel frameworks. These gaps are categorized by severity and impact.

| Category | Files Affected | Severity | Effort |
|----------|----------------|----------|--------|
| **Neural Network Training** | 3 | CRITICAL | HIGH |
| **LLM Provider** | 1 | CRITICAL | MEDIUM |
| **Hardware Adapters** | 4 | HIGH | HIGH |
| **Planning Algorithms** | 4 | HIGH | MEDIUM |
| **Forward Kinematics** | 1 | HIGH | MEDIUM |
| **Error Handling** | 8+ | MEDIUM | LOW |
| **Persistence (Save/Load)** | 4 | MEDIUM | LOW |

---

## 1. CRITICAL: Neural Network Training Infrastructure

### Current State

The learning subsystem has **skeleton implementations** that cannot train actual neural networks:

#### 1.1 Skill Learning (`learning/skill_learning.py`)

**Lines 342-379: `train_step()` is a skeleton**
```python
def train_step(self) -> Dict[str, float]:
    """
    Skeleton: Returns placeholder metrics.
    Actual implementation requires neural network framework.
    """
    # ... only returns status dict, no training
```

**Impact:** Cannot learn from robot experience. The reinforcement learning loop is non-functional.

**Lines 381-408: `get_action_modifier()` returns base action unchanged**
```python
# Placeholder: Would apply policy here
return base_action, confidence
```

**Impact:** Learned skills cannot modify robot behavior.

**Lines 410-417: `get_bcvf_modifier()` returns hardcoded ones**
```python
return np.ones(4)  # Placeholder for 4 action types
```

**Impact:** Cannot modulate BCVF action selection based on learned policies.

#### 1.2 Dynamics Model (`learning/dynamics_model.py`)

**Lines 152-161: Class marked as "Skeleton Implementation"**
- Only implements basic linear regression
- Neural network ensemble requires external framework
- Cannot provide reliable predictions for MPC planning

**Lines 217-271: `train()` implements only linear regression**
```python
# Skeleton: Implements simple linear regression
# Complex models (neural networks) require external framework
```

**Impact:** Model predictive control (MPC) planning relies on inaccurate linear predictions.

### Required Upgrade

| Task | Description | Dependency |
|------|-------------|------------|
| Add PyTorch/JAX integration | Implement actual NN training in `train_step()` | PyTorch >= 2.0 or JAX |
| Policy network architecture | Define and initialize policy/value networks | PyTorch/JAX |
| Ensemble dynamics model | Implement neural network ensemble for uncertainty | PyTorch/JAX |
| GPU acceleration | Add CUDA support for training | CUDA 11.8+ |

**Estimated Effort:** 2-3 weeks

---

## 2. CRITICAL: LLM Provider Implementation

### Current State

**File:** `comms/human_interface.py`

**Lines 264-318: OpenAILLMProvider is skeleton-only**
```python
class OpenAILLMProvider(LLMProvider):
    """
    Skeleton: Defines interface, actual API calls require external setup.
    """

    def parse_command(self, text, context):
        # Skeleton: Would call OpenAI API here
        return self._mock.parse_command(text, context)  # Falls back to regex!
```

**Impact:**
- Natural language commands fall back to regex parsing
- Complex commands fail or misinterpret
- No actual LLM reasoning available

### Required Upgrade

| Task | Description | Priority |
|------|-------------|----------|
| Implement OpenAI API calls | Add actual `openai.ChatCompletion.create()` calls | P1 |
| Add streaming support | For responsive human interaction | P2 |
| Add local LLM option | Ollama/vLLM for edge deployment | P2 |
| Error handling | Rate limits, timeouts, API errors | P1 |

**Estimated Effort:** 1 week

**Note:** This is a prerequisite for Phase-Quad integration - the skeleton must be functional before Phase-Quad can enhance it.

---

## 3. HIGH: Hardware Adapter Mock Fallbacks

### Current State

All hardware adapters fall back to mock implementations when actual hardware is unavailable:

#### 3.1 Isaac Sim Adapter (`adapters/isaac_adapter.py`)

**Lines 72-77:**
```python
except ImportError:
    print("Isaac Sim not available. Running in simulation mode.")
    self._init_mock()  # Falls back to simple numpy mock
```

**Mock implementation (lines 83-88):**
- `_mock_joints = np.zeros(6)`
- `_mock_velocities = np.zeros(6)`
- Simple Euler integration, no physics

**Impact:** Cannot run realistic simulation without Isaac Sim.

#### 3.2 MuJoCo Adapter (`adapters/mujoco_adapter.py`)

**Line 193:** Empty `pass` in exception handler
- No graceful degradation
- Errors silently ignored

#### 3.3 ROS2 Adapter (`adapters/ros2_adapter.py`)

**Line 92:** Placeholder comment
```python
# Quaternion to Euler would go here
```

**Impact:** Orientation handling incomplete.

#### 3.4 Serial Adapter (`adapters/serial_adapter.py`)

**Lines 54-168:** Multiple stub methods returning `False` or empty lists
- `is_connected()` → stub
- `get_firmware_version()` → empty
- `read_digital_inputs()` → empty list

**Impact:** Cannot interface with microcontroller-based robots.

### Required Upgrade

| Task | Description | Priority |
|------|-------------|----------|
| Improve mock physics | Add basic rigid body dynamics to mock mode | P2 |
| Complete ROS2 orientation | Implement quaternion-to-Euler conversion | P1 |
| Serial protocol implementation | Implement actual serial communication | P1 |
| Graceful degradation | Add proper error handling, not empty `pass` | P1 |

**Estimated Effort:** 2 weeks

---

## 4. HIGH: Planning Algorithm Completeness

### Current State

#### 4.1 MPC Planner (`planning/mpc_planner.py`)

**Lines 240-243: Marked as "Skeleton Implementation"**

**Line 303:**
```python
# Simple optimization loop (gradient-free for skeleton)
# Production version should use CasADi/IPOPT
```

**Line 338:**
```python
# Simple perturbation (would use gradient in production)
```

**Impact:** MPC uses random perturbation instead of gradient-based optimization. Suboptimal trajectories.

#### 4.2 HTN Planner (`planning/htn_planner.py`)

**Lines 206-210: Marked as "Skeleton Implementation"**

**Multiple methods return `None`:**
- Lines 287, 301, 307, 316, 321, 334, 338, 341, 364, 472

**Impact:** Hierarchical task decomposition incomplete. Cannot handle complex multi-step tasks.

#### 4.3 Path Planner (`planning/path_planner.py`)

**Line 220:**
```python
return []  # No path found
```

**Impact:** Path planning fails silently with empty result.

#### 4.4 World Model (`planning/world_model.py`)

**Lines 175, 187-188:** Methods return `None` or `False`

**Line 209:**
```python
return 0.1  # Minimal awareness
```

**Impact:** World state tracking unreliable. Planning lacks environmental context.

### Required Upgrade

| Task | Description | Priority |
|------|-------------|----------|
| Integrate CasADi/IPOPT | Gradient-based MPC optimization | P1 |
| Complete HTN decomposition | Implement full task decomposition logic | P1 |
| A* / RRT* path planning | Replace empty fallback with actual pathfinding | P1 |
| World model persistence | Track objects and obstacles reliably | P2 |

**Estimated Effort:** 3 weeks

---

## 5. HIGH: Forward Kinematics Placeholder

### Current State

**File:** `safety/trajectory_validator.py`

**Lines 828-839:**
```python
def _default_fk(self, positions: np.ndarray) -> RobotPose:
    """Default forward kinematics (placeholder)."""
    # Simplified FK - in practice, this would be robot-specific
    if len(positions) >= 3:
        x = 0.5 * np.cos(positions[0]) * np.cos(positions[1])
        y = 0.5 * np.sin(positions[0]) * np.cos(positions[1])
        z = 0.3 + 0.5 * np.sin(positions[1])
    else:
        x, y, z = 0.0, 0.0, 0.3
    return RobotPose(x=x, y=y, z=z)
```

**Impact:**
- Safety validation uses incorrect end-effector positions
- Collision checking unreliable
- Trajectory validation compromised

### Required Upgrade

| Task | Description | Priority |
|------|-------------|----------|
| URDF/MJCF parser | Load robot description from standard formats | P1 |
| DH parameter support | Implement Denavit-Hartenberg kinematics | P1 |
| Robot-specific FK | Support for common robots (UR5, Franka, etc.) | P1 |
| Jacobian computation | For velocity/force mapping | P2 |

**Estimated Effort:** 2 weeks

---

## 6. MEDIUM: Persistence (Save/Load) Missing

### Current State

Multiple modules have empty `save()` and `load()` methods:

#### 6.1 Skill Learning (`learning/skill_learning.py`)

**Lines 419-427:**
```python
def save(self, path: str) -> None:
    # Placeholder: Would serialize skills
    pass

def load(self, path: str) -> None:
    # Placeholder: Would deserialize skills
    pass
```

#### 6.2 Dynamics Model (`learning/dynamics_model.py`)

**Lines 444-452:**
```python
def save(self, path: str) -> None:
    # Placeholder
    pass

def load(self, path: str) -> None:
    # Placeholder
    pass
```

**Impact:**
- Learned skills lost on restart
- Dynamics model must be retrained every session
- No transfer learning possible

### Required Upgrade

| Task | Description | Priority |
|------|-------------|----------|
| Implement pickle/torch.save | Basic serialization for weights | P2 |
| Add versioning | Handle model version compatibility | P3 |
| Cloud storage option | For multi-robot skill sharing | P3 |

**Estimated Effort:** 3-5 days

---

## 7. MEDIUM: Error Handling Gaps

### Current State

**8+ files** have empty `pass` statements in exception handlers:

| File | Line | Issue |
|------|------|-------|
| `comms/ros_bridge.py` | 106-107, 190, 199, 261 | Silent failure |
| `adapters/isaac_adapter.py` | 96 | Exception ignored |
| `adapters/mujoco_adapter.py` | 193 | Exception ignored |
| `recovery/watchdog.py` | 227 | Exception ignored |
| `recovery/fallback.py` | Multiple | Returns False/None |

**Example:**
```python
try:
    # ... operation
except:
    pass  # Error silently ignored!
```

**Impact:**
- Errors go undetected
- Debugging extremely difficult
- Safety hazards from silent failures

### Required Upgrade

| Task | Description | Priority |
|------|-------------|----------|
| Add logging | Log all exceptions with context | P1 |
| Graceful degradation | Define fallback behavior per exception type | P1 |
| Exception typing | Use specific exception types, not bare `except:` | P2 |
| Alerting | Notify operator of critical failures | P2 |

**Estimated Effort:** 1 week

---

## 8. MEDIUM: Safety Layer Hardcoding

### Current State

**File:** `safety/human_proximity.py`

**Lines 97-109:** Methods return hardcoded values
```python
def get_min_distance(self) -> float:
    return 0.5  # Hardcoded 0.5m

def get_slow_zone_radius(self) -> float:
    return 1.5  # Hardcoded 1.5m
```

**File:** `safety/collision_guard.py`

**Lines 64-173:** Multiple hardcoded boolean returns

**Impact:**
- Safety parameters not configurable
- Cannot adapt to different environments
- Not compliant with ISO 10218 / ISO 15066 variable safety zones

### Required Upgrade

| Task | Description | Priority |
|------|-------------|----------|
| Configurable safety zones | Load from config file | P1 |
| Dynamic safety adjustment | Based on speed, payload, human detection | P1 |
| ISO compliance | Implement ISO 10218-1/2 and ISO 15066 zones | P2 |

**Estimated Effort:** 1 week

---

## 9. Upgrade Dependency Graph

```
                    ┌─────────────────────────────────────┐
                    │  Phase 1: Core Infrastructure       │
                    │                                     │
                    │  1. Neural Network Framework        │
                    │     (PyTorch/JAX integration)       │
                    │                                     │
                    │  2. LLM Provider Implementation     │
                    │     (OpenAI API or local LLM)       │
                    └───────────────┬─────────────────────┘
                                    │
                    ┌───────────────▼─────────────────────┐
                    │  Phase 2: Planning & Control        │
                    │                                     │
                    │  3. MPC with CasADi/IPOPT          │
                    │                                     │
                    │  4. Forward Kinematics (URDF)      │
                    │                                     │
                    │  5. HTN Planner Completion         │
                    └───────────────┬─────────────────────┘
                                    │
                    ┌───────────────▼─────────────────────┐
                    │  Phase 3: Hardware & Safety         │
                    │                                     │
                    │  6. Hardware Adapter Completion     │
                    │                                     │
                    │  7. Safety Layer Configuration      │
                    │                                     │
                    │  8. Error Handling & Logging        │
                    └───────────────┬─────────────────────┘
                                    │
                    ┌───────────────▼─────────────────────┐
                    │  Phase 4: Persistence & Polish      │
                    │                                     │
                    │  9. Save/Load Implementation        │
                    │                                     │
                    │  10. Integration Testing            │
                    └─────────────────────────────────────┘
                                    │
                                    ▼
                    ┌─────────────────────────────────────┐
                    │  READY FOR FRAMEWORK INTEGRATION    │
                    │                                     │
                    │  - Phase-Quad LLM                   │
                    │  - CTM+                             │
                    │  - PCAM                             │
                    │  - Sentinel                         │
                    └─────────────────────────────────────┘
```

---

## 10. Prioritized Upgrade Roadmap

### Phase 1: Core Infrastructure (Weeks 1-3)

| # | Task | Files | Est. Days |
|---|------|-------|-----------|
| 1.1 | PyTorch/JAX integration framework | `learning/*.py` | 5 |
| 1.2 | Implement SkillLearner.train_step() | `skill_learning.py` | 3 |
| 1.3 | Implement DynamicsModel neural ensemble | `dynamics_model.py` | 4 |
| 1.4 | Implement OpenAI LLM provider | `human_interface.py` | 3 |
| 1.5 | Add local LLM option (Ollama) | `human_interface.py` | 2 |

### Phase 2: Planning & Control (Weeks 4-6)

| # | Task | Files | Est. Days |
|---|------|-------|-----------|
| 2.1 | Integrate CasADi for MPC | `mpc_planner.py` | 5 |
| 2.2 | Implement URDF parser | `new: urdf_parser.py` | 4 |
| 2.3 | Implement FK from URDF | `trajectory_validator.py` | 3 |
| 2.4 | Complete HTN decomposition | `htn_planner.py` | 4 |
| 2.5 | Implement A* path planning | `path_planner.py` | 2 |

### Phase 3: Hardware & Safety (Weeks 7-8)

| # | Task | Files | Est. Days |
|---|------|-------|-----------|
| 3.1 | ROS2 quaternion handling | `ros2_adapter.py` | 1 |
| 3.2 | Serial protocol implementation | `serial_adapter.py` | 3 |
| 3.3 | Configurable safety zones | `human_proximity.py`, `collision_guard.py` | 2 |
| 3.4 | Add logging throughout | All files with `pass` | 2 |
| 3.5 | Exception handling cleanup | 8+ files | 2 |

### Phase 4: Persistence & Testing (Week 9)

| # | Task | Files | Est. Days |
|---|------|-------|-----------|
| 4.1 | Implement save/load for skills | `skill_learning.py` | 1 |
| 4.2 | Implement save/load for dynamics | `dynamics_model.py` | 1 |
| 4.3 | Integration tests | `tests/*.py` | 3 |

---

## 11. Critical Path for Framework Integration

Before integrating each framework, these specific upgrades are **mandatory**:

### For Phase-Quad LLM Integration

| Prerequisite | Status | Notes |
|--------------|--------|-------|
| OpenAI/LLM provider working | ❌ SKELETON | Must implement API calls first |
| Error handling in `human_interface.py` | ❌ MISSING | Add timeout, rate limit handling |

### For CTM+ Integration

| Prerequisite | Status | Notes |
|--------------|--------|-------|
| ExperienceBuffer working | ✅ WORKING | Basic functionality exists |
| Persistence (save/load) | ❌ SKELETON | Need serialization for CTM+ tiers |

### For PCAM Integration

| Prerequisite | Status | Notes |
|--------------|--------|-------|
| SU-ViT attention layer | ✅ WORKING | Phase-locked attention exists |
| GPU support | ⚠️ PARTIAL | Needs verification |

### For Sentinel Integration

| Prerequisite | Status | Notes |
|--------------|--------|-------|
| LLM provider working | ❌ SKELETON | Sentinel wraps LLM |
| SCC coherence monitoring | ✅ WORKING | Maps to Sentinel coherence |
| Safety layer configurable | ❌ HARDCODED | Need for Safety Contract |
| Error handling | ❌ EMPTY PASS | Sentinel requires proper error reporting |

---

## 12. Conclusion

**The robotics module is architecturally sound but implementation-incomplete.**

Key findings:
1. **45+ files** have skeleton/placeholder code
2. **Neural network training** is completely non-functional
3. **LLM provider** falls back to regex only
4. **Hardware adapters** use simplistic mocks
5. **Safety validation** uses placeholder kinematics

**Recommended approach:**
1. Complete **Phase 1 (Core Infrastructure)** before any framework integration
2. **Phase-Quad and Sentinel** require LLM provider to be functional
3. **CTM+ and PCAM** can integrate after Phase 2
4. Full integration possible after **Week 9**

**Total estimated effort: 9 weeks** to production-ready standalone module.

---

## Appendix: File-by-File Skeleton Locations

| File | Line Numbers | Type |
|------|--------------|------|
| `learning/skill_learning.py` | 82, 176-180, 342-379, 381-408, 410-417, 419-427 | Skeleton class, methods |
| `learning/dynamics_model.py` | 152-161, 169-172, 217-271, 444-452 | Skeleton class, linear-only |
| `learning/transfer.py` | 338-339 | Placeholder domain adaptation |
| `learning/calibration.py` | 155, 185, 195, 412, 418 | Incomplete calibration |
| `planning/mpc_planner.py` | 240-243, 303, 338, 469, 471, 528 | Skeleton MPC |
| `planning/htn_planner.py` | 206-210, 287, 301, 307, 316, 321, 334, 338, 341, 364, 472 | Skeleton HTN |
| `planning/path_planner.py` | 220 | Empty path fallback |
| `planning/world_model.py` | 175, 187-188, 209 | Incomplete world state |
| `comms/human_interface.py` | 268-269, 296-298, 307-308, 317-318, 513, 556 | Skeleton LLM |
| `comms/ros_bridge.py` | 106-107, 190, 199, 261 | Empty exception handlers |
| `adapters/isaac_adapter.py` | 72-77, 83-88, 96 | Mock fallback |
| `adapters/ros2_adapter.py` | 92 | Placeholder quaternion |
| `adapters/serial_adapter.py` | 54-168 (multiple) | Stub methods |
| `safety/trajectory_validator.py` | 747, 764, 773, 794, 805, 828-839 | Placeholder FK |
| `safety/human_proximity.py` | 97, 100, 104, 109 | Hardcoded values |
| `recovery/watchdog.py` | 227 | Empty exception |
| `recovery/fallback.py` | 237, 243, 281, 285, 289, 291, 311, 324, 343 | Stub methods |
