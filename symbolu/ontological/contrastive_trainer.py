"""
Ontological Engine - Contrastive Training Pipeline
===================================================

Training pipeline with contrastive loss for domain separation.

Features:
- Triplet contrastive loss for reasoning vs creativity separation
- Domain centroid separation loss
- GSM8K (reasoning) and Stories (creativity) datasets
- Mixed precision training
- Checkpoint saving and resumption

Usage:
    from symbolu.ontological.contrastive_trainer import ContrastiveTrainer

    trainer = ContrastiveTrainer()
    trainer.train(epochs=10, use_synthetic=True)
    trainer.save("model_contrastive.pt")
"""

from typing import List, Dict, Optional, Tuple, Any
from dataclasses import dataclass, field
from pathlib import Path
import time
import random
import numpy as np

# Check PyTorch availability
try:
    import torch
    import torch.nn as nn
    import torch.nn.functional as F
    from torch.optim import AdamW
    from torch.optim.lr_scheduler import CosineAnnealingLR, LinearLR, SequentialLR
    PYTORCH_AVAILABLE = True
except ImportError:
    PYTORCH_AVAILABLE = False


def set_seed(seed: int) -> None:
    """Set random seed for reproducibility."""
    random.seed(seed)
    np.random.seed(seed)
    if PYTORCH_AVAILABLE:
        torch.manual_seed(seed)
        if torch.cuda.is_available():
            torch.cuda.manual_seed_all(seed)


if PYTORCH_AVAILABLE:
    from symbolu.ontological.pytorch_engine import PyTorchOntologicalEngine
    from symbolu.ontological.encoder import get_encoder, TextEncoder
    from symbolu.ontological.domain_datasets import (
        GSM8KDataset,
        ROCStoriesDataset,
        ContrastiveDataset,
        create_contrastive_dataset,
    )


    @dataclass
    class ContrastiveConfig:
        """Configuration for contrastive training."""
        # Optimization
        learning_rate: float = 1e-4
        weight_decay: float = 0.01
        warmup_ratio: float = 0.1
        max_grad_norm: float = 1.0

        # Training
        epochs: int = 10
        batch_size: int = 16
        gradient_accumulation_steps: int = 1

        # Loss weights
        contrastive_weight: float = 1.0
        separation_weight: float = 0.5
        purity_weight: float = 0.1
        orthogonality_weight: float = 0.05

        # Contrastive settings
        triplet_margin: float = 0.5
        centroid_margin: float = 1.0

        # Encoder
        encoder_type: str = "auto"
        model_path: Optional[str] = None

        # Device
        device: str = "auto"

        # Mixed precision
        use_fp16: bool = True

        # Checkpointing
        checkpoint_dir: str = "checkpoints/contrastive"
        save_every_n_epochs: int = 1

        # Logging
        log_every_n_steps: int = 10

        # Data
        reasoning_samples: int = 500
        creativity_samples: int = 500
        use_huggingface: bool = False  # Set False for offline use

        # Reproducibility
        seed: int = 42

        # Validation and early stopping
        validation_split: float = 0.2
        early_stopping_patience: int = 3
        early_stopping_min_delta: float = 0.001


    class ContrastiveTrainer:
        """
        Contrastive trainer for domain separation.

        Trains the ontological engine to separate reasoning and creativity
        domains in the embedding space using triplet loss.

        Usage:
            trainer = ContrastiveTrainer()

            # With synthetic data (for testing)
            trainer.train(epochs=5, use_synthetic=True)

            # With real data
            trainer.train(
                epochs=10,
                gsm8k_path="data/gsm8k.jsonl",
                stories_path="data/rocstories.csv",
            )

            trainer.save("model_contrastive.pt")
        """

        def __init__(
            self,
            engine: Optional[PyTorchOntologicalEngine] = None,
            config: Optional[ContrastiveConfig] = None,
        ):
            self.config = config or ContrastiveConfig()

            # Set seed for reproducibility
            set_seed(self.config.seed)
            print(f"Random seed: {self.config.seed}")

            self.engine = engine or PyTorchOntologicalEngine()

            # Setup device
            self.device = self._get_device()
            self.engine = self.engine.to(self.device)

            # Setup encoder
            self.encoder = get_encoder(
                self.config.encoder_type,
                model_path=self.config.model_path,
            )

            # Training state
            self.global_step = 0
            self.best_separation = 0.0
            self.best_val_separation = 0.0
            self.epochs_without_improvement = 0
            self.history: List[Dict[str, float]] = []

            # Mixed precision
            self.scaler = None
            if self.config.use_fp16 and self.device.type == "cuda":
                self.scaler = torch.cuda.amp.GradScaler()

            print(self.engine.summary())
            print(f"Device: {self.device}")
            print(f"Encoder: {self.encoder.name}")
            print(f"Validation split: {self.config.validation_split:.0%}")
            print(f"Early stopping patience: {self.config.early_stopping_patience}")

        def _get_device(self) -> torch.device:
            """Get the best available device."""
            if self.config.device != "auto":
                return torch.device(self.config.device)

            if torch.cuda.is_available():
                return torch.device("cuda")
            elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
                return torch.device("mps")
            else:
                return torch.device("cpu")

        def _encode_batch(self, texts: List[str]) -> torch.Tensor:
            """Encode a batch of texts to embeddings."""
            embeddings = self.encoder.encode_batch(texts)
            return torch.tensor(embeddings, dtype=torch.float32, device=self.device)

        def train(
            self,
            epochs: int = None,
            use_synthetic: bool = True,
            gsm8k_path: str = None,
            stories_path: str = None,
        ) -> Dict[str, Any]:
            """
            Train with contrastive loss.

            Args:
                epochs: Number of epochs (overrides config)
                use_synthetic: Use synthetic data for testing
                gsm8k_path: Path to GSM8K JSONL file
                stories_path: Path to ROCStories CSV file

            Returns:
                Training history
            """
            epochs = epochs or self.config.epochs

            # Load datasets
            print("\nLoading datasets...")
            if use_synthetic:
                gsm8k = GSM8KDataset.create_synthetic(self.config.reasoning_samples)
                stories = ROCStoriesDataset.create_synthetic(self.config.creativity_samples)
            else:
                if gsm8k_path:
                    gsm8k = GSM8KDataset.load_from_jsonl(gsm8k_path, self.config.reasoning_samples)
                elif self.config.use_huggingface:
                    gsm8k = GSM8KDataset.load_from_huggingface(max_samples=self.config.reasoning_samples)
                else:
                    gsm8k = GSM8KDataset.create_synthetic(self.config.reasoning_samples)

                if stories_path:
                    stories = ROCStoriesDataset.load_from_csv(stories_path, self.config.creativity_samples)
                elif self.config.use_huggingface:
                    stories = ROCStoriesDataset.load_from_huggingface(max_samples=self.config.creativity_samples)
                else:
                    stories = ROCStoriesDataset.create_synthetic(self.config.creativity_samples)

            # Create contrastive dataset
            contrastive_data = ContrastiveDataset(
                reasoning_texts=gsm8k.get_texts(),
                creativity_texts=stories.get_texts(),
            )

            print(f"  Reasoning samples: {len(gsm8k)}")
            print(f"  Creativity samples: {len(stories)}")
            print(f"  Total triplets: {len(contrastive_data)}")

            # Pre-encode all texts for efficiency
            print("\nPre-encoding texts...")
            all_reasoning = gsm8k.get_texts()
            all_creativity = stories.get_texts()

            reasoning_embeddings = self._encode_batch(all_reasoning)
            creativity_embeddings = self._encode_batch(all_creativity)

            print(f"  Reasoning embeddings: {reasoning_embeddings.shape}")
            print(f"  Creativity embeddings: {creativity_embeddings.shape}")

            # Split into train/val
            val_split = self.config.validation_split
            n_r = len(reasoning_embeddings)
            n_c = len(creativity_embeddings)
            n_r_val = int(n_r * val_split)
            n_c_val = int(n_c * val_split)

            # Shuffle indices
            r_indices = torch.randperm(n_r)
            c_indices = torch.randperm(n_c)

            # Split embeddings
            train_reasoning = reasoning_embeddings[r_indices[n_r_val:]]
            val_reasoning = reasoning_embeddings[r_indices[:n_r_val]]
            train_creativity = creativity_embeddings[c_indices[n_c_val:]]
            val_creativity = creativity_embeddings[c_indices[:n_c_val]]

            print(f"  Train: {len(train_reasoning)} reasoning, {len(train_creativity)} creativity")
            print(f"  Val: {len(val_reasoning)} reasoning, {len(val_creativity)} creativity")

            # Update contrastive dataset to use training data only
            contrastive_data = ContrastiveDataset(
                reasoning_texts=all_reasoning[:n_r - n_r_val],
                creativity_texts=all_creativity[:n_c - n_c_val],
            )

            # Setup optimizer
            optimizer = AdamW(
                self.engine.parameters(),
                lr=self.config.learning_rate,
                weight_decay=self.config.weight_decay,
            )

            # Setup scheduler
            steps_per_epoch = len(contrastive_data) // self.config.batch_size
            total_steps = steps_per_epoch * epochs
            warmup_steps = int(total_steps * self.config.warmup_ratio)

            warmup_scheduler = LinearLR(
                optimizer,
                start_factor=0.1,
                end_factor=1.0,
                total_iters=max(warmup_steps, 1),
            )
            main_scheduler = CosineAnnealingLR(
                optimizer,
                T_max=max(total_steps - warmup_steps, 1),
            )
            scheduler = SequentialLR(
                optimizer,
                schedulers=[warmup_scheduler, main_scheduler],
                milestones=[warmup_steps],
            )

            # Training loop
            print(f"\nStarting contrastive training for {epochs} epochs")
            print(f"  Steps per epoch: {steps_per_epoch}")
            print(f"  Early stopping patience: {self.config.early_stopping_patience}")
            print()

            for epoch in range(epochs):
                epoch_metrics = self._train_epoch(
                    contrastive_data,
                    train_reasoning,  # Use train split
                    train_creativity,  # Use train split
                    optimizer,
                    scheduler,
                    epoch,
                )

                # Compute train separation score
                train_separation = self._compute_separation_score(
                    train_reasoning,
                    train_creativity,
                )

                # Compute validation separation score
                val_separation = self._compute_separation_score(
                    val_reasoning,
                    val_creativity,
                )

                print(f"Epoch {epoch + 1}: loss={epoch_metrics['total_loss']:.4f}, "
                      f"train_sep={train_separation:.4f}, val_sep={val_separation:.4f}")

                # Track best based on validation
                if val_separation > self.best_val_separation + self.config.early_stopping_min_delta:
                    self.best_val_separation = val_separation
                    self.best_separation = train_separation
                    self.epochs_without_improvement = 0
                    self._save_checkpoint("best")
                else:
                    self.epochs_without_improvement += 1
                    print(f"  No improvement for {self.epochs_without_improvement} epoch(s)")

                # Save checkpoint
                if (epoch + 1) % self.config.save_every_n_epochs == 0:
                    self._save_checkpoint(f"epoch_{epoch + 1}")

                self.history.append({
                    "epoch": epoch + 1,
                    **epoch_metrics,
                    "train_separation": train_separation,
                    "val_separation": val_separation,
                })

                # Early stopping check
                if self.epochs_without_improvement >= self.config.early_stopping_patience:
                    print(f"\nEarly stopping triggered after {epoch + 1} epochs")
                    print(f"Best validation separation: {self.best_val_separation:.4f}")
                    break

            return {
                "history": self.history,
                "best_separation": self.best_separation,
                "best_val_separation": self.best_val_separation,
            }

        def _train_epoch(
            self,
            contrastive_data: ContrastiveDataset,
            reasoning_embeddings: torch.Tensor,
            creativity_embeddings: torch.Tensor,
            optimizer: AdamW,
            scheduler: Any,
            epoch: int,
        ) -> Dict[str, float]:
            """Train for one epoch."""
            self.engine.train()

            total_loss = 0.0
            total_contrastive = 0.0
            total_separation = 0.0
            num_batches = 0

            optimizer.zero_grad()

            # Number of batches
            n_samples = len(contrastive_data)
            n_batches = n_samples // self.config.batch_size

            for step in range(n_batches):
                # Sample batch of triplet indices
                batch_indices = random.sample(
                    range(n_samples),
                    self.config.batch_size,
                )

                # Gather embeddings for triplets
                anchor_embs = []
                positive_embs = []
                negative_embs = []

                for idx in batch_indices:
                    if idx < len(reasoning_embeddings):
                        # Reasoning anchor
                        anchor_embs.append(reasoning_embeddings[idx])
                        # Positive: another reasoning
                        pos_idx = random.choice([i for i in range(len(reasoning_embeddings)) if i != idx])
                        positive_embs.append(reasoning_embeddings[pos_idx])
                        # Negative: creativity
                        neg_idx = random.randint(0, len(creativity_embeddings) - 1)
                        negative_embs.append(creativity_embeddings[neg_idx])
                    else:
                        # Creativity anchor
                        c_idx = idx - len(reasoning_embeddings)
                        anchor_embs.append(creativity_embeddings[c_idx])
                        # Positive: another creativity
                        pos_idx = random.choice([i for i in range(len(creativity_embeddings)) if i != c_idx])
                        positive_embs.append(creativity_embeddings[pos_idx])
                        # Negative: reasoning
                        neg_idx = random.randint(0, len(reasoning_embeddings) - 1)
                        negative_embs.append(reasoning_embeddings[neg_idx])

                anchor_batch = torch.stack(anchor_embs)
                positive_batch = torch.stack(positive_embs)
                negative_batch = torch.stack(negative_embs)

                # Forward pass
                if self.scaler:
                    with torch.cuda.amp.autocast():
                        loss, metrics = self._compute_batch_loss(
                            anchor_batch,
                            positive_batch,
                            negative_batch,
                            reasoning_embeddings,
                            creativity_embeddings,
                        )
                        loss = loss / self.config.gradient_accumulation_steps

                    self.scaler.scale(loss).backward()

                    if (step + 1) % self.config.gradient_accumulation_steps == 0:
                        self.scaler.unscale_(optimizer)
                        torch.nn.utils.clip_grad_norm_(
                            self.engine.parameters(),
                            self.config.max_grad_norm,
                        )
                        self.scaler.step(optimizer)
                        self.scaler.update()
                        optimizer.zero_grad()
                        scheduler.step()
                else:
                    loss, metrics = self._compute_batch_loss(
                        anchor_batch,
                        positive_batch,
                        negative_batch,
                        reasoning_embeddings,
                        creativity_embeddings,
                    )
                    loss = loss / self.config.gradient_accumulation_steps
                    loss.backward()

                    if (step + 1) % self.config.gradient_accumulation_steps == 0:
                        torch.nn.utils.clip_grad_norm_(
                            self.engine.parameters(),
                            self.config.max_grad_norm,
                        )
                        optimizer.step()
                        optimizer.zero_grad()
                        scheduler.step()

                total_loss += loss.item() * self.config.gradient_accumulation_steps
                total_contrastive += metrics["contrastive"]
                total_separation += metrics["separation"]
                num_batches += 1
                self.global_step += 1

                # Logging
                if self.global_step % self.config.log_every_n_steps == 0:
                    avg_loss = total_loss / num_batches
                    lr = scheduler.get_last_lr()[0]
                    print(f"  Step {self.global_step}: loss={avg_loss:.4f}, lr={lr:.2e}")

            return {
                "total_loss": total_loss / max(num_batches, 1),
                "contrastive_loss": total_contrastive / max(num_batches, 1),
                "separation_loss": total_separation / max(num_batches, 1),
            }

        def _compute_batch_loss(
            self,
            anchor: torch.Tensor,
            positive: torch.Tensor,
            negative: torch.Tensor,
            reasoning_embeddings: torch.Tensor,
            creativity_embeddings: torch.Tensor,
        ) -> Tuple[torch.Tensor, Dict[str, float]]:
            """Compute loss for a batch."""
            # Forward pass for triplets
            anchor_out = self.engine(anchor)
            positive_out = self.engine(positive)
            negative_out = self.engine(negative)

            # Contrastive loss
            contrastive_loss = self.engine.compute_contrastive_loss(
                anchor_out,
                positive_out,
                negative_out,
                margin=self.config.triplet_margin,
            )

            # Domain separation loss (sample subset for efficiency)
            sample_size = min(32, len(reasoning_embeddings), len(creativity_embeddings))
            r_indices = random.sample(range(len(reasoning_embeddings)), sample_size)
            c_indices = random.sample(range(len(creativity_embeddings)), sample_size)

            r_sample = reasoning_embeddings[r_indices]
            c_sample = creativity_embeddings[c_indices]

            r_out = self.engine(r_sample)
            c_out = self.engine(c_sample)

            separation_loss = self.engine.compute_domain_separation_loss(
                r_out,
                c_out,
                margin=self.config.centroid_margin,
            )

            # Combined loss
            loss = (
                self.config.contrastive_weight * contrastive_loss +
                self.config.separation_weight * separation_loss
            )

            return loss, {
                "contrastive": contrastive_loss.item(),
                "separation": separation_loss.item(),
            }

        def _compute_separation_score(
            self,
            reasoning_embeddings: torch.Tensor,
            creativity_embeddings: torch.Tensor,
        ) -> float:
            """Compute separation score between domains."""
            self.engine.eval()

            with torch.no_grad():
                r_out = self.engine(reasoning_embeddings)
                c_out = self.engine(creativity_embeddings)

                r_centroid = r_out["ontological"].mean(dim=0)
                c_centroid = c_out["ontological"].mean(dim=0)

                # Cosine distance (1 - similarity)
                cos_sim = F.cosine_similarity(
                    r_centroid.unsqueeze(0),
                    c_centroid.unsqueeze(0),
                )

                # Convert to separation score (higher = better separated)
                separation = (1 - cos_sim.item()) / 2  # Normalize to [0, 1]

            return separation

        def _save_checkpoint(self, name: str) -> None:
            """Save model checkpoint."""
            checkpoint_dir = Path(self.config.checkpoint_dir)
            checkpoint_dir.mkdir(parents=True, exist_ok=True)

            path = checkpoint_dir / f"{name}.pt"
            torch.save({
                "engine_state": self.engine.state_dict(),
                "global_step": self.global_step,
                "best_separation": self.best_separation,
                "config": self.config.__dict__,
                "history": self.history,
            }, path)

            print(f"Saved checkpoint: {path}")

        def load_checkpoint(self, path: str) -> None:
            """Load model from checkpoint."""
            checkpoint = torch.load(path, map_location=self.device)
            self.engine.load_state_dict(checkpoint["engine_state"])
            self.global_step = checkpoint.get("global_step", 0)
            self.best_separation = checkpoint.get("best_separation", 0.0)
            self.history = checkpoint.get("history", [])

            print(f"Loaded checkpoint: {path}")

        def save(self, path: str) -> None:
            """Save complete model."""
            torch.save({
                "engine_state": self.engine.state_dict(),
                "config": self.config.__dict__,
            }, path)
            print(f"Model saved to: {path}")

        def benchmark(self) -> Dict[str, float]:
            """Run quick benchmark on current model."""
            print("\nRunning benchmark...")

            # Create test samples
            gsm8k = GSM8KDataset.create_synthetic(50)
            stories = ROCStoriesDataset.create_synthetic(50)

            r_embeddings = self._encode_batch(gsm8k.get_texts())
            c_embeddings = self._encode_batch(stories.get_texts())

            self.engine.eval()
            with torch.no_grad():
                r_out = self.engine(r_embeddings)
                c_out = self.engine(c_embeddings)

                # Separation score
                separation = self._compute_separation_score(r_embeddings, c_embeddings)

                # Classification accuracy (using centroids)
                r_centroid = r_out["ontological"].mean(dim=0)
                c_centroid = c_out["ontological"].mean(dim=0)

                # Classify by nearest centroid
                r_correct = 0
                c_correct = 0

                for i in range(len(r_out["ontological"])):
                    vec = r_out["ontological"][i]
                    r_dist = F.pairwise_distance(vec.unsqueeze(0), r_centroid.unsqueeze(0))
                    c_dist = F.pairwise_distance(vec.unsqueeze(0), c_centroid.unsqueeze(0))
                    if r_dist < c_dist:
                        r_correct += 1

                for i in range(len(c_out["ontological"])):
                    vec = c_out["ontological"][i]
                    r_dist = F.pairwise_distance(vec.unsqueeze(0), r_centroid.unsqueeze(0))
                    c_dist = F.pairwise_distance(vec.unsqueeze(0), c_centroid.unsqueeze(0))
                    if c_dist < r_dist:
                        c_correct += 1

                r_acc = r_correct / len(r_out["ontological"])
                c_acc = c_correct / len(c_out["ontological"])

            results = {
                "separation_score": separation,
                "reasoning_accuracy": r_acc,
                "creativity_accuracy": c_acc,
                "overall_accuracy": (r_acc + c_acc) / 2,
            }

            print(f"  Separation: {separation:.2%}")
            print(f"  Reasoning accuracy: {r_acc:.2%}")
            print(f"  Creativity accuracy: {c_acc:.2%}")
            print(f"  Overall accuracy: {results['overall_accuracy']:.2%}")

            return results


    def train_contrastive(
        epochs: int = 10,
        use_synthetic: bool = True,
        device: str = "auto",
        save_path: str = "model_contrastive.pt",
    ) -> ContrastiveTrainer:
        """
        Convenience function to train with contrastive loss.

        Usage:
            trainer = train_contrastive(epochs=10)
            trainer.benchmark()
        """
        config = ContrastiveConfig(
            epochs=epochs,
            device=device,
            use_huggingface=not use_synthetic,
        )

        trainer = ContrastiveTrainer(config=config)
        trainer.train(epochs=epochs, use_synthetic=use_synthetic)
        trainer.save(save_path)

        return trainer


else:
    # Stubs when PyTorch not available
    class ContrastiveTrainer:
        def __init__(self, *args, **kwargs):
            raise ImportError("PyTorch required. Install with: pip install torch")

    def train_contrastive(*args, **kwargs):
        raise ImportError("PyTorch required. Install with: pip install torch")
