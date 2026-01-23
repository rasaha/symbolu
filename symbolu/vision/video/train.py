#!/usr/bin/env python3
"""
Training script for Phase-Quad Video Generator.

This script trains the Phase-Quad video diffusion model using:
- Pretrained Video VAE (CogVideoX) for encoding videos to latents
- Pretrained CLIP for text conditioning
- Standard diffusion training objective (predict noise)

Usage:
    # Train on synthetic data (for testing)
    python -m symbolu.vision.video.train --synthetic --epochs 10

    # Train on local dataset
    python -m symbolu.vision.video.train --data-dir /path/to/videos --epochs 100

    # Train on HuggingFace dataset
    python -m symbolu.vision.video.train --hf-dataset webvid

    # Resume from checkpoint
    python -m symbolu.vision.video.train --resume checkpoints_video/epoch_10.pt

    # Progressive training from image model
    python -m symbolu.vision.video.train --init-from-image checkpoints/final.pt

Requirements:
    pip install torch diffusers transformers datasets decord
"""

import argparse
import os
import time
from pathlib import Path
from typing import Optional, Dict, Any

import torch
import torch.nn as nn
import torch.nn.functional as F
from torch import Tensor
from torch.optim import AdamW
from torch.optim.lr_scheduler import CosineAnnealingLR
from torch.cuda.amp import autocast, GradScaler

from symbolu.vision.video.generator import PhaseQuadVideoGenerator
from symbolu.vision.video.config import PhaseQuadVideoConfig
from symbolu.vision.video.dataset import (
    get_video_dataset,
    create_video_dataloader,
    SyntheticVideoDataset,
)
from symbolu.vision.inference.samplers import NoiseSchedule


class VideoMockVAE(nn.Module):
    """Mock video VAE for testing without pretrained weights."""

    def __init__(
        self,
        latent_channels: int = 16,
        temporal_compression: int = 4,
        spatial_compression: int = 8,
        scaling_factor: float = 0.7,
    ):
        super().__init__()
        self.latent_channels = latent_channels
        self.temporal_compression = temporal_compression
        self.spatial_compression = spatial_compression
        self.scaling_factor = scaling_factor

    def encode(self, videos: Tensor) -> Tensor:
        """
        Mock encode videos to latents.

        Args:
            videos: [B, T, C, H, W] or [B, C, T, H, W] in [-1, 1].

        Returns:
            latents: [B, C_lat, T', H', W'].
        """
        # Handle both formats
        if videos.dim() == 5 and videos.shape[2] == 3:
            # [B, T, C, H, W] -> [B, C, T, H, W]
            videos = videos.permute(0, 2, 1, 3, 4)

        B, C, T, H, W = videos.shape

        # Simple downsampling
        T_lat = T // self.temporal_compression
        H_lat = H // self.spatial_compression
        W_lat = W // self.spatial_compression

        # Project to latent channels via interpolation + random projection
        latents = F.interpolate(
            videos.reshape(B, C * T, H, W),
            size=(H_lat, W_lat),
            mode='bilinear',
            align_corners=False,
        )

        # Reshape and project
        latents = latents.reshape(B, C, T, H_lat, W_lat)

        # Temporal downsampling
        if T_lat < T:
            latents = F.interpolate(
                latents.reshape(B, C * H_lat, T, W_lat).permute(0, 1, 3, 2),
                size=(T_lat,),
                mode='linear',
                align_corners=False,
            ).permute(0, 1, 3, 2).reshape(B, C, T_lat, H_lat, W_lat)

        # Project to latent channels
        latents = torch.randn(B, self.latent_channels, T_lat, H_lat, W_lat, device=videos.device)
        latents = latents * self.scaling_factor

        return latents

    def decode(self, latents: Tensor) -> Tensor:
        """Mock decode (not used in training)."""
        return latents


class MockTextEncoder(nn.Module):
    """Mock text encoder for testing."""

    def __init__(self, embed_dim: int = 768, max_length: int = 77):
        super().__init__()
        self.embed_dim = embed_dim
        self.max_length = max_length
        self.proj = nn.Linear(embed_dim, embed_dim)

    def encode(self, prompts: list) -> Tensor:
        batch_size = len(prompts)
        device = next(self.parameters()).device
        embeddings = torch.randn(batch_size, self.max_length, self.embed_dim, device=device)
        for i, prompt in enumerate(prompts):
            scale = len(prompt) / 100.0
            embeddings[i] = embeddings[i] * (0.5 + scale)
        return self.proj(embeddings)


class VideoDiffusionTrainer:
    """
    Trainer for Phase-Quad Video diffusion model.

    Handles the full training loop including:
    - Video VAE encoding to latents
    - Text encoding of captions
    - Diffusion noise addition
    - Model forward pass
    - Loss computation
    - Gradient updates
    - Checkpointing

    Args:
        model: PhaseQuadVideoGenerator model.
        config: PhaseQuadVideoConfig.
        vae: Video VAE for encoding.
        text_encoder: Text encoder.
        device: Training device.
        output_dir: Checkpoint directory.
        use_amp: Use mixed precision.
        gradient_accumulation_steps: Accumulation steps.
    """

    def __init__(
        self,
        model: PhaseQuadVideoGenerator,
        config: PhaseQuadVideoConfig,
        vae: nn.Module,
        text_encoder: nn.Module,
        device: torch.device,
        output_dir: str = "checkpoints_video",
        use_amp: bool = True,
        gradient_accumulation_steps: int = 4,
    ):
        self.model = model.to(device)
        self.config = config
        self.vae = vae
        self.text_encoder = text_encoder
        self.device = device
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.use_amp = use_amp and device.type == "cuda"
        self.gradient_accumulation_steps = gradient_accumulation_steps

        # Noise schedule (same as image)
        self.noise_schedule = NoiseSchedule(num_timesteps=1000).to(device)

        # Mixed precision
        self.scaler = GradScaler() if self.use_amp else None

        # Logging
        self.global_step = 0
        self.epoch = 0

    def encode_videos(self, videos: Tensor) -> Tensor:
        """
        Encode videos to VAE latents.

        Args:
            videos: [B, T, C, H, W] videos in [-1, 1].

        Returns:
            latents: [B, C_lat, T', H', W'] latents.
        """
        if torch.isnan(videos).any():
            print(f"WARNING: NaN in input videos!")
            B, T, C, H, W = videos.shape
            T_lat = T // self.config.vae.temporal_compression
            H_lat = H // self.config.vae.spatial_compression
            W_lat = W // self.config.vae.spatial_compression
            return torch.zeros(B, self.config.vae.latent_channels, T_lat, H_lat, W_lat, device=videos.device)

        with torch.no_grad():
            if hasattr(self.vae, 'encode'):
                latents = self.vae.encode(videos)
            else:
                # Simple fallback
                B, T, C, H, W = videos.shape
                T_lat = T // self.config.vae.temporal_compression
                H_lat = H // self.config.vae.spatial_compression
                W_lat = W // self.config.vae.spatial_compression
                latents = torch.randn(B, self.config.vae.latent_channels, T_lat, H_lat, W_lat, device=videos.device)
                latents = latents * self.config.vae.scaling_factor

        if self.global_step == 0:
            print(f"  Videos: shape={videos.shape}, min={videos.min():.3f}, max={videos.max():.3f}")
            print(f"  Latents: shape={latents.shape}, min={latents.min():.3f}, max={latents.max():.3f}")

        return latents

    def encode_text(self, captions: list) -> Tensor:
        """Encode text captions."""
        with torch.no_grad():
            embeddings = self.text_encoder.encode(captions)

        if self.global_step == 0:
            print(f"  Text: shape={embeddings.shape}")

        return embeddings

    def compute_loss(
        self,
        latents: Tensor,
        text_embeddings: Tensor,
    ) -> Tensor:
        """
        Compute diffusion training loss.

        Args:
            latents: [B, C, T, H, W] clean latents.
            text_embeddings: [B, L, D] text embeddings.

        Returns:
            loss: MSE loss between predicted and actual noise.
        """
        batch_size = latents.shape[0]

        latents = latents.float()
        text_embeddings = text_embeddings.float()

        if torch.isnan(latents).any():
            print("WARNING: NaN in latents!")
            return torch.tensor(0.0, device=self.device, requires_grad=True)

        # Sample timesteps
        timesteps = torch.randint(
            0,
            self.noise_schedule.num_timesteps,
            (batch_size,),
            device=self.device,
        )

        # Sample noise
        noise = torch.randn_like(latents)

        # Add noise to latents
        noisy_latents = self.noise_schedule.add_noise(latents, noise, timesteps)

        if torch.isnan(noisy_latents).any():
            print("WARNING: NaN after add_noise!")
            return torch.tensor(0.0, device=self.device, requires_grad=True)

        # Predict noise
        noise_pred = self.model(
            noisy_latents,
            timesteps,
            text_embeddings,
        )

        if torch.isnan(noise_pred).any():
            print("WARNING: NaN in model output!")
            return torch.tensor(0.0, device=self.device, requires_grad=True)

        # MSE loss
        loss = F.mse_loss(noise_pred, noise)

        return loss

    def train_step(
        self,
        batch: Dict[str, Any],
        optimizer: torch.optim.Optimizer,
    ) -> Dict[str, float]:
        """Single training step."""
        videos = batch["videos"].to(self.device)  # [B, T, C, H, W]
        captions = batch["captions"]

        # Encode videos to latents
        latents = self.encode_videos(videos)

        # Encode text
        text_embeddings = self.encode_text(captions)

        # Forward pass
        if self.use_amp:
            with autocast():
                loss = self.compute_loss(latents, text_embeddings)

            self.scaler.scale(loss / self.gradient_accumulation_steps).backward()

            if (self.global_step + 1) % self.gradient_accumulation_steps == 0:
                self.scaler.unscale_(optimizer)
                torch.nn.utils.clip_grad_norm_(self.model.parameters(), 1.0)
                self.scaler.step(optimizer)
                self.scaler.update()
                optimizer.zero_grad()
        else:
            loss = self.compute_loss(latents, text_embeddings)
            (loss / self.gradient_accumulation_steps).backward()

            if (self.global_step + 1) % self.gradient_accumulation_steps == 0:
                torch.nn.utils.clip_grad_norm_(self.model.parameters(), 1.0)
                optimizer.step()
                optimizer.zero_grad()

        self.global_step += 1

        # Collect BCVF metrics
        bcvf_metrics = {}
        if hasattr(self.model, 'get_bcvf_metrics'):
            bcvf_metrics = self.model.get_bcvf_metrics()

        return {
            "loss": loss.item(),
            "latent_norm": latents.norm().item(),
            **bcvf_metrics,
        }

    def train_epoch(
        self,
        dataloader,
        optimizer: torch.optim.Optimizer,
        scheduler=None,
    ) -> Dict[str, float]:
        """Train for one epoch."""
        self.model.train()

        total_loss = 0.0
        num_batches = 0

        for batch_idx, batch in enumerate(dataloader):
            metrics = self.train_step(batch, optimizer)

            total_loss += metrics["loss"]
            num_batches += 1

            if batch_idx % 10 == 0:
                # Build log string
                log_str = (
                    f"  Batch {batch_idx}/{len(dataloader)} | "
                    f"Loss: {metrics['loss']:.4f} | "
                    f"LR: {optimizer.param_groups[0]['lr']:.2e}"
                )
                # Add BCVF metrics if available
                bcvf_sf = metrics.get("block_0/bcvf_video/sf_mean")
                bcvf_st = metrics.get("block_0/bcvf_video/st_mean")
                if bcvf_sf is not None:
                    log_str += f" | sf={bcvf_sf:.3f}"
                if bcvf_st is not None:
                    log_str += f" st={bcvf_st:.3f}"
                print(log_str)

        if scheduler is not None:
            scheduler.step()

        self.epoch += 1

        return {
            "avg_loss": total_loss / max(num_batches, 1),
        }

    def save_checkpoint(
        self,
        optimizer: torch.optim.Optimizer,
        scheduler=None,
        filename: Optional[str] = None,
    ):
        """Save training checkpoint."""
        if filename is None:
            filename = f"epoch_{self.epoch}.pt"

        checkpoint = {
            "epoch": self.epoch,
            "global_step": self.global_step,
            "model_state_dict": self.model.state_dict(),
            "optimizer_state_dict": optimizer.state_dict(),
            "config": self.config,
        }

        if scheduler is not None:
            checkpoint["scheduler_state_dict"] = scheduler.state_dict()

        if self.scaler is not None:
            checkpoint["scaler_state_dict"] = self.scaler.state_dict()

        path = self.output_dir / filename
        torch.save(checkpoint, path)
        print(f"Saved checkpoint to {path}")

    def load_checkpoint(
        self,
        path: str,
        optimizer=None,
        scheduler=None,
    ):
        """Load training checkpoint."""
        checkpoint = torch.load(path, map_location=self.device)

        self.model.load_state_dict(checkpoint["model_state_dict"])
        self.epoch = checkpoint["epoch"]
        self.global_step = checkpoint["global_step"]

        if optimizer is not None and "optimizer_state_dict" in checkpoint:
            optimizer.load_state_dict(checkpoint["optimizer_state_dict"])

        if scheduler is not None and "scheduler_state_dict" in checkpoint:
            scheduler.load_state_dict(checkpoint["scheduler_state_dict"])

        if self.scaler is not None and "scaler_state_dict" in checkpoint:
            self.scaler.load_state_dict(checkpoint["scaler_state_dict"])

        print(f"Loaded checkpoint from {path} (epoch {self.epoch})")


def init_from_image_model(
    video_model: PhaseQuadVideoGenerator,
    image_checkpoint_path: str,
):
    """
    Initialize video model from pretrained image model.

    Copies weights for:
    - FFN layers
    - Row/col integrators (maps to PhaseIntegrator2D)
    - Quad retriever
    - Gate mixer

    The time integrator is initialized randomly.

    Args:
        video_model: Video model to initialize.
        image_checkpoint_path: Path to image model checkpoint.
    """
    print(f"Initializing from image model: {image_checkpoint_path}")

    checkpoint = torch.load(image_checkpoint_path, map_location="cpu")
    if "model_state_dict" in checkpoint:
        image_state = checkpoint["model_state_dict"]
    else:
        image_state = checkpoint

    video_state = video_model.state_dict()
    loaded_keys = []
    skipped_keys = []

    for key, value in image_state.items():
        # Map image keys to video keys
        video_key = key

        # Skip patch embed (different dimensions)
        if "patch_embed" in key:
            skipped_keys.append(key)
            continue

        # Map row/col integrator weights
        if "phase_integrator.row_integrator" in key:
            video_key = key.replace("phase_integrator", "phase_integrator")
        elif "phase_integrator.col_integrator" in key:
            video_key = key.replace("phase_integrator", "phase_integrator")

        # Try to load if shapes match
        if video_key in video_state:
            if video_state[video_key].shape == value.shape:
                video_state[video_key] = value
                loaded_keys.append(video_key)
            else:
                skipped_keys.append(f"{key} (shape mismatch)")
        else:
            skipped_keys.append(f"{key} (not found)")

    video_model.load_state_dict(video_state, strict=False)

    print(f"  Loaded {len(loaded_keys)} parameters")
    print(f"  Skipped {len(skipped_keys)} parameters")


def train(
    model_size: str = "small",
    data_dir: Optional[str] = None,
    hf_dataset: Optional[str] = None,
    synthetic: bool = False,
    batch_size: int = 2,
    learning_rate: float = 1e-5,
    epochs: int = 50,
    save_every: int = 10,
    output_dir: str = "checkpoints_video",
    resume: Optional[str] = None,
    init_from_image: Optional[str] = None,
    num_workers: int = 2,
    use_pretrained: bool = True,
    num_frames: int = 16,
    image_size: int = 256,
    gradient_accumulation: int = 4,
):
    """
    Main training function.

    Args:
        model_size: Model size ("tiny", "small", "base").
        data_dir: Local video data directory.
        hf_dataset: HuggingFace dataset name.
        synthetic: Use synthetic data for testing.
        batch_size: Training batch size.
        learning_rate: Learning rate.
        epochs: Number of epochs.
        save_every: Save checkpoint every N epochs.
        output_dir: Output directory.
        resume: Checkpoint to resume from.
        init_from_image: Image model checkpoint for initialization.
        num_workers: Data loading workers.
        use_pretrained: Use pretrained VAE/CLIP.
        num_frames: Number of video frames.
        image_size: Frame size.
        gradient_accumulation: Gradient accumulation steps.
    """
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Training on {device}")
    print(f"CUDA available: {torch.cuda.is_available()}")
    if torch.cuda.is_available():
        print(f"GPU: {torch.cuda.get_device_name(0)}")
        print(f"GPU Memory: {torch.cuda.get_device_properties(0).total_memory / 1e9:.1f} GB")

    # Create model
    print(f"\nCreating Phase-Quad Video model ({model_size})...")
    config_fn = getattr(PhaseQuadVideoConfig, model_size)
    config = config_fn()

    # Override config with CLI args
    config.num_frames = num_frames
    config.height = image_size
    config.width = image_size

    model = PhaseQuadVideoGenerator(config)

    n_params = sum(p.numel() for p in model.parameters())
    print(f"Model parameters: {n_params:,}")
    print(f"Video config: {num_frames} frames @ {image_size}x{image_size}")

    # Initialize from image model if specified
    if init_from_image is not None:
        init_from_image_model(model, init_from_image)

    # Load VAE and text encoder
    if use_pretrained:
        print("\nLoading pretrained VAE and text encoder...")
        try:
            from symbolu.vision.video.vae import PretrainedVideoVAE
            from symbolu.vision.inference.pretrained import PretrainedCLIP
            vae = PretrainedVideoVAE(device=device)
            text_encoder = PretrainedCLIP(device=device)
        except Exception as e:
            print(f"Could not load pretrained models: {e}")
            print("Using mock models instead...")
            vae = VideoMockVAE(
                latent_channels=config.vae.latent_channels,
                temporal_compression=config.vae.temporal_compression,
                spatial_compression=config.vae.spatial_compression,
            ).to(device)
            text_encoder = MockTextEncoder(embed_dim=config.text_encoder.embed_dim).to(device)
    else:
        print("\nUsing mock VAE and text encoder...")
        vae = VideoMockVAE(
            latent_channels=config.vae.latent_channels,
            temporal_compression=config.vae.temporal_compression,
            spatial_compression=config.vae.spatial_compression,
        ).to(device)
        text_encoder = MockTextEncoder(embed_dim=config.text_encoder.embed_dim).to(device)

    # Create dataset
    print("\nLoading dataset...")
    if synthetic:
        dataset = get_video_dataset(
            "synthetic",
            num_samples=500,
            num_frames=num_frames,
            image_size=image_size,
        )
    elif hf_dataset:
        dataset = get_video_dataset(
            "huggingface",
            dataset_name=hf_dataset,
            num_frames=num_frames,
            image_size=image_size,
        )
    elif data_dir:
        dataset = get_video_dataset(
            "local",
            data_dir=data_dir,
            num_frames=num_frames,
            image_size=image_size,
        )
    else:
        print("No dataset specified, using synthetic data")
        dataset = get_video_dataset(
            "synthetic",
            num_samples=500,
            num_frames=num_frames,
            image_size=image_size,
        )

    dataloader = create_video_dataloader(
        dataset,
        batch_size=batch_size,
        num_workers=num_workers,
    )
    print(f"Dataset: {len(dataset)} samples, {len(dataloader)} batches per epoch")

    # Create trainer
    trainer = VideoDiffusionTrainer(
        model=model,
        config=config,
        vae=vae,
        text_encoder=text_encoder,
        device=device,
        output_dir=output_dir,
        use_amp=False,  # Disable for stability
        gradient_accumulation_steps=gradient_accumulation,
    )

    # Create optimizer and scheduler
    optimizer = AdamW(
        model.parameters(),
        lr=learning_rate,
        betas=(0.9, 0.999),
        weight_decay=0.01,
    )

    scheduler = CosineAnnealingLR(
        optimizer,
        T_max=epochs,
        eta_min=learning_rate / 100,
    )

    # Resume from checkpoint
    if resume:
        trainer.load_checkpoint(resume, optimizer, scheduler)

    # Training loop
    print(f"\nStarting training for {epochs} epochs...")
    print(f"Effective batch size: {batch_size * gradient_accumulation}")
    print("=" * 60)

    start_time = time.time()

    for epoch in range(trainer.epoch, epochs):
        print(f"\nEpoch {epoch + 1}/{epochs}")
        print("-" * 40)

        metrics = trainer.train_epoch(dataloader, optimizer, scheduler)

        print(f"Epoch {epoch + 1} complete | Avg Loss: {metrics['avg_loss']:.4f}")

        if (epoch + 1) % save_every == 0:
            trainer.save_checkpoint(optimizer, scheduler)

    # Save final
    trainer.save_checkpoint(optimizer, scheduler, "final.pt")

    total_time = time.time() - start_time
    print(f"\nTraining complete in {total_time / 3600:.2f} hours")


def main():
    parser = argparse.ArgumentParser(
        description="Train Phase-Quad Video Generator"
    )

    # Data arguments
    parser.add_argument(
        "--data-dir",
        type=str,
        help="Local data directory with videos and captions",
    )
    parser.add_argument(
        "--hf-dataset",
        type=str,
        help="HuggingFace dataset name",
    )
    parser.add_argument(
        "--synthetic",
        action="store_true",
        help="Use synthetic data for testing",
    )

    # Model arguments
    parser.add_argument(
        "--model-size",
        type=str,
        default="small",
        choices=["tiny", "small", "base"],
        help="Model size",
    )
    parser.add_argument(
        "--num-frames",
        type=int,
        default=16,
        help="Number of video frames",
    )
    parser.add_argument(
        "--image-size",
        type=int,
        default=256,
        help="Frame size",
    )

    # Training arguments
    parser.add_argument(
        "--batch-size",
        type=int,
        default=2,
        help="Training batch size",
    )
    parser.add_argument(
        "--learning-rate", "--lr",
        type=float,
        default=1e-5,
        help="Learning rate",
    )
    parser.add_argument(
        "--epochs",
        type=int,
        default=50,
        help="Number of epochs",
    )
    parser.add_argument(
        "--save-every",
        type=int,
        default=10,
        help="Save checkpoint every N epochs",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="checkpoints_video",
        help="Output directory",
    )
    parser.add_argument(
        "--resume",
        type=str,
        help="Checkpoint to resume from",
    )
    parser.add_argument(
        "--init-from-image",
        type=str,
        help="Initialize from image model checkpoint",
    )
    parser.add_argument(
        "--num-workers",
        type=int,
        default=2,
        help="Data loading workers",
    )
    parser.add_argument(
        "--gradient-accumulation",
        type=int,
        default=4,
        help="Gradient accumulation steps",
    )
    parser.add_argument(
        "--no-pretrained",
        action="store_true",
        help="Don't use pretrained VAE/CLIP",
    )

    args = parser.parse_args()

    train(
        model_size=args.model_size,
        data_dir=args.data_dir,
        hf_dataset=args.hf_dataset,
        synthetic=args.synthetic,
        batch_size=args.batch_size,
        learning_rate=args.learning_rate,
        epochs=args.epochs,
        save_every=args.save_every,
        output_dir=args.output_dir,
        resume=args.resume,
        init_from_image=args.init_from_image,
        num_workers=args.num_workers,
        use_pretrained=not args.no_pretrained,
        num_frames=args.num_frames,
        image_size=args.image_size,
        gradient_accumulation=args.gradient_accumulation,
    )


if __name__ == "__main__":
    main()
