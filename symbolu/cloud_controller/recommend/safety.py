"""Safety Bounds — enforces hard limits on scaling recommendations.

Always enforced, even after human approval:
  - Max scale-out: +50% of current replicas per action
  - Max scale-in:  -25% of current replicas per action
  - Minimum replicas: never below min_replicas setting
  - Cooldown: observation period after each executed action
"""

import time
import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class SafetyConfig:
    """Safety bounds configuration."""
    # Maximum scale-out as fraction of current replicas
    max_scale_out_fraction: float = 0.50   # +50%
    # Maximum scale-in as fraction of current replicas
    max_scale_in_fraction: float = 0.25    # -25%
    # Absolute minimum replicas (never go below this)
    min_replicas: int = 1
    # Cooldown after an executed action (seconds)
    cooldown_seconds: float = 120.0        # 2 minutes


@dataclass
class SafetyResult:
    """Result of safety bounds check."""
    original_delta: int
    clamped_delta: int
    target_replicas: int
    was_clamped: bool
    clamp_reason: str
    in_cooldown: bool
    cooldown_remaining: float  # seconds remaining, 0 if not in cooldown


class SafetyBounds:
    """Enforces safety limits on scaling actions.

    Usage:
        bounds = SafetyBounds(SafetyConfig())
        result = bounds.check(current_replicas=5, proposed_delta=4)
        # result.clamped_delta = 2 (50% of 5 = 2.5, rounded to 2)
    """

    def __init__(self, config: SafetyConfig | None = None):
        self.config = config or SafetyConfig()
        self._last_action_time: float | None = None

    def check(
        self,
        current_replicas: int,
        proposed_delta: int,
        current_time: float | None = None,
    ) -> SafetyResult:
        """Check and clamp a proposed scaling action.

        Args:
            current_replicas: Current number of replicas.
            proposed_delta: Proposed change (+N or -N).
            current_time: Current timestamp (defaults to now).

        Returns:
            SafetyResult with potentially clamped delta.
        """
        if current_time is None:
            current_time = time.time()

        # Check cooldown
        in_cooldown = False
        cooldown_remaining = 0.0
        if self._last_action_time is not None:
            elapsed = current_time - self._last_action_time
            if elapsed < self.config.cooldown_seconds:
                in_cooldown = True
                cooldown_remaining = self.config.cooldown_seconds - elapsed

        if proposed_delta == 0:
            return SafetyResult(
                original_delta=0,
                clamped_delta=0,
                target_replicas=current_replicas,
                was_clamped=False,
                clamp_reason="",
                in_cooldown=in_cooldown,
                cooldown_remaining=cooldown_remaining,
            )

        clamped = proposed_delta
        reasons = []

        if proposed_delta > 0:
            # Scale out — cap at +50% of current
            max_out = max(1, int(current_replicas * self.config.max_scale_out_fraction))
            if proposed_delta > max_out:
                clamped = max_out
                reasons.append(
                    f"Scale-out clamped from +{proposed_delta} to +{max_out} "
                    f"(max {self.config.max_scale_out_fraction:.0%} of {current_replicas})"
                )
        else:
            # Scale in — cap at -25% of current
            max_in = max(1, int(current_replicas * self.config.max_scale_in_fraction))
            if abs(proposed_delta) > max_in:
                clamped = -max_in
                reasons.append(
                    f"Scale-in clamped from {proposed_delta} to -{max_in} "
                    f"(max {self.config.max_scale_in_fraction:.0%} of {current_replicas})"
                )

        # Enforce minimum replicas
        target = current_replicas + clamped
        if target < self.config.min_replicas:
            old_clamped = clamped
            clamped = self.config.min_replicas - current_replicas
            if clamped >= 0:
                clamped = 0  # Can't scale in if already at or below min
            reasons.append(
                f"Floor applied: target {current_replicas + old_clamped} "
                f"below min {self.config.min_replicas}"
            )

        target = current_replicas + clamped
        was_clamped = clamped != proposed_delta

        if was_clamped:
            logger.info(
                "Safety bounds clamped delta: %+d → %+d (target=%d): %s",
                proposed_delta, clamped, target, "; ".join(reasons),
            )

        return SafetyResult(
            original_delta=proposed_delta,
            clamped_delta=clamped,
            target_replicas=target,
            was_clamped=was_clamped,
            clamp_reason="; ".join(reasons),
            in_cooldown=in_cooldown,
            cooldown_remaining=cooldown_remaining,
        )

    def record_action(self, timestamp: float | None = None) -> None:
        """Record that an action was executed (starts cooldown)."""
        self._last_action_time = timestamp or time.time()

    @property
    def last_action_time(self) -> float | None:
        return self._last_action_time

    def reset(self) -> None:
        """Clear cooldown state."""
        self._last_action_time = None
