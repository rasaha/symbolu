"""
Enhanced Ontological Engine - Multi-Task Training Pipeline
============================================================

Implements the recommended training strategy:

Phase 1: Semantic Bootstrap
- DistilBERT encoder (frozen or lightly tuned)
- Curated datasets with auto-labels

Phase 2: Bhava-Specific Fine-Tuning
- Multi-task loss composition
- Contrastive pull for reasoning vs creativity
- Purity/orthogonality regularization

Usage:
    trainer = EnhancedTrainer()
    trainer.train(train_data, val_data, epochs=10)
    trainer.benchmark()  # Before/after comparison
"""

import time
import random
from typing import List, Dict, Tuple, Optional, Any
from dataclasses import dataclass, field
from pathlib import Path

try:
    import torch
    import torch.nn as nn
    from torch.optim import AdamW
    from torch.optim.lr_scheduler import CosineAnnealingWarmRestarts
    PYTORCH_AVAILABLE = True
except ImportError:
    PYTORCH_AVAILABLE = False

from symbolu.ontological.types import LAYER_NAMES, LAYER_INDEX


# Domain mapping
DOMAIN_NAMES = ["technical", "reasoning", "creative", "action", "governance"]
DOMAIN_TO_IDX = {name: i for i, name in enumerate(DOMAIN_NAMES)}


def create_curated_dataset() -> List[Dict[str, Any]]:
    """
    Create a curated dataset with proper ontological labels.

    Categories:
    - Reasoning: High O6, low O2
    - Creativity: High O2, low O6
    - Technical: High O6, O3
    - Action: High O3, O5
    - Governance: High O7, O8
    """
    dataset = []

    # REASONING examples (O6 dominant)
    reasoning_texts = [
        "If the hypothesis is valid, then the conclusion necessarily follows from the premises.",
        "Given that A implies B and B implies C, we can logically deduce that A implies C.",
        "The mathematical proof demonstrates that the theorem holds for all natural numbers.",
        "Analyzing the correlation coefficient reveals a statistically significant relationship.",
        "The evidence strongly supports the causal mechanism proposed by the theory.",
        "By applying modus ponens, we can derive the consequent from the antecedent.",
        "The logical structure of the argument is valid, though the premises may be disputed.",
        "Deductive reasoning from first principles leads to the inevitable conclusion.",
        "The proof by contradiction shows that the opposite assumption leads to absurdity.",
        "Statistical inference allows us to generalize from the sample to the population.",
        "The algorithm's correctness can be proven using loop invariants.",
        "From the axioms of set theory, we derive the properties of infinite cardinals.",
        "The causal chain from input to output is fully deterministic.",
        "Analyzing the failure modes reveals the root cause of the system breakdown.",
        "The theorem follows directly from the definitions and previously proven lemmas.",
    ]

    for text in reasoning_texts:
        dataset.append({
            "text": text,
            "onto_labels": {"O7_REASONING": 0.9, "O5_COGNITION": 0.6, "O4_STRUCTURE": -0.3},
            "is_reasoning": True,
            "is_creativity": False,
            "reasoning_score": 0.9,
            "creativity_score": 0.2,
            "domain": DOMAIN_TO_IDX["reasoning"],
        })

    # CREATIVITY examples (O2 dominant)
    creative_texts = [
        "Colors dance like whispered secrets across the velvet canvas of twilight.",
        "The melody weaves emotions into tapestries of sound and silence.",
        "Imagine a world where thoughts bloom as visible flowers of light.",
        "Poetry breathes life into the spaces between words and meaning.",
        "The sculpture captures the essence of motion frozen in eternal stillness.",
        "Stars sing lullabies to the dreaming moon in languages of light.",
        "Art transforms the invisible currents of feeling into tangible form.",
        "The story unfolds like origami, revealing hidden dimensions with each fold.",
        "Music paints emotions in frequencies that bypass the rational mind.",
        "The metaphor bridges two distant shores of meaning with a single word.",
        "Creativity is the art of making the impossible feel inevitable.",
        "The dancer's body becomes a poem written in the language of movement.",
        "Imagination seeds clouds from which inspiration rains.",
        "The novel world emerges from the collision of familiar elements.",
        "Beauty hides in the cracks between what is and what could be.",
    ]

    for text in creative_texts:
        dataset.append({
            "text": text,
            "onto_labels": {"O4_STRUCTURE": 0.9, "O10_UNIFYING": 0.6, "O7_REASONING": -0.3},
            "is_reasoning": False,
            "is_creativity": True,
            "reasoning_score": 0.2,
            "creativity_score": 0.9,
            "domain": DOMAIN_TO_IDX["creative"],
        })

    # TECHNICAL examples (O6 + O3)
    technical_texts = [
        "The API endpoint accepts JSON payloads with OAuth2 bearer authentication.",
        "Configure the Kubernetes deployment with resource limits and health checks.",
        "The database query optimizer selects the most efficient execution plan.",
        "Implement retry logic with exponential backoff for transient failures.",
        "The microservices architecture enables independent scaling and deployment.",
        "Use connection pooling to minimize database connection overhead.",
        "The REST interface follows HATEOAS principles for discoverability.",
        "Monitor latency percentiles at p50, p95, and p99 for SLA compliance.",
        "The distributed cache reduces read latency for frequently accessed data.",
        "Implement circuit breakers to prevent cascade failures in the system.",
    ]

    for text in technical_texts:
        dataset.append({
            "text": text,
            "onto_labels": {"O7_REASONING": 0.7, "O3_EXECUTION": 0.7, "O6_AGENCY": 0.5},
            "is_reasoning": True,
            "is_creativity": False,
            "reasoning_score": 0.7,
            "creativity_score": 0.2,
            "domain": DOMAIN_TO_IDX["technical"],
        })

    # ACTION examples (O3 dominant)
    action_texts = [
        "First, run the test suite. Then, deploy to staging. Finally, verify health.",
        "Execute the migration script before the scheduled maintenance window.",
        "Initialize the database, seed the data, then start the application server.",
        "Build the container image, push to registry, and update the deployment.",
        "Run diagnostics, identify the failing component, then apply the hotfix.",
        "Start the backup job, monitor progress, verify completion, cleanup temp files.",
        "Deploy the canary release, monitor metrics, then proceed with full rollout.",
        "Compile the source, link the libraries, and generate the executable.",
        "Trigger the workflow, wait for approval, then execute the production change.",
        "Bootstrap the cluster, join the nodes, and verify quorum establishment.",
    ]

    for text in action_texts:
        dataset.append({
            "text": text,
            "onto_labels": {"O3_EXECUTION": 0.9, "O6_AGENCY": 0.7, "O7_REASONING": 0.3},
            "is_reasoning": False,
            "is_creativity": False,
            "reasoning_score": 0.4,
            "creativity_score": 0.1,
            "domain": DOMAIN_TO_IDX["action"],
        })

    # GOVERNANCE examples (O7 + O8 dominant)
    governance_texts = [
        "AI systems must be designed with fairness, accountability, and transparency.",
        "The ethical framework requires regular bias audits and impact assessments.",
        "Privacy by design ensures data minimization and purpose limitation.",
        "Responsible AI deployment mandates human oversight and intervention capabilities.",
        "The governance policy establishes clear accountability for AI decisions.",
        "Transparency requirements include disclosure of AI involvement in decisions.",
        "Risk assessment protocols identify and mitigate potential AI harms.",
        "Compliance frameworks ensure alignment with regulatory requirements.",
        "The audit trail provides complete traceability of AI system behavior.",
        "Ethical guidelines prohibit discriminatory outcomes and ensure equitable access.",
    ]

    for text in governance_texts:
        dataset.append({
            "text": text,
            "onto_labels": {"O8_PURPOSE": 0.8, "O9_WITNESSES": 0.7, "O7_REASONING": 0.5},
            "is_reasoning": True,
            "is_creativity": False,
            "reasoning_score": 0.6,
            "creativity_score": 0.2,
            "domain": DOMAIN_TO_IDX["governance"],
        })

    # Shuffle
    random.shuffle(dataset)
    return dataset


if PYTORCH_AVAILABLE:
    from symbolu.ontological.enhanced_engine import (
        EnhancedOntologicalEngine,
        MultiTaskLoss,
        create_training_batch,
    )

    @dataclass
    class TrainerConfig:
        """Training configuration."""
        learning_rate: float = 2e-5
        weight_decay: float = 0.01
        epochs: int = 10
        batch_size: int = 8
        warmup_ratio: float = 0.1
        max_grad_norm: float = 1.0

        # Loss weights
        onto_weight: float = 1.0
        bhava_weight: float = 0.5
        contrastive_weight: float = 0.3
        purity_weight: float = 0.1
        orthogonality_weight: float = 0.1

        # Device
        device: str = "auto"

        # Logging
        log_every_n_steps: int = 5


    class EnhancedTrainer:
        """
        Trainer for the enhanced multi-task ontological engine.
        """

        def __init__(
            self,
            engine: Optional[EnhancedOntologicalEngine] = None,
            config: Optional[TrainerConfig] = None,
        ):
            self.config = config or TrainerConfig()
            self.device = self._get_device()

            # Create engine
            if engine is None:
                self.engine = EnhancedOntologicalEngine(
                    freeze_encoder=True,
                    tune_last_n_layers=2,
                )
            else:
                self.engine = engine
            self.engine = self.engine.to(self.device)

            # Loss function
            self.loss_fn = MultiTaskLoss(
                onto_weight=self.config.onto_weight,
                bhava_weight=self.config.bhava_weight,
                contrastive_weight=self.config.contrastive_weight,
                purity_weight=self.config.purity_weight,
                orthogonality_weight=self.config.orthogonality_weight,
            )

            # Training state
            self.global_step = 0
            self.history = []

        def _get_device(self) -> torch.device:
            if self.config.device != "auto":
                return torch.device(self.config.device)
            if torch.cuda.is_available():
                return torch.device("cuda")
            elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
                return torch.device("mps")
            return torch.device("cpu")

        def train(
            self,
            train_data: List[Dict[str, Any]],
            val_data: Optional[List[Dict[str, Any]]] = None,
        ) -> Dict[str, Any]:
            """
            Train the enhanced engine.

            Args:
                train_data: List of training examples
                val_data: Optional validation data

            Returns:
                Training history
            """
            print(f"Training on {len(train_data)} examples")
            print(f"Device: {self.device}")

            # Optimizer
            optimizer = AdamW(
                filter(lambda p: p.requires_grad, self.engine.parameters()),
                lr=self.config.learning_rate,
                weight_decay=self.config.weight_decay,
            )

            # Training loop
            for epoch in range(self.config.epochs):
                self.engine.train()
                epoch_losses = []

                # Shuffle and batch
                random.shuffle(train_data)
                batches = [
                    train_data[i:i + self.config.batch_size]
                    for i in range(0, len(train_data), self.config.batch_size)
                ]

                for batch_idx, batch in enumerate(batches):
                    optimizer.zero_grad()

                    # Prepare batch
                    targets = create_training_batch(batch, self.device)
                    texts = targets.pop("texts")

                    # Forward
                    outputs = self.engine(texts, self.device)

                    # Loss
                    losses = self.loss_fn(outputs, targets)
                    loss = losses["total"]

                    # Backward
                    loss.backward()
                    nn.utils.clip_grad_norm_(
                        self.engine.parameters(),
                        self.config.max_grad_norm,
                    )
                    optimizer.step()

                    epoch_losses.append(loss.item())
                    self.global_step += 1

                    # Logging
                    if self.global_step % self.config.log_every_n_steps == 0:
                        loss_str = ", ".join(
                            f"{k}={v.item():.4f}" for k, v in losses.items()
                            if isinstance(v, torch.Tensor)
                        )
                        print(f"  Step {self.global_step}: {loss_str}")

                # Epoch summary
                avg_loss = sum(epoch_losses) / len(epoch_losses)
                print(f"Epoch {epoch + 1}/{self.config.epochs}: loss={avg_loss:.4f}")

                # Validation
                if val_data:
                    val_loss = self.evaluate(val_data)
                    print(f"  Val loss: {val_loss:.4f}")

                self.history.append({
                    "epoch": epoch + 1,
                    "train_loss": avg_loss,
                })

            return {"history": self.history}

        def evaluate(self, data: List[Dict[str, Any]]) -> float:
            """Evaluate on data and return loss."""
            self.engine.eval()
            total_loss = 0.0

            with torch.no_grad():
                for i in range(0, len(data), self.config.batch_size):
                    batch = data[i:i + self.config.batch_size]
                    targets = create_training_batch(batch, self.device)
                    texts = targets.pop("texts")

                    outputs = self.engine(texts, self.device)
                    losses = self.loss_fn(outputs, targets)
                    total_loss += losses["total"].item()

            return total_loss / max(len(data) // self.config.batch_size, 1)

        def analyze(self, text: str) -> Dict[str, Any]:
            """Analyze a single text."""
            self.engine.eval()
            with torch.no_grad():
                outputs = self.engine([text], self.device)

            onto = outputs["onto"][0].cpu().tolist()
            bhava = outputs["bhava"][0].cpu().tolist()

            # Find dominant
            dominant_idx = onto.index(max(onto))
            dominant_layer = LAYER_NAMES[dominant_idx]

            return {
                "text": text,
                "onto": {LAYER_NAMES[i]: onto[i] for i in range(10)},
                "dominant": dominant_layer,
                "o6_reasoning": onto[5],
                "o2_forming": onto[1],
                "reasoning_score": outputs["reasoning"][0].item(),
                "creativity_score": outputs["creativity"][0].item(),
                "domain_logits": outputs["domain"][0].cpu().tolist(),
            }

        def benchmark(self) -> Dict[str, Any]:
            """
            Run benchmark and report results.

            Tests:
            - Reasoning vs creativity separation
            - Domain classification
            - O6/O2 differentiation
            """
            print("\n" + "=" * 60)
            print("BENCHMARK: Enhanced Engine")
            print("=" * 60)

            # Test samples
            reasoning_samples = [
                "If the hypothesis is true, then the conclusion follows.",
                "The proof demonstrates that the theorem holds.",
                "Analyzing the evidence reveals a causal relationship.",
            ]

            creativity_samples = [
                "Stars dance like dreams across the velvet sky.",
                "Poetry breathes color into silence.",
                "Imagination paints worlds that logic cannot map.",
            ]

            # Analyze reasoning
            print("\nREASONING Samples:")
            reasoning_results = []
            for text in reasoning_samples:
                result = self.analyze(text)
                print(f"  O6={result['o6_reasoning']:+.3f}, O2={result['o2_forming']:+.3f}, "
                      f"R={result['reasoning_score']:.2f}, C={result['creativity_score']:.2f}")
                reasoning_results.append(result)

            # Analyze creativity
            print("\nCREATIVITY Samples:")
            creativity_results = []
            for text in creativity_samples:
                result = self.analyze(text)
                print(f"  O6={result['o6_reasoning']:+.3f}, O2={result['o2_forming']:+.3f}, "
                      f"R={result['reasoning_score']:.2f}, C={result['creativity_score']:.2f}")
                creativity_results.append(result)

            # Calculate metrics
            avg_r_o6 = sum(r["o6_reasoning"] for r in reasoning_results) / len(reasoning_results)
            avg_r_o2 = sum(r["o2_forming"] for r in reasoning_results) / len(reasoning_results)
            avg_c_o6 = sum(r["o6_reasoning"] for r in creativity_results) / len(creativity_results)
            avg_c_o2 = sum(r["o2_forming"] for r in creativity_results) / len(creativity_results)

            # Separation
            o6_separation = avg_r_o6 - avg_c_o6
            o2_separation = avg_c_o2 - avg_r_o2

            # Accuracy
            reasoning_correct = sum(1 for r in reasoning_results if r["o6_reasoning"] > r["o2_forming"])
            creativity_correct = sum(1 for r in creativity_results if r["o2_forming"] > r["o6_reasoning"])
            accuracy = (reasoning_correct + creativity_correct) / 6

            print("\n" + "-" * 40)
            print("RESULTS:")
            print(f"  Reasoning avg: O6={avg_r_o6:+.3f}, O2={avg_r_o2:+.3f}")
            print(f"  Creativity avg: O6={avg_c_o6:+.3f}, O2={avg_c_o2:+.3f}")
            print(f"  O6 separation (R-C): {o6_separation:+.3f}")
            print(f"  O2 separation (C-R): {o2_separation:+.3f}")
            print(f"  Direction accuracy: {accuracy:.0%}")

            return {
                "accuracy": accuracy,
                "o6_separation": o6_separation,
                "o2_separation": o2_separation,
            }


    def train_enhanced_model(
        epochs: int = 10,
        device: str = "auto",
    ) -> Tuple[EnhancedTrainer, Dict[str, Any]]:
        """
        Train the enhanced model and run benchmarks.

        Returns trainer and benchmark results.
        """
        # Create dataset
        dataset = create_curated_dataset()
        train_data = dataset[:int(len(dataset) * 0.8)]
        val_data = dataset[int(len(dataset) * 0.8):]

        print(f"Dataset: {len(train_data)} train, {len(val_data)} val")

        # Create trainer
        config = TrainerConfig(epochs=epochs, device=device)
        trainer = EnhancedTrainer(config=config)

        # Benchmark BEFORE training
        print("\n" + "=" * 60)
        print("BEFORE TRAINING")
        print("=" * 60)
        before_results = trainer.benchmark()

        # Train
        print("\n" + "=" * 60)
        print("TRAINING")
        print("=" * 60)
        trainer.train(train_data, val_data)

        # Benchmark AFTER training
        print("\n" + "=" * 60)
        print("AFTER TRAINING")
        print("=" * 60)
        after_results = trainer.benchmark()

        # Summary
        print("\n" + "=" * 60)
        print("IMPROVEMENT SUMMARY")
        print("=" * 60)
        print(f"Accuracy:       {before_results['accuracy']:.0%} → {after_results['accuracy']:.0%}")
        print(f"O6 Separation:  {before_results['o6_separation']:+.3f} → {after_results['o6_separation']:+.3f}")
        print(f"O2 Separation:  {before_results['o2_separation']:+.3f} → {after_results['o2_separation']:+.3f}")

        return trainer, {
            "before": before_results,
            "after": after_results,
        }


else:
    class EnhancedTrainer:
        def __init__(self, *args, **kwargs):
            raise ImportError("PyTorch required")

    def train_enhanced_model(*args, **kwargs):
        raise ImportError("PyTorch required")
