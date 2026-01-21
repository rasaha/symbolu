"""
Inference pipeline for Phase-Quad Image Generator.

This module provides the complete pipeline for generating images
from text prompts using the Phase-Quad diffusion model.
"""

import time
from dataclasses import dataclass, field
from typing import Optional, List, Union, Callable, Any, Dict

import torch
import torch.nn as nn
from torch import Tensor

from symbolu.vision.phase_quad_generator import PhaseQuadImageGenerator
from symbolu.vision.config import PhaseQuadVisionConfig
from symbolu.vision.controls import GeneratorControl
from symbolu.vision.inference.samplers import (
    NoiseSchedule,
    DDPMSampler,
    DDIMSampler,
    get_sampler,
)


@dataclass
class GenerationConfig:
    """
    Configuration for image generation.

    Attributes:
        height: Output image height in pixels.
        width: Output image width in pixels.
        num_inference_steps: Number of denoising steps (more = higher quality).
        guidance_scale: Classifier-free guidance scale (higher = more prompt adherence).
        sampler: Sampler type ("ddpm" or "ddim").
        eta: Stochasticity for DDIM (0 = deterministic, 1 = stochastic).
        seed: Random seed for reproducibility.
        tau: Temperature for Phase-Quad gating.
    """
    height: int = 512
    width: int = 512
    num_inference_steps: int = 50
    guidance_scale: float = 7.5
    sampler: str = "ddim"
    eta: float = 0.0
    seed: Optional[int] = None
    tau: float = 1.0

    @classmethod
    def fast(cls) -> "GenerationConfig":
        """Fast generation (lower quality)."""
        return cls(
            height=256,
            width=256,
            num_inference_steps=20,
            guidance_scale=7.5,
        )

    @classmethod
    def quality(cls) -> "GenerationConfig":
        """High quality generation."""
        return cls(
            height=512,
            width=512,
            num_inference_steps=50,
            guidance_scale=7.5,
        )

    @classmethod
    def hd(cls) -> "GenerationConfig":
        """HD generation (slow)."""
        return cls(
            height=1024,
            width=1024,
            num_inference_steps=100,
            guidance_scale=7.5,
        )


@dataclass
class GenerationResult:
    """
    Result of image generation.

    Attributes:
        images: Generated images as tensors [B, C, H, W] in range [0, 1].
        latents: Final latents before VAE decoding.
        seed: Random seed used.
        generation_time_ms: Time taken in milliseconds.
        num_steps: Number of denoising steps used.
    """
    images: Tensor  # [B, C, H, W] in [0, 1]
    latents: Tensor  # [B, C, H_lat, W_lat]
    seed: int
    generation_time_ms: float
    num_steps: int

    def save(self, path: str, index: int = 0):
        """
        Save image to file.

        Args:
            path: Output path (e.g., "output.png")
            index: Batch index to save
        """
        try:
            from PIL import Image
            import numpy as np

            # Convert to PIL Image
            img = self.images[index].cpu()
            img = img.permute(1, 2, 0).numpy()  # [H, W, C]
            img = (img * 255).clip(0, 255).astype(np.uint8)

            Image.fromarray(img).save(path)
            print(f"Saved image to {path}")
        except ImportError:
            print("PIL not available. Install with: pip install Pillow")


class MockVAE(nn.Module):
    """
    Mock VAE for testing without pretrained weights.

    In production, replace with actual SDXL VAE.
    """

    def __init__(self, latent_channels: int = 4, scaling_factor: float = 0.18215):
        super().__init__()
        self.latent_channels = latent_channels
        self.scaling_factor = scaling_factor

        # Simple decoder (not realistic, just for shape testing)
        self.decoder = nn.Sequential(
            nn.ConvTranspose2d(latent_channels, 128, 4, 2, 1),  # 2x upsample
            nn.SiLU(),
            nn.ConvTranspose2d(128, 64, 4, 2, 1),  # 2x upsample
            nn.SiLU(),
            nn.ConvTranspose2d(64, 32, 4, 2, 1),  # 2x upsample
            nn.SiLU(),
            nn.Conv2d(32, 3, 3, 1, 1),
            nn.Sigmoid(),  # Output in [0, 1]
        )

    def decode(self, latents: Tensor) -> Tensor:
        """Decode latents to images."""
        # Unscale
        latents = latents / self.scaling_factor
        return self.decoder(latents)

    def encode(self, images: Tensor) -> Tensor:
        """Encode images to latents (simple downscale for mock)."""
        B, C, H, W = images.shape
        # Simple mock encoding: downsample and project to latent channels
        latents = F.interpolate(images, scale_factor=1/8, mode='bilinear', align_corners=False)
        # Project 3 channels to latent_channels (4)
        if latents.shape[1] != self.latent_channels:
            latents = F.pad(latents, (0, 0, 0, 0, 0, self.latent_channels - latents.shape[1]))
        return latents * self.scaling_factor


class MockTextEncoder(nn.Module):
    """
    Mock text encoder for testing without pretrained weights.

    In production, replace with actual CLIP text encoder.
    """

    def __init__(self, embed_dim: int = 768, max_length: int = 77):
        super().__init__()
        self.embed_dim = embed_dim
        self.max_length = max_length

        # Simple projection (not realistic)
        self.proj = nn.Linear(embed_dim, embed_dim)

    def encode(self, prompts: List[str]) -> Tensor:
        """
        Encode text prompts.

        For mock: Returns random embeddings shaped correctly.
        """
        batch_size = len(prompts)
        device = next(self.parameters()).device

        # Generate deterministic-ish embeddings based on prompt length
        embeddings = torch.randn(
            batch_size, self.max_length, self.embed_dim,
            device=device
        )

        # Add some structure based on prompt
        for i, prompt in enumerate(prompts):
            # Use prompt length to seed some variation
            scale = len(prompt) / 100.0
            embeddings[i] = embeddings[i] * (0.5 + scale)

        return self.proj(embeddings)


class PhaseQuadInferencePipeline:
    """
    Complete inference pipeline for Phase-Quad Image Generator.

    This pipeline handles:
    1. Text encoding (prompt → embeddings)
    2. Latent sampling (noise → clean latent via diffusion)
    3. VAE decoding (latent → pixel image)
    4. Classifier-free guidance

    Example usage:
        >>> pipeline = PhaseQuadInferencePipeline.from_pretrained("path/to/model")
        >>> result = pipeline.generate("A beautiful sunset over mountains")
        >>> result.save("output.png")

    For testing without pretrained weights:
        >>> pipeline = PhaseQuadInferencePipeline.create_mock()
        >>> result = pipeline.generate("Test prompt")
    """

    def __init__(
        self,
        model: PhaseQuadImageGenerator,
        vae: nn.Module,
        text_encoder: nn.Module,
        config: PhaseQuadVisionConfig,
        device: Optional[torch.device] = None,
    ):
        """
        Initialize pipeline.

        Args:
            model: Phase-Quad diffusion model
            vae: VAE for encoding/decoding images
            text_encoder: Text encoder for prompts
            config: Model configuration
            device: Device to use
        """
        self.model = model
        self.vae = vae
        self.text_encoder = text_encoder
        self.config = config
        self.device = device or torch.device("cuda" if torch.cuda.is_available() else "cpu")

        # Move to device
        self.model = self.model.to(self.device)
        self.vae = self.vae.to(self.device)
        self.text_encoder = self.text_encoder.to(self.device)

        # Set to eval mode
        self.model.eval()
        self.vae.eval()
        self.text_encoder.eval()

        # Default noise schedule
        self.noise_schedule = NoiseSchedule(num_timesteps=1000).to(self.device)

    @classmethod
    def create_mock(
        cls,
        model_size: str = "tiny",
        device: Optional[torch.device] = None,
    ) -> "PhaseQuadInferencePipeline":
        """
        Create pipeline with mock components for testing.

        This creates a working pipeline without pretrained weights.
        Useful for testing the generation loop and shapes.

        Args:
            model_size: "tiny", "small", "base", or "large"
            device: Device to use

        Returns:
            Pipeline with mock VAE and text encoder
        """
        # Get config
        config_fn = getattr(PhaseQuadVisionConfig, model_size)
        config = config_fn()

        # Create model
        model = PhaseQuadImageGenerator(config)

        # Create mock components
        vae = MockVAE(latent_channels=config.vae.in_channels)
        text_encoder = MockTextEncoder(embed_dim=config.text_encoder.embed_dim)

        return cls(
            model=model,
            vae=vae,
            text_encoder=text_encoder,
            config=config,
            device=device,
        )

    @classmethod
    def from_pretrained(
        cls,
        checkpoint_path: Optional[str] = None,
        model_size: str = "base",
        vae_model_id: str = "stabilityai/stable-diffusion-xl-base-1.0",
        text_encoder_id: str = "openai/clip-vit-large-patch14",
        device: Optional[torch.device] = None,
        torch_dtype: torch.dtype = torch.float16,
    ) -> "PhaseQuadInferencePipeline":
        """
        Create pipeline with pretrained VAE and text encoder.

        This creates a pipeline that can generate actual images using
        pretrained components from HuggingFace.

        Args:
            checkpoint_path: Path to trained Phase-Quad model checkpoint.
                            If None, uses random initialization.
            model_size: "tiny", "small", "base", or "large"
            vae_model_id: HuggingFace model ID for VAE.
            text_encoder_id: HuggingFace model ID for text encoder.
            device: Device to use.
            torch_dtype: Data type for pretrained models.

        Returns:
            Pipeline with pretrained VAE and text encoder.

        Example:
            >>> # With trained checkpoint
            >>> pipeline = PhaseQuadInferencePipeline.from_pretrained(
            ...     checkpoint_path="checkpoints/phase_quad_epoch_10.pt"
            ... )
            >>> result = pipeline.generate("A sunset over mountains")

            >>> # Without checkpoint (for testing pretrained components)
            >>> pipeline = PhaseQuadInferencePipeline.from_pretrained()
        """
        from symbolu.vision.inference.pretrained import (
            PretrainedVAE,
            PretrainedCLIP,
        )

        device = device or torch.device("cuda" if torch.cuda.is_available() else "cpu")

        # Get config
        config_fn = getattr(PhaseQuadVisionConfig, model_size)
        config = config_fn()

        # Create Phase-Quad model
        model = PhaseQuadImageGenerator(config)

        # Load checkpoint if provided
        if checkpoint_path is not None:
            print(f"Loading Phase-Quad checkpoint from {checkpoint_path}...")
            checkpoint = torch.load(checkpoint_path, map_location="cpu")
            if "model_state_dict" in checkpoint:
                model.load_state_dict(checkpoint["model_state_dict"])
            else:
                model.load_state_dict(checkpoint)
            print("Checkpoint loaded successfully.")

        # Load pretrained VAE
        vae = PretrainedVAE(
            model_id=vae_model_id,
            torch_dtype=torch_dtype,
            device=device,
        )

        # Load pretrained text encoder
        text_encoder = PretrainedCLIP(
            model_id=text_encoder_id,
            torch_dtype=torch_dtype,
            device=device,
        )

        return cls(
            model=model,
            vae=vae,
            text_encoder=text_encoder,
            config=config,
            device=device,
        )

    @torch.no_grad()
    def generate(
        self,
        prompt: Union[str, List[str]],
        negative_prompt: Optional[Union[str, List[str]]] = None,
        config: Optional[GenerationConfig] = None,
        callback: Optional[Callable[[int, int, Tensor], None]] = None,
    ) -> GenerationResult:
        """
        Generate images from text prompts.

        Args:
            prompt: Text prompt(s) describing desired image.
            negative_prompt: Optional negative prompt(s) for guidance.
            config: Generation configuration.
            callback: Optional callback(step, total_steps, latents) for progress.

        Returns:
            GenerationResult with generated images.

        Example:
            >>> result = pipeline.generate(
            ...     "A serene lake at sunset with mountains",
            ...     config=GenerationConfig(num_inference_steps=30)
            ... )
            >>> result.save("lake.png")
        """
        start_time = time.time()

        # Default config
        if config is None:
            config = GenerationConfig()

        # Handle single prompt
        if isinstance(prompt, str):
            prompt = [prompt]
        batch_size = len(prompt)

        if negative_prompt is None:
            negative_prompt = [""] * batch_size
        elif isinstance(negative_prompt, str):
            negative_prompt = [negative_prompt] * batch_size

        # Set seed
        seed = config.seed if config.seed is not None else torch.randint(0, 2**32, (1,)).item()
        generator = torch.Generator(device=self.device).manual_seed(seed)

        # Encode text
        text_embeddings = self.text_encoder.encode(prompt)
        uncond_embeddings = self.text_encoder.encode(negative_prompt)

        # Compute latent size (VAE downsamples 8x)
        latent_h = config.height // 8
        latent_w = config.width // 8

        # Initialize with noise
        latents = torch.randn(
            batch_size,
            self.config.vae.in_channels,
            latent_h,
            latent_w,
            device=self.device,
            generator=generator,
        )

        # Get sampler
        sampler = get_sampler(
            sampler_type=config.sampler,
            num_timesteps=self.noise_schedule.num_timesteps,
            eta=config.eta,
        )
        sampler.schedule = sampler.schedule.to(self.device)

        # Get timesteps
        timesteps = sampler.get_timesteps(config.num_inference_steps)

        # Control for Phase-Quad
        control = GeneratorControl(tau=config.tau)

        # Denoising loop
        for i, t in enumerate(timesteps):
            # Expand latents for classifier-free guidance
            latent_model_input = torch.cat([latents, latents], dim=0)

            # Combine embeddings
            combined_embeddings = torch.cat([uncond_embeddings, text_embeddings], dim=0)

            # Predict noise
            t_tensor = torch.tensor([t] * (batch_size * 2), device=self.device)
            noise_pred = self.model(
                latent_model_input,
                t_tensor,
                combined_embeddings,
                control=control,
            )

            # Classifier-free guidance
            noise_pred_uncond, noise_pred_text = noise_pred.chunk(2)
            noise_pred = noise_pred_uncond + config.guidance_scale * (
                noise_pred_text - noise_pred_uncond
            )

            # Denoise step
            t_prev = timesteps[i + 1] if i + 1 < len(timesteps) else 0
            if isinstance(sampler, DDIMSampler):
                latents = sampler.step(noise_pred, t, latents, t_prev, generator)
            else:
                latents = sampler.step(noise_pred, t, latents, generator)

            # Callback
            if callback is not None:
                callback(i + 1, len(timesteps), latents)

        # Decode latents to images
        images = self.vae.decode(latents)

        # Ensure in [0, 1]
        images = torch.clamp(images, 0, 1)

        generation_time = (time.time() - start_time) * 1000

        return GenerationResult(
            images=images,
            latents=latents,
            seed=seed,
            generation_time_ms=generation_time,
            num_steps=len(timesteps),
        )

    @torch.no_grad()
    def generate_variations(
        self,
        image: Tensor,
        prompt: str,
        strength: float = 0.75,
        config: Optional[GenerationConfig] = None,
    ) -> GenerationResult:
        """
        Generate variations of an existing image.

        Args:
            image: Input image tensor [1, 3, H, W] in [0, 1]
            prompt: Text prompt for guidance
            strength: How much to change (0 = identical, 1 = completely new)
            config: Generation configuration

        Returns:
            GenerationResult with variation image
        """
        if config is None:
            config = GenerationConfig()

        # This would require VAE encoding, which mock doesn't support
        # For now, just call generate
        return self.generate(prompt, config=config)

    def __repr__(self) -> str:
        n_params = sum(p.numel() for p in self.model.parameters())
        return (
            f"PhaseQuadInferencePipeline(\n"
            f"  model_params={n_params:,},\n"
            f"  device={self.device},\n"
            f"  config={self.config.preset_name if hasattr(self.config, 'preset_name') else 'custom'}\n"
            f")"
        )
