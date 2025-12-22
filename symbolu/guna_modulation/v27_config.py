"""
v2.7 Configuration Module
=========================

Comprehensive configuration for SymbolU v2.7 State Evolution Layer.

Includes:
- UtilityCoefficients: Operator-configurable utility term signs
- ToneLogitConfig: Named, bounded tone coefficients
- AlphaConfig: Tier-specific learning rates with half-life
- StatePersistenceConfig: State storage and decay semantics
- V27Config: Master configuration combining all above

Version: 2.7.1
Date: 2025-12-22
"""

from dataclasses import dataclass, field
from typing import Optional, Dict
import math


# =============================================================================
# Constants
# =============================================================================

# Tier identifiers
TIER_ENTERPRISE_1 = "enterprise_tier_1"
TIER_ENTERPRISE_2 = "enterprise_tier_2"
TIER_CONSUMER = "consumer"

# Validation epsilon
VALIDATION_EPSILON: float = 1e-6


# =============================================================================
# Utility Coefficients (Fix #1)
# =============================================================================

@dataclass(frozen=True)
class UtilityCoefficients:
    """
    Operator-configurable utility term signs and weights.

    The utility formula becomes:
        U_t = (c_S × w_S × s + c_R × w_R × r + c_T × w_T × t)
              + λ_H × H + λ_C × C_contr + λ_F × F_fail

    By default:
        - Sattva contributes positively (+1)
        - Rajas/Tamas contribute negatively (-1)
        - Penalties are negative (entropy, contradiction, failure)

    Operators can flip signs to change the objective.

    Attributes:
        c_S: Sattva contribution sign/weight (default +1.0)
        c_R: Rajas contribution sign/weight (default -1.0)
        c_T: Tamas contribution sign/weight (default -1.0)
        lambda_H: Entropy coefficient (default -0.3, penalty)
        lambda_C: Contradiction coefficient (default -0.5, penalty)
        lambda_F: Failure coefficient (default -0.4, penalty)
    """
    # Guna contribution signs (positive = reward, negative = penalty)
    c_S: float = 1.0    # Sattva contribution
    c_R: float = -1.0   # Rajas contribution
    c_T: float = -1.0   # Tamas contribution

    # Penalty coefficients (typically negative)
    lambda_H: float = -0.3   # Entropy penalty
    lambda_C: float = -0.5   # Contradiction penalty
    lambda_F: float = -0.4   # Failure penalty

    def __post_init__(self):
        """Validate coefficient bounds."""
        # Guna coefficients must be bounded to prevent runaway utility
        total_guna = abs(self.c_S) + abs(self.c_R) + abs(self.c_T)
        if total_guna > 3.0 + VALIDATION_EPSILON:
            raise ValueError(
                f"|c_S| + |c_R| + |c_T| must be ≤ 3, got {total_guna}"
            )

        # Lambda coefficients should be bounded
        for name, val in [("lambda_H", self.lambda_H),
                          ("lambda_C", self.lambda_C),
                          ("lambda_F", self.lambda_F)]:
            if abs(val) > 1.0 + VALIDATION_EPSILON:
                raise ValueError(f"|{name}| must be ≤ 1, got {abs(val)}")

    def compute_guna_term(self, s: float, r: float, t: float,
                          w_S: float, w_R: float, w_T: float) -> float:
        """Compute the Guna contribution to utility."""
        return (
            self.c_S * w_S * s +
            self.c_R * w_R * r +
            self.c_T * w_T * t
        )

    def compute_penalties(self, H: float, C_contr: float, F_fail: float) -> float:
        """Compute the penalty terms."""
        return (
            self.lambda_H * H +
            self.lambda_C * C_contr +
            self.lambda_F * F_fail
        )


# Default utility coefficients
DEFAULT_UTILITY_COEFFICIENTS = UtilityCoefficients()

# Neutral coefficients (no preference, all terms contribute equally)
NEUTRAL_UTILITY_COEFFICIENTS = UtilityCoefficients(
    c_S=1.0, c_R=1.0, c_T=1.0,
    lambda_H=0.0, lambda_C=0.0, lambda_F=0.0,
)


# =============================================================================
# Tone Logit Configuration (Fix #3)
# =============================================================================

@dataclass(frozen=True)
class ToneLogitConfig:
    """
    Named, bounded coefficients for tone weight computation.

    Logit formulas:
        ℓ_sweet = k_sweet_sattva × s - k_sweet_tamas × t
        ℓ_jolt = k_jolt_rajas × r + k_jolt_contr × C_contr
        ℓ_metaphor = k_metaphor_entropy × H + k_metaphor_rajas × r

    All values are bounded to [0, 2] to prevent extreme softmax outputs.

    Interpretation:
        - Higher k_sweet_sattva → Sattva more strongly promotes calm delivery
        - Higher k_jolt_contr → Contradictions trigger more corrective energy
        - Higher k_metaphor_entropy → High entropy leads to more abstract/poetic tone
    """
    # Sweet tone (calm, harmonious delivery)
    k_sweet_sattva: float = 1.0    # Sattva promotes sweetness
    k_sweet_tamas: float = 0.5     # Tamas reduces sweetness

    # Jolt tone (energetic, activating delivery)
    k_jolt_rajas: float = 0.8      # Rajas promotes jolt
    k_jolt_contr: float = 0.3      # Contradiction promotes jolt

    # Metaphor tone (abstract, poetic delivery)
    k_metaphor_entropy: float = 0.6  # Entropy promotes metaphor
    k_metaphor_rajas: float = 0.4    # Rajas also promotes metaphor

    def __post_init__(self):
        """Validate all coefficients are in [0, 2]."""
        for name in ["k_sweet_sattva", "k_sweet_tamas",
                     "k_jolt_rajas", "k_jolt_contr",
                     "k_metaphor_entropy", "k_metaphor_rajas"]:
            val = getattr(self, name)
            if not (0.0 <= val <= 2.0 + VALIDATION_EPSILON):
                raise ValueError(f"{name} must be in [0, 2], got {val}")

    def compute_logits(self, s: float, r: float, t: float,
                       H: float, C_contr: float) -> tuple:
        """
        Compute tone logits from observables.

        Returns:
            (logit_sweet, logit_jolt, logit_metaphor) tuple
        """
        logit_sweet = self.k_sweet_sattva * s - self.k_sweet_tamas * t
        logit_jolt = self.k_jolt_rajas * r + self.k_jolt_contr * C_contr
        logit_metaphor = self.k_metaphor_entropy * H + self.k_metaphor_rajas * r
        return (logit_sweet, logit_jolt, logit_metaphor)


# Default tone configuration
DEFAULT_TONE_CONFIG = ToneLogitConfig()


# =============================================================================
# Alpha Configuration (Fix #2)
# =============================================================================

@dataclass(frozen=True)
class AlphaConfig:
    """
    Tier-specific learning rate configuration with half-life documentation.

    The state update equation uses α (alpha) as:
        θ_{t+1} = (1 - α) × θ_t + α × θ*_t

    Half-life formula:
        t_½ = ln(0.5) / ln(1 - α) ≈ 0.693 / α

    This means after t_½ updates, 50% of the original state remains.

    Attributes:
        alpha: Learning rate in (0, 1)
        half_life_updates: Number of updates for 50% decay (computed)
        tier: Associated tier name (for documentation)
    """
    alpha: float
    tier: str = "custom"

    def __post_init__(self):
        """Validate alpha range."""
        if not (0.0 < self.alpha < 1.0):
            raise ValueError(f"alpha must be in (0, 1), got {self.alpha}")

    @property
    def half_life_updates(self) -> float:
        """Number of updates for 50% decay toward target."""
        return math.log(0.5) / math.log(1 - self.alpha)

    @property
    def decay_90_updates(self) -> float:
        """Number of updates for 90% decay toward target."""
        return math.log(0.1) / math.log(1 - self.alpha)

    def decay_after_n(self, n: int) -> float:
        """Fraction of original state remaining after n updates."""
        return (1 - self.alpha) ** n


# Tier-specific alpha configurations
ALPHA_ENTERPRISE_T1 = AlphaConfig(alpha=0.02, tier=TIER_ENTERPRISE_1)
ALPHA_ENTERPRISE_T2 = AlphaConfig(alpha=0.05, tier=TIER_ENTERPRISE_2)
ALPHA_CONSUMER = AlphaConfig(alpha=0.10, tier=TIER_CONSUMER)

# Mapping from tier to alpha config
TIER_ALPHA_CONFIGS: Dict[str, AlphaConfig] = {
    TIER_ENTERPRISE_1: ALPHA_ENTERPRISE_T1,
    TIER_ENTERPRISE_2: ALPHA_ENTERPRISE_T2,
    TIER_CONSUMER: ALPHA_CONSUMER,
}

# Default alpha (same as Enterprise T2)
DEFAULT_ALPHA_CONFIG = ALPHA_ENTERPRISE_T2


def get_alpha_for_tier(tier: str) -> AlphaConfig:
    """Get alpha configuration for a tier."""
    return TIER_ALPHA_CONFIGS.get(tier, DEFAULT_ALPHA_CONFIG)


# =============================================================================
# State Persistence Configuration (Fix #4)
# =============================================================================

@dataclass(frozen=True)
class StatePersistenceConfig:
    """
    Configuration for state persistence across sessions.

    Defines:
        - Scope: What entity owns the state (global, tenant, user, session)
        - Decay on restart: How much to decay toward default on system restart
        - Max age: When to reset stale state entirely
        - Storage backend: Where to persist state

    Attributes:
        scope: "global" | "tenant" | "user" | "session"
        decay_on_restart: Whether to decay state on system restart
        restart_decay_factor: θ_restart = factor×θ_saved + (1-factor)×θ_0
        max_state_age_hours: Reset state if older than this
        storage_backend: "redis" | "postgres" | "memory"
    """
    scope: str = "tenant"
    decay_on_restart: bool = True
    restart_decay_factor: float = 0.5
    max_state_age_hours: int = 168  # 7 days
    storage_backend: str = "memory"

    def __post_init__(self):
        """Validate configuration."""
        valid_scopes = {"global", "tenant", "user", "session"}
        if self.scope not in valid_scopes:
            raise ValueError(f"scope must be one of {valid_scopes}, got {self.scope}")

        if not (0.0 <= self.restart_decay_factor <= 1.0):
            raise ValueError(
                f"restart_decay_factor must be in [0, 1], got {self.restart_decay_factor}"
            )

        valid_backends = {"redis", "postgres", "memory"}
        if self.storage_backend not in valid_backends:
            raise ValueError(
                f"storage_backend must be one of {valid_backends}, got {self.storage_backend}"
            )

    @property
    def is_persistent(self) -> bool:
        """Whether state persists beyond session."""
        return self.scope != "session"

    @property
    def max_state_age_seconds(self) -> int:
        """Max age in seconds."""
        return self.max_state_age_hours * 3600


# Scope-specific defaults
PERSISTENCE_GLOBAL = StatePersistenceConfig(scope="global")
PERSISTENCE_TENANT = StatePersistenceConfig(scope="tenant")
PERSISTENCE_USER = StatePersistenceConfig(scope="user")
PERSISTENCE_SESSION = StatePersistenceConfig(scope="session", decay_on_restart=False)

# Default persistence (tenant-scoped)
DEFAULT_PERSISTENCE_CONFIG = PERSISTENCE_TENANT


# =============================================================================
# Master v2.7 Configuration (Combines all above)
# =============================================================================

@dataclass(frozen=True)
class V27Config:
    """
    Master configuration for v2.7 State Evolution.

    Combines:
        - Version gating (v2_7_enabled)
        - Alpha/learning rate (tier-specific)
        - Utility coefficients (operator-configurable)
        - Tone logit coefficients (named, bounded)
        - State persistence (scoped, decay-governed)

    Attributes:
        v2_7_enabled: Master switch. When False, behaves like v2.6.
        alpha_config: Learning rate configuration
        utility_coefficients: Guna and penalty signs/weights
        tone_config: Tone logit coefficients
        persistence_config: State storage configuration
    """
    v2_7_enabled: bool = False
    alpha_config: AlphaConfig = field(default_factory=lambda: DEFAULT_ALPHA_CONFIG)
    utility_coefficients: UtilityCoefficients = field(
        default_factory=lambda: DEFAULT_UTILITY_COEFFICIENTS
    )
    tone_config: ToneLogitConfig = field(default_factory=lambda: DEFAULT_TONE_CONFIG)
    persistence_config: StatePersistenceConfig = field(
        default_factory=lambda: DEFAULT_PERSISTENCE_CONFIG
    )

    @property
    def alpha(self) -> float:
        """Convenience accessor for learning rate."""
        return self.alpha_config.alpha

    @property
    def tier(self) -> str:
        """Convenience accessor for tier name."""
        return self.alpha_config.tier

    @property
    def half_life(self) -> float:
        """Convenience accessor for half-life in updates."""
        return self.alpha_config.half_life_updates

    @classmethod
    def for_tier(cls, tier: str, enabled: bool = True) -> "V27Config":
        """
        Create configuration for a specific tier.

        Args:
            tier: "enterprise_tier_1", "enterprise_tier_2", or "consumer"
            enabled: Whether v2.7 is enabled

        Returns:
            V27Config with tier-appropriate alpha
        """
        alpha_config = get_alpha_for_tier(tier)
        return cls(v2_7_enabled=enabled, alpha_config=alpha_config)

    @classmethod
    def disabled(cls) -> "V27Config":
        """Create a v2.6-compatible configuration (evolution disabled)."""
        return cls(v2_7_enabled=False)

    @classmethod
    def enterprise_t1(cls, enabled: bool = True) -> "V27Config":
        """Create Enterprise Tier 1 configuration (α=0.02, half-life≈35)."""
        return cls.for_tier(TIER_ENTERPRISE_1, enabled)

    @classmethod
    def enterprise_t2(cls, enabled: bool = True) -> "V27Config":
        """Create Enterprise Tier 2 configuration (α=0.05, half-life≈14)."""
        return cls.for_tier(TIER_ENTERPRISE_2, enabled)

    @classmethod
    def consumer(cls, enabled: bool = True) -> "V27Config":
        """Create Consumer configuration (α=0.10, half-life≈7)."""
        return cls.for_tier(TIER_CONSUMER, enabled)


# Pre-built configurations
DEFAULT_V27_CONFIG = V27Config.disabled()
ENABLED_V27_CONFIG = V27Config.enterprise_t2(enabled=True)
ENTERPRISE_T1_CONFIG = V27Config.enterprise_t1()
ENTERPRISE_T2_CONFIG = V27Config.enterprise_t2()
CONSUMER_CONFIG = V27Config.consumer()
