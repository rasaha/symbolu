#!/usr/bin/env python3
"""
RAG Stitching Optimization Module
=================================

Implements the Objective/Stitching Formula for optimal RAG snippet selection:

    S* = argmax Σᵢ relᵢ - λ₁·red(S) - λ₂·dj(S)

Subject to:
    - |S| ≤ K (max K snippets, default K=4)
    - Σᵢ len(sᵢ) ≤ L (total length budget)

Components:
-----------
- Σᵢ relᵢ: Sum of relevance scores (from BhavaRelationshipModule)
- red(S): Redundancy penalty - penalizes overlapping/similar snippets
- dj(S): Domain jump penalty - penalizes switching between topic domains

The optimization selects K snippets that maximize total relevance
while minimizing redundancy and topic fragmentation.

Usage:
------
    from symbolu.ontological.stitching_optimization import (
        StitchingOptimizer,
        RAGSnippet,
        StitchingConfig,
        select_optimal_snippets,
    )

    # Create snippets with relevance scores
    snippets = [
        RAGSnippet(text="...", relevance=0.95, ontological_probs=[...]),
        RAGSnippet(text="...", relevance=0.87, ontological_probs=[...]),
        ...
    ]

    # Select optimal set
    optimizer = StitchingOptimizer()
    selected = optimizer.optimize(snippets, max_k=4, length_budget=2000)
"""

from typing import Dict, List, Optional, Tuple, Any, Set
from dataclasses import dataclass, field
import math

try:
    import torch
    import torch.nn as nn
    import torch.nn.functional as F
    PYTORCH_AVAILABLE = True
except ImportError:
    PYTORCH_AVAILABLE = False

import numpy as np

from symbolu.ontological.types import LAYER_NAMES, NUM_LAYERS


# =============================================================================
# DATA STRUCTURES
# =============================================================================

@dataclass
class RAGSnippet:
    """
    A single RAG snippet with relevance and ontological information.

    Attributes:
        text: The snippet text content
        relevance: Relevance score from BhavaRelationshipModule (0-1)
        ontological_probs: 12D ontological layer probabilities
        domain_id: Optional domain/topic identifier
        length: Character length (computed from text if not provided)
        metadata: Additional metadata (source, page, etc.)
    """
    text: str
    relevance: float
    ontological_probs: List[float]
    domain_id: Optional[int] = None
    length: Optional[int] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if self.length is None:
            self.length = len(self.text)
        if len(self.ontological_probs) != NUM_LAYERS:
            raise ValueError(f"ontological_probs must be {NUM_LAYERS}D, got {len(self.ontological_probs)}")

    @property
    def dominant_layer(self) -> str:
        """Get the dominant ontological layer."""
        idx = int(np.argmax(self.ontological_probs))
        return LAYER_NAMES[idx]

    @property
    def dominant_layer_idx(self) -> int:
        """Get the dominant ontological layer index."""
        return int(np.argmax(self.ontological_probs))


@dataclass
class StitchingConfig:
    """
    Configuration for the stitching optimization.

    Attributes:
        lambda_redundancy: Weight for redundancy penalty (λ₁)
        lambda_domain_jump: Weight for domain jump penalty (λ₂)
        max_k: Maximum number of snippets to select
        length_budget: Maximum total character length
        similarity_threshold: Threshold for considering snippets similar
        use_greedy: Use greedy algorithm (faster) vs beam search (better)
        beam_width: Width for beam search (if not greedy)
    """
    lambda_redundancy: float = 0.3
    lambda_domain_jump: float = 0.2
    max_k: int = 4
    length_budget: int = 4000
    similarity_threshold: float = 0.7
    use_greedy: bool = True
    beam_width: int = 5


@dataclass
class StitchingResult:
    """
    Result of stitching optimization.

    Attributes:
        selected_snippets: List of selected RAGSnippet objects
        selected_indices: Original indices of selected snippets
        total_relevance: Σᵢ relᵢ
        redundancy_penalty: red(S)
        domain_jump_penalty: dj(S)
        objective_value: S* = Σᵢ relᵢ - λ₁·red(S) - λ₂·dj(S)
        total_length: Total character length of selected snippets
    """
    selected_snippets: List[RAGSnippet]
    selected_indices: List[int]
    total_relevance: float
    redundancy_penalty: float
    domain_jump_penalty: float
    objective_value: float
    total_length: int

    def __repr__(self) -> str:
        return (
            f"StitchingResult(\n"
            f"  selected={len(self.selected_snippets)} snippets,\n"
            f"  objective={self.objective_value:.4f},\n"
            f"  relevance={self.total_relevance:.4f},\n"
            f"  redundancy_penalty={self.redundancy_penalty:.4f},\n"
            f"  domain_jump_penalty={self.domain_jump_penalty:.4f},\n"
            f"  total_length={self.total_length}\n"
            f")"
        )


# =============================================================================
# PENALTY FUNCTIONS
# =============================================================================

def compute_ontological_similarity(
    probs_a: List[float],
    probs_b: List[float],
) -> float:
    """
    Compute similarity between two snippets based on ontological profiles.

    Uses Jensen-Shannon divergence (symmetric KL) for distribution comparison.
    Returns similarity in [0, 1] where 1 = identical distributions.
    """
    p = np.array(probs_a) + 1e-8
    q = np.array(probs_b) + 1e-8

    # Normalize
    p = p / p.sum()
    q = q / q.sum()

    # Jensen-Shannon divergence
    m = 0.5 * (p + q)
    kl_pm = np.sum(p * np.log(p / m))
    kl_qm = np.sum(q * np.log(q / m))
    jsd = 0.5 * (kl_pm + kl_qm)

    # Convert to similarity (0 = different, 1 = identical)
    # JSD is bounded [0, ln(2)] for normalized distributions
    similarity = 1.0 - (jsd / np.log(2))
    return float(similarity)


def compute_text_similarity(
    text_a: str,
    text_b: str,
) -> float:
    """
    Compute text similarity using word overlap (Jaccard).

    Simple but effective for redundancy detection.
    Returns similarity in [0, 1].
    """
    words_a = set(text_a.lower().split())
    words_b = set(text_b.lower().split())

    if not words_a or not words_b:
        return 0.0

    intersection = len(words_a & words_b)
    union = len(words_a | words_b)

    return intersection / union if union > 0 else 0.0


def compute_redundancy_penalty(
    snippets: List[RAGSnippet],
    alpha_onto: float = 0.6,
    alpha_text: float = 0.4,
) -> float:
    """
    Compute redundancy penalty red(S) for a set of snippets.

    Formula:
        red(S) = Σᵢ<ⱼ sim(sᵢ, sⱼ) / |S|(|S|-1)/2

    Where sim() combines ontological and text similarity:
        sim(a, b) = α_onto · sim_onto(a,b) + α_text · sim_text(a,b)

    Args:
        snippets: List of snippets to evaluate
        alpha_onto: Weight for ontological similarity
        alpha_text: Weight for text similarity

    Returns:
        Normalized redundancy penalty in [0, 1]
    """
    n = len(snippets)
    if n <= 1:
        return 0.0

    total_sim = 0.0
    num_pairs = 0

    for i in range(n):
        for j in range(i + 1, n):
            onto_sim = compute_ontological_similarity(
                snippets[i].ontological_probs,
                snippets[j].ontological_probs,
            )
            text_sim = compute_text_similarity(
                snippets[i].text,
                snippets[j].text,
            )

            combined_sim = alpha_onto * onto_sim + alpha_text * text_sim
            total_sim += combined_sim
            num_pairs += 1

    # Normalize by number of pairs
    return total_sim / num_pairs if num_pairs > 0 else 0.0


def compute_domain_jump_penalty(
    snippets: List[RAGSnippet],
    use_explicit_domains: bool = True,
) -> float:
    """
    Compute domain jump penalty dj(S) for a set of snippets.

    Two modes:
    1. Explicit domains: Count transitions between different domain_ids
    2. Implicit domains: Use ontological layer distance as domain proxy

    Formula:
        dj(S) = Σᵢ 1[domain(sᵢ) ≠ domain(sᵢ₊₁)] / (|S| - 1)

    Args:
        snippets: Ordered list of snippets
        use_explicit_domains: If True, use domain_id; else use dominant layer

    Returns:
        Normalized domain jump penalty in [0, 1]
    """
    n = len(snippets)
    if n <= 1:
        return 0.0

    jumps = 0

    for i in range(n - 1):
        if use_explicit_domains and snippets[i].domain_id is not None:
            # Use explicit domain IDs
            if snippets[i].domain_id != snippets[i + 1].domain_id:
                jumps += 1
        else:
            # Use dominant ontological layer as domain proxy
            layer_i = snippets[i].dominant_layer_idx
            layer_j = snippets[i + 1].dominant_layer_idx

            # Consider it a "jump" if layers differ significantly
            layer_distance = abs(layer_i - layer_j)
            circular_distance = min(layer_distance, 12 - layer_distance)

            # Threshold: jump if more than 2 layers apart
            if circular_distance > 2:
                jumps += 1

    return jumps / (n - 1)


def compute_domain_jump_penalty_soft(
    snippets: List[RAGSnippet],
) -> float:
    """
    Soft version of domain jump penalty using ontological distance.

    Instead of binary jumps, computes average ontological distance
    between consecutive snippets.

    Formula:
        dj(S) = Σᵢ dist(onto_i, onto_{i+1}) / (|S| - 1)

    Where dist() is 1 - ontological_similarity.

    Returns:
        Average ontological distance in [0, 1]
    """
    n = len(snippets)
    if n <= 1:
        return 0.0

    total_distance = 0.0

    for i in range(n - 1):
        sim = compute_ontological_similarity(
            snippets[i].ontological_probs,
            snippets[i + 1].ontological_probs,
        )
        total_distance += (1.0 - sim)

    return total_distance / (n - 1)


# =============================================================================
# OPTIMIZATION ALGORITHMS
# =============================================================================

class StitchingOptimizer:
    """
    Optimizer for RAG snippet selection using the Objective Formula.

    Implements:
        S* = argmax Σᵢ relᵢ - λ₁·red(S) - λ₂·dj(S)

    Subject to:
        - |S| ≤ K
        - Σᵢ len(sᵢ) ≤ L

    Two algorithms available:
    1. Greedy: Fast O(N·K) approximate solution
    2. Beam Search: Better O(N·K·B) solution with beam width B
    """

    def __init__(self, config: Optional[StitchingConfig] = None):
        self.config = config or StitchingConfig()

    def compute_objective(
        self,
        snippets: List[RAGSnippet],
        lambda_red: Optional[float] = None,
        lambda_dj: Optional[float] = None,
    ) -> Tuple[float, float, float, float]:
        """
        Compute the objective value for a set of snippets.

        Returns:
            (objective, total_relevance, redundancy_penalty, domain_jump_penalty)
        """
        if not snippets:
            return 0.0, 0.0, 0.0, 0.0

        lambda_red = lambda_red or self.config.lambda_redundancy
        lambda_dj = lambda_dj or self.config.lambda_domain_jump

        # Total relevance
        total_relevance = sum(s.relevance for s in snippets)

        # Redundancy penalty
        redundancy = compute_redundancy_penalty(snippets)

        # Domain jump penalty (soft version for smoother optimization)
        domain_jump = compute_domain_jump_penalty_soft(snippets)

        # Objective
        objective = total_relevance - lambda_red * redundancy - lambda_dj * domain_jump

        return objective, total_relevance, redundancy, domain_jump

    def optimize_greedy(
        self,
        snippets: List[RAGSnippet],
        max_k: Optional[int] = None,
        length_budget: Optional[int] = None,
    ) -> StitchingResult:
        """
        Greedy optimization: iteratively add best snippet.

        At each step, adds the snippet that maximizes marginal objective gain
        while respecting constraints.

        Complexity: O(N·K) where N = number of candidates, K = max selection
        """
        max_k = max_k or self.config.max_k
        length_budget = length_budget or self.config.length_budget

        if not snippets:
            return StitchingResult(
                selected_snippets=[],
                selected_indices=[],
                total_relevance=0.0,
                redundancy_penalty=0.0,
                domain_jump_penalty=0.0,
                objective_value=0.0,
                total_length=0,
            )

        # Sort by relevance for tie-breaking
        indexed_snippets = list(enumerate(snippets))
        indexed_snippets.sort(key=lambda x: x[1].relevance, reverse=True)

        selected: List[Tuple[int, RAGSnippet]] = []
        selected_set: Set[int] = set()
        current_length = 0

        while len(selected) < max_k:
            best_gain = float('-inf')
            best_candidate = None

            for orig_idx, snippet in indexed_snippets:
                # Skip if already selected
                if orig_idx in selected_set:
                    continue

                # Check length constraint
                if current_length + snippet.length > length_budget:
                    continue

                # Compute marginal gain
                candidate_set = [s for _, s in selected] + [snippet]
                new_obj, _, _, _ = self.compute_objective(candidate_set)

                if selected:
                    old_obj, _, _, _ = self.compute_objective([s for _, s in selected])
                    gain = new_obj - old_obj
                else:
                    gain = new_obj

                if gain > best_gain:
                    best_gain = gain
                    best_candidate = (orig_idx, snippet)

            # If no valid candidate or negative gain, stop
            if best_candidate is None or best_gain < 0:
                break

            selected.append(best_candidate)
            selected_set.add(best_candidate[0])
            current_length += best_candidate[1].length

        # Build result
        selected_snippets = [s for _, s in selected]
        selected_indices = [idx for idx, _ in selected]

        obj, rel, red, dj = self.compute_objective(selected_snippets)

        return StitchingResult(
            selected_snippets=selected_snippets,
            selected_indices=selected_indices,
            total_relevance=rel,
            redundancy_penalty=red,
            domain_jump_penalty=dj,
            objective_value=obj,
            total_length=current_length,
        )

    def optimize_beam_search(
        self,
        snippets: List[RAGSnippet],
        max_k: Optional[int] = None,
        length_budget: Optional[int] = None,
        beam_width: Optional[int] = None,
    ) -> StitchingResult:
        """
        Beam search optimization: maintain top-B partial solutions.

        Explores multiple promising paths simultaneously for better solutions.

        Complexity: O(N·K·B) where B = beam width
        """
        max_k = max_k or self.config.max_k
        length_budget = length_budget or self.config.length_budget
        beam_width = beam_width or self.config.beam_width

        if not snippets:
            return StitchingResult(
                selected_snippets=[],
                selected_indices=[],
                total_relevance=0.0,
                redundancy_penalty=0.0,
                domain_jump_penalty=0.0,
                objective_value=0.0,
                total_length=0,
            )

        # State: (objective, selected_indices, total_length)
        # Start with empty selection
        beam: List[Tuple[float, List[int], int]] = [(0.0, [], 0)]

        for _ in range(max_k):
            candidates = []

            for obj, selected, length in beam:
                selected_set = set(selected)

                for idx, snippet in enumerate(snippets):
                    if idx in selected_set:
                        continue

                    new_length = length + snippet.length
                    if new_length > length_budget:
                        continue

                    new_selected = selected + [idx]
                    new_snippets = [snippets[i] for i in new_selected]
                    new_obj, _, _, _ = self.compute_objective(new_snippets)

                    candidates.append((new_obj, new_selected, new_length))

            if not candidates:
                break

            # Keep top beam_width candidates
            candidates.sort(key=lambda x: x[0], reverse=True)
            beam = candidates[:beam_width]

        # Best solution
        best_obj, best_indices, best_length = beam[0]
        selected_snippets = [snippets[i] for i in best_indices]

        obj, rel, red, dj = self.compute_objective(selected_snippets)

        return StitchingResult(
            selected_snippets=selected_snippets,
            selected_indices=best_indices,
            total_relevance=rel,
            redundancy_penalty=red,
            domain_jump_penalty=dj,
            objective_value=obj,
            total_length=best_length,
        )

    def optimize(
        self,
        snippets: List[RAGSnippet],
        max_k: Optional[int] = None,
        length_budget: Optional[int] = None,
    ) -> StitchingResult:
        """
        Run optimization using configured algorithm.

        Uses greedy by default (fast), beam search if use_greedy=False.
        """
        if self.config.use_greedy:
            return self.optimize_greedy(snippets, max_k, length_budget)
        else:
            return self.optimize_beam_search(snippets, max_k, length_budget)


# =============================================================================
# PYTORCH MODULE (for end-to-end training)
# =============================================================================

if PYTORCH_AVAILABLE:

    class DifferentiableStitchingModule(nn.Module):
        """
        Differentiable stitching optimization for end-to-end training.

        Uses soft selection instead of hard discrete selection,
        allowing gradients to flow through snippet selection.

        For inference, use StitchingOptimizer (discrete selection).
        For training, use this module (differentiable).
        """

        def __init__(
            self,
            lambda_redundancy: float = 0.3,
            lambda_domain_jump: float = 0.2,
            temperature: float = 1.0,
        ):
            super().__init__()
            self.lambda_redundancy = nn.Parameter(
                torch.tensor(lambda_redundancy), requires_grad=True
            )
            self.lambda_domain_jump = nn.Parameter(
                torch.tensor(lambda_domain_jump), requires_grad=True
            )
            self.temperature = temperature

        def compute_similarity_matrix(
            self,
            ontological_probs: torch.Tensor,
        ) -> torch.Tensor:
            """
            Compute pairwise similarity matrix from ontological probs.

            Args:
                ontological_probs: (N, 12) ontological probabilities

            Returns:
                similarity: (N, N) similarity matrix
            """
            # Normalize
            probs = F.normalize(ontological_probs, p=1, dim=-1)

            # Cosine similarity as proxy for distribution similarity
            similarity = torch.mm(probs, probs.t())

            return similarity

        def compute_soft_redundancy(
            self,
            selection_weights: torch.Tensor,
            similarity_matrix: torch.Tensor,
        ) -> torch.Tensor:
            """
            Compute soft redundancy penalty.

            Args:
                selection_weights: (N,) soft selection weights
                similarity_matrix: (N, N) pairwise similarities

            Returns:
                redundancy: scalar
            """
            # Weight similarities by selection probabilities
            # red = Σᵢⱼ wᵢ wⱼ sim(i,j) / Σᵢⱼ wᵢ wⱼ
            weight_matrix = selection_weights.unsqueeze(0) * selection_weights.unsqueeze(1)

            # Exclude diagonal (self-similarity)
            mask = 1.0 - torch.eye(len(selection_weights), device=selection_weights.device)
            weighted_sim = (weight_matrix * similarity_matrix * mask).sum()
            weight_sum = (weight_matrix * mask).sum() + 1e-8

            return weighted_sim / weight_sum

        def compute_soft_domain_jump(
            self,
            selection_weights: torch.Tensor,
            ontological_probs: torch.Tensor,
        ) -> torch.Tensor:
            """
            Compute soft domain jump penalty.

            Uses weighted ontological distance between snippets.
            """
            n = len(selection_weights)
            if n <= 1:
                return torch.tensor(0.0, device=selection_weights.device)

            # Compute pairwise ontological distances
            similarity = self.compute_similarity_matrix(ontological_probs)
            distance = 1.0 - similarity

            # Weight by selection (consecutive weighting approximation)
            # Use sorted selection weights to approximate ordering
            sorted_weights, _ = torch.sort(selection_weights, descending=True)

            # Approximate consecutive pairs penalty
            total_jump = 0.0
            for i in range(n - 1):
                for j in range(i + 1, n):
                    # Weight by how likely both are selected consecutively
                    pair_weight = sorted_weights[i] * sorted_weights[j]
                    total_jump = total_jump + pair_weight * distance[i, j]

            return total_jump / (n * (n - 1) / 2 + 1e-8)

        def forward(
            self,
            relevance_scores: torch.Tensor,
            ontological_probs: torch.Tensor,
            lengths: Optional[torch.Tensor] = None,
            max_k: int = 4,
            length_budget: Optional[int] = None,
        ) -> Dict[str, torch.Tensor]:
            """
            Compute differentiable stitching objective.

            Args:
                relevance_scores: (N,) relevance per snippet
                ontological_probs: (N, 12) ontological distributions
                lengths: (N,) snippet lengths (optional)
                max_k: Maximum snippets
                length_budget: Length constraint (optional)

            Returns:
                Dict with objective, selection_weights, penalties
            """
            n = len(relevance_scores)

            # Compute soft selection weights using Gumbel-Softmax
            # Higher relevance → higher selection probability
            logits = relevance_scores / self.temperature
            selection_weights = F.softmax(logits, dim=0)

            # Apply top-k approximation (soft)
            if max_k < n:
                topk_mask = torch.zeros_like(selection_weights)
                _, topk_indices = torch.topk(selection_weights, max_k)
                topk_mask[topk_indices] = 1.0
                selection_weights = selection_weights * topk_mask
                selection_weights = selection_weights / (selection_weights.sum() + 1e-8)

            # Compute penalties
            similarity_matrix = self.compute_similarity_matrix(ontological_probs)
            redundancy = self.compute_soft_redundancy(selection_weights, similarity_matrix)
            domain_jump = self.compute_soft_domain_jump(selection_weights, ontological_probs)

            # Total relevance (weighted)
            total_relevance = (selection_weights * relevance_scores).sum()

            # Objective
            objective = (
                total_relevance
                - self.lambda_redundancy * redundancy
                - self.lambda_domain_jump * domain_jump
            )

            return {
                'objective': objective,
                'total_relevance': total_relevance,
                'redundancy_penalty': redundancy,
                'domain_jump_penalty': domain_jump,
                'selection_weights': selection_weights,
                'lambda_redundancy': self.lambda_redundancy,
                'lambda_domain_jump': self.lambda_domain_jump,
            }


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

def select_optimal_snippets(
    snippets: List[RAGSnippet],
    max_k: int = 4,
    length_budget: int = 4000,
    lambda_redundancy: float = 0.3,
    lambda_domain_jump: float = 0.2,
    use_greedy: bool = True,
) -> StitchingResult:
    """
    Convenience function to select optimal snippets.

    Implements:
        S* = argmax Σᵢ relᵢ - λ₁·red(S) - λ₂·dj(S)

    Args:
        snippets: List of RAGSnippet candidates
        max_k: Maximum number of snippets (default 4)
        length_budget: Maximum total length (default 4000)
        lambda_redundancy: Redundancy penalty weight (default 0.3)
        lambda_domain_jump: Domain jump penalty weight (default 0.2)
        use_greedy: Use greedy algorithm (default True)

    Returns:
        StitchingResult with selected snippets and metrics

    Example:
        >>> snippets = [
        ...     RAGSnippet(text="...", relevance=0.95, ontological_probs=[...]),
        ...     RAGSnippet(text="...", relevance=0.87, ontological_probs=[...]),
        ... ]
        >>> result = select_optimal_snippets(snippets, max_k=3)
        >>> print(result.objective_value)
        >>> for s in result.selected_snippets:
        ...     print(s.text[:50])
    """
    config = StitchingConfig(
        lambda_redundancy=lambda_redundancy,
        lambda_domain_jump=lambda_domain_jump,
        max_k=max_k,
        length_budget=length_budget,
        use_greedy=use_greedy,
    )

    optimizer = StitchingOptimizer(config)
    return optimizer.optimize(snippets)


def create_rag_snippet(
    text: str,
    relevance: float,
    ontological_probs: List[float],
    domain_id: Optional[int] = None,
    **metadata,
) -> RAGSnippet:
    """
    Helper to create a RAGSnippet.

    Args:
        text: Snippet text
        relevance: Relevance score (0-1)
        ontological_probs: 12D layer probabilities
        domain_id: Optional domain identifier
        **metadata: Additional metadata

    Returns:
        RAGSnippet instance
    """
    return RAGSnippet(
        text=text,
        relevance=relevance,
        ontological_probs=ontological_probs,
        domain_id=domain_id,
        metadata=metadata,
    )


# =============================================================================
# SUMMARY
# =============================================================================

def get_stitching_summary() -> str:
    """Get summary of the stitching optimization module."""
    return """
================================================================================
RAG STITCHING OPTIMIZATION
================================================================================

OBJECTIVE FORMULA:
    S* = argmax Σᵢ relᵢ - λ₁·red(S) - λ₂·dj(S)

CONSTRAINTS:
    - |S| ≤ K: Maximum K snippets (default K=4)
    - Σᵢ len(sᵢ) ≤ L: Total length budget

COMPONENTS:
    1. Σᵢ relᵢ: Sum of relevance scores from BhavaRelationshipModule
       - Each snippet has a relevance computed via multiplicative formula

    2. red(S): Redundancy penalty
       - Penalizes selecting similar snippets
       - Combines ontological similarity (Jensen-Shannon) + text overlap (Jaccard)
       - Formula: red(S) = avg(sim(sᵢ, sⱼ)) for all pairs i < j

    3. dj(S): Domain jump penalty
       - Penalizes topic fragmentation in the result
       - Uses ontological layer distance as domain proxy
       - Formula: dj(S) = avg(1 - sim(onto_i, onto_{i+1}))

HYPERPARAMETERS:
    - λ₁ (lambda_redundancy): Weight for redundancy (default 0.3)
    - λ₂ (lambda_domain_jump): Weight for domain jumps (default 0.2)

ALGORITHMS:
    1. Greedy (default): O(N·K), fast approximate solution
    2. Beam Search: O(N·K·B), better solution with beam width B

USAGE:
    from symbolu.ontological.stitching_optimization import (
        select_optimal_snippets,
        RAGSnippet,
    )

    snippets = [
        RAGSnippet(text="...", relevance=0.95, ontological_probs=[...]),
        RAGSnippet(text="...", relevance=0.87, ontological_probs=[...]),
    ]

    result = select_optimal_snippets(snippets, max_k=4)
    print(result.objective_value)
    for s in result.selected_snippets:
        print(s.text)

================================================================================
"""


if __name__ == "__main__":
    print(get_stitching_summary())

    # Example usage
    print("\nExample Usage:")
    print("-" * 60)

    # Create sample snippets
    sample_snippets = [
        RAGSnippet(
            text="Consciousness emerges from information integration...",
            relevance=0.95,
            ontological_probs=[0.05, 0.1, 0.1, 0.15, 0.25, 0.1, 0.1, 0.05, 0.05, 0.02, 0.02, 0.01],
        ),
        RAGSnippet(
            text="The hard problem of consciousness remains unsolved...",
            relevance=0.88,
            ontological_probs=[0.08, 0.1, 0.08, 0.12, 0.2, 0.12, 0.15, 0.05, 0.05, 0.02, 0.02, 0.01],
        ),
        RAGSnippet(
            text="Quantum mechanics may play a role in consciousness...",
            relevance=0.72,
            ontological_probs=[0.15, 0.12, 0.1, 0.08, 0.15, 0.1, 0.1, 0.08, 0.05, 0.03, 0.02, 0.02],
        ),
        RAGSnippet(
            text="Neural correlates of consciousness include the prefrontal...",
            relevance=0.85,
            ontological_probs=[0.05, 0.08, 0.15, 0.2, 0.18, 0.12, 0.1, 0.05, 0.03, 0.02, 0.01, 0.01],
        ),
        RAGSnippet(
            text="Integration theory suggests consciousness requires...",
            relevance=0.91,
            ontological_probs=[0.06, 0.1, 0.1, 0.14, 0.22, 0.12, 0.12, 0.06, 0.04, 0.02, 0.01, 0.01],
        ),
    ]

    result = select_optimal_snippets(sample_snippets, max_k=3)
    print(result)

    print("\nSelected snippets:")
    for i, s in enumerate(result.selected_snippets):
        print(f"  {i+1}. {s.text[:50]}... (rel={s.relevance:.2f})")
