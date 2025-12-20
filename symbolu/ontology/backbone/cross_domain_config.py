"""
Cross-Domain Learning Configuration
====================================

Admin-level configuration for cross-domain learning policies.
This is SYSTEM-WIDE, not per-persona.

Controls:
    - Which domain pairs can learn from each other
    - Minimum thresholds for cross-domain transfer
    - Blocked pairs (dangerous or unreliable)
    - Counters for blocked/successful transfers

The config file (JSON) allows admins to:
    1. Enable/disable cross-domain learning globally
    2. Set per-pair policies and thresholds
    3. Block specific domain pairs
    4. Track where learning fails (for tuning)
"""

import json
import os
from dataclasses import dataclass, field, asdict
from typing import Dict, Optional, List, Set, Any, Tuple
from datetime import datetime
from pathlib import Path
from enum import Enum


class DomainPairPolicy(Enum):
    """Policy for a domain pair."""
    ALLOW = "allow"           # Cross-domain learning enabled
    BLOCK = "block"           # Cross-domain learning blocked
    REQUIRE_HIGH = "require_high"  # Requires higher thresholds
    MONITOR = "monitor"       # Allow but track closely


@dataclass
class DomainPairConfig:
    """Configuration for a specific domain pair."""
    domain_a: str
    domain_b: str
    policy: DomainPairPolicy = DomainPairPolicy.ALLOW

    # Thresholds (override defaults if set)
    min_structural_threshold: Optional[float] = None  # 10D similarity
    min_causal_threshold: Optional[float] = None      # Causal chain overlap
    min_combined_threshold: Optional[float] = None    # Combined score

    # Metadata
    reason: str = ""
    created_at: str = ""
    updated_at: str = ""

    @property
    def pair_key(self) -> str:
        """Canonical key for this pair (sorted alphabetically)."""
        return "_".join(sorted([self.domain_a.lower(), self.domain_b.lower()]))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "domain_a": self.domain_a,
            "domain_b": self.domain_b,
            "policy": self.policy.value,
            "min_structural_threshold": self.min_structural_threshold,
            "min_causal_threshold": self.min_causal_threshold,
            "min_combined_threshold": self.min_combined_threshold,
            "reason": self.reason,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DomainPairConfig":
        return cls(
            domain_a=data["domain_a"],
            domain_b=data["domain_b"],
            policy=DomainPairPolicy(data.get("policy", "allow")),
            min_structural_threshold=data.get("min_structural_threshold"),
            min_causal_threshold=data.get("min_causal_threshold"),
            min_combined_threshold=data.get("min_combined_threshold"),
            reason=data.get("reason", ""),
            created_at=data.get("created_at", ""),
            updated_at=data.get("updated_at", ""),
        )


@dataclass
class CrossDomainCounters:
    """
    Counters for cross-domain learning attempts.

    Tracks where learning succeeds and fails for admin visibility.
    """
    # Per-pair counters
    blocked_attempts: Dict[str, int] = field(default_factory=dict)
    successful_transfers: Dict[str, int] = field(default_factory=dict)
    threshold_failures: Dict[str, int] = field(default_factory=dict)

    # Global counters
    total_blocked: int = 0
    total_successful: int = 0
    total_threshold_failures: int = 0

    # Last reset
    last_reset: str = ""

    def record_blocked(self, pair_key: str):
        """Record a blocked cross-domain attempt."""
        self.blocked_attempts[pair_key] = self.blocked_attempts.get(pair_key, 0) + 1
        self.total_blocked += 1

    def record_success(self, pair_key: str):
        """Record a successful cross-domain transfer."""
        self.successful_transfers[pair_key] = self.successful_transfers.get(pair_key, 0) + 1
        self.total_successful += 1

    def record_threshold_failure(self, pair_key: str):
        """Record a threshold failure (below min thresholds)."""
        self.threshold_failures[pair_key] = self.threshold_failures.get(pair_key, 0) + 1
        self.total_threshold_failures += 1

    def reset(self):
        """Reset all counters."""
        self.blocked_attempts = {}
        self.successful_transfers = {}
        self.threshold_failures = {}
        self.total_blocked = 0
        self.total_successful = 0
        self.total_threshold_failures = 0
        self.last_reset = datetime.utcnow().isoformat()

    def get_problem_pairs(self, min_failures: int = 5) -> List[Tuple[str, int]]:
        """Get pairs with high failure rates."""
        problems = []
        for pair_key, failures in self.threshold_failures.items():
            if failures >= min_failures:
                successes = self.successful_transfers.get(pair_key, 0)
                if successes == 0 or failures / (failures + successes) > 0.5:
                    problems.append((pair_key, failures))
        return sorted(problems, key=lambda x: -x[1])

    def to_dict(self) -> Dict[str, Any]:
        return {
            "blocked_attempts": self.blocked_attempts,
            "successful_transfers": self.successful_transfers,
            "threshold_failures": self.threshold_failures,
            "total_blocked": self.total_blocked,
            "total_successful": self.total_successful,
            "total_threshold_failures": self.total_threshold_failures,
            "last_reset": self.last_reset,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CrossDomainCounters":
        counters = cls()
        counters.blocked_attempts = data.get("blocked_attempts", {})
        counters.successful_transfers = data.get("successful_transfers", {})
        counters.threshold_failures = data.get("threshold_failures", {})
        counters.total_blocked = data.get("total_blocked", 0)
        counters.total_successful = data.get("total_successful", 0)
        counters.total_threshold_failures = data.get("total_threshold_failures", 0)
        counters.last_reset = data.get("last_reset", "")
        return counters


@dataclass
class CrossDomainConfig:
    """
    Master configuration for cross-domain learning.

    This is the admin-level config that controls system-wide behavior.
    """
    # Global settings
    enabled: bool = True
    default_policy: DomainPairPolicy = DomainPairPolicy.ALLOW

    # Default thresholds (can be overridden per-pair)
    default_structural_threshold: float = 0.5
    default_causal_threshold: float = 0.3
    default_combined_threshold: float = 0.4

    # Per-pair configurations
    domain_pairs: Dict[str, DomainPairConfig] = field(default_factory=dict)

    # Explicitly blocked pairs (quick lookup)
    blocked_pairs: Set[str] = field(default_factory=set)

    # Counters
    counters: CrossDomainCounters = field(default_factory=CrossDomainCounters)

    # Metadata
    version: str = "1.0"
    last_updated: str = ""

    def _make_pair_key(self, domain_a: str, domain_b: str) -> str:
        """Create canonical pair key."""
        return "_".join(sorted([domain_a.lower(), domain_b.lower()]))

    def is_pair_allowed(self, domain_a: str, domain_b: str) -> bool:
        """Check if cross-domain learning is allowed for this pair."""
        if not self.enabled:
            return False

        pair_key = self._make_pair_key(domain_a, domain_b)

        # Check explicit blocks
        if pair_key in self.blocked_pairs:
            self.counters.record_blocked(pair_key)
            return False

        # Check pair-specific config
        if pair_key in self.domain_pairs:
            config = self.domain_pairs[pair_key]
            if config.policy == DomainPairPolicy.BLOCK:
                self.counters.record_blocked(pair_key)
                return False

        # Use default policy
        if self.default_policy == DomainPairPolicy.BLOCK:
            self.counters.record_blocked(pair_key)
            return False

        return True

    def get_thresholds(self, domain_a: str, domain_b: str) -> Dict[str, float]:
        """Get thresholds for a domain pair."""
        pair_key = self._make_pair_key(domain_a, domain_b)

        # Start with defaults
        thresholds = {
            "structural": self.default_structural_threshold,
            "causal": self.default_causal_threshold,
            "combined": self.default_combined_threshold,
        }

        # Override with pair-specific if available
        if pair_key in self.domain_pairs:
            config = self.domain_pairs[pair_key]
            if config.min_structural_threshold is not None:
                thresholds["structural"] = config.min_structural_threshold
            if config.min_causal_threshold is not None:
                thresholds["causal"] = config.min_causal_threshold
            if config.min_combined_threshold is not None:
                thresholds["combined"] = config.min_combined_threshold

            # REQUIRE_HIGH policy doubles thresholds
            if config.policy == DomainPairPolicy.REQUIRE_HIGH:
                thresholds = {k: min(v * 1.5, 0.95) for k, v in thresholds.items()}

        return thresholds

    def block_pair(self, domain_a: str, domain_b: str, reason: str = ""):
        """Block a domain pair from cross-domain learning."""
        pair_key = self._make_pair_key(domain_a, domain_b)
        self.blocked_pairs.add(pair_key)

        # Also update/create pair config
        self.domain_pairs[pair_key] = DomainPairConfig(
            domain_a=domain_a.lower(),
            domain_b=domain_b.lower(),
            policy=DomainPairPolicy.BLOCK,
            reason=reason,
            created_at=datetime.utcnow().isoformat(),
            updated_at=datetime.utcnow().isoformat(),
        )
        self.last_updated = datetime.utcnow().isoformat()

    def allow_pair(self, domain_a: str, domain_b: str):
        """Allow a domain pair for cross-domain learning."""
        pair_key = self._make_pair_key(domain_a, domain_b)
        self.blocked_pairs.discard(pair_key)

        if pair_key in self.domain_pairs:
            self.domain_pairs[pair_key].policy = DomainPairPolicy.ALLOW
            self.domain_pairs[pair_key].updated_at = datetime.utcnow().isoformat()

        self.last_updated = datetime.utcnow().isoformat()

    def set_pair_thresholds(
        self,
        domain_a: str,
        domain_b: str,
        structural: Optional[float] = None,
        causal: Optional[float] = None,
        combined: Optional[float] = None,
    ):
        """Set custom thresholds for a domain pair."""
        pair_key = self._make_pair_key(domain_a, domain_b)

        if pair_key not in self.domain_pairs:
            self.domain_pairs[pair_key] = DomainPairConfig(
                domain_a=domain_a.lower(),
                domain_b=domain_b.lower(),
                created_at=datetime.utcnow().isoformat(),
            )

        config = self.domain_pairs[pair_key]
        if structural is not None:
            config.min_structural_threshold = structural
        if causal is not None:
            config.min_causal_threshold = causal
        if combined is not None:
            config.min_combined_threshold = combined
        config.updated_at = datetime.utcnow().isoformat()

        self.last_updated = datetime.utcnow().isoformat()

    def record_transfer_result(
        self,
        domain_a: str,
        domain_b: str,
        success: bool,
        threshold_met: bool = True,
    ):
        """Record the result of a cross-domain transfer attempt."""
        pair_key = self._make_pair_key(domain_a, domain_b)

        if success:
            self.counters.record_success(pair_key)
        elif not threshold_met:
            self.counters.record_threshold_failure(pair_key)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "enabled": self.enabled,
            "default_policy": self.default_policy.value,
            "default_structural_threshold": self.default_structural_threshold,
            "default_causal_threshold": self.default_causal_threshold,
            "default_combined_threshold": self.default_combined_threshold,
            "domain_pairs": {k: v.to_dict() for k, v in self.domain_pairs.items()},
            "blocked_pairs": list(self.blocked_pairs),
            "counters": self.counters.to_dict(),
            "version": self.version,
            "last_updated": self.last_updated,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CrossDomainConfig":
        config = cls()
        config.enabled = data.get("enabled", True)
        config.default_policy = DomainPairPolicy(data.get("default_policy", "allow"))
        config.default_structural_threshold = data.get("default_structural_threshold", 0.5)
        config.default_causal_threshold = data.get("default_causal_threshold", 0.3)
        config.default_combined_threshold = data.get("default_combined_threshold", 0.4)

        # Load domain pairs
        for key, pair_data in data.get("domain_pairs", {}).items():
            config.domain_pairs[key] = DomainPairConfig.from_dict(pair_data)

        config.blocked_pairs = set(data.get("blocked_pairs", []))

        if "counters" in data:
            config.counters = CrossDomainCounters.from_dict(data["counters"])

        config.version = data.get("version", "1.0")
        config.last_updated = data.get("last_updated", "")

        return config


# =============================================================================
# Config File Management
# =============================================================================

DEFAULT_CONFIG_PATH = Path(__file__).parent / "cross_domain_config.json"


def load_config(path: Optional[Path] = None) -> CrossDomainConfig:
    """
    Load cross-domain config from JSON file.

    Creates default config if file doesn't exist.
    """
    config_path = path or DEFAULT_CONFIG_PATH

    if config_path.exists():
        with open(config_path, "r") as f:
            data = json.load(f)
        return CrossDomainConfig.from_dict(data)

    # Create default config
    config = create_default_config()
    save_config(config, config_path)
    return config


def save_config(config: CrossDomainConfig, path: Optional[Path] = None):
    """Save cross-domain config to JSON file."""
    config_path = path or DEFAULT_CONFIG_PATH

    with open(config_path, "w") as f:
        json.dump(config.to_dict(), f, indent=2)


def create_default_config() -> CrossDomainConfig:
    """
    Create default cross-domain config with sensible defaults.

    Includes some pre-configured blocked pairs for safety.
    """
    config = CrossDomainConfig(
        enabled=True,
        default_policy=DomainPairPolicy.ALLOW,
        default_structural_threshold=0.5,
        default_causal_threshold=0.3,
        default_combined_threshold=0.4,
        version="1.0",
        last_updated=datetime.utcnow().isoformat(),
    )

    # Block potentially dangerous pairs
    config.block_pair(
        "fiction", "medicine",
        reason="Fictional medical patterns could be dangerous if transferred"
    )
    config.block_pair(
        "entertainment", "medicine",
        reason="Entertainment patterns unreliable for medical context"
    )
    config.block_pair(
        "fiction", "finance",
        reason="Fictional financial patterns unreliable for real decisions"
    )

    # Require higher thresholds for sensitive pairs
    config.domain_pairs["finance_politics"] = DomainPairConfig(
        domain_a="finance",
        domain_b="politics",
        policy=DomainPairPolicy.REQUIRE_HIGH,
        reason="Political-financial transfers need high confidence",
        created_at=datetime.utcnow().isoformat(),
    )

    config.domain_pairs["medicine_religion"] = DomainPairConfig(
        domain_a="medicine",
        domain_b="religion",
        policy=DomainPairPolicy.REQUIRE_HIGH,
        reason="Medical-religious transfers need high confidence",
        created_at=datetime.utcnow().isoformat(),
    )

    return config


# =============================================================================
# Global Config Instance
# =============================================================================

_config: Optional[CrossDomainConfig] = None


def get_cross_domain_config() -> CrossDomainConfig:
    """Get or load the global cross-domain config."""
    global _config
    if _config is None:
        _config = load_config()
    return _config


def reload_config():
    """Reload config from disk."""
    global _config
    _config = load_config()


def get_counters_report() -> Dict[str, Any]:
    """Get a report of cross-domain learning counters."""
    config = get_cross_domain_config()
    counters = config.counters

    return {
        "summary": {
            "total_successful": counters.total_successful,
            "total_blocked": counters.total_blocked,
            "total_threshold_failures": counters.total_threshold_failures,
            "success_rate": (
                counters.total_successful /
                (counters.total_successful + counters.total_threshold_failures)
                if (counters.total_successful + counters.total_threshold_failures) > 0
                else 0.0
            ),
        },
        "problem_pairs": counters.get_problem_pairs(),
        "top_successful": sorted(
            counters.successful_transfers.items(),
            key=lambda x: -x[1]
        )[:10],
        "top_blocked": sorted(
            counters.blocked_attempts.items(),
            key=lambda x: -x[1]
        )[:10],
        "last_reset": counters.last_reset,
    }


__all__ = [
    # Enums
    "DomainPairPolicy",
    # Data classes
    "DomainPairConfig",
    "CrossDomainCounters",
    "CrossDomainConfig",
    # Functions
    "load_config",
    "save_config",
    "create_default_config",
    "get_cross_domain_config",
    "reload_config",
    "get_counters_report",
]
