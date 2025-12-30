"""
SymbolU12 Training Utilities: Phase-Lock Stability Monitors
============================================================

This module provides monitoring and diagnostic tools for tracking
the model's "Mathematical Conscience" during training.

Key Monitors:
    - Trace stability over time
    - Determinant drift detection
    - Epistemic decay tracking
    - R2H progress visualization
"""

from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from collections import deque
import torch
import torch.nn as nn
import time


# =============================================================================
# TRACE MONITOR
# =============================================================================

@dataclass
class TraceSnapshot:
    """Snapshot of trace state at a point in time."""
    step: int
    trace_mean: float
    trace_min: float
    trace_max: float
    trace_std: float
    timestamp: float


class TraceMonitor:
    """
    Monitors Phase-Lock trace stability over training.

    Tracks:
        - Trace mean, min, max, std over rolling window
        - Trace volatility (sudden drops)
        - Convergence to target threshold
    """

    def __init__(
        self,
        window_size: int = 100,
        volatility_threshold: float = 0.15,
        target_trace: float = 0.85,
    ):
        self.window_size = window_size
        self.volatility_threshold = volatility_threshold
        self.target_trace = target_trace

        self.history: deque = deque(maxlen=window_size)
        self.snapshots: List[TraceSnapshot] = []
        self.volatility_events: List[Tuple[int, float]] = []

    def update(self, trace: torch.Tensor, step: int):
        """Update monitor with new trace values."""
        if trace.dim() > 0:
            trace_mean = trace.mean().item()
            trace_min = trace.min().item()
            trace_max = trace.max().item()
            trace_std = trace.std().item()
        else:
            trace_mean = trace_min = trace_max = trace.item()
            trace_std = 0.0

        # Check for volatility (sudden drop)
        if len(self.history) > 0:
            prev_mean = sum(self.history) / len(self.history)
            if prev_mean - trace_mean > self.volatility_threshold:
                self.volatility_events.append((step, prev_mean - trace_mean))

        self.history.append(trace_mean)

        # Take snapshot
        snapshot = TraceSnapshot(
            step=step,
            trace_mean=trace_mean,
            trace_min=trace_min,
            trace_max=trace_max,
            trace_std=trace_std,
            timestamp=time.time(),
        )
        self.snapshots.append(snapshot)

    def get_stability_score(self) -> float:
        """Get current stability score (0 to 1)."""
        if len(self.history) < 2:
            return 1.0

        values = list(self.history)
        mean = sum(values) / len(values)
        variance = sum((v - mean) ** 2 for v in values) / len(values)
        std = variance ** 0.5

        # Lower std = higher stability
        # Normalize: std of 0.1 -> score 0.5
        stability = max(0, 1 - std * 5)
        return stability

    def get_convergence_progress(self) -> float:
        """Get progress toward target trace (0 to 1)."""
        if len(self.history) == 0:
            return 0.0

        current_mean = sum(self.history) / len(self.history)
        # Assuming starting from 0.5, target 0.85
        progress = (current_mean - 0.5) / (self.target_trace - 0.5)
        return max(0, min(1, progress))

    def get_summary(self) -> Dict[str, Any]:
        """Get summary statistics."""
        if len(self.history) == 0:
            return {'status': 'no_data'}

        values = list(self.history)
        return {
            'current_mean': values[-1] if values else 0,
            'rolling_mean': sum(values) / len(values),
            'stability_score': self.get_stability_score(),
            'convergence_progress': self.get_convergence_progress(),
            'volatility_events': len(self.volatility_events),
            'total_snapshots': len(self.snapshots),
        }


# =============================================================================
# DETERMINANT MONITOR
# =============================================================================

class DeterminantMonitor:
    """
    Monitors R matrix determinant drift.

    det(R) should stay close to 1.0 for orthogonality.
    Drift indicates the model is trying to "escape" the Stiefel manifold.
    """

    def __init__(
        self,
        drift_threshold: float = 0.05,
        window_size: int = 100,
    ):
        self.drift_threshold = drift_threshold
        self.window_size = window_size
        self.history: deque = deque(maxlen=window_size)
        self.drift_events: List[Tuple[int, float]] = []

    def update(self, R: torch.Tensor, step: int):
        """Update monitor with new R matrix."""
        det = torch.linalg.det(R)
        if det.dim() > 0:
            det_mean = det.mean().item()
        else:
            det_mean = det.item()

        drift = abs(det_mean - 1.0)

        if drift > self.drift_threshold:
            self.drift_events.append((step, drift))

        self.history.append(det_mean)

    def get_current_drift(self) -> float:
        """Get current drift from 1.0."""
        if len(self.history) == 0:
            return 0.0
        return abs(self.history[-1] - 1.0)

    def needs_correction(self) -> bool:
        """Check if relativistic shift is needed."""
        return self.get_current_drift() > self.drift_threshold

    def get_summary(self) -> Dict[str, Any]:
        """Get summary statistics."""
        if len(self.history) == 0:
            return {'status': 'no_data'}

        values = list(self.history)
        return {
            'current_det': values[-1] if values else 1.0,
            'current_drift': self.get_current_drift(),
            'needs_correction': self.needs_correction(),
            'drift_events': len(self.drift_events),
            'avg_det': sum(values) / len(values),
        }


# =============================================================================
# ENTROPY SENTINEL
# =============================================================================

class EntropySentinel:
    """
    Monitors entropy to detect "gaslighting" attacks.

    If entropy stays high for too long, the model may be confused
    by adversarial input and needs a state reset.
    """

    def __init__(
        self,
        window_size: int = 10,
        high_entropy_threshold: float = 0.9,
    ):
        self.window_size = window_size
        self.high_entropy_threshold = high_entropy_threshold
        self.history: deque = deque(maxlen=window_size)
        self.confusion_events: List[int] = []

    def update(self, entropy: float, step: int):
        """Update monitor with new entropy value."""
        self.history.append(entropy)

        # Check for sustained high entropy
        if len(self.history) >= self.window_size:
            if all(e > self.high_entropy_threshold for e in self.history):
                self.confusion_events.append(step)
                self.history.clear()  # Reset after detecting

    def is_confused(self) -> bool:
        """Check if model is in sustained confusion state."""
        if len(self.history) < self.window_size:
            return False
        return all(e > self.high_entropy_threshold for e in self.history)

    def needs_reset(self) -> bool:
        """Check if state reset is recommended."""
        return self.is_confused()

    def get_summary(self) -> Dict[str, Any]:
        """Get summary statistics."""
        if len(self.history) == 0:
            return {'status': 'no_data'}

        values = list(self.history)
        return {
            'current_entropy': values[-1] if values else 0,
            'avg_entropy': sum(values) / len(values),
            'is_confused': self.is_confused(),
            'confusion_events': len(self.confusion_events),
            'high_entropy_streak': sum(1 for e in values if e > self.high_entropy_threshold),
        }


# =============================================================================
# R2H PROGRESS TRACKER
# =============================================================================

@dataclass
class R2HCheckpoint:
    """Checkpoint of R2H metrics."""
    step: int
    r2h_score: float
    meta_exit_rate: float
    paradoxes_tested: int
    timestamp: float


class R2HProgressTracker:
    """
    Tracks R2H (Refusal-to-Hallucinate) progress during training.

    Monitors:
        - R2H score over time
        - META exit rate
        - Progress toward certification threshold
    """

    def __init__(self, target_score: float = 0.95):
        self.target_score = target_score
        self.checkpoints: List[R2HCheckpoint] = []
        self.best_score = 0.0
        self.best_step = 0

    def update(
        self,
        step: int,
        r2h_score: float,
        meta_exit_rate: float,
        paradoxes_tested: int,
    ):
        """Record new R2H checkpoint."""
        checkpoint = R2HCheckpoint(
            step=step,
            r2h_score=r2h_score,
            meta_exit_rate=meta_exit_rate,
            paradoxes_tested=paradoxes_tested,
            timestamp=time.time(),
        )
        self.checkpoints.append(checkpoint)

        if r2h_score > self.best_score:
            self.best_score = r2h_score
            self.best_step = step

    def get_progress(self) -> float:
        """Get progress toward target (0 to 1)."""
        if len(self.checkpoints) == 0:
            return 0.0
        return min(1.0, self.checkpoints[-1].r2h_score / self.target_score)

    def is_certified(self) -> bool:
        """Check if current score meets certification."""
        if len(self.checkpoints) == 0:
            return False
        return self.checkpoints[-1].r2h_score >= self.target_score

    def get_improvement_rate(self) -> float:
        """Calculate improvement rate (score gain per 1000 steps)."""
        if len(self.checkpoints) < 2:
            return 0.0

        first = self.checkpoints[0]
        last = self.checkpoints[-1]
        steps = last.step - first.step
        if steps == 0:
            return 0.0

        score_gain = last.r2h_score - first.r2h_score
        return score_gain / (steps / 1000)

    def get_summary(self) -> Dict[str, Any]:
        """Get summary statistics."""
        if len(self.checkpoints) == 0:
            return {'status': 'no_data'}

        latest = self.checkpoints[-1]
        return {
            'current_score': latest.r2h_score,
            'best_score': self.best_score,
            'best_step': self.best_step,
            'progress': self.get_progress(),
            'is_certified': self.is_certified(),
            'improvement_rate': self.get_improvement_rate(),
            'total_checkpoints': len(self.checkpoints),
        }


# =============================================================================
# COMBINED TRAINING MONITOR
# =============================================================================

class Sattva1Monitor:
    """
    Combined monitor for all Sattva-1 training metrics.

    Provides a unified interface for tracking:
        - Trace stability
        - Determinant drift
        - Entropy confusion
        - R2H progress
    """

    def __init__(
        self,
        trace_target: float = 0.85,
        r2h_target: float = 0.95,
    ):
        self.trace_monitor = TraceMonitor(target_trace=trace_target)
        self.det_monitor = DeterminantMonitor()
        self.entropy_sentinel = EntropySentinel()
        self.r2h_tracker = R2HProgressTracker(target_score=r2h_target)

        self.step = 0

    def update_training_step(
        self,
        trace: torch.Tensor,
        R_internal: torch.Tensor,
        entropy: Optional[float] = None,
    ):
        """Update monitors with training step data."""
        self.step += 1
        self.trace_monitor.update(trace, self.step)
        self.det_monitor.update(R_internal, self.step)

        if entropy is not None:
            self.entropy_sentinel.update(entropy, self.step)

    def update_validation(
        self,
        r2h_score: float,
        meta_exit_rate: float,
        paradoxes_tested: int,
    ):
        """Update with validation results."""
        self.r2h_tracker.update(
            self.step, r2h_score, meta_exit_rate, paradoxes_tested
        )

    def get_alerts(self) -> List[str]:
        """Get list of active alerts."""
        alerts = []

        if self.det_monitor.needs_correction():
            alerts.append(f"DRIFT: det(R) = {self.det_monitor.history[-1]:.4f}")

        if self.entropy_sentinel.needs_reset():
            alerts.append("CONFUSION: High entropy sustained - state reset recommended")

        if self.trace_monitor.get_stability_score() < 0.5:
            alerts.append("UNSTABLE: Trace volatility detected")

        return alerts

    def get_dashboard(self) -> Dict[str, Any]:
        """Get full dashboard of metrics."""
        return {
            'step': self.step,
            'trace': self.trace_monitor.get_summary(),
            'determinant': self.det_monitor.get_summary(),
            'entropy': self.entropy_sentinel.get_summary(),
            'r2h': self.r2h_tracker.get_summary(),
            'alerts': self.get_alerts(),
            'overall_health': self._compute_health_score(),
        }

    def _compute_health_score(self) -> float:
        """Compute overall training health (0 to 1)."""
        scores = []

        # Trace stability
        scores.append(self.trace_monitor.get_stability_score())

        # Determinant health (inverse of drift)
        det_health = 1.0 - min(1.0, self.det_monitor.get_current_drift() * 10)
        scores.append(det_health)

        # Confusion health (no confusion = healthy)
        conf_health = 0.0 if self.entropy_sentinel.is_confused() else 1.0
        scores.append(conf_health)

        # R2H progress
        scores.append(self.r2h_tracker.get_progress())

        return sum(scores) / len(scores)

    def print_status(self):
        """Print current status to console."""
        dashboard = self.get_dashboard()

        print("\n" + "="*50)
        print(f"SATTVA-1 MONITOR | Step {self.step}")
        print("="*50)

        print(f"\nTrace: {dashboard['trace'].get('rolling_mean', 0):.3f}")
        print(f"  Stability: {dashboard['trace'].get('stability_score', 0):.3f}")

        print(f"\nDeterminant: {dashboard['determinant'].get('current_det', 1):.4f}")
        print(f"  Drift: {dashboard['determinant'].get('current_drift', 0):.4f}")

        print(f"\nR2H Score: {dashboard['r2h'].get('current_score', 0):.3f}")
        print(f"  Progress: {dashboard['r2h'].get('progress', 0)*100:.1f}%")

        print(f"\nHealth Score: {dashboard['overall_health']:.3f}")

        if dashboard['alerts']:
            print("\nALERTS:")
            for alert in dashboard['alerts']:
                print(f"  ⚠️  {alert}")

        print("="*50 + "\n")


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    'TraceSnapshot',
    'TraceMonitor',
    'DeterminantMonitor',
    'EntropySentinel',
    'R2HCheckpoint',
    'R2HProgressTracker',
    'Sattva1Monitor',
]
