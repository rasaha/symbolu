"""
Sovereign Metrics — Runtime-Safe Extractions (Phase S2).

Pure-Python, float-friendly versions of sovereign health monitoring logic
extracted from metrics.py. These can be consumed by the governance pipeline
without importing PyTorch.

Extracted pieces:
- AlertConfig / SovereignAlertState / check_sovereign_alert(): Alert state machine
- StabilityState / check_stability_constraint(): S8 entropy brake logic
- get_entropy_status(): Entropy classification
- SovereignHealthSummary: Structured health snapshot for governance

The original tensor-based implementations remain in metrics.py for training use.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


# =========================================================================
# Entropy status (pure function, extracted from metrics.py)
# =========================================================================

def get_entropy_status(entropy: float) -> Tuple[str, str]:
    """Classify normalized entropy [0, 1] into sovereign cognitive state.

    Returns:
        (indicator, status_name) where status_name is one of:
        SATTVIC, FOCUSED, BALANCED, RAJASIC, NIDRA
    """
    if entropy < 0.30:
        return "SATTVIC_CLARITY", "SATTVIC"
    elif entropy < 0.50:
        return "HIGH_PRECISION", "FOCUSED"
    elif entropy < 0.70:
        return "CREATIVE_EXPLORATION", "BALANCED"
    elif entropy < 0.85:
        return "CONFUSION_RISK", "RAJASIC"
    else:
        return "COLLAPSE_RISK", "NIDRA"


# =========================================================================
# S8 Stability Constraint (pure Python, extracted from metrics.py)
# =========================================================================

@dataclass
class StabilityState:
    """Tracks entropy history for the S8 stability constraint."""
    entropy_history: List[float] = field(default_factory=list)
    window_size: int = 5
    inertial_brake_active: bool = False
    brake_trigger_step: int = -1


def check_stability_constraint(
    current_entropy: float,
    state: StabilityState,
    current_step: int,
    brake_duration: int = 100,
) -> Tuple[bool, StabilityState]:
    """[Formula S8] Check entropy rate and apply inertial brake if needed.

    Pure-Python equivalent of SovereignMetrics.check_stability_constraint().

    Returns:
        (brake_active, updated_state)
    """
    state.entropy_history.append(current_entropy)
    if len(state.entropy_history) > state.window_size:
        state.entropy_history.pop(0)

    # Brake still active?
    if state.inertial_brake_active:
        steps_since = current_step - state.brake_trigger_step
        if steps_since < brake_duration:
            return True, state
        else:
            state.inertial_brake_active = False
            state.brake_trigger_step = -1

    if len(state.entropy_history) < state.window_size:
        return False, state

    # Check for consistently increasing entropy
    increasing = sum(
        1 for i in range(1, len(state.entropy_history))
        if state.entropy_history[i] > state.entropy_history[i - 1]
    )
    threshold = (state.window_size - 1) * 0.6

    if increasing >= threshold:
        state.inertial_brake_active = True
        state.brake_trigger_step = current_step
        return True, state

    return False, state


# =========================================================================
# Alert Monitor (pure Python state machine, extracted from metrics.py)
# =========================================================================

@dataclass
class AlertConfig:
    """Threshold configuration for sovereign alert monitoring."""
    sa_ratio_danger: float = 0.55
    gc_danger: float = 0.25
    consistency_danger: float = 0.45
    entropy_spike_threshold: float = 0.15

    # Recovery targets
    sa_ratio_healthy_min: float = 0.25
    sa_ratio_healthy_max: float = 0.40
    gc_healthy: float = 0.80
    consistency_healthy: float = 0.10


# Valid alert states
ALERT_STATES = ("STABLE", "ALERT", "LOCKDOWN_ACTIVE", "RECOVERING")


@dataclass
class SovereignAlertState:
    """Snapshot of the sovereign alert state machine."""
    state: str = "STABLE"
    lockdown_count: int = 0
    recovery_streak: int = 0
    prev_entropy: Optional[float] = None


def check_sovereign_alert(
    metrics: Dict[str, float],
    alert_state: SovereignAlertState,
    config: Optional[AlertConfig] = None,
) -> Tuple[SovereignAlertState, List[str]]:
    """Evaluate sovereign health metrics and advance alert state machine.

    Pure-Python equivalent of SovereignAlertMonitor.check().
    Does not mutate external objects (PID controller, gradient scaler);
    instead returns action descriptions for the caller to interpret.

    Args:
        metrics: Dict with optional keys: sa_ratio, guna_coherence/gc,
            l_consistency, entropy.
        alert_state: Current state machine snapshot (will be mutated).
        config: Alert thresholds. Defaults to AlertConfig().

    Returns:
        (updated_alert_state, action_strings)
    """
    if config is None:
        config = AlertConfig()

    actions: List[str] = []

    sa_ratio = metrics.get("sa_ratio", metrics.get("s_a_ratio", 0.35))
    gc = metrics.get("guna_coherence", metrics.get("gc", metrics.get("coherence", 0.5)))
    consistency = metrics.get("l_consistency", 0.0)
    entropy = metrics.get("entropy", 0.0)

    is_sa_danger = sa_ratio > config.sa_ratio_danger
    is_gc_danger = gc < config.gc_danger
    is_consistency_danger = consistency > config.consistency_danger

    is_entropy_spike = False
    if alert_state.prev_entropy is not None and alert_state.prev_entropy > 0:
        entropy_change = (entropy - alert_state.prev_entropy) / alert_state.prev_entropy
        is_entropy_spike = entropy_change > config.entropy_spike_threshold
    alert_state.prev_entropy = entropy

    danger_count = sum([is_sa_danger, is_gc_danger, is_consistency_danger, is_entropy_spike])

    if danger_count >= 2 or (is_sa_danger and is_gc_danger):
        if alert_state.state != "LOCKDOWN_ACTIVE":
            alert_state.state = "LOCKDOWN_ACTIVE"
            alert_state.lockdown_count += 1
            actions.append(
                f"LOCKDOWN: sa_ratio={sa_ratio:.2f} gc={gc:.2f} "
                f"consistency={consistency:.3f}"
            )
        alert_state.recovery_streak = 0

    elif alert_state.state == "LOCKDOWN_ACTIVE":
        is_recovering = (
            sa_ratio <= config.sa_ratio_healthy_max
            and gc >= config.gc_danger * 1.5
        )
        if is_recovering:
            alert_state.recovery_streak += 1
            if alert_state.recovery_streak >= 5:
                alert_state.state = "RECOVERING"
                actions.append("RECOVERING: metrics improving")
        else:
            alert_state.recovery_streak = 0

    elif alert_state.state == "RECOVERING":
        is_sattvic = (
            config.sa_ratio_healthy_min <= sa_ratio <= config.sa_ratio_healthy_max
            and gc >= config.gc_healthy
            and consistency <= config.consistency_healthy
        )
        if is_sattvic:
            alert_state.state = "STABLE"
            actions.append("STABLE: sattvic state restored")
        elif danger_count >= 2:
            alert_state.state = "LOCKDOWN_ACTIVE"
            alert_state.lockdown_count += 1
            actions.append("RELAPSE: returning to lockdown")

    elif danger_count == 1:
        if alert_state.state == "STABLE":
            alert_state.state = "ALERT"
            trigger = (
                "S/A" if is_sa_danger else
                "GC" if is_gc_danger else
                "Consistency" if is_consistency_danger else
                "Entropy"
            )
            actions.append(f"ALERT: {trigger} approaching danger zone")
    else:
        if alert_state.state == "ALERT":
            alert_state.state = "STABLE"

    return alert_state, actions


# =========================================================================
# Sovereign Health Summary (structured output for governance)
# =========================================================================

@dataclass(frozen=True)
class SovereignHealthSummary:
    """Structured sovereign health snapshot for governance consumption.

    All fields are plain Python types — no tensors.
    """
    alert_state: str  # STABLE / ALERT / LOCKDOWN_ACTIVE / RECOVERING
    lockdown_count: int
    entropy_status: str  # SATTVIC / FOCUSED / BALANCED / RAJASIC / NIDRA
    entropy_indicator: str  # human-readable indicator
    inertial_brake_active: bool
    alert_actions: Tuple[str, ...]  # actions from latest alert check
    source: str = "sovereign_metrics_runtime"

    def to_audit_dict(self) -> Dict[str, object]:
        """Serialize for governance audit."""
        return {
            "alert_state": self.alert_state,
            "lockdown_count": self.lockdown_count,
            "entropy_status": self.entropy_status,
            "entropy_indicator": self.entropy_indicator,
            "inertial_brake_active": self.inertial_brake_active,
            "alert_actions": list(self.alert_actions),
            "source": self.source,
        }

    @property
    def is_lockdown(self) -> bool:
        return self.alert_state == "LOCKDOWN_ACTIVE"

    @property
    def is_degraded(self) -> bool:
        """True if alert state is anything other than STABLE."""
        return self.alert_state != "STABLE"


def build_health_summary(
    *,
    alert_state: SovereignAlertState,
    alert_actions: List[str],
    entropy: Optional[float] = None,
    brake_active: bool = False,
) -> SovereignHealthSummary:
    """Build a SovereignHealthSummary from runtime-safe components."""
    if entropy is not None:
        indicator, status = get_entropy_status(entropy)
    else:
        indicator, status = "UNKNOWN", "UNKNOWN"

    return SovereignHealthSummary(
        alert_state=alert_state.state,
        lockdown_count=alert_state.lockdown_count,
        entropy_status=status,
        entropy_indicator=indicator,
        inertial_brake_active=brake_active,
        alert_actions=tuple(alert_actions),
    )
