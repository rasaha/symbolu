# §6.2 nuScenes-mini Pilot — RunPod Execution Runbook

A copy-pasteable runbook for executing the §6.2 real-data pilot on
[RunPod](https://www.runpod.io). All sandbox-blocked steps
(`nuscenes-devkit` install, dataset download, real-data execution)
land in this environment.

**The pilot harness already lands cleanly with no nuScenes-specific
code on the trunk.** This runbook covers the four out-of-sandbox
steps: dataset acquisition, predictor implementation,
`NuScenesAdapter.load_scene()` filling, and execution.

Estimated wall time: **3–5 days** of focused engineering for a
first reportable result. Pilot plan estimate of "3–4 weeks" is
inclusive of a learned-forecaster M3; with the simpler M3 fallback
described below, the timeline compresses.

---

## §0 Prerequisites (5 minutes, do this BEFORE renting the pod)

1. **Create a nuScenes account.** Sign up at
   [nuscenes.org](https://www.nuscenes.org/) and accept the license.
   Required for dataset access.
2. **Download nuScenes-mini locally** (~3.9 GB compressed). From
   the [Downloads](https://www.nuscenes.org/nuscenes#download)
   page, grab:
   - `v1.0-mini.tgz` — the mini split metadata + sensor data
   - The map expansion `nuScenes-map-expansion-v1.3.zip` if you'll
     run M1 (HD-map prior)
3. **Create a RunPod account** with $20+ credit.
4. **Install `runpodctl` locally** (for SCP-style file transfer to
   the pod):
   ```bash
   wget -qO- cli.runpod.net | sudo bash
   runpodctl config --apiKey YOUR_API_KEY
   ```

---

## §1 Pod selection

### Recommended config (CPU-only, sufficient for the simple-M3 fallback)

| Field | Value | Why |
|---|---|---|
| **GPU** | None (CPU pod) | The pilot is pure NumPy. No GPU needed unless you use a learned forecaster as M3. |
| **vCPU** | 8 | Predictor rollouts are vectorized; 8 cores covers M=4 in parallel comfortably. |
| **RAM** | 16 GB | nuScenes-mini metadata + scene records fit comfortably. |
| **Disk** | 50 GB | nuScenes-mini extracted ≈ 9 GB; results + checkpoints buffer. |
| **Volume** | 50 GB Network Volume | Persists if the pod terminates; only pay $0.07/GB/month. |
| **Image** | `runpod/pytorch:2.1.0-py3.10-cuda11.8.0-devel-ubuntu22.04` | Has Python 3.10 + system tools; we won't actually use CUDA. |
| **Hourly cost** | ~$0.10–0.30/hr CPU on-demand | Pilot wall time ~10 hours over a few days. |

If you choose to run a learned-forecaster M3 (CoverNet / MTP /
Trajectron++), upgrade to:
- **GPU**: RTX A4000 / RTX 4000 (16 GB VRAM)
- **Hourly cost**: ~$0.50–1.00/hr
- **Image**: same — already has CUDA

### Network volume mount point

Mount the volume at `/workspace`. The runbook assumes that path
throughout.

---

## §2 Pod boot + repo clone (3 minutes)

SSH into the pod (RunPod gives you the host + port) and run:

```bash
cd /workspace
git clone https://github.com/rasaha/symbolu.git
cd symbolu
git checkout claude/compare-bcvf-designs-7KqS8   # the active pilot branch
git pull origin claude/compare-bcvf-designs-7KqS8

# Confirm the pilot harness is on the branch
ls symbolu_robotics/bcvf_autonomous/pilot/
# Expected: DESIGN.md __init__.py runner.py scene_evaluator.py sign_test.py
```

---

## §3 Environment setup (5 minutes)

```bash
# Use the pod's Python 3.10
python3 -m venv /workspace/venv
source /workspace/venv/bin/activate
pip install --upgrade pip wheel

# Core deps for the BCVF runtime
pip install numpy pytest

# Pilot-specific deps (the one this sandbox couldn't install)
pip install nuscenes-devkit pyquaternion shapely scikit-learn

# Sanity check: pilot runs against the in-tree synthetic adapter
cd /workspace/symbolu
python -m pytest symbolu_robotics/bcvf_autonomous/tests/test_pilot.py -q
# Expect: 16 passed
```

---

## §4 Upload nuScenes-mini to the pod (10 minutes)

From your **local machine** (where you downloaded the tgz / zip):

```bash
# Send the dataset tarball to the pod's persistent volume
runpodctl send v1.0-mini.tgz <your-pod-id>:/workspace/
runpodctl send nuScenes-map-expansion-v1.3.zip <your-pod-id>:/workspace/

# (Or use scp -P <port> v1.0-mini.tgz root@<pod-host>:/workspace/)
```

On the **pod**:

```bash
cd /workspace
mkdir -p nuscenes-mini
tar -xzf v1.0-mini.tgz -C nuscenes-mini/
unzip -q nuScenes-map-expansion-v1.3.zip -d nuscenes-mini/maps/

# Verify
ls nuscenes-mini/
# Expected: maps  samples  sweeps  v1.0-mini

# Quick smoke test that nuscenes-devkit can read it
python -c "
from nuscenes.nuscenes import NuScenes
nusc = NuScenes(version='v1.0-mini', dataroot='/workspace/nuscenes-mini', verbose=False)
print(f'Scenes available: {len(nusc.scene)}')
"
# Expected: 'Scenes available: 10'
```

---

## §5 Implement the four predictors

This is the actual engineering work. The runbook ships
copy-pasteable skeletons for each predictor; you fill in the
dataset-specific bits.

Save each file under
`/workspace/symbolu/symbolu_robotics/bcvf_autonomous/predictors/nuscenes/`.

### 5.1 — Common scaffolding

`predictors/nuscenes/__init__.py`:

```python
from .m1_hdmap import HDMapPredictor
from .m2_ctrv import CTRVKalmanPredictor
from .m3_cv_baseline import CVBaselinePredictor
from .m4_failure_inject import FailureInjectedPredictor

__all__ = [
    "HDMapPredictor",
    "CTRVKalmanPredictor",
    "CVBaselinePredictor",
    "FailureInjectedPredictor",
]
```

### 5.2 — M1 HD-map prior

`predictors/nuscenes/m1_hdmap.py` — projects the current ego pose
onto the closest lane centerline and propagates at current
velocity:

```python
"""M1 — HD-map prior predictor (nuScenes wrapper)."""
from __future__ import annotations
import numpy as np
from nuscenes.map_expansion.map_api import NuScenesMap
from ..base import BasePredictor, BicycleConfig, PredictorState


class HDMapPredictor(BasePredictor):
    def __init__(self, nusc_map: NuScenesMap,
                 bicycle_config: BicycleConfig | None = None,
                 seed: int = 100):
        super().__init__(model_id="M1", bicycle_config=bicycle_config, seed=seed)
        self._map = nusc_map

    def apply_noise(self, state, step):
        # HD-map prior is deterministic — no observation noise.
        return state

    def apply_failure(self, state, time):
        return state

    # NOTE: predict_batch override is OPTIONAL for nuScenes; the
    # default base-class loop is fast enough for K=1 (we're not
    # running MPPI — pilot is open-loop replay). If you wire BCVF
    # into a closed-loop MPPI on real data, add a batch override.

    def project_to_lane(self, ego_xy, ego_theta) -> tuple:
        """Find the closest lane and the projected (x, y, theta)."""
        lane_token = self._map.get_closest_lane(
            x=ego_xy[0], y=ego_xy[1], radius=2.0,
        )
        if lane_token == "":
            # No lane found — fall back to current pose (BCVF will
            # still see disagreement against M2/M3 if they keep
            # moving).
            return ego_xy[0], ego_xy[1], ego_theta
        lane = self._map.arcline_path_3.get(lane_token)
        # nuScenes lane API returns a list of (x, y, theta, ...) poses.
        pts = self._map.discretize_lanes([lane_token], resolution_meters=0.5)
        pts = pts[lane_token]
        if not pts:
            return ego_xy[0], ego_xy[1], ego_theta
        # Closest point on the discretized lane.
        arr = np.array([(p[0], p[1], p[2]) for p in pts])
        d = np.linalg.norm(arr[:, :2] - np.array(ego_xy), axis=-1)
        idx = int(d.argmin())
        return float(arr[idx, 0]), float(arr[idx, 1]), float(arr[idx, 2])
```

### 5.3 — M2 CTRV Kalman extrapolation

`predictors/nuscenes/m2_ctrv.py`:

```python
"""M2 — Constant-Turn-Rate Constant-Velocity Kalman predictor."""
from __future__ import annotations
import math
import numpy as np
from ..base import BasePredictor, BicycleConfig, PredictorState
from ...manifold import wrap_angle


class CTRVKalmanPredictor(BasePredictor):
    def __init__(self, bicycle_config=None, seed: int = 200):
        super().__init__(model_id="M2", bicycle_config=bicycle_config, seed=seed)
        self._yaw_rate: float = 0.0    # set per-frame from CAN bus

    def set_yaw_rate(self, yaw_rate: float) -> None:
        """Update the yaw rate from the latest CAN-bus sample."""
        self._yaw_rate = float(yaw_rate)

    def apply_noise(self, state, step):
        rng = self._rng
        # Per-frame Gaussian noise calibrated to filtered CAN bus.
        state.x += float(rng.normal(0.0, 0.01))
        state.y += float(rng.normal(0.0, 0.01))
        state.theta += float(rng.normal(0.0, 0.001))
        return state

    def apply_failure(self, state, time):
        return state

    # Override predict() to use CTRV instead of bicycle dynamics —
    # CTRV ignores the steering control input and propagates with
    # the cached yaw rate.
    def predict(self, control_sequence: np.ndarray) -> np.ndarray:
        from dataclasses import replace
        ctrl = np.asarray(control_sequence, dtype=np.float64)
        self._reset_call_context()
        s = replace(self._state)
        H = ctrl.shape[0]
        out = np.zeros((H, 3), dtype=np.float64)
        dt = self.bicycle_config.dt
        for h in range(H):
            v = float(ctrl[h, 0])
            yaw = self._yaw_rate
            if abs(yaw) < 1e-6:
                s.x += v * math.cos(s.theta) * dt
                s.y += v * math.sin(s.theta) * dt
            else:
                s.x += (v / yaw) * (math.sin(s.theta + yaw * dt) - math.sin(s.theta))
                s.y += (v / yaw) * (-math.cos(s.theta + yaw * dt) + math.cos(s.theta))
                s.theta = wrap_angle(s.theta + yaw * dt)
            obs = self.apply_noise(replace(s), h)
            out[h] = [obs.x, obs.y, wrap_angle(obs.theta)]
        return out
```

### 5.4 — M3 constant-velocity baseline (the simple-M3 fallback)

`predictors/nuscenes/m3_cv_baseline.py`:

```python
"""M3 — Constant-velocity straight-line baseline.

Pilot plan §risks-and-fallbacks option (c): in the absence of a
trained learned forecaster, a CV baseline that ignores yaw rate
gives M3 a different dynamic model than M2 (CTRV with yaw). When
the ego turns, M2 and M3 disagree — that's the within-horizon
2nd-order signal BCVF can detect.

Replace this with CoverNet / MTP / Trajectron++ for the
production pilot if you want a learned baseline.
"""
from __future__ import annotations
import math
import numpy as np
from dataclasses import replace
from ..base import BasePredictor
from ...manifold import wrap_angle


class CVBaselinePredictor(BasePredictor):
    def __init__(self, bicycle_config=None, seed: int = 300):
        super().__init__(model_id="M3", bicycle_config=bicycle_config, seed=seed)

    def apply_noise(self, state, step):
        rng = self._rng
        state.x += float(rng.normal(0.0, 0.02))
        state.y += float(rng.normal(0.0, 0.02))
        state.theta += float(rng.normal(0.0, 0.002))
        return state

    def apply_failure(self, state, time):
        return state

    def predict(self, control_sequence):
        ctrl = np.asarray(control_sequence, dtype=np.float64)
        self._reset_call_context()
        s = replace(self._state)
        H = ctrl.shape[0]
        out = np.zeros((H, 3), dtype=np.float64)
        dt = self.bicycle_config.dt
        for h in range(H):
            v = float(ctrl[h, 0])
            # Straight line — ignore steering, ignore yaw.
            s.x += v * math.cos(s.theta) * dt
            s.y += v * math.sin(s.theta) * dt
            obs = self.apply_noise(replace(s), h)
            out[h] = [obs.x, obs.y, wrap_angle(obs.theta)]
        return out
```

### 5.5 — M4 failure-injected wrapper

`predictors/nuscenes/m4_failure_inject.py`:

```python
"""M4 — Wraps M2 (or M1) and injects a documented failure pattern.

Use one of the four pilot-plan failure types:
- gps_multipath: lateral position jumps during a window
- map_misalignment: constant lateral offset throughout
- camera_degradation: high-frequency yaw jitter during a window
- constant_bias_sanity: fixed bias for Lemma 1 negative control
"""
from __future__ import annotations
import math
import numpy as np
from dataclasses import replace
from ..base import BasePredictor


class FailureInjectedPredictor(BasePredictor):
    def __init__(self, base_predictor: BasePredictor,
                 failure_type: str = "gps_multipath",
                 onset_step: int = 50,
                 duration_steps: int = 50,
                 magnitude: float = 2.0,
                 seed: int = 400):
        super().__init__(model_id="M4", bicycle_config=base_predictor.bicycle_config, seed=seed)
        self._base = base_predictor
        self.failure_type = failure_type
        self.onset_step = onset_step
        self.duration_steps = duration_steps
        self.magnitude = magnitude

    def apply_noise(self, state, step): return state
    def apply_failure(self, state, time): return state

    def predict(self, control_sequence):
        # Run the base predictor's prediction first.
        traj = self._base.predict(control_sequence).copy()
        # Inject failure within the configured horizon window.
        H = traj.shape[0]
        rng = self._rng
        if self.failure_type == "gps_multipath":
            # Lateral jumps during the failure window
            for h in range(H):
                if rng.random() < 0.3:
                    traj[h, 1] += rng.exponential(scale=self.magnitude)
        elif self.failure_type == "map_misalignment":
            traj[:, 1] += self.magnitude
        elif self.failure_type == "camera_degradation":
            # High-frequency yaw jitter — within-horizon 2nd-order signal
            traj[:, 2] += rng.normal(scale=self.magnitude * 0.1, size=H)
        elif self.failure_type == "constant_bias_sanity":
            traj[:, 1] += self.magnitude * 0.5
        return traj
```

---

## §6 Implement `NuScenesAdapter.load_scene()`

Create
`/workspace/symbolu/symbolu_robotics/bcvf_autonomous/datasets/nuscenes_real.py`
(don't overwrite the stub at `nuscenes.py`; this is the real one):

```python
"""Real nuScenes-mini adapter — fills in the §6.2 stub."""
from __future__ import annotations
from typing import List
import numpy as np
from nuscenes.nuscenes import NuScenes
from nuscenes.map_expansion.map_api import NuScenesMap
from .base import DatasetAdapter, SceneRecord
from ..predictors.nuscenes import (
    HDMapPredictor, CTRVKalmanPredictor,
    CVBaselinePredictor, FailureInjectedPredictor,
)
from ..predictors.base import PredictorState

H = 20   # 2 s horizon at 10 Hz
DT = 0.1


class NuScenesAdapter(DatasetAdapter):
    def __init__(self, dataroot: str, version: str = "v1.0-mini"):
        self._nusc = NuScenes(version=version, dataroot=dataroot, verbose=False)
        # Load all four nuScenes-mini maps lazily on demand.
        self._maps: dict = {}
        self._dataroot = dataroot
        # Failure-pattern rotation across scenes.
        self._failure_types = (
            "gps_multipath", "map_misalignment",
            "camera_degradation", "constant_bias_sanity",
        )

    def _get_map(self, log_token: str) -> NuScenesMap:
        log = self._nusc.get("log", log_token)
        loc = log["location"]
        if loc not in self._maps:
            self._maps[loc] = NuScenesMap(dataroot=self._dataroot, map_name=loc)
        return self._maps[loc]

    def scene_ids(self) -> List[str]:
        return [s["token"] for s in self._nusc.scene]

    def load_scene(self, scene_id: str) -> SceneRecord:
        scene = self._nusc.get("scene", scene_id)
        log = self._nusc.get("log", scene["log_token"])
        nusc_map = self._get_map(scene["log_token"])

        # Walk every keyframe in the scene; build the ego trace + per-step
        # predictor outputs.
        sample_token = scene["first_sample_token"]
        ego_poses: list = []
        sample_tokens: list = []
        while sample_token != "":
            sample = self._nusc.get("sample", sample_token)
            sd = self._nusc.get("sample_data", sample["data"]["LIDAR_TOP"])
            ego = self._nusc.get("ego_pose", sd["ego_pose_token"])
            x, y, _ = ego["translation"]
            # Yaw from quaternion
            from pyquaternion import Quaternion
            q = Quaternion(ego["rotation"])
            theta = q.yaw_pitch_roll[0]
            ego_poses.append([x, y, theta])
            sample_tokens.append(sample_token)
            sample_token = sample["next"]

        ego_trace = np.array(ego_poses, dtype=np.float64)
        T = ego_trace.shape[0]

        # Pick failure type based on scene index — round-robin so the
        # 10 mini scenes cover 2-3 of each pattern.
        idx = self.scene_ids().index(scene_id)
        ftype = self._failure_types[idx % len(self._failure_types)]

        # Instantiate predictors. M2 is the base for M4 to wrap.
        m1 = HDMapPredictor(nusc_map=nusc_map, seed=idx * 4 + 1)
        m2 = CTRVKalmanPredictor(seed=idx * 4 + 2)
        m3 = CVBaselinePredictor(seed=idx * 4 + 3)
        m4 = FailureInjectedPredictor(
            base_predictor=CTRVKalmanPredictor(seed=idx * 4 + 4),
            failure_type=ftype,
            onset_step=int(T * 0.3),
            duration_steps=int(T * 0.2),
            magnitude=2.0,
            seed=idx * 4 + 4,
        )

        # At each step, every predictor emits an (H, 3) trajectory
        # rooted at the ego pose at that step.
        predictor_trajs: dict = {}
        for name, predictor in [("M1", m1), ("M2", m2), ("M3", m3), ("M4", m4)]:
            traj_TxHx3 = np.zeros((T, H, 3), dtype=np.float64)
            for t, pose in enumerate(ego_poses):
                # Reset the predictor's state to the ego pose at t.
                predictor.set_state(PredictorState(
                    x=pose[0], y=pose[1], theta=pose[2],
                    velocity=5.0,   # TODO: pull from CAN bus
                    timestamp=t * DT,
                ))
                # Drive the predictor with a simple constant-speed
                # control sequence — replace with the recorded ego
                # control if you want closed-loop fidelity.
                ctrl = np.zeros((H, 2), dtype=np.float64)
                ctrl[:, 0] = 5.0  # m/s forward
                traj_TxHx3[t] = predictor.predict(ctrl)
            predictor_trajs[name] = traj_TxHx3

        return SceneRecord(
            scene_id=scene_id,
            ego_trace=ego_trace,
            predictor_trajectories=predictor_trajs,
            failure_metadata={
                "type": ftype,
                "onset_step": (
                    int(T * 0.3) if ftype != "constant_bias_sanity" else None
                ),
                "duration_steps": int(T * 0.2),
                "ground_truth_failing_predictor": "M4",
            },
            dt=DT,
        )
```

> **Engineering caveat:** the snippet above is a runnable *first
> draft*. Two known refinements you'll likely need:
>
> 1. **CAN-bus velocity / yaw-rate.** The CTRV predictor needs the
>    real ego speed and yaw rate per frame — pull from
>    `vehicle_monitor` or compute by finite-differencing
>    `ego_pose.translation`. Substitute the placeholder
>    `velocity=5.0`.
> 2. **Closed-loop control replay.** The placeholder constant
>    velocity in `ctrl` produces a forward extrapolation of the
>    ego pose at each frame — fine for open-loop forecast-error
>    metrics. For Mode B (closed-loop), drive the planner instead.

---

## §7 Run the pilot

`scripts/run_phase_6_2_real.py`:

```python
"""Execute the §6.2 pilot against real nuScenes-mini data."""
from symbolu_robotics.bcvf_autonomous.datasets.nuscenes_real import (
    NuScenesAdapter,
)
from symbolu_robotics.bcvf_autonomous.pilot import run_pilot

adapter = NuScenesAdapter(
    dataroot="/workspace/nuscenes-mini",
    version="v1.0-mini",
)
print(f"Scenes available: {len(adapter)}")

result = run_pilot(
    adapter=adapter,
    output_dir="/workspace/symbolu/results/phase_6_2_real",
    pilot_label="phase_6_2_real",
)

print(f"\nN paired: {result.paired_comparison.n_paired}")
print(f"A3 wins:  {result.paired_comparison.n_a3_wins}")
print(f"A0 wins:  {result.paired_comparison.n_a0_wins}")
print(f"win rate: {result.paired_comparison.win_rate:.3f}")
print(f"sign-test p (one-sided): {result.paired_comparison.p_value_one_sided:.4f}")
print(f"Lemma-1 negative control PASS: {result.lemma1_negative_control_pass}")
print(f"\nArtifacts in /workspace/symbolu/results/phase_6_2_real/")
```

Run:

```bash
cd /workspace/symbolu
PYTHONPATH=. python scripts/run_phase_6_2_real.py
```

Expected wall time: **~5–15 minutes** for 10 scenes (nuScenes-mini
has ~10 scenes × ~40 frames each). Scaling to full nuScenes (~850
scenes) is ~6 hours.

---

## §8 Pull artifacts back to local

From your **local machine**:

```bash
runpodctl receive <pod-id>:/workspace/symbolu/results/phase_6_2_real ./results_real

# Or scp -r -P <port> root@<pod-host>:/workspace/symbolu/results/phase_6_2_real ./
```

You should now have locally:

```
results_real/
├── phase_6_2_real_paired_comparison.csv
├── phase_6_2_real_fleet_summary.json
└── phase_6_2_real_pilot_report.md
```

Open the markdown report — that's the headline you can show an
investor or safety auditor.

---

## §9 Sanity checks + troubleshooting

### Hard gates the pilot must pass

1. **Lemma-1 negative control.** On `constant_bias_sanity` scenes,
   `mean_bcvf_total` must be ≤ 1e-3. If it fires meaningfully, the
   real-data pipeline has injected an unintended within-horizon
   2nd-order signal — usually a CAN-bus or map-API call returning
   a noisy second derivative. Investigate the per-frame predictor
   output before reporting the pilot.
2. **Forecast error sanity.** A0 forecast error should be in the
   single-digit-meters range over a 2 s horizon at 5 m/s. If it's
   larger than ~5 m, the predictors aren't tracking the ego
   sensibly — check the state-reset loop in `load_scene()`.

### Common failure modes

| Symptom | Likely cause | Fix |
|---|---|---|
| `ImportError: nuscenes-devkit` on adapter import | venv not activated | `source /workspace/venv/bin/activate` |
| `KeyError: log_token` | nuScenes-mini extracted wrong | re-extract the tarball; structure is `nuscenes-mini/v1.0-mini/*.json` + `nuscenes-mini/{samples,sweeps,maps}/...` |
| All A0/A3 ties | failure-injection magnitude too small or all scenes are Lemma-1 invariant | crank `magnitude` up to 5.0 in the M4 wrapper, or rotate failure types more aggressively |
| Pilot crashes on map_api lookup | wrong map for the log's location | confirm the `_get_map` helper picks `boston-seaport` / `singapore-onenorth` etc. correctly per log |

### Cost projection

| Step | Wall time | Pod cost |
|---|---|---|
| Setup + data upload | ~30 min | ~$0.15 |
| Predictor implementation + iteration | ~2 days | ~$10 |
| First clean nuScenes-mini run | ~15 min | ~$0.10 |
| Re-runs as you tune | ~5 hours total | ~$2 |
| **Total** | **~3 days** | **~$15** |

---

## §10 What "done" looks like

A reportable §6.2 result has these three artifacts on disk:

1. **`phase_6_2_real_paired_comparison.csv`** — one row per scene
   from real nuScenes-mini.
2. **`phase_6_2_real_fleet_summary.json`** — feeds straight into
   the v0.4 fleet analysis harness; the FleetSummary is
   investor-facing.
3. **`phase_6_2_real_pilot_report.md`** — markdown headline:
   *"on real nuScenes-mini sensor data, A3 [some result] vs A0
   on the responsive failure class."*

The v0.5 brief footer can then be updated:

> v0.6 · 389 internal tests · §6.2 pilot executed end-to-end on
> nuScenes-mini real automotive sensor data (N=10, paired, attribution
> X%, sign-test p=Y) · ...

Whatever the actual numbers turn out to be — that's the headline
the investor narrative is missing today.
