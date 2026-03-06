"""
PrimitiveLambdaScheduler: Controls λ_f ramp schedules per curriculum stage.

Supports linear ramp, cosine ramp, and step transitions for smooth introduction
of primitive losses. Integrates with CurriculumStageManager for per-stage targets.

Reference: CONSCIOUS_GENERATION_DESIGN.md, Appendix D Phase 5 (D.7.2)
"""

import math
from typing import Dict, Optional


class PrimitiveLambdaScheduler:
    """
    Smooth weight scheduler for conscious generation loss lambdas.

    Each lambda is ramped from a start value to a target value over a specified
    number of steps. Supports three ramp modes:
      - 'linear': λ(t) = start + (target - start) * t / ramp_steps
      - 'cosine': λ(t) = start + (target - start) * 0.5 * (1 - cos(π * t / ramp_steps))
      - 'step':   λ(t) = target if t >= ramp_steps else start

    Args:
        ramp_mode: One of 'linear', 'cosine', 'step'. Default 'cosine'.
    """

    RAMP_MODES = ("linear", "cosine", "step")

    def __init__(self, ramp_mode: str = "cosine"):
        if ramp_mode not in self.RAMP_MODES:
            raise ValueError(f"ramp_mode must be one of {self.RAMP_MODES}, got '{ramp_mode}'")
        self.ramp_mode = ramp_mode
        # Active schedules: key -> {start, target, ramp_steps, start_step}
        self._schedules: Dict[str, dict] = {}
        # Current values
        self._values: Dict[str, float] = {}

    def set_schedule(
        self,
        key: str,
        start: float,
        target: float,
        ramp_steps: int,
        start_step: int = 0,
    ):
        """
        Set a ramp schedule for a lambda key.

        Args:
            key: Lambda identifier (e.g., 'lambda_ont', 'lambda_jepa_token').
            start: Starting value.
            target: Target value at end of ramp.
            ramp_steps: Number of steps over which to ramp.
            start_step: Global step at which this ramp begins.
        """
        self._schedules[key] = {
            "start": start,
            "target": target,
            "ramp_steps": max(ramp_steps, 1),
            "start_step": start_step,
        }
        self._values[key] = start

    def set_immediate(self, key: str, value: float):
        """Set a lambda to a fixed value immediately (no ramp)."""
        self._schedules.pop(key, None)
        self._values[key] = value

    def step(self, global_step: int) -> Dict[str, float]:
        """
        Update all lambdas for the current global step.

        Args:
            global_step: Current training step.

        Returns:
            Dict of current lambda values.
        """
        for key, sched in self._schedules.items():
            t = global_step - sched["start_step"]
            if t < 0:
                self._values[key] = sched["start"]
            elif t >= sched["ramp_steps"]:
                self._values[key] = sched["target"]
            else:
                frac = t / sched["ramp_steps"]
                if self.ramp_mode == "linear":
                    alpha = frac
                elif self.ramp_mode == "cosine":
                    alpha = 0.5 * (1.0 - math.cos(math.pi * frac))
                else:  # step
                    alpha = 0.0
                self._values[key] = sched["start"] + (sched["target"] - sched["start"]) * alpha

        return dict(self._values)

    def get(self, key: str, default: float = 0.0) -> float:
        """Get the current value of a lambda."""
        return self._values.get(key, default)

    def get_all(self) -> Dict[str, float]:
        """Get all current lambda values."""
        return dict(self._values)

    def get_diagnostics(self) -> Dict[str, float]:
        """Get diagnostic info about current scheduler state."""
        return {f"sched_{k}": v for k, v in self._values.items()}
