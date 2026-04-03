"""
FSCS-V: Frequency-Stratified Coherence for Video Diffusion.

Wrapper module that injects temporal coherence gradients into the
denoising loop of video diffusion models. Implements the patent's
core formula C' = C+ * S+ with two-component gradient composition.

Addresses temporal consistency weaknesses (flickering, identity drift,
motion incoherence) without retraining the base model.

Patent formulas implemented:
  D1: C+ = (PhaseCorr(u, v) + 1) / 2       (rectified phase correlation)
  D2: S+ = (cos(u, v) + 1) / 2             (rectified semantic similarity)
  D3: C' = C+ * S+                          (multiplicative coherence)
  V1: z_hat_0 = (z_t - sqrt(1-a)*eps) / sqrt(a)  (Tweedie projection)
  V2: lambda(t) coupling schedule
  V3: ||lambda*grad(C')|| <= tau*||eps||     (gradient safety bound)
  V4: Three-band semantic hierarchy

Usage with PhaseQuadVideoPipeline:
    >>> from symbolu_extensions.vision.video.fscsv_wrapper import FSCSVModule, FSCSVConfig, make_fscsv_callback
    >>> fscsv = FSCSVModule(FSCSVConfig(lambda_max=0.1))
    >>> callback = make_fscsv_callback(fscsv)
    >>> result = pipeline.generate("A cat playing", coherence_callback=callback)

Usage with FSCSVPipeline (convenience wrapper):
    >>> from symbolu_extensions.vision.video.fscsv_wrapper import FSCSVPipeline, FSCSVConfig
    >>> pipeline = FSCSVPipeline.create_mock(fscsv_config=FSCSVConfig())
    >>> result = pipeline.generate("A cat playing")
"""

import math
from dataclasses import dataclass, field
from typing import Optional, Tuple, Dict, Callable

import torch
import torch.nn as nn
import torch.nn.functional as F
from torch import Tensor


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

@dataclass
class FSCSVConfig:
    """
    Configuration for FSCS-V coherence injection.

    Patent reference: FSCS-DIFFUSION v3.2

    The coupling schedule controls how strongly coherence gradients are
    injected at each denoising step. It is strongest at high-noise timesteps
    (early denoising) and decays toward clean frames.

    The identity schedule is the reverse: strongest toward clean frames
    where identity should be locked to prevent drift.
    """

    # Coupling schedule: lambda(t) = lambda_max * ((t - delta)+ / (T - delta))^alpha
    lambda_max: float = 0.1
    lambda_alpha: float = 2.0
    warmup_delta: int = 50

    # Identity schedule: beta_id(t) = beta_max * (1 - t/T)^gamma_id
    beta_id_max: float = 0.05
    gamma_id: float = 1.5

    # Three-band semantic hierarchy
    enable_bands: bool = True
    semantic_weight: float = 1.0   # Low-frequency: object identity, scene type
    spatial_weight: float = 0.5    # Mid-frequency: spatial layout, positions
    detail_weight: float = 0.25    # High-frequency: textures, fine detail
    spatial_pool_factor: int = 4   # Downsample factor for spatial band

    # Gradient safety: ||lambda * grad(C')|| <= tau * ||eps||
    safety_tau: float = 0.1

    # Proxy encoder (requires separate training; off by default)
    proxy_dim: int = 256
    use_proxy: bool = False

    # Diffusion
    num_total_timesteps: int = 1000


# ---------------------------------------------------------------------------
# Schedules
# ---------------------------------------------------------------------------

class CouplingSchedule:
    """
    Coupling schedule for coherence gradient injection.

    Patent formula:
        lambda(t) = lambda_max * ((t - delta)+ / (T - delta))^alpha

    Strong at high noise (early denoising), decays toward clean frames.
    Warmup period (first `delta` steps) returns zero — no interference
    during initial structure formation.
    """

    def __init__(
        self,
        lambda_max: float = 0.1,
        alpha: float = 2.0,
        warmup_delta: int = 50,
        total_timesteps: int = 1000,
    ):
        self.lambda_max = lambda_max
        self.alpha = alpha
        self.warmup_delta = warmup_delta
        self.total_timesteps = total_timesteps

    def __call__(self, t: int) -> float:
        """Compute coupling strength at timestep t."""
        if t <= self.warmup_delta:
            return 0.0
        denom = max(self.total_timesteps - self.warmup_delta, 1)
        progress = (t - self.warmup_delta) / denom
        return self.lambda_max * (progress ** self.alpha)


class IdentitySchedule:
    """
    Identity-locking schedule.

    Patent formula:
        beta_id(t) = beta_max * (1 - t/T)^gamma_id

    Stronger toward clean frames (low t) where identity should be locked.
    Opposite direction from the main coupling schedule.
    """

    def __init__(
        self,
        beta_max: float = 0.05,
        gamma_id: float = 1.5,
        total_timesteps: int = 1000,
    ):
        self.beta_max = beta_max
        self.gamma_id = gamma_id
        self.total_timesteps = total_timesteps

    def __call__(self, t: int) -> float:
        """Compute identity-locking strength at timestep t."""
        progress = t / max(self.total_timesteps, 1)
        return self.beta_max * ((1.0 - progress) ** self.gamma_id)


# ---------------------------------------------------------------------------
# Gradient Safety
# ---------------------------------------------------------------------------

class GradientSafetyBound:
    """
    Gradient safety bound.

    Patent formula:
        ||lambda(t) * grad(C')|| <= tau * ||eps_theta||

    Prevents coherence gradients from overwhelming the base prediction.
    Applies per-tensor scaling: min(1, tau * ||eps|| / ||grad||).
    """

    def __init__(self, tau: float = 0.1):
        self.tau = tau

    def __call__(self, coherence_grad: Tensor, base_prediction: Tensor) -> Tensor:
        """Apply safety bound. Returns bounded gradient."""
        grad_norm = coherence_grad.norm()
        if grad_norm < 1e-10:
            return coherence_grad
        max_norm = self.tau * base_prediction.norm()
        scale = min(1.0, max_norm.item() / grad_norm.item())
        return coherence_grad * scale


# ---------------------------------------------------------------------------
# Three-Band Decomposition
# ---------------------------------------------------------------------------

class ThreeBandDecomposer(nn.Module):
    """
    Three-band frequency decomposition for semantic hierarchy.

    Decomposes video latents into:
      - Semantic band: Global average per frame (identity, scene type)
      - Spatial band: Coarse spatial grid (positions, relationships)
      - Detail band: Full resolution residual (textures, edges)

    Patent reference: Issue 8 — Three-Band Video Architecture.
    """

    def __init__(self, spatial_pool_factor: int = 4):
        super().__init__()
        self.spatial_pool_factor = spatial_pool_factor

    def forward(self, z: Tensor) -> Tuple[Tensor, Tensor, Tensor]:
        """
        Decompose video latent into three semantic bands.

        Args:
            z: Video latent [B, C, T, H, W].

        Returns:
            semantic: [B, C, T, 1, 1] global features per frame.
            spatial:  [B, C, T, H', W'] coarse spatial layout.
            detail:   [B, C, T, H, W] fine detail residual.
        """
        B, C, T, H, W = z.shape

        # Semantic: global average per frame
        semantic = z.mean(dim=(-2, -1), keepdim=True)  # [B, C, T, 1, 1]

        # Spatial: adaptive pool to coarse grid
        pool_h = max(1, H // self.spatial_pool_factor)
        pool_w = max(1, W // self.spatial_pool_factor)
        z_frames = z.reshape(B * T, C, H, W)
        spatial_frames = F.adaptive_avg_pool2d(z_frames, (pool_h, pool_w))
        spatial = spatial_frames.reshape(B, C, T, pool_h, pool_w)

        # Detail: residual after upsampling spatial back to full resolution
        spatial_up = F.interpolate(
            spatial_frames, size=(H, W), mode="bilinear", align_corners=False,
        ).reshape(B, C, T, H, W)
        detail = z - spatial_up

        return semantic, spatial, detail


# ---------------------------------------------------------------------------
# Proxy Encoder (Optional — requires separate training)
# ---------------------------------------------------------------------------

class ProxyEncoder(nn.Module):
    """
    Proxy encoder for efficient coherence feature extraction.

    Projects diffusion latents to a compact coherence feature space.
    Can be trained with CLIP distillation for richer features.

    Patent formula:
        phi_proxy(z) = W_proxy * z  (with optional FiLM conditioning)
    """

    def __init__(self, in_channels: int, proxy_dim: int):
        super().__init__()
        self.proj = nn.Conv3d(in_channels, proxy_dim, kernel_size=1, bias=False)
        self.norm = nn.GroupNorm(min(8, proxy_dim), proxy_dim)

    def forward(self, z: Tensor) -> Tensor:
        """
        Extract coherence features.

        Args:
            z: Video latent [B, C, T, H, W].

        Returns:
            features: [B, proxy_dim, T, H, W].
        """
        return self.norm(self.proj(z))


# ---------------------------------------------------------------------------
# Coherence Primitives
# ---------------------------------------------------------------------------

def compute_phase_correlation(x: Tensor, y: Tensor, eps: float = 1e-8) -> Tensor:
    """
    Compute rectified phase correlation C+ between feature vectors.

    Patent formula D1:
        C+ = (PhaseCorr(u, v) + 1) / 2

    Interprets feature dimensions as complex phasor pairs and measures
    alignment of their phases. Based on formula U1:
        C[i,j] = (1/W) * sum_k cos(phi_i[k] - phi_j[k])

    Args:
        x: Features [..., D].
        y: Features [..., D].
        eps: Numerical stability.

    Returns:
        C_plus: Rectified phase correlation in [0, 1], shape [...].
    """
    D = x.shape[-1]
    half_D = D // 2

    # Split into real/imaginary pairs (complex phasor interpretation)
    x_re, x_im = x[..., :half_D], x[..., half_D : 2 * half_D]
    y_re, y_im = y[..., :half_D], y[..., half_D : 2 * half_D]

    # Cross-correlation: Re(x * conj(y)) = x_re*y_re + x_im*y_im
    cross_re = x_re * y_re + x_im * y_im

    # Magnitudes
    x_mag = torch.sqrt(x_re ** 2 + x_im ** 2 + eps)
    y_mag = torch.sqrt(y_re ** 2 + y_im ** 2 + eps)

    # Normalized phase correlation per component
    phase_corr = cross_re / (x_mag * y_mag + eps)  # [..., half_D]

    # Average over feature components (formula U1)
    raw_corr = phase_corr.mean(dim=-1)  # [...]

    # Rectify to [0, 1]
    return (raw_corr + 1.0) / 2.0


def compute_semantic_similarity(x: Tensor, y: Tensor, eps: float = 1e-8) -> Tensor:
    """
    Compute rectified semantic similarity S+ between feature vectors.

    Patent formula D2:
        S+ = (cos(u, v) + 1) / 2

    Args:
        x: Features [..., D].
        y: Features [..., D].
        eps: Numerical stability.

    Returns:
        S_plus: Rectified semantic similarity in [0, 1], shape [...].
    """
    x_norm = F.normalize(x, dim=-1, eps=eps)
    y_norm = F.normalize(y, dim=-1, eps=eps)
    cos_sim = (x_norm * y_norm).sum(dim=-1)
    return (cos_sim + 1.0) / 2.0


class FrameCoherence(nn.Module):
    """
    Frame-to-frame coherence computation.

    Computes rectified coherence C' = C+ * S+ between adjacent frames
    using the patent's two-component multiplicative formula.

    Patent formula D3:
        C' = C+ * S+
        grad(C') = S+ * grad(C+) + C+ * grad(S+)  [product rule]
    """

    def forward(
        self, frame_features: Tensor
    ) -> Tuple[Tensor, Tensor, Tensor]:
        """
        Compute coherence scores between adjacent frames.

        Args:
            frame_features: [B, T, D] per-frame feature vectors.

        Returns:
            C_prime: [B, T-1] multiplicative coherence.
            C_plus:  [B, T-1] phase correlation.
            S_plus:  [B, T-1] semantic similarity.
        """
        B, T, D = frame_features.shape

        if T < 2:
            device = frame_features.device
            empty = torch.ones(B, 0, device=device)
            return empty, empty, empty

        prev_frames = frame_features[:, :-1]  # [B, T-1, D]
        curr_frames = frame_features[:, 1:]   # [B, T-1, D]

        C_plus = compute_phase_correlation(prev_frames, curr_frames)  # [B, T-1]
        S_plus = compute_semantic_similarity(prev_frames, curr_frames)  # [B, T-1]
        C_prime = C_plus * S_plus  # [B, T-1]

        return C_prime, C_plus, S_plus


# ---------------------------------------------------------------------------
# Tweedie Projection
# ---------------------------------------------------------------------------

class TweedieProjection:
    """
    Tweedie denoising projection.

    Predicts clean sample from noisy latents and noise prediction.

    Patent formula V1:
        z_hat_0 = (z_t - sqrt(1 - alpha_bar_t) * eps_theta) / sqrt(alpha_bar_t)
    """

    @staticmethod
    def project(
        z_t: Tensor,
        eps_theta: Tensor,
        t: int,
        sqrt_alphas_cumprod: Tensor,
        sqrt_one_minus_alphas_cumprod: Tensor,
        clamp: float = 3.0,
    ) -> Tensor:
        """
        Compute Tweedie projection to predict clean frame.

        Args:
            z_t: Noisy latent [B, C, T, H, W].
            eps_theta: Predicted noise [B, C, T, H, W].
            t: Current timestep.
            sqrt_alphas_cumprod: sqrt(alpha_bar) schedule.
            sqrt_one_minus_alphas_cumprod: sqrt(1-alpha_bar) schedule.
            clamp: Clamping range for stability.

        Returns:
            z_hat_0: Predicted clean latent [B, C, T, H, W].
        """
        sqrt_alpha = sqrt_alphas_cumprod[t]
        sqrt_one_minus_alpha = sqrt_one_minus_alphas_cumprod[t]

        z_hat_0 = (z_t - sqrt_one_minus_alpha * eps_theta) / (sqrt_alpha + 1e-8)

        if clamp > 0:
            z_hat_0 = z_hat_0.clamp(-clamp, clamp)

        return z_hat_0


# ---------------------------------------------------------------------------
# Main FSCS-V Module
# ---------------------------------------------------------------------------

class FSCSVModule(nn.Module):
    """
    FSCS-V: Frequency-Stratified Coherence for Video.

    Combines all FSCS-V components to compute coherence-corrected noise
    predictions. Operates as a wrapper around any video diffusion model's
    denoising loop.

    The correction modifies the noise prediction at each step:
        eps_corrected = eps_theta + noise_space_correction

    Where the correction pushes the denoising trajectory toward more
    temporally coherent frame sequences, weighted by the product of
    phase correlation C+ and semantic similarity S+.

    Args:
        config: FSCSVConfig with all hyperparameters.
        latent_channels: Number of channels in the latent space.
    """

    def __init__(self, config: FSCSVConfig, latent_channels: int = 16):
        super().__init__()
        self.config = config
        self.latent_channels = latent_channels

        # Schedules
        self.coupling_schedule = CouplingSchedule(
            lambda_max=config.lambda_max,
            alpha=config.lambda_alpha,
            warmup_delta=config.warmup_delta,
            total_timesteps=config.num_total_timesteps,
        )
        self.identity_schedule = IdentitySchedule(
            beta_max=config.beta_id_max,
            gamma_id=config.gamma_id,
            total_timesteps=config.num_total_timesteps,
        )

        # Safety bound
        self.safety_bound = GradientSafetyBound(tau=config.safety_tau)

        # Three-band decomposition
        if config.enable_bands:
            self.band_decomposer = ThreeBandDecomposer(
                spatial_pool_factor=config.spatial_pool_factor,
            )
            self.band_weights = {
                "semantic": config.semantic_weight,
                "spatial": config.spatial_weight,
                "detail": config.detail_weight,
            }

        # Proxy encoder (optional)
        if config.use_proxy:
            self.proxy_encoder = ProxyEncoder(latent_channels, config.proxy_dim)

        # Frame coherence
        self.frame_coherence = FrameCoherence()

        # Diagnostics
        self._last_metrics: Dict[str, float] = {}

        # Reference frame for identity locking (set externally)
        self._reference_features: Optional[Tensor] = None

    def set_reference_frame(self, features: Tensor):
        """
        Set reference frame features for identity locking.

        Call this before generation with features from a known-good frame.
        Typically the first generated frame or a user-provided reference.

        Args:
            features: [B, C] per-channel features from a reference frame.
        """
        self._reference_features = features.detach()

    # ------------------------------------------------------------------
    # Band-level coherence correction
    # ------------------------------------------------------------------

    def _compute_band_correction(
        self,
        band_z: Tensor,
        band_name: str,
        coupling_lambda: float,
    ) -> Tensor:
        """
        Compute coherence correction for a single frequency band.

        For each adjacent frame pair, measures incoherence (1 - C')
        and generates a correction that nudges both frames toward
        each other proportionally to their disagreement.

        Args:
            band_z: Band-filtered latent [B, C, T, *spatial].
            band_name: "semantic", "spatial", or "detail".
            coupling_lambda: Current coupling schedule value.

        Returns:
            correction: Same shape as band_z, in z_hat_0 space.
        """
        B, C, T = band_z.shape[:3]
        spatial_dims = band_z.shape[3:]

        if T < 2:
            return torch.zeros_like(band_z)

        band_weight = self.band_weights.get(band_name, 1.0)
        effective_lambda = coupling_lambda * band_weight

        # Adjacent frame features
        prev = band_z[:, :, :-1]  # [B, C, T-1, ...]
        curr = band_z[:, :, 1:]   # [B, C, T-1, ...]

        # Flatten spatial dims for coherence computation
        total_spatial = 1
        for s in spatial_dims:
            total_spatial *= s

        # Reshape to [..., C] for coherence primitives
        # [B, C, T-1, *spatial] -> [B*(T-1)*spatial, C]
        prev_features = (
            prev.reshape(B, C, (T - 1) * total_spatial)
            .permute(0, 2, 1)
            .reshape(-1, C)
        )
        curr_features = (
            curr.reshape(B, C, (T - 1) * total_spatial)
            .permute(0, 2, 1)
            .reshape(-1, C)
        )

        # Phase correlation C+ and semantic similarity S+
        C_plus = compute_phase_correlation(prev_features, curr_features)
        S_plus = compute_semantic_similarity(prev_features, curr_features)
        C_prime = C_plus * S_plus  # [B*(T-1)*spatial]

        # Incoherence weight: higher = more correction needed
        incoherence = (1.0 - C_prime).clamp(0.0, 1.0)

        # Reshape to [B, 1, T-1, *spatial] for broadcasting
        incoherence = incoherence.reshape(B, T - 1, *spatial_dims).unsqueeze(1)

        # Correction direction: push frames toward each other
        diff = prev - curr  # [B, C, T-1, *spatial]
        pair_correction = effective_lambda * incoherence * diff

        # Distribute symmetrically across frame pairs
        correction = torch.zeros_like(band_z)
        correction[:, :, 1:] = correction[:, :, 1:] + pair_correction * 0.5
        correction[:, :, :-1] = correction[:, :, :-1] - pair_correction * 0.5

        return correction

    # ------------------------------------------------------------------
    # Identity locking
    # ------------------------------------------------------------------

    def _compute_identity_correction(
        self,
        z_hat_0: Tensor,
        identity_beta: float,
    ) -> Tensor:
        """
        Compute identity-locking correction.

        Pushes per-frame global features toward the reference frame
        to prevent identity drift over long sequences.

        Args:
            z_hat_0: Predicted clean latent [B, C, T, H, W].
            identity_beta: Current identity schedule strength.

        Returns:
            correction: [B, C, T, H, W] identity correction.
        """
        if self._reference_features is None:
            return torch.zeros_like(z_hat_0)

        B, C, T, H, W = z_hat_0.shape
        ref = self._reference_features  # [B, C]

        if ref.shape[-1] != C:
            return torch.zeros_like(z_hat_0)

        # Per-frame global features
        frame_features = z_hat_0.mean(dim=(-2, -1))  # [B, C, T]

        # Drift from reference
        drift = ref.unsqueeze(-1) - frame_features  # [B, C, T]

        # Broadcast to spatial dimensions
        correction = identity_beta * drift[:, :, :, None, None].expand_as(z_hat_0)
        return correction

    # ------------------------------------------------------------------
    # Main correction entry point
    # ------------------------------------------------------------------

    @torch.no_grad()
    def correct_noise_prediction(
        self,
        noise_pred: Tensor,
        z_t: Tensor,
        t: int,
        noise_schedule,
    ) -> Tensor:
        """
        Apply FSCS-V coherence correction to noise prediction.

        This is the main entry point. Called once per denoising step,
        after the model produces its noise prediction and before the
        scheduler step.

        The correction flow:
          1. Compute coupling strength lambda(t)
          2. Tweedie-project to predict clean frames z_hat_0
          3. Decompose into semantic bands (optional)
          4. Compute per-band coherence C' = C+ * S+
          5. Generate corrections in z_hat_0 space
          6. Convert to noise space via Tweedie chain rule
          7. Apply gradient safety bound
          8. Add to noise prediction

        Args:
            noise_pred: Base noise prediction [B, C, T, H, W].
            z_t: Current noisy latents [B, C, T, H, W].
            t: Current diffusion timestep.
            noise_schedule: NoiseSchedule with alpha parameters.

        Returns:
            corrected_noise_pred: Coherence-corrected noise prediction.
        """
        coupling_lambda = self.coupling_schedule(t)
        identity_beta = self.identity_schedule(t)

        # Skip entirely during warmup
        if coupling_lambda == 0.0 and identity_beta == 0.0:
            return noise_pred

        # Tweedie projection: predict clean frame
        z_hat_0 = TweedieProjection.project(
            z_t,
            noise_pred,
            t,
            noise_schedule.sqrt_alphas_cumprod,
            noise_schedule.sqrt_one_minus_alphas_cumprod,
        )

        # Compute coherence correction in z_hat_0 space
        if self.config.enable_bands and hasattr(self, "band_decomposer"):
            correction_z0 = self._compute_banded_correction(
                z_hat_0, coupling_lambda,
            )
        else:
            correction_z0 = self._compute_band_correction(
                z_hat_0, "semantic", coupling_lambda,
            )

        # Identity locking
        if identity_beta > 0.0 and self._reference_features is not None:
            correction_z0 = correction_z0 + self._compute_identity_correction(
                z_hat_0, identity_beta,
            )

        # Convert correction from z_hat_0 space to noise space.
        # Chain rule: d(eps)/d(z_hat_0) = -sqrt(alpha_bar) / sqrt(1-alpha_bar)
        sqrt_alpha = noise_schedule.sqrt_alphas_cumprod[t]
        sqrt_one_minus_alpha = noise_schedule.sqrt_one_minus_alphas_cumprod[t]
        noise_correction = (
            -correction_z0 * sqrt_alpha / (sqrt_one_minus_alpha + 1e-8)
        )

        # Gradient safety bound
        noise_correction = self.safety_bound(noise_correction, noise_pred)

        # Update diagnostics
        self._update_metrics(
            z_hat_0, coupling_lambda, identity_beta,
            noise_correction, noise_pred, t,
        )

        return noise_pred + noise_correction

    def _compute_banded_correction(
        self,
        z_hat_0: Tensor,
        coupling_lambda: float,
    ) -> Tensor:
        """
        Compute coherence correction using three-band decomposition.

        Decomposes z_hat_0 into semantic, spatial, and detail bands,
        computes per-band corrections, and reconstructs the full
        correction in z_hat_0 space.
        """
        B, C, T, H, W = z_hat_0.shape

        semantic, spatial, detail = self.band_decomposer(z_hat_0)

        # Per-band corrections
        corr_semantic = self._compute_band_correction(
            semantic, "semantic", coupling_lambda,
        )
        corr_spatial = self._compute_band_correction(
            spatial, "spatial", coupling_lambda,
        )
        corr_detail = self._compute_band_correction(
            detail, "detail", coupling_lambda,
        )

        # Upsample semantic correction (1x1) to full resolution
        semantic_up = corr_semantic.expand(-1, -1, -1, H, W)

        # Upsample spatial correction to full resolution
        pool_h, pool_w = corr_spatial.shape[3], corr_spatial.shape[4]
        spatial_up = F.interpolate(
            corr_spatial.reshape(B * T, C, pool_h, pool_w),
            size=(H, W),
            mode="bilinear",
            align_corners=False,
        ).reshape(B, C, T, H, W)

        return semantic_up + spatial_up + corr_detail

    # ------------------------------------------------------------------
    # Diagnostics
    # ------------------------------------------------------------------

    def _update_metrics(
        self,
        z_hat_0: Tensor,
        coupling_lambda: float,
        identity_beta: float,
        noise_correction: Tensor,
        noise_pred: Tensor,
        t: int,
    ):
        """Update diagnostic metrics from this denoising step."""
        B, C, T = z_hat_0.shape[:3]

        # Global frame features for coherence measurement
        features = z_hat_0.mean(dim=(-2, -1)).permute(0, 2, 1)  # [B, T, C]

        metrics: Dict[str, float] = {
            "fscsv/coupling_lambda": coupling_lambda,
            "fscsv/identity_beta": identity_beta,
            "fscsv/correction_norm": noise_correction.norm().item(),
            "fscsv/prediction_norm": noise_pred.norm().item(),
            "fscsv/correction_ratio": (
                noise_correction.norm().item()
                / max(noise_pred.norm().item(), 1e-8)
            ),
            "fscsv/timestep": float(t),
        }

        if T >= 2:
            C_prime, C_plus, S_plus = self.frame_coherence(features)
            metrics["fscsv/C_prime_mean"] = C_prime.mean().item()
            metrics["fscsv/C_plus_mean"] = C_plus.mean().item()
            metrics["fscsv/S_plus_mean"] = S_plus.mean().item()

        self._last_metrics = metrics

    def get_metrics(self) -> Dict[str, float]:
        """Get diagnostic metrics from the most recent denoising step."""
        return self._last_metrics.copy()


# ---------------------------------------------------------------------------
# Callback Factory
# ---------------------------------------------------------------------------

def make_fscsv_callback(
    fscsv_module: FSCSVModule,
) -> Callable[[Tensor, Tensor, int, object], Tensor]:
    """
    Create a coherence callback for use with PhaseQuadVideoPipeline.

    The returned callback has the signature expected by the pipeline's
    ``coherence_callback`` parameter.

    Args:
        fscsv_module: Configured FSCSVModule instance.

    Returns:
        Callback function: (noise_pred, latents, t, noise_schedule) -> corrected_noise_pred
    """

    def callback(
        noise_pred: Tensor,
        latents: Tensor,
        t: int,
        noise_schedule,
    ) -> Tensor:
        return fscsv_module.correct_noise_prediction(
            noise_pred, latents, t, noise_schedule,
        )

    return callback


# ---------------------------------------------------------------------------
# Convenience Pipeline Wrapper
# ---------------------------------------------------------------------------

class FSCSVPipeline:
    """
    Video generation pipeline with FSCS-V coherence injection.

    Wraps a PhaseQuadVideoPipeline and injects coherence correction
    at every denoising step. Provides the same API as the base
    pipeline.

    Usage:
        >>> pipeline = FSCSVPipeline.create_mock(fscsv_config=FSCSVConfig())
        >>> result = pipeline.generate("A cat playing in the garden")
        >>> print(pipeline.get_coherence_metrics())

    Or wrap an existing pipeline:
        >>> base_pipeline = PhaseQuadVideoPipeline.create_mock()
        >>> pipeline = FSCSVPipeline.from_pipeline(base_pipeline)
    """

    def __init__(
        self,
        base_pipeline,
        fscsv_config: Optional[FSCSVConfig] = None,
    ):
        self.pipeline = base_pipeline
        config = fscsv_config or FSCSVConfig()
        self.fscsv = FSCSVModule(
            config,
            latent_channels=base_pipeline.config.vae.latent_channels,
        )
        self._callback = make_fscsv_callback(self.fscsv)

    @classmethod
    def create_mock(
        cls,
        model_size: str = "tiny",
        device=None,
        fscsv_config: Optional[FSCSVConfig] = None,
    ) -> "FSCSVPipeline":
        """Create pipeline with mock components for testing."""
        from symbolu_extensions.vision.video.pipeline import PhaseQuadVideoPipeline

        base = PhaseQuadVideoPipeline.create_mock(model_size=model_size, device=device)
        return cls(base, fscsv_config=fscsv_config)

    @classmethod
    def from_pipeline(
        cls,
        base_pipeline,
        fscsv_config: Optional[FSCSVConfig] = None,
    ) -> "FSCSVPipeline":
        """Wrap an existing PhaseQuadVideoPipeline with FSCS-V."""
        return cls(base_pipeline, fscsv_config=fscsv_config)

    @classmethod
    def from_pretrained(
        cls,
        checkpoint_path: Optional[str] = None,
        model_size: str = "small",
        vae_model_id: str = "THUDM/CogVideoX-2b",
        device=None,
        fscsv_config: Optional[FSCSVConfig] = None,
    ) -> "FSCSVPipeline":
        """Create pipeline with pretrained components plus FSCS-V."""
        from symbolu_extensions.vision.video.pipeline import PhaseQuadVideoPipeline

        base = PhaseQuadVideoPipeline.from_pretrained(
            checkpoint_path=checkpoint_path,
            model_size=model_size,
            vae_model_id=vae_model_id,
            device=device,
        )
        return cls(base, fscsv_config=fscsv_config)

    def generate(self, prompt, negative_prompt=None, config=None, callback=None):
        """
        Generate video with FSCS-V coherence injection.

        Same API as PhaseQuadVideoPipeline.generate() but automatically
        injects coherence correction at every denoising step.
        """
        return self.pipeline.generate(
            prompt=prompt,
            negative_prompt=negative_prompt,
            config=config,
            callback=callback,
            coherence_callback=self._callback,
        )

    def get_coherence_metrics(self) -> Dict[str, float]:
        """Get FSCS-V coherence metrics from the most recent generation."""
        return self.fscsv.get_metrics()

    def __repr__(self) -> str:
        return (
            f"FSCSVPipeline(\n"
            f"  base={self.pipeline!r},\n"
            f"  fscsv_config=FSCSVConfig(\n"
            f"    lambda_max={self.fscsv.config.lambda_max},\n"
            f"    enable_bands={self.fscsv.config.enable_bands},\n"
            f"    safety_tau={self.fscsv.config.safety_tau},\n"
            f"  )\n"
            f")"
        )
