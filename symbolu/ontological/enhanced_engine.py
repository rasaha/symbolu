"""
Enhanced Ontological Engine v2 - Multi-Task Architecture
==========================================================

Implements Grok's recommended architecture:

Input Text
   ↓
DistilBERT (pretrained) → 768D semantic embedding
   ↓
Hidden Layer 1 (512D) + Skip
   ↓
Hidden Layer 2 (256D) + Skip
   ↓
┌────────────────────┬────────────────────┐
│ Branch 1           │ Branch 2           │
│ 10D Ontological    │ 100D Bhava Grid    │
│ (O1-O10)           │ (10 pairs × 10)    │
└────────────────────┴────────────────────┘
           ↓                    ↓
      Task Heads (Reasoning, Creativity, Domain)

Loss Composition:
- Main: MSE on 10D ontological
- Aux 1: BCE on 100D bhava grid
- Aux 2: Orthogonality + purity on 10D
- Aux 3: Contrastive for reasoning vs creativity
"""

import math
from typing import List, Dict, Tuple, Optional, Any
from dataclasses import dataclass

# Check PyTorch availability
try:
    import torch
    import torch.nn as nn
    import torch.nn.functional as F
    PYTORCH_AVAILABLE = True
except ImportError:
    PYTORCH_AVAILABLE = False

from symbolu.ontological.types import LAYER_NAMES, LAYER_INDEX


if PYTORCH_AVAILABLE:

    class HashEncoder(nn.Module):
        """
        Deterministic hash-based encoder (fallback when DistilBERT unavailable).

        Uses character n-grams and word frequencies to create embeddings.
        Not as semantically rich as DistilBERT but works without network.
        """

        def __init__(self, output_dim: int = 768):
            super().__init__()
            self.output_dim = output_dim
            # Learnable projection for hash features
            self.projection = nn.Linear(output_dim, output_dim)

        def _hash_text(self, text: str) -> List[float]:
            """Create deterministic hash embedding."""
            import hashlib

            # Normalize
            text = text.lower().strip()

            # Character trigrams
            trigrams = [text[i:i+3] for i in range(len(text) - 2)]

            # Word unigrams and bigrams
            words = text.split()
            bigrams = [f"{words[i]} {words[i+1]}" for i in range(len(words) - 1)]

            # Create embedding vector
            embedding = [0.0] * self.output_dim

            # Hash each feature into the embedding
            all_features = trigrams + words + bigrams
            for feat in all_features:
                h = int(hashlib.md5(feat.encode()).hexdigest(), 16)
                for i in range(4):  # 4 hash functions
                    idx = (h >> (i * 10)) % self.output_dim
                    val = ((h >> (i * 10 + 5)) % 1000) / 500.0 - 1.0  # [-1, 1]
                    embedding[idx] += val

            # Normalize
            norm = max(sum(x*x for x in embedding) ** 0.5, 1e-10)
            embedding = [x / norm for x in embedding]

            return embedding

        def forward(
            self,
            texts: List[str],
            device: torch.device,
            max_length: int = 128,
        ) -> torch.Tensor:
            """Encode texts to embeddings."""
            embeddings = [self._hash_text(t) for t in texts]
            x = torch.tensor(embeddings, dtype=torch.float32, device=device)
            return self.projection(x)


    class DistilBERTEncoder(nn.Module):
        """
        DistilBERT encoder with optional fine-tuning.
        Falls back to HashEncoder if network unavailable.

        Uses [CLS] token embedding as sentence representation.
        """

        def __init__(
            self,
            model_name: str = "distilbert-base-uncased",
            freeze: bool = True,
            tune_last_n_layers: int = 0,
        ):
            super().__init__()
            self.model_name = model_name
            self._model = None
            self._tokenizer = None
            self.freeze = freeze
            self.tune_last_n_layers = tune_last_n_layers
            self.output_dim = 768
            self._use_fallback = False
            self._fallback_encoder = None

        def _load_model(self, device):
            """Lazy load model with fallback."""
            if self._model is not None or self._use_fallback:
                return

            try:
                from transformers import DistilBertModel, DistilBertTokenizer

                self._tokenizer = DistilBertTokenizer.from_pretrained(self.model_name)
                self._model = DistilBertModel.from_pretrained(self.model_name)
                self._model = self._model.to(device)

                # Freeze parameters
                if self.freeze:
                    for param in self._model.parameters():
                        param.requires_grad = False

                    # Optionally unfreeze last N layers
                    if self.tune_last_n_layers > 0:
                        for layer in self._model.transformer.layer[-self.tune_last_n_layers:]:
                            for param in layer.parameters():
                                param.requires_grad = True

                print(f"Loaded {self.model_name} (freeze={self.freeze})")
            except Exception as e:
                print(f"Warning: Could not load DistilBERT ({e})")
                print("Falling back to HashEncoder")
                self._use_fallback = True
                self._fallback_encoder = HashEncoder(self.output_dim).to(device)

        def forward(
            self,
            texts: List[str],
            device: torch.device,
            max_length: int = 128,
        ) -> torch.Tensor:
            """
            Encode texts to embeddings.

            Args:
                texts: List of input texts
                device: Target device
                max_length: Max sequence length

            Returns:
                (batch, 768) embeddings
            """
            self._load_model(device)

            # Use fallback if DistilBERT unavailable
            if self._use_fallback:
                return self._fallback_encoder(texts, device, max_length)

            # Tokenize
            inputs = self._tokenizer(
                texts,
                padding=True,
                truncation=True,
                max_length=max_length,
                return_tensors="pt",
            )
            inputs = {k: v.to(device) for k, v in inputs.items()}

            # Forward
            with torch.set_grad_enabled(not self.freeze or self.tune_last_n_layers > 0):
                outputs = self._model(**inputs)

            # [CLS] token embedding
            return outputs.last_hidden_state[:, 0, :]


    class MultiTaskHead(nn.Module):
        """
        Multi-task output heads for ontological + bhava + tasks.
        """

        def __init__(self, input_dim: int = 256):
            super().__init__()

            # 10D Ontological output
            self.onto_head = nn.Sequential(
                nn.Linear(input_dim, 64),
                nn.ReLU(),
                nn.Dropout(0.1),
                nn.Linear(64, 10),
                nn.Tanh(),  # Output in [-1, 1]
            )

            # 100D Bhava output (10 pairs × 10 sub-layers)
            self.bhava_head = nn.Sequential(
                nn.Linear(input_dim, 128),
                nn.ReLU(),
                nn.Dropout(0.1),
                nn.Linear(128, 100),
                nn.Tanh(),
            )

            # Reasoning score head
            self.reasoning_head = nn.Sequential(
                nn.Linear(input_dim + 10, 32),  # Takes hidden + onto
                nn.ReLU(),
                nn.Linear(32, 1),
                nn.Sigmoid(),
            )

            # Creativity score head
            self.creativity_head = nn.Sequential(
                nn.Linear(input_dim + 10, 32),
                nn.ReLU(),
                nn.Linear(32, 1),
                nn.Sigmoid(),
            )

            # Domain classification head (5 classes)
            self.domain_head = nn.Sequential(
                nn.Linear(input_dim + 10, 32),
                nn.ReLU(),
                nn.Linear(32, 5),  # technical, reasoning, creative, action, governance
            )

        def forward(
            self,
            hidden: torch.Tensor,
        ) -> Dict[str, torch.Tensor]:
            """
            Forward through all heads.

            Args:
                hidden: (batch, 256) hidden representation

            Returns:
                Dict with onto, bhava, reasoning, creativity, domain
            """
            # Primary outputs
            onto = self.onto_head(hidden)
            bhava = self.bhava_head(hidden)

            # Task outputs (use hidden + onto)
            hidden_onto = torch.cat([hidden, onto], dim=-1)
            reasoning = self.reasoning_head(hidden_onto).squeeze(-1)
            creativity = self.creativity_head(hidden_onto).squeeze(-1)
            domain = self.domain_head(hidden_onto)

            return {
                "onto": onto,
                "bhava": bhava,
                "reasoning": reasoning,
                "creativity": creativity,
                "domain": domain,
            }


    class EnhancedOntologicalEngine(nn.Module):
        """
        Enhanced 110D Ontological Engine with Multi-Task Learning.

        Architecture:
            DistilBERT → 768D → MLP → 256D
                                    ↓
                         ┌──────────┴──────────┐
                         │                     │
                    10D Onto              100D Bhava
                         │                     │
                         └──────────┬──────────┘
                                    ↓
                            Task Heads
        """

        def __init__(
            self,
            encoder_name: str = "distilbert-base-uncased",
            freeze_encoder: bool = True,
            tune_last_n_layers: int = 2,
            hidden_dims: Tuple[int, ...] = (512, 256),
            dropout: float = 0.1,
        ):
            super().__init__()

            # Encoder
            self.encoder = DistilBERTEncoder(
                model_name=encoder_name,
                freeze=freeze_encoder,
                tune_last_n_layers=tune_last_n_layers,
            )

            # MLP backbone
            self.backbone = nn.Sequential(
                nn.Linear(768, hidden_dims[0]),
                nn.LayerNorm(hidden_dims[0]),
                nn.GELU(),
                nn.Dropout(dropout),
                nn.Linear(hidden_dims[0], hidden_dims[1]),
                nn.LayerNorm(hidden_dims[1]),
                nn.GELU(),
                nn.Dropout(dropout),
            )

            # Skip connection projection
            self.skip_proj = nn.Linear(768, hidden_dims[1])

            # Multi-task heads
            self.heads = MultiTaskHead(input_dim=hidden_dims[1])

            # Store config
            self.hidden_dim = hidden_dims[1]

        def forward(
            self,
            texts: List[str],
            device: Optional[torch.device] = None,
        ) -> Dict[str, torch.Tensor]:
            """
            Forward pass from text to all outputs.

            Args:
                texts: List of input texts
                device: Target device (auto-detect if None)

            Returns:
                Dict with embeddings, hidden, onto, bhava, and task outputs
            """
            if device is None:
                device = next(self.parameters()).device

            # Encode texts
            embeddings = self.encoder(texts, device)

            # Backbone with skip connection
            hidden = self.backbone(embeddings)
            skip = self.skip_proj(embeddings)
            hidden = hidden + skip

            # Multi-task outputs
            outputs = self.heads(hidden)
            outputs["embeddings"] = embeddings
            outputs["hidden"] = hidden

            return outputs

        def forward_from_embeddings(
            self,
            embeddings: torch.Tensor,
        ) -> Dict[str, torch.Tensor]:
            """
            Forward from pre-computed embeddings (for efficiency).
            """
            hidden = self.backbone(embeddings)
            skip = self.skip_proj(embeddings)
            hidden = hidden + skip

            outputs = self.heads(hidden)
            outputs["embeddings"] = embeddings
            outputs["hidden"] = hidden

            return outputs

        def get_contrastive_embeddings(
            self,
            outputs: Dict[str, torch.Tensor],
        ) -> torch.Tensor:
            """
            Get embeddings suitable for contrastive learning.

            Concatenates onto + normalized hidden.
            """
            onto = outputs["onto"]
            hidden = F.normalize(outputs["hidden"], dim=-1)
            return torch.cat([onto, hidden], dim=-1)


    class MultiTaskLoss(nn.Module):
        """
        Multi-task loss for enhanced ontological engine.

        Components:
        1. MSE on 10D ontological targets
        2. BCE on 100D bhava grid
        3. Orthogonality + purity on 10D
        4. Contrastive for reasoning vs creativity
        5. Cross-entropy for domain classification
        """

        def __init__(
            self,
            onto_weight: float = 1.0,
            bhava_weight: float = 0.5,
            orthogonality_weight: float = 0.1,
            purity_weight: float = 0.1,
            contrastive_weight: float = 0.3,
            reasoning_weight: float = 0.3,
            creativity_weight: float = 0.3,
            domain_weight: float = 0.2,
            contrastive_margin: float = 0.5,
        ):
            super().__init__()
            self.onto_weight = onto_weight
            self.bhava_weight = bhava_weight
            self.orthogonality_weight = orthogonality_weight
            self.purity_weight = purity_weight
            self.contrastive_weight = contrastive_weight
            self.reasoning_weight = reasoning_weight
            self.creativity_weight = creativity_weight
            self.domain_weight = domain_weight
            self.contrastive_margin = contrastive_margin

        def forward(
            self,
            outputs: Dict[str, torch.Tensor],
            targets: Dict[str, torch.Tensor],
        ) -> Dict[str, torch.Tensor]:
            """
            Compute multi-task loss.

            Args:
                outputs: Model outputs
                targets: Target values

            Returns:
                Dict with total loss and components
            """
            losses = {}
            total = torch.tensor(0.0, device=outputs["onto"].device)

            onto = outputs["onto"]
            bhava = outputs["bhava"]

            # 1. Ontological MSE loss
            if "onto" in targets and targets["onto"] is not None:
                mask = ~torch.isnan(targets["onto"])
                if mask.any():
                    onto_loss = F.mse_loss(onto[mask], targets["onto"][mask])
                    losses["onto"] = onto_loss
                    total = total + self.onto_weight * onto_loss

            # 2. Bhava BCE loss (treat as multi-label)
            if "bhava" in targets and targets["bhava"] is not None:
                mask = ~torch.isnan(targets["bhava"])
                if mask.any():
                    # Shift from [-1,1] to [0,1] for BCE
                    bhava_pred = (bhava[mask] + 1) / 2
                    bhava_target = (targets["bhava"][mask] + 1) / 2
                    bhava_loss = F.binary_cross_entropy(bhava_pred, bhava_target)
                    losses["bhava"] = bhava_loss
                    total = total + self.bhava_weight * bhava_loss

            # 3. Orthogonality loss (decorrelate dimensions)
            if onto.size(0) > 1:
                centered = onto - onto.mean(dim=0, keepdim=True)
                cov = (centered.T @ centered) / (onto.size(0) - 1)
                eye = torch.eye(10, device=onto.device)
                off_diag = (cov * (1 - eye)).pow(2).sum() / 45  # 10*9/2
                losses["orthogonality"] = off_diag
                total = total + self.orthogonality_weight * off_diag

            # 4. Purity loss (sparse activations)
            positive = (onto + 1) / 2  # Shift to [0, 1]
            probs = positive / (positive.sum(dim=-1, keepdim=True) + 1e-10)
            entropy = -(probs * torch.log(probs + 1e-10)).sum(dim=-1).mean()
            purity = entropy / math.log(10)  # Normalize
            losses["purity"] = purity
            total = total + self.purity_weight * purity

            # 5. Contrastive loss (reasoning vs creativity)
            if "is_reasoning" in targets and "is_creativity" in targets:
                reasoning_mask = targets["is_reasoning"]
                creativity_mask = targets["is_creativity"]

                if reasoning_mask.any() and creativity_mask.any():
                    # Get O6 (reasoning) and O2 (creativity) activations
                    o6 = onto[:, 5]  # O7_REASONING
                    o2 = onto[:, 1]  # O2_FORMING

                    # Reasoning samples should have high O6, low O2
                    # Creativity samples should have high O2, low O6
                    reasoning_pull = (1 - o6[reasoning_mask]).mean() + o2[reasoning_mask].mean()
                    creativity_pull = (1 - o2[creativity_mask]).mean() + o6[creativity_mask].mean()

                    contrastive = (reasoning_pull + creativity_pull) / 2
                    losses["contrastive"] = contrastive
                    total = total + self.contrastive_weight * contrastive

            # 6. Reasoning score loss
            if "reasoning" in targets and targets["reasoning"] is not None:
                mask = ~torch.isnan(targets["reasoning"])
                if mask.any():
                    r_loss = F.binary_cross_entropy(
                        outputs["reasoning"][mask],
                        targets["reasoning"][mask]
                    )
                    losses["reasoning"] = r_loss
                    total = total + self.reasoning_weight * r_loss

            # 7. Creativity score loss
            if "creativity" in targets and targets["creativity"] is not None:
                mask = ~torch.isnan(targets["creativity"])
                if mask.any():
                    c_loss = F.mse_loss(
                        outputs["creativity"][mask],
                        targets["creativity"][mask]
                    )
                    losses["creativity"] = c_loss
                    total = total + self.creativity_weight * c_loss

            # 8. Domain classification loss
            if "domain" in targets and targets["domain"] is not None:
                mask = targets["domain"] >= 0  # Valid domain labels
                if mask.any():
                    d_loss = F.cross_entropy(
                        outputs["domain"][mask],
                        targets["domain"][mask].long()
                    )
                    losses["domain"] = d_loss
                    total = total + self.domain_weight * d_loss

            losses["total"] = total
            return losses


    def create_training_batch(
        examples: List[Dict[str, Any]],
        device: torch.device,
    ) -> Dict[str, torch.Tensor]:
        """
        Create training batch from examples.

        Each example should have:
        - text: str
        - onto_labels: Optional[Dict[str, float]] - dimension labels
        - bhava_labels: Optional[List[float]] - 100D bhava targets
        - is_reasoning: bool
        - is_creativity: bool
        - reasoning_score: Optional[float]
        - creativity_score: Optional[float]
        - domain: Optional[int] - 0-4
        """
        batch_size = len(examples)

        # Ontological targets (10D)
        onto_targets = torch.full((batch_size, 10), float("nan"), device=device)
        for i, ex in enumerate(examples):
            if "onto_labels" in ex and ex["onto_labels"]:
                for layer_name, value in ex["onto_labels"].items():
                    if layer_name in LAYER_INDEX:
                        onto_targets[i, LAYER_INDEX[layer_name]] = value

        # Bhava targets (100D)
        bhava_targets = torch.full((batch_size, 100), float("nan"), device=device)
        for i, ex in enumerate(examples):
            if "bhava_labels" in ex and ex["bhava_labels"]:
                for j, val in enumerate(ex["bhava_labels"][:100]):
                    bhava_targets[i, j] = val

        # Contrastive flags
        is_reasoning = torch.tensor(
            [ex.get("is_reasoning", False) for ex in examples],
            dtype=torch.bool, device=device
        )
        is_creativity = torch.tensor(
            [ex.get("is_creativity", False) for ex in examples],
            dtype=torch.bool, device=device
        )

        # Task scores
        reasoning_targets = torch.tensor(
            [ex.get("reasoning_score", float("nan")) for ex in examples],
            dtype=torch.float32, device=device
        )
        creativity_targets = torch.tensor(
            [ex.get("creativity_score", float("nan")) for ex in examples],
            dtype=torch.float32, device=device
        )

        # Domain labels
        domain_targets = torch.tensor(
            [ex.get("domain", -1) for ex in examples],
            dtype=torch.long, device=device
        )

        return {
            "texts": [ex["text"] for ex in examples],
            "onto": onto_targets,
            "bhava": bhava_targets,
            "is_reasoning": is_reasoning,
            "is_creativity": is_creativity,
            "reasoning": reasoning_targets,
            "creativity": creativity_targets,
            "domain": domain_targets,
        }


else:
    class EnhancedOntologicalEngine:
        def __init__(self, *args, **kwargs):
            raise ImportError("PyTorch required. Install: pip install torch transformers")

    class MultiTaskLoss:
        def __init__(self, *args, **kwargs):
            raise ImportError("PyTorch required")
