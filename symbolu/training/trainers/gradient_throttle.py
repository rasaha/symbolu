"""
Gradient Norm Throttle Controller
=================================

Stabilizes training by dynamically reducing learning rate when gradient norms spike.
Acts as a physical safety layer that prevents destructive weight updates during
training instabilities.

Usage:
    throttle = GradientNormThrottle(ema_decay=0.99, spike_threshold=2.0, min_factor=0.05)

    # In training loop, after loss.backward() and before optimizer.step():
    factor, grad_norm = throttle.step(model, optimizer, base_lr)
    if factor < 1.0:
        print(f"Gradient spike detected: {grad_norm:.1f}, LR throttled to {factor:.2f}x")
"""

import torch
import torch.nn as nn
from typing import Tuple, Optional


class GradientNormThrottle:
    """
    Stabilizes training by reducing LR when gradient norms spike.

    The gradient norm is the Euclidean norm (L2) of all gradients in the model.
    When this spikes above a threshold relative to the exponential moving average,
    the learning rate is temporarily reduced to prevent destructive updates.

    Args:
        ema_decay: Decay factor for exponential moving average (0.99 = slow adaptation)
        spike_threshold: Trigger throttle if current norm > threshold * EMA
        min_factor: Minimum LR multiplier (floor to prevent complete stalling)
        warmup_steps: Number of steps to skip throttling during warmup
    """

    def __init__(
        self,
        ema_decay: float = 0.99,
        spike_threshold: float = 2.0,
        min_factor: float = 0.05,
        warmup_steps: int = 100,
    ):
        self.ema_decay = ema_decay
        self.spike_threshold = spike_threshold
        self.min_factor = min_factor
        self.warmup_steps = warmup_steps

        # State
        self.ema_grad_norm: Optional[float] = None
        self.step_count: int = 0
        self.throttle_events: int = 0
        self.total_throttle_time: int = 0  # Steps spent throttled
        self.last_factor: float = 1.0
        self.last_grad_norm: float = 0.0

        # Statistics for monitoring
        self.max_spike_ratio: float = 1.0
        self.spike_history: list = []  # Last 10 spikes

    def compute_grad_norm(self, model: nn.Module) -> float:
        """
        Compute the total L2 norm of all gradients in the model.

        This is equivalent to treating all gradients as one flattened vector
        and computing its Euclidean length.
        """
        total_norm_sq = 0.0
        for p in model.parameters():
            if p.grad is not None:
                total_norm_sq += p.grad.data.norm(2).item() ** 2
        return total_norm_sq ** 0.5

    def step(
        self,
        model: nn.Module,
        optimizer: torch.optim.Optimizer,
        base_lr: float,
        precomputed_norm: Optional[float] = None,
    ) -> Tuple[float, float]:
        """
        Check gradient norm and apply throttling if needed.

        Args:
            model: The model being trained
            optimizer: The optimizer to adjust
            base_lr: The base learning rate (before throttling)
            precomputed_norm: Optional pre-computed gradient norm to avoid recomputation

        Returns:
            Tuple of (throttle_factor, current_grad_norm)
            - throttle_factor: 1.0 if no throttle, < 1.0 if throttled
            - current_grad_norm: The measured gradient norm
        """
        self.step_count += 1

        # Compute gradient norm (reuse if already computed)
        if precomputed_norm is not None:
            total_norm = precomputed_norm
        else:
            total_norm = self.compute_grad_norm(model)

        self.last_grad_norm = total_norm

        # Initialize EMA on first step
        if self.ema_grad_norm is None:
            self.ema_grad_norm = total_norm
            self.last_factor = 1.0
            return 1.0, total_norm

        # Skip throttling during warmup
        if self.step_count <= self.warmup_steps:
            # Still update EMA during warmup
            self.ema_grad_norm = (
                self.ema_decay * self.ema_grad_norm +
                (1 - self.ema_decay) * total_norm
            )
            self.last_factor = 1.0
            return 1.0, total_norm

        # Detect spike
        ratio = total_norm / (self.ema_grad_norm + 1e-8)

        factor = 1.0
        if ratio > self.spike_threshold:
            # Throttle proportionally to the spike magnitude
            # Spike 5x normal -> LR becomes 1/5th (0.2x), clamped to min_factor
            factor = max(self.ema_grad_norm / total_norm, self.min_factor)

            self.throttle_events += 1
            self.max_spike_ratio = max(self.max_spike_ratio, ratio)

            # Track spike history
            self.spike_history.append({
                'step': self.step_count,
                'ratio': ratio,
                'factor': factor,
                'norm': total_norm,
            })
            if len(self.spike_history) > 10:
                self.spike_history.pop(0)

        # Track time spent throttled
        if factor < 1.0:
            self.total_throttle_time += 1

        # Apply to optimizer — preserve relative LR scaling between param groups.
        # Each group may have a different base LR (e.g., slot memory at 0.1x).
        # We track each group's "unthrottled" LR and detect when external systems
        # (adaptive controller, scheduler, stress probes) change it between steps.
        for param_group in optimizer.param_groups:
            if '_throttle_applied_lr' in param_group \
                    and param_group['lr'] != param_group['_throttle_applied_lr']:
                # External system changed LR since last throttle — update base
                param_group['_unthrottled_lr'] = param_group['lr']
            elif '_unthrottled_lr' not in param_group:
                # First time — snapshot current LR as unthrottled base
                param_group['_unthrottled_lr'] = param_group['lr']
            # Apply throttle factor to the unthrottled base (preserves relative scaling)
            param_group['lr'] = param_group['_unthrottled_lr'] * factor
            param_group['_throttle_applied_lr'] = param_group['lr']

        # Update EMA (slowly adapt to new normal)
        self.ema_grad_norm = (
            self.ema_decay * self.ema_grad_norm +
            (1 - self.ema_decay) * total_norm
        )

        self.last_factor = factor
        return factor, total_norm

    def get_stats(self) -> dict:
        """Return throttle statistics for logging."""
        return {
            'throttle_events': self.throttle_events,
            'throttle_rate': self.throttle_events / max(self.step_count, 1),
            'throttle_time_pct': 100 * self.total_throttle_time / max(self.step_count, 1),
            'max_spike_ratio': self.max_spike_ratio,
            'ema_grad_norm': self.ema_grad_norm or 0.0,
            'last_grad_norm': self.last_grad_norm,
            'last_factor': self.last_factor,
        }

    def reset_stats(self):
        """Reset statistics (but keep EMA for continuous operation)."""
        self.throttle_events = 0
        self.total_throttle_time = 0
        self.max_spike_ratio = 1.0
        self.spike_history = []
