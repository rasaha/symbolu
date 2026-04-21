"""§5.1 TrustShaper — autonomy-validated three-stage trust-shaping pattern.

Converts per-source BCVF costs into softmin trust weights while
respecting the three V1 commitments from §5.1:

  1. Per-source EMA baseline normalization (`ema_alpha = 0.05`,
     cold-start initializes EMA from the first observed cost so
     residual is exactly zero on step 0 → uniform weights).
  2. Significance gate before softmin — either a hard deadband
     (`|residual| < k · σ` → 0, with `k = 2.0` and `σ` tracked as
     an EMA of squared residual) or a hinge-φ transform
     (`φ(d) = max(d − θ, 0)`). V1 default is deadband; hinge is
     opt-in via config.
  3. All-pairs (non-anchor) pair enumeration — enforced upstream
     at the kernel config level (`BCVFLLMConfig.use_anchor_pairing
     = False`); this module does not re-validate that.

The pattern is a **V1 design constraint for continuous trust-
shaping consumers**, not a universal theorem. See §5.1 for scope
and §5.2 for the downstream-sensitivity caveat.

Softmin form (temperature `τ_w`):

    w_i = exp(−shaped_i / τ_w) / Σ_j exp(−shaped_j / τ_w)

`τ_w = 1.0` is the V1 starting point per §2.5.5 autonomy carry-
over; §3 per_source_cost distributions on the outlier family are
O(1) under V1 defaults, so τ_w = 1.0 puts the softmin in a
meaningful regime (outlier weight roughly 0.4× non-outlier).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

import numpy as np


@dataclass
class TrustShaperConfig:
    """Parameters of the §5.1 trust-shaping pipeline."""

    # §5.1 stage 1 — EMA baseline normalization
    ema_alpha: float = 0.05
    # §5.1 stage 2 — significance gate
    use_hinge: bool = False             # False = deadband (V1 default), True = hinge
    deadband_k_sigma: float = 2.0
    hinge_theta: float = 0.0
    # Softmin
    trust_temperature: float = 1.0
    # Numerical
    min_sigma: float = 1e-8


@dataclass
class TrustShaperStep:
    """Diagnostic record of a single shaper call."""

    cost: np.ndarray            # (M,) raw per-source cost input
    ema_mean_before: np.ndarray # (M,) EMA snapshot used for residual
    residual: np.ndarray        # (M,) cost − EMA_mean_before
    sigma: float                # scalar σ used for deadband threshold (0 if hinge)
    shaped: np.ndarray          # (M,) gate output feeding softmin
    weights: np.ndarray         # (M,) softmin output, sums to 1


class TrustShaper:
    """Stateful per-step trust-weight producer (§5.1 pattern)."""

    def __init__(self, M: int, config: Optional[TrustShaperConfig] = None) -> None:
        if M < 1:
            raise ValueError("TrustShaper requires M >= 1")
        self._M = M
        self._config = config or TrustShaperConfig()
        self._ema_mean: Optional[np.ndarray] = None       # (M,) fp64
        self._ema_sq: Optional[np.ndarray] = None         # (M,) fp64
        self._step_index = 0
        self.history: List[TrustShaperStep] = []

    # Public API ---------------------------------------------------- #

    @property
    def M(self) -> int:
        return self._M

    @property
    def step_index(self) -> int:
        return self._step_index

    def reset(self) -> None:
        self._ema_mean = None
        self._ema_sq = None
        self._step_index = 0
        self.history.clear()

    def step(self, per_source_costs: np.ndarray) -> np.ndarray:
        """Consume one per-source cost vector and emit (M,) trust weights.

        Args:
            per_source_costs: shape (M,) fp64-compatible.

        Returns:
            weights: shape (M,) fp64, sums to 1.
        """
        c = np.asarray(per_source_costs, dtype=np.float64).reshape(-1)
        if c.shape != (self._M,):
            raise ValueError(
                f"per_source_costs must have shape ({self._M},); got {c.shape}"
            )
        if not np.isfinite(c).all():
            raise ValueError(
                "per_source_costs contains non-finite values; BCVF kernel "
                "upstream should have caught this (§2.7.6)"
            )

        ema_mean_before = self._snapshot_ema_before(c)
        residual = c - ema_mean_before
        sigma = self._update_ema_and_sigma(c, residual)
        shaped = self._apply_significance_gate(residual, sigma)
        weights = self._softmin(shaped)
        self._step_index += 1

        self.history.append(
            TrustShaperStep(
                cost=c.copy(),
                ema_mean_before=ema_mean_before.copy(),
                residual=residual.copy(),
                sigma=float(sigma),
                shaped=shaped.copy(),
                weights=weights.copy(),
            )
        )
        return weights

    # Stages -------------------------------------------------------- #

    def _snapshot_ema_before(self, c: np.ndarray) -> np.ndarray:
        """Return EMA_mean *before* this step's update. Cold-start
        semantics: on step 0, EMA_mean is initialized to `c` itself,
        so residual = 0 → uniform weights. This matches §5.1 commit
        1 ("cold-start initializes EMA_mean[i] from the first
        observed value so the residual is exactly zero on step 0")."""
        if self._ema_mean is None:
            self._ema_mean = c.copy()
            self._ema_sq = np.zeros_like(self._ema_mean)
        return self._ema_mean.copy()

    def _update_ema_and_sigma(
        self, c: np.ndarray, residual: np.ndarray
    ) -> float:
        """Update EMA_mean and EMA_sq in place; return current σ scalar.

        σ is a single scalar across all M sources — we want a
        global "how noisy is the per-source signal" estimate, not
        a per-source one. Taking σ = sqrt(mean(EMA_sq)) matches
        the autonomy `S3_map_error_accel` implementation.
        """
        alpha = self._config.ema_alpha
        assert self._ema_mean is not None and self._ema_sq is not None
        # Mean update (standard EMA) — skip on the exact cold-start
        # step because we already initialized to `c`.
        if self._step_index > 0:
            self._ema_mean = (1.0 - alpha) * self._ema_mean + alpha * c
        # Squared-residual update — track even on step 0 so σ is
        # defined on step 1. On step 0, residual = 0, so EMA_sq
        # stays at 0 → σ = min_sigma.
        self._ema_sq = (1.0 - alpha) * self._ema_sq + alpha * (residual ** 2)
        sigma2 = float(np.mean(self._ema_sq))
        return np.sqrt(max(sigma2, self._config.min_sigma))

    def _apply_significance_gate(
        self, residual: np.ndarray, sigma: float
    ) -> np.ndarray:
        """§5.1 commit 2 — deadband or hinge, producing non-negative
        shaped cost fed to softmin.

        Only the *positive* side of the residual is meaningful for
        trust down-weighting (a source whose cost is *below* the
        EMA is not an outlier — that just means it's quieter than
        average, which is fine). Both deadband and hinge zero out
        the negative residuals alongside the sub-threshold middle.
        """
        if self._config.use_hinge:
            return np.maximum(residual - self._config.hinge_theta, 0.0)
        # Deadband: zero out |residual| < k·σ AND any negative residual.
        threshold = self._config.deadband_k_sigma * sigma
        positive_and_significant = (residual > threshold)
        return np.where(positive_and_significant, residual - threshold, 0.0)

    def _softmin(self, shaped: np.ndarray) -> np.ndarray:
        """Numerically-stable softmin: w_i ∝ exp(−shaped_i / τ)."""
        tau = self._config.trust_temperature
        scaled = -shaped / tau
        # Shift by max for numerical stability.
        scaled = scaled - np.max(scaled)
        w = np.exp(scaled)
        total = w.sum()
        if total <= 0.0 or not np.isfinite(total):
            # Fall back to uniform if something pathological happens
            # (shouldn't, given the finite-ness guarantees upstream).
            return np.full(self._M, 1.0 / self._M, dtype=np.float64)
        return w / total
