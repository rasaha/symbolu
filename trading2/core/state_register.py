"""
Bayesian State Register

Maintains posterior distributions for all trading parameters.
Uses conjugate priors for efficient closed-form updates:
- Beta-Bernoulli for bounded [0,1] parameters
- Normal-Normal for unbounded parameters

Key difference from EMA:
- EMA: θ_{t+1} = (1-α)θ_t + αx (point estimate)
- Bayesian: P(θ|data) ∝ P(data|θ)P(θ) (full distribution)

Benefits:
- Uncertainty quantification (credible intervals)
- Natural adaptation rate (data-driven, not fixed α)
- Regime-appropriate updates via likelihood weighting
"""

from dataclasses import dataclass, replace, field
from typing import Optional, Tuple, Dict, Any
import math

from trading2.core.config import RegimeType, PriorConfig


@dataclass(frozen=True)
class BetaPosterior:
    """
    Beta posterior for bounded [0,1] parameters.

    Beta(α, β) with:
        Mean = α / (α + β)
        Variance = αβ / ((α+β)²(α+β+1))
        Mode = (α-1) / (α+β-2) for α,β > 1

    Update rule (conjugate):
        Prior: Beta(α₀, β₀)
        Likelihood: Binomial(n, k successes)
        Posterior: Beta(α₀ + k, β₀ + n - k)
    """
    alpha: float
    beta: float

    @property
    def mean(self) -> float:
        """Posterior mean (point estimate)."""
        return self.alpha / (self.alpha + self.beta)

    @property
    def variance(self) -> float:
        """Posterior variance (uncertainty)."""
        total = self.alpha + self.beta
        return (self.alpha * self.beta) / (total * total * (total + 1))

    @property
    def std(self) -> float:
        """Posterior standard deviation."""
        return math.sqrt(self.variance)

    @property
    def mode(self) -> float:
        """Posterior mode (MAP estimate)."""
        if self.alpha > 1 and self.beta > 1:
            return (self.alpha - 1) / (self.alpha + self.beta - 2)
        return self.mean

    @property
    def concentration(self) -> float:
        """Total concentration (α + β), higher = more confident."""
        return self.alpha + self.beta

    def credible_interval(self, level: float = 0.95) -> Tuple[float, float]:
        """
        Approximate credible interval using normal approximation.

        For more accurate intervals, use scipy.stats.beta.ppf
        """
        z = 1.96 if level == 0.95 else 2.576  # 95% or 99%
        lower = max(0.0, self.mean - z * self.std)
        upper = min(1.0, self.mean + z * self.std)
        return (lower, upper)

    def update(self, observation: float, weight: float = 1.0) -> "BetaPosterior":
        """
        Update posterior with new observation.

        Args:
            observation: Value in [0, 1] (treated as success rate)
            weight: Effective sample size of observation

        Returns:
            New BetaPosterior with updated parameters
        """
        # Treat observation as weighted pseudo-count
        successes = observation * weight
        failures = (1 - observation) * weight

        return BetaPosterior(
            alpha=self.alpha + successes,
            beta=self.beta + failures,
        )

    def decay(self, factor: float = 0.999) -> "BetaPosterior":
        """
        Apply decay to prevent posterior from becoming too concentrated.

        Multiplies both α and β by factor, reducing confidence over time.
        """
        return BetaPosterior(
            alpha=max(1.0, self.alpha * factor),
            beta=max(1.0, self.beta * factor),
        )


@dataclass(frozen=True)
class NormalPosterior:
    """
    Normal posterior for unbounded parameters.

    Normal(μ, σ²) with conjugate Normal-Normal update.

    Update rule:
        Prior: N(μ₀, σ₀²)
        Likelihood: N(x, σ_obs²)
        Posterior: N(μ₁, σ₁²) where:
            σ₁² = 1 / (1/σ₀² + 1/σ_obs²)
            μ₁ = σ₁² × (μ₀/σ₀² + x/σ_obs²)
    """
    mean: float
    variance: float

    @property
    def std(self) -> float:
        return math.sqrt(max(1e-10, self.variance))

    @property
    def precision(self) -> float:
        """Precision = 1/variance (higher = more confident)."""
        return 1.0 / max(1e-10, self.variance)

    def credible_interval(self, level: float = 0.95) -> Tuple[float, float]:
        """Credible interval using normal quantiles."""
        z = 1.96 if level == 0.95 else 2.576
        return (self.mean - z * self.std, self.mean + z * self.std)

    def update(self, observation: float, obs_variance: float) -> "NormalPosterior":
        """
        Update posterior with new observation.

        Args:
            observation: Observed value
            obs_variance: Variance of observation (lower = more weight)

        Returns:
            New NormalPosterior with updated parameters
        """
        prior_precision = self.precision
        obs_precision = 1.0 / max(1e-10, obs_variance)

        new_precision = prior_precision + obs_precision
        new_variance = 1.0 / new_precision

        new_mean = new_variance * (
            self.mean * prior_precision + observation * obs_precision
        )

        return NormalPosterior(mean=new_mean, variance=new_variance)

    def decay(self, factor: float = 1.01) -> "NormalPosterior":
        """
        Apply decay by increasing variance (reducing confidence).
        """
        return NormalPosterior(
            mean=self.mean,
            variance=self.variance * factor,
        )


@dataclass(frozen=True)
class BayesianPosterior:
    """
    Complete posterior state for all trading parameters.

    Combines Beta posteriors (for bounded params) and
    Normal posteriors (for unbounded params).
    """
    # Signal thresholds (Beta)
    tau_entry: BetaPosterior
    tau_exit: BetaPosterior

    # Signal weights (Beta)
    w_momentum: BetaPosterior
    w_reversion: BetaPosterior
    w_elliott: BetaPosterior

    # Position sizing (Beta)
    position_scalar: BetaPosterior

    # Volatility anchor (Normal)
    volatility_anchor: NormalPosterior

    # Regime probabilities (Dirichlet approximated as independent Betas)
    regime_trending: BetaPosterior
    regime_ranging: BetaPosterior
    regime_volatile: BetaPosterior

    @classmethod
    def from_prior(cls, prior: PriorConfig) -> "BayesianPosterior":
        """Initialize posteriors from prior configuration."""
        return cls(
            tau_entry=BetaPosterior(prior.tau_entry_alpha, prior.tau_entry_beta),
            tau_exit=BetaPosterior(prior.tau_exit_alpha, prior.tau_exit_beta),
            w_momentum=BetaPosterior(prior.w_momentum_alpha, prior.w_momentum_beta),
            w_reversion=BetaPosterior(prior.w_reversion_alpha, prior.w_reversion_beta),
            w_elliott=BetaPosterior(prior.w_elliott_alpha, prior.w_elliott_beta),
            position_scalar=BetaPosterior(prior.position_scalar_alpha, prior.position_scalar_beta),
            volatility_anchor=NormalPosterior(
                prior.volatility_anchor_mean,
                prior.volatility_anchor_var
            ),
            # Initialize regime priors as uniform
            regime_trending=BetaPosterior(2.0, 2.0),
            regime_ranging=BetaPosterior(2.0, 2.0),
            regime_volatile=BetaPosterior(2.0, 2.0),
        )

    def get_point_estimates(self) -> Dict[str, float]:
        """Get MAP estimates for all parameters."""
        return {
            "tau_entry": self.tau_entry.mean,
            "tau_exit": self.tau_exit.mean,
            "w_momentum": self.w_momentum.mean,
            "w_reversion": self.w_reversion.mean,
            "w_elliott": self.w_elliott.mean,
            "position_scalar": self.position_scalar.mean,
            "volatility_anchor": self.volatility_anchor.mean,
            "regime_trending": self.regime_trending.mean,
            "regime_ranging": self.regime_ranging.mean,
            "regime_volatile": self.regime_volatile.mean,
        }

    def get_uncertainties(self) -> Dict[str, float]:
        """Get standard deviations for all parameters."""
        return {
            "tau_entry": self.tau_entry.std,
            "tau_exit": self.tau_exit.std,
            "w_momentum": self.w_momentum.std,
            "w_reversion": self.w_reversion.std,
            "w_elliott": self.w_elliott.std,
            "position_scalar": self.position_scalar.std,
            "volatility_anchor": self.volatility_anchor.std,
            "regime_trending": self.regime_trending.std,
            "regime_ranging": self.regime_ranging.std,
            "regime_volatile": self.regime_volatile.std,
        }

    def decay_all(self, factor: float = 0.999) -> "BayesianPosterior":
        """Apply decay to all posteriors."""
        return replace(
            self,
            tau_entry=self.tau_entry.decay(factor),
            tau_exit=self.tau_exit.decay(factor),
            w_momentum=self.w_momentum.decay(factor),
            w_reversion=self.w_reversion.decay(factor),
            w_elliott=self.w_elliott.decay(factor),
            position_scalar=self.position_scalar.decay(factor),
            volatility_anchor=self.volatility_anchor.decay(1.0 + (1.0 - factor)),
            regime_trending=self.regime_trending.decay(factor),
            regime_ranging=self.regime_ranging.decay(factor),
            regime_volatile=self.regime_volatile.decay(factor),
        )


@dataclass(frozen=True)
class BayesianStateRegister:
    """
    Immutable state container for Bayesian trading system.

    Combines:
    - Posterior distributions (uncertainty-aware parameters)
    - Point estimates (for quick decision making)
    - Runtime state (drawdown, regime, etc.)
    """
    # Posterior distributions
    posterior: BayesianPosterior

    # Current regime
    regime: RegimeType = RegimeType.UNKNOWN

    # Runtime state
    drawdown: float = 0.0
    peak_equity: float = 1.0
    current_equity: float = 1.0
    tick_count: int = 0

    # Elliott Wave state
    current_wave: Optional[int] = None  # 1-5 for impulse, A-C for corrective
    wave_confidence: float = 0.0

    @classmethod
    def initialize(cls, prior: PriorConfig) -> "BayesianStateRegister":
        """Create initial state from prior configuration."""
        return cls(posterior=BayesianPosterior.from_prior(prior))

    @property
    def tau_entry(self) -> float:
        """Entry threshold (point estimate)."""
        return self.posterior.tau_entry.mean

    @property
    def tau_exit(self) -> float:
        """Exit threshold (point estimate)."""
        return self.posterior.tau_exit.mean

    @property
    def w_momentum(self) -> float:
        """Momentum weight (point estimate)."""
        return self.posterior.w_momentum.mean

    @property
    def w_reversion(self) -> float:
        """Mean reversion weight (point estimate)."""
        return self.posterior.w_reversion.mean

    @property
    def w_elliott(self) -> float:
        """Elliott wave weight (point estimate)."""
        return self.posterior.w_elliott.mean

    @property
    def position_scalar(self) -> float:
        """Position size scalar (point estimate)."""
        return self.posterior.position_scalar.mean

    @property
    def volatility_anchor(self) -> float:
        """Volatility anchor (point estimate)."""
        return self.posterior.volatility_anchor.mean

    @property
    def total_uncertainty(self) -> float:
        """Sum of all parameter uncertainties (for monitoring)."""
        uncertainties = self.posterior.get_uncertainties()
        return sum(uncertainties.values())

    def with_posterior_update(
        self,
        param: str,
        observation: float,
        weight: float = 1.0,
    ) -> "BayesianStateRegister":
        """
        Update a specific posterior with new observation.

        Args:
            param: Parameter name (e.g., "tau_entry", "w_momentum")
            observation: Observed value
            weight: Observation weight

        Returns:
            New state with updated posterior
        """
        posterior = self.posterior
        current = getattr(posterior, param, None)

        if current is None:
            return self

        if isinstance(current, BetaPosterior):
            updated = current.update(observation, weight)
        elif isinstance(current, NormalPosterior):
            # For Normal, weight translates to observation variance
            obs_var = 0.01 / max(0.1, weight)  # Higher weight = lower variance
            updated = current.update(observation, obs_var)
        else:
            return self

        new_posterior = replace(posterior, **{param: updated})
        return replace(self, posterior=new_posterior, tick_count=self.tick_count + 1)

    def with_regime(self, regime: RegimeType) -> "BayesianStateRegister":
        """Update regime classification."""
        return replace(self, regime=regime)

    def with_equity(self, equity: float) -> "BayesianStateRegister":
        """Update equity and drawdown."""
        new_peak = max(self.peak_equity, equity)
        new_drawdown = (new_peak - equity) / new_peak if new_peak > 0 else 0.0
        return replace(
            self,
            current_equity=equity,
            peak_equity=new_peak,
            drawdown=new_drawdown,
        )

    def with_wave(self, wave: Optional[int], confidence: float) -> "BayesianStateRegister":
        """Update Elliott wave state."""
        return replace(
            self,
            current_wave=wave,
            wave_confidence=confidence,
        )

    def decay(self, factor: float = 0.999) -> "BayesianStateRegister":
        """Apply decay to posteriors (prevents over-concentration)."""
        return replace(self, posterior=self.posterior.decay_all(factor))

    def to_dict(self) -> Dict[str, Any]:
        """Export state as dictionary."""
        estimates = self.posterior.get_point_estimates()
        uncertainties = self.posterior.get_uncertainties()

        return {
            "estimates": estimates,
            "uncertainties": uncertainties,
            "regime": self.regime.value,
            "drawdown": self.drawdown,
            "current_wave": self.current_wave,
            "wave_confidence": self.wave_confidence,
            "tick_count": self.tick_count,
            "total_uncertainty": self.total_uncertainty,
        }
