"""
Diffusion samplers for Phase-Quad Image Generator.

Implements DDPM and DDIM sampling strategies for converting
noise to clean latents through iterative denoising.
"""

import math
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional, Callable, List

import torch
import torch.nn as nn
from torch import Tensor


@dataclass
class NoiseSchedule:
    """
    Noise schedule parameters for diffusion.

    Uses the standard linear beta schedule from DDPM.
    """
    num_timesteps: int = 1000
    beta_start: float = 0.0001
    beta_end: float = 0.02

    def __post_init__(self):
        """Compute schedule parameters."""
        # Linear beta schedule
        self.betas = torch.linspace(self.beta_start, self.beta_end, self.num_timesteps)

        # Alpha parameters
        self.alphas = 1.0 - self.betas
        self.alphas_cumprod = torch.cumprod(self.alphas, dim=0)
        self.alphas_cumprod_prev = torch.cat([
            torch.tensor([1.0]), self.alphas_cumprod[:-1]
        ])

        # For adding noise
        self.sqrt_alphas_cumprod = torch.sqrt(self.alphas_cumprod)
        self.sqrt_one_minus_alphas_cumprod = torch.sqrt(1.0 - self.alphas_cumprod)

        # For removing noise
        self.sqrt_recip_alphas_cumprod = torch.sqrt(1.0 / self.alphas_cumprod)
        self.sqrt_recipm1_alphas_cumprod = torch.sqrt(1.0 / self.alphas_cumprod - 1)

        # Posterior variance
        self.posterior_variance = (
            self.betas * (1.0 - self.alphas_cumprod_prev) / (1.0 - self.alphas_cumprod)
        )

    def to(self, device: torch.device) -> "NoiseSchedule":
        """Move schedule tensors to device."""
        self.betas = self.betas.to(device)
        self.alphas = self.alphas.to(device)
        self.alphas_cumprod = self.alphas_cumprod.to(device)
        self.alphas_cumprod_prev = self.alphas_cumprod_prev.to(device)
        self.sqrt_alphas_cumprod = self.sqrt_alphas_cumprod.to(device)
        self.sqrt_one_minus_alphas_cumprod = self.sqrt_one_minus_alphas_cumprod.to(device)
        self.sqrt_recip_alphas_cumprod = self.sqrt_recip_alphas_cumprod.to(device)
        self.sqrt_recipm1_alphas_cumprod = self.sqrt_recipm1_alphas_cumprod.to(device)
        self.posterior_variance = self.posterior_variance.to(device)
        return self

    def add_noise(self, x0: Tensor, noise: Tensor, t: Tensor) -> Tensor:
        """
        Add noise to clean sample at timestep t.

        q(x_t | x_0) = N(sqrt(alpha_cumprod_t) * x_0, (1 - alpha_cumprod_t) * I)

        Args:
            x0: Clean sample [B, C, H, W]
            noise: Gaussian noise [B, C, H, W]
            t: Timesteps [B]

        Returns:
            x_t: Noisy sample at timestep t
        """
        sqrt_alpha = self.sqrt_alphas_cumprod[t].view(-1, 1, 1, 1)
        sqrt_one_minus_alpha = self.sqrt_one_minus_alphas_cumprod[t].view(-1, 1, 1, 1)
        return sqrt_alpha * x0 + sqrt_one_minus_alpha * noise


class BaseSampler(ABC):
    """Base class for diffusion samplers."""

    def __init__(self, schedule: NoiseSchedule):
        self.schedule = schedule

    @abstractmethod
    def step(
        self,
        model_output: Tensor,
        t: int,
        x_t: Tensor,
        generator: Optional[torch.Generator] = None,
    ) -> Tensor:
        """
        Single denoising step.

        Args:
            model_output: Predicted noise from model
            t: Current timestep
            x_t: Current noisy sample
            generator: Optional random generator

        Returns:
            x_{t-1}: Less noisy sample
        """
        pass

    @abstractmethod
    def get_timesteps(self, num_steps: int) -> List[int]:
        """Get timesteps for sampling."""
        pass


class DDPMSampler(BaseSampler):
    """
    DDPM (Denoising Diffusion Probabilistic Models) sampler.

    Uses the full reverse diffusion process with stochastic sampling.
    Slower but higher quality.
    """

    def get_timesteps(self, num_steps: int) -> List[int]:
        """Get timesteps - uses all timesteps for DDPM."""
        # DDPM uses all timesteps
        step_size = self.schedule.num_timesteps // num_steps
        timesteps = list(range(0, self.schedule.num_timesteps, step_size))
        return list(reversed(timesteps))

    def step(
        self,
        model_output: Tensor,
        t: int,
        x_t: Tensor,
        generator: Optional[torch.Generator] = None,
    ) -> Tensor:
        """
        DDPM reverse diffusion step.

        p(x_{t-1} | x_t) = N(mu_theta(x_t, t), sigma_t^2 I)
        """
        device = x_t.device
        t_tensor = torch.tensor([t], device=device)

        # Get schedule values
        alpha = self.schedule.alphas[t]
        alpha_cumprod = self.schedule.alphas_cumprod[t]
        alpha_cumprod_prev = self.schedule.alphas_cumprod_prev[t]
        beta = self.schedule.betas[t]

        # Predict x_0 from x_t and noise prediction
        # x_0 = (x_t - sqrt(1 - alpha_cumprod) * noise) / sqrt(alpha_cumprod)
        pred_x0 = (
            self.schedule.sqrt_recip_alphas_cumprod[t] * x_t -
            self.schedule.sqrt_recipm1_alphas_cumprod[t] * model_output
        )

        # Clip predicted x_0
        pred_x0 = torch.clamp(pred_x0, -1, 1)

        # Compute mean
        # mu = (sqrt(alpha_cumprod_prev) * beta * x_0 + sqrt(alpha) * (1 - alpha_cumprod_prev) * x_t) / (1 - alpha_cumprod)
        coef1 = torch.sqrt(alpha_cumprod_prev) * beta / (1 - alpha_cumprod)
        coef2 = torch.sqrt(alpha) * (1 - alpha_cumprod_prev) / (1 - alpha_cumprod)
        mean = coef1 * pred_x0 + coef2 * x_t

        # Add noise (except for t=0)
        if t > 0:
            variance = self.schedule.posterior_variance[t]
            noise = torch.randn(x_t.shape, device=device, generator=generator)
            x_prev = mean + torch.sqrt(variance) * noise
        else:
            x_prev = mean

        return x_prev


class DDIMSampler(BaseSampler):
    """
    DDIM (Denoising Diffusion Implicit Models) sampler.

    Deterministic sampling with fewer steps. Faster inference.
    """

    def __init__(self, schedule: NoiseSchedule, eta: float = 0.0):
        """
        Args:
            schedule: Noise schedule
            eta: Stochasticity parameter (0 = deterministic, 1 = DDPM-like)
        """
        super().__init__(schedule)
        self.eta = eta

    def get_timesteps(self, num_steps: int) -> List[int]:
        """Get evenly spaced timesteps for DDIM."""
        step_size = self.schedule.num_timesteps // num_steps
        timesteps = list(range(0, self.schedule.num_timesteps, step_size))
        return list(reversed(timesteps))

    def step(
        self,
        model_output: Tensor,
        t: int,
        x_t: Tensor,
        t_prev: Optional[int] = None,
        generator: Optional[torch.Generator] = None,
    ) -> Tensor:
        """
        DDIM sampling step.

        Implements deterministic (or semi-deterministic) sampling.
        """
        device = x_t.device

        # Get alpha values
        alpha_cumprod_t = self.schedule.alphas_cumprod[t]

        if t_prev is None:
            t_prev = max(t - 1, 0)
        alpha_cumprod_prev = self.schedule.alphas_cumprod[t_prev] if t_prev >= 0 else torch.tensor(1.0)

        # Predict x_0
        pred_x0 = (
            self.schedule.sqrt_recip_alphas_cumprod[t] * x_t -
            self.schedule.sqrt_recipm1_alphas_cumprod[t] * model_output
        )

        # Clip
        pred_x0 = torch.clamp(pred_x0, -1, 1)

        # Compute variance
        sigma_t = self.eta * torch.sqrt(
            (1 - alpha_cumprod_prev) / (1 - alpha_cumprod_t) *
            (1 - alpha_cumprod_t / alpha_cumprod_prev)
        )

        # Direction pointing to x_t
        pred_dir = torch.sqrt(1 - alpha_cumprod_prev - sigma_t**2) * model_output

        # x_{t-1}
        x_prev = torch.sqrt(alpha_cumprod_prev) * pred_x0 + pred_dir

        # Add noise if eta > 0
        if self.eta > 0 and t > 0:
            noise = torch.randn(x_t.shape, device=device, generator=generator)
            x_prev = x_prev + sigma_t * noise

        return x_prev


def get_sampler(
    sampler_type: str = "ddim",
    num_timesteps: int = 1000,
    eta: float = 0.0,
) -> BaseSampler:
    """
    Get a sampler by name.

    Args:
        sampler_type: "ddpm" or "ddim"
        num_timesteps: Number of diffusion timesteps
        eta: Stochasticity for DDIM (0 = deterministic)

    Returns:
        Sampler instance
    """
    schedule = NoiseSchedule(num_timesteps=num_timesteps)

    if sampler_type.lower() == "ddpm":
        return DDPMSampler(schedule)
    elif sampler_type.lower() == "ddim":
        return DDIMSampler(schedule, eta=eta)
    else:
        raise ValueError(f"Unknown sampler type: {sampler_type}")
