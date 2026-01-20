"""
Temperature scheduling for Phase-Quad sigmoid gating.

Temperature schedule: τ starts high (2.0) → decays to 1.0 during training.
This prevents early gate collapse and improves gradient flow.

Rationale:
- Early training: High τ (2.0) makes gates softer, more proposals get gradient
- Late training: Low τ (1.0) allows sharper selection

This prevents the "Quad appears broken then suddenly clicks" phenomenon.
"""

import math
from abc import ABC, abstractmethod
from typing import Optional


class TemperatureSchedule(ABC):
    """
    Base class for temperature schedules.

    Temperature controls the sharpness of sigmoid gating.
    Higher temperature = softer gates = more gradient flow.
    """

    @abstractmethod
    def __call__(self, step: int) -> float:
        """
        Get temperature for given training step.

        Args:
            step: Current training step.

        Returns:
            Temperature value.
        """
        pass

    @abstractmethod
    def get_progress(self, step: int) -> float:
        """
        Get schedule progress (0.0 to 1.0).

        Args:
            step: Current training step.

        Returns:
            Progress from 0.0 (start) to 1.0 (end).
        """
        pass


class LinearSchedule(TemperatureSchedule):
    """
    Linear temperature decay schedule.

    τ(step) = start + (end - start) * min(step / warmup_steps, 1.0)

    Args:
        start: Initial temperature (default: 2.0).
        end: Final temperature (default: 1.0).
        warmup_steps: Steps to reach final temperature (default: 50000).
    """

    def __init__(
        self,
        start: float = 2.0,
        end: float = 1.0,
        warmup_steps: int = 50000,
    ):
        if start < end:
            raise ValueError(
                f"Temperature should decay, but start ({start}) < end ({end})"
            )
        if start < 1.5:
            raise ValueError(
                f"Start temperature ({start}) must be >= 1.5 per design specification"
            )

        self.start = start
        self.end = end
        self.warmup_steps = warmup_steps

    def __call__(self, step: int) -> float:
        """Get temperature for given step."""
        if step >= self.warmup_steps:
            return self.end

        progress = step / self.warmup_steps
        return self.start + (self.end - self.start) * progress

    def get_progress(self, step: int) -> float:
        """Get schedule progress."""
        return min(step / self.warmup_steps, 1.0)


class CosineSchedule(TemperatureSchedule):
    """
    Cosine temperature decay schedule.

    τ(step) = end + (start - end) * (1 + cos(π * progress)) / 2

    This provides smoother decay than linear, with slower decay at
    the beginning and end.

    Args:
        start: Initial temperature (default: 2.0).
        end: Final temperature (default: 1.0).
        warmup_steps: Steps to reach final temperature (default: 50000).
    """

    def __init__(
        self,
        start: float = 2.0,
        end: float = 1.0,
        warmup_steps: int = 50000,
    ):
        if start < end:
            raise ValueError(
                f"Temperature should decay, but start ({start}) < end ({end})"
            )
        if start < 1.5:
            raise ValueError(
                f"Start temperature ({start}) must be >= 1.5 per design specification"
            )

        self.start = start
        self.end = end
        self.warmup_steps = warmup_steps

    def __call__(self, step: int) -> float:
        """Get temperature for given step."""
        if step >= self.warmup_steps:
            return self.end

        progress = step / self.warmup_steps
        return self.end + (self.start - self.end) * (1 + math.cos(math.pi * progress)) / 2

    def get_progress(self, step: int) -> float:
        """Get schedule progress."""
        return min(step / self.warmup_steps, 1.0)


class WarmupCosineSchedule(TemperatureSchedule):
    """
    Temperature schedule with initial warmup period.

    Holds temperature constant during warmup, then decays via cosine.

    Args:
        start: Initial temperature (default: 2.0).
        end: Final temperature (default: 1.0).
        warmup_steps: Steps before decay begins (default: 5000).
        decay_steps: Steps for decay after warmup (default: 45000).
    """

    def __init__(
        self,
        start: float = 2.0,
        end: float = 1.0,
        warmup_steps: int = 5000,
        decay_steps: int = 45000,
    ):
        if start < end:
            raise ValueError(
                f"Temperature should decay, but start ({start}) < end ({end})"
            )

        self.start = start
        self.end = end
        self.warmup_steps = warmup_steps
        self.decay_steps = decay_steps
        self.total_steps = warmup_steps + decay_steps

    def __call__(self, step: int) -> float:
        """Get temperature for given step."""
        if step < self.warmup_steps:
            # Hold at start temperature
            return self.start

        if step >= self.total_steps:
            return self.end

        # Cosine decay
        decay_progress = (step - self.warmup_steps) / self.decay_steps
        return self.end + (self.start - self.end) * (1 + math.cos(math.pi * decay_progress)) / 2

    def get_progress(self, step: int) -> float:
        """Get schedule progress."""
        return min(step / self.total_steps, 1.0)


def get_temperature_schedule(
    schedule_type: str,
    start: float = 2.0,
    end: float = 1.0,
    warmup_steps: int = 50000,
) -> TemperatureSchedule:
    """
    Factory function for temperature schedules.

    Args:
        schedule_type: One of "linear", "cosine", "warmup_cosine".
        start: Initial temperature.
        end: Final temperature.
        warmup_steps: Steps for schedule.

    Returns:
        TemperatureSchedule instance.
    """
    if schedule_type == "linear":
        return LinearSchedule(start, end, warmup_steps)
    elif schedule_type == "cosine":
        return CosineSchedule(start, end, warmup_steps)
    elif schedule_type == "warmup_cosine":
        return WarmupCosineSchedule(start, end, warmup_steps // 10, warmup_steps * 9 // 10)
    else:
        raise ValueError(f"Unknown schedule type: {schedule_type}")
