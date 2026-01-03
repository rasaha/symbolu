"""
Sovereign Trainer - Training Loop with PID Governor Integration.

This module implements the training loop for Sovereign models,
integrating with Symbolu's existing components:
- symbolu.resonance for phoneme processing
- symbolu.guna_modulation for entropy state
- symbolu.formulas for vritti mapping

Features:
- Multi-objective loss optimization
- R-Signal coherence monitoring
- PID Governor for intent drift correction
- Integration with existing Symbolu pipeline
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import torch
import torch.nn as nn
from torch.utils.data import DataLoader, Dataset

# Local imports
from symbolu.sovereign.embedding import (
    SovereignEmbedding,
    SovereignEmbeddingConfig,
    SovereignOutputHead,
)
from symbolu.sovereign.train_loss import (
    MultiObjectiveLoss,
    TrainingLossConfig,
    RSignalCoherenceLoss,
    IntentDriftMonitor,
)


@dataclass
class SovereignTrainerConfig:
    """Configuration for Sovereign training."""

    # Model
    vocab_size: int = 50257
    d_model: int = 1024
    n_layers: int = 12
    n_heads: int = 16

    # Training
    batch_size: int = 32
    learning_rate: float = 3e-4
    weight_decay: float = 0.01
    max_epochs: int = 10
    warmup_steps: int = 1000
    gradient_clip: float = 1.0

    # Loss weights
    lambda_r: float = 0.1
    lambda_s: float = 0.1
    lambda_c: float = 0.05

    # PID Governor
    use_pid_governor: bool = True
    pid_kp: float = 0.5
    pid_ki: float = 0.1
    pid_kd: float = 0.05

    # Logging
    log_interval: int = 100
    eval_interval: int = 1000
    save_interval: int = 5000

    # Paths
    output_dir: str = "outputs/sovereign"
    checkpoint_dir: str = "checkpoints/sovereign"


class RSignalGovernor:
    """
    PID Governor for R-Signal drift correction.

    Monitors intent drift during generation and applies
    corrections to prevent hallucination.
    """

    def __init__(
        self,
        kp: float = 0.5,
        ki: float = 0.1,
        kd: float = 0.05,
        r_classes: int = 12,
    ):
        self.kp = kp
        self.ki = ki
        self.kd = kd
        self.r_classes = r_classes

        # State
        self.integral = 0.0
        self.last_error = 0.0
        self.target_r: Optional[int] = None

    def reset(self):
        """Reset governor state."""
        self.integral = 0.0
        self.last_error = 0.0
        self.target_r = None

    def set_target(self, target_r: int):
        """Set target R-Signal for the sequence."""
        self.target_r = target_r

    def compute_correction(self, actual_r: int) -> float:
        """
        Compute PID correction for R-Signal drift.

        Args:
            actual_r: Current predicted R-Signal

        Returns:
            Correction factor to apply
        """
        if self.target_r is None:
            return 0.0

        error = self.target_r - actual_r

        self.integral += error
        self.integral = max(-10, min(10, self.integral))  # Anti-windup

        derivative = error - self.last_error
        self.last_error = error

        correction = (
            self.kp * error
            + self.ki * self.integral
            + self.kd * derivative
        )

        return correction

    def apply_to_logits(
        self,
        logits: torch.Tensor,
        r_mapping: Dict[int, int],
    ) -> torch.Tensor:
        """
        Apply correction to token logits based on R-Signal alignment.

        Args:
            logits: Token prediction logits [vocab_size]
            r_mapping: Token ID to R-Signal mapping

        Returns:
            Adjusted logits
        """
        if self.target_r is None:
            return logits

        adjusted = logits.clone()

        for token_id, token_r in r_mapping.items():
            if token_r != self.target_r:
                # Suppress tokens with wrong intent
                adjustment = abs(self.compute_correction(token_r)) * 2.0
                adjusted[token_id] -= adjustment

        return adjusted


class SovereignDataset(Dataset):
    """
    Dataset wrapper for Sovereign-preprocessed data.

    Expects data files with structure:
    {
        'input_ids': [Seq],
        'c_signals': [Seq, 32],
        's_signals': [Seq],
        'r_signals': [Seq],
        'g_states': [Seq, 3]
    }
    """

    def __init__(self, data_dir: str, split: str = "train"):
        self.data_dir = Path(data_dir) / split
        self.files = sorted(self.data_dir.glob("*.pt"))

        if not self.files:
            raise ValueError(f"No .pt files found in {self.data_dir}")

        # Load first file to get dimensions
        sample = torch.load(self.files[0])
        self.seq_len = sample["input_ids"].shape[0]

    def __len__(self) -> int:
        return len(self.files)

    def __getitem__(self, idx: int) -> Dict[str, torch.Tensor]:
        data = torch.load(self.files[idx])
        return data


class SovereignTrainer:
    """
    Trainer for Sovereign models with multi-objective optimization.
    """

    def __init__(
        self,
        model: nn.Module,
        config: Optional[SovereignTrainerConfig] = None,
    ):
        self.model = model
        self.config = config or SovereignTrainerConfig()

        # Loss function
        loss_config = TrainingLossConfig(
            lambda_token=1.0,
            lambda_r=self.config.lambda_r,
            lambda_s=self.config.lambda_s,
            lambda_c=self.config.lambda_c,
        )
        self.loss_fn = MultiObjectiveLoss(loss_config)
        self.coherence_loss = RSignalCoherenceLoss()

        # PID Governor
        if self.config.use_pid_governor:
            self.governor = RSignalGovernor(
                kp=self.config.pid_kp,
                ki=self.config.pid_ki,
                kd=self.config.pid_kd,
            )
        else:
            self.governor = None

        # Drift monitor
        self.drift_monitor = IntentDriftMonitor()

        # Device
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.model.to(self.device)

        # Optimizer
        self.optimizer = torch.optim.AdamW(
            self.model.parameters(),
            lr=self.config.learning_rate,
            weight_decay=self.config.weight_decay,
        )

        # Scheduler
        self.scheduler = None  # Will be set in train()

        # Metrics
        self.global_step = 0
        self.metrics_history: List[Dict[str, float]] = []

    def train_step(
        self,
        batch: Dict[str, torch.Tensor],
    ) -> Dict[str, float]:
        """
        Execute single training step.

        Args:
            batch: Dictionary with input_ids, c_signals, s_signals, r_signals, g_states

        Returns:
            Dictionary with loss metrics
        """
        self.model.train()

        # Move to device
        input_ids = batch["input_ids"].to(self.device)
        c_signals = batch["c_signals"].to(self.device)
        s_signals = batch["s_signals"].to(self.device)
        r_signals = batch["r_signals"].to(self.device)
        g_states = batch["g_states"].to(self.device)
        attention_mask = batch.get("attention_mask")
        if attention_mask is not None:
            attention_mask = attention_mask.to(self.device)

        # Shift for next-token prediction
        target_tokens = input_ids[:, 1:].contiguous()
        target_r = r_signals[:, 1:].contiguous()
        target_s = s_signals[:, 1:].contiguous()
        target_c = c_signals[:, 1:].contiguous()

        input_ids = input_ids[:, :-1]
        c_signals = c_signals[:, :-1]
        s_signals = s_signals[:, :-1]
        r_signals = r_signals[:, :-1]
        g_states = g_states[:, :-1]

        # Forward pass
        outputs = self.model(
            input_ids=input_ids,
            c_signals=c_signals,
            s_signals=s_signals,
            r_signals=r_signals,
            g_states=g_states,
        )

        # Compute loss
        loss_output = self.loss_fn(
            token_logits=outputs["token_logits"],
            r_logits=outputs["r_logits"],
            s_logits=outputs["s_logits"],
            c_pred=outputs["c_pred"],
            target_tokens=target_tokens,
            target_r=target_r,
            target_s=target_s,
            target_c=target_c,
            attention_mask=attention_mask,
        )

        # Add coherence penalty
        coherence_penalty = self.coherence_loss(outputs["r_logits"])
        total_loss = loss_output.total + coherence_penalty

        # Backward pass
        self.optimizer.zero_grad()
        total_loss.backward()

        # Gradient clipping
        if self.config.gradient_clip > 0:
            torch.nn.utils.clip_grad_norm_(
                self.model.parameters(),
                self.config.gradient_clip,
            )

        self.optimizer.step()

        if self.scheduler is not None:
            self.scheduler.step()

        self.global_step += 1

        # Return metrics
        metrics = loss_output.to_dict()
        metrics["loss/coherence"] = coherence_penalty.item()
        metrics["lr"] = self.optimizer.param_groups[0]["lr"]

        return metrics

    def train(
        self,
        train_loader: DataLoader,
        val_loader: Optional[DataLoader] = None,
    ):
        """
        Run full training loop.

        Args:
            train_loader: Training data loader
            val_loader: Optional validation data loader
        """
        # Create output directories
        os.makedirs(self.config.output_dir, exist_ok=True)
        os.makedirs(self.config.checkpoint_dir, exist_ok=True)

        # Setup scheduler
        total_steps = len(train_loader) * self.config.max_epochs
        self.scheduler = torch.optim.lr_scheduler.OneCycleLR(
            self.optimizer,
            max_lr=self.config.learning_rate,
            total_steps=total_steps,
            pct_start=self.config.warmup_steps / total_steps,
        )

        print(f"\n{'='*70}")
        print("SOVEREIGN TRAINING")
        print(f"{'='*70}")
        print(f"Device: {self.device}")
        print(f"Total steps: {total_steps}")
        print(f"Batch size: {self.config.batch_size}")
        print(f"Learning rate: {self.config.learning_rate}")
        print(f"Loss weights: λ_R={self.config.lambda_r}, λ_S={self.config.lambda_s}, λ_C={self.config.lambda_c}")
        print(f"{'='*70}\n")

        start_time = time.time()

        for epoch in range(self.config.max_epochs):
            epoch_metrics = []

            for batch_idx, batch in enumerate(train_loader):
                metrics = self.train_step(batch)
                epoch_metrics.append(metrics)

                # Logging
                if self.global_step % self.config.log_interval == 0:
                    avg_metrics = {
                        k: sum(m[k] for m in epoch_metrics[-self.config.log_interval:])
                        / min(len(epoch_metrics), self.config.log_interval)
                        for k in metrics.keys()
                    }
                    elapsed = time.time() - start_time
                    print(
                        f"Step {self.global_step:6d} | "
                        f"Loss: {avg_metrics['loss/total']:.4f} | "
                        f"Token: {avg_metrics['loss/token']:.4f} | "
                        f"R: {avg_metrics['loss/r_signal']:.4f} | "
                        f"S: {avg_metrics['loss/s_signal']:.4f} | "
                        f"LR: {avg_metrics['lr']:.2e} | "
                        f"Time: {elapsed:.1f}s"
                    )

                # Evaluation
                if val_loader is not None and self.global_step % self.config.eval_interval == 0:
                    val_metrics = self.evaluate(val_loader)
                    print(f"[EVAL] Val Loss: {val_metrics['loss/total']:.4f}")

                # Checkpointing
                if self.global_step % self.config.save_interval == 0:
                    self.save_checkpoint(f"step_{self.global_step}")

            # End of epoch
            print(f"\n[EPOCH {epoch+1}/{self.config.max_epochs}] Complete")
            self.save_checkpoint(f"epoch_{epoch+1}")

        print(f"\n{'='*70}")
        print("TRAINING COMPLETE")
        print(f"{'='*70}\n")

    def evaluate(self, val_loader: DataLoader) -> Dict[str, float]:
        """Evaluate model on validation set."""
        self.model.eval()
        total_metrics = {}
        n_batches = 0

        with torch.no_grad():
            for batch in val_loader:
                # Similar to train_step but without backward pass
                input_ids = batch["input_ids"].to(self.device)
                c_signals = batch["c_signals"].to(self.device)
                s_signals = batch["s_signals"].to(self.device)
                r_signals = batch["r_signals"].to(self.device)
                g_states = batch["g_states"].to(self.device)

                target_tokens = input_ids[:, 1:].contiguous()
                target_r = r_signals[:, 1:].contiguous()
                target_s = s_signals[:, 1:].contiguous()
                target_c = c_signals[:, 1:].contiguous()

                outputs = self.model(
                    input_ids=input_ids[:, :-1],
                    c_signals=c_signals[:, :-1],
                    s_signals=s_signals[:, :-1],
                    r_signals=r_signals[:, :-1],
                    g_states=g_states[:, :-1],
                )

                loss_output = self.loss_fn(
                    token_logits=outputs["token_logits"],
                    r_logits=outputs["r_logits"],
                    s_logits=outputs["s_logits"],
                    c_pred=outputs["c_pred"],
                    target_tokens=target_tokens,
                    target_r=target_r,
                    target_s=target_s,
                    target_c=target_c,
                )

                metrics = loss_output.to_dict()
                for k, v in metrics.items():
                    total_metrics[k] = total_metrics.get(k, 0) + v
                n_batches += 1

        return {k: v / n_batches for k, v in total_metrics.items()}

    def save_checkpoint(self, name: str):
        """Save model checkpoint."""
        path = Path(self.config.checkpoint_dir) / f"{name}.pt"
        torch.save({
            "model_state_dict": self.model.state_dict(),
            "optimizer_state_dict": self.optimizer.state_dict(),
            "global_step": self.global_step,
            "config": self.config,
        }, path)
        print(f"[SAVE] Checkpoint saved: {path}")

    def load_checkpoint(self, path: str):
        """Load model checkpoint."""
        checkpoint = torch.load(path, map_location=self.device)
        self.model.load_state_dict(checkpoint["model_state_dict"])
        self.optimizer.load_state_dict(checkpoint["optimizer_state_dict"])
        self.global_step = checkpoint["global_step"]
        print(f"[LOAD] Checkpoint loaded: {path}")


def create_sovereign_model(config: Optional[SovereignTrainerConfig] = None):
    """
    Create a complete Sovereign model for training.

    This creates a simple transformer with SovereignEmbedding
    and SovereignOutputHead for demonstration.
    """
    if config is None:
        config = SovereignTrainerConfig()

    embed_config = SovereignEmbeddingConfig(
        vocab_size=config.vocab_size,
        d_model=config.d_model,
    )

    class SovereignModel(nn.Module):
        def __init__(self):
            super().__init__()
            self.embedding = SovereignEmbedding(embed_config)
            self.output_head = SovereignOutputHead(embed_config)

            # Simple transformer layers (placeholder)
            encoder_layer = nn.TransformerEncoderLayer(
                d_model=config.d_model,
                nhead=config.n_heads,
                dim_feedforward=config.d_model * 4,
                dropout=0.1,
                batch_first=True,
            )
            self.transformer = nn.TransformerEncoder(
                encoder_layer,
                num_layers=config.n_layers,
            )

        def forward(
            self,
            input_ids: torch.Tensor,
            c_signals: torch.Tensor,
            s_signals: torch.Tensor,
            r_signals: torch.Tensor,
            g_states: torch.Tensor,
        ) -> Dict[str, torch.Tensor]:
            # Embedding
            x = self.embedding(
                input_ids=input_ids,
                c_signals=c_signals,
                s_signals=s_signals,
                r_signals=r_signals,
                g_states=g_states,
            )

            # Transformer
            x = self.transformer(x)

            # Output heads
            token_logits, r_logits, s_logits, c_pred = self.output_head(x)

            return {
                "token_logits": token_logits,
                "r_logits": r_logits,
                "s_logits": s_logits,
                "c_pred": c_pred,
                "hidden_states": x,
            }

    return SovereignModel()


if __name__ == "__main__":
    # Quick test
    print("\n" + "=" * 70)
    print("SOVEREIGN TRAINER - QUICK TEST")
    print("=" * 70)

    config = SovereignTrainerConfig(
        n_layers=2,  # Small for testing
        batch_size=2,
    )

    model = create_sovereign_model(config)
    trainer = SovereignTrainer(model, config)

    # Create dummy batch
    B, Seq = 2, 64
    dummy_batch = {
        "input_ids": torch.randint(0, config.vocab_size, (B, Seq)),
        "c_signals": torch.randn(B, Seq, 32),
        "s_signals": torch.randint(0, 17, (B, Seq)),
        "r_signals": torch.randint(0, 12, (B, Seq)),
        "g_states": torch.rand(B, Seq, 3),
    }

    # Single training step
    metrics = trainer.train_step(dummy_batch)

    print("\nTraining step metrics:")
    for k, v in metrics.items():
        print(f"  {k}: {v:.4f}")

    print("\n[PASS] Trainer test successful!")
    print("=" * 70 + "\n")
