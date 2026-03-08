"""Bliss Coherence Functional — Appendix G.3/G.4 Implementation.

Bliss = the integrated representational surface where all weak priors reconcile.
It is MEASURED (not injected). It is a scalar functional over hidden states and
their relationship to active weak priors.

B = (1/L) Σ B_A^ℓ  −  β · B_B

Where:
  B_A^ℓ = per-layer integration (cosine agreement with Kosha-weighted priors)
  B_B   = cross-layer stability penalty (anti-fragmentation)

The Bliss value gates injection strength via:
  λ_{k,eff} = λ_k · (λ_min + (1 - λ_min) · σ(γ · (B − τ)))

See: LATENT_SEMANTIC_TOKEN_BRIDGE_DESIGN.md, Appendix G
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import torch
import torch.nn.functional as F

logger = logging.getLogger(__name__)


@dataclass
class BlissConfig:
    """Configuration for the Bliss coherence functional."""
    # Bliss functional parameters
    beta: float = 0.3            # Cross-layer stability weight
    alpha_uniform: bool = True   # Use uniform per-layer stability weights

    # Adaptive gate parameters
    gamma: float = 5.0           # Gate sharpness
    tau_init: float = 0.1        # Initial threshold (overridden by running mean)
    use_running_tau: bool = True # Use running_mean(B) as threshold
    tau_ema_alpha: float = 0.01  # EMA smoothing for running tau

    # Safety parameters
    lambda_min: float = 0.1      # Floor for gated injection (never fully dead)
    warmup_steps: int = 1000     # Steps before Bliss gating activates
    eps_layer_init: float = 0.01 # Initial per-layer injection norm cap (fraction of rms(H))
    eps_layer_max: float = 0.05  # Maximum per-layer injection norm cap
    eps_ramp_steps: int = 5000   # Steps to ramp eps from init to max

    # Computation scope
    compute_every_n_layers: int = 1  # 1=all layers, 4=every 4th layer
    dead_channel_alert_steps: int = 1000  # Alert if λ_eff < 1.1×λ_min for this many steps


@dataclass
class BlissMetrics:
    """Metrics from one Bliss computation step."""
    B: float = 0.0                # Combined Bliss scalar
    B_A_mean: float = 0.0         # Mean integration across layers
    B_B: float = 0.0              # Cross-layer stability penalty
    B_A_per_layer: Dict[int, float] = field(default_factory=dict)
    delta_per_layer: Dict[int, float] = field(default_factory=dict)
    cosine_per_prior: Dict[str, float] = field(default_factory=dict)
    lambda_eff: Dict[str, float] = field(default_factory=dict)
    injection_norms: Dict[str, float] = field(default_factory=dict)
    cap_violations: int = 0
    dead_channels: List[str] = field(default_factory=list)


class BlissCoherenceFunctional:
    """
    Computes the Bliss coherence functional B over hidden states and weak priors.

    This is a pure measurement module — no nn.Module, no parameters, no gradients.
    It reads detached hidden states and prior vectors to produce a scalar B.

    Per Appendix G.4a (Trap 1): Priors MUST come from external sources
    (phoneme pipeline, JEPA predictor), not from H^ℓ itself. If any prior
    uses hidden states, the Bliss measurement must use a detached copy.
    """

    def __init__(self, config: BlissConfig):
        self.config = config
        self._step = 0
        self._tau = config.tau_init
        self._tau_ema = config.tau_init

        # Dead channel tracking: {prior_name: consecutive_steps_at_floor}
        self._dead_channel_counter: Dict[str, int] = {}

    def compute(
        self,
        hidden_states: List[torch.Tensor],
        priors: Dict[str, torch.Tensor],
        router_weights: Optional[Dict[str, float]] = None,
    ) -> BlissMetrics:
        """
        Compute Bliss coherence functional.

        Args:
            hidden_states: List of H^ℓ tensors, each [B, T, d_model].
                           These should be POST-LayerNorm (per G.4a Trap 4).
                           Must be detached or not require grad for Bliss measurement.
            priors: Dict mapping prior name → projected prior tensor [B, T, d_model].
                    Each prior MUST be derived from an external source, NOT from H^ℓ.
                    If derived from H, must be computed from H.detach() (Trap 1).
            router_weights: Optional Kosha router weights per prior.
                            Dict mapping prior_name → scalar weight ≥ 0.
                            If None, uniform weights are used.

        Returns:
            BlissMetrics with B scalar and diagnostic values.
        """
        self._step += 1
        metrics = BlissMetrics()

        if not hidden_states or not priors:
            return metrics

        L = len(hidden_states)
        K = len(priors)

        # Default router weights: uniform
        if router_weights is None:
            router_weights = {name: 1.0 / K for name in priors}

        # Normalize router weights to sum to 1
        w_sum = sum(router_weights.values())
        if w_sum > 0:
            router_weights = {k: v / w_sum for k, v in router_weights.items()}

        # --- Option A: Integration (cosine agreement with priors) ---
        B_A_layers = []
        layer_indices = range(0, L, self.config.compute_every_n_layers)

        for ell in layer_indices:
            H_ell = hidden_states[ell].detach()  # Always detach for measurement

            layer_agreement = 0.0
            for prior_name, P_k in priors.items():
                w_k = router_weights.get(prior_name, 1.0 / K)

                # Compute per-token cosine similarity, then average
                # P_k may need to be broadcast if it doesn't vary per layer
                cos_sim = F.cosine_similarity(H_ell, P_k.detach(), dim=-1)  # [B, T]
                mean_cos = cos_sim.mean().item()

                layer_agreement += w_k * mean_cos

                # Track per-prior cosine (use last layer for reporting)
                if ell == list(layer_indices)[-1]:
                    metrics.cosine_per_prior[prior_name] = mean_cos

            B_A_ell = layer_agreement
            B_A_layers.append(B_A_ell)
            metrics.B_A_per_layer[ell] = B_A_ell

        B_A_mean = sum(B_A_layers) / max(len(B_A_layers), 1)
        metrics.B_A_mean = B_A_mean

        # --- Option B: Cross-layer stability (anti-fragmentation) ---
        B_B = 0.0
        num_deltas = 0
        for ell in range(1, L):
            H_curr = hidden_states[ell].detach()
            H_prev = hidden_states[ell - 1].detach()

            # Per-token directional change
            delta = 1.0 - F.cosine_similarity(H_curr, H_prev, dim=-1)  # [B, T]
            delta_mean = delta.mean().item()
            B_B += delta_mean
            num_deltas += 1
            metrics.delta_per_layer[ell] = delta_mean

        if num_deltas > 0:
            B_B = B_B / num_deltas
        metrics.B_B = B_B

        # --- Combined Bliss ---
        B = B_A_mean - self.config.beta * B_B
        metrics.B = B

        # --- Update running tau ---
        if self.config.use_running_tau:
            self._tau_ema = (1 - self.config.tau_ema_alpha) * self._tau_ema + self.config.tau_ema_alpha * B
            self._tau = self._tau_ema

        return metrics

    def compute_lambda_eff(
        self,
        B: float,
        base_lambdas: Dict[str, float],
    ) -> Dict[str, float]:
        """
        Compute effective injection strengths gated by Bliss.

        λ_{k,eff} = λ_k · (λ_min + (1 - λ_min) · σ(γ · (B − τ)))

        Args:
            B: Current Bliss scalar.
            base_lambdas: Dict mapping prior_name → base λ_k.

        Returns:
            Dict mapping prior_name → effective λ_{k,eff}.
        """
        lambda_eff = {}
        cfg = self.config

        # During warmup, bypass gating
        if self._step < cfg.warmup_steps:
            for name, lam in base_lambdas.items():
                lambda_eff[name] = lam
                self._dead_channel_counter[name] = 0
            return lambda_eff

        # Sigmoid gate
        gate = torch.sigmoid(torch.tensor(cfg.gamma * (B - self._tau))).item()
        effective_gate = cfg.lambda_min + (1.0 - cfg.lambda_min) * gate

        for name, lam in base_lambdas.items():
            lam_eff = lam * effective_gate
            lambda_eff[name] = lam_eff

            # Dead channel tracking (Trap 2)
            floor_threshold = lam * cfg.lambda_min * 1.1
            if lam_eff < floor_threshold:
                self._dead_channel_counter[name] = self._dead_channel_counter.get(name, 0) + 1
                if self._dead_channel_counter[name] >= cfg.dead_channel_alert_steps:
                    logger.warning(
                        f"Dead channel alert: prior '{name}' at floor for "
                        f"{self._dead_channel_counter[name]} steps (λ_eff={lam_eff:.6f})"
                    )
            else:
                self._dead_channel_counter[name] = 0

        return lambda_eff

    def get_eps_layer(self, step: int) -> float:
        """Get current per-layer injection norm cap (ramps from init to max)."""
        cfg = self.config
        if step >= cfg.eps_ramp_steps:
            return cfg.eps_layer_max
        progress = step / max(cfg.eps_ramp_steps, 1)
        return cfg.eps_layer_init + progress * (cfg.eps_layer_max - cfg.eps_layer_init)

    @property
    def tau(self) -> float:
        return self._tau

    @property
    def step_count(self) -> int:
        return self._step


def apply_injection_discipline(
    hidden_state: torch.Tensor,
    priors: Dict[str, torch.Tensor],
    lambda_eff: Dict[str, float],
    layer_scale: float,
    eps_layer: float,
) -> Tuple[torch.Tensor, Dict[str, float]]:
    """
    Apply weak priors to hidden state following injection discipline (G.5).

    1. Each prior is already L2-normalized and confidence-gated by the provider
    2. Sum all scaled priors into a single injection vector
    3. Clip total injection norm to eps_layer × rms(H)
    4. Add to hidden state (post-LayerNorm assumed by caller)

    Args:
        hidden_state: H^ℓ [B, T, d_model] — post-LayerNorm
        priors: Dict mapping prior_name → P_k [B, T, d_model]
        lambda_eff: Dict mapping prior_name → effective λ_{k,eff}
        layer_scale: Per-layer scale s^ℓ (from existing layer_scales)
        eps_layer: Current injection norm cap (fraction of rms(H))

    Returns:
        (modified_hidden_state, injection_norms_per_prior)
    """
    injection_norms = {}

    # Compute total injection vector (Trap 3: additive stacking)
    total_injection = torch.zeros_like(hidden_state)
    for name, P_k in priors.items():
        lam = lambda_eff.get(name, 0.0)
        if lam <= 0:
            injection_norms[name] = 0.0
            continue
        scaled = layer_scale * lam * P_k
        total_injection = total_injection + scaled
        injection_norms[name] = scaled.norm(dim=-1).mean().item()

    # Global norm cap per layer (Trap 3 guardrail)
    injection_norm = total_injection.norm(dim=-1, keepdim=True)  # [B, T, 1]
    h_rms = hidden_state.norm(dim=-1, keepdim=True) / (hidden_state.shape[-1] ** 0.5)  # [B, T, 1]
    max_norm = eps_layer * h_rms
    scale = torch.clamp(max_norm / (injection_norm + 1e-8), max=1.0)
    total_injection = total_injection * scale

    # Count cap violations
    cap_violations = (injection_norm > max_norm).sum().item()
    injection_norms['_cap_violations'] = cap_violations

    # Apply injection (post-LN by contract)
    modified = hidden_state + total_injection

    return modified, injection_norms


class OntologyHealthMonitor:
    """
    12D Permanence Monitoring — G.10.1.

    Tracks singular values, per-axis variance, and basis drift of the
    ontology projection to detect silent dimensional collapse.
    """

    def __init__(
        self,
        eps_sv: float = 0.01,
        eps_var: float = 1e-4,
        cos_drift_threshold: float = 0.5,
        check_every_n_steps: int = 100,
    ):
        self.eps_sv = eps_sv
        self.eps_var = eps_var
        self.cos_drift_threshold = cos_drift_threshold
        self.check_every_n_steps = check_every_n_steps

        self._initial_weight: Optional[torch.Tensor] = None
        self._step = 0
        self._consecutive_low_var: Dict[int, int] = {}

    def register_initial_weight(self, weight: torch.Tensor):
        """Store initial projection weight for drift comparison."""
        self._initial_weight = weight.detach().clone()

    @torch.no_grad()
    def check(
        self,
        projection_weight: torch.Tensor,
        ontology_output: Optional[torch.Tensor] = None,
    ) -> Dict[str, any]:
        """
        Run 12D health checks.

        Args:
            projection_weight: Ontology projection W [12, d_model] or [d_model, 12]
            ontology_output: Optional batch of 12D outputs [B, T, 12] for variance check

        Returns:
            Dict with health metrics and any alerts.
        """
        self._step += 1
        if self._step % self.check_every_n_steps != 0:
            return {}

        results = {'step': self._step, 'alerts': []}

        # Store initial weight on first check
        if self._initial_weight is None:
            self.register_initial_weight(projection_weight)

        # Singular value check
        try:
            S = torch.linalg.svdvals(projection_weight.float())
            results['singular_values'] = S.tolist()
            results['min_sv'] = S.min().item()
            if S.min().item() < self.eps_sv:
                alert = f"12D collapse risk: min singular value = {S.min().item():.6f}"
                results['alerts'].append(alert)
                logger.warning(alert)
        except Exception as e:
            results['svd_error'] = str(e)

        # Per-axis variance check
        if ontology_output is not None:
            axis_var = ontology_output.detach().float().var(dim=(0, 1))  # [12]
            results['axis_variance'] = axis_var.tolist()
            for dim_idx in range(axis_var.shape[0]):
                if axis_var[dim_idx].item() < self.eps_var:
                    self._consecutive_low_var[dim_idx] = self._consecutive_low_var.get(dim_idx, 0) + 1
                    if self._consecutive_low_var[dim_idx] >= 100:
                        alert = f"12D axis {dim_idx} below variance threshold for {self._consecutive_low_var[dim_idx]} checks"
                        results['alerts'].append(alert)
                        logger.warning(alert)
                else:
                    self._consecutive_low_var[dim_idx] = 0

        # Basis drift check
        if self._initial_weight is not None:
            cos_sim = F.cosine_similarity(
                projection_weight.float(),
                self._initial_weight.float().to(projection_weight.device),
                dim=-1,
            )  # [12] or [d_model] depending on shape
            results['basis_drift_cosine'] = cos_sim.tolist()
            drifted = (cos_sim < self.cos_drift_threshold).sum().item()
            if drifted > 0:
                alert = f"12D: {drifted} axes drifted >{int((1-self.cos_drift_threshold)*180/3.14159)}° from init"
                results['alerts'].append(alert)
                logger.warning(alert)

        return results


class GradientVarianceTracker:
    """
    Gradient Variance Tracking — G.10.3.

    Tracks gradient norm mean, variance, and layer-wise cosine similarity
    to detect instability from dual injection paths and coherence feedback.
    """

    def __init__(self, window_size: int = 100, variance_spike_factor: float = 10.0):
        self.window_size = window_size
        self.variance_spike_factor = variance_spike_factor

        self._grad_history: Dict[str, List[float]] = {}
        self._baseline_variance: Dict[str, float] = {}
        self._prev_grads: Dict[str, torch.Tensor] = {}
        self._baseline_set = False
        self._step = 0
        # V9.9.1: Rate-limit alerts per layer (only alert once per window_size steps)
        self._last_alert_step: Dict[str, int] = {}
        # V9.9.1: EMA factor for baseline updates (adapts to LR changes)
        # V10.15: Increased from 0.01 to 0.05 so baseline tracks LR warmup
        # faster, preventing false positive spike alerts during warmup phase
        self._baseline_ema_alpha = 0.05

    def notify_lr_change(self, factor: float):
        """Scale baselines when LR changes abruptly (e.g. LR boost).

        Gradient norms scale ~linearly with LR, so variance scales ~factor².
        Without this, a 1.5x LR boost causes every layer to exceed the spike
        threshold and flood the log with false-positive alerts.
        """
        scale = factor ** 2
        for name in self._baseline_variance:
            self._baseline_variance[name] *= scale

    def get_spike_count_since(self, since_step: int) -> int:
        """Return number of unique params that spiked since given step.

        Used by AdaptiveTrainingController to dampen future boosts when
        previous boosts caused widespread gradient instability.
        """
        count = 0
        for name, last_step in self._last_alert_step.items():
            if last_step >= since_step:
                count += 1
        return count

    @torch.no_grad()
    def record(self, model: torch.nn.Module) -> Dict[str, any]:
        """
        Record gradient statistics for one training step.

        Call AFTER backward(), BEFORE optimizer.step().

        Returns:
            Dict with gradient health metrics and any spike alerts.
        """
        self._step += 1
        results = {'step': self._step, 'alerts': []}

        total_norm = 0.0
        param_count = 0

        for name, param in model.named_parameters():
            if param.grad is None:
                continue

            grad_norm = param.grad.norm().item()
            total_norm += grad_norm ** 2
            param_count += 1

            # Only track named layers, not every parameter
            # Focus on larger parameters for efficiency
            if param.numel() < 1000:
                continue

            if name not in self._grad_history:
                self._grad_history[name] = []

            self._grad_history[name].append(grad_norm)

            # Keep window bounded
            if len(self._grad_history[name]) > self.window_size:
                self._grad_history[name] = self._grad_history[name][-self.window_size:]

            # Check variance after we have enough samples
            if len(self._grad_history[name]) >= self.window_size:
                norms = self._grad_history[name]
                mean_val = sum(norms) / len(norms)
                variance = sum((x - mean_val) ** 2 for x in norms) / len(norms)

                # Set baseline on first full window
                if name not in self._baseline_variance:
                    self._baseline_variance[name] = max(variance, 1e-10)
                    continue

                baseline = self._baseline_variance[name]

                # V9.9.1: EMA-update the baseline so it adapts to LR changes
                # Without this, a one-time LR boost permanently exceeds the
                # frozen baseline and floods the log every step.
                self._baseline_variance[name] = (
                    (1 - self._baseline_ema_alpha) * baseline
                    + self._baseline_ema_alpha * variance
                )

                if variance > self.variance_spike_factor * baseline:
                    # V9.9.1: Rate-limit alerts — at most once per window_size steps per layer
                    last_alert = self._last_alert_step.get(name, -self.window_size)
                    if self._step - last_alert >= self.window_size:
                        self._last_alert_step[name] = self._step
                        alert = (
                            f"Gradient variance spike: {name} "
                            f"var={variance:.6f} vs baseline={baseline:.6f} "
                            f"({variance/baseline:.1f}x)"
                        )
                        results['alerts'].append(alert)
                        logger.warning(alert)

            # Layer-wise gradient cosine (direction stability)
            grad_flat = param.grad.detach().flatten()
            if name in self._prev_grads:
                prev = self._prev_grads[name]
                if prev.shape == grad_flat.shape:
                    cos = F.cosine_similarity(grad_flat.unsqueeze(0), prev.unsqueeze(0)).item()
                    if cos < 0.0:  # Gradient direction reversal
                        results.setdefault('direction_reversals', []).append(name)
            self._prev_grads[name] = grad_flat.clone()

        results['total_grad_norm'] = total_norm ** 0.5
        results['param_count'] = param_count

        return results
