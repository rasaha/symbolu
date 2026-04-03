"""
Agentic Safety Bounds — Hard limits always enforced on agent actions.

Clamps proposed action magnitude to safe ranges and enforces a
cooldown period between actions.  These bounds are non-negotiable:
they apply even after human approval.

OLM mapping: O3_EXECUTION (execution boundary), O4_STRUCTURE (structural compliance)

Pattern extracted from cloud_controller.recommend.safety.SafetyBounds,
rewritten for AI agent governance (no K8s dependencies).
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Optional


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class SafetyConfig:
    """Hard safety limits for agent actions.

    Attributes:
        max_action_magnitude: Upper bound on action magnitude [0, 1].
            Prevents any single action from exceeding this fraction of
            the action space.  Default 0.50 (50%).
        min_action_magnitude: Lower bound on action magnitude [0, 1].
            Prevents trivially small actions that add overhead without
            meaningful effect.  Default 0.0 (no floor).
        cooldown_seconds: Minimum interval between consecutive actions.
            Prevents rapid-fire action sequences.  Default 120s.
        max_concurrent_actions: Maximum actions allowed in flight
            simultaneously.  Default 1.
    """
    max_action_magnitude: float = 0.50
    min_action_magnitude: float = 0.0
    cooldown_seconds: float = 120.0
    max_concurrent_actions: int = 1


@dataclass(frozen=True)
class SafetyResult:
    """Outcome of a safety bounds check.

    Attributes:
        original_magnitude: The magnitude the caller proposed.
        clamped_magnitude: The magnitude after applying hard limits.
        was_clamped: Whether the magnitude was adjusted.
        clamp_reason: Human-readable reason if clamped.
        in_cooldown: Whether the system is currently in cooldown.
        cooldown_remaining: Seconds until cooldown expires (0 if not).
    """
    original_magnitude: float
    clamped_magnitude: float
    was_clamped: bool
    clamp_reason: str
    in_cooldown: bool
    cooldown_remaining: float


# ---------------------------------------------------------------------------
# Bounds checker
# ---------------------------------------------------------------------------

class SafetyBounds:
    """Enforces hard, non-negotiable safety limits on agent actions.

    Thread-safe.  Maintains cooldown state.

    Usage::

        bounds = SafetyBounds(SafetyConfig(cooldown_seconds=60))
        result = bounds.check(proposed_magnitude=0.8)
        if result.in_cooldown:
            print("Wait", result.cooldown_remaining, "seconds")
        elif result.was_clamped:
            print("Clamped to", result.clamped_magnitude)
        else:
            bounds.record_action()
    """

    def __init__(self, config: Optional[SafetyConfig] = None) -> None:
        self.config = config or SafetyConfig()
        self._last_action_time: Optional[float] = None
        self._lock = threading.Lock()

    def check(
        self,
        proposed_magnitude: float,
        *,
        current_time: Optional[float] = None,
    ) -> SafetyResult:
        """Evaluate proposed action magnitude against hard limits."""
        now = current_time if current_time is not None else time.time()
        cfg = self.config

        # Cooldown check
        with self._lock:
            last = self._last_action_time
        in_cooldown = False
        cooldown_remaining = 0.0
        if last is not None:
            elapsed = now - last
            if elapsed < cfg.cooldown_seconds:
                in_cooldown = True
                cooldown_remaining = cfg.cooldown_seconds - elapsed

        # Clamp magnitude
        clamped = proposed_magnitude
        reasons: list[str] = []

        if clamped > cfg.max_action_magnitude:
            reasons.append(
                f"clamped from {clamped:.3f} to max {cfg.max_action_magnitude:.3f}"
            )
            clamped = cfg.max_action_magnitude

        if clamped < cfg.min_action_magnitude:
            reasons.append(
                f"raised from {clamped:.3f} to min {cfg.min_action_magnitude:.3f}"
            )
            clamped = cfg.min_action_magnitude

        was_clamped = abs(clamped - proposed_magnitude) > 1e-9
        reason = "; ".join(reasons) if reasons else ""

        return SafetyResult(
            original_magnitude=proposed_magnitude,
            clamped_magnitude=clamped,
            was_clamped=was_clamped,
            clamp_reason=reason,
            in_cooldown=in_cooldown,
            cooldown_remaining=cooldown_remaining,
        )

    def record_action(self, timestamp: Optional[float] = None) -> None:
        """Record that an action was executed (starts cooldown)."""
        ts = timestamp if timestamp is not None else time.time()
        with self._lock:
            self._last_action_time = ts

    @property
    def last_action_time(self) -> Optional[float]:
        with self._lock:
            return self._last_action_time

    def reset(self) -> None:
        """Clear cooldown state."""
        with self._lock:
            self._last_action_time = None
