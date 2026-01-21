#!/usr/bin/env python3
"""
Training script for Phase-Quad Image Generator.

This script trains the Phase-Quad diffusion model using:
- Pretrained SDXL VAE for encoding images to latents
- Pretrained CLIP for text conditioning
- Standard diffusion training objective (predict noise)

Usage:
    # Train on synthetic data (for testing)
    python -m symbolu.vision.training.train --synthetic --epochs 5

    # Train on local dataset
    python -m symbolu.vision.training.train --data-dir /path/to/data --epochs 100

    # Train on HuggingFace dataset
    python -m symbolu.vision.training.train --hf-dataset lambdalabs/pokemon-blip-captions

    # Resume from checkpoint
    python -m symbolu.vision.training.train --resume checkpoints/epoch_10.pt

Requirements:
    pip install torch diffusers transformers datasets accelerate wandb
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

from symbolu.vision.phase_quad_generator import PhaseQuadImageGenerator
from symbolu.vision.config import PhaseQuadVisionConfig
from symbolu.vision.inference.samplers import NoiseSchedule
from symbolu.vision.training.dataset import (
    get_dataset,
    create_dataloader,
    SyntheticDataset,
)


class DiffusionTrainer:
    """
    Trainer for Phase-Quad diffusion model.

    Handles the full training loop including:
    - VAE encoding of images to latents
    - Text encoding of captions
    - Diffusion noise addition
    - Model forward pass
    - Loss computation
    - Gradient updates
    - Checkpointing
    - Logging

    Args:
        model: PhaseQuadImageGenerator model.
        config: PhaseQuadVisionConfig.
        vae: Pretrained VAE for encoding.
        text_encoder: Pretrained text encoder.
        device: Device to train on.
        output_dir: Directory for checkpoints and logs.
    """

    def __init__(
        self,
        model: PhaseQuadImageGenerator,
        config: PhaseQuadVisionConfig,
        vae: nn.Module,
        text_encoder: nn.Module,
        device: torch.device,
        output_dir: str = "checkpoints",
        use_amp: bool = True,
        gradient_accumulation_steps: int = 1,
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

        # Noise schedule
        self.noise_schedule = NoiseSchedule(num_timesteps=1000).to(device)

        # Mixed precision scaler
        self.scaler = GradScaler() if self.use_amp else None

        # Logging
        self.global_step = 0
        self.epoch = 0

    def encode_images(self, images: Tensor) -> Tensor:
        """
        Encode images to VAE latents.

        Args:
            images: [B, 3, H, W] images in [-1, 1].

        Returns:
            latents: [B, 4, H//8, W//8] latents.
        """
        # Check input validity
        if torch.isnan(images).any():
            print(f"WARNING: NaN in input images!")
            return torch.zeros(images.shape[0], 4, images.shape[2]//8, images.shape[3]//8, device=images.device)

        with torch.no_grad():
            if hasattr(self.vae, 'encode'):
                latents = self.vae.encode(images)
            else:
                # For mock VAE
                latents = images[:, :4] if images.shape[1] >= 4 else images
                latents = F.interpolate(latents, scale_factor=1/8, mode='bilinear')

        # Debug first batch
        if self.global_step == 0:
            print(f"  Images: shape={images.shape}, min={images.min():.3f}, max={images.max():.3f}")
            print(f"  Latents: shape={latents.shape}, min={latents.min():.3f}, max={latents.max():.3f}")

        return latents

    def encode_text(self, captions: list) -> Tensor:
        """
        Encode text captions.

        Args:
            captions: List of caption strings.

        Returns:
            embeddings: [B, T, D] text embeddings.
        """
        with torch.no_grad():
            embeddings = self.text_encoder.encode(captions)

        # Debug first batch
        if self.global_step == 0:
            print(f"  Text: shape={embeddings.shape}, min={embeddings.min():.3f}, max={embeddings.max():.3f}")
            if torch.isnan(embeddings).any():
                print("  WARNING: NaN in text embeddings!")

        return embeddings

    def compute_loss(
        self,
        latents: Tensor,
        text_embeddings: Tensor,
    ) -> Tensor:
        """
        Compute diffusion training loss.

        Args:
            latents: [B, C, H, W] clean latents.
            text_embeddings: [B, T, D] text embeddings.

        Returns:
            loss: MSE loss between predicted and actual noise.
        """
        batch_size = latents.shape[0]

        # Ensure float32 for model forward pass (avoid fp16 precision issues)
        latents = latents.float()
        text_embeddings = text_embeddings.float()

        # Debug: Check for NaN early
        if torch.isnan(latents).any():
            print(f"WARNING: NaN in latents! shape={latents.shape}, min={latents.min()}, max={latents.max()}")
            return torch.tensor(0.0, device=self.device, requires_grad=True)
        if torch.isnan(text_embeddings).any():
            print(f"WARNING: NaN in text_embeddings! shape={text_embeddings.shape}")
            return torch.tensor(0.0, device=self.device, requires_grad=True)

        # Sample random timesteps
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

        # Check for NaN after noise addition
        if torch.isnan(noisy_latents).any():
            print(f"WARNING: NaN after add_noise! timesteps={timesteps.tolist()}")
            return torch.tensor(0.0, device=self.device, requires_grad=True)

        # Predict noise
        noise_pred = self.model(
            noisy_latents,
            timesteps,
            text_embeddings,
        )

        # Check for NaN in output
        if torch.isnan(noise_pred).any():
            print("WARNING: NaN detected in model output!")
            return torch.tensor(0.0, device=self.device, requires_grad=True)

        # MSE loss
        loss = F.mse_loss(noise_pred, noise)

        return loss

    def train_step(
        self,
        batch: Dict[str, Any],
        optimizer: torch.optim.Optimizer,
    ) -> Dict[str, float]:
        """
        Single training step.

        Args:
            batch: Batch of images and captions.
            optimizer: Optimizer instance.

        Returns:
            Dictionary of metrics.
        """
        images = batch["images"].to(self.device)
        captions = batch["captions"]

        # Encode images to latents
        latents = self.encode_images(images)

        # Encode text
        text_embeddings = self.encode_text(captions)

        # Forward pass with mixed precision
        if self.use_amp:
            with autocast():
                loss = self.compute_loss(latents, text_embeddings)

            # Backward pass
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

        return {
            "loss": loss.item(),
            "latent_norm": latents.norm().item(),
        }

    def train_epoch(
        self,
        dataloader,
        optimizer: torch.optim.Optimizer,
        scheduler: Optional[torch.optim.lr_scheduler._LRScheduler] = None,
    ) -> Dict[str, float]:
        """
        Train for one epoch.

        Args:
            dataloader: Training data loader.
            optimizer: Optimizer.
            scheduler: Optional learning rate scheduler.

        Returns:
            Dictionary of average metrics.
        """
        self.model.train()

        total_loss = 0.0
        num_batches = 0

        for batch_idx, batch in enumerate(dataloader):
            metrics = self.train_step(batch, optimizer)

            total_loss += metrics["loss"]
            num_batches += 1

            # Log progress
            if batch_idx % 10 == 0:
                print(
                    f"  Batch {batch_idx}/{len(dataloader)} | "
                    f"Loss: {metrics['loss']:.4f} | "
                    f"LR: {optimizer.param_groups[0]['lr']:.2e}"
                )

        if scheduler is not None:
            scheduler.step()

        self.epoch += 1

        return {
            "avg_loss": total_loss / num_batches,
        }

    def save_checkpoint(
        self,
        optimizer: torch.optim.Optimizer,
        scheduler: Optional[torch.optim.lr_scheduler._LRScheduler] = None,
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
        optimizer: Optional[torch.optim.Optimizer] = None,
        scheduler: Optional[torch.optim.lr_scheduler._LRScheduler] = None,
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


def train(
    model_size: str = "base",
    data_dir: Optional[str] = None,
    hf_dataset: Optional[str] = None,
    synthetic: bool = False,
    batch_size: int = 4,
    learning_rate: float = 1e-4,
    epochs: int = 100,
    save_every: int = 10,
    output_dir: str = "checkpoints",
    resume: Optional[str] = None,
    num_workers: int = 4,
    use_pretrained: bool = True,
    image_size: int = 512,
):
    """
    Main training function.

    Args:
        model_size: Model size ("tiny", "small", "base", "large").
        data_dir: Local data directory.
        hf_dataset: HuggingFace dataset name.
        synthetic: Use synthetic data for testing.
        batch_size: Training batch size.
        learning_rate: Learning rate.
        epochs: Number of epochs.
        save_every: Save checkpoint every N epochs.
        output_dir: Output directory for checkpoints.
        resume: Path to checkpoint to resume from.
        num_workers: Number of data loading workers.
        use_pretrained: Whether to use pretrained VAE/CLIP.
        image_size: Training image size.
    """
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Training on {device}")

    # Create model
    print(f"\nCreating Phase-Quad model ({model_size})...")
    config_fn = getattr(PhaseQuadVisionConfig, model_size)
    config = config_fn()
    model = PhaseQuadImageGenerator(config)

    n_params = sum(p.numel() for p in model.parameters())
    print(f"Model parameters: {n_params:,}")

    # Load VAE and text encoder
    if use_pretrained:
        print("\nLoading pretrained VAE and text encoder...")
        from symbolu.vision.inference.pretrained import (
            PretrainedVAE,
            PretrainedCLIP,
        )
        vae = PretrainedVAE(device=device)
        text_encoder = PretrainedCLIP(device=device)
    else:
        print("\nUsing mock VAE and text encoder...")
        from symbolu.vision.inference.pipeline import MockVAE, MockTextEncoder
        vae = MockVAE().to(device)
        text_encoder = MockTextEncoder(embed_dim=config.text_encoder.embed_dim).to(device)

    # Create dataset
    print("\nLoading dataset...")
    if synthetic:
        dataset = get_dataset(
            "synthetic",
            num_samples=1000,
            image_size=image_size,
        )
    elif hf_dataset:
        dataset = get_dataset(
            "huggingface",
            dataset_name=hf_dataset,
            image_size=image_size,
        )
    elif data_dir:
        dataset = get_dataset(
            "local",
            data_dir=data_dir,
            image_size=image_size,
        )
    else:
        print("No dataset specified, using synthetic data")
        dataset = get_dataset(
            "synthetic",
            num_samples=1000,
            image_size=image_size,
        )

    dataloader = create_dataloader(
        dataset,
        batch_size=batch_size,
        num_workers=num_workers,
    )
    print(f"Dataset: {len(dataset)} samples, {len(dataloader)} batches per epoch")

    # Create trainer (disable AMP for stability during initial training)
    trainer = DiffusionTrainer(
        model=model,
        config=config,
        vae=vae,
        text_encoder=text_encoder,
        device=device,
        output_dir=output_dir,
        use_amp=False,  # Disable mixed precision for stability
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
    print("=" * 60)

    start_time = time.time()

    for epoch in range(trainer.epoch, epochs):
        print(f"\nEpoch {epoch + 1}/{epochs}")
        print("-" * 40)

        metrics = trainer.train_epoch(dataloader, optimizer, scheduler)

        print(f"Epoch {epoch + 1} complete | Avg Loss: {metrics['avg_loss']:.4f}")

        # Save checkpoint
        if (epoch + 1) % save_every == 0:
            trainer.save_checkpoint(optimizer, scheduler)

    # Save final checkpoint
    trainer.save_checkpoint(optimizer, scheduler, "final.pt")

    total_time = time.time() - start_time
    print(f"\nTraining complete in {total_time / 3600:.2f} hours")


def main():
    parser = argparse.ArgumentParser(
        description="Train Phase-Quad Image Generator"
    )

    # Data arguments
    parser.add_argument(
        "--data-dir",
        type=str,
        help="Local data directory with images and captions",
    )
    parser.add_argument(
        "--hf-dataset",
        type=str,
        help="HuggingFace dataset name (e.g., lambdalabs/pokemon-blip-captions)",
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
        default="base",
        choices=["tiny", "small", "base", "large"],
        help="Model size",
    )
    parser.add_argument(
        "--image-size",
        type=int,
        default=512,
        help="Training image size",
    )

    # Training arguments
    parser.add_argument(
        "--batch-size",
        type=int,
        default=4,
        help="Training batch size",
    )
    parser.add_argument(
        "--learning-rate", "--lr",
        type=float,
        default=1e-4,
        help="Learning rate",
    )
    parser.add_argument(
        "--epochs",
        type=int,
        default=100,
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
        default="checkpoints",
        help="Output directory for checkpoints",
    )
    parser.add_argument(
        "--resume",
        type=str,
        help="Path to checkpoint to resume from",
    )
    parser.add_argument(
        "--num-workers",
        type=int,
        default=4,
        help="Number of data loading workers",
    )

    # Component arguments
    parser.add_argument(
        "--no-pretrained",
        action="store_true",
        help="Don't use pretrained VAE/CLIP (for testing)",
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
        num_workers=args.num_workers,
        use_pretrained=not args.no_pretrained,
        image_size=args.image_size,
    )


if __name__ == "__main__":
    main()
