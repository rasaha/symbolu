"""
Video VAE wrapper for Phase-Quad Video Generator.

This module provides wrappers for video VAE models that handle both
temporal and spatial compression. The primary supported VAE is CogVideoX.

Video VAE characteristics:
    - Temporal compression: T → T' (typically 4:1)
    - Spatial compression: H,W → H',W' (typically 8:1)
    - Latent channels: 4-16 depending on model

Example:
    >>> vae = PretrainedVideoVAE.from_pretrained("THUDM/CogVideoX-2b")
    >>> latents = vae.encode(video)  # [B, T, 3, H, W] -> [B, T', C, H', W']
    >>> decoded = vae.decode(latents)  # [B, T', C, H', W'] -> [B, T, 3, H, W]
"""

from typing import Optional, Union
from pathlib import Path

import torch
import torch.nn as nn
from torch import Tensor


class PretrainedVideoVAE(nn.Module):
    """
    Wrapper for video VAE models from HuggingFace diffusers.

    Supports CogVideoX VAE and similar video autoencoders.
    Handles temporal + spatial compression.

    Args:
        model_id: HuggingFace model ID or local path.
        subfolder: Subfolder within model (usually "vae").
        torch_dtype: Data type for model weights.
        device: Device to load model on.
    """

    def __init__(
        self,
        model_id: str = "THUDM/CogVideoX-2b",
        subfolder: str = "vae",
        torch_dtype: torch.dtype = torch.float32,
        device: Optional[torch.device] = None,
    ):
        super().__init__()

        self.model_id = model_id
        self.subfolder = subfolder
        self.torch_dtype = torch_dtype
        self.device = device or torch.device("cuda" if torch.cuda.is_available() else "cpu")

        # Lazy loading
        self._vae = None

        # CogVideoX VAE parameters (default)
        self.latent_channels = 16
        self.temporal_compression = 4  # T -> T/4
        self.spatial_compression = 8   # H,W -> H/8, W/8
        self.scaling_factor = 0.7  # CogVideoX specific

    def _load_vae(self):
        """Load VAE on first use."""
        if self._vae is not None:
            return

        try:
            from diffusers import AutoencoderKLCogVideoX

            print(f"Loading Video VAE from {self.model_id}...")
            self._vae = AutoencoderKLCogVideoX.from_pretrained(
                self.model_id,
                subfolder=self.subfolder,
                torch_dtype=self.torch_dtype,
            ).to(self.device)
            # Force float32 for numerical stability
            self._vae = self._vae.float()
            self._vae.eval()

            # Update parameters from loaded model if available
            if hasattr(self._vae.config, 'latent_channels'):
                self.latent_channels = self._vae.config.latent_channels
            if hasattr(self._vae.config, 'scaling_factor'):
                self.scaling_factor = self._vae.config.scaling_factor
            if hasattr(self._vae.config, 'temporal_compression_ratio'):
                self.temporal_compression = self._vae.config.temporal_compression_ratio

            print(f"Video VAE loaded: {self.latent_channels} channels, "
                  f"{self.temporal_compression}x temporal, {self.spatial_compression}x spatial")

        except ImportError:
            raise ImportError(
                "diffusers is required for video VAE. "
                "Install with: pip install diffusers>=0.25.0"
            )
        except Exception as e:
            print(f"Warning: Could not load CogVideoX VAE ({e})")
            print("Falling back to mock VAE for testing...")
            self._vae = MockVideoVAE(
                latent_channels=self.latent_channels,
                temporal_compression=self.temporal_compression,
                spatial_compression=self.spatial_compression,
            )

    @classmethod
    def from_pretrained(
        cls,
        model_id: str,
        subfolder: str = "vae",
        device: Optional[torch.device] = None,
    ) -> "PretrainedVideoVAE":
        """
        Load a pretrained video VAE.

        Args:
            model_id: HuggingFace model ID or local path.
            subfolder: Subfolder for VAE.
            device: Device to load on.

        Returns:
            PretrainedVideoVAE instance.
        """
        vae = cls(model_id=model_id, subfolder=subfolder, device=device)
        vae._load_vae()  # Eagerly load
        return vae

    @torch.no_grad()
    def encode(self, videos: Tensor) -> Tensor:
        """
        Encode videos to latents.

        Args:
            videos: [B, T, 3, H, W] or [B, 3, T, H, W] video frames in range [0, 1] or [-1, 1].
                   T = number of frames, H/W = spatial dimensions.

        Returns:
            latents: [B, T', C, H', W'] scaled video latents.
                    T' = T / temporal_compression
                    H' = H / spatial_compression
                    W' = W / spatial_compression
        """
        self._load_vae()

        # Handle both [B, T, 3, H, W] and [B, 3, T, H, W] formats
        if videos.dim() == 5 and videos.shape[2] == 3:
            # [B, T, 3, H, W] -> [B, 3, T, H, W]
            videos = videos.permute(0, 2, 1, 3, 4)

        # Normalize to [-1, 1] if needed
        if videos.min() >= 0:
            videos = videos * 2.0 - 1.0

        # Encode
        latent_dist = self._vae.encode(videos.to(self.torch_dtype)).latent_dist
        latents = latent_dist.sample()

        # Scale
        latents = latents * self.scaling_factor

        return latents

    @torch.no_grad()
    def decode(self, latents: Tensor) -> Tensor:
        """
        Decode latents to video frames.

        Args:
            latents: [B, C, T', H', W'] video latents.

        Returns:
            videos: [B, T, 3, H, W] video frames in range [0, 1].
                   T = T' * temporal_compression
        """
        self._load_vae()

        # Unscale
        latents = latents / self.scaling_factor

        # Decode (always use float32 for stability)
        decoded = self._vae.decode(latents.float()).sample

        # Convert to [0, 1]
        videos = (decoded + 1.0) / 2.0
        videos = torch.clamp(videos, 0, 1)

        # Convert from [B, 3, T, H, W] to [B, T, 3, H, W]
        videos = videos.permute(0, 2, 1, 3, 4)

        return videos.float()

    def get_latent_size(
        self,
        num_frames: int,
        height: int,
        width: int,
    ) -> tuple:
        """
        Calculate latent dimensions for given video size.

        Args:
            num_frames: Number of input frames.
            height: Input height.
            width: Input width.

        Returns:
            (T', C, H', W') latent dimensions.
        """
        t_latent = num_frames // self.temporal_compression
        h_latent = height // self.spatial_compression
        w_latent = width // self.spatial_compression
        return (t_latent, self.latent_channels, h_latent, w_latent)

    def forward(self, x: Tensor) -> Tensor:
        """Alias for decode."""
        return self.decode(x)


class MockVideoVAE(nn.Module):
    """
    Mock video VAE for testing without downloading pretrained weights.

    Performs simple pooling for encoding and interpolation for decoding.
    """

    def __init__(
        self,
        latent_channels: int = 16,
        temporal_compression: int = 4,
        spatial_compression: int = 8,
    ):
        super().__init__()
        self.latent_channels = latent_channels
        self.temporal_compression = temporal_compression
        self.spatial_compression = spatial_compression

        # Simple projection layers
        self.encode_proj = nn.Conv3d(3, latent_channels, kernel_size=1)
        self.decode_proj = nn.Conv3d(latent_channels, 3, kernel_size=1)

    def encode(self, videos: Tensor) -> "MockLatentDist":
        """Mock encode."""
        # [B, 3, T, H, W] -> [B, C, T', H', W']
        x = self.encode_proj(videos)
        x = nn.functional.avg_pool3d(
            x,
            kernel_size=(self.temporal_compression, self.spatial_compression, self.spatial_compression),
            stride=(self.temporal_compression, self.spatial_compression, self.spatial_compression),
        )
        return MockLatentDist(x)

    def decode(self, latents: Tensor) -> "MockDecoded":
        """Mock decode."""
        # [B, C, T', H', W'] -> [B, 3, T, H, W]
        x = nn.functional.interpolate(
            latents,
            scale_factor=(self.temporal_compression, self.spatial_compression, self.spatial_compression),
            mode='trilinear',
            align_corners=False,
        )
        x = self.decode_proj(x)
        return MockDecoded(x)


class MockLatentDist:
    """Mock latent distribution for compatibility."""
    def __init__(self, mean: Tensor):
        self.mean = mean

    def sample(self) -> Tensor:
        return self.mean


class MockDecoded:
    """Mock decoded output for compatibility."""
    def __init__(self, sample: Tensor):
        self.sample = sample


def load_video_vae(
    model_id: str = "THUDM/CogVideoX-2b",
    device: Optional[torch.device] = None,
) -> PretrainedVideoVAE:
    """
    Helper to load a pretrained video VAE.

    Args:
        model_id: HuggingFace model ID.
        device: Device to use.

    Returns:
        PretrainedVideoVAE instance.
    """
    return PretrainedVideoVAE(model_id=model_id, device=device)
