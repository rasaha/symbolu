"""
Ontological Engine - Multi-Domain Trainer
==========================================

Trains all 10 ontological layers with multi-label support and soft targets.

Unlike ContrastiveTrainer (2 domains), this trains on all 10 layers:
- O1_THINKING through O12_ABSOLVING
- Supports multi-label (samples can belong to multiple domains)
- Uses soft cross-entropy loss with label smoothing
- Activates the full 100D space (10D onto + 90D bhava)

Usage:
    from symbolu_core.ontological import MultiDomainTrainer

    trainer = MultiDomainTrainer()
    trainer.train(epochs=10)
    trainer.benchmark()
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
    from symbolu_core.ontological.pytorch_engine import PyTorchOntologicalEngine
    from symbolu_core.ontological.encoder import get_encoder, TextEncoder
    from symbolu_core.ontological.multi_domain_dataset import (
        MultiDomainDataset,
        DomainSample,
    )
    from symbolu_core.ontological.types import LAYER_NAMES, LAYER_INDEX

    @dataclass
    class MultiDomainConfig:
        """Configuration for multi-domain training."""
        # Training
        epochs: int = 10
        batch_size: int = 32
        learning_rate: float = 1e-4
        weight_decay: float = 0.01

        # Loss weights
        domain_loss_weight: float = 1.0
        bhava_loss_weight: float = 0.5
        purity_loss_weight: float = 0.1
        orthogonality_weight: float = 0.05

        # Label smoothing
        label_smoothing: float = 0.1

        # Device
        device: str = "auto"
        use_fp16: bool = False

        # Encoder
        encoder_type: str = "minilm"
        model_path: Optional[str] = None

        # Scheduler
        warmup_ratio: float = 0.1
        scheduler_type: str = "cosine"

        # Checkpointing
        save_every_n_epochs: int = 5
        checkpoint_dir: str = "checkpoints"

        # Logging
        log_every_n_steps: int = 10

        # Data
        samples_per_domain: int = 100

        # Reproducibility
        seed: int = 42

        # Validation and early stopping
        validation_split: float = 0.2
        early_stopping_patience: int = 5
        early_stopping_min_delta: float = 0.001

    class MultiDomainTrainer:
        """
        Multi-domain trainer for all 10 ontological layers.

        Trains the full 100D ontological space with soft multi-label targets.

        Usage:
            trainer = MultiDomainTrainer()
            trainer.train(epochs=10)
            results = trainer.benchmark()
        """

        def __init__(
            self,
            engine: Optional[PyTorchOntologicalEngine] = None,
            config: Optional[MultiDomainConfig] = None,
        ):
            self.config = config or MultiDomainConfig()

            # Set seed
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
            self.best_accuracy = 0.0
            self.best_val_accuracy = 0.0
            self.epochs_without_improvement = 0
            self.history: List[Dict[str, float]] = []

            # Mixed precision
            self.scaler = None
            if self.config.use_fp16 and self.device.type == "cuda":
                self.scaler = torch.cuda.amp.GradScaler()

            print(self.engine.summary())
            print(f"Device: {self.device}")
            print(f"Encoder: {self.encoder.name}")
            print(f"Training all 10 ontological layers")

        def _get_device(self) -> torch.device:
            """Get the best available device."""
            if self.config.device != "auto":
                return torch.device(self.config.device)

            if torch.cuda.is_available():
                return torch.device("cuda")
            elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
                return torch.device("mps")
            return torch.device("cpu")

        def _encode_batch(self, texts: List[str]) -> torch.Tensor:
            """Encode texts to embeddings."""
            embeddings = []
            batch_size = 32

            for i in range(0, len(texts), batch_size):
                batch = texts[i:i + batch_size]
                batch_emb = [self.encoder.encode(t) for t in batch]
                embeddings.extend(batch_emb)

            return torch.tensor(np.array(embeddings), dtype=torch.float32)

        def train(
            self,
            epochs: int = None,
            dataset: MultiDomainDataset = None,
        ) -> Dict[str, Any]:
            """
            Train on all 10 domains.

            Args:
                epochs: Number of training epochs
                dataset: Optional pre-generated dataset
            """
            epochs = epochs or self.config.epochs

            # Generate or use provided dataset
            if dataset is None:
                print("\nGenerating multi-domain dataset...")
                dataset = MultiDomainDataset.generate(
                    samples_per_domain=self.config.samples_per_domain,
                    seed=self.config.seed,
                )

            print(f"Dataset size: {len(dataset)} samples")
            print(f"Domain distribution: {dataset.get_domain_counts()}")

            # Prepare data
            all_texts = dataset.get_texts()
            all_labels = dataset.get_labels()

            embeddings = self._encode_batch(all_texts)
            labels = torch.tensor(all_labels, dtype=torch.float32)

            print(f"Embeddings shape: {embeddings.shape}")
            print(f"Labels shape: {labels.shape}")

            # Split train/val
            n = len(embeddings)
            n_val = int(n * self.config.validation_split)
            indices = torch.randperm(n)

            train_emb = embeddings[indices[n_val:]]
            train_labels = labels[indices[n_val:]]
            val_emb = embeddings[indices[:n_val]]
            val_labels = labels[indices[:n_val]]

            print(f"Train: {len(train_emb)}, Val: {len(val_emb)}")

            # Setup optimizer
            optimizer = AdamW(
                self.engine.parameters(),
                lr=self.config.learning_rate,
                weight_decay=self.config.weight_decay,
            )

            # Setup scheduler
            total_steps = epochs * (len(train_emb) // self.config.batch_size + 1)
            warmup_steps = int(total_steps * self.config.warmup_ratio)

            warmup_scheduler = LinearLR(
                optimizer,
                start_factor=0.1,
                end_factor=1.0,
                total_iters=warmup_steps,
            )
            main_scheduler = CosineAnnealingLR(
                optimizer,
                T_max=total_steps - warmup_steps,
            )
            scheduler = SequentialLR(
                optimizer,
                schedulers=[warmup_scheduler, main_scheduler],
                milestones=[warmup_steps],
            )

            # Training loop
            print(f"\nStarting multi-domain training for {epochs} epochs")
            print(f"Early stopping patience: {self.config.early_stopping_patience}")
            print()

            for epoch in range(epochs):
                epoch_loss, epoch_acc = self._train_epoch(
                    train_emb, train_labels, optimizer, scheduler, epoch
                )

                # Validation
                val_loss, val_acc = self._evaluate(val_emb, val_labels)

                print(f"Epoch {epoch + 1}: train_loss={epoch_loss:.4f}, "
                      f"train_acc={epoch_acc:.2%}, val_acc={val_acc:.2%}")

                # Track best based on validation
                if val_acc > self.best_val_accuracy + self.config.early_stopping_min_delta:
                    self.best_val_accuracy = val_acc
                    self.best_accuracy = epoch_acc
                    self.epochs_without_improvement = 0
                    self._save_checkpoint("best")
                else:
                    self.epochs_without_improvement += 1
                    print(f"  No improvement for {self.epochs_without_improvement} epoch(s)")

                # Save periodic checkpoint
                if (epoch + 1) % self.config.save_every_n_epochs == 0:
                    self._save_checkpoint(f"epoch_{epoch + 1}")

                self.history.append({
                    "epoch": epoch + 1,
                    "train_loss": epoch_loss,
                    "train_accuracy": epoch_acc,
                    "val_loss": val_loss,
                    "val_accuracy": val_acc,
                })

                # Early stopping
                if self.epochs_without_improvement >= self.config.early_stopping_patience:
                    print(f"\nEarly stopping after {epoch + 1} epochs")
                    print(f"Best validation accuracy: {self.best_val_accuracy:.2%}")
                    break

            return {
                "history": self.history,
                "best_accuracy": self.best_accuracy,
                "best_val_accuracy": self.best_val_accuracy,
            }

        def _train_epoch(
            self,
            embeddings: torch.Tensor,
            labels: torch.Tensor,
            optimizer: AdamW,
            scheduler: Any,
            epoch: int,
        ) -> Tuple[float, float]:
            """Train one epoch."""
            self.engine.train()

            # Shuffle
            indices = torch.randperm(len(embeddings))
            embeddings = embeddings[indices]
            labels = labels[indices]

            total_loss = 0.0
            total_correct = 0
            total_samples = 0
            batch_size = self.config.batch_size

            for i in range(0, len(embeddings), batch_size):
                batch_emb = embeddings[i:i + batch_size].to(self.device)
                batch_labels = labels[i:i + batch_size].to(self.device)

                optimizer.zero_grad()

                # Forward pass
                onto_output = self.engine.mlp(batch_emb)
                bhava_output = self.engine.bhava(onto_output)

                # Domain classification loss (soft cross-entropy)
                # Normalize labels to sum to 1 for each sample
                normalized_labels = batch_labels / (batch_labels.sum(dim=1, keepdim=True) + 1e-8)

                # Label smoothing
                if self.config.label_smoothing > 0:
                    smooth = self.config.label_smoothing
                    normalized_labels = (1 - smooth) * normalized_labels + smooth / 10

                log_probs = F.log_softmax(onto_output, dim=1)
                domain_loss = -torch.sum(normalized_labels * log_probs, dim=1).mean()

                # Bhava consistency loss (bhava should reflect onto relationships)
                bhava_target = self._compute_bhava_target(onto_output)
                bhava_loss = F.mse_loss(bhava_output, bhava_target)

                # Purity loss (encourage sparse activations)
                onto_probs = F.softmax(onto_output, dim=1)
                purity_loss = -torch.mean(torch.sum(onto_probs * torch.log(onto_probs + 1e-8), dim=1))
                purity_loss = purity_loss / np.log(10)  # Normalize

                # Orthogonality loss (decorrelate dimensions)
                batch_centered = onto_output - onto_output.mean(dim=0)
                cov = torch.mm(batch_centered.t(), batch_centered) / (batch_centered.shape[0] - 1)
                eye = torch.eye(10, device=self.device)
                ortho_loss = torch.norm(cov - torch.diag(torch.diag(cov))) / 10

                # Total loss
                loss = (
                    self.config.domain_loss_weight * domain_loss +
                    self.config.bhava_loss_weight * bhava_loss +
                    self.config.purity_loss_weight * purity_loss +
                    self.config.orthogonality_weight * ortho_loss
                )

                loss.backward()
                optimizer.step()
                scheduler.step()

                total_loss += loss.item()

                # Accuracy (check if predicted domain matches primary domain)
                predicted = torch.argmax(onto_output, dim=1)
                targets = torch.argmax(batch_labels, dim=1)
                total_correct += (predicted == targets).sum().item()
                total_samples += len(batch_labels)

                self.global_step += 1

            avg_loss = total_loss / (len(embeddings) // batch_size + 1)
            accuracy = total_correct / total_samples

            return avg_loss, accuracy

        def _compute_bhava_target(self, onto_output: torch.Tensor) -> torch.Tensor:
            """Compute bhava target from ontological output."""
            # Bhava is 90D representing interactions between ontological layers
            # For each pair (i, j), compute interaction features
            batch_size = onto_output.shape[0]
            bhava = torch.zeros(batch_size, 90, device=self.device)

            idx = 0
            for i in range(9):
                for j in range(10):
                    # Interaction between adjacent layers
                    if j == 0:
                        bhava[:, idx] = onto_output[:, i] * onto_output[:, i + 1]
                    else:
                        bhava[:, idx] = onto_output[:, i] * onto_output[:, (i + j) % 10]
                    idx += 1

            return bhava

        def _evaluate(
            self,
            embeddings: torch.Tensor,
            labels: torch.Tensor,
        ) -> Tuple[float, float]:
            """Evaluate on validation set."""
            self.engine.eval()

            with torch.no_grad():
                embeddings = embeddings.to(self.device)
                labels = labels.to(self.device)

                onto_output = self.engine.mlp(embeddings)

                # Loss
                normalized_labels = labels / (labels.sum(dim=1, keepdim=True) + 1e-8)
                log_probs = F.log_softmax(onto_output, dim=1)
                loss = -torch.sum(normalized_labels * log_probs, dim=1).mean()

                # Accuracy
                predicted = torch.argmax(onto_output, dim=1)
                targets = torch.argmax(labels, dim=1)
                accuracy = (predicted == targets).float().mean().item()

            return loss.item(), accuracy

        def _save_checkpoint(self, name: str) -> None:
            """Save a checkpoint."""
            checkpoint_dir = Path(self.config.checkpoint_dir)
            checkpoint_dir.mkdir(parents=True, exist_ok=True)

            path = checkpoint_dir / f"multi_domain_{name}.pt"
            torch.save({
                "engine_state": self.engine.state_dict(),
                "config": self.config,
                "global_step": self.global_step,
                "best_accuracy": self.best_accuracy,
                "best_val_accuracy": self.best_val_accuracy,
                "history": self.history,
            }, path)

        def save(self, path: str) -> None:
            """Save the trained model."""
            torch.save({
                "engine_state": self.engine.state_dict(),
                "config": self.config,
                "best_accuracy": self.best_accuracy,
                "best_val_accuracy": self.best_val_accuracy,
                "history": self.history,
            }, path)
            print(f"Model saved to {path}")

        def benchmark(self) -> Dict[str, Any]:
            """Run benchmark on all 10 domains."""
            print("\n" + "=" * 60)
            print("MULTI-DOMAIN BENCHMARK")
            print("=" * 60)

            self.engine.eval()

            # Generate test samples
            test_dataset = MultiDomainDataset.generate(
                samples_per_domain=20,
                seed=self.config.seed + 1000,  # Different seed
            )

            results = {
                "per_domain": {},
                "confusion_matrix": torch.zeros(10, 10, dtype=torch.int64),
            }

            correct_per_domain = {name: 0 for name in LAYER_NAMES}
            total_per_domain = {name: 0 for name in LAYER_NAMES}

            with torch.no_grad():
                for sample in test_dataset.samples:
                    emb = torch.tensor(
                        self.encoder.encode(sample.text),
                        dtype=torch.float32
                    ).unsqueeze(0).to(self.device)

                    onto_output = self.engine.mlp(emb)
                    predicted_idx = torch.argmax(onto_output, dim=1).item()
                    predicted_domain = LAYER_NAMES[predicted_idx]

                    true_idx = LAYER_INDEX[sample.primary_domain]

                    total_per_domain[sample.primary_domain] += 1
                    if predicted_domain == sample.primary_domain:
                        correct_per_domain[sample.primary_domain] += 1

                    results["confusion_matrix"][true_idx, predicted_idx] += 1

            # Compute per-domain accuracy
            for domain in LAYER_NAMES:
                if total_per_domain[domain] > 0:
                    acc = correct_per_domain[domain] / total_per_domain[domain]
                    results["per_domain"][domain] = acc
                    print(f"  {domain}: {acc:.0%} ({correct_per_domain[domain]}/{total_per_domain[domain]})")

            # Overall accuracy
            total_correct = sum(correct_per_domain.values())
            total = sum(total_per_domain.values())
            results["overall_accuracy"] = total_correct / total

            print(f"\nOverall accuracy: {results['overall_accuracy']:.2%}")

            return results


    def train_multi_domain(
        epochs: int = 10,
        samples_per_domain: int = 100,
        seed: int = 42,
        output_path: str = "model_multi_domain.pt",
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Convenience function to train multi-domain model.

        Args:
            epochs: Number of training epochs
            samples_per_domain: Samples per domain
            seed: Random seed
            output_path: Where to save the model
            **kwargs: Additional config options

        Returns:
            Training results
        """
        config = MultiDomainConfig(
            epochs=epochs,
            samples_per_domain=samples_per_domain,
            seed=seed,
            **kwargs,
        )

        trainer = MultiDomainTrainer(config=config)
        result = trainer.train(epochs=epochs)
        trainer.save(output_path)

        return result
