"""
Evidential Ontological Engine
==============================

Bayesian uncertainty quantification using Evidential Deep Learning.
Outputs Dirichlet distribution parameters instead of point estimates.

Key benefits:
- Calibrated uncertainty scores
- Can detect out-of-distribution inputs
- Knows when to say "I don't know"
- Adaptive to new evidence

Based on: "Evidential Deep Learning to Quantify Classification Uncertainty"
https://arxiv.org/abs/1806.01768
"""

from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
import numpy as np

try:
    import torch
    import torch.nn as nn
    import torch.nn.functional as F
    PYTORCH_AVAILABLE = True
except ImportError:
    PYTORCH_AVAILABLE = False

if PYTORCH_AVAILABLE:
    from symbolu.ontological.types import LAYER_NAMES, LAYER_INDEX


    class EvidentialHead(nn.Module):
        """
        Evidential output layer that produces Dirichlet parameters.

        Instead of softmax probabilities, outputs evidence for each class.
        Uncertainty is computed from lack of total evidence.
        """

        def __init__(self, input_dim: int, num_classes: int = 12):
            super().__init__()
            self.num_classes = num_classes
            self.fc = nn.Linear(input_dim, num_classes)

        def forward(self, x: torch.Tensor) -> Dict[str, torch.Tensor]:
            """
            Forward pass producing Dirichlet parameters.

            Returns:
                Dict with:
                - evidence: Non-negative evidence for each class
                - alpha: Dirichlet concentration parameters (evidence + 1)
                - prob: Expected probabilities (alpha / sum(alpha))
                - uncertainty: Epistemic uncertainty (K / sum(alpha))
            """
            # Evidence must be non-negative
            evidence = F.softplus(self.fc(x))

            # Dirichlet parameters
            alpha = evidence + 1.0

            # Dirichlet strength (sum of alphas)
            S = torch.sum(alpha, dim=1, keepdim=True)

            # Expected probability (mean of Dirichlet)
            prob = alpha / S

            # Epistemic uncertainty: K / S
            # Higher S = more evidence = lower uncertainty
            uncertainty = self.num_classes / S.squeeze(-1)

            return {
                "evidence": evidence,
                "alpha": alpha,
                "prob": prob,
                "uncertainty": uncertainty,
            }


    class EvidentialOntologicalEngine(nn.Module):
        """
        Ontological Engine with Evidential uncertainty.

        Architecture:
            Text → Encoder (384D) → MLP → EvidentialHead → Dirichlet params
                                        → BhavaLayer → 90D relational

        Usage:
            engine = EvidentialOntologicalEngine()
            result = engine.analyze("What is truth?")

            print(result["dominant_layer"])  # O1_POTENTIAL
            print(result["confidence"])      # 0.85 (high confidence)
            print(result["uncertainty"])     # 0.15 (low uncertainty)
        """

        def __init__(
            self,
            encoder_dim: int = 384,
            hidden_dims: Tuple[int, ...] = (256, 128),
            ontological_dim: int = 10,
            bhava_dim: int = 90,
            dropout: float = 0.1,
        ):
            super().__init__()

            self.encoder_dim = encoder_dim
            self.ontological_dim = ontological_dim
            self.bhava_dim = bhava_dim

            # Build MLP layers
            layers = []
            prev_dim = encoder_dim
            for hidden_dim in hidden_dims:
                layers.extend([
                    nn.Linear(prev_dim, hidden_dim),
                    nn.LayerNorm(hidden_dim),
                    nn.GELU(),
                    nn.Dropout(dropout),
                ])
                prev_dim = hidden_dim

            self.mlp = nn.Sequential(*layers)

            # Evidential head (replaces softmax)
            self.evidential_head = EvidentialHead(
                input_dim=prev_dim,
                num_classes=ontological_dim,
            )

            # Bhava layer (relational dynamics)
            self.bhava = nn.Linear(ontological_dim, bhava_dim)

            # Prior belief (learnable, starts uniform)
            self.register_buffer(
                "prior_alpha",
                torch.ones(ontological_dim)
            )

            # Encoder (lazy loaded)
            self._encoder = None

        @property
        def encoder(self):
            if self._encoder is None:
                from symbolu.ontological.encoder import get_encoder
                self._encoder = get_encoder("minilm")
            return self._encoder

        def forward(self, x: torch.Tensor) -> Dict[str, torch.Tensor]:
            """
            Forward pass with evidential outputs.

            Args:
                x: Input embeddings (batch, encoder_dim)

            Returns:
                Dict with ontological outputs and uncertainty
            """
            # MLP projection
            hidden = self.mlp(x)

            # Evidential head
            evidential = self.evidential_head(hidden)

            # Bhava from expected probabilities
            bhava = self.bhava(evidential["prob"])

            return {
                "ontological": evidential["prob"],
                "evidence": evidential["evidence"],
                "alpha": evidential["alpha"],
                "uncertainty": evidential["uncertainty"],
                "bhava": bhava,
            }

        def analyze(self, text: str) -> Dict[str, Any]:
            """
            Analyze text with uncertainty quantification.

            Args:
                text: Input text to analyze

            Returns:
                Dict with:
                - dominant_layer: Most likely ontological layer
                - confidence: Confidence in prediction (0-1)
                - uncertainty: Epistemic uncertainty (0-1)
                - probabilities: Dict of layer -> probability
                - evidence: Total evidence collected
            """
            self.eval()

            # Encode text
            embedding = self.encoder.encode(text)
            x = torch.tensor(embedding, dtype=torch.float32).unsqueeze(0)

            if next(self.parameters()).is_cuda:
                x = x.cuda()

            with torch.no_grad():
                output = self.forward(x)

            # Extract results
            probs = output["ontological"].squeeze(0).cpu().numpy()
            uncertainty = output["uncertainty"].item()
            evidence = output["evidence"].sum().item()

            # Dominant layer
            dominant_idx = int(np.argmax(probs))
            dominant_layer = LAYER_NAMES[dominant_idx]
            confidence = float(probs[dominant_idx])

            # All probabilities
            probabilities = {
                LAYER_NAMES[i]: float(probs[i])
                for i in range(len(LAYER_NAMES))
            }

            # Uncertainty interpretation
            if uncertainty > 0.7:
                certainty_level = "very_uncertain"
            elif uncertainty > 0.4:
                certainty_level = "uncertain"
            elif uncertainty > 0.2:
                certainty_level = "moderate"
            else:
                certainty_level = "confident"

            return {
                "dominant_layer": dominant_layer,
                "confidence": confidence,
                "uncertainty": uncertainty,
                "certainty_level": certainty_level,
                "probabilities": probabilities,
                "total_evidence": evidence,
                "ontological_vector": probs.tolist(),
            }

        def compute_loss(
            self,
            output: Dict[str, torch.Tensor],
            targets: torch.Tensor,
            kl_weight: float = 0.1,
        ) -> torch.Tensor:
            """
            Evidential loss function.

            Combines:
            1. Expected cross-entropy under Dirichlet
            2. KL divergence to prior (regularization)

            Args:
                output: Forward pass output
                targets: One-hot or soft targets (batch, num_classes)
                kl_weight: Weight for KL regularization

            Returns:
                Total loss
            """
            alpha = output["alpha"]
            S = torch.sum(alpha, dim=1, keepdim=True)

            # Ensure targets sum to 1
            targets = targets / (targets.sum(dim=1, keepdim=True) + 1e-8)

            # Expected cross-entropy under Dirichlet
            # E[log(p)] = digamma(alpha) - digamma(S)
            log_likelihood = torch.sum(
                targets * (torch.digamma(alpha) - torch.digamma(S)),
                dim=1
            )
            ce_loss = -log_likelihood.mean()

            # KL divergence to uniform prior
            # Removes evidence for incorrect classes
            alpha_tilde = targets + (1 - targets) * alpha
            kl_loss = self._kl_divergence(alpha_tilde)

            return ce_loss + kl_weight * kl_loss

        def _kl_divergence(self, alpha: torch.Tensor) -> torch.Tensor:
            """KL divergence between Dirichlet(alpha) and Dirichlet(1)."""
            K = alpha.shape[1]
            alpha0 = torch.sum(alpha, dim=1, keepdim=True)

            # KL(Dir(alpha) || Dir(1))
            kl = (
                torch.lgamma(alpha0.squeeze(-1)) -
                torch.lgamma(torch.tensor(K, dtype=torch.float32, device=alpha.device)) -
                torch.sum(torch.lgamma(alpha), dim=1) +
                torch.sum((alpha - 1) * (torch.digamma(alpha) - torch.digamma(alpha0)), dim=1)
            )

            return kl.mean()

        def update_prior(self, domain_counts: Dict[str, int]) -> None:
            """
            Update prior beliefs based on observed domain frequencies.

            Args:
                domain_counts: Dict mapping domain names to observation counts
            """
            total = sum(domain_counts.values()) + len(LAYER_NAMES)  # Smoothing
            new_prior = torch.ones(self.ontological_dim)

            for domain, count in domain_counts.items():
                if domain in LAYER_INDEX:
                    idx = LAYER_INDEX[domain]
                    new_prior[idx] = count + 1  # Add-one smoothing

            # Normalize to sum to num_classes (like uniform)
            new_prior = new_prior / new_prior.sum() * self.ontological_dim
            self.prior_alpha = new_prior.to(self.prior_alpha.device)

        def summary(self) -> str:
            """Model summary."""
            total_params = sum(p.numel() for p in self.parameters())

            return f"""
============================================================
EVIDENTIAL ONTOLOGICAL ENGINE
============================================================

Architecture:
  Encoder Input: {self.encoder_dim}D
  Hidden: {[m.out_features for m in self.mlp if hasattr(m, 'out_features')]}
  Ontological Output: {self.ontological_dim}D (Dirichlet)
  Bhava Output: {self.bhava_dim}D

Key Features:
  - Evidential Deep Learning (Dirichlet outputs)
  - Uncertainty quantification
  - Adaptive prior beliefs
  - KL-regularized training

Total Parameters: {total_params:,}
============================================================
"""


    @dataclass
    class EvidentialConfig:
        """Configuration for evidential training."""
        epochs: int = 10
        batch_size: int = 32
        learning_rate: float = 1e-4
        kl_weight: float = 0.1
        kl_annealing: bool = True  # Gradually increase KL weight
        seed: int = 42
        validation_split: float = 0.2
        early_stopping_patience: int = 5


    class EvidentialTrainer:
        """
        Trainer for the Evidential Ontological Engine.

        Usage:
            trainer = EvidentialTrainer()
            trainer.train(epochs=10)
            trainer.benchmark()
        """

        def __init__(
            self,
            engine: Optional[EvidentialOntologicalEngine] = None,
            config: Optional[EvidentialConfig] = None,
        ):
            self.config = config or EvidentialConfig()
            self.engine = engine or EvidentialOntologicalEngine()

            # Set seed
            torch.manual_seed(self.config.seed)
            np.random.seed(self.config.seed)

            # Device
            self.device = torch.device(
                "cuda" if torch.cuda.is_available() else "cpu"
            )
            self.engine = self.engine.to(self.device)

            self.history = []
            self.best_val_acc = 0.0

            print(self.engine.summary())

        def train(self, epochs: int = None) -> Dict[str, Any]:
            """Train with evidential loss."""
            from symbolu.ontological.multi_domain_dataset import MultiDomainDataset
            from symbolu.ontological.encoder import get_encoder

            epochs = epochs or self.config.epochs

            # Generate dataset
            print("Generating multi-domain dataset...")
            dataset = MultiDomainDataset.generate(
                samples_per_domain=100,
                seed=self.config.seed,
            )

            # Encode
            encoder = get_encoder("minilm")
            texts = dataset.get_texts()
            labels = dataset.get_labels()

            print("Encoding texts...")
            embeddings = torch.tensor(
                np.array([encoder.encode(t) for t in texts]),
                dtype=torch.float32
            )
            labels = torch.tensor(labels, dtype=torch.float32)

            # Split
            n = len(embeddings)
            n_val = int(n * self.config.validation_split)
            indices = torch.randperm(n)

            train_emb = embeddings[indices[n_val:]].to(self.device)
            train_labels = labels[indices[n_val:]].to(self.device)
            val_emb = embeddings[indices[:n_val]].to(self.device)
            val_labels = labels[indices[:n_val]].to(self.device)

            print(f"Train: {len(train_emb)}, Val: {len(val_emb)}")

            # Optimizer
            optimizer = torch.optim.AdamW(
                self.engine.parameters(),
                lr=self.config.learning_rate,
            )

            # Training loop
            print(f"\nTraining for {epochs} epochs...")

            for epoch in range(epochs):
                self.engine.train()

                # KL annealing
                if self.config.kl_annealing:
                    kl_weight = min(1.0, epoch / (epochs / 2)) * self.config.kl_weight
                else:
                    kl_weight = self.config.kl_weight

                # Shuffle
                perm = torch.randperm(len(train_emb))
                train_emb = train_emb[perm]
                train_labels = train_labels[perm]

                total_loss = 0
                total_correct = 0

                for i in range(0, len(train_emb), self.config.batch_size):
                    batch_emb = train_emb[i:i + self.config.batch_size]
                    batch_labels = train_labels[i:i + self.config.batch_size]

                    optimizer.zero_grad()

                    output = self.engine(batch_emb)
                    loss = self.engine.compute_loss(output, batch_labels, kl_weight)

                    loss.backward()
                    optimizer.step()

                    total_loss += loss.item()

                    # Accuracy
                    pred = torch.argmax(output["ontological"], dim=1)
                    target = torch.argmax(batch_labels, dim=1)
                    total_correct += (pred == target).sum().item()

                train_acc = total_correct / len(train_emb)

                # Validation
                val_acc, val_uncertainty = self._evaluate(val_emb, val_labels)

                print(f"Epoch {epoch + 1}: train_acc={train_acc:.2%}, "
                      f"val_acc={val_acc:.2%}, val_uncertainty={val_uncertainty:.3f}")

                self.history.append({
                    "epoch": epoch + 1,
                    "train_acc": train_acc,
                    "val_acc": val_acc,
                    "val_uncertainty": val_uncertainty,
                })

                if val_acc > self.best_val_acc:
                    self.best_val_acc = val_acc

            return {"history": self.history, "best_val_acc": self.best_val_acc}

        def _evaluate(
            self,
            embeddings: torch.Tensor,
            labels: torch.Tensor,
        ) -> Tuple[float, float]:
            """Evaluate accuracy and uncertainty."""
            self.engine.eval()

            with torch.no_grad():
                output = self.engine(embeddings)

                pred = torch.argmax(output["ontological"], dim=1)
                target = torch.argmax(labels, dim=1)
                accuracy = (pred == target).float().mean().item()

                mean_uncertainty = output["uncertainty"].mean().item()

            return accuracy, mean_uncertainty

        def benchmark(self) -> Dict[str, Any]:
            """Benchmark with uncertainty analysis."""
            from symbolu.ontological.multi_domain_dataset import MultiDomainDataset

            print("\n" + "=" * 60)
            print("EVIDENTIAL BENCHMARK")
            print("=" * 60)

            # Generate test data
            test_dataset = MultiDomainDataset.generate(
                samples_per_domain=20,
                seed=self.config.seed + 1000,
            )

            results = {
                "per_domain": {},
                "uncertainties": [],
            }

            correct = {name: 0 for name in LAYER_NAMES}
            total = {name: 0 for name in LAYER_NAMES}

            for sample in test_dataset.samples:
                result = self.engine.analyze(sample.text)

                total[sample.primary_domain] += 1
                if result["dominant_layer"] == sample.primary_domain:
                    correct[sample.primary_domain] += 1

                results["uncertainties"].append(result["uncertainty"])

            # Print results
            for domain in LAYER_NAMES:
                if total[domain] > 0:
                    acc = correct[domain] / total[domain]
                    results["per_domain"][domain] = acc
                    print(f"  {domain}: {acc:.0%} ({correct[domain]}/{total[domain]})")

            overall = sum(correct.values()) / sum(total.values())
            mean_uncertainty = np.mean(results["uncertainties"])

            print(f"\nOverall accuracy: {overall:.2%}")
            print(f"Mean uncertainty: {mean_uncertainty:.3f}")

            results["overall_accuracy"] = overall
            results["mean_uncertainty"] = mean_uncertainty

            return results

        def save(self, path: str) -> None:
            """Save model."""
            torch.save({
                "engine_state": self.engine.state_dict(),
                "config": self.config,
                "history": self.history,
                "best_val_acc": self.best_val_acc,
            }, path)
            print(f"Saved to {path}")
