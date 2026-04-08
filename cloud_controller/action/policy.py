"""Policy Engine — customer-configurable safety limits beyond SafetyBounds.

SafetyBounds (recommend/safety.py) enforces per-action rate limits
(+50% / -25%). The policy engine adds business-level constraints:

  1. Absolute replica bounds: hard min/max per deployment
  2. Blackout windows: time ranges where scaling is blocked
  3. Rate limits: max actions per time period
  4. Deployment-specific overrides

Design doc reference: Stage 5, line 561:
  "Policy engine: customer-configurable safety limits
   (max replicas, max change rate, blackout windows)"

The policy engine runs BEFORE the actuator — if a policy check fails,
the action is blocked and the reason is logged.
"""

import logging
import time
import threading
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


@dataclass
class BlackoutWindow:
    """A time window during which scaling is blocked.

    Times are in 24-hour format as hours + minutes (e.g. 2:30 AM = 2.5).
    """
    start_hour: float      # 0.0 - 23.99
    end_hour: float        # 0.0 - 23.99 (wraps past midnight if end < start)
    days: List[int] = field(default_factory=lambda: [0, 1, 2, 3, 4, 5, 6])
    reason: str = ""

    def is_active(self, current_time: Optional[float] = None) -> bool:
        """Check if the blackout window is currently active."""
        if current_time is None:
            current_time = time.time()

        lt = time.localtime(current_time)
        current_day = lt.tm_wday  # Monday=0, Sunday=6
        current_hour = lt.tm_hour + lt.tm_min / 60.0

        if current_day not in self.days:
            return False

        if self.start_hour <= self.end_hour:
            # Normal range (e.g. 2:00 - 4:00)
            return self.start_hour <= current_hour < self.end_hour
        else:
            # Wraps midnight (e.g. 23:00 - 1:00)
            return current_hour >= self.start_hour or current_hour < self.end_hour


@dataclass
class DeploymentPolicy:
    """Policy constraints for a specific deployment."""
    # Absolute replica bounds
    min_replicas: int = 1
    max_replicas: int = 100
    # Blackout windows
    blackout_windows: List[BlackoutWindow] = field(default_factory=list)
    # Rate limit: max scaling actions within the window
    max_actions_per_window: int = 10
    rate_limit_window_seconds: float = 3600.0  # 1 hour


@dataclass
class PolicyConfig:
    """Global policy configuration."""
    # Default policy for deployments without specific overrides
    default_policy: DeploymentPolicy = field(default_factory=DeploymentPolicy)
    # Per-deployment overrides (key = "namespace/deployment")
    deployment_overrides: Dict[str, DeploymentPolicy] = field(default_factory=dict)


@dataclass
class PolicyCheckResult:
    """Result of a policy check."""
    allowed: bool
    deployment: str
    namespace: str
    target_replicas: int
    violations: List[str] = field(default_factory=list)

    @property
    def reason(self) -> str:
        return "; ".join(self.violations) if self.violations else "Policy check passed"


class PolicyEngine:
    """Enforces customer-configurable scaling policies.

    Usage:
        policy = PolicyEngine(PolicyConfig(
            default_policy=DeploymentPolicy(max_replicas=50),
            deployment_overrides={
                "prod/api-gateway": DeploymentPolicy(
                    min_replicas=3, max_replicas=20,
                    blackout_windows=[BlackoutWindow(2.0, 4.0, reason="maintenance")],
                ),
            },
        ))
        result = policy.check("api-gateway", "prod", current=5, target=25)
        # result.allowed = False, violations = ["max_replicas exceeded: 25 > 20"]
    """

    def __init__(self, config: Optional[PolicyConfig] = None):
        self.config = config or PolicyConfig()
        self._action_log: List[Tuple[str, float]] = []  # (deployment_key, timestamp)
        self._max_log = 10000
        self._lock = threading.Lock()

    def _get_policy(self, deployment: str, namespace: str) -> DeploymentPolicy:
        """Get the policy for a deployment (override or default)."""
        key = f"{namespace}/{deployment}"
        return self.config.deployment_overrides.get(key, self.config.default_policy)

    def check(
        self,
        deployment: str,
        namespace: str,
        current_replicas: int,
        target_replicas: int,
        current_time: Optional[float] = None,
    ) -> PolicyCheckResult:
        """Check if a scaling action is allowed by policy.

        Args:
            deployment: K8s deployment name.
            namespace: K8s namespace.
            current_replicas: Current replica count.
            target_replicas: Desired replica count.
            current_time: Current timestamp (defaults to now).

        Returns:
            PolicyCheckResult with allowed/denied and violation reasons.
        """
        if current_time is None:
            current_time = time.time()

        policy = self._get_policy(deployment, namespace)
        violations = []

        # 1. Check absolute replica bounds
        if target_replicas > policy.max_replicas:
            violations.append(
                f"Exceeds max replicas: {target_replicas} > {policy.max_replicas}"
            )
        if target_replicas < policy.min_replicas:
            violations.append(
                f"Below min replicas: {target_replicas} < {policy.min_replicas}"
            )

        # 2. Check blackout windows
        for window in policy.blackout_windows:
            if window.is_active(current_time):
                reason = window.reason or "blackout window active"
                violations.append(
                    f"Blackout: {reason} "
                    f"({window.start_hour:.1f}h-{window.end_hour:.1f}h)"
                )

        # 3. Check rate limit
        key = f"{namespace}/{deployment}"
        with self._lock:
            cutoff = current_time - policy.rate_limit_window_seconds
            recent_count = sum(
                1 for k, ts in self._action_log
                if k == key and ts > cutoff
            )
        if recent_count >= policy.max_actions_per_window:
            violations.append(
                f"Rate limit: {recent_count} actions in last "
                f"{policy.rate_limit_window_seconds:.0f}s "
                f"(max {policy.max_actions_per_window})"
            )

        result = PolicyCheckResult(
            allowed=len(violations) == 0,
            deployment=deployment,
            namespace=namespace,
            target_replicas=target_replicas,
            violations=violations,
        )

        if not result.allowed:
            logger.warning(
                "Policy DENIED %s/%s -> %d replicas: %s",
                namespace, deployment, target_replicas, result.reason,
            )

        return result

    def record_action(
        self,
        deployment: str,
        namespace: str,
        timestamp: Optional[float] = None,
    ) -> None:
        """Record that a scaling action was executed (for rate limiting)."""
        key = f"{namespace}/{deployment}"
        ts = timestamp or time.time()
        with self._lock:
            self._action_log.append((key, ts))
            if len(self._action_log) > self._max_log:
                self._action_log = self._action_log[-self._max_log:]

    def reset(self) -> None:
        """Clear action log."""
        with self._lock:
            self._action_log.clear()
