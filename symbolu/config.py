"""
Symbol-U Configuration
======================

Configuration for Symbol-U's pluggable provider architecture.
Supports two modes:
- "enterprise": Symbolic/auditable providers (hash embedding, phoneme routing)
- "consumer": Pre-trained/semantic providers (learned embedding, trained routing)

License Types:
- ENT-XXXX-XXXX-XXXX: Enterprise license (symbolic providers only)
- CON-XXXX-XXXX-XXXX: Consumer license (learned providers only)
- DEV-XXXX-XXXX-XXXX: Development license (full access)

Usage:
    from symbolu.config import SymboluConfig

    # Enterprise mode with license
    config = SymboluConfig(
        mode="enterprise",
        license_key="ENT-ABCD-1234-EFGH",
    )

    # Consumer mode with license
    config = SymboluConfig(
        mode="consumer",
        license_key="CON-WXYZ-5678-IJKL",
    )

    # Development mode (no license required)
    config = SymboluConfig(mode="enterprise", enforce_license=False)
"""

from dataclasses import dataclass, field
from typing import Literal, Optional, Dict, Any


@dataclass
class SymboluConfig:
    """
    Configuration for Symbol-U provider selection.

    Attributes:
        mode: Provider mode - "enterprise" (symbolic) or "consumer" (pre-trained)
        license_key: License key for feature validation
        enforce_license: Whether to enforce license validation (default: False for dev)
        audit_enabled: Enable audit logging (auto-set True for enterprise)
        embedding_config: Provider-specific embedding configuration
        router_config: Provider-specific router configuration
        filter_config: Provider-specific filter configuration
    """

    mode: Literal["enterprise", "consumer"] = "enterprise"
    license_key: str = ""
    enforce_license: bool = False
    audit_enabled: bool = False
    embedding_config: Dict[str, Any] = field(default_factory=dict)
    router_config: Dict[str, Any] = field(default_factory=dict)
    filter_config: Dict[str, Any] = field(default_factory=dict)

    # Cached license features
    _license_features: Optional[Any] = field(default=None, repr=False)

    def __post_init__(self):
        """Auto-configure based on mode and validate license."""
        # Enterprise mode always has audit enabled
        if self.mode == "enterprise":
            self.audit_enabled = True

        # Validate mode
        if self.mode not in ("enterprise", "consumer"):
            raise ValueError(
                f"Invalid mode: {self.mode}. Must be 'enterprise' or 'consumer'"
            )

        # Validate license if enforcement is enabled
        if self.enforce_license:
            self._validate_license()

    def _validate_license(self):
        """Validate license for the requested mode."""
        from symbolu.licensing import get_available_features, LicenseError

        features = get_available_features(self.license_key)
        self._license_features = features

        if not features.is_valid:
            raise ValueError(
                f"Invalid license key. Please provide a valid license."
            )

        if not features.validate_mode(self.mode):
            raise ValueError(
                f"License does not allow {self.mode} mode. "
                f"Your license type: {features.license_type.value}"
            )

    @property
    def license_features(self) -> Optional[Any]:
        """Get cached license features (if validated)."""
        if self._license_features is None and self.license_key:
            from symbolu.licensing import get_available_features
            self._license_features = get_available_features(self.license_key)
        return self._license_features

    @property
    def is_enterprise(self) -> bool:
        """Check if running in enterprise mode."""
        return self.mode == "enterprise"

    @property
    def is_consumer(self) -> bool:
        """Check if running in consumer mode."""
        return self.mode == "consumer"

    def get_embedding_dim(self) -> int:
        """
        Get the embedding dimension for the current mode.

        Returns:
            256 for enterprise (hash-based)
            768 for consumer (pre-trained)
        """
        if self.mode == "enterprise":
            return 256
        else:
            return 768

    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary."""
        return {
            "mode": self.mode,
            "license_key": self.license_key,
            "audit_enabled": self.audit_enabled,
            "embedding_config": self.embedding_config,
            "router_config": self.router_config,
            "filter_config": self.filter_config,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SymboluConfig":
        """Create configuration from dictionary."""
        return cls(
            mode=data.get("mode", "enterprise"),
            license_key=data.get("license_key", ""),
            audit_enabled=data.get("audit_enabled", False),
            embedding_config=data.get("embedding_config", {}),
            router_config=data.get("router_config", {}),
            filter_config=data.get("filter_config", {}),
        )


# Default configurations
DEFAULT_ENTERPRISE_CONFIG = SymboluConfig(mode="enterprise")
DEFAULT_CONSUMER_CONFIG = SymboluConfig(mode="consumer")
