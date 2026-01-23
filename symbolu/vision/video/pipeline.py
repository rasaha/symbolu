"""
Inference pipeline for Phase-Quad Video Generator.

This module provides the complete pipeline for generating videos
from text prompts using the Phase-Quad diffusion model.

Example:
    >>> pipeline = PhaseQuadVideoPipeline.from_pretrained("checkpoint.pt")
    >>> result = pipeline.generate("A cat playing in the garden")
    >>> result.save("output.mp4")
"""

import time
from dataclasses import dataclass
from typing import Optional, List, Union, Callable
from pathlib import Path

import torch
import torch.nn as nn
from torch import Tensor

from symbolu.vision.video.generator import PhaseQuadVideoGenerator
from symbolu.vision.video.config import PhaseQuadVideoConfig
from symbolu.vision.video.vae import PretrainedVideoVAE, MockVideoVAE
from symbolu.vision.controls import (
    GeneratorControl,
    BlockControl,
    CreativityControl,
)
from symbolu.vision.inference.samplers import (
    NoiseSchedule,
    DDIMSampler,
    get_sampler,
)


@dataclass
class VideoGenerationConfig:
    """
    Configuration for video generation.

    Attributes:
        num_frames: Number of output video frames.
        height: Output video height in pixels.
        width: Output video width in pixels.
        num_inference_steps: Number of denoising steps.
        guidance_scale: Classifier-free guidance scale.
        fps: Output frames per second.
        eta: DDIM stochasticity (0 = deterministic).
        seed: Random seed for reproducibility.
        creativity: Creativity level [0.0, 1.0].
            - 0.0 = deterministic/stable
            - 0.5 = balanced
            - 1.0 = maximum creativity (more frame variation)
    """
    num_frames: int = 16
    height: int = 256
    width: int = 256
    num_inference_steps: int = 50
    guidance_scale: float = 7.5
    fps: int = 8
    eta: float = 0.0
    seed: Optional[int] = None
    creativity: float = 0.0

    @classmethod
    def fast(cls) -> "VideoGenerationConfig":
        """Fast generation (lower quality)."""
        return cls(
            num_frames=8,
            height=128,
            width=128,
            num_inference_steps=20,
        )

    @classmethod
    def quality(cls) -> "VideoGenerationConfig":
        """Standard quality generation."""
        return cls(
            num_frames=16,
            height=256,
            width=256,
            num_inference_steps=50,
        )

    @classmethod
    def hd(cls) -> "VideoGenerationConfig":
        """HD generation (slow)."""
        return cls(
            num_frames=32,
            height=480,
            width=720,
            num_inference_steps=100,
        )


@dataclass
class VideoGenerationResult:
    """
    Result of video generation.

    Attributes:
        frames: Generated video frames [B, T, C, H, W] in range [0, 1].
        latents: Final latents before VAE decoding.
        seed: Random seed used.
        generation_time_ms: Time taken in milliseconds.
        num_steps: Number of denoising steps.
        fps: Frames per second.
    """
    frames: Tensor  # [B, T, C, H, W] in [0, 1]
    latents: Tensor
    seed: int
    generation_time_ms: float
    num_steps: int
    fps: int

    def save(self, path: str, index: int = 0):
        """
        Save video to file.

        Args:
            path: Output path (e.g., "output.mp4" or "output.gif")
            index: Batch index to save
        """
        try:
            import numpy as np

            # Get frames for this batch item
            frames = self.frames[index].cpu()  # [T, C, H, W]
            frames = frames.permute(0, 2, 3, 1).numpy()  # [T, H, W, C]
            frames = (frames * 255).clip(0, 255).astype(np.uint8)

            path = Path(path)

            if path.suffix == ".gif":
                self._save_gif(frames, path)
            elif path.suffix in [".mp4", ".avi", ".mov"]:
                self._save_video(frames, path)
            else:
                # Default to MP4
                path = path.with_suffix(".mp4")
                self._save_video(frames, path)

            print(f"Saved video to {path}")

        except ImportError as e:
            print(f"Could not save video: {e}")
            print("Install with: pip install imageio imageio-ffmpeg")

    def _save_gif(self, frames, path: Path):
        """Save as GIF."""
        try:
            from PIL import Image
            imgs = [Image.fromarray(f) for f in frames]
            imgs[0].save(
                path,
                save_all=True,
                append_images=imgs[1:],
                duration=int(1000 / self.fps),
                loop=0,
            )
        except ImportError:
            import imageio
            imageio.mimsave(path, frames, fps=self.fps)

    def _save_video(self, frames, path: Path):
        """Save as video file."""
        import imageio
        writer = imageio.get_writer(path, fps=self.fps)
        for frame in frames:
            writer.append_data(frame)
        writer.close()

    def to_tensor(self) -> Tensor:
        """Get video frames as tensor."""
        return self.frames


class MockTextEncoder(nn.Module):
    """Mock text encoder for testing."""

    def __init__(self, embed_dim: int = 768, max_length: int = 77):
        super().__init__()
        self.embed_dim = embed_dim
        self.max_length = max_length
        self.proj = nn.Linear(embed_dim, embed_dim)

    def encode(self, prompts: List[str]) -> Tensor:
        batch_size = len(prompts)
        device = next(self.parameters()).device
        embeddings = torch.randn(batch_size, self.max_length, self.embed_dim, device=device)
        for i, prompt in enumerate(prompts):
            scale = len(prompt) / 100.0
            embeddings[i] = embeddings[i] * (0.5 + scale)
        return self.proj(embeddings)


class PhaseQuadVideoPipeline:
    """
    Complete inference pipeline for Phase-Quad Video Generator.

    This pipeline handles:
    1. Text encoding (prompt → embeddings)
    2. Latent sampling (noise → clean latent via diffusion)
    3. VideoVAE decoding (latent → video frames)
    4. Classifier-free guidance

    Example:
        >>> pipeline = PhaseQuadVideoPipeline.create_mock()
        >>> result = pipeline.generate("A sunset over the ocean")
        >>> result.save("sunset.mp4")
    """

    def __init__(
        self,
        model: PhaseQuadVideoGenerator,
        vae: nn.Module,
        text_encoder: nn.Module,
        config: PhaseQuadVideoConfig,
        device: Optional[torch.device] = None,
    ):
        self.model = model
        self.vae = vae
        self.text_encoder = text_encoder
        self.config = config
        self.device = device or torch.device("cuda" if torch.cuda.is_available() else "cpu")

        # Move to device
        self.model = self.model.to(self.device)
        self.vae = self.vae.to(self.device)
        self.text_encoder = self.text_encoder.to(self.device)

        # Set to eval
        self.model.eval()
        self.vae.eval()
        self.text_encoder.eval()

        # Noise schedule
        self.noise_schedule = NoiseSchedule(num_timesteps=1000).to(self.device)

    @classmethod
    def create_mock(
        cls,
        model_size: str = "tiny",
        device: Optional[torch.device] = None,
    ) -> "PhaseQuadVideoPipeline":
        """
        Create pipeline with mock components for testing.

        Args:
            model_size: "tiny", "small", or "base"
            device: Device to use

        Returns:
            Pipeline with mock VAE and text encoder
        """
        config_fn = getattr(PhaseQuadVideoConfig, model_size)
        config = config_fn()

        model = PhaseQuadVideoGenerator(config)
        vae = MockVideoVAE(
            latent_channels=config.vae.latent_channels,
            temporal_compression=config.vae.temporal_compression,
            spatial_compression=config.vae.spatial_compression,
        )
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
        model_size: str = "small",
        vae_model_id: str = "THUDM/CogVideoX-2b",
        device: Optional[torch.device] = None,
    ) -> "PhaseQuadVideoPipeline":
        """
        Create pipeline with pretrained components.

        Args:
            checkpoint_path: Path to trained model checkpoint.
            model_size: "tiny", "small", or "base"
            vae_model_id: HuggingFace model ID for video VAE.
            device: Device to use.

        Returns:
            Pipeline with pretrained VAE.
        """
        from symbolu.vision.inference.pretrained import PretrainedCLIP

        device = device or torch.device("cuda" if torch.cuda.is_available() else "cpu")

        config_fn = getattr(PhaseQuadVideoConfig, model_size)
        config = config_fn()

        model = PhaseQuadVideoGenerator(config)

        if checkpoint_path is not None:
            print(f"Loading checkpoint from {checkpoint_path}...")
            checkpoint = torch.load(checkpoint_path, map_location="cpu")
            if "model_state_dict" in checkpoint:
                model.load_state_dict(checkpoint["model_state_dict"])
            else:
                model.load_state_dict(checkpoint)
            print("Checkpoint loaded.")

        # Load video VAE
        try:
            vae = PretrainedVideoVAE.from_pretrained(vae_model_id, device=device)
        except Exception as e:
            print(f"Could not load video VAE: {e}")
            print("Using mock VAE instead.")
            vae = MockVideoVAE(
                latent_channels=config.vae.latent_channels,
                temporal_compression=config.vae.temporal_compression,
                spatial_compression=config.vae.spatial_compression,
            )

        # Load text encoder
        text_encoder = PretrainedCLIP(device=device)

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
        config: Optional[VideoGenerationConfig] = None,
        callback: Optional[Callable[[int, int, Tensor], None]] = None,
    ) -> VideoGenerationResult:
        """
        Generate videos from text prompts.

        Args:
            prompt: Text prompt(s) describing desired video.
            negative_prompt: Optional negative prompt(s).
            config: Generation configuration.
            callback: Optional callback(step, total, latents) for progress.

        Returns:
            VideoGenerationResult with generated video frames.
        """
        start_time = time.time()

        if config is None:
            config = VideoGenerationConfig()

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

        # Compute latent dimensions
        t_latent = config.num_frames // self.config.vae.temporal_compression
        h_latent = config.height // self.config.vae.spatial_compression
        w_latent = config.width // self.config.vae.spatial_compression

        # Initialize with noise
        init_sigma = getattr(self.vae, 'scaling_factor', 1.0)
        latents = torch.randn(
            batch_size,
            self.config.vae.latent_channels,
            t_latent,
            h_latent,
            w_latent,
            device=self.device,
            generator=generator,
        ) * init_sigma

        # Get sampler
        sampler = get_sampler("ddim", self.noise_schedule.num_timesteps, eta=config.eta)
        sampler.schedule = sampler.schedule.to(self.device)
        timesteps = sampler.get_timesteps(config.num_inference_steps)

        # Build control with creativity
        if config.creativity > 0.0:
            creativity = CreativityControl.from_level(config.creativity)
            per_block_controls = {}
            for i in range(self.config.num_blocks):
                per_block_controls[i] = BlockControl(
                    enable_quad=True,
                    enable_phase=True,
                    tau=creativity.tau,
                    phase_control=creativity.to_phase_control(),
                    quad_control=creativity.to_quad_control(),
                )
            control = GeneratorControl(
                tau=creativity.tau,
                per_block_controls=per_block_controls,
            )
        else:
            control = GeneratorControl()

        use_cfg = config.guidance_scale > 1.0

        # Denoising loop
        for i, t in enumerate(timesteps):
            if use_cfg:
                latent_input = torch.cat([latents, latents], dim=0)
                combined_embeddings = torch.cat([uncond_embeddings, text_embeddings], dim=0)
                t_tensor = torch.tensor([t] * (batch_size * 2), device=self.device)

                noise_pred = self.model(latent_input, t_tensor, combined_embeddings, control)

                noise_pred_uncond, noise_pred_text = noise_pred.chunk(2)
                noise_pred = noise_pred_uncond + config.guidance_scale * (
                    noise_pred_text - noise_pred_uncond
                )
            else:
                t_tensor = torch.tensor([t] * batch_size, device=self.device)
                noise_pred = self.model(latents, t_tensor, text_embeddings, control)

            # Denoise step
            t_prev = timesteps[i + 1] if i + 1 < len(timesteps) else 0
            latents = sampler.step(noise_pred, t, latents, t_prev, generator)

            if callback is not None:
                callback(i + 1, len(timesteps), latents)

        # Decode latents to video frames
        frames = self.vae.decode(latents)
        # Handle both raw tensor and wrapped outputs (e.g., MockDecoded)
        if hasattr(frames, 'sample'):
            frames = frames.sample
        frames = torch.clamp(frames, 0, 1)

        generation_time = (time.time() - start_time) * 1000

        return VideoGenerationResult(
            frames=frames,
            latents=latents,
            seed=seed,
            generation_time_ms=generation_time,
            num_steps=len(timesteps),
            fps=config.fps,
        )

    def __repr__(self) -> str:
        n_params = sum(p.numel() for p in self.model.parameters())
        return (
            f"PhaseQuadVideoPipeline(\n"
            f"  model_params={n_params:,},\n"
            f"  device={self.device},\n"
            f"  config={self.config.num_frames}f @ {self.config.height}x{self.config.width}\n"
            f")"
        )
