"""
Unified Ontological Engine
===========================

The best of all worlds - combines:
- 12-class classification (from multi_domain)
- Reasoning/Creativity task heads (from contrastive)
- Bayesian uncertainty quantification (from evidential)
- Bhava relationships (144D inter-layer dynamics - NEW ARCHITECTURE)

ARCHITECTURAL EVOLUTION:
------------------------
OLD (Deprecated):
    - BhavaLayer: 120D relational space from sub-layers
    - Sequential relationships between adjacent layers only
    - ~34% computational overhead

NEW (Current):
    - InterLayerBhavaEngine: 144D inter-layer relationships
    - All-to-all relationship modeling
    - Based on Vedic Drishti (aspect) patterns
    - ~5% computational overhead
    - Richer relationship space

Usage:
    # NEW Architecture (Recommended)
    from symbolu_core.ontological import UnifiedOntologicalEngineV2

    engine = UnifiedOntologicalEngineV2()
    result = engine.analyze("What is truth?")

    # All outputs available:
    print(result["dominant_layer"])     # O1_POTENTIAL
    print(result["confidence"])         # 0.92
    print(result["uncertainty"])        # 0.15
    print(result["coherence"])          # 0.85 (NEW: global coherence)
    print(result["reasoning_score"])    # 0.35
    print(result["creativity_score"])   # 0.28
    print(result["bhava_vector"])       # 144D inter-layer relationships

    # OLD Architecture (Deprecated)
    from symbolu_core.ontological import UnifiedOntologicalEngine

    engine = UnifiedOntologicalEngine()  # Uses 120D sub-layer architecture
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
    from symbolu_core.ontological.types import (
        LAYER_NAMES, LAYER_INDEX,
        REASONING_LAYERS, CREATIVITY_LAYERS,
    )


    class EvidentialLayer(nn.Module):
        """Evidential output layer producing Dirichlet parameters."""

        def __init__(self, input_dim: int, num_classes: int = 12):
            super().__init__()
            self.num_classes = num_classes
            self.fc = nn.Linear(input_dim, num_classes)

        def forward(self, x: torch.Tensor) -> Dict[str, torch.Tensor]:
            evidence = F.softplus(self.fc(x))
            alpha = evidence + 1.0
            S = torch.sum(alpha, dim=1, keepdim=True)
            prob = alpha / S
            uncertainty = self.num_classes / S.squeeze(-1)

            return {
                "evidence": evidence,
                "alpha": alpha,
                "prob": prob,
                "uncertainty": uncertainty,
            }


    # Import the new inter-layer relationship architecture
    from symbolu_core.ontological.bhava_relationships import (
        InterLayerBhavaEngine,
        BhavaRelationshipModule,
        get_relationship_meaning,
        BHAVA_SIGNIFICANCES,
    )

    class BhavaLayer(nn.Module):
        """
        [DEPRECATED] Bhava layer computing 120D relational dynamics from 12D ontological.

        WARNING: This class uses the old sub-layer architecture.
        For new implementations, use InterLayerBhavaEngine instead.

        Models interactions between ontological layer pairs.
        """

        def __init__(self, ontological_dim: int = 12, bhava_dim: int = 120):
            super().__init__()
            self.ontological_dim = ontological_dim
            self.bhava_dim = bhava_dim

            # Learnable interaction weights
            self.interaction = nn.Linear(ontological_dim, bhava_dim)
            self.gate = nn.Linear(ontological_dim, bhava_dim)

        def forward(self, onto: torch.Tensor) -> torch.Tensor:
            """
            Compute bhava from ontological vector.

            Uses gated interaction to model relational dynamics.
            """
            interaction = self.interaction(onto)
            gate = torch.sigmoid(self.gate(onto))
            bhava = interaction * gate
            return torch.tanh(bhava)


    class TaskHead(nn.Module):
        """Task-specific head (reasoning or creativity)."""

        def __init__(
            self,
            input_dim: int,
            layer_indices: Tuple[int, ...],
            hidden_dim: int = 64,
        ):
            super().__init__()
            self.layer_indices = layer_indices

            self.mlp = nn.Sequential(
                nn.Linear(input_dim + len(layer_indices), hidden_dim),
                nn.GELU(),
                nn.Dropout(0.1),
                nn.Linear(hidden_dim, 1),
                nn.Sigmoid(),
            )

        def forward(
            self,
            hidden: torch.Tensor,
            onto_probs: torch.Tensor,
        ) -> torch.Tensor:
            # Extract relevant ontological dimensions
            relevant = onto_probs[:, list(self.layer_indices)]
            combined = torch.cat([hidden, relevant], dim=1)
            return self.mlp(combined).squeeze(-1)


    class UnifiedOntologicalEngine(nn.Module):
        """
        Unified Ontological Engine with all features.

        Architecture:
            Text → Encoder (384D) → MLP → Hidden (128D)
                                        ↓
                              EvidentialLayer → 12D + Uncertainty
                                        ↓
                              BhavaLayer → 120D relational
                                        ↓
                              ┌─────────┴─────────┐
                              ↓                   ↓
                        ReasoningHead       CreativityHead

        Features:
        - 12-class evidential classification with uncertainty
        - 120D Bhava relational dynamics
        - Reasoning and Creativity task scores
        - Adaptive prior beliefs
        """

        def __init__(
            self,
            encoder_dim: int = 384,
            hidden_dims: Tuple[int, ...] = (256, 128),
            ontological_dim: int = 12,
            bhava_dim: int = 120,
            dropout: float = 0.1,
        ):
            super().__init__()

            self.encoder_dim = encoder_dim
            self.ontological_dim = ontological_dim
            self.bhava_dim = bhava_dim

            # Build MLP backbone
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

            self.backbone = nn.Sequential(*layers)
            self.hidden_dim = prev_dim

            # Evidential classification head
            self.evidential = EvidentialLayer(prev_dim, ontological_dim)

            # Bhava layer (relational dynamics)
            self.bhava = BhavaLayer(ontological_dim, bhava_dim)

            # Task heads
            self.reasoning_head = TaskHead(
                input_dim=prev_dim,
                layer_indices=REASONING_LAYERS,
            )
            self.creativity_head = TaskHead(
                input_dim=prev_dim,
                layer_indices=CREATIVITY_LAYERS,
            )

            # Encoder (lazy loaded)
            self._encoder = None

        @property
        def encoder(self):
            if self._encoder is None:
                from symbolu_core.ontological.encoder import get_encoder
                self._encoder = get_encoder("minilm")
            return self._encoder

        def forward(self, x: torch.Tensor) -> Dict[str, torch.Tensor]:
            """
            Full forward pass.

            Args:
                x: Input embeddings (batch, encoder_dim)

            Returns:
                Dict with all outputs
            """
            # Backbone
            hidden = self.backbone(x)

            # Evidential classification
            evidential = self.evidential(hidden)

            # Bhava from expected probabilities
            bhava = self.bhava(evidential["prob"])

            # Task scores
            reasoning = self.reasoning_head(hidden, evidential["prob"])
            creativity = self.creativity_head(hidden, evidential["prob"])

            return {
                # Classification
                "ontological": evidential["prob"],
                "evidence": evidential["evidence"],
                "alpha": evidential["alpha"],
                "uncertainty": evidential["uncertainty"],
                # Relational
                "bhava": bhava,
                # Task scores
                "reasoning_score": reasoning,
                "creativity_score": creativity,
                # Hidden state (for downstream)
                "hidden": hidden,
            }

        def analyze(self, text: str) -> Dict[str, Any]:
            """
            Analyze text with full output.

            Returns comprehensive analysis including:
            - Dominant layer and confidence
            - Uncertainty quantification
            - Reasoning and creativity scores
            - Full 132D vector (12D onto + 120D bhava)
            """
            self.eval()

            # Encode
            embedding = self.encoder.encode(text)
            x = torch.tensor(embedding, dtype=torch.float32).unsqueeze(0)

            device = next(self.parameters()).device
            x = x.to(device)

            with torch.no_grad():
                output = self.forward(x)

            # Extract results
            probs = output["ontological"].squeeze(0).cpu().numpy()
            uncertainty = output["uncertainty"].item()
            bhava = output["bhava"].squeeze(0).cpu().numpy()
            reasoning = output["reasoning_score"].item()
            creativity = output["creativity_score"].item()

            # Dominant layer
            dominant_idx = int(np.argmax(probs))
            dominant_layer = LAYER_NAMES[dominant_idx]
            confidence = float(probs[dominant_idx])

            # All probabilities
            probabilities = {
                LAYER_NAMES[i]: float(probs[i])
                for i in range(len(LAYER_NAMES))
            }

            # Certainty level
            if uncertainty > 0.7:
                certainty_level = "very_uncertain"
            elif uncertainty > 0.4:
                certainty_level = "uncertain"
            elif uncertainty > 0.2:
                certainty_level = "moderate"
            else:
                certainty_level = "confident"

            # Full 132D vector
            full_vector = np.concatenate([probs, bhava])

            return {
                # Classification
                "dominant_layer": dominant_layer,
                "confidence": confidence,
                "probabilities": probabilities,
                # Uncertainty
                "uncertainty": uncertainty,
                "certainty_level": certainty_level,
                # Task scores
                "reasoning_score": reasoning,
                "creativity_score": creativity,
                # Vectors
                "ontological_vector": probs.tolist(),
                "bhava_vector": bhava.tolist(),
                "full_100d_vector": full_vector.tolist(),
            }

        def compute_loss(
            self,
            output: Dict[str, torch.Tensor],
            targets: torch.Tensor,
            reasoning_targets: Optional[torch.Tensor] = None,
            creativity_targets: Optional[torch.Tensor] = None,
            kl_weight: float = 0.1,
            bhava_weight: float = 0.3,
            task_weight: float = 0.2,
        ) -> Dict[str, torch.Tensor]:
            """
            Compute unified loss.

            Combines:
            1. Evidential classification loss
            2. KL regularization
            3. Bhava consistency loss
            4. Task head losses (if targets provided)
            """
            alpha = output["alpha"]
            S = torch.sum(alpha, dim=1, keepdim=True)

            # Normalize targets
            targets = targets / (targets.sum(dim=1, keepdim=True) + 1e-8)

            # 1. Evidential cross-entropy
            log_likelihood = torch.sum(
                targets * (torch.digamma(alpha) - torch.digamma(S)),
                dim=1
            )
            ce_loss = -log_likelihood.mean()

            # 2. KL divergence to prior
            alpha_tilde = targets + (1 - targets) * alpha
            kl_loss = self._kl_divergence(alpha_tilde)

            # 3. Bhava consistency loss
            # Bhava should be consistent with ontological probabilities
            onto_probs = output["ontological"]
            bhava = output["bhava"]
            bhava_target = self._compute_bhava_target(onto_probs)
            bhava_loss = F.mse_loss(bhava, bhava_target)

            # 4. Task losses (if targets provided)
            task_loss = torch.tensor(0.0, device=alpha.device)
            if reasoning_targets is not None:
                task_loss = task_loss + F.binary_cross_entropy(
                    output["reasoning_score"], reasoning_targets
                )
            if creativity_targets is not None:
                task_loss = task_loss + F.binary_cross_entropy(
                    output["creativity_score"], creativity_targets
                )

            # Total loss
            total_loss = (
                ce_loss +
                kl_weight * kl_loss +
                bhava_weight * bhava_loss +
                task_weight * task_loss
            )

            return {
                "total": total_loss,
                "ce": ce_loss,
                "kl": kl_loss,
                "bhava": bhava_loss,
                "task": task_loss,
            }

        def _kl_divergence(self, alpha: torch.Tensor) -> torch.Tensor:
            """KL divergence between Dirichlet(alpha) and Dirichlet(1)."""
            K = alpha.shape[1]
            alpha0 = torch.sum(alpha, dim=1, keepdim=True)

            kl = (
                torch.lgamma(alpha0.squeeze(-1)) -
                torch.lgamma(torch.tensor(K, dtype=torch.float32, device=alpha.device)) -
                torch.sum(torch.lgamma(alpha), dim=1) +
                torch.sum((alpha - 1) * (torch.digamma(alpha) - torch.digamma(alpha0)), dim=1)
            )

            return kl.mean()

        def _compute_bhava_target(self, onto: torch.Tensor) -> torch.Tensor:
            """Compute bhava target from ontological probabilities."""
            batch_size = onto.shape[0]
            device = onto.device
            bhava = torch.zeros(batch_size, 90, device=device)

            idx = 0
            for i in range(9):
                for j in range(10):
                    bhava[:, idx] = onto[:, i] * onto[:, (i + j + 1) % 10]
                    idx += 1

            return bhava

        def summary(self) -> str:
            """Model summary."""
            total_params = sum(p.numel() for p in self.parameters())

            return f"""
============================================================
UNIFIED ONTOLOGICAL ENGINE
============================================================

Architecture:
  Encoder Input: {self.encoder_dim}D (MiniLM)
  Hidden: {self.hidden_dim}D
  Ontological Output: {self.ontological_dim}D (Evidential/Dirichlet)
  Bhava Output: {self.bhava_dim}D (Relational)
  Full Vector: {self.ontological_dim + self.bhava_dim}D

Features:
  ✓ 12-class evidential classification
  ✓ Bayesian uncertainty quantification
  ✓ 120D Bhava relational dynamics
  ✓ Reasoning head (layers {REASONING_LAYERS})
  ✓ Creativity head (layers {CREATIVITY_LAYERS})

Total Parameters: {total_params:,}
============================================================
"""


    @dataclass
    class UnifiedConfig:
        """Configuration for unified training."""
        epochs: int = 15
        batch_size: int = 32
        learning_rate: float = 1e-4
        weight_decay: float = 0.01

        # Loss weights
        kl_weight: float = 0.1
        bhava_weight: float = 0.3
        task_weight: float = 0.2
        kl_annealing: bool = True

        # Training
        seed: int = 42
        validation_split: float = 0.2
        early_stopping_patience: int = 5

        # Device
        device: str = "auto"


    class UnifiedTrainer:
        """
        Trainer for the Unified Ontological Engine.

        Trains all components jointly:
        - Evidential classification
        - Bhava relational dynamics
        - Reasoning/Creativity task heads
        """

        def __init__(
            self,
            engine: Optional[UnifiedOntologicalEngine] = None,
            config: Optional[UnifiedConfig] = None,
        ):
            self.config = config or UnifiedConfig()
            self.engine = engine or UnifiedOntologicalEngine()

            # Set seed
            torch.manual_seed(self.config.seed)
            np.random.seed(self.config.seed)

            # Device
            if self.config.device == "auto":
                self.device = torch.device(
                    "cuda" if torch.cuda.is_available() else "cpu"
                )
            else:
                self.device = torch.device(self.config.device)

            self.engine = self.engine.to(self.device)

            self.history = []
            self.best_val_acc = 0.0

            print(self.engine.summary())
            print(f"Device: {self.device}")

        def train(self, epochs: int = None) -> Dict[str, Any]:
            """Train the unified model."""
            from symbolu_core.ontological.multi_domain_dataset import MultiDomainDataset
            from symbolu_core.ontological.encoder import get_encoder

            epochs = epochs or self.config.epochs

            # Generate dataset
            print("\nGenerating multi-domain dataset...")
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

            # Generate task targets based on domain
            reasoning_targets = torch.zeros(len(labels))
            creativity_targets = torch.zeros(len(labels))

            for i, sample in enumerate(dataset.samples):
                domain = sample.primary_domain
                if domain in ["O5_COGNITION", "O7_REASONING", "O9_WITNESSES"]:
                    reasoning_targets[i] = 1.0
                if domain in ["O4_STRUCTURE", "O8_PURPOSE", "O10_UNIFYING"]:
                    creativity_targets[i] = 1.0

            # Split
            n = len(embeddings)
            n_val = int(n * self.config.validation_split)
            indices = torch.randperm(n)

            train_idx = indices[n_val:]
            val_idx = indices[:n_val]

            train_emb = embeddings[train_idx].to(self.device)
            train_labels = labels[train_idx].to(self.device)
            train_reasoning = reasoning_targets[train_idx].to(self.device)
            train_creativity = creativity_targets[train_idx].to(self.device)

            val_emb = embeddings[val_idx].to(self.device)
            val_labels = labels[val_idx].to(self.device)

            print(f"Train: {len(train_emb)}, Val: {len(val_emb)}")

            # Optimizer
            optimizer = torch.optim.AdamW(
                self.engine.parameters(),
                lr=self.config.learning_rate,
                weight_decay=self.config.weight_decay,
            )

            # Scheduler
            scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(
                optimizer, T_max=epochs
            )

            print(f"\nTraining unified model for {epochs} epochs...")

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
                train_reasoning = train_reasoning[perm]
                train_creativity = train_creativity[perm]

                total_loss = 0
                total_correct = 0

                for i in range(0, len(train_emb), self.config.batch_size):
                    batch_emb = train_emb[i:i + self.config.batch_size]
                    batch_labels = train_labels[i:i + self.config.batch_size]
                    batch_reasoning = train_reasoning[i:i + self.config.batch_size]
                    batch_creativity = train_creativity[i:i + self.config.batch_size]

                    optimizer.zero_grad()

                    output = self.engine(batch_emb)
                    losses = self.engine.compute_loss(
                        output,
                        batch_labels,
                        reasoning_targets=batch_reasoning,
                        creativity_targets=batch_creativity,
                        kl_weight=kl_weight,
                        bhava_weight=self.config.bhava_weight,
                        task_weight=self.config.task_weight,
                    )

                    losses["total"].backward()
                    optimizer.step()

                    total_loss += losses["total"].item()

                    # Accuracy
                    pred = torch.argmax(output["ontological"], dim=1)
                    target = torch.argmax(batch_labels, dim=1)
                    total_correct += (pred == target).sum().item()

                scheduler.step()

                train_acc = total_correct / len(train_emb)

                # Validation
                val_acc, val_uncertainty = self._evaluate(val_emb, val_labels)

                print(f"Epoch {epoch + 1}: train_acc={train_acc:.2%}, "
                      f"val_acc={val_acc:.2%}, uncertainty={val_uncertainty:.3f}")

                self.history.append({
                    "epoch": epoch + 1,
                    "train_acc": train_acc,
                    "val_acc": val_acc,
                    "val_uncertainty": val_uncertainty,
                })

                if val_acc > self.best_val_acc:
                    self.best_val_acc = val_acc
                    self._save_checkpoint("best")

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

        def _save_checkpoint(self, name: str) -> None:
            """Save checkpoint."""
            import os
            os.makedirs("checkpoints", exist_ok=True)
            torch.save({
                "engine_state": self.engine.state_dict(),
                "config": self.config,
                "history": self.history,
            }, f"checkpoints/unified_{name}.pt")

        def save(self, path: str) -> None:
            """Save model."""
            torch.save({
                "engine_state": self.engine.state_dict(),
                "config": self.config,
                "history": self.history,
                "best_val_acc": self.best_val_acc,
            }, path)
            print(f"Saved to {path}")

        def benchmark(self) -> Dict[str, Any]:
            """Comprehensive benchmark."""
            from symbolu_core.ontological.multi_domain_dataset import MultiDomainDataset

            print("\n" + "=" * 60)
            print("UNIFIED ENGINE BENCHMARK")
            print("=" * 60)

            # Generate test data
            test_dataset = MultiDomainDataset.generate(
                samples_per_domain=20,
                seed=self.config.seed + 1000,
            )

            results = {
                "per_domain": {},
                "uncertainties": [],
                "reasoning_scores": [],
                "creativity_scores": [],
            }

            correct = {name: 0 for name in LAYER_NAMES}
            total = {name: 0 for name in LAYER_NAMES}

            for sample in test_dataset.samples:
                result = self.engine.analyze(sample.text)

                total[sample.primary_domain] += 1
                if result["dominant_layer"] == sample.primary_domain:
                    correct[sample.primary_domain] += 1

                results["uncertainties"].append(result["uncertainty"])
                results["reasoning_scores"].append(result["reasoning_score"])
                results["creativity_scores"].append(result["creativity_score"])

            # Print results
            print("\nPer-domain accuracy:")
            for domain in LAYER_NAMES:
                if total[domain] > 0:
                    acc = correct[domain] / total[domain]
                    results["per_domain"][domain] = acc
                    print(f"  {domain}: {acc:.0%} ({correct[domain]}/{total[domain]})")

            overall = sum(correct.values()) / sum(total.values())
            mean_uncertainty = np.mean(results["uncertainties"])
            mean_reasoning = np.mean(results["reasoning_scores"])
            mean_creativity = np.mean(results["creativity_scores"])

            print(f"\nOverall accuracy: {overall:.2%}")
            print(f"Mean uncertainty: {mean_uncertainty:.3f}")
            print(f"Mean reasoning score: {mean_reasoning:.3f}")
            print(f"Mean creativity score: {mean_creativity:.3f}")

            results["overall_accuracy"] = overall
            results["mean_uncertainty"] = mean_uncertainty

            return results


    # =========================================================================
    # NEW ARCHITECTURE: UnifiedOntologicalEngineV2 with Inter-Layer Bhava
    # =========================================================================

    class UnifiedOntologicalEngineV2(nn.Module):
        """
        Unified Ontological Engine V2 with Inter-Layer Bhava Relationships.

        This is the NEW recommended engine that replaces sub-layer Bhava with
        inter-layer relationship modeling based on Vedic astrology principles.

        Architecture:
            Text → Encoder (384D) → MLP → Hidden (128D)
                                        ↓
                              EvidentialLayer → 12D + Uncertainty
                                        ↓
                              InterLayerBhavaEngine → 144D relationships + Coherence
                                        ↓
                              ┌─────────┴─────────┐
                              ↓                   ↓
                        ReasoningHead       CreativityHead

        Key Improvements over V1:
        - 144D inter-layer relationships (vs 120D sub-layers)
        - All-to-all relationship modeling
        - Vedic Drishti (aspect) patterns for attention
        - Global coherence score
        - ~5% overhead (vs ~34% for sub-layers)

        Features:
        - 12-class evidential classification with uncertainty
        - 144D inter-layer Bhava relationships
        - Global coherence from relationship matrix
        - Reasoning and Creativity task scores
        """

        def __init__(
            self,
            encoder_dim: int = 384,
            hidden_dims: Tuple[int, ...] = (256, 128),
            ontological_dim: int = 12,
            bhava_hidden_dim: int = 128,
            dropout: float = 0.1,
        ):
            super().__init__()

            self.encoder_dim = encoder_dim
            self.ontological_dim = ontological_dim
            self.bhava_dim = 144  # 12 × 12 inter-layer relationships

            # Build MLP backbone
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

            self.backbone = nn.Sequential(*layers)
            self.hidden_dim = prev_dim

            # Evidential classification head
            self.evidential = EvidentialLayer(prev_dim, ontological_dim)

            # Inter-layer Bhava relationships (NEW - replaces BhavaLayer)
            self.bhava_engine = InterLayerBhavaEngine(
                ontological_dim=ontological_dim,
                hidden_dim=bhava_hidden_dim,
            )

            # Task heads
            self.reasoning_head = TaskHead(
                input_dim=prev_dim,
                layer_indices=REASONING_LAYERS,
            )
            self.creativity_head = TaskHead(
                input_dim=prev_dim,
                layer_indices=CREATIVITY_LAYERS,
            )

            # Encoder (lazy loaded)
            self._encoder = None

        @property
        def encoder(self):
            if self._encoder is None:
                from symbolu_core.ontological.encoder import get_encoder
                self._encoder = get_encoder("minilm")
            return self._encoder

        def forward(self, x: torch.Tensor) -> Dict[str, torch.Tensor]:
            """
            Full forward pass with inter-layer Bhava relationships.

            Args:
                x: Input embeddings (batch, encoder_dim)

            Returns:
                Dict with all outputs including relationship matrix and coherence
            """
            # Backbone
            hidden = self.backbone(x)

            # Evidential classification
            evidential = self.evidential(hidden)

            # Inter-layer Bhava relationships (NEW)
            bhava_output = self.bhava_engine(evidential["prob"])

            # Task scores
            reasoning = self.reasoning_head(hidden, evidential["prob"])
            creativity = self.creativity_head(hidden, evidential["prob"])

            return {
                # Classification
                "ontological": evidential["prob"],
                "evidence": evidential["evidence"],
                "alpha": evidential["alpha"],
                "uncertainty": evidential["uncertainty"],
                # Inter-layer Bhava (NEW)
                "bhava": bhava_output["bhava"],
                "relationship_matrix": bhava_output["relationship_matrix"],
                "coherence": bhava_output["coherence"],
                "attended_layers": bhava_output["attended_layers"],
                # Task scores
                "reasoning_score": reasoning,
                "creativity_score": creativity,
                # Hidden state
                "hidden": hidden,
            }

        def analyze(self, text: str) -> Dict[str, Any]:
            """
            Analyze text with inter-layer Bhava relationships.

            Returns comprehensive analysis including:
            - Dominant layer and confidence
            - Uncertainty quantification
            - Global coherence score (NEW)
            - Strongest inter-layer relationships (NEW)
            - Reasoning and creativity scores
            - Full 156D vector (12D onto + 144D bhava)
            """
            self.eval()

            # Encode
            embedding = self.encoder.encode(text)
            x = torch.tensor(embedding, dtype=torch.float32).unsqueeze(0)

            device = next(self.parameters()).device
            x = x.to(device)

            with torch.no_grad():
                output = self.forward(x)

            # Extract results
            probs = output["ontological"].squeeze(0).cpu().numpy()
            uncertainty = output["uncertainty"].item()
            coherence = output["coherence"].item()
            bhava = output["bhava"].squeeze(0).cpu().numpy()
            rel_matrix = output["relationship_matrix"].squeeze(0).cpu().numpy()
            reasoning = output["reasoning_score"].item()
            creativity = output["creativity_score"].item()

            # Dominant layer
            dominant_idx = int(np.argmax(probs))
            dominant_layer = LAYER_NAMES[dominant_idx]
            confidence = float(probs[dominant_idx])

            # All probabilities
            probabilities = {
                LAYER_NAMES[i]: float(probs[i])
                for i in range(len(LAYER_NAMES))
            }

            # Certainty level
            if uncertainty > 0.7:
                certainty_level = "very_uncertain"
            elif uncertainty > 0.4:
                certainty_level = "uncertain"
            elif uncertainty > 0.2:
                certainty_level = "moderate"
            else:
                certainty_level = "confident"

            # Find strongest relationships (NEW)
            flat_rel = rel_matrix.flatten()
            top_indices = np.argsort(np.abs(flat_rel))[-5:][::-1]
            strongest_relationships = []
            for idx in top_indices:
                i, j = idx // 12, idx % 12
                meaning = get_relationship_meaning(i, j)
                strongest_relationships.append({
                    "from": LAYER_NAMES[i],
                    "to": LAYER_NAMES[j],
                    "strength": float(flat_rel[idx]),
                    "bhava": meaning['relationship_bhava']['name'],
                    "interpretation": meaning['interpretation'],
                })

            # Full 156D vector
            full_vector = np.concatenate([probs, bhava])

            return {
                # Classification
                "dominant_layer": dominant_layer,
                "confidence": confidence,
                "probabilities": probabilities,
                # Uncertainty
                "uncertainty": uncertainty,
                "certainty_level": certainty_level,
                # Coherence (NEW)
                "coherence": coherence,
                # Inter-layer relationships (NEW)
                "strongest_relationships": strongest_relationships,
                # Task scores
                "reasoning_score": reasoning,
                "creativity_score": creativity,
                # Vectors
                "ontological_vector": probs.tolist(),
                "bhava_vector": bhava.tolist(),
                "relationship_matrix": rel_matrix.tolist(),
                "full_156d_vector": full_vector.tolist(),
            }

        def compute_loss(
            self,
            output: Dict[str, torch.Tensor],
            targets: torch.Tensor,
            reasoning_targets: Optional[torch.Tensor] = None,
            creativity_targets: Optional[torch.Tensor] = None,
            kl_weight: float = 0.1,
            coherence_weight: float = 0.2,  # NEW: coherence loss
            task_weight: float = 0.2,
        ) -> Dict[str, torch.Tensor]:
            """
            Compute unified loss with coherence regularization.

            Combines:
            1. Evidential classification loss
            2. KL regularization
            3. Coherence maximization (NEW - replaces bhava consistency)
            4. Task head losses (if targets provided)
            """
            alpha = output["alpha"]
            S = torch.sum(alpha, dim=1, keepdim=True)

            # Normalize targets
            targets = targets / (targets.sum(dim=1, keepdim=True) + 1e-8)

            # 1. Evidential cross-entropy
            log_likelihood = torch.sum(
                targets * (torch.digamma(alpha) - torch.digamma(S)),
                dim=1
            )
            ce_loss = -log_likelihood.mean()

            # 2. KL divergence to prior
            alpha_tilde = targets + (1 - targets) * alpha
            kl_loss = self._kl_divergence(alpha_tilde)

            # 3. Coherence maximization (NEW)
            # Encourage high coherence in the relationship matrix
            coherence = output["coherence"]
            coherence_loss = -coherence.mean()  # Maximize coherence

            # 4. Task losses (if targets provided)
            task_loss = torch.tensor(0.0, device=alpha.device)
            if reasoning_targets is not None:
                task_loss = task_loss + F.binary_cross_entropy(
                    output["reasoning_score"], reasoning_targets
                )
            if creativity_targets is not None:
                task_loss = task_loss + F.binary_cross_entropy(
                    output["creativity_score"], creativity_targets
                )

            # Total loss
            total_loss = (
                ce_loss +
                kl_weight * kl_loss +
                coherence_weight * coherence_loss +
                task_weight * task_loss
            )

            return {
                "total": total_loss,
                "ce": ce_loss,
                "kl": kl_loss,
                "coherence": coherence_loss,
                "task": task_loss,
            }

        def _kl_divergence(self, alpha: torch.Tensor) -> torch.Tensor:
            """KL divergence between Dirichlet(alpha) and Dirichlet(1)."""
            K = alpha.shape[1]
            alpha0 = torch.sum(alpha, dim=1, keepdim=True)

            kl = (
                torch.lgamma(alpha0.squeeze(-1)) -
                torch.lgamma(torch.tensor(K, dtype=torch.float32, device=alpha.device)) -
                torch.sum(torch.lgamma(alpha), dim=1) +
                torch.sum((alpha - 1) * (torch.digamma(alpha) - torch.digamma(alpha0)), dim=1)
            )

            return kl.mean()

        def summary(self) -> str:
            """Model summary."""
            total_params = sum(p.numel() for p in self.parameters())

            return f"""
============================================================
UNIFIED ONTOLOGICAL ENGINE V2 (INTER-LAYER ARCHITECTURE)
============================================================

VEDIC PRINCIPLE:
  Bhavas are RELATIONSHIPS, not separate entities.
  The 12 ontological layers inherently embody Bhava dynamics
  through their inter-layer relationships.

Architecture:
  Encoder Input: {self.encoder_dim}D (MiniLM)
  Hidden: {self.hidden_dim}D
  Ontological Output: {self.ontological_dim}D (Evidential/Dirichlet)
  Inter-Layer Bhava: {self.bhava_dim}D (12×12 relationships)
  Full Vector: {self.ontological_dim + self.bhava_dim}D (156D)

Features:
  ✓ 12-class evidential classification
  ✓ Bayesian uncertainty quantification
  ✓ 144D inter-layer Bhava relationships (NEW)
  ✓ Global coherence score (NEW)
  ✓ Vedic Drishti (aspect) attention (NEW)
  ✓ Reasoning head (layers {REASONING_LAYERS})
  ✓ Creativity head (layers {CREATIVITY_LAYERS})

Drishti (Aspect) Patterns:
  • Conjunction (same): 1.0
  • Opposition (6 apart): 1.0 (complementary)
  • Trine (4/8 apart): 0.9 (harmonious)
  • Square (3/9 apart): 0.75 (action/tension)
  • Adjacent (1/11 apart): 0.8 (resource flow)

Improvements over V1:
  • Richer relationship space (144 vs 120)
  • All-to-all relationships (vs adjacent only)
  • ~5% overhead (vs ~34% for sub-layers)
  • Coherence-based loss (vs bhava consistency)

Total Parameters: {total_params:,}
============================================================
"""
