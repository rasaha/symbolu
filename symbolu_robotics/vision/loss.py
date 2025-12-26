"""
Symbol-U Vision Loss Functions
==============================

Custom loss functions that incorporate Symbol-U principles:

L_total = L_task + λ·L_align + μ·L_consistency + ν·L_phase

- L_task: Standard task loss (cross-entropy, etc.)
- L_align: Cross-layer alignment (adjacent layers should be coherent)
- L_consistency: Global coherence should be high
- L_phase: Layer coherences should all exceed threshold
"""

from typing import Dict, List, Optional, Any

import torch
import torch.nn as nn
import torch.nn.functional as F


def compute_alignment_loss(
    layer_embeddings: List[torch.Tensor],
    adjacency_only: bool = True,
) -> torch.Tensor:
    """
    Compute cross-layer alignment loss.

    Adjacent ontological layers should have similar representations
    (smooth transition from Sensory → Feature → Object → etc.)

    Args:
        layer_embeddings: List of [B, D] tensors, one per layer
        adjacency_only: If True, only compare adjacent layers

    Returns:
        Alignment loss (lower = better alignment)
    """
    if len(layer_embeddings) < 2:
        return torch.tensor(0.0, device=layer_embeddings[0].device)

    total_loss = 0.0
    num_pairs = 0

    for i in range(len(layer_embeddings) - 1):
        if adjacency_only:
            # Only compare adjacent layers
            j_range = [i + 1]
        else:
            # Compare all subsequent layers (weighted by distance)
            j_range = range(i + 1, len(layer_embeddings))

        for j in j_range:
            # Cosine similarity (1 = aligned, 0 = orthogonal, -1 = opposite)
            similarity = F.cosine_similarity(
                layer_embeddings[i],
                layer_embeddings[j],
                dim=-1
            ).mean()

            # Loss = 1 - similarity (want high similarity)
            # Weight by distance (closer layers should be more similar)
            distance_weight = 1.0 / (j - i) if not adjacency_only else 1.0
            total_loss += (1 - similarity) * distance_weight
            num_pairs += distance_weight

    return total_loss / num_pairs if num_pairs > 0 else total_loss


def compute_consistency_loss(
    global_coherence: torch.Tensor,
    target_coherence: float = 0.9,
) -> torch.Tensor:
    """
    Compute consistency loss based on global coherence.

    Global coherence should be high (close to 1.0).

    Args:
        global_coherence: Scalar or [B] tensor of coherence values
        target_coherence: Target coherence level

    Returns:
        Consistency loss (lower = better)
    """
    # Squared error from target
    return (target_coherence - global_coherence) ** 2


def compute_phase_loss(
    coherence_per_layer: List[torch.Tensor],
    threshold: float = 0.7,
) -> torch.Tensor:
    """
    Compute phase coherence loss.

    All layers should have coherence above threshold.

    Args:
        coherence_per_layer: List of coherence scores per layer
        threshold: Minimum acceptable coherence

    Returns:
        Phase loss (lower = better, 0 if all above threshold)
    """
    total_loss = torch.tensor(0.0, device=coherence_per_layer[0].device)

    for coherence in coherence_per_layer:
        # ReLU: only penalize if below threshold
        violation = F.relu(threshold - coherence)
        total_loss += violation ** 2

    return total_loss / len(coherence_per_layer)


def compute_hierarchy_loss(
    layer_embeddings: List[torch.Tensor],
) -> torch.Tensor:
    """
    Compute hierarchy preservation loss.

    Higher layers should have more abstract (compressed) representations.
    Measured by variance - higher layers should have lower variance
    across the batch (more unified representations).

    Args:
        layer_embeddings: List of [B, D] tensors

    Returns:
        Hierarchy loss
    """
    variances = []
    for emb in layer_embeddings:
        # Variance across batch dimension
        var = emb.var(dim=0).mean()
        variances.append(var)

    # Higher layers should have lower variance (more unified)
    # Penalize if variance increases with layer index
    total_loss = torch.tensor(0.0, device=layer_embeddings[0].device)

    for i in range(len(variances) - 1):
        # Variance should decrease or stay same
        violation = F.relu(variances[i + 1] - variances[i])
        total_loss += violation

    return total_loss / (len(variances) - 1) if len(variances) > 1 else total_loss


def compute_orthogonality_loss(
    layer_embeddings: List[torch.Tensor],
) -> torch.Tensor:
    """
    Compute orthogonality loss for layer embeddings.

    Different layers should capture different information
    (not be too similar). This encourages diverse representations.

    Args:
        layer_embeddings: List of [B, D] tensors

    Returns:
        Orthogonality loss (encourages some diversity)
    """
    if len(layer_embeddings) < 2:
        return torch.tensor(0.0, device=layer_embeddings[0].device)

    # Stack embeddings: [num_layers, B, D]
    stacked = torch.stack(layer_embeddings, dim=0)

    # Mean across batch: [num_layers, D]
    mean_emb = stacked.mean(dim=1)

    # Normalize
    mean_emb = F.normalize(mean_emb, dim=-1)

    # Gram matrix: [num_layers, num_layers]
    gram = torch.matmul(mean_emb, mean_emb.T)

    # We want diagonal to be 1 (self-similarity) but off-diagonal
    # to have some value (not 0, but not 1 either)
    # Target: off-diagonal around 0.5 (some similarity but not identical)
    num_layers = len(layer_embeddings)
    mask = ~torch.eye(num_layers, dtype=torch.bool, device=gram.device)

    off_diag = gram[mask]

    # Penalize if off-diagonal is too high (>0.9) or too low (<0.1)
    too_high = F.relu(off_diag - 0.9)
    too_low = F.relu(0.1 - off_diag)

    return (too_high.mean() + too_low.mean()) / 2


class SymbolULoss(nn.Module):
    """
    Complete Symbol-U loss function.

    L_total = L_task + λ·L_align + μ·L_consistency + ν·L_phase + γ·L_hierarchy

    This loss function trains the network to:
    1. Perform the task (classification, etc.)
    2. Maintain cross-layer coherence
    3. Keep global coherence high
    4. Ensure all layers have sufficient phase coherence
    5. Preserve ontological hierarchy (optional)
    """

    def __init__(
        self,
        task_loss_fn: Optional[nn.Module] = None,
        lambda_align: float = 0.1,
        mu_consistency: float = 0.1,
        nu_phase: float = 0.05,
        gamma_hierarchy: float = 0.0,
        delta_orthogonality: float = 0.0,
        coherence_threshold: float = 0.7,
        target_coherence: float = 0.9,
    ):
        """
        Args:
            task_loss_fn: Loss function for main task (default: CrossEntropyLoss)
            lambda_align: Weight for alignment loss
            mu_consistency: Weight for consistency loss
            nu_phase: Weight for phase loss
            gamma_hierarchy: Weight for hierarchy loss (0 to disable)
            delta_orthogonality: Weight for orthogonality loss (0 to disable)
            coherence_threshold: Threshold for phase loss
            target_coherence: Target for consistency loss
        """
        super().__init__()

        self.task_loss_fn = task_loss_fn or nn.CrossEntropyLoss()
        self.lambda_align = lambda_align
        self.mu_consistency = mu_consistency
        self.nu_phase = nu_phase
        self.gamma_hierarchy = gamma_hierarchy
        self.delta_orthogonality = delta_orthogonality
        self.coherence_threshold = coherence_threshold
        self.target_coherence = target_coherence

    def forward(
        self,
        outputs: Dict[str, Any],
        targets: torch.Tensor,
    ) -> Dict[str, torch.Tensor]:
        """
        Compute total loss with breakdown.

        Args:
            outputs: Model outputs dictionary with:
                - logits: [B, num_classes]
                - layer_embeddings: List of [B, D] (optional)
                - global_coherence: scalar
                - coherence_per_layer: List of scalars
            targets: Ground truth labels [B]

        Returns:
            Dictionary with total loss and breakdown
        """
        # Task loss
        L_task = self.task_loss_fn(outputs['logits'], targets)

        # Initialize auxiliary losses
        L_align = torch.tensor(0.0, device=L_task.device)
        L_consistency = torch.tensor(0.0, device=L_task.device)
        L_phase = torch.tensor(0.0, device=L_task.device)
        L_hierarchy = torch.tensor(0.0, device=L_task.device)
        L_orthogonality = torch.tensor(0.0, device=L_task.device)

        # Alignment loss (requires layer embeddings)
        if 'layer_embeddings' in outputs and self.lambda_align > 0:
            L_align = compute_alignment_loss(outputs['layer_embeddings'])

        # Consistency loss
        if 'global_coherence' in outputs and self.mu_consistency > 0:
            L_consistency = compute_consistency_loss(
                outputs['global_coherence'],
                self.target_coherence
            )

        # Phase loss
        if 'coherence_per_layer' in outputs and self.nu_phase > 0:
            L_phase = compute_phase_loss(
                outputs['coherence_per_layer'],
                self.coherence_threshold
            )

        # Hierarchy loss (optional)
        if 'layer_embeddings' in outputs and self.gamma_hierarchy > 0:
            L_hierarchy = compute_hierarchy_loss(outputs['layer_embeddings'])

        # Orthogonality loss (optional)
        if 'layer_embeddings' in outputs and self.delta_orthogonality > 0:
            L_orthogonality = compute_orthogonality_loss(
                outputs['layer_embeddings']
            )

        # Total loss
        L_total = (
            L_task +
            self.lambda_align * L_align +
            self.mu_consistency * L_consistency +
            self.nu_phase * L_phase +
            self.gamma_hierarchy * L_hierarchy +
            self.delta_orthogonality * L_orthogonality
        )

        return {
            'loss': L_total,
            'task_loss': L_task,
            'align_loss': L_align,
            'consistency_loss': L_consistency,
            'phase_loss': L_phase,
            'hierarchy_loss': L_hierarchy,
            'orthogonality_loss': L_orthogonality,
        }


class SymbolUContrastiveLoss(nn.Module):
    """
    Contrastive loss for Symbol-U embeddings.

    Trains embeddings such that:
    - Same-class samples have high coherence across layers
    - Different-class samples have low coherence

    Useful for learning rich ontological representations.
    """

    def __init__(
        self,
        temperature: float = 0.07,
        layer_weights: Optional[List[float]] = None,
    ):
        super().__init__()
        self.temperature = temperature
        self.layer_weights = layer_weights

    def forward(
        self,
        layer_embeddings: List[torch.Tensor],
        labels: torch.Tensor,
    ) -> torch.Tensor:
        """
        Args:
            layer_embeddings: List of [B, D] tensors
            labels: Class labels [B]

        Returns:
            Contrastive loss
        """
        # Default weights: higher layers weighted more
        if self.layer_weights is None:
            weights = [i / 10.0 for i in range(1, 11)]
        else:
            weights = self.layer_weights

        total_loss = torch.tensor(0.0, device=labels.device)

        for i, (emb, w) in enumerate(zip(layer_embeddings, weights)):
            # Normalize embeddings
            emb = F.normalize(emb, dim=-1)

            # Similarity matrix
            sim = torch.matmul(emb, emb.T) / self.temperature

            # Create positive mask (same class)
            labels_eq = labels.unsqueeze(0) == labels.unsqueeze(1)
            labels_eq = labels_eq.float()

            # Remove self-similarity
            mask = ~torch.eye(len(labels), dtype=torch.bool, device=labels.device)
            labels_eq = labels_eq * mask.float()

            # InfoNCE-style loss
            exp_sim = torch.exp(sim) * mask.float()
            pos_sim = (exp_sim * labels_eq).sum(dim=1)
            all_sim = exp_sim.sum(dim=1)

            # Avoid log(0)
            layer_loss = -torch.log(pos_sim / (all_sim + 1e-8) + 1e-8)
            layer_loss = layer_loss[labels_eq.sum(dim=1) > 0].mean()

            if not torch.isnan(layer_loss):
                total_loss += w * layer_loss

        return total_loss / sum(weights)


# ============================================================================
# Utility Functions
# ============================================================================

def get_coherence_metrics(
    outputs: Dict[str, Any],
) -> Dict[str, float]:
    """
    Extract coherence metrics from model outputs.

    Returns:
        Dictionary of metrics for logging
    """
    metrics = {}

    if 'global_coherence' in outputs:
        gc = outputs['global_coherence']
        if isinstance(gc, torch.Tensor):
            metrics['global_coherence'] = gc.item()
        else:
            metrics['global_coherence'] = gc

    if 'coherence_per_layer' in outputs:
        for i, c in enumerate(outputs['coherence_per_layer']):
            if isinstance(c, torch.Tensor):
                metrics[f'layer_{i+1}_coherence'] = c.mean().item()
            else:
                metrics[f'layer_{i+1}_coherence'] = c

        # Statistics
        coherences = [
            c.mean().item() if isinstance(c, torch.Tensor) else c
            for c in outputs['coherence_per_layer']
        ]
        metrics['min_layer_coherence'] = min(coherences)
        metrics['max_layer_coherence'] = max(coherences)
        metrics['mean_layer_coherence'] = sum(coherences) / len(coherences)

    return metrics
