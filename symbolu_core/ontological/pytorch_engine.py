"""
Ontological Engine - PyTorch Implementation
=============================================

GPU-accelerated version of the 100D ontological engine using PyTorch.

Features:
- MiniLM encoder integration (384D, 2.5x faster than DistilBERT)
- GPU acceleration (CUDA/MPS)
- Proper backpropagation
- Batch processing
- Mixed precision training
- Contrastive loss for domain separation

Usage:
    engine = PyTorchOntologicalEngine()
    engine.to("cuda")
    output = engine("What is the meaning of truth?")
"""

from typing import List, Dict, Tuple, Optional, Any
from dataclasses import dataclass

# Check if PyTorch is available
try:
    import torch
    import torch.nn as nn
    import torch.nn.functional as F
    PYTORCH_AVAILABLE = True
except ImportError:
    PYTORCH_AVAILABLE = False
    print("PyTorch not available. Install with: pip install torch")

from symbolu_core.ontological.types import LAYER_NAMES, OntologicalVector


if PYTORCH_AVAILABLE:

    class OntologicalMLP(nn.Module):
        """
        Multi-layer perceptron for ontological projection.

        Maps encoder output (384D MiniLM) to 10D ontological vector
        with skip connections and layer normalization.
        """

        def __init__(
            self,
            input_dim: int = 384,
            hidden_dims: Tuple[int, ...] = (256, 128),
            output_dim: int = 10,
            dropout: float = 0.1,
            use_skip: bool = True,
        ):
            super().__init__()

            self.use_skip = use_skip
            dims = [input_dim] + list(hidden_dims) + [output_dim]

            # Build layers
            self.layers = nn.ModuleList()
            self.norms = nn.ModuleList()
            self.skips = nn.ModuleList()

            for i in range(len(dims) - 1):
                self.layers.append(nn.Linear(dims[i], dims[i + 1]))
                if i < len(dims) - 2:  # No norm/skip for output layer
                    self.norms.append(nn.LayerNorm(dims[i + 1]))
                    # Skip projection if dimensions differ
                    if use_skip and i > 0:
                        if dims[i - 1] != dims[i + 1]:
                            self.skips.append(nn.Linear(dims[i - 1], dims[i + 1], bias=False))
                        else:
                            self.skips.append(nn.Identity())

            self.dropout = nn.Dropout(dropout)
            self.output_activation = nn.Tanh()

        def forward(self, x: torch.Tensor) -> torch.Tensor:
            """Forward pass with skip connections."""
            prev = None

            for i, layer in enumerate(self.layers[:-1]):
                identity = x if prev is None else prev
                x = layer(x)
                x = self.norms[i](x)
                x = F.gelu(x)
                x = self.dropout(x)

                # Skip connection
                if self.use_skip and i > 0 and i - 1 < len(self.skips):
                    skip_out = self.skips[i - 1](identity)
                    x = x + skip_out

                prev = identity

            # Output layer
            x = self.layers[-1](x)
            x = self.output_activation(x)

            return x


    class BhavaLayer(nn.Module):
        """
        Computes 90 Bhava values from 10 ontological dimensions.

        Each of 9 ontological pairs gets 10 sub-layer values,
        computed via learned linear combinations.
        """

        def __init__(self, ontological_dim: int = 10, bhava_dim: int = 90):
            super().__init__()

            # Linear layer: 10 → 90
            self.projection = nn.Linear(ontological_dim, bhava_dim)

            # Initialize with structure: boost weights for connected pairs
            self._init_structured_weights()

        def _init_structured_weights(self):
            """Initialize weights to respect pair structure."""
            with torch.no_grad():
                # Reset to small random values
                nn.init.normal_(self.projection.weight, mean=0, std=0.1)
                nn.init.zeros_(self.projection.bias)

                # Boost weights for connected ontological pairs
                pairs = [
                    (0, 1), (1, 2), (2, 3), (3, 4), (4, 5),
                    (5, 6), (6, 7), (7, 8), (8, 9)
                ]

                for pair_idx, (o1, o2) in enumerate(pairs):
                    start = pair_idx * 10
                    for sublayer in range(10):
                        bhava_idx = start + sublayer
                        self.projection.weight[bhava_idx, o1] = 0.5
                        self.projection.weight[bhava_idx, o2] = 0.5

        def forward(self, ontological: torch.Tensor) -> torch.Tensor:
            """Compute 90 Bhava values from 10 ontological dimensions."""
            return torch.tanh(self.projection(ontological))


    class DirectBhavaHead(nn.Module):
        """
        Direct 100D Bhava prediction from encoder embedding.

        Unlike BhavaLayer which derives 90D from 10D ontological,
        this head predicts 100D bhava directly from the 384D encoder output.

        Architecture (optimized for MiniLM 384D):
            384D → 256D → 128D → 100D
        """

        def __init__(
            self,
            input_dim: int = 384,
            hidden_dims: Tuple[int, ...] = (256, 128),
            output_dim: int = 100,
            dropout: float = 0.1,
        ):
            super().__init__()

            dims = [input_dim] + list(hidden_dims) + [output_dim]

            layers = []
            for i in range(len(dims) - 1):
                layers.append(nn.Linear(dims[i], dims[i + 1]))
                if i < len(dims) - 2:  # No activation on output
                    layers.append(nn.LayerNorm(dims[i + 1]))
                    layers.append(nn.ReLU())
                    layers.append(nn.Dropout(dropout))

            self.mlp = nn.Sequential(*layers)
            self.output_activation = nn.Tanh()

        def forward(self, encoder_output: torch.Tensor) -> torch.Tensor:
            """Predict 100D bhava directly from encoder embedding."""
            return self.output_activation(self.mlp(encoder_output))


    class ReasoningHead(nn.Module):
        """Task head for reasoning quality assessment."""

        def __init__(self, input_dim: int = 10, hidden_dim: int = 64):
            super().__init__()
            self.mlp = nn.Sequential(
                nn.Linear(input_dim, hidden_dim),
                nn.ReLU(),
                nn.Dropout(0.1),
                nn.Linear(hidden_dim, 1),
                nn.Sigmoid(),
            )

            # Attention weights focusing on O6, O1, O8
            self.register_buffer(
                "attention",
                torch.tensor([1.5, 0.5, 0.5, 0.5, 0.5, 2.0, 0.5, 1.5, 0.5, 0.5])
            )

        def forward(self, ontological: torch.Tensor) -> torch.Tensor:
            # Apply attention
            weighted = ontological * self.attention.unsqueeze(0)
            return self.mlp(weighted).squeeze(-1)


    class CreativityHead(nn.Module):
        """Task head for creativity quality assessment."""

        def __init__(self, input_dim: int = 10, hidden_dim: int = 64):
            super().__init__()
            self.mlp = nn.Sequential(
                nn.Linear(input_dim, hidden_dim),
                nn.ReLU(),
                nn.Dropout(0.1),
                nn.Linear(hidden_dim, 1),
                nn.Sigmoid(),
            )

            # Attention weights focusing on O2, O9, O7
            self.register_buffer(
                "attention",
                torch.tensor([0.5, 2.0, 0.5, 0.5, 0.5, 0.5, 1.5, 0.5, 1.5, 0.5])
            )

        def forward(self, ontological: torch.Tensor) -> torch.Tensor:
            weighted = ontological * self.attention.unsqueeze(0)
            return self.mlp(weighted).squeeze(-1)


    class PyTorchOntologicalEngine(nn.Module):
        """
        Full PyTorch implementation of the 100D Ontological Engine.

        Architecture:
            Text → Encoder (384D MiniLM) → MLP → 10D Ontological
                                              → 90D Bhava (derived)
                                              → 100D Bhava (direct, optional)
                                              → Reasoning Score
                                              → Creativity Score

        Usage:
            engine = PyTorchOntologicalEngine()
            engine.to("cuda")

            # Training
            optimizer = torch.optim.AdamW(engine.parameters())
            output = engine(embeddings)
            loss = engine.compute_loss(output, targets)
            loss.backward()
            optimizer.step()

            # Inference
            with torch.no_grad():
                result = engine.analyze("What is truth?")
        """

        def __init__(
            self,
            encoder_dim: int = 384,
            hidden_dims: Tuple[int, ...] = (256, 128),
            ontological_dim: int = 10,
            bhava_dim: int = 90,
            direct_bhava_dim: int = 100,
            dropout: float = 0.1,
            use_skip: bool = True,
            use_direct_bhava: bool = False,
        ):
            super().__init__()

            # Main ontological projection
            self.mlp = OntologicalMLP(
                input_dim=encoder_dim,
                hidden_dims=hidden_dims,
                output_dim=ontological_dim,
                dropout=dropout,
                use_skip=use_skip,
            )

            # Bhava layer (10 → 90) - derived from ontological
            self.bhava = BhavaLayer(ontological_dim, bhava_dim)

            # Direct Bhava head (384 → 100) - optional
            self.use_direct_bhava = use_direct_bhava
            if use_direct_bhava:
                self.direct_bhava = DirectBhavaHead(
                    input_dim=encoder_dim,
                    hidden_dims=hidden_dims,
                    output_dim=direct_bhava_dim,
                    dropout=dropout,
                )

            # Task heads
            self.reasoning_head = ReasoningHead(ontological_dim)
            self.creativity_head = CreativityHead(ontological_dim)

            # Store dimensions
            self.encoder_dim = encoder_dim
            self.ontological_dim = ontological_dim
            self.bhava_dim = bhava_dim
            self.direct_bhava_dim = direct_bhava_dim

            # Text encoder (lazy loaded)
            self._text_encoder = None

        def forward(
            self,
            embeddings: torch.Tensor,
        ) -> Dict[str, torch.Tensor]:
            """
            Forward pass with dual-head architecture.

            Args:
                embeddings: (batch, 384) encoder output

            Returns:
                Dict with:
                    - ontological: (batch, 10) main layer activations
                    - bhava: (batch, 90) computed from ontological
                    - bhava_direct: (batch, 100) predicted directly (if enabled)
                    - full: (batch, 100) combined ontological + derived bhava
                    - reasoning: (batch,) reasoning task score
                    - creativity: (batch,) creativity task score
            """
            # Ontological projection (384 → 10)
            ontological = self.mlp(embeddings)

            # Derived Bhava (10 → 90)
            bhava = self.bhava(ontological)

            # Direct Bhava (384 → 100) - optional
            bhava_direct = None
            if self.use_direct_bhava:
                bhava_direct = self.direct_bhava(embeddings)

            # Task scores
            reasoning = self.reasoning_head(ontological)
            creativity = self.creativity_head(ontological)

            # Full 100D vector (ontological + derived bhava)
            full = torch.cat([ontological, bhava], dim=-1)

            result = {
                "ontological": ontological,
                "bhava": bhava,
                "full": full,
                "reasoning": reasoning,
                "creativity": creativity,
            }

            if bhava_direct is not None:
                result["bhava_direct"] = bhava_direct

            return result

        def compute_loss(
            self,
            output: Dict[str, torch.Tensor],
            targets: Optional[Dict[str, torch.Tensor]] = None,
            purity_weight: float = 0.1,
            orthogonality_weight: float = 0.05,
        ) -> torch.Tensor:
            """
            Compute combined loss.

            Args:
                output: Forward pass output
                targets: Optional dict with target values
                purity_weight: Weight for purity regularization
                orthogonality_weight: Weight for orthogonality regularization

            Returns:
                Combined loss tensor
            """
            loss = torch.tensor(0.0, device=output["ontological"].device)

            ontological = output["ontological"]

            # Supervision loss (if targets provided)
            if targets is not None:
                if "ontological" in targets and targets["ontological"] is not None:
                    mask = ~torch.isnan(targets["ontological"])
                    if mask.any():
                        loss = loss + F.mse_loss(
                            ontological[mask],
                            targets["ontological"][mask]
                        )

                if "reasoning" in targets and targets["reasoning"] is not None:
                    mask = ~torch.isnan(targets["reasoning"])
                    if mask.any():
                        loss = loss + F.binary_cross_entropy(
                            output["reasoning"][mask],
                            targets["reasoning"][mask]
                        )

                if "creativity" in targets and targets["creativity"] is not None:
                    mask = ~torch.isnan(targets["creativity"])
                    if mask.any():
                        loss = loss + F.mse_loss(
                            output["creativity"][mask],
                            targets["creativity"][mask]
                        )

            # Purity loss (encourage sparse activations)
            positive = (ontological + 1) / 2  # Shift to [0, 1]
            probs = positive / (positive.sum(dim=-1, keepdim=True) + 1e-10)
            entropy = -(probs * torch.log(probs + 1e-10)).sum(dim=-1).mean()
            max_entropy = torch.log(torch.tensor(10.0, device=ontological.device))
            purity_loss = entropy / max_entropy
            loss = loss + purity_weight * purity_loss

            # Orthogonality loss (decorrelate dimensions)
            if ontological.size(0) > 1:
                centered = ontological - ontological.mean(dim=0, keepdim=True)
                cov = (centered.T @ centered) / (ontological.size(0) - 1)
                # Off-diagonal correlation
                eye = torch.eye(10, device=ontological.device)
                off_diag = (cov * (1 - eye)).pow(2).sum() / 90  # 10*9/2 pairs
                loss = loss + orthogonality_weight * off_diag

            return loss

        def compute_contrastive_loss(
            self,
            anchor_output: Dict[str, torch.Tensor],
            positive_output: Dict[str, torch.Tensor],
            negative_output: Dict[str, torch.Tensor],
            margin: float = 0.5,
            use_ontological: bool = True,
        ) -> torch.Tensor:
            """
            Compute contrastive loss for reasoning vs creativity separation.

            Uses triplet loss: anchor should be closer to positive than negative.

            Args:
                anchor_output: Forward pass output for anchor samples
                positive_output: Forward pass output for positive (same domain)
                negative_output: Forward pass output for negative (different domain)
                margin: Margin for triplet loss
                use_ontological: Use 10D ontological (True) or full 100D (False)

            Returns:
                Triplet contrastive loss
            """
            if use_ontological:
                anchor = anchor_output["ontological"]
                positive = positive_output["ontological"]
                negative = negative_output["ontological"]
            else:
                anchor = anchor_output["full"]
                positive = positive_output["full"]
                negative = negative_output["full"]

            # Compute distances
            pos_dist = F.pairwise_distance(anchor, positive, p=2)
            neg_dist = F.pairwise_distance(anchor, negative, p=2)

            # Triplet loss: max(0, pos_dist - neg_dist + margin)
            loss = F.relu(pos_dist - neg_dist + margin).mean()

            return loss

        def compute_domain_separation_loss(
            self,
            reasoning_outputs: Dict[str, torch.Tensor],
            creativity_outputs: Dict[str, torch.Tensor],
            margin: float = 1.0,
        ) -> torch.Tensor:
            """
            Encourage separation between reasoning and creativity domains.

            Maximizes distance between domain centroids.

            Args:
                reasoning_outputs: Outputs from reasoning domain samples
                creativity_outputs: Outputs from creativity domain samples
                margin: Target minimum distance between centroids

            Returns:
                Domain separation loss (lower when domains are well-separated)
            """
            # Get ontological vectors
            reasoning_onto = reasoning_outputs["ontological"]
            creativity_onto = creativity_outputs["ontological"]

            # Compute centroids
            reasoning_centroid = reasoning_onto.mean(dim=0)
            creativity_centroid = creativity_onto.mean(dim=0)

            # Distance between centroids
            centroid_dist = F.pairwise_distance(
                reasoning_centroid.unsqueeze(0),
                creativity_centroid.unsqueeze(0),
                p=2
            )

            # Loss: encourage distance >= margin
            loss = F.relu(margin - centroid_dist).squeeze()

            return loss

        def analyze(self, text: str) -> Dict[str, Any]:
            """
            Analyze a single text and return full breakdown.

            Args:
                text: Input text to analyze

            Returns:
                Dict with ontological vector, Bhava, and task scores
            """
            # Get encoder
            if self._text_encoder is None:
                from symbolu_core.ontological.encoder import get_encoder
                self._text_encoder = get_encoder("auto")

            # Encode
            embedding = self._text_encoder.encode(text)
            embedding_tensor = torch.tensor([embedding], dtype=torch.float32)

            # Move to same device as model
            device = next(self.parameters()).device
            embedding_tensor = embedding_tensor.to(device)

            # Forward
            with torch.no_grad():
                output = self(embedding_tensor)

            # Convert to Python types
            onto_values = output["ontological"][0].cpu().tolist()
            bhava_values = output["bhava"][0].cpu().tolist()

            result = {
                "text": text,
                "encoder": self._text_encoder.name,
                "ontological": {LAYER_NAMES[i]: onto_values[i] for i in range(10)},
                "bhava_count": len(bhava_values),
                "reasoning_score": output["reasoning"][0].item(),
                "creativity_score": output["creativity"][0].item(),
                "dominant_layer": LAYER_NAMES[onto_values.index(max(onto_values))],
            }

            # Include direct bhava if available
            if "bhava_direct" in output:
                bhava_direct = output["bhava_direct"][0].cpu().tolist()
                result["bhava_direct_count"] = len(bhava_direct)

            return result

        def parameter_count(self) -> int:
            """Count total trainable parameters."""
            return sum(p.numel() for p in self.parameters() if p.requires_grad)

        def summary(self) -> str:
            """Print model summary."""
            lines = [
                "=" * 60,
                "PYTORCH 100D ONTOLOGICAL ENGINE",
                "=" * 60,
                "",
                f"Total Parameters: {self.parameter_count():,}",
                "",
                "Architecture:",
                f"  Encoder Input: {self.encoder_dim}D (MiniLM/Hash)",
                f"  Ontological Output: {self.ontological_dim}D",
                f"  Bhava Derived: {self.bhava_dim}D (from ontological)",
            ]

            if self.use_direct_bhava:
                lines.append(f"  Bhava Direct: {self.direct_bhava_dim}D (from encoder)")

            lines.extend([
                "",
                "Components:",
                f"  - MLP ({self.encoder_dim}→10): {sum(p.numel() for p in self.mlp.parameters()):,} params",
                f"  - Bhava Layer (10→90): {sum(p.numel() for p in self.bhava.parameters()):,} params",
            ])

            if self.use_direct_bhava:
                lines.append(f"  - Direct Bhava ({self.encoder_dim}→100): {sum(p.numel() for p in self.direct_bhava.parameters()):,} params")

            lines.extend([
                f"  - Reasoning Head: {sum(p.numel() for p in self.reasoning_head.parameters()):,} params",
                f"  - Creativity Head: {sum(p.numel() for p in self.creativity_head.parameters()):,} params",
                "",
                "=" * 60,
            ])
            return "\n".join(lines)


else:
    # Stub class when PyTorch is not available
    class PyTorchOntologicalEngine:
        def __init__(self, *args, **kwargs):
            raise ImportError(
                "PyTorch is required for PyTorchOntologicalEngine. "
                "Install with: pip install torch"
            )
