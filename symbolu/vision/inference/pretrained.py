"""
Pretrained component wrappers for Phase-Quad Image Generator.

This module provides wrappers for loading pretrained VAE and text encoders
from HuggingFace, enabling actual image generation (not just mock).

Requirements:
    pip install diffusers transformers accelerate safetensors
"""

from typing import Optional, List, Union
import torch
import torch.nn as nn
from torch import Tensor


class PretrainedVAE(nn.Module):
    """
    Wrapper for SDXL VAE from HuggingFace diffusers.

    The SDXL VAE encodes 512x512 images to 64x64 latents (8x downscale)
    with 4 channels.

    Args:
        model_id: HuggingFace model ID or local path.
        subfolder: Subfolder within model (usually "vae").
        torch_dtype: Data type for model weights.
        device: Device to load model on.
    """

    def __init__(
        self,
        model_id: str = "stabilityai/stable-diffusion-xl-base-1.0",
        subfolder: str = "vae",
        torch_dtype: torch.dtype = torch.float32,  # Use fp32 for stability
        device: Optional[torch.device] = None,
    ):
        super().__init__()

        self.model_id = model_id
        self.torch_dtype = torch_dtype
        self.device = device or torch.device("cuda" if torch.cuda.is_available() else "cpu")

        # Lazy loading - will load on first use
        self._vae = None
        self._subfolder = subfolder

        # SDXL VAE parameters
        self.latent_channels = 4
        self.scaling_factor = 0.13025  # SDXL specific

    def _load_vae(self):
        """Load VAE on first use."""
        if self._vae is not None:
            return

        try:
            from diffusers import AutoencoderKL

            print(f"Loading VAE from {self.model_id}...")
            self._vae = AutoencoderKL.from_pretrained(
                self.model_id,
                subfolder=self._subfolder,
                torch_dtype=self.torch_dtype,
            ).to(self.device)
            self._vae.eval()
            print("VAE loaded successfully.")

        except ImportError:
            raise ImportError(
                "diffusers is required for pretrained VAE. "
                "Install with: pip install diffusers"
            )

    @torch.no_grad()
    def encode(self, images: Tensor) -> Tensor:
        """
        Encode images to latents.

        Args:
            images: [B, 3, H, W] in range [0, 1] or [-1, 1].

        Returns:
            latents: [B, 4, H//8, W//8] scaled latents.
        """
        self._load_vae()

        # Normalize to [-1, 1] if needed
        if images.min() >= 0:
            images = images * 2.0 - 1.0

        # Encode
        latent_dist = self._vae.encode(images.to(self.torch_dtype)).latent_dist
        latents = latent_dist.sample()

        # Scale
        latents = latents * self.scaling_factor

        return latents

    @torch.no_grad()
    def decode(self, latents: Tensor) -> Tensor:
        """
        Decode latents to images.

        Args:
            latents: [B, 4, H, W] latents.

        Returns:
            images: [B, 3, H*8, W*8] in range [0, 1].
        """
        self._load_vae()

        # Unscale
        latents = latents / self.scaling_factor

        # Decode
        images = self._vae.decode(latents.to(self.torch_dtype)).sample

        # Convert to [0, 1]
        images = (images + 1.0) / 2.0
        images = torch.clamp(images, 0, 1)

        return images.float()

    def forward(self, x: Tensor) -> Tensor:
        """Alias for decode."""
        return self.decode(x)


class PretrainedCLIP(nn.Module):
    """
    Wrapper for CLIP text encoder from HuggingFace transformers.

    Uses the CLIP text encoder to convert text prompts into embeddings
    for conditioning the diffusion model.

    Args:
        model_id: HuggingFace model ID.
        max_length: Maximum sequence length.
        torch_dtype: Data type for model weights.
        device: Device to load model on.
    """

    def __init__(
        self,
        model_id: str = "openai/clip-vit-large-patch14",
        max_length: int = 77,
        torch_dtype: torch.dtype = torch.float32,  # Use fp32 for stability
        device: Optional[torch.device] = None,
    ):
        super().__init__()

        self.model_id = model_id
        self.max_length = max_length
        self.torch_dtype = torch_dtype
        self.device = device or torch.device("cuda" if torch.cuda.is_available() else "cpu")

        # Lazy loading
        self._encoder = None
        self._tokenizer = None

        # CLIP-L has 768-dim embeddings
        self.embed_dim = 768

    def _load_encoder(self):
        """Load encoder on first use."""
        if self._encoder is not None:
            return

        try:
            from transformers import CLIPTextModel, CLIPTokenizer

            print(f"Loading CLIP from {self.model_id}...")

            self._tokenizer = CLIPTokenizer.from_pretrained(self.model_id)
            self._encoder = CLIPTextModel.from_pretrained(
                self.model_id,
                torch_dtype=self.torch_dtype,
            ).to(self.device)
            self._encoder.eval()

            print("CLIP loaded successfully.")

        except ImportError:
            raise ImportError(
                "transformers is required for pretrained CLIP. "
                "Install with: pip install transformers"
            )

    @torch.no_grad()
    def encode(self, prompts: Union[str, List[str]]) -> Tensor:
        """
        Encode text prompts to embeddings.

        Args:
            prompts: Single prompt or list of prompts.

        Returns:
            embeddings: [B, max_length, 768] text embeddings.
        """
        self._load_encoder()

        if isinstance(prompts, str):
            prompts = [prompts]

        # Tokenize
        tokens = self._tokenizer(
            prompts,
            padding="max_length",
            max_length=self.max_length,
            truncation=True,
            return_tensors="pt",
        ).to(self.device)

        # Encode
        outputs = self._encoder(**tokens)

        # Use last hidden state (not pooled output)
        embeddings = outputs.last_hidden_state

        return embeddings.float()

    def forward(self, prompts: Union[str, List[str]]) -> Tensor:
        """Alias for encode."""
        return self.encode(prompts)


class PretrainedSDXLTextEncoder(nn.Module):
    """
    SDXL uses dual text encoders (CLIP-L + OpenCLIP-G).

    This provides the combined embedding used by SDXL models.

    Args:
        model_id: HuggingFace model ID for SDXL.
        torch_dtype: Data type.
        device: Device.
    """

    def __init__(
        self,
        model_id: str = "stabilityai/stable-diffusion-xl-base-1.0",
        torch_dtype: torch.dtype = torch.float32,  # Use fp32 for stability
        device: Optional[torch.device] = None,
    ):
        super().__init__()

        self.model_id = model_id
        self.torch_dtype = torch_dtype
        self.device = device or torch.device("cuda" if torch.cuda.is_available() else "cpu")

        # Lazy loading
        self._encoder_1 = None
        self._encoder_2 = None
        self._tokenizer_1 = None
        self._tokenizer_2 = None

        # SDXL combined dim (CLIP-L 768 + OpenCLIP-G 1280 pooled)
        self.embed_dim = 768  # We'll use CLIP-L for simplicity
        self.max_length = 77

    def _load_encoders(self):
        """Load encoders on first use."""
        if self._encoder_1 is not None:
            return

        try:
            from transformers import CLIPTextModel, CLIPTokenizer

            print(f"Loading SDXL text encoders...")

            # Load CLIP-L (text_encoder)
            self._tokenizer_1 = CLIPTokenizer.from_pretrained(
                self.model_id, subfolder="tokenizer"
            )
            self._encoder_1 = CLIPTextModel.from_pretrained(
                self.model_id,
                subfolder="text_encoder",
                torch_dtype=self.torch_dtype,
            ).to(self.device)
            self._encoder_1.eval()

            print("SDXL text encoder loaded successfully.")

        except ImportError:
            raise ImportError(
                "transformers is required. Install with: pip install transformers"
            )
        except Exception as e:
            print(f"Warning: Could not load SDXL encoders ({e}), falling back to CLIP-L")
            # Fallback to standard CLIP
            self._tokenizer_1 = CLIPTokenizer.from_pretrained("openai/clip-vit-large-patch14")
            self._encoder_1 = CLIPTextModel.from_pretrained(
                "openai/clip-vit-large-patch14",
                torch_dtype=self.torch_dtype,
            ).to(self.device)
            self._encoder_1.eval()

    @torch.no_grad()
    def encode(self, prompts: Union[str, List[str]]) -> Tensor:
        """
        Encode text prompts.

        Args:
            prompts: Single prompt or list of prompts.

        Returns:
            embeddings: [B, 77, 768] text embeddings.
        """
        self._load_encoders()

        if isinstance(prompts, str):
            prompts = [prompts]

        # Tokenize with first encoder
        tokens = self._tokenizer_1(
            prompts,
            padding="max_length",
            max_length=self.max_length,
            truncation=True,
            return_tensors="pt",
        ).to(self.device)

        # Encode
        outputs = self._encoder_1(**tokens)
        embeddings = outputs.last_hidden_state

        return embeddings.float()

    def forward(self, prompts: Union[str, List[str]]) -> Tensor:
        """Alias for encode."""
        return self.encode(prompts)


def load_pretrained_vae(
    model_id: str = "stabilityai/stable-diffusion-xl-base-1.0",
    device: Optional[torch.device] = None,
) -> PretrainedVAE:
    """
    Helper to load pretrained VAE.

    Args:
        model_id: HuggingFace model ID.
        device: Device to use.

    Returns:
        Pretrained VAE wrapper.
    """
    return PretrainedVAE(model_id=model_id, device=device)


def load_pretrained_text_encoder(
    model_id: str = "openai/clip-vit-large-patch14",
    device: Optional[torch.device] = None,
) -> PretrainedCLIP:
    """
    Helper to load pretrained text encoder.

    Args:
        model_id: HuggingFace model ID.
        device: Device to use.

    Returns:
        Pretrained CLIP wrapper.
    """
    return PretrainedCLIP(model_id=model_id, device=device)
