"""
v2.7 Configuration Module
=========================

Comprehensive configuration for SymbolU v2.7 State Evolution Layer.

Includes:
- UtilityCoefficients: Operator-configurable utility term signs
- ToneLogitConfig: Named, bounded tone coefficients
- AlphaConfig: Tier-specific learning rates with half-life
- StatePersistenceConfig: State storage and decay semantics
- UpdateMode: Switch between EMA (bounded) and Bayesian (unbounded) updates
- BayesianConfig: Configuration for Bayesian update mode
- V27Config: Master configuration combining all above

Version: 2.7.2
Date: 2025-12-22

Alpha 2.7 Feature:
- Introduces Bayesian update mode as alternative to EMA
- Bayesian mode provides true probability distributions with uncertainty
- Switch via update_mode="bayesian" in V27Config
"""

from dataclasses import dataclass, field
from typing import Optional, Dict, Tuple
from enum import Enum
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
# Update Mode (Alpha 2.7 Feature)
# =============================================================================

class UpdateMode(Enum):
    """
    State update algorithm selection.

    EMA (default):
        θ_{t+1} = (1 - α) × θ_t + α × θ*
        - Bounded by design
        - Fixed learning rate
        - No uncertainty quantification

    FAST (lightweight):
        Same as EMA, but with phase variance confidence
        - Uses variance of observable signals as confidence proxy
        - ~0.1% compute overhead
        - No posterior tracking
        - Good for 95% of inference calls

    BAYESIAN (full):
        P(θ | data) ∝ P(data | θ) × P(θ)
        - Natural bounds via priors
        - Adaptive learning rate (automatic)
        - Full uncertainty quantification
        - Principled probabilistic inference
    """
    EMA = "ema"
    FAST = "fast"
    BAYESIAN = "bayesian"


@dataclass(frozen=True)
class BayesianConfig:
    """
    Configuration for Bayesian update mode.

    Uses Beta distributions for bounded parameters [0, 1] and
    Normal distributions for unbounded parameters.

    Attributes:
        prior_strength: Equivalent sample size of prior (higher = more resistant to change)
        min_confidence: Minimum confidence before acting on posterior
        use_conjugate_priors: Whether to use conjugate priors (faster) or MCMC
        uncertainty_threshold: Uncertainty level below which we trust the estimate
    """
    # Prior configuration
    prior_strength: float = 10.0  # Equivalent to 10 observations
    prior_mean_tau: float = 0.5   # Prior belief about tau thresholds
    prior_mean_w: float = 0.333   # Prior belief about weights (uniform)

    # Confidence thresholds
    min_confidence: float = 0.6   # Minimum confidence to trust estimate
    uncertainty_threshold: float = 0.1  # Variance below this = confident

    # Algorithm selection
    use_conjugate_priors: bool = True  # Use Beta/Normal conjugates

    def __post_init__(self):
        """Validate configuration."""
        if self.prior_strength <= 0:
            raise ValueError(f"prior_strength must be > 0, got {self.prior_strength}")
        if not (0.0 <= self.min_confidence <= 1.0):
            raise ValueError(f"min_confidence must be in [0, 1], got {self.min_confidence}")
        if not (0.0 < self.prior_mean_tau < 1.0):
            raise ValueError(f"prior_mean_tau must be in (0, 1), got {self.prior_mean_tau}")


@dataclass
class BayesianPosterior:
    """
    Posterior distribution for a single parameter.

    For Beta distribution (bounded parameters):
        alpha, beta = shape parameters
        mean = alpha / (alpha + beta)
        variance = (alpha * beta) / ((alpha + beta)^2 * (alpha + beta + 1))

    For Normal distribution (unbounded parameters):
        mu, sigma = mean and std deviation
    """
    # Beta distribution parameters (for bounded [0,1] params)
    alpha: float = 1.0  # Successes + prior
    beta: float = 1.0   # Failures + prior

    # Observation count
    n_observations: int = 0

    @property
    def mean(self) -> float:
        """Posterior mean estimate."""
        return self.alpha / (self.alpha + self.beta)

    @property
    def variance(self) -> float:
        """Posterior variance (uncertainty)."""
        total = self.alpha + self.beta
        if total <= 0:
            return 0.25  # Maximum variance for Beta distribution
        var = (self.alpha * self.beta) / (total * total * (total + 1))
        return max(0.0, var)  # Guard against floating point issues

    @property
    def std(self) -> float:
        """Posterior standard deviation."""
        return math.sqrt(max(0.0, self.variance))

    @property
    def confidence(self) -> float:
        """
        Confidence in estimate [0, 1].

        Higher with more observations and lower variance.
        """
        # Confidence increases with observations
        obs_factor = 1 - 1 / (1 + self.n_observations)
        # Confidence increases with lower variance (max variance for Beta is 0.25)
        var_factor = 1 - min(1.0, self.variance / 0.25)
        return obs_factor * var_factor

    @property
    def credible_interval_95(self) -> Tuple[float, float]:
        """95% credible interval (approximate)."""
        # Approximate using mean ± 2*std, clipped to [0, 1]
        lower = max(0.0, self.mean - 2 * self.std)
        upper = min(1.0, self.mean + 2 * self.std)
        return (lower, upper)

    def update(self, observation: float, weight: float = 1.0) -> "BayesianPosterior":
        """
        Update posterior with new observation.

        For bounded params, observation in [0, 1] treated as:
        - Closer to 1 = more "successes"
        - Closer to 0 = more "failures"

        Args:
            observation: Observed value in [0, 1]
            weight: Weight of this observation (default 1.0)

        Returns:
            New BayesianPosterior with updated parameters
        """
        # Treat observation as success/failure proportion
        successes = observation * weight
        failures = (1 - observation) * weight

        return BayesianPosterior(
            alpha=self.alpha + successes,
            beta=self.beta + failures,
            n_observations=self.n_observations + 1,
        )

    def decay_toward_prior(self, decay_factor: float, prior_alpha: float = 1.0, prior_beta: float = 1.0) -> "BayesianPosterior":
        """
        Decay posterior toward prior (for restart/reset).

        new_alpha = decay_factor * alpha + (1 - decay_factor) * prior_alpha
        """
        return BayesianPosterior(
            alpha=decay_factor * self.alpha + (1 - decay_factor) * prior_alpha,
            beta=decay_factor * self.beta + (1 - decay_factor) * prior_beta,
            n_observations=int(self.n_observations * decay_factor),
        )

    @classmethod
    def from_prior(cls, prior_mean: float, prior_strength: float) -> "BayesianPosterior":
        """
        Create posterior from prior belief.

        Args:
            prior_mean: Prior belief about parameter value
            prior_strength: Equivalent sample size (higher = more confident prior)
        """
        # For Beta distribution with mean m and "strength" n:
        # alpha = m * n, beta = (1-m) * n
        alpha = prior_mean * prior_strength
        beta = (1 - prior_mean) * prior_strength
        return cls(alpha=alpha, beta=beta, n_observations=0)


@dataclass
class BayesianStateRegister:
    """
    State register with Bayesian posteriors for each parameter.

    Instead of point estimates, tracks full distributions.
    """
    # Posteriors for tau thresholds
    tau_768_posterior: BayesianPosterior = field(default_factory=BayesianPosterior)
    tau_175_posterior: BayesianPosterior = field(default_factory=BayesianPosterior)

    # Posteriors for tone weights (Dirichlet would be better, but using independent Betas)
    w_tone_sweet_posterior: BayesianPosterior = field(default_factory=BayesianPosterior)
    w_tone_jolt_posterior: BayesianPosterior = field(default_factory=BayesianPosterior)
    w_tone_metaphor_posterior: BayesianPosterior = field(default_factory=BayesianPosterior)

    # Posterior for b_policy
    b_policy_posterior: BayesianPosterior = field(default_factory=BayesianPosterior)

    @property
    def tau_768(self) -> float:
        """Point estimate for tau_768."""
        return self.tau_768_posterior.mean

    @property
    def tau_175(self) -> float:
        """Point estimate for tau_175."""
        return self.tau_175_posterior.mean

    @property
    def w_tone(self) -> Tuple[float, float, float]:
        """Point estimates for w_tone (normalized)."""
        raw = (
            self.w_tone_sweet_posterior.mean,
            self.w_tone_jolt_posterior.mean,
            self.w_tone_metaphor_posterior.mean,
        )
        total = sum(raw)
        if total > 0:
            return (raw[0] / total, raw[1] / total, raw[2] / total)
        return (0.333, 0.333, 0.334)

    @property
    def b_policy(self) -> float:
        """Point estimate for b_policy."""
        return self.b_policy_posterior.mean

    @property
    def overall_confidence(self) -> float:
        """Average confidence across all parameters."""
        confidences = [
            self.tau_768_posterior.confidence,
            self.tau_175_posterior.confidence,
            self.w_tone_sweet_posterior.confidence,
            self.w_tone_jolt_posterior.confidence,
            self.w_tone_metaphor_posterior.confidence,
            self.b_policy_posterior.confidence,
        ]
        return sum(confidences) / len(confidences)

    @property
    def uncertainty_summary(self) -> Dict[str, float]:
        """Summary of uncertainties for each parameter."""
        return {
            "tau_768_std": self.tau_768_posterior.std,
            "tau_175_std": self.tau_175_posterior.std,
            "w_tone_sweet_std": self.w_tone_sweet_posterior.std,
            "w_tone_jolt_std": self.w_tone_jolt_posterior.std,
            "w_tone_metaphor_std": self.w_tone_metaphor_posterior.std,
            "b_policy_std": self.b_policy_posterior.std,
            "overall_confidence": self.overall_confidence,
        }

    def to_dict(self) -> Dict:
        """Export to dictionary for logging/audit."""
        return {
            "tau_768": self.tau_768,
            "tau_768_ci95": self.tau_768_posterior.credible_interval_95,
            "tau_175": self.tau_175,
            "tau_175_ci95": self.tau_175_posterior.credible_interval_95,
            "w_tone": self.w_tone,
            "b_policy": self.b_policy,
            "b_policy_ci95": self.b_policy_posterior.credible_interval_95,
            "overall_confidence": self.overall_confidence,
            "n_observations": self.tau_768_posterior.n_observations,
        }

    @classmethod
    def from_config(cls, config: "BayesianConfig") -> "BayesianStateRegister":
        """Create state register with priors from config."""
        return cls(
            tau_768_posterior=BayesianPosterior.from_prior(
                config.prior_mean_tau, config.prior_strength
            ),
            tau_175_posterior=BayesianPosterior.from_prior(
                config.prior_mean_tau, config.prior_strength
            ),
            w_tone_sweet_posterior=BayesianPosterior.from_prior(
                config.prior_mean_w, config.prior_strength
            ),
            w_tone_jolt_posterior=BayesianPosterior.from_prior(
                config.prior_mean_w, config.prior_strength
            ),
            w_tone_metaphor_posterior=BayesianPosterior.from_prior(
                config.prior_mean_w, config.prior_strength
            ),
            b_policy_posterior=BayesianPosterior.from_prior(
                0.5, config.prior_strength
            ),
        )


# Default Bayesian configuration
DEFAULT_BAYESIAN_CONFIG = BayesianConfig()


# =============================================================================
# Fast Mode Configuration (Lightweight Inference)
# =============================================================================

@dataclass(frozen=True)
class FastConfig:
    """
    Configuration for Fast inference mode (lightweight confidence).

    Uses phase variance as a proxy for confidence instead of full Bayesian
    posterior tracking. This is the same approach as SattvicBrake in training.

    Cost: ~0.1% compute, 0% extra memory

    Confidence = 1 - variance(observables)

    Attributes:
        confidence_threshold: Threshold below which we hedge responses
        variance_window: Number of observations for rolling variance
        use_observable_variance: Use variance of s,r,t signals (default)
        hedging_enabled: Whether to add hedging language on low confidence
    """
    confidence_threshold: float = 0.5
    variance_window: int = 10
    use_observable_variance: bool = True
    hedging_enabled: bool = True

    def __post_init__(self):
        """Validate configuration."""
        if not (0.0 <= self.confidence_threshold <= 1.0):
            raise ValueError(f"confidence_threshold must be in [0, 1], got {self.confidence_threshold}")
        if self.variance_window < 1:
            raise ValueError(f"variance_window must be >= 1, got {self.variance_window}")


# Default Fast configuration
DEFAULT_FAST_CONFIG = FastConfig()


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
        - Update mode (EMA, FAST, or BAYESIAN)
        - Alpha/learning rate (tier-specific, for EMA/FAST mode)
        - Fast configuration (for FAST mode - lightweight inference)
        - Bayesian configuration (for BAYESIAN mode)
        - Utility coefficients (operator-configurable)
        - Tone logit coefficients (named, bounded)
        - State persistence (scoped, decay-governed)

    Update Modes:
        - EMA: Simple exponential moving average (default)
        - FAST: EMA + phase variance confidence (~0.1% overhead)
        - BAYESIAN: Full posterior tracking (~2-5% overhead)

    Attributes:
        v2_7_enabled: Master switch. When False, behaves like v2.6.
        update_mode: UpdateMode.EMA (default), FAST, or BAYESIAN
        alpha_config: Learning rate configuration (used in EMA/FAST mode)
        fast_config: Fast mode configuration (used in FAST mode)
        bayesian_config: Bayesian update configuration (used in BAYESIAN mode)
        utility_coefficients: Guna and penalty signs/weights
        tone_config: Tone logit coefficients
        persistence_config: State storage configuration
    """
    v2_7_enabled: bool = False
    update_mode: UpdateMode = UpdateMode.FAST  # Default: lightweight confidence tracking
    alpha_config: AlphaConfig = field(default_factory=lambda: DEFAULT_ALPHA_CONFIG)
    fast_config: FastConfig = field(default_factory=lambda: DEFAULT_FAST_CONFIG)
    bayesian_config: BayesianConfig = field(default_factory=lambda: DEFAULT_BAYESIAN_CONFIG)
    utility_coefficients: UtilityCoefficients = field(
        default_factory=lambda: DEFAULT_UTILITY_COEFFICIENTS
    )
    tone_config: ToneLogitConfig = field(default_factory=lambda: DEFAULT_TONE_CONFIG)
    persistence_config: StatePersistenceConfig = field(
        default_factory=lambda: DEFAULT_PERSISTENCE_CONFIG
    )
    # v2.7.4: Recursive self-improvement configuration
    self_improvement_enabled: bool = False  # Master switch (separate from config)
    self_improvement_config: "SelfImprovementConfig" = None  # Populated via factory

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

    @property
    def is_fast(self) -> bool:
        """Check if using Fast update mode (lightweight confidence)."""
        return self.update_mode == UpdateMode.FAST

    @property
    def is_bayesian(self) -> bool:
        """Check if using Bayesian update mode."""
        return self.update_mode == UpdateMode.BAYESIAN

    @property
    def is_ema(self) -> bool:
        """Check if using EMA update mode."""
        return self.update_mode == UpdateMode.EMA

    @classmethod
    def for_tier(cls, tier: str, enabled: bool = True, bayesian: bool = False) -> "V27Config":
        """
        Create configuration for a specific tier.

        Args:
            tier: "enterprise_tier_1", "enterprise_tier_2", or "consumer"
            enabled: Whether v2.7 is enabled
            bayesian: Whether to use Bayesian mode (Alpha 2.7)

        Returns:
            V27Config with tier-appropriate settings
        """
        alpha_config = get_alpha_for_tier(tier)
        update_mode = UpdateMode.BAYESIAN if bayesian else UpdateMode.EMA
        return cls(
            v2_7_enabled=enabled,
            update_mode=update_mode,
            alpha_config=alpha_config,
        )

    @classmethod
    def disabled(cls) -> "V27Config":
        """Create a v2.6-compatible configuration (evolution disabled)."""
        return cls(v2_7_enabled=False)

    @classmethod
    def enterprise_t1(cls, enabled: bool = True, bayesian: bool = False) -> "V27Config":
        """Create Enterprise Tier 1 configuration (α=0.02, half-life≈35)."""
        return cls.for_tier(TIER_ENTERPRISE_1, enabled, bayesian)

    @classmethod
    def enterprise_t2(cls, enabled: bool = True, bayesian: bool = False) -> "V27Config":
        """Create Enterprise Tier 2 configuration (α=0.05, half-life≈14)."""
        return cls.for_tier(TIER_ENTERPRISE_2, enabled, bayesian)

    @classmethod
    def consumer(cls, enabled: bool = True, bayesian: bool = False) -> "V27Config":
        """Create Consumer configuration (α=0.10, half-life≈7)."""
        return cls.for_tier(TIER_CONSUMER, enabled, bayesian)

    @classmethod
    def fast(cls, tier: str = TIER_ENTERPRISE_2, confidence_threshold: float = 0.5) -> "V27Config":
        """
        Create Fast mode configuration (lightweight inference).

        Uses phase variance as confidence proxy instead of full Bayesian.
        Same approach as SattvicBrake in training.

        Cost: ~0.1% compute, 0% extra memory

        Args:
            tier: Tier for alpha (learning rate)
            confidence_threshold: Threshold below which to hedge responses

        Returns:
            V27Config with Fast mode enabled
        """
        return cls(
            v2_7_enabled=True,
            update_mode=UpdateMode.FAST,
            alpha_config=get_alpha_for_tier(tier),
            fast_config=FastConfig(confidence_threshold=confidence_threshold),
        )

    @classmethod
    def bayesian(cls, tier: str = TIER_ENTERPRISE_2, prior_strength: float = 10.0) -> "V27Config":
        """
        Create Bayesian mode configuration (full posterior tracking).

        Args:
            tier: Tier for fallback alpha (if needed)
            prior_strength: Prior strength for Bayesian updates

        Returns:
            V27Config with Bayesian mode enabled
        """
        return cls(
            v2_7_enabled=True,
            update_mode=UpdateMode.BAYESIAN,
            alpha_config=get_alpha_for_tier(tier),
            bayesian_config=BayesianConfig(prior_strength=prior_strength),
        )

    @classmethod
    def with_self_improvement(
        cls,
        tier: str = TIER_ENTERPRISE_2,
        bayesian: bool = True,
        auto_improve: bool = False,
        improvement_threshold: float = 0.6,
    ) -> "V27Config":
        """
        Create configuration with recursive self-improvement enabled (v2.7.4).

        Args:
            tier: Tier for learning rate configuration
            bayesian: Use Bayesian mode (recommended for self-improvement)
            auto_improve: Automatically execute improvements
            improvement_threshold: Minimum priority to execute

        Returns:
            V27Config with self-improvement enabled
        """
        from agentic.guna_modulation.v27_config import SelfImprovementConfig

        return cls(
            v2_7_enabled=True,
            update_mode=UpdateMode.BAYESIAN if bayesian else UpdateMode.EMA,
            alpha_config=get_alpha_for_tier(tier),
            self_improvement_enabled=True,
            self_improvement_config=SelfImprovementConfig(
                enabled=True,
                auto_improve=auto_improve,
                improvement_threshold=improvement_threshold,
            ),
        )

    @property
    def is_self_improving(self) -> bool:
        """Check if self-improvement is enabled."""
        return self.self_improvement_enabled and (
            self.self_improvement_config is not None and
            self.self_improvement_config.enabled
        )


# Pre-built configurations
DEFAULT_V27_CONFIG = V27Config.disabled()
ENABLED_V27_CONFIG = V27Config.enterprise_t2(enabled=True)
ENTERPRISE_T1_CONFIG = V27Config.enterprise_t1()
ENTERPRISE_T2_CONFIG = V27Config.enterprise_t2()
CONSUMER_CONFIG = V27Config.consumer()

# Alpha 2.7: Bayesian configurations
BAYESIAN_V27_CONFIG = V27Config.bayesian()
BAYESIAN_ENTERPRISE_T1 = V27Config.enterprise_t1(bayesian=True)
BAYESIAN_ENTERPRISE_T2 = V27Config.enterprise_t2(bayesian=True)
BAYESIAN_CONSUMER = V27Config.consumer(bayesian=True)


# =============================================================================
# Self-Improvement Configuration (v2.7.4)
# =============================================================================

@dataclass(frozen=True)
class SelfImprovementConfig:
    """
    Configuration for recursive self-improvement.

    Controls whether and how the system can modify its own
    coefficients and beliefs based on utility observations.

    Attributes:
        enabled: Master switch for self-improvement
        auto_improve: Automatically execute improvements (vs manual approval)
        improvement_threshold: Minimum priority to execute (0.0-1.0)
        observation_window: Number of observations before improvement cycle
        max_coefficient_change: Maximum coefficient adjustment per cycle
        enable_conservative_mode: Allow system to enter conservative mode
        persist_improvements: Save learned improvements across sessions
    """
    enabled: bool = False  # Off by default for safety
    auto_improve: bool = False  # Require approval by default
    improvement_threshold: float = 0.6
    observation_window: int = 100  # Run improvement cycle every N observations
    max_coefficient_change: float = 0.2  # Max 20% change per cycle
    enable_conservative_mode: bool = True
    persist_improvements: bool = True

    def __post_init__(self):
        """Validate configuration."""
        if not (0.0 <= self.improvement_threshold <= 1.0):
            raise ValueError(
                f"improvement_threshold must be in [0, 1], got {self.improvement_threshold}"
            )
        if self.observation_window < 10:
            raise ValueError(
                f"observation_window must be >= 10, got {self.observation_window}"
            )
        if not (0.0 < self.max_coefficient_change <= 0.5):
            raise ValueError(
                f"max_coefficient_change must be in (0, 0.5], got {self.max_coefficient_change}"
            )


# Default self-improvement configs
DEFAULT_SELF_IMPROVEMENT_CONFIG = SelfImprovementConfig(enabled=False)
ENABLED_SELF_IMPROVEMENT_CONFIG = SelfImprovementConfig(
    enabled=True,
    auto_improve=False,  # Manual approval
    improvement_threshold=0.7,
)
AUTO_SELF_IMPROVEMENT_CONFIG = SelfImprovementConfig(
    enabled=True,
    auto_improve=True,
    improvement_threshold=0.6,
)
