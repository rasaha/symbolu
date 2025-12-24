"""
Ontological Engine - PyTorch Training Pipeline
================================================

GPU-accelerated training for the 100D ontological engine.

Features:
- DistilBERT/SentenceTransformer encoding
- Mixed precision training (FP16)
- Gradient accumulation
- Learning rate scheduling
- Checkpointing and resumption
- TensorBoard logging
- Early stopping

Usage:
    trainer = PyTorchTrainer(engine)
    trainer.train(train_loader, val_loader, epochs=10)
    trainer.save("model.pt")
"""

from typing import List, Dict, Optional, Tuple, Any, Iterator
from dataclasses import dataclass, field
from pathlib import Path
import json
import time

from symbolu.ontological.types import TrainingExample, LAYER_NAMES, LAYER_INDEX
from symbolu.ontological.data_loader import MixedDataLoader

# Check PyTorch availability
try:
    import torch
    import torch.nn as nn
    from torch.utils.data import Dataset, DataLoader
    from torch.optim import AdamW
    from torch.optim.lr_scheduler import CosineAnnealingLR, LinearLR, SequentialLR
    PYTORCH_AVAILABLE = True
except ImportError:
    PYTORCH_AVAILABLE = False


if PYTORCH_AVAILABLE:
    from symbolu.ontological.pytorch_engine import PyTorchOntologicalEngine
    from symbolu.ontological.encoder import get_encoder, TextEncoder


    class OntologicalDataset(Dataset):
        """
        PyTorch Dataset for ontological training.

        Pre-encodes all texts using the text encoder for efficiency.
        """

        def __init__(
            self,
            examples: List[TrainingExample],
            encoder: TextEncoder,
            cache_embeddings: bool = True,
        ):
            self.examples = examples
            self.encoder = encoder
            self.cache_embeddings = cache_embeddings
            self._embedding_cache: Dict[int, torch.Tensor] = {}

            if cache_embeddings:
                print(f"Pre-encoding {len(examples)} examples...")
                self._precompute_embeddings()

        def _precompute_embeddings(self):
            """Pre-compute all embeddings for efficiency."""
            batch_size = 32
            for i in range(0, len(self.examples), batch_size):
                batch = self.examples[i:i + batch_size]
                texts = [ex.text for ex in batch]
                embeddings = self.encoder.encode_batch(texts)

                for j, emb in enumerate(embeddings):
                    self._embedding_cache[i + j] = torch.tensor(emb, dtype=torch.float32)

            print(f"Cached {len(self._embedding_cache)} embeddings")

        def __len__(self) -> int:
            return len(self.examples)

        def __getitem__(self, idx: int) -> Dict[str, torch.Tensor]:
            example = self.examples[idx]

            # Get embedding
            if idx in self._embedding_cache:
                embedding = self._embedding_cache[idx]
            else:
                emb = self.encoder.encode(example.text)
                embedding = torch.tensor(emb, dtype=torch.float32)

            # Build target tensors
            item = {"embedding": embedding}

            # Ontological targets (10D)
            onto_target = torch.full((10,), float("nan"))
            if example.dimension_labels:
                for layer_name, value in example.dimension_labels.items():
                    if layer_name in LAYER_INDEX:
                        onto_target[LAYER_INDEX[layer_name]] = value
            item["onto_target"] = onto_target

            # Reasoning target
            if example.reasoning_label is not None:
                item["reasoning_target"] = torch.tensor(example.reasoning_label)
            else:
                item["reasoning_target"] = torch.tensor(float("nan"))

            # Creativity target
            if example.creativity_label is not None:
                item["creativity_target"] = torch.tensor(example.creativity_label)
            else:
                item["creativity_target"] = torch.tensor(float("nan"))

            return item


    def collate_fn(batch: List[Dict]) -> Dict[str, torch.Tensor]:
        """Custom collate function for batching."""
        return {
            "embedding": torch.stack([b["embedding"] for b in batch]),
            "onto_target": torch.stack([b["onto_target"] for b in batch]),
            "reasoning_target": torch.stack([b["reasoning_target"] for b in batch]),
            "creativity_target": torch.stack([b["creativity_target"] for b in batch]),
        }


    @dataclass
    class TrainerConfig:
        """Configuration for PyTorch trainer."""
        # Optimization
        learning_rate: float = 2e-5
        weight_decay: float = 0.01
        warmup_ratio: float = 0.1
        max_grad_norm: float = 1.0

        # Training
        epochs: int = 10
        batch_size: int = 32
        gradient_accumulation_steps: int = 1

        # Loss weights
        purity_weight: float = 0.1
        orthogonality_weight: float = 0.05

        # Encoder
        encoder_type: str = "auto"  # "auto", "distilbert", "hash"

        # Device
        device: str = "auto"  # "auto", "cuda", "mps", "cpu"

        # Mixed precision
        use_fp16: bool = True

        # Checkpointing
        checkpoint_dir: str = "checkpoints/ontological_pytorch"
        save_every_n_epochs: int = 1

        # Logging
        log_every_n_steps: int = 10

        # Early stopping
        patience: int = 3
        min_delta: float = 0.001


    class PyTorchTrainer:
        """
        PyTorch trainer for the 100D ontological engine.

        Handles:
        - GPU/MPS/CPU device management
        - Mixed precision training
        - Gradient accumulation
        - Learning rate scheduling
        - Checkpointing
        - Early stopping

        Usage:
            engine = PyTorchOntologicalEngine()
            trainer = PyTorchTrainer(engine, config)

            # From RAG data
            loader = MixedDataLoader().add_rag("data/rag").add_synthetic(500)
            train_examples, val_examples = loader.split()

            # Train
            trainer.train(train_examples, val_examples)

            # Save
            trainer.save("model.pt")
        """

        def __init__(
            self,
            engine: Optional[PyTorchOntologicalEngine] = None,
            config: Optional[TrainerConfig] = None,
        ):
            self.config = config or TrainerConfig()
            self.engine = engine or PyTorchOntologicalEngine()

            # Setup device
            self.device = self._get_device()
            self.engine = self.engine.to(self.device)

            # Setup encoder
            self.encoder = get_encoder(self.config.encoder_type)

            # Training state
            self.global_step = 0
            self.best_val_loss = float("inf")
            self.patience_counter = 0
            self.history: List[Dict[str, float]] = []

            # Mixed precision
            self.scaler = None
            if self.config.use_fp16 and self.device.type == "cuda":
                self.scaler = torch.cuda.amp.GradScaler()

            print(self.engine.summary())
            print(f"Device: {self.device}")
            print(f"Encoder: {self.encoder.name}")

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

        def train(
            self,
            train_examples: List[TrainingExample],
            val_examples: Optional[List[TrainingExample]] = None,
        ) -> Dict[str, Any]:
            """
            Train the ontological engine.

            Args:
                train_examples: Training data
                val_examples: Optional validation data

            Returns:
                Training history
            """
            # Create datasets
            train_dataset = OntologicalDataset(train_examples, self.encoder)
            train_loader = DataLoader(
                train_dataset,
                batch_size=self.config.batch_size,
                shuffle=True,
                collate_fn=collate_fn,
                num_workers=0,
            )

            val_loader = None
            if val_examples:
                val_dataset = OntologicalDataset(val_examples, self.encoder)
                val_loader = DataLoader(
                    val_dataset,
                    batch_size=self.config.batch_size,
                    shuffle=False,
                    collate_fn=collate_fn,
                    num_workers=0,
                )

            # Setup optimizer
            optimizer = AdamW(
                self.engine.parameters(),
                lr=self.config.learning_rate,
                weight_decay=self.config.weight_decay,
            )

            # Setup scheduler
            total_steps = len(train_loader) * self.config.epochs
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
            print(f"\nStarting training for {self.config.epochs} epochs")
            print(f"  Train examples: {len(train_examples)}")
            print(f"  Val examples: {len(val_examples) if val_examples else 0}")
            print(f"  Steps per epoch: {len(train_loader)}")
            print()

            for epoch in range(self.config.epochs):
                epoch_loss = self._train_epoch(
                    train_loader, optimizer, scheduler, epoch
                )

                # Validation
                val_loss = None
                if val_loader:
                    val_loss = self._validate(val_loader)
                    print(f"Epoch {epoch + 1}: train_loss={epoch_loss:.4f}, val_loss={val_loss:.4f}")

                    # Early stopping
                    if val_loss < self.best_val_loss - self.config.min_delta:
                        self.best_val_loss = val_loss
                        self.patience_counter = 0
                        self._save_checkpoint("best")
                    else:
                        self.patience_counter += 1
                        if self.patience_counter >= self.config.patience:
                            print(f"Early stopping at epoch {epoch + 1}")
                            break
                else:
                    print(f"Epoch {epoch + 1}: train_loss={epoch_loss:.4f}")

                # Save checkpoint
                if (epoch + 1) % self.config.save_every_n_epochs == 0:
                    self._save_checkpoint(f"epoch_{epoch + 1}")

                self.history.append({
                    "epoch": epoch + 1,
                    "train_loss": epoch_loss,
                    "val_loss": val_loss,
                })

            return {"history": self.history, "best_val_loss": self.best_val_loss}

        def _train_epoch(
            self,
            loader: DataLoader,
            optimizer: AdamW,
            scheduler: Any,
            epoch: int,
        ) -> float:
            """Train for one epoch."""
            self.engine.train()
            total_loss = 0.0
            num_batches = 0

            optimizer.zero_grad()

            for step, batch in enumerate(loader):
                # Move to device
                embeddings = batch["embedding"].to(self.device)
                targets = {
                    "ontological": batch["onto_target"].to(self.device),
                    "reasoning": batch["reasoning_target"].to(self.device),
                    "creativity": batch["creativity_target"].to(self.device),
                }

                # Forward pass (with mixed precision if enabled)
                if self.scaler:
                    with torch.cuda.amp.autocast():
                        output = self.engine(embeddings)
                        loss = self.engine.compute_loss(
                            output, targets,
                            purity_weight=self.config.purity_weight,
                            orthogonality_weight=self.config.orthogonality_weight,
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
                    output = self.engine(embeddings)
                    loss = self.engine.compute_loss(
                        output, targets,
                        purity_weight=self.config.purity_weight,
                        orthogonality_weight=self.config.orthogonality_weight,
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
                num_batches += 1
                self.global_step += 1

                # Logging
                if self.global_step % self.config.log_every_n_steps == 0:
                    avg_loss = total_loss / num_batches
                    lr = scheduler.get_last_lr()[0]
                    print(f"  Step {self.global_step}: loss={avg_loss:.4f}, lr={lr:.2e}")

            return total_loss / num_batches

        def _validate(self, loader: DataLoader) -> float:
            """Validate on validation set."""
            self.engine.eval()
            total_loss = 0.0
            num_batches = 0

            with torch.no_grad():
                for batch in loader:
                    embeddings = batch["embedding"].to(self.device)
                    targets = {
                        "ontological": batch["onto_target"].to(self.device),
                        "reasoning": batch["reasoning_target"].to(self.device),
                        "creativity": batch["creativity_target"].to(self.device),
                    }

                    output = self.engine(embeddings)
                    loss = self.engine.compute_loss(
                        output, targets,
                        purity_weight=self.config.purity_weight,
                        orthogonality_weight=self.config.orthogonality_weight,
                    )

                    total_loss += loss.item()
                    num_batches += 1

            return total_loss / num_batches

        def _save_checkpoint(self, name: str) -> None:
            """Save model checkpoint."""
            checkpoint_dir = Path(self.config.checkpoint_dir)
            checkpoint_dir.mkdir(parents=True, exist_ok=True)

            path = checkpoint_dir / f"{name}.pt"
            torch.save({
                "engine_state": self.engine.state_dict(),
                "global_step": self.global_step,
                "best_val_loss": self.best_val_loss,
                "config": self.config.__dict__,
                "history": self.history,
            }, path)

            print(f"Saved checkpoint: {path}")

        def load_checkpoint(self, path: str) -> None:
            """Load model from checkpoint."""
            checkpoint = torch.load(path, map_location=self.device)
            self.engine.load_state_dict(checkpoint["engine_state"])
            self.global_step = checkpoint.get("global_step", 0)
            self.best_val_loss = checkpoint.get("best_val_loss", float("inf"))
            self.history = checkpoint.get("history", [])

            print(f"Loaded checkpoint: {path}")

        def save(self, path: str) -> None:
            """Save complete model."""
            torch.save({
                "engine_state": self.engine.state_dict(),
                "config": self.config.__dict__,
            }, path)

        def analyze(self, text: str) -> Dict[str, Any]:
            """Analyze a single text."""
            return self.engine.analyze(text)


    def train_from_rag(
        rag_dir: str = "data/rag",
        synthetic_count: int = 500,
        epochs: int = 10,
        device: str = "auto",
    ) -> PyTorchTrainer:
        """
        Convenience function to train from RAG database.

        Usage:
            trainer = train_from_rag("data/rag", epochs=10)
            trainer.save("model.pt")
        """
        # Load data
        loader = MixedDataLoader()
        loader.add_rag(rag_dir)
        loader.add_synthetic(synthetic_count)

        train_examples, val_examples = loader.split(val_ratio=0.2)

        print(f"Loaded {len(loader)} total examples")
        print(f"  Train: {len(train_examples)}")
        print(f"  Val: {len(val_examples)}")

        # Create engine and trainer
        engine = PyTorchOntologicalEngine()
        config = TrainerConfig(epochs=epochs, device=device)
        trainer = PyTorchTrainer(engine, config)

        # Train
        trainer.train(train_examples, val_examples)

        return trainer


else:
    # Stubs when PyTorch not available
    class PyTorchTrainer:
        def __init__(self, *args, **kwargs):
            raise ImportError("PyTorch required. Install with: pip install torch")

    def train_from_rag(*args, **kwargs):
        raise ImportError("PyTorch required. Install with: pip install torch")
