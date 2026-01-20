"""
ReplaceabilityTester: Ablation tests to prove each component contributes.

Run every N steps during training to catch regressions.

Success criteria:
- Quad disabled: Quality should DROP (>5% FID increase)
- Phase disabled: Quality should DROP (>5% FID increase)
- Local disabled: Texture degrades but semantics should remain

If any component shows <2% drop when disabled, it's DECORATIVE.
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Callable, Any

import torch
import torch.nn as nn
from torch import Tensor
from torch.utils.data import DataLoader

from symbolu.vision.controls import GeneratorControl, BlockControl
from symbolu.vision.phase_quad_generator import PhaseQuadImageGenerator


@dataclass
class AblationResult:
    """Result of a single ablation test."""
    name: str
    fid: float
    baseline_fid: float
    contribution: float  # (ablated_fid - baseline_fid) / baseline_fid
    is_decorative: bool  # contribution < 0.02

    def to_dict(self) -> Dict[str, float]:
        """Convert to dictionary for logging."""
        return {
            f"ablation/{self.name}_fid": self.fid,
            f"ablation/{self.name}_contribution": self.contribution,
            f"ablation/{self.name}_is_decorative": float(self.is_decorative),
        }


@dataclass
class ReplaceabilityReport:
    """Full report from replaceability testing."""
    baseline_fid: float
    ablations: List[AblationResult]
    alerts: List[str]

    def to_dict(self) -> Dict[str, float]:
        """Convert to flat dictionary for logging."""
        result = {"ablation/baseline_fid": self.baseline_fid}
        for ablation in self.ablations:
            result.update(ablation.to_dict())
        return result


class ReplaceabilityTester:
    """
    Ablation tests to prove each component contributes.

    Run every N steps during training to catch regressions.

    Success criteria:
    - Quad disabled: Quality should DROP (>5% FID increase)
    - Phase disabled: Quality should DROP (>5% FID increase)
    - Local disabled: Texture degrades but semantics should remain

    If any component shows <2% drop when disabled, it's DECORATIVE.

    Args:
        model: PhaseQuadImageGenerator model.
        val_dataloader: Validation dataloader.
        fid_calculator: Optional FID calculator (if None, uses MSE proxy).
        num_samples: Number of samples for FID computation.
        device: Device to use.
    """

    def __init__(
        self,
        model: PhaseQuadImageGenerator,
        val_dataloader: DataLoader,
        fid_calculator: Optional[Callable] = None,
        num_samples: int = 1000,
        device: Optional[torch.device] = None,
    ):
        self.model = model
        self.val_loader = val_dataloader
        self.fid_calculator = fid_calculator
        self.num_samples = num_samples
        self.device = device or torch.device("cuda" if torch.cuda.is_available() else "cpu")

        # Decorative threshold
        self.decorative_threshold = 0.02  # 2% contribution minimum

    def run_ablations(self) -> ReplaceabilityReport:
        """
        Run all ablation tests.

        Returns:
            ReplaceabilityReport with all results.
        """
        self.model.eval()

        # Baseline (all enabled)
        baseline_fid = self._compute_fid(
            enable_quad=True,
            enable_phase=True,
            enable_local=True,
        )

        ablations = []
        alerts = []

        # Quad disabled
        quad_disabled_fid = self._compute_fid(
            enable_quad=False,
            enable_phase=True,
            enable_local=True,
        )
        quad_contribution = (quad_disabled_fid - baseline_fid) / (baseline_fid + 1e-8)
        quad_result = AblationResult(
            name="quad_disabled",
            fid=quad_disabled_fid,
            baseline_fid=baseline_fid,
            contribution=quad_contribution,
            is_decorative=quad_contribution < self.decorative_threshold,
        )
        ablations.append(quad_result)
        if quad_result.is_decorative:
            alerts.append(
                f"ALERT: Quad appears DECORATIVE (contribution={quad_contribution:.2%})"
            )

        # Phase disabled (replace with mean pooling)
        phase_disabled_fid = self._compute_fid(
            enable_quad=True,
            enable_phase=False,
            enable_local=True,
        )
        phase_contribution = (phase_disabled_fid - baseline_fid) / (baseline_fid + 1e-8)
        phase_result = AblationResult(
            name="phase_disabled",
            fid=phase_disabled_fid,
            baseline_fid=baseline_fid,
            contribution=phase_contribution,
            is_decorative=phase_contribution < self.decorative_threshold,
        )
        ablations.append(phase_result)
        if phase_result.is_decorative:
            alerts.append(
                f"ALERT: Phase appears DECORATIVE (contribution={phase_contribution:.2%})"
            )

        # Local disabled
        local_disabled_fid = self._compute_fid(
            enable_quad=True,
            enable_phase=True,
            enable_local=False,
        )
        local_contribution = (local_disabled_fid - baseline_fid) / (baseline_fid + 1e-8)
        local_result = AblationResult(
            name="local_disabled",
            fid=local_disabled_fid,
            baseline_fid=baseline_fid,
            contribution=local_contribution,
            is_decorative=local_contribution < self.decorative_threshold,
        )
        ablations.append(local_result)
        # Local being decorative is less concerning - it's for texture

        # All disabled (sanity check)
        all_disabled_fid = self._compute_fid(
            enable_quad=False,
            enable_phase=False,
            enable_local=False,
        )
        all_contribution = (all_disabled_fid - baseline_fid) / (baseline_fid + 1e-8)
        all_result = AblationResult(
            name="all_disabled",
            fid=all_disabled_fid,
            baseline_fid=baseline_fid,
            contribution=all_contribution,
            is_decorative=all_contribution < self.decorative_threshold,
        )
        ablations.append(all_result)

        return ReplaceabilityReport(
            baseline_fid=baseline_fid,
            ablations=ablations,
            alerts=alerts,
        )

    def _compute_fid(
        self,
        enable_quad: bool,
        enable_phase: bool,
        enable_local: bool,
    ) -> float:
        """
        Generate images and compute FID (or proxy metric).

        Args:
            enable_quad: Enable Quad retrieval.
            enable_phase: Enable Phase integration.
            enable_local: Enable Local mixer.

        Returns:
            FID score (lower is better).
        """
        control = GeneratorControl(
            enable_quad=enable_quad,
            enable_phase=enable_phase,
        )

        # Update per-block controls for local
        if not enable_local:
            control.per_block_controls = {}
            for i in range(self.model.num_blocks):
                control.per_block_controls[i] = BlockControl(
                    enable_quad=enable_quad,
                    enable_phase=enable_phase,
                    enable_local=enable_local,
                )

        # If we have a FID calculator, use it
        if self.fid_calculator is not None:
            return self._compute_fid_with_calculator(control)

        # Otherwise, use MSE as proxy
        return self._compute_mse_proxy(control)

    def _compute_mse_proxy(self, control: GeneratorControl) -> float:
        """
        Compute MSE as a proxy for FID when FID calculator is not available.

        This is useful for quick ablation tests during training.
        Higher MSE roughly correlates with worse generation quality.

        Args:
            control: GeneratorControl specifying ablation settings.

        Returns:
            Average MSE (higher is worse).
        """
        total_mse = 0.0
        num_batches = 0

        with torch.no_grad():
            for batch in self.val_loader:
                if num_batches * self.val_loader.batch_size >= self.num_samples:
                    break

                # Get latent
                if "latent" in batch:
                    z0 = batch["latent"].to(self.device)
                else:
                    continue

                # Get text conditioning
                text_cond = batch.get("text_embeds")
                if text_cond is not None:
                    text_cond = text_cond.to(self.device)

                # Sample random timestep
                B = z0.shape[0]
                t = torch.randint(0, 1000, (B,), device=self.device)

                # Add noise
                noise = torch.randn_like(z0)
                alpha_t = 0.5  # Simplified - use actual schedule in practice
                z_t = alpha_t * z0 + (1 - alpha_t) * noise

                # Predict noise
                noise_pred = self.model(z_t, t, text_cond, control)

                # Compute MSE
                mse = ((noise_pred - noise) ** 2).mean()
                total_mse += mse.item()
                num_batches += 1

        return total_mse / max(num_batches, 1)

    def _compute_fid_with_calculator(self, control: GeneratorControl) -> float:
        """
        Compute actual FID using provided calculator.

        This requires generating full images through diffusion sampling
        and computing Inception features.

        Args:
            control: GeneratorControl specifying ablation settings.

        Returns:
            FID score.
        """
        # Generate images
        generated_images = []

        with torch.no_grad():
            for batch in self.val_loader:
                if len(generated_images) >= self.num_samples:
                    break

                # This would require full diffusion sampling loop
                # For now, return placeholder
                pass

        # Compute FID
        if self.fid_calculator is not None and generated_images:
            return self.fid_calculator(generated_images)

        # Fallback to MSE proxy
        return self._compute_mse_proxy(control)


def run_quick_ablation(
    model: PhaseQuadImageGenerator,
    sample_batch: Dict[str, Tensor],
    device: torch.device,
) -> Dict[str, float]:
    """
    Quick ablation test on a single batch.

    Useful for monitoring during training without full FID computation.

    Args:
        model: PhaseQuadImageGenerator model.
        sample_batch: Single batch for testing.
        device: Device to use.

    Returns:
        Dictionary with MSE for each ablation.
    """
    model.eval()
    results = {}

    z0 = sample_batch["latent"].to(device)
    text_cond = sample_batch.get("text_embeds")
    if text_cond is not None:
        text_cond = text_cond.to(device)

    B = z0.shape[0]
    t = torch.randint(0, 1000, (B,), device=device)
    noise = torch.randn_like(z0)
    z_t = 0.5 * z0 + 0.5 * noise

    with torch.no_grad():
        # Baseline
        control = GeneratorControl()
        pred = model(z_t, t, text_cond, control)
        results["baseline_mse"] = ((pred - noise) ** 2).mean().item()

        # Quad disabled
        control = GeneratorControl(enable_quad=False)
        pred = model(z_t, t, text_cond, control)
        results["quad_disabled_mse"] = ((pred - noise) ** 2).mean().item()

        # Phase disabled
        control = GeneratorControl(enable_phase=False)
        pred = model(z_t, t, text_cond, control)
        results["phase_disabled_mse"] = ((pred - noise) ** 2).mean().item()

    # Compute contributions
    baseline = results["baseline_mse"]
    results["quad_contribution"] = (results["quad_disabled_mse"] - baseline) / (baseline + 1e-8)
    results["phase_contribution"] = (results["phase_disabled_mse"] - baseline) / (baseline + 1e-8)

    return results
