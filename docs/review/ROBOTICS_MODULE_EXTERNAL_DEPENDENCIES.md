# Robotics Module - External Dependency Implementation Analysis

**Date:** 2026-02-03
**Purpose:** Evaluate which standalone upgrades can be implemented using external libraries

---

## Executive Summary

Of the 10 major upgrade areas identified, **8 can be implemented primarily with external dependencies**, significantly reducing custom development effort.

| Area | External Dependency Solution | Effort Reduction |
|------|------------------------------|------------------|
| Neural Network Training | PyTorch + Stable-Baselines3 | 80% → ~3 days |
| LLM Provider | openai / litellm | 90% → ~1 day |
| MPC Planning | CasADi + IPOPT | 85% → ~2 days |
| HTN Planning | pyhop3 / SHOP3 | 70% → ~3 days |
| Path Planning | ompl / networkx | 90% → ~1 day |
| Forward Kinematics | roboticstoolbox / pinocchio | 95% → ~1 day |
| URDF Parsing | urdf_parser_py / yourdfpy | 95% → ~0.5 days |
| Serial Communication | pyserial | 70% → ~2 days |

**Total: 9 weeks → ~2-3 weeks with external dependencies**

---

## 1. Neural Network Training Infrastructure

### Current Gap
- `skill_learning.py:342-379` - `train_step()` is skeleton
- `dynamics_model.py:217-271` - Only linear regression

### External Dependencies Available

| Library | Purpose | Maturity | License |
|---------|---------|----------|---------|
| **PyTorch** | NN framework | Production | BSD |
| **Stable-Baselines3** | RL algorithms (PPO, SAC, TD3) | Production | MIT |
| **CleanRL** | Single-file RL implementations | Good | MIT |
| **tianshou** | RL with PyTorch | Good | MIT |

### Recommended: PyTorch + Stable-Baselines3

```python
# skill_learning.py - Implementation with SB3
from stable_baselines3 import SAC
from stable_baselines3.common.buffers import ReplayBuffer

class SkillLearner:
    def __init__(self, config):
        # Existing interface preserved
        self._model = SAC(
            "MlpPolicy",
            env=None,  # Custom wrapper for Layer12D
            learning_rate=config.learning_rate,
            buffer_size=config.buffer_size,
            batch_size=config.batch_size,
        )

    def train_step(self) -> Dict[str, float]:
        # Now functional!
        self._model.train(gradient_steps=1)
        return {"loss": self._model.logger.name_to_value.get("train/loss", 0)}
```

### Implementation Effort

| Task | With External Deps | Without |
|------|-------------------|---------|
| RL training loop | 1 day (SB3 wrapper) | 5 days |
| Policy network | 0.5 days (SB3 MlpPolicy) | 3 days |
| Experience replay | 0 (SB3 ReplayBuffer) | 2 days |
| Dynamics ensemble | 1 day (PyTorch) | 4 days |
| **Total** | **2.5 days** | **14 days** |

### Dependencies to Add
```
torch>=2.0.0
stable-baselines3>=2.0.0
gymnasium>=0.29.0
```

---

## 2. LLM Provider Implementation

### Current Gap
- `human_interface.py:296-318` - Falls back to regex

### External Dependencies Available

| Library | Purpose | Features | License |
|---------|---------|----------|---------|
| **openai** | OpenAI API | Official SDK | MIT |
| **litellm** | Universal LLM API | 100+ providers | MIT |
| **ollama** | Local LLM | Edge deployment | MIT |
| **langchain** | LLM orchestration | Chains, agents | MIT |

### Recommended: litellm (universal provider)

```python
# human_interface.py - Implementation with litellm
import litellm

class OpenAILLMProvider(LLMProvider):
    def __init__(self, api_key=None, config=None):
        self._config = config or LLMConfig()
        # litellm handles OpenAI, Anthropic, Ollama, Azure, etc.

    def parse_command(self, text: str, context: Dict) -> Dict:
        response = litellm.completion(
            model=self._config.model_name,  # "gpt-4", "ollama/llama2", etc.
            messages=[
                {"role": "system", "content": self._system_prompt},
                {"role": "user", "content": f"Context: {context}\nCommand: {text}"}
            ],
            temperature=self._config.temperature,
            max_tokens=self._config.max_tokens,
            response_format={"type": "json_object"},
        )
        return json.loads(response.choices[0].message.content)
```

### Implementation Effort

| Task | With External Deps | Without |
|------|-------------------|---------|
| API integration | 0.5 days (litellm) | 2 days |
| Streaming | 0.5 days (litellm) | 1 day |
| Error handling | 0.5 days | 1 day |
| Local LLM option | 0 (litellm + ollama) | 3 days |
| **Total** | **1.5 days** | **7 days** |

### Dependencies to Add
```
litellm>=1.0.0
# or minimal:
openai>=1.0.0
```

---

## 3. MPC Planning (CasADi/IPOPT)

### Current Gap
- `mpc_planner.py:303-339` - Random perturbation, not gradient-based

### External Dependencies Available

| Library | Purpose | Speed | License |
|---------|---------|-------|---------|
| **CasADi** | Symbolic optimization | Fast | LGPL |
| **IPOPT** | Nonlinear optimization | Fast | EPL |
| **scipy.optimize** | General optimization | Moderate | BSD |
| **cvxpy** | Convex optimization | Moderate | Apache |

### Recommended: CasADi + IPOPT

```python
# mpc_planner.py - Implementation with CasADi
import casadi as ca

class MPCPlanner:
    def __init__(self, config):
        self._config = config
        self._setup_optimization()

    def _setup_optimization(self):
        # Symbolic variables
        self._x = ca.SX.sym('x', 12)  # 12D state
        self._u = ca.SX.sym('u', 7)   # 7 DOF control

        # Dynamics (from learned model or nominal)
        self._f = self._define_dynamics()

        # Cost function
        Q = ca.diag(self._config.state_cost_weights)
        R = ca.diag(self._config.control_cost_weights)
        self._cost = ca.mtimes([self._x.T, Q, self._x]) + ca.mtimes([self._u.T, R, self._u])

        # NLP problem
        self._nlp = {'x': ca.vertcat(self._x, self._u), 'f': self._cost}
        self._solver = ca.nlpsol('mpc', 'ipopt', self._nlp, {
            'ipopt.print_level': 0,
            'ipopt.max_iter': self._config.max_iterations,
        })

    def plan(self, current_state, current_coherence=1.0, goal_state=None):
        # Now uses gradient-based optimization!
        solution = self._solver(x0=self._initial_guess, lbx=self._lb, ubx=self._ub)
        return self._extract_result(solution)
```

### Implementation Effort

| Task | With External Deps | Without |
|------|-------------------|---------|
| Optimization setup | 1 day (CasADi) | 5 days |
| Constraint handling | 0.5 days | 3 days |
| Warm-starting | 0.5 days | 1 day |
| **Total** | **2 days** | **9 days** |

### Dependencies to Add
```
casadi>=3.6.0
```

---

## 4. HTN Planning

### Current Gap
- `htn_planner.py:287-472` - 10+ methods return `None`

### External Dependencies Available

| Library | Purpose | Features | License |
|---------|---------|----------|---------|
| **pyhop** | HTN planner | Simple, Pythonic | MIT |
| **SHOP3** | HTN planner | Full-featured | MPL |
| **unified-planning** | Planning framework | Multiple planners | Apache |

### Recommended: pyhop3 (simple integration)

```python
# htn_planner.py - Implementation with pyhop
import pyhop

class HTNPlanner:
    def __init__(self, config):
        self._config = config
        self._setup_domain()

    def _setup_domain(self):
        # Define operators (primitive actions)
        pyhop.declare_operators(move_to, pick_up, put_down, wait)

        # Define methods (task decomposition)
        pyhop.declare_methods('transport', transport_method)
        pyhop.declare_methods('navigate', navigate_method)

    def plan(self, initial_state, goal_tasks):
        # Convert to pyhop state
        state = self._to_pyhop_state(initial_state)
        tasks = self._to_pyhop_tasks(goal_tasks)

        # Plan!
        plan = pyhop.pyhop(state, tasks, verbose=0)
        return self._from_pyhop_plan(plan)
```

### Implementation Effort

| Task | With External Deps | Without |
|------|-------------------|---------|
| Domain definition | 1 day | 3 days |
| Task decomposition | 1 day (pyhop methods) | 4 days |
| Plan execution | 1 day | 2 days |
| **Total** | **3 days** | **9 days** |

### Dependencies to Add
```
pyhop3>=1.0.0
# or
unified-planning>=1.0.0
```

---

## 5. Path Planning

### Current Gap
- `path_planner.py:220` - Returns empty list

### External Dependencies Available

| Library | Purpose | Algorithms | License |
|---------|---------|------------|---------|
| **OMPL** | Motion planning | RRT*, PRM*, etc. | BSD |
| **networkx** | Graph algorithms | A*, Dijkstra | BSD |
| **python-rrt** | RRT implementation | RRT, RRT* | MIT |

### Recommended: networkx (for grid) + OMPL (for continuous)

```python
# path_planner.py - Implementation with networkx
import networkx as nx

class PathPlanner:
    def __init__(self, config):
        self._config = config
        self._graph = None

    def plan_grid(self, start, goal, obstacles):
        # Build graph from grid
        G = nx.grid_2d_graph(self._config.grid_size, self._config.grid_size)

        # Remove obstacle nodes
        for obs in obstacles:
            if obs in G:
                G.remove_node(obs)

        # A* search
        try:
            path = nx.astar_path(G, start, goal, heuristic=self._euclidean)
            return path
        except nx.NetworkXNoPath:
            return []  # No path exists (explicit)
```

### Implementation Effort

| Task | With External Deps | Without |
|------|-------------------|---------|
| Grid A* | 0.5 days (networkx) | 2 days |
| RRT* | 0.5 days (OMPL/python-rrt) | 4 days |
| **Total** | **1 day** | **6 days** |

### Dependencies to Add
```
networkx>=3.0
# optional for continuous spaces:
ompl>=1.6.0
```

---

## 6. Forward Kinematics & URDF

### Current Gap
- `trajectory_validator.py:828-839` - Placeholder simplified FK

### External Dependencies Available

| Library | Purpose | Features | License |
|---------|---------|----------|---------|
| **roboticstoolbox-python** | Robotics | FK, IK, Jacobian | MIT |
| **pinocchio** | Rigid body dynamics | Fast FK/IK | BSD |
| **yourdfpy** | URDF parsing | Modern Python | MIT |
| **urdf_parser_py** | URDF parsing | ROS standard | BSD |

### Recommended: roboticstoolbox-python (all-in-one)

```python
# trajectory_validator.py - Implementation with roboticstoolbox
import roboticstoolbox as rtb
from spatialmath import SE3

class TrajectoryValidator:
    def __init__(self, urdf_path: str):
        # Load robot from URDF
        self._robot = rtb.Robot.URDF(urdf_path)

    def _compute_fk(self, joint_positions: np.ndarray) -> RobotPose:
        # Real FK using DH parameters from URDF
        T = self._robot.fkine(joint_positions)  # SE3 transform
        return RobotPose(
            x=T.t[0], y=T.t[1], z=T.t[2],
            qw=T.q[0], qx=T.q[1], qy=T.q[2], qz=T.q[3]
        )

    def _compute_jacobian(self, joint_positions: np.ndarray) -> np.ndarray:
        # Jacobian for velocity mapping
        return self._robot.jacob0(joint_positions)
```

### Implementation Effort

| Task | With External Deps | Without |
|------|-------------------|---------|
| URDF parsing | 0 (roboticstoolbox) | 3 days |
| FK computation | 0 (roboticstoolbox) | 2 days |
| Jacobian | 0 (roboticstoolbox) | 2 days |
| IK (bonus) | 0 (roboticstoolbox) | 4 days |
| **Total** | **1 day** (integration) | **11 days** |

### Dependencies to Add
```
roboticstoolbox-python>=1.1.0
spatialmath-python>=1.1.0
# or lightweight:
yourdfpy>=0.0.53
```

---

## 7. Serial Communication

### Current Gap
- `serial_adapter.py:54-168` - Stub methods

### External Dependencies Available

| Library | Purpose | Features | License |
|---------|---------|----------|---------|
| **pyserial** | Serial ports | Cross-platform | BSD |
| **pyserial-asyncio** | Async serial | Non-blocking | BSD |

### Recommended: pyserial

```python
# serial_adapter.py - Implementation with pyserial
import serial
import struct

class SerialAdapter(BaseAdapter):
    def __init__(self, port: str, baudrate: int = 115200):
        self._serial = serial.Serial(port, baudrate, timeout=0.1)

    def connect(self) -> bool:
        if not self._serial.is_open:
            self._serial.open()
        return self._serial.is_open

    def read_sensors(self) -> SensorFrame:
        # Read packet from microcontroller
        data = self._serial.read(self._packet_size)
        if len(data) == self._packet_size:
            # Unpack binary data
            joints = struct.unpack('6f', data[:24])
            return SensorFrame(joint_positions=np.array(joints))
        return None

    def send_command(self, command: ActuatorCommand) -> bool:
        # Pack and send
        data = struct.pack('7f', *command.target_velocities)
        self._serial.write(data)
        return True
```

### Implementation Effort

| Task | With External Deps | Without |
|------|-------------------|---------|
| Serial connection | 0.5 days (pyserial) | 2 days |
| Protocol implementation | 1.5 days | 3 days |
| **Total** | **2 days** | **5 days** |

### Dependencies to Add
```
pyserial>=3.5
```

---

## 8. Persistence (Save/Load)

### Current Gap
- Empty `save()`/`load()` methods

### External Dependencies Available

| Library | Purpose | Features |
|---------|---------|----------|
| **torch.save/load** | PyTorch models | Standard |
| **pickle** | Python objects | Built-in |
| **safetensors** | Safe model storage | Hugging Face |

### Implementation (mostly built-in)

```python
# skill_learning.py
import torch

def save(self, path: str) -> None:
    torch.save({
        'skills': {name: skill.__dict__ for name, skill in self._skills.items()},
        'buffer': self._buffer,
        'config': self._config,
    }, path)

def load(self, path: str) -> None:
    checkpoint = torch.load(path)
    self._skills = {name: LearnedSkill(**data) for name, data in checkpoint['skills'].items()}
    self._buffer = checkpoint['buffer']
```

### Implementation Effort

| Task | With External Deps | Without |
|------|-------------------|---------|
| Model serialization | 0.5 days (torch.save) | 1 day |
| Versioning | 0.5 days | 1 day |
| **Total** | **1 day** | **2 days** |

---

## 9. Error Handling & Logging

### Current Gap
- Empty `pass` in exception handlers

### External Dependencies Available

| Library | Purpose | Features |
|---------|---------|----------|
| **logging** | Logging | Built-in |
| **structlog** | Structured logging | JSON, context |
| **sentry-sdk** | Error tracking | Production |

### Implementation (built-in Python)

```python
# Throughout codebase
import logging

logger = logging.getLogger(__name__)

try:
    # ... operation
except ConnectionError as e:
    logger.warning(f"Connection failed: {e}, falling back to mock")
    self._init_mock()
except Exception as e:
    logger.error(f"Unexpected error: {e}", exc_info=True)
    raise
```

### Implementation Effort

| Task | Effort |
|------|--------|
| Add logging throughout | 1 day |
| Structured error handling | 1 day |
| **Total** | **2 days** |

---

## 10. Complete Dependency Summary

### New Dependencies Required

```toml
# pyproject.toml additions

[project.dependencies]
# ML/RL (for learning module)
torch = ">=2.0.0"
stable-baselines3 = ">=2.0.0"
gymnasium = ">=0.29.0"

# LLM (for human interface)
litellm = ">=1.0.0"

# Planning
casadi = ">=3.6.0"
networkx = ">=3.0"
pyhop3 = ">=1.0.0"

# Robotics
roboticstoolbox-python = ">=1.1.0"
spatialmath-python = ">=1.1.0"

# Hardware
pyserial = ">=3.5"

[project.optional-dependencies]
# Optional for advanced features
ompl = ["ompl>=1.6.0"]
local-llm = ["ollama>=0.1.0"]
```

### Dependency Installation Size

| Category | Size | Notes |
|----------|------|-------|
| PyTorch | ~2 GB | Required for learning |
| Stable-Baselines3 | ~50 MB | RL algorithms |
| CasADi | ~100 MB | MPC optimization |
| roboticstoolbox | ~100 MB | FK/IK/dynamics |
| litellm | ~10 MB | LLM provider |
| Others | ~50 MB | networkx, pyserial, etc. |
| **Total** | **~2.3 GB** | Mostly PyTorch |

---

## 11. Revised Implementation Roadmap

### With External Dependencies

| Phase | Tasks | Duration |
|-------|-------|----------|
| **Phase 1** | NN training (SB3), LLM provider (litellm) | **4 days** |
| **Phase 2** | MPC (CasADi), FK (roboticstoolbox), HTN (pyhop) | **6 days** |
| **Phase 3** | Path planning, Serial, Error handling | **4 days** |
| **Phase 4** | Integration testing | **3 days** |
| **Total** | | **17 days (~3.5 weeks)** |

### Without External Dependencies

| Phase | Duration |
|-------|----------|
| Phase 1 | 21 days |
| Phase 2 | 20 days |
| Phase 3 | 8 days |
| Phase 4 | 5 days |
| **Total** | **54 days (~11 weeks)** |

### Time Savings: 68% reduction (11 weeks → 3.5 weeks)

---

## 12. Implementation Priority with Dependencies

| Priority | Area | Library | Days | Blocks |
|----------|------|---------|------|--------|
| P0 | LLM Provider | litellm | 1.5 | Phase-Quad, Sentinel |
| P0 | NN Training | SB3 + PyTorch | 2.5 | Learning module |
| P1 | FK/URDF | roboticstoolbox | 1 | Safety validation |
| P1 | MPC | CasADi | 2 | Planning |
| P2 | HTN | pyhop3 | 3 | Complex tasks |
| P2 | Path Planning | networkx | 1 | Navigation |
| P3 | Serial | pyserial | 2 | Hardware |
| P3 | Persistence | torch.save | 1 | CTM+ integration |
| P3 | Error Handling | logging | 2 | Production readiness |

---

## 13. Risk Assessment

| Risk | Mitigation |
|------|------------|
| PyTorch size (2GB) | Edge deployment may need ONNX export |
| CasADi licensing (LGPL) | Can use scipy.optimize as fallback |
| roboticstoolbox dependencies | Core FK works without visualization |
| litellm API changes | Pin version, has good backwards compat |

---

## 14. Conclusion

**8 of 10 upgrade areas can be implemented with external dependencies**, reducing total effort from **11 weeks to 3.5 weeks**.

Key external libraries:
1. **PyTorch + Stable-Baselines3** - Complete RL infrastructure
2. **litellm** - Universal LLM provider (OpenAI, Anthropic, Ollama, etc.)
3. **CasADi** - Production-grade MPC optimization
4. **roboticstoolbox-python** - FK, IK, Jacobian, URDF parsing
5. **networkx** - Path planning algorithms

The only areas requiring significant custom development:
- Protocol-specific serial communication (robot-dependent)
- Domain-specific HTN methods (task-dependent)

**Recommendation:** Proceed with external dependency integration. The 68% time savings and production-quality implementations outweigh the ~2.3GB dependency footprint.
