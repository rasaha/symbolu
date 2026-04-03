"""
Agentic Policy Engine — Configurable allow/deny enforcement for agent actions.

Evaluates proposed agent actions against:
  1. Action-type allowlists/denylists per agent
  2. Blackout windows (time ranges blocking specific action types)
  3. Rate limits (max actions per sliding window)

OLM mapping: O1_POTENTIAL (capability gating), O6_AGENCY (directional policy)

Pattern extracted from cloud_controller.action.policy.PolicyEngine,
rewritten for AI agent governance (no K8s dependencies).
"""

from __future__ import annotations

import math
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class BlackoutWindow:
    """Time range during which certain action types are blocked.

    Attributes:
        start_hour: Start hour (0-23 inclusive).
        end_hour: End hour (0-23 inclusive).  Wraps at midnight if start > end.
        days: Tuple of ISO weekday numbers (1=Mon … 7=Sun).  Empty = all days.
        blocked_actions: Action types blocked during this window.  Empty = all.
        reason: Human-readable explanation for audit logs.
    """
    start_hour: int
    end_hour: int
    days: Tuple[int, ...] = ()
    blocked_actions: Tuple[str, ...] = ()
    reason: str = ""

    def active_at(self, hour: int, weekday: int) -> bool:
        """Return True if *now* falls inside this blackout window."""
        if self.days and weekday not in self.days:
            return False
        if self.start_hour <= self.end_hour:
            return self.start_hour <= hour <= self.end_hour
        # Wraps midnight (e.g. 22 → 04)
        return hour >= self.start_hour or hour <= self.end_hour


@dataclass(frozen=True)
class AgentPolicy:
    """Per-agent policy constraints.

    Attributes:
        allowed_actions: Explicit allowlist.  Empty = all allowed.
        denied_actions: Explicit denylist (takes precedence over allowlist).
        max_actions_per_window: Rate limit ceiling.
        rate_limit_window_seconds: Sliding window duration for rate limiting.
        blackout_windows: Time-based action blocks.
    """
    allowed_actions: Tuple[str, ...] = ()
    denied_actions: Tuple[str, ...] = ()
    max_actions_per_window: int = 100
    rate_limit_window_seconds: float = 3600.0
    blackout_windows: Tuple[BlackoutWindow, ...] = ()


@dataclass(frozen=True)
class PolicyConfig:
    """Global policy configuration.

    Attributes:
        default_policy: Baseline policy for agents without overrides.
        agent_overrides: Per-agent policy overrides keyed by agent_id.
    """
    default_policy: AgentPolicy = field(default_factory=AgentPolicy)
    agent_overrides: Dict[str, AgentPolicy] = field(default_factory=dict)


@dataclass(frozen=True)
class PolicyCheckResult:
    """Outcome of a policy evaluation.

    Attributes:
        allowed: Whether the action is permitted.
        agent_id: Agent that requested the action.
        action_type: The action being evaluated.
        violations: List of reasons if denied.
    """
    allowed: bool
    agent_id: str
    action_type: str
    violations: Tuple[str, ...] = ()


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

class PolicyEngine:
    """Evaluates agent actions against configurable policy constraints.

    Thread-safe.  Maintains a sliding-window action log for rate limiting.

    Usage::

        engine = PolicyEngine(config)
        result = engine.check("agent-7", "execute_tool", current_time=time.time())
        if result.allowed:
            engine.record_action("agent-7", "execute_tool")
    """

    def __init__(self, config: Optional[PolicyConfig] = None) -> None:
        self.config = config or PolicyConfig()
        self._action_log: List[Tuple[str, str, float]] = []
        self._max_log: int = 10_000
        self._lock = threading.Lock()

    def check(
        self,
        agent_id: str,
        action_type: str,
        *,
        current_time: Optional[float] = None,
    ) -> PolicyCheckResult:
        """Evaluate whether *agent_id* may perform *action_type* now."""
        now = current_time if current_time is not None else time.time()
        policy = self.config.agent_overrides.get(
            agent_id, self.config.default_policy
        )
        violations: List[str] = []

        # 1. Denylist
        if policy.denied_actions and action_type in policy.denied_actions:
            violations.append(f"action '{action_type}' is explicitly denied")

        # 2. Allowlist
        if (
            policy.allowed_actions
            and action_type not in policy.allowed_actions
            and action_type not in (policy.denied_actions or ())
        ):
            violations.append(
                f"action '{action_type}' not in allowlist"
            )

        # 3. Blackout windows
        import datetime as _dt
        dt = _dt.datetime.fromtimestamp(now, tz=_dt.timezone.utc)
        hour, weekday = dt.hour, dt.isoweekday()
        for bw in policy.blackout_windows:
            if bw.active_at(hour, weekday):
                if not bw.blocked_actions or action_type in bw.blocked_actions:
                    violations.append(
                        f"blackout window active ({bw.reason or 'no reason'})"
                    )
                    break

        # 4. Rate limit
        with self._lock:
            window_start = now - policy.rate_limit_window_seconds
            count = sum(
                1
                for aid, atype, ts in self._action_log
                if aid == agent_id and ts >= window_start
            )
        if count >= policy.max_actions_per_window:
            violations.append(
                f"rate limit exceeded ({count}/{policy.max_actions_per_window})"
            )

        return PolicyCheckResult(
            allowed=len(violations) == 0,
            agent_id=agent_id,
            action_type=action_type,
            violations=tuple(violations),
        )

    def record_action(
        self,
        agent_id: str,
        action_type: str,
        timestamp: Optional[float] = None,
    ) -> None:
        """Record an executed action for rate-limit tracking."""
        ts = timestamp if timestamp is not None else time.time()
        with self._lock:
            self._action_log.append((agent_id, action_type, ts))
            if len(self._action_log) > self._max_log:
                self._action_log = self._action_log[-self._max_log:]

    def reset(self) -> None:
        """Clear all action history."""
        with self._lock:
            self._action_log.clear()
