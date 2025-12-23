"""
Symbol-U Token Usage Tracker

Tracks LLM token usage per user/session with daily limits.

Features:
    - Per-request token tracking
    - Daily usage accumulation
    - Configurable limits per tier
    - Cost estimation

Example:
    tracker = UsageTracker()

    # Record usage
    tracker.record_usage(
        user_id="demo_user",
        tier="power_user",
        input_tokens=150,
        output_tokens=500,
        provider="anthropic",
        model="claude-3-5-sonnet"
    )

    # Get usage stats
    stats = tracker.get_usage("demo_user")
    print(f"Today: {stats['daily_tokens']} tokens, ${stats['daily_cost']:.4f}")
"""

import os
import logging
from dataclasses import dataclass, field
from datetime import datetime, date
from typing import Dict, Optional, List
from threading import Lock
from enum import Enum

logger = logging.getLogger(__name__)


# ============================================================================
# CONFIGURATION
# ============================================================================

class UsageTier(Enum):
    """Usage tier limits."""
    FREE = "free"
    DEMO = "demo"
    STANDARD = "standard"
    ENTERPRISE = "enterprise"


# Default daily token limits per tier
DEFAULT_LIMITS = {
    UsageTier.FREE: 10_000,        # 10K tokens/day
    UsageTier.DEMO: 50_000,        # 50K tokens/day
    UsageTier.STANDARD: 500_000,   # 500K tokens/day
    UsageTier.ENTERPRISE: None,    # Unlimited
}

# Cost per 1M tokens (input/output)
COST_PER_MILLION = {
    "anthropic": {
        "claude-3-5-haiku-20241022": {"input": 0.80, "output": 4.00},
        "claude-3-5-sonnet-20241022": {"input": 3.00, "output": 15.00},
    },
    "google": {
        "gemini-1.5-flash": {"input": 0.075, "output": 0.30},
        "gemini-1.5-pro": {"input": 1.25, "output": 5.00},
    }
}


@dataclass
class UsageRecord:
    """Single usage record."""
    timestamp: datetime
    input_tokens: int
    output_tokens: int
    provider: str
    model: str
    tier: str
    cost: float = 0.0


@dataclass
class UserUsage:
    """User's accumulated usage."""
    user_id: str
    usage_tier: UsageTier = UsageTier.DEMO
    daily_limit: Optional[int] = None
    records: List[UsageRecord] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)

    @property
    def today_records(self) -> List[UsageRecord]:
        """Get today's records."""
        today = date.today()
        return [r for r in self.records if r.timestamp.date() == today]

    @property
    def daily_tokens(self) -> int:
        """Total tokens used today."""
        return sum(r.input_tokens + r.output_tokens for r in self.today_records)

    @property
    def daily_input_tokens(self) -> int:
        """Input tokens used today."""
        return sum(r.input_tokens for r in self.today_records)

    @property
    def daily_output_tokens(self) -> int:
        """Output tokens used today."""
        return sum(r.output_tokens for r in self.today_records)

    @property
    def daily_cost(self) -> float:
        """Estimated cost today."""
        return sum(r.cost for r in self.today_records)

    @property
    def total_tokens(self) -> int:
        """Total tokens used all time."""
        return sum(r.input_tokens + r.output_tokens for r in self.records)

    @property
    def total_cost(self) -> float:
        """Total estimated cost all time."""
        return sum(r.cost for r in self.records)

    @property
    def request_count_today(self) -> int:
        """Number of requests today."""
        return len(self.today_records)


# ============================================================================
# USAGE TRACKER
# ============================================================================

class UsageTracker:
    """
    Thread-safe token usage tracker.

    Tracks token consumption per user with daily limits and cost estimation.
    """

    def __init__(self):
        self._users: Dict[str, UserUsage] = {}
        self._lock = Lock()

        # Load custom limits from environment
        self._custom_daily_limit = int(os.getenv("DAILY_TOKEN_LIMIT", "50000"))

    def _get_or_create_user(self, user_id: str) -> UserUsage:
        """Get or create user usage record."""
        if user_id not in self._users:
            self._users[user_id] = UserUsage(
                user_id=user_id,
                daily_limit=self._custom_daily_limit,
            )
        return self._users[user_id]

    def _calculate_cost(
        self,
        input_tokens: int,
        output_tokens: int,
        provider: str,
        model: str
    ) -> float:
        """Calculate cost for token usage."""
        provider_costs = COST_PER_MILLION.get(provider, {})
        model_costs = provider_costs.get(model, {"input": 3.0, "output": 15.0})

        input_cost = (input_tokens / 1_000_000) * model_costs["input"]
        output_cost = (output_tokens / 1_000_000) * model_costs["output"]

        return input_cost + output_cost

    def record_usage(
        self,
        user_id: str,
        input_tokens: int,
        output_tokens: int,
        provider: str,
        model: str,
        tier: str = "power_user",
    ) -> Dict:
        """
        Record token usage for a user.

        Args:
            user_id: User identifier
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens
            provider: LLM provider (anthropic, google)
            model: Model name
            tier: Presentation tier

        Returns:
            Dict with usage stats and limit info
        """
        with self._lock:
            user = self._get_or_create_user(user_id)

            # Calculate cost
            cost = self._calculate_cost(input_tokens, output_tokens, provider, model)

            # Create record
            record = UsageRecord(
                timestamp=datetime.now(),
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                provider=provider,
                model=model,
                tier=tier,
                cost=cost,
            )

            user.records.append(record)

            # Check if over limit
            is_over_limit = False
            remaining = None
            if user.daily_limit:
                remaining = max(0, user.daily_limit - user.daily_tokens)
                is_over_limit = user.daily_tokens > user.daily_limit

            return {
                "recorded": True,
                "this_request": {
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens,
                    "total_tokens": input_tokens + output_tokens,
                    "cost": round(cost, 6),
                },
                "daily": {
                    "input_tokens": user.daily_input_tokens,
                    "output_tokens": user.daily_output_tokens,
                    "total_tokens": user.daily_tokens,
                    "cost": round(user.daily_cost, 4),
                    "requests": user.request_count_today,
                },
                "limit": {
                    "daily_limit": user.daily_limit,
                    "remaining": remaining,
                    "is_over_limit": is_over_limit,
                },
            }

    def get_usage(self, user_id: str) -> Dict:
        """
        Get usage statistics for a user.

        Args:
            user_id: User identifier

        Returns:
            Dict with usage statistics
        """
        with self._lock:
            if user_id not in self._users:
                return {
                    "user_id": user_id,
                    "daily": {
                        "input_tokens": 0,
                        "output_tokens": 0,
                        "total_tokens": 0,
                        "cost": 0.0,
                        "requests": 0,
                    },
                    "total": {
                        "tokens": 0,
                        "cost": 0.0,
                        "requests": 0,
                    },
                    "limit": {
                        "daily_limit": self._custom_daily_limit,
                        "remaining": self._custom_daily_limit,
                        "is_over_limit": False,
                    },
                }

            user = self._users[user_id]
            remaining = None
            if user.daily_limit:
                remaining = max(0, user.daily_limit - user.daily_tokens)

            return {
                "user_id": user_id,
                "daily": {
                    "input_tokens": user.daily_input_tokens,
                    "output_tokens": user.daily_output_tokens,
                    "total_tokens": user.daily_tokens,
                    "cost": round(user.daily_cost, 4),
                    "requests": user.request_count_today,
                },
                "total": {
                    "tokens": user.total_tokens,
                    "cost": round(user.total_cost, 4),
                    "requests": len(user.records),
                },
                "limit": {
                    "daily_limit": user.daily_limit,
                    "remaining": remaining,
                    "is_over_limit": user.daily_tokens > (user.daily_limit or float('inf')),
                },
            }

    def check_limit(self, user_id: str, estimated_tokens: int = 0) -> Dict:
        """
        Check if user is within their daily limit.

        Args:
            user_id: User identifier
            estimated_tokens: Estimated tokens for next request

        Returns:
            Dict with limit check result
        """
        with self._lock:
            if user_id not in self._users:
                return {
                    "allowed": True,
                    "remaining": self._custom_daily_limit,
                    "daily_limit": self._custom_daily_limit,
                }

            user = self._users[user_id]
            if user.daily_limit is None:
                return {
                    "allowed": True,
                    "remaining": None,
                    "daily_limit": None,
                }

            remaining = user.daily_limit - user.daily_tokens
            allowed = remaining >= estimated_tokens

            return {
                "allowed": allowed,
                "remaining": max(0, remaining),
                "daily_limit": user.daily_limit,
                "current_usage": user.daily_tokens,
            }

    def reset_daily(self, user_id: Optional[str] = None):
        """
        Reset daily usage (for testing or manual reset).

        Args:
            user_id: Specific user to reset, or None for all users
        """
        with self._lock:
            if user_id:
                if user_id in self._users:
                    # Keep only non-today records
                    today = date.today()
                    self._users[user_id].records = [
                        r for r in self._users[user_id].records
                        if r.timestamp.date() != today
                    ]
            else:
                # Reset all users
                today = date.today()
                for user in self._users.values():
                    user.records = [
                        r for r in user.records
                        if r.timestamp.date() != today
                    ]


# ============================================================================
# SINGLETON
# ============================================================================

_tracker: Optional[UsageTracker] = None


def get_usage_tracker() -> UsageTracker:
    """Get or create the global usage tracker."""
    global _tracker
    if _tracker is None:
        _tracker = UsageTracker()
    return _tracker
