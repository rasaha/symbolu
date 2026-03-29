"""Main Controller — Sense -> Interpret -> Decide -> Act -> Learn.

Wires together all core modules into a single step() function.
No cloud dependencies — accepts a metrics dict, returns an ActionResult.
Cloud connectors (Prometheus, K8s) are plugged in externally.

Core equation:
    Action_t = d_t * G_t * P_t * S_t
"""

import math
import threading
import numpy as np
from dataclasses import dataclass
from typing import Dict, List, Optional

from symbolu.cloud_controller.config import InfraControllerConfig
from symbolu.cloud_controller.core.plasticity_gate import PlasticityGate, PlasticityResult
from symbolu.cloud_controller.core.adaptive_gain import AdaptiveGain, GainResult
from symbolu.cloud_controller.core.damping import Damping, DampingResult
from symbolu.cloud_controller.core.identity_ema import IdentityEMA
from symbolu.cloud_controller.core.coherence import CoherenceModel, CoherenceResult
from symbolu.cloud_controller.core.replay_buffer import ReplayBuffer


@dataclass
class ActionResult:
    """Complete decision output with full explainability."""

    # Final decision
    action_score: float             # A_t = d_t * G_t * P_t * S_t
    recommendation: str             # "no_action", "scale_out_1", "scale_in_1", etc.
    replica_delta: int              # +N or -N replicas suggested

    # Pressure
    pressure: float                 # S_t: weighted normalized demand

    # Component breakdown (explainability)
    plasticity: PlasticityResult
    gain: GainResult
    damping: DampingResult
    coherence: CoherenceResult

    # Context
    step: int
    metrics_snapshot: Dict[str, float]

    def explain(self) -> str:
        """Human-readable decision explanation."""
        lines = [
            f"Decision: {self.recommendation.upper().replace('_', ' ')}",
            f"  Pressure (S_t):      {self.pressure:.2f}",
            f"  Coherence (C_t):     {self.coherence.coherence:.2f} "
            f"({'coherent' if self.coherence.coherence > 0.6 else 'incoherent'}"
            f" — {self.coherence.elevated_count} signals elevated)",
            f"  Stability (R_t):     {self.plasticity.resistance:.2f}",
            f"  Misalignment (M_t):  {self.plasticity.misalignment:.2f}",
            f"  Plasticity (P_t):    {self.plasticity.plasticity:.2f} "
            f"({'open' if self.plasticity.plasticity > 0.5 else 'closed'})",
            f"  Gain (G_t):          {self.gain.gain:.2f}"
            f"{' [rate-limited]' if self.gain.rate_limited else ''}",
            f"  Damping (d_t):       {self.damping.damping:.2f}"
            f"{' [rate-limited]' if self.damping.rate_limited else ''}",
            f"  Action Score (A_t):  {self.action_score:.3f}"
            f" → {self.recommendation.upper().replace('_', ' ')}",
        ]
        return "\n".join(lines)


class Controller:
    """Neural Cloud Scaling Controller.

    Accepts normalized metrics, produces scaling decisions with full
    explainability. No cloud provider dependencies — pure control logic.

    Usage:
        ctrl = Controller(InfraControllerConfig())
        result = ctrl.step(
            metrics={"cpu": 0.82, "latency_p99": 0.65, ...},
            current_replicas=5,
            deploy_active=False,
            phase="peak",
        )
        print(result.explain())
    """

    def __init__(self, config: Optional[InfraControllerConfig] = None):
        self.config = config or InfraControllerConfig()

        # Core modules
        self.plasticity_gate = PlasticityGate(
            k_r=self.config.k_r,
            k_m=self.config.k_m,
            b_p=self.config.b_p,
        )
        self.adaptive_gain = AdaptiveGain(
            G_base=self.config.G_base,
            G_min=self.config.G_min,
            G_max=self.config.G_max,
        )
        self.damping = Damping(
            k_dv=self.config.k_dv,
            k_dc=self.config.k_dc,
        )
        self.identity = IdentityEMA(
            dim=self.config.identity_dim,
            alpha_base=self.config.alpha_base,
        )
        self.coherence_model = CoherenceModel(
            w_infra=self.config.w_infra,
            w_app=self.config.w_app,
            w_business=self.config.w_business,
        )
        self.replay_buffer = ReplayBuffer(
            capacity=self.config.replay_buffer_size,
            ttl=self.config.replay_ttl,
        )

        self._step = 0
        self._recent_scale_times: List[int] = []
        self._lock = threading.Lock()

    def step(
        self,
        metrics: Dict[str, float],
        current_replicas: int = 1,
        deploy_active: bool = False,
        phase: str = "normal",
        recent_pod_restarts: int = 0,
    ) -> ActionResult:
        """Execute one control cycle.

        Args:
            metrics: Normalized metric values in [0, 1].
                Expected keys: "cpu", "memory", "latency_p99", "error_rate",
                "queue_depth", "request_rate". Missing keys are ignored.
            current_replicas: Current number of running replicas.
            deploy_active: Whether a deployment/rollout is currently in progress.
            phase: Time context — "peak", "normal", "off_peak", "maintenance".
            recent_pod_restarts: Number of pod restarts in recent window.

        Returns:
            ActionResult with decision, component breakdown, and explanation.
        """
        with self._lock:
            return self._step_inner(
                metrics, current_replicas, deploy_active, phase, recent_pod_restarts,
            )

    def _step_inner(
        self,
        metrics: Dict[str, float],
        current_replicas: int,
        deploy_active: bool,
        phase: str,
        recent_pod_restarts: int,
    ) -> ActionResult:
        """Inner step logic, called under lock."""
        self._step += 1

        # === SENSE ===
        # Compute pressure signal (weighted normalized demand)
        pressure = self._compute_pressure(metrics)

        # === INTERPRET ===
        # Coherence: do the signals agree?
        coherence_result = self.coherence_model.compute(metrics)

        # Resistance: how stable is the system?
        resistance = self._compute_resistance(
            metrics, deploy_active, recent_pod_restarts,
        )

        # Metric variance (for damping)
        metric_values = list(metrics.values())
        metric_variance = float(np.var(metric_values)) if metric_values else 0.0

        # Misalignment: how big is the proposed change?
        # Estimate: pressure * G_base gives rough scaling magnitude
        estimated_delta = abs(pressure * self.config.G_base)
        misalignment = estimated_delta / max(current_replicas, 1)

        # Identity accumulation (fast loop)
        # _metrics_to_identity_vector pads to identity_dim, so any metrics count works
        if len(metrics) > 0:
            state_vec = self._metrics_to_identity_vector(metrics)
            salience = coherence_result.coherence  # High coherence = high salience
            self.identity.accumulate(state_vec, salience)

        # Identity consolidation (slow loop)
        if self._step % self.config.consolidation_interval == 0:
            self.identity.consolidate()

        # === DECIDE ===
        # Plasticity gate: is it safe to act?
        plasticity_result = self.plasticity_gate.compute(
            resistance=resistance,
            misalignment=misalignment,
        )

        # Adaptive gain: how aggressively?
        gain_result = self.adaptive_gain.compute(
            coherence=coherence_result.coherence,
            phase=phase,
            step=self._step,
            warmup_steps=100,
        )

        # Damping: suppress if volatile
        damping_result = self.damping.compute(
            metric_variance=metric_variance,
            coherence_instability=coherence_result.instability,
        )

        # Final action score: A_t = d_t * G_t * P_t * S_t
        action_score = (
            damping_result.damping
            * gain_result.gain
            * plasticity_result.plasticity
            * pressure
        )

        # Map to recommendation
        recommendation, replica_delta = self._score_to_action(
            action_score, current_replicas,
        )

        # === LEARN ===
        # Store to replay if high misalignment + low plasticity
        if misalignment > 0.3 and plasticity_result.plasticity < 0.4:
            self.replay_buffer.store(
                {
                    "metrics": dict(metrics),
                    "coherence": coherence_result.coherence,
                    "plasticity": plasticity_result.plasticity,
                    "action_score": action_score,
                    "recommendation": recommendation,
                    "resistance": resistance,
                    "priority": misalignment * (1.0 - plasticity_result.plasticity),
                },
                step=self._step,
            )

        # Prune stale replay entries
        if self._step % self.config.replay_interval == 0:
            self.replay_buffer.prune(self._step)

        # Track scaling actions for resistance calculation
        if abs(replica_delta) > 0:
            self._recent_scale_times.append(self._step)
        # Keep only last 20 scale events
        self._recent_scale_times = self._recent_scale_times[-20:]

        return ActionResult(
            action_score=action_score,
            recommendation=recommendation,
            replica_delta=replica_delta,
            pressure=pressure,
            plasticity=plasticity_result,
            gain=gain_result,
            damping=damping_result,
            coherence=coherence_result,
            step=self._step,
            metrics_snapshot=dict(metrics),
        )

    def _compute_pressure(self, metrics: Dict[str, float]) -> float:
        """Compute weighted pressure signal from normalized metrics.

        Pressure is positive when system needs more resources,
        negative when over-provisioned.
        """
        infra_keys = ["cpu", "memory"]
        app_keys = ["latency_p99", "error_rate"]
        business_keys = ["queue_depth"]

        infra_pressure = self._group_pressure(metrics, infra_keys)
        app_pressure = self._group_pressure(metrics, app_keys)
        business_pressure = self._group_pressure(metrics, business_keys)

        total_weight = self.config.w_infra + self.config.w_app
        if any(k in metrics for k in business_keys):
            total_weight += self.config.w_business
            pressure = (
                self.config.w_infra * infra_pressure
                + self.config.w_app * app_pressure
                + self.config.w_business * business_pressure
            ) / total_weight
        else:
            pressure = (
                self.config.w_infra * infra_pressure
                + self.config.w_app * app_pressure
            ) / total_weight

        return pressure

    @staticmethod
    def _group_pressure(metrics: Dict[str, float], keys: list) -> float:
        """Average pressure from a signal group. Values above 0.5 = positive pressure."""
        values = [metrics[k] for k in keys if k in metrics]
        if not values:
            return 0.0
        return sum(v - 0.5 for v in values) / len(values)  # Centered at 0

    def _compute_resistance(
        self,
        metrics: Dict[str, float],
        deploy_active: bool,
        recent_pod_restarts: int,
    ) -> float:
        """Compute system stability score in [0, 1].

        1.0 = fully stable, 0.0 = highly fragile.

        Uses multiplicative penalties to prevent stacking beyond 1.0:
        each penalty reduces remaining resistance rather than subtracting
        from a fixed budget.
        """
        resistance = 1.0

        # Penalty for active deployment
        if deploy_active:
            resistance *= 0.6  # 40% penalty

        # Penalty for recent pod restarts
        if recent_pod_restarts > 0:
            restart_factor = max(0.5, 1.0 - recent_pod_restarts * 0.1)
            resistance *= restart_factor

        # Penalty for recent scaling actions (thrash detection)
        recent_scales = sum(
            1 for t in self._recent_scale_times
            if self._step - t < 20  # Within last 20 cycles (~5 min at 15s intervals)
        )
        if recent_scales > 0:
            thrash_factor = max(0.5, 1.0 - recent_scales * 0.1)
            resistance *= thrash_factor

        # Penalty for high metric variance (signals are noisy)
        values = list(metrics.values())
        if len(values) >= 2:
            variance = float(np.var(values))
            variance_factor = max(0.7, 1.0 - variance * 2.0)
            resistance *= variance_factor

        return max(0.0, min(1.0, resistance))

    def _metrics_to_identity_vector(self, metrics: Dict[str, float]) -> np.ndarray:
        """Convert metrics dict to fixed-dimension identity vector.

        Pads or truncates to identity_dim.
        """
        values = list(metrics.values())
        vec = np.zeros(self.config.identity_dim)
        n = min(len(values), self.config.identity_dim)
        vec[:n] = values[:n]
        return vec

    def _score_to_action(
        self,
        action_score: float,
        current_replicas: int,
    ) -> tuple:
        """Map action score to a recommendation and replica delta.

        Returns:
            (recommendation_string, replica_delta_int)
        """
        thresholds = self.config.action_thresholds
        abs_score = abs(action_score)
        sign = 1 if action_score >= 0 else -1
        direction = "out" if sign > 0 else "in"

        if abs_score < thresholds.get("no_action", 0.05):
            return "no_action", 0
        elif abs_score < thresholds.get("recommend", 0.2):
            return f"observe_{direction}", 0
        elif abs_score < thresholds.get("scale_1", 0.5):
            delta = sign * 1
        elif abs_score < thresholds.get("scale_2", 1.0):
            delta = sign * 2
        else:
            delta = sign * 3

        # Apply safety bounds
        if delta > 0:
            max_out = max(1, int(current_replicas * self.config.max_scale_out_ratio))
            delta = min(delta, max_out)
        elif delta < 0:
            max_in = max(1, int(current_replicas * self.config.max_scale_in_ratio))
            delta = max(delta, -max_in)
            # Never go below minimum
            if current_replicas + delta < self.config.min_replicas:
                delta = self.config.min_replicas - current_replicas

        if delta > 0:
            return f"scale_out_{delta}", delta
        elif delta < 0:
            return f"scale_in_{abs(delta)}", delta
        else:
            return "no_action", 0

    def reset(self) -> None:
        """Reset all internal state."""
        self.plasticity_gate.reset()
        self.adaptive_gain.reset()
        self.damping.reset()
        self.identity.reset()
        self.replay_buffer = ReplayBuffer(
            capacity=self.config.replay_buffer_size,
            ttl=self.config.replay_ttl,
        )
        self._step = 0
        self._recent_scale_times = []
