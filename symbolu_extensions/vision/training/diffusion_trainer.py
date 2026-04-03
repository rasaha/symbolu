"""
PhaseQuadDiffusionTrainer: Training loop for Phase-Quad Image Generator.

Uses standard noise prediction (or v-prediction) loss.
Provides fair comparison against normal DiT/U-Net.
"""

from dataclasses import dataclass, field
from typing import Dict, Optional, Any, Callable

import torch
import torch.nn as nn
import torch.nn.functional as F
from torch import Tensor
from torch.optim import AdamW
from torch.optim.lr_scheduler import CosineAnnealingLR

from symbolu_extensions.vision.config import PhaseQuadVisionConfig, TrainingConfig
from symbolu_extensions.vision.controls import BlockControl, GeneratorControl
from symbolu_extensions.vision.phase_quad_generator import PhaseQuadImageGenerator
from symbolu_extensions.vision.training.temperature_schedule import (
    TemperatureSchedule,
    get_temperature_schedule,
)
from symbolu_extensions.vision.diagnostics import ModelDiagnostics


@dataclass
class TrainingStep:
    """Result of a single training step."""
    loss: float
    tau: float
    step: int
    diagnostics: Optional[Dict[str, float]] = None
    alerts: Optional[list] = None


class PhaseQuadDiffusionTrainer:
    """
    Training loop for Phase-Quad Image Generator.

    Uses standard noise prediction (or v-prediction) loss.
    Provides fair comparison against normal DiT/U-Net.

    Features:
    - Temperature scheduling for gate warming
    - Comprehensive diagnostics collection
    - Mixed precision support
    - Gradient checkpointing option

    Args:
        model: PhaseQuadImageGenerator model.
        config: TrainingConfig with hyperparameters.
        vae: Optional VAE for encoding images (can be None for latent-only training).
        text_encoder: Optional text encoder (can be None for unconditional training).
    """

    def __init__(
        self,
        model: PhaseQuadImageGenerator,
        config: TrainingConfig,
        vae: Optional[nn.Module] = None,
        text_encoder: Optional[nn.Module] = None,
        device: Optional[torch.device] = None,
    ):
        self.model = model
        self.config = config
        self.vae = vae
        self.text_encoder = text_encoder
        self.device = device or torch.device("cuda" if torch.cuda.is_available() else "cpu")

        # Move model to device
        self.model = self.model.to(self.device)
        if self.vae is not None:
            self.vae = self.vae.to(self.device)
            self.vae.eval()  # VAE is frozen
        if self.text_encoder is not None:
            self.text_encoder = self.text_encoder.to(self.device)
            self.text_encoder.eval()  # Text encoder is frozen

        # Temperature schedule for gating
        self.tau_schedule = get_temperature_schedule(
            config.temperature.schedule_type,
            config.temperature.start,
            config.temperature.end,
            config.temperature.warmup_steps,
        )

        # Optimizer
        self.optimizer = AdamW(
            self.model.parameters(),
            lr=config.learning_rate,
            weight_decay=config.weight_decay,
        )

        # Learning rate scheduler
        self.scheduler = CosineAnnealingLR(
            self.optimizer,
            T_max=config.max_steps,
            eta_min=config.learning_rate * 0.1,
        )

        # Mixed precision scaler
        self.scaler = torch.cuda.amp.GradScaler() if config.mixed_precision else None

        # Noise schedule parameters (linear beta schedule)
        self.num_train_timesteps = config.diffusion.num_train_timesteps
        self.prediction_type = config.diffusion.prediction_type

        # Precompute noise schedule
        betas = torch.linspace(
            config.diffusion.beta_start,
            config.diffusion.beta_end,
            self.num_train_timesteps,
            device=self.device,
        )
        alphas = 1.0 - betas
        self.alphas_cumprod = torch.cumprod(alphas, dim=0)

        # Training state
        self.global_step = 0

    def training_step(
        self,
        batch: Dict[str, Any],
        collect_diagnostics: bool = False,
    ) -> TrainingStep:
        """
        Perform one training step.

        Args:
            batch: Contains 'latent' (or 'image') and optionally 'text_embeds' (or 'prompt').
            collect_diagnostics: If True, collect full diagnostics (slower).

        Returns:
            TrainingStep with loss and metrics.
        """
        self.model.train()
        self.optimizer.zero_grad()

        # Get latent (encode if necessary)
        if "latent" in batch:
            z0 = batch["latent"].to(self.device)
        elif "image" in batch and self.vae is not None:
            with torch.no_grad():
                z0 = self.vae.encode(batch["image"].to(self.device)).latent_dist.sample()
                z0 = z0 * 0.18215  # SD scaling factor
        else:
            raise ValueError("Batch must contain 'latent' or 'image' with VAE")

        # Get text conditioning
        text_cond = None
        if "text_embeds" in batch:
            text_cond = batch["text_embeds"].to(self.device)
        elif "prompt" in batch and self.text_encoder is not None:
            with torch.no_grad():
                text_cond = self.text_encoder(batch["prompt"]).last_hidden_state

        # Sample timestep and noise
        B = z0.shape[0]
        t = torch.randint(
            0, self.num_train_timesteps, (B,),
            device=self.device,
        )
        noise = torch.randn_like(z0)

        # Corrupt latent (add noise)
        sqrt_alpha = self.alphas_cumprod[t].sqrt().view(B, 1, 1, 1)
        sqrt_one_minus_alpha = (1 - self.alphas_cumprod[t]).sqrt().view(B, 1, 1, 1)
        z_t = sqrt_alpha * z0 + sqrt_one_minus_alpha * noise

        # Get temperature for this step
        tau = self.tau_schedule(self.global_step)
        control = GeneratorControl(tau=tau)

        # Forward pass
        if self.scaler is not None:
            with torch.cuda.amp.autocast():
                if collect_diagnostics:
                    noise_pred, diagnostics = self.model.forward_with_diagnostics(
                        z_t, t, text_cond, control
                    )
                else:
                    noise_pred = self.model(z_t, t, text_cond, control)
                    diagnostics = None

                # Compute loss
                if self.prediction_type == "epsilon":
                    target = noise
                elif self.prediction_type == "v_prediction":
                    target = sqrt_alpha.squeeze() * noise - sqrt_one_minus_alpha.squeeze() * z0
                else:
                    raise ValueError(f"Unknown prediction type: {self.prediction_type}")

                loss = F.mse_loss(noise_pred, target)

            # Backward pass with scaling
            self.scaler.scale(loss).backward()
            self.scaler.unscale_(self.optimizer)
            torch.nn.utils.clip_grad_norm_(self.model.parameters(), self.config.gradient_clip)
            self.scaler.step(self.optimizer)
            self.scaler.update()
        else:
            if collect_diagnostics:
                noise_pred, diagnostics = self.model.forward_with_diagnostics(
                    z_t, t, text_cond, control
                )
            else:
                noise_pred = self.model(z_t, t, text_cond, control)
                diagnostics = None

            # Compute loss
            if self.prediction_type == "epsilon":
                target = noise
            elif self.prediction_type == "v_prediction":
                target = sqrt_alpha.squeeze() * noise - sqrt_one_minus_alpha.squeeze() * z0
            else:
                raise ValueError(f"Unknown prediction type: {self.prediction_type}")

            loss = F.mse_loss(noise_pred, target)

            # Backward pass
            loss.backward()
            torch.nn.utils.clip_grad_norm_(self.model.parameters(), self.config.gradient_clip)
            self.optimizer.step()

        # Update scheduler
        self.scheduler.step()

        # Increment step
        self.global_step += 1

        # Prepare result
        result = TrainingStep(
            loss=loss.item(),
            tau=tau,
            step=self.global_step,
        )

        if diagnostics is not None:
            result.diagnostics = diagnostics.to_dict()
            result.alerts = diagnostics.get_all_alerts()

        return result

    def get_state_dict(self) -> Dict[str, Any]:
        """Get trainer state for checkpointing."""
        return {
            "model": self.model.state_dict(),
            "optimizer": self.optimizer.state_dict(),
            "scheduler": self.scheduler.state_dict(),
            "global_step": self.global_step,
            "scaler": self.scaler.state_dict() if self.scaler else None,
        }

    def load_state_dict(self, state: Dict[str, Any]) -> None:
        """Load trainer state from checkpoint."""
        self.model.load_state_dict(state["model"])
        self.optimizer.load_state_dict(state["optimizer"])
        self.scheduler.load_state_dict(state["scheduler"])
        self.global_step = state["global_step"]
        if self.scaler and state.get("scaler"):
            self.scaler.load_state_dict(state["scaler"])


def create_trainer(
    config: PhaseQuadVisionConfig,
    vae: Optional[nn.Module] = None,
    text_encoder: Optional[nn.Module] = None,
    device: Optional[torch.device] = None,
) -> PhaseQuadDiffusionTrainer:
    """
    Factory function to create trainer from config.

    Args:
        config: PhaseQuadVisionConfig.
        vae: Optional VAE model.
        text_encoder: Optional text encoder.
        device: Device to use.

    Returns:
        Configured PhaseQuadDiffusionTrainer.
    """
    model = PhaseQuadImageGenerator(config)
    return PhaseQuadDiffusionTrainer(
        model=model,
        config=config.training,
        vae=vae,
        text_encoder=text_encoder,
        device=device,
    )
