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

from symbolu.cloud_controller.config import InfraControllerConfig, INFRA_KEYS, APP_KEYS, BUSINESS_KEYS
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

    # Identity
    identity_deviation: float       # How far current state is from learned baseline

    # Context
    step: int
    metrics_snapshot: Dict[str, float]

    def explain(self) -> str:
        """Human-readable decision explanation."""
        drift_label = "normal" if self.identity_deviation < 0.3 else (
            "drifting" if self.identity_deviation < 0.6 else "anomalous"
        )
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
            f"  Identity Drift:      {self.identity_deviation:.2f} ({drift_label})",
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
            warmup_steps=self.config.damping_warmup_steps,
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

        # Baseline-memory floor — remember recent capacity needs so the
        # controller doesn't collapse replicas to 1 immediately after a
        # high-demand period. Rises instantly, decays slowly (asymmetric).
        # Used only as a scale-in floor — never touches scale-out authority.
        self._recent_required_floor: float = 1.0
        self._floor_ratio: float = 0.8  # scale-in floor = 80% of recent peak

        # Pending replica tracking — detect actuation lag
        # Each entry: (step_issued, delta) — persists across cycles until realized or TTL expires
        self._pending_deltas: List[tuple] = []
        self._pending_ttl: int = 15  # max cycles to wait for delta to land
        self._last_replicas: Optional[int] = None  # previous cycle's replica count

        # Replica-drop detection — detect unplanned loss (spot eviction, OOM)
        self._unplanned_drop_boost: float = 0.0  # pressure boost after detected drop

        # Pressure trend detector — catch gradual drift that never crosses
        # a sharp threshold. Tracks a rolling window of pressure values and
        # computes monotonic-increase ratio. When pressure is steadily rising,
        # the trend boost nudges action_score above the decision threshold.
        self._pressure_history: List[float] = []
        self._trend_window: int = 20  # cycles to look back

        # Signal staleness detector — track per-metric values to detect
        # stuck/frozen signals (e.g., stale exporter cache, counter reset missed).
        # If a metric hasn't changed in N cycles, exclude it from pressure.
        self._metric_history: Dict[str, List[float]] = {}
        self._staleness_window: int = 10  # cycles of identical value = stale

        # Latency override — track latency trend for cascade detection
        self._latency_history: List[float] = []
        self._latency_override_active: bool = False

        # Demand upshift detector — when pressure transitions from negative
        # to positive while replicas are near the floor, the controller is
        # recovering from a trough. Boost positive pressure temporarily so
        # the weak initial positive signal can cross the action threshold.
        self._recovery_cycles: int = 0


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
        # Input validation — clamp metrics to [0, 1] and sanitize args
        metrics = {k: max(0.0, min(1.0, v)) for k, v in metrics.items()}
        current_replicas = max(1, current_replicas)
        recent_pod_restarts = max(0, recent_pod_restarts)

        self._step += 1

        # === SENSE ===
        # Detect unplanned replica loss (spot eviction, OOM kill, node failure)
        # If replicas dropped without the controller issuing a scale-in,
        # something external killed pods — boost pressure to compensate.
        pending_sum = sum(d for _, d in self._pending_deltas)
        if self._last_replicas is not None:
            expected_replicas = self._last_replicas + pending_sum
            actual_drop = expected_replicas - current_replicas
            if actual_drop > 0 and not any(d < 0 for _, d in self._pending_deltas):
                # Replicas decreased without any pending scale-in → unplanned loss
                self._unplanned_drop_boost = min(0.3, actual_drop * 0.1)
            else:
                # Decay the boost
                self._unplanned_drop_boost *= 0.7

        # Age out realized pending deltas: if actual replicas changed in the
        # direction of a pending delta, consider it landed. Keep entries for
        # up to _pending_ttl cycles, then expire them.
        if self._last_replicas is not None:
            realized = current_replicas - self._last_replicas
            remaining: List[tuple] = []
            for issued_step, d in self._pending_deltas:
                age = self._step - issued_step
                if age > self._pending_ttl:
                    continue  # expired — assume it landed or was lost
                if realized != 0 and ((d > 0 and realized > 0) or (d < 0 and realized < 0)):
                    # This delta likely just landed — consume it
                    realized -= d
                    continue
                # Blocked detection: if delta is >= 3 cycles old and replicas
                # haven't moved at all, the delta was likely blocked by an
                # external constraint (budget cap, resource quota). Don't let
                # blocked deltas suppress future scaling decisions.
                if age >= 3 and realized == 0:
                    continue  # blocked — expire early
                remaining.append((issued_step, d))
            self._pending_deltas = remaining

        self._last_replicas = current_replicas

        # Signal staleness: detect and exclude metrics stuck at the same value
        # (stale exporter cache, frozen counter). Must happen before pressure
        # computation so stale CPU=0.3 doesn't pull infra_pressure negative.
        metrics = self._filter_stale_signals(metrics)

        # Compute pressure signal (weighted normalized demand)
        pressure = self._compute_pressure(metrics)

        # Add unplanned-drop boost to pressure (compensates for lost capacity)
        pressure += self._unplanned_drop_boost

        # Trend detection: if pressure is monotonically rising over N cycles,
        # boost it slightly so gradual drift crosses the action threshold.
        self._pressure_history.append(pressure)
        if len(self._pressure_history) > self._trend_window:
            self._pressure_history = self._pressure_history[-self._trend_window:]
        trend_boost = self._compute_trend_boost()
        # Attenuate trend boost during startup — prevents massive cold-start overshoot
        if self._step < self.config.warmup_steps:
            trend_boost *= 0.3
        pressure += trend_boost

        # Demand upshift detection: when pressure crosses zero going positive
        # and replicas are near the floor, the controller is recovering from
        # a trough. Boost positive pressure so the weak initial signal can
        # cross the action threshold. Without this, ultra-gradual demand ramps
        # spend 30+ cycles in a dead zone where pressure is positive but A_t
        # is too low for any action. Only fires when at low replica count to
        # avoid amplifying overshoot in oscillatory scenarios.
        if (len(self._pressure_history) >= 2
                and self._pressure_history[-2] < 0
                and pressure >= 0
                and current_replicas <= 2):
            self._recovery_cycles = 20
        if self._recovery_cycles > 0 and pressure > 0 and current_replicas <= 3:
            pressure *= 2.5  # amplify weak positive pressure during recovery
            self._recovery_cycles -= 1

        # Latency override: if latency is critically high but pressure is
        # still low (e.g., CPU normal during upstream cascade), latency must
        # independently drive action. Without this, cascading failures where
        # CPU stays flat but latency climbs are invisible to the controller.
        pre_override_pressure = pressure
        pressure = self._apply_latency_override(metrics, pressure)
        self._latency_override_active = pressure > pre_override_pressure + 0.01

        # === BASELINE MEMORY ===
        # Update the capacity floor — tracks what the system recently needed.
        # Always tracks current replica count (the system WAS running at this
        # level for a reason). Rises instantly, decays slowly. Faster decay
        # when pressure is strongly negative (clearly over-provisioned) to
        # avoid holding unnecessary buffer in truly idle periods.
        needed_now = float(current_replicas)
        if pressure < -0.1:
            decay = 0.95  # faster decay in strongly low-demand periods
        else:
            decay = 0.98  # slow decay normally
        if needed_now > self._recent_required_floor:
            self._recent_required_floor = needed_now  # rise immediately
        else:
            self._recent_required_floor = (
                decay * self._recent_required_floor
                + (1.0 - decay) * needed_now
            )

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
        identity_deviation = 0.0
        if len(metrics) > 0:
            state_vec = self._metrics_to_identity_vector(metrics)
            identity_deviation = self.identity.deviation(state_vec)
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
            warmup_steps=self.config.warmup_steps,
        )

        # Damping: suppress if volatile
        damping_result = self.damping.compute(
            metric_variance=metric_variance,
            coherence_instability=coherence_result.instability,
        )

        # Final action score: A_t = d_t * G_t * P_t * S_t
        # When latency override is active (cascade detected), use a floor
        # on the multiplicative chain to prevent coherence/damping from
        # completely suppressing the cascade signal.
        effective_gain = gain_result.gain
        effective_damping = damping_result.damping
        if self._latency_override_active:
            effective_gain = max(effective_gain, 0.8)
            effective_damping = max(effective_damping, 0.7)

        action_score = (
            effective_damping
            * effective_gain
            * plasticity_result.plasticity
            * pressure
        )

        # Pending capacity suppression: if there are unrealized scale-out
        # deltas in flight, suppress additional scale-out to prevent the
        # feedback delay loop from compounding overshoot.
        pending_out = sum(d for _, d in self._pending_deltas if d > 0)
        if pending_out > 0 and action_score > 0:
            # Dampen action score proportionally to pending capacity
            suppression = min(0.8, pending_out * 0.15)
            action_score *= (1.0 - suppression)

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
            self._pending_deltas.append((self._step, replica_delta))
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
            identity_deviation=identity_deviation,
            step=self._step,
            metrics_snapshot=dict(metrics),
        )

    def _compute_pressure(self, metrics: Dict[str, float]) -> float:
        """Compute weighted pressure signal from normalized metrics.

        Pressure is positive when system needs more resources,
        negative when over-provisioned.

        When a signal group has no data (all keys missing), its weight
        is redistributed to groups that do have data. This prevents
        partial observability (e.g., CPU metric gone) from suppressing
        pressure to zero when remaining signals clearly show load.
        """
        infra_has_data = any(k in metrics for k in INFRA_KEYS)
        app_has_data = any(k in metrics for k in APP_KEYS)
        business_has_data = any(k in metrics for k in BUSINESS_KEYS)

        infra_pressure = self._group_pressure(metrics, INFRA_KEYS)
        app_pressure = self._group_pressure(metrics, APP_KEYS)
        business_pressure = self._group_pressure(metrics, BUSINESS_KEYS)

        # Build weighted sum only from groups that have data,
        # redistributing missing-group weight proportionally.
        weighted_sum = 0.0
        total_weight = 0.0

        if infra_has_data:
            weighted_sum += self.config.w_infra * infra_pressure
            total_weight += self.config.w_infra
        if app_has_data:
            weighted_sum += self.config.w_app * app_pressure
            total_weight += self.config.w_app
        if business_has_data:
            weighted_sum += self.config.w_business * business_pressure
            total_weight += self.config.w_business

        if total_weight == 0:
            return 0.0

        return weighted_sum / total_weight

    @staticmethod
    def _group_pressure(
        metrics: Dict[str, float],
        keys: list,
        invert_keys: tuple = ("error_rate",),
    ) -> float:
        """Average pressure from a signal group. Values above 0.5 = positive pressure.

        For inverted metrics (like error_rate), high values mean BAD, but low
        values should NOT create negative pressure (suggesting scale-in).
        error_rate=0.0 means "everything is fine", not "over-provisioned".
        """
        values = []
        for k in keys:
            if k not in metrics:
                continue
            v = metrics[k]
            if k in invert_keys:
                # Inverted: only contributes positive pressure (bad is high),
                # but 0.0 means fine — not over-provisioned
                values.append(max(0.0, v - 0.5))
            else:
                values.append(v - 0.5)
        if not values:
            return 0.0
        return sum(values) / len(values)

    def _apply_latency_override(
        self, metrics: Dict[str, float], pressure: float,
    ) -> float:
        """Latency floor override — makes latency a first-class actuator.

        Only activates when latency is critically high AND infra signals
        are calm (the cascade signature: CPU normal, latency climbing).
        This prevents the override from firing when conflicting signals
        cause high latency but low CPU as a test of coherence.

        The key distinguisher: in a true cascade, latency rises *over time*
        while CPU stays flat. In a conflicting-signals scenario, the
        disagreement is injected instantaneously.
        """
        latency = metrics.get("latency_p99", 0.0)
        cpu = metrics.get("cpu", None)
        error_rate = metrics.get("error_rate", 0.0)

        # Track latency trend
        self._latency_history.append(latency)
        if len(self._latency_history) > 10:
            self._latency_history = self._latency_history[-10:]

        # Only activate when CPU is calm or absent AND latency has been
        # rising over multiple cycles (cascade signature). CPU missing
        # (filtered by staleness) is an even stronger cascade signal.
        # Use a 10-cycle window since cascades build slowly (~0.008/cycle).
        cpu_calm_or_absent = cpu is None or cpu < 0.5
        window_size = min(10, len(self._latency_history))
        if window_size >= 5 and cpu_calm_or_absent:
            recent = self._latency_history[-window_size:]
            latency_rising = recent[-1] > recent[0] + 0.03

            if latency_rising and latency > 0.6:
                # Cascade detected: latency climbing while CPU flat/absent
                latency_pressure = (latency - 0.3) * 0.8
                if error_rate > 0.1:
                    latency_pressure += error_rate * 0.3
                pressure = max(pressure, latency_pressure)

        return pressure

    def _filter_stale_signals(self, metrics: Dict[str, float]) -> Dict[str, float]:
        """Detect and exclude metrics whose value hasn't changed.

        If a metric has reported the same value (within tolerance) for
        _staleness_window consecutive cycles while other metrics are
        changing, it's likely stale (frozen exporter, missed counter
        reset). Exclude it from pressure computation to prevent a
        stale low value from actively counteracting real pressure.
        """
        # Update history
        for key, value in metrics.items():
            if key not in self._metric_history:
                self._metric_history[key] = []
            self._metric_history[key].append(value)
            if len(self._metric_history[key]) > self._staleness_window:
                self._metric_history[key] = self._metric_history[key][-self._staleness_window:]

        if self._step < self._staleness_window:
            return metrics  # Not enough history yet

        # Check each metric for staleness
        stale_keys = set()
        for key, history in self._metric_history.items():
            if len(history) < self._staleness_window:
                continue
            # All values within 0.01 of each other = stuck
            if max(history) - min(history) < 0.01:
                stale_keys.add(key)

        if not stale_keys:
            return metrics

        # Only exclude stale metrics if other metrics ARE changing
        # (if everything is stable, nothing is "stale" — the system is just idle)
        non_stale_changing = False
        for key, history in self._metric_history.items():
            if key not in stale_keys and len(history) >= self._staleness_window:
                if max(history) - min(history) > 0.02:
                    non_stale_changing = True
                    break

        if not non_stale_changing:
            return metrics  # System is genuinely idle

        return {k: v for k, v in metrics.items() if k not in stale_keys}

    def _compute_trend_boost(self) -> float:
        """Detect monotonically rising pressure and return a small boost.

        If the last N pressure readings are mostly increasing (>70% of
        consecutive pairs are non-decreasing), the system is under slow
        but steady load growth. Return a boost proportional to the
        total rise, capped at 0.1 to prevent runaway.

        This catches the "frog in boiling water" pattern where demand
        creeps up 0.003/cycle and never triggers a sharp threshold.
        """
        history = self._pressure_history
        if len(history) < 10:
            return 0.0

        # Count increasing pairs
        increases = sum(
            1 for i in range(1, len(history))
            if history[i] >= history[i - 1] - 0.005  # small tolerance for noise
        )
        ratio = increases / (len(history) - 1)

        if ratio < 0.7:
            return 0.0

        # Total rise over the window
        total_rise = history[-1] - history[0]
        if total_rise <= 0:
            return 0.0

        # Boost proportional to rise, scaled by how sustained the trend is
        # (longer sustained monotonic rise = more confidence it's real drift)
        sustained_factor = min(2.0, ratio / 0.7)  # 1.0 at threshold, up to 2.0
        return min(0.15, total_rise * 0.7 * sustained_factor)

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

        Keys are sorted for deterministic ordering — dict iteration order
        depends on insertion order, which may vary between calls.
        Pads or truncates to identity_dim.
        """
        values = [metrics[k] for k in sorted(metrics.keys())]
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

        # Asymmetric scale-in: require 2x the action score to scale in.
        # This prevents aggressive scale-in during low-demand phases,
        # keeping more replicas available as a hedge against demand spikes.
        # Scale-out thresholds are unchanged — react quickly to load.
        if sign < 0:
            scale_in_factor = 2.0
        else:
            scale_in_factor = 1.0

        if abs_score < thresholds.get("no_action", 0.05) * scale_in_factor:
            return "no_action", 0
        elif abs_score < thresholds.get("recommend", 0.2) * scale_in_factor:
            return f"observe_{direction}", 0
        elif abs_score < thresholds.get("scale_1", 0.5) * scale_in_factor:
            delta = sign * 1
        elif abs_score < thresholds.get("scale_2", 1.0) * scale_in_factor:
            delta = sign * 2
        else:
            delta = sign * 3

        # Startup clamp: limit max delta during warmup to prevent
        # cold-start amplification (trend detector + gain ramp = overshoot)
        if self._step < self.config.warmup_steps:
            delta = max(-1, min(1, delta))

        # Apply safety bounds
        if delta > 0:
            max_out = max(1, int(current_replicas * self.config.max_scale_out_ratio))
            delta = min(delta, max_out)
        elif delta < 0:
            max_in = max(1, int(current_replicas * self.config.max_scale_in_ratio))
            delta = max(delta, -max_in)
            # Scale-in step cap: limit to -1 per cycle. Scale-out can add
            # +1, +2, +3 but scale-in is always gradual. This prevents
            # rapid capacity collapse while allowing steady cost recovery.
            delta = max(delta, -1)
            # Never go below minimum
            if current_replicas + delta < self.config.min_replicas:
                delta = self.config.min_replicas - current_replicas
            # Baseline-memory floor: don't scale in below a fraction of
            # what the system recently needed. Prevents collapsing to 1
            # replica immediately after a high-demand period.
            scale_in_floor = max(1, int(round(
                self._recent_required_floor * self._floor_ratio
            )))
            if current_replicas + delta < scale_in_floor:
                delta = scale_in_floor - current_replicas
                if delta >= 0:
                    delta = 0  # floor reached — don't scale in further

        if delta > 0:
            return f"scale_out_{delta}", delta
        elif delta < 0:
            return f"scale_in_{abs(delta)}", delta
        else:
            return "no_action", 0

    def bootstrap(self, historical_snapshots: List[Dict[str, float]]) -> None:
        """Pre-learn baselines from historical metrics so the controller acts from cycle 1.

        Replays historical metric snapshots through all internal modules:
        - Identity EMA learns what "normal" looks like
        - Damping calibrates its variance baseline
        - Adaptive gain skips the warmup ramp
        - Plasticity gate's double-smoothed resistance stabilizes

        This eliminates the learning phase — the controller is ready to make
        coherence-gated decisions immediately, like Cast AI's fixed thresholds
        but with the full adaptive control equation.

        Args:
            historical_snapshots: List of metric dicts (oldest first), each with
                keys like "cpu", "memory", "latency_p99", etc. Values in [0, 1].
                Typically 100-500 snapshots covering 30min-2hr of history.
        """
        if not historical_snapshots:
            return

        with self._lock:
            self._bootstrap_inner(historical_snapshots)

    def _bootstrap_inner(self, historical_snapshots: List[Dict[str, float]]) -> None:
        """Bootstrap logic, called under lock."""
        # 1. Bootstrap Identity EMA — replay vectors to learn baseline
        identity_vectors = []
        for snap in historical_snapshots:
            if snap:
                vec = self._metrics_to_identity_vector(snap)
                identity_vectors.append(vec)
        self.identity.bootstrap(identity_vectors)

        # 2. Bootstrap Damping — compute variance history from snapshots
        variance_history = []
        for snap in historical_snapshots:
            values = list(snap.values())
            if len(values) >= 2:
                variance_history.append(float(np.var(values)))
            elif values:
                variance_history.append(0.0)
        self.damping.bootstrap(variance_history)

        # 3. Bootstrap Adaptive Gain — skip warmup ramp
        self.adaptive_gain.bootstrap()

        # 4. Warm up plasticity gate's double-smoothed resistance by replaying
        #    a subset of snapshots through the resistance computation
        for snap in historical_snapshots[-50:]:
            snap_clamped = {k: max(0.0, min(1.0, v)) for k, v in snap.items()}
            resistance = self._compute_resistance(
                snap_clamped, deploy_active=False, recent_pod_restarts=0,
            )
            self.plasticity_gate.compute(resistance=resistance, misalignment=0.1)

        # 5. Set step counter so warmup_steps are considered elapsed
        self._step = max(self._step, self.config.warmup_steps)

    @property
    def bootstrapped(self) -> bool:
        """Whether the controller has been bootstrapped with historical data."""
        return self.adaptive_gain.bootstrapped and self.identity.bootstrapped

    def reset(self) -> None:
        """Reset all internal state. Thread-safe."""
        with self._lock:
            self.plasticity_gate.reset()
            self.adaptive_gain.reset()
            self.damping.reset(warmup_steps=self.config.damping_warmup_steps)
            self.identity.reset()
            self.replay_buffer = ReplayBuffer(
                capacity=self.config.replay_buffer_size,
                ttl=self.config.replay_ttl,
            )
            self._step = 0
            self._recent_scale_times = []
            self._pending_deltas = []
            self._last_replicas = None
            self._unplanned_drop_boost = 0.0
            self._pressure_history = []
            self._metric_history = {}
            self._latency_history = []
            self._latency_override_active = False
            self._recovery_cycles = 0
            self._recent_required_floor = 1.0
