#!/usr/bin/env python3
"""
BCVF: Bidirectional Consistency Verification Framework
=======================================================

Patent-pending framework for verifying generation quality through
bidirectional consistency checks.

Core Innovation - Consistency Lagrangian (B1):
    L = λf(1 - sf)² + λb(1 - sb)² + λc(sf - sb)²

Where:
    - sf: Forward feasibility score (linguistic coherence, factual grounding)
    - sb: Backward goal-achievement score (outcome alignment, constraint verification)
    - λf, λb, λc: Penalty weights for forward, backward, and consistency terms

Key Properties:
    - Low sf → penalized (incoherent/unfactual generation)
    - Low sb → penalized (doesn't achieve goal)
    - sf ≠ sb → penalized (inconsistent forward/backward)

The Lagrangian is converted to a weight via:
    w = exp(-β × L)    # Lower Lagrangian → higher weight

And normalized across candidates:
    W(i) = w(i) / Σⱼ w(j)    # Softmax-style probability

Usage:
------
    from symbolu_core.ontological.bcvf import (
        BCVFVerifier,
        ConsistencyLagrangian,
        SemanticEntropyMonitor,
        verify_candidates,
    )

    # Verify multiple candidates
    verifier = BCVFVerifier()
    candidates = ["answer1", "answer2", "answer3"]
    result = verifier.verify(candidates, query="What is 2+2?", goal="Provide correct answer")

    # Get best candidate
    best = result.best_candidate
    print(f"Selected: {best.text} (score: {best.consistency_weight:.3f})")

    # Monitor for hallucination
    entropy_monitor = SemanticEntropyMonitor()
    if entropy_monitor.detect_hallucination(generation_probs):
        print("Warning: Potential hallucination detected!")
"""

from typing import Dict, List, Optional, Tuple, Any, Callable
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

from symbolu_core.ontological.types import LAYER_NAMES, NUM_LAYERS


# =============================================================================
# CONFIGURATION
# =============================================================================

@dataclass
class BCVFConfig:
    """
    Configuration for BCVF verification.

    Attributes:
        lambda_forward: Weight for forward feasibility penalty (λf)
        lambda_backward: Weight for backward goal penalty (λb)
        lambda_consistency: Weight for forward-backward consistency (λc)
        beta: Temperature for exponential weighting
        use_ontological_coherence: Use Bhava coherence in forward score
        hallucination_entropy_threshold: Entropy threshold for hallucination detection
    """
    lambda_forward: float = 1.0
    lambda_backward: float = 1.0
    lambda_consistency: float = 0.5
    beta: float = 2.0
    use_ontological_coherence: bool = True
    hallucination_entropy_threshold: float = 0.7


# =============================================================================
# CONSISTENCY LAGRANGIAN (B1)
# =============================================================================

@dataclass
class ConsistencyScore:
    """
    Consistency scores for a single candidate.

    Attributes:
        forward_score: sf ∈ [0,1] - linguistic coherence, factual grounding
        backward_score: sb ∈ [0,1] - goal achievement, constraint satisfaction
        lagrangian: L = λf(1-sf)² + λb(1-sb)² + λc(sf-sb)²
        consistency_weight: w = exp(-β×L)
        normalized_weight: W = w / Σw (after normalization across candidates)
    """
    forward_score: float
    backward_score: float
    lagrangian: float
    consistency_weight: float
    normalized_weight: float = 0.0

    @property
    def is_consistent(self) -> bool:
        """Check if forward and backward scores are consistent."""
        return abs(self.forward_score - self.backward_score) < 0.2

    @property
    def quality_category(self) -> str:
        """Categorize quality based on scores."""
        if self.forward_score >= 0.8 and self.backward_score >= 0.8:
            return "high_quality"
        elif self.forward_score >= 0.6 and self.backward_score >= 0.6:
            return "acceptable"
        elif self.forward_score >= 0.4 or self.backward_score >= 0.4:
            return "low_quality"
        else:
            return "reject"


class ConsistencyLagrangian:
    """
    Implements the BCVF Consistency Lagrangian (Patent Formula B1).

    Core formula:
        L = λf(1 - sf)² + λb(1 - sb)² + λc(sf - sb)²

    This is the key innovation that:
    1. Penalizes low forward feasibility (incoherent generation)
    2. Penalizes low backward goal achievement (off-target generation)
    3. Penalizes inconsistency between forward and backward (hallucination indicator)

    The quadratic terms ensure:
    - Stronger penalty as scores deviate more from 1.0
    - Smooth, differentiable objective for optimization
    - Balanced multi-objective optimization
    """

    def __init__(self, config: Optional[BCVFConfig] = None):
        self.config = config or BCVFConfig()

    def compute_lagrangian(
        self,
        forward_score: float,
        backward_score: float,
    ) -> float:
        """
        Compute the Consistency Lagrangian L.

        Formula (B1):
            L = λf(1 - sf)² + λb(1 - sb)² + λc(sf - sb)²

        Args:
            forward_score: sf ∈ [0,1]
            backward_score: sb ∈ [0,1]

        Returns:
            Lagrangian value (lower is better)
        """
        sf = np.clip(forward_score, 0.0, 1.0)
        sb = np.clip(backward_score, 0.0, 1.0)

        # Three penalty terms
        forward_penalty = (1.0 - sf) ** 2
        backward_penalty = (1.0 - sb) ** 2
        consistency_penalty = (sf - sb) ** 2

        # Weighted sum
        L = (
            self.config.lambda_forward * forward_penalty +
            self.config.lambda_backward * backward_penalty +
            self.config.lambda_consistency * consistency_penalty
        )

        return float(L)

    def compute_weight(self, lagrangian: float) -> float:
        """
        Convert Lagrangian to consistency weight.

        Formula (B2):
            w = exp(-β × L)

        Lower Lagrangian → higher weight.
        """
        return float(np.exp(-self.config.beta * lagrangian))

    def normalize_weights(self, weights: List[float]) -> List[float]:
        """
        Normalize weights across candidates.

        Formula (B3):
            W(i) = w(i) / Σⱼ w(j)

        Returns probability distribution over candidates.
        """
        total = sum(weights) + 1e-10
        return [w / total for w in weights]

    def score_candidate(
        self,
        forward_score: float,
        backward_score: float,
    ) -> ConsistencyScore:
        """
        Compute full consistency score for a candidate.

        Args:
            forward_score: sf ∈ [0,1]
            backward_score: sb ∈ [0,1]

        Returns:
            ConsistencyScore with all metrics
        """
        lagrangian = self.compute_lagrangian(forward_score, backward_score)
        weight = self.compute_weight(lagrangian)

        return ConsistencyScore(
            forward_score=forward_score,
            backward_score=backward_score,
            lagrangian=lagrangian,
            consistency_weight=weight,
        )

    def score_candidates(
        self,
        forward_scores: List[float],
        backward_scores: List[float],
    ) -> List[ConsistencyScore]:
        """
        Score multiple candidates and normalize weights.

        Args:
            forward_scores: List of sf values
            backward_scores: List of sb values

        Returns:
            List of ConsistencyScore with normalized weights
        """
        if len(forward_scores) != len(backward_scores):
            raise ValueError("Forward and backward score lists must have same length")

        # Compute individual scores
        scores = [
            self.score_candidate(sf, sb)
            for sf, sb in zip(forward_scores, backward_scores)
        ]

        # Normalize weights
        weights = [s.consistency_weight for s in scores]
        normalized = self.normalize_weights(weights)

        # Update normalized weights
        for score, norm_weight in zip(scores, normalized):
            score.normalized_weight = norm_weight

        return scores

    def select_best(
        self,
        candidates: List[Any],
        forward_scores: List[float],
        backward_scores: List[float],
    ) -> Tuple[Any, ConsistencyScore]:
        """
        Select the best candidate based on consistency scores.

        Returns:
            (best_candidate, best_score)
        """
        scores = self.score_candidates(forward_scores, backward_scores)
        best_idx = max(range(len(scores)), key=lambda i: scores[i].normalized_weight)
        return candidates[best_idx], scores[best_idx]


# =============================================================================
# FORWARD SCORER (sf) - Linguistic Coherence & Factual Grounding
# =============================================================================

class ForwardScorer:
    """
    Computes forward feasibility score sf ∈ [0,1].

    Components:
    1. Linguistic coherence - grammatical correctness, fluency
    2. Semantic consistency - internal meaning consistency
    3. Factual grounding - alignment with known facts (if available)
    4. Ontological coherence - Bhava relationship coherence

    The forward scorer answers: "Is this text well-formed and coherent?"
    """

    def __init__(
        self,
        use_ontological: bool = True,
        coherence_weight: float = 0.3,
        fluency_weight: float = 0.3,
        consistency_weight: float = 0.2,
        factual_weight: float = 0.2,
    ):
        self.use_ontological = use_ontological
        self.coherence_weight = coherence_weight
        self.fluency_weight = fluency_weight
        self.consistency_weight = consistency_weight
        self.factual_weight = factual_weight

    def compute_fluency_score(self, text: str) -> float:
        """
        Estimate fluency based on text properties.

        Heuristics:
        - Proper sentence structure
        - Reasonable word length distribution
        - No excessive repetition
        """
        if not text or len(text.strip()) == 0:
            return 0.0

        words = text.split()
        if len(words) < 2:
            return 0.3

        # Check sentence ending
        has_ending = text.strip()[-1] in '.!?'

        # Word length distribution (avg should be 4-8)
        avg_word_len = sum(len(w) for w in words) / len(words)
        length_score = 1.0 - abs(avg_word_len - 6) / 10.0
        length_score = max(0.0, min(1.0, length_score))

        # Repetition check
        unique_ratio = len(set(words)) / len(words)
        repetition_score = unique_ratio

        # Combine
        score = (
            0.3 * (1.0 if has_ending else 0.5) +
            0.3 * length_score +
            0.4 * repetition_score
        )

        return float(np.clip(score, 0.0, 1.0))

    def compute_internal_consistency(
        self,
        text: str,
        ontological_probs: Optional[List[float]] = None,
    ) -> float:
        """
        Check internal semantic consistency.

        Uses ontological layer distribution if available.
        High consistency = coherent meaning throughout.
        """
        if ontological_probs is not None:
            # Use ontological entropy as consistency measure
            # Lower entropy = more focused = more consistent
            probs = np.array(ontological_probs) + 1e-8
            probs = probs / probs.sum()
            entropy = -np.sum(probs * np.log(probs))
            max_entropy = np.log(NUM_LAYERS)
            # Invert: low entropy = high consistency
            consistency = 1.0 - (entropy / max_entropy)
            return float(consistency)

        # Fallback: simple length-based heuristic
        words = text.split()
        if len(words) < 5:
            return 0.5

        # Check for contradictory patterns (simple heuristic)
        contradiction_words = ['but', 'however', 'although', 'yet', 'still']
        contradiction_count = sum(1 for w in words if w.lower() in contradiction_words)

        # Some contradiction is fine, too much suggests inconsistency
        if contradiction_count > len(words) / 10:
            return 0.5
        return 0.8

    def compute_ontological_coherence(
        self,
        ontological_probs: List[float],
        bhava_coherence: Optional[float] = None,
    ) -> float:
        """
        Compute coherence from Bhava relationships.

        Uses pre-computed Bhava coherence if available,
        otherwise estimates from ontological distribution.
        """
        if bhava_coherence is not None:
            return float(np.clip(bhava_coherence, 0.0, 1.0))

        # Estimate from distribution shape
        probs = np.array(ontological_probs) + 1e-8
        probs = probs / probs.sum()

        # Check for dominant layers (good) vs uniform (bad)
        max_prob = np.max(probs)
        top_2_sum = np.sum(np.sort(probs)[-2:])

        # Good coherence = focused on 1-2 layers
        coherence = 0.5 * max_prob + 0.5 * (top_2_sum / 2.0)
        return float(np.clip(coherence * 2.0, 0.0, 1.0))

    def score(
        self,
        text: str,
        ontological_probs: Optional[List[float]] = None,
        bhava_coherence: Optional[float] = None,
        factual_score: Optional[float] = None,
    ) -> float:
        """
        Compute forward feasibility score sf.

        Args:
            text: Generated text to score
            ontological_probs: 12D layer probabilities (optional)
            bhava_coherence: Pre-computed Bhava coherence (optional)
            factual_score: External factual grounding score (optional)

        Returns:
            sf ∈ [0,1] forward feasibility score
        """
        # Component scores
        fluency = self.compute_fluency_score(text)
        consistency = self.compute_internal_consistency(text, ontological_probs)

        # Ontological coherence
        if self.use_ontological and ontological_probs is not None:
            coherence = self.compute_ontological_coherence(
                ontological_probs, bhava_coherence
            )
        else:
            coherence = 0.7  # Default neutral

        # Factual grounding
        if factual_score is not None:
            factual = factual_score
        else:
            factual = 0.7  # Default neutral

        # Weighted combination
        sf = (
            self.fluency_weight * fluency +
            self.consistency_weight * consistency +
            self.coherence_weight * coherence +
            self.factual_weight * factual
        )

        return float(np.clip(sf, 0.0, 1.0))


# =============================================================================
# BACKWARD SCORER (sb) - Goal Achievement & Constraint Verification
# =============================================================================

class BackwardScorer:
    """
    Computes backward goal-achievement score sb ∈ [0,1].

    Components:
    1. Goal alignment - does output address the query/goal?
    2. Constraint satisfaction - does output meet requirements?
    3. Outcome simulation - would this output achieve desired outcome?
    4. Completeness - does output fully address the goal?

    The backward scorer answers: "Does this text achieve what was asked?"
    """

    def __init__(
        self,
        alignment_weight: float = 0.4,
        constraint_weight: float = 0.2,
        completeness_weight: float = 0.2,
        outcome_weight: float = 0.2,
    ):
        self.alignment_weight = alignment_weight
        self.constraint_weight = constraint_weight
        self.completeness_weight = completeness_weight
        self.outcome_weight = outcome_weight

    def compute_keyword_alignment(
        self,
        text: str,
        goal: str,
    ) -> float:
        """
        Check keyword overlap between text and goal.

        Simple but effective proxy for goal alignment.
        """
        text_words = set(text.lower().split())
        goal_words = set(goal.lower().split())

        # Remove common words
        stopwords = {'the', 'a', 'an', 'is', 'are', 'was', 'were', 'be', 'to', 'of', 'and', 'in', 'that', 'it'}
        text_words = text_words - stopwords
        goal_words = goal_words - stopwords

        if not goal_words:
            return 0.5

        overlap = len(text_words & goal_words)
        alignment = overlap / len(goal_words)

        return float(np.clip(alignment, 0.0, 1.0))

    def compute_ontological_alignment(
        self,
        text_probs: List[float],
        goal_probs: List[float],
    ) -> float:
        """
        Check ontological layer alignment between text and goal.

        Good alignment = text focuses on same layers as goal.
        """
        text_p = np.array(text_probs) + 1e-8
        goal_p = np.array(goal_probs) + 1e-8

        text_p = text_p / text_p.sum()
        goal_p = goal_p / goal_p.sum()

        # Cosine similarity
        similarity = np.dot(text_p, goal_p) / (np.linalg.norm(text_p) * np.linalg.norm(goal_p))

        return float(np.clip(similarity, 0.0, 1.0))

    def compute_length_completeness(
        self,
        text: str,
        expected_length: Optional[int] = None,
    ) -> float:
        """
        Check if text length is appropriate for the task.

        Too short = incomplete, too long = verbose.
        """
        text_len = len(text.split())

        if expected_length is not None:
            # Ratio-based scoring
            ratio = text_len / expected_length
            if 0.5 <= ratio <= 1.5:
                return 1.0
            elif 0.25 <= ratio <= 2.0:
                return 0.7
            else:
                return 0.4

        # Default: reasonable length range
        if 10 <= text_len <= 200:
            return 1.0
        elif 5 <= text_len <= 300:
            return 0.7
        else:
            return 0.4

    def check_constraints(
        self,
        text: str,
        constraints: Optional[List[Callable[[str], bool]]] = None,
    ) -> float:
        """
        Check if text satisfies given constraints.

        Constraints are functions that return True if satisfied.
        """
        if not constraints:
            return 0.8  # Default neutral

        satisfied = sum(1 for c in constraints if c(text))
        return satisfied / len(constraints)

    def score(
        self,
        text: str,
        goal: str,
        text_ontological_probs: Optional[List[float]] = None,
        goal_ontological_probs: Optional[List[float]] = None,
        constraints: Optional[List[Callable[[str], bool]]] = None,
        expected_length: Optional[int] = None,
    ) -> float:
        """
        Compute backward goal-achievement score sb.

        Args:
            text: Generated text to score
            goal: The goal/query to achieve
            text_ontological_probs: 12D probs for text (optional)
            goal_ontological_probs: 12D probs for goal (optional)
            constraints: List of constraint functions (optional)
            expected_length: Expected word count (optional)

        Returns:
            sb ∈ [0,1] backward goal-achievement score
        """
        # Keyword alignment
        keyword_align = self.compute_keyword_alignment(text, goal)

        # Ontological alignment (if available)
        if text_ontological_probs is not None and goal_ontological_probs is not None:
            onto_align = self.compute_ontological_alignment(
                text_ontological_probs, goal_ontological_probs
            )
            alignment = 0.5 * keyword_align + 0.5 * onto_align
        else:
            alignment = keyword_align

        # Constraint satisfaction
        constraint_score = self.check_constraints(text, constraints)

        # Completeness
        completeness = self.compute_length_completeness(text, expected_length)

        # Outcome simulation (simplified - would need task-specific logic)
        # For now, use alignment as proxy
        outcome = alignment

        # Weighted combination
        sb = (
            self.alignment_weight * alignment +
            self.constraint_weight * constraint_score +
            self.completeness_weight * completeness +
            self.outcome_weight * outcome
        )

        return float(np.clip(sb, 0.0, 1.0))


# =============================================================================
# SEMANTIC ENTROPY MONITOR (S5) - Hallucination Detection
# =============================================================================

class SemanticEntropyMonitor:
    """
    Monitors semantic entropy for hallucination detection.

    Formula (S5):
        Hₛₑₘ(t) = -Σ pₖ log pₖ

    Key Insight:
    - High entropy spike during generation = potential hallucination
    - Stable/decreasing entropy = coherent generation
    - Stability constraint: dHₛₑₘ/dt ≤ 0 for coherent generation
    """

    def __init__(
        self,
        threshold: float = 0.7,
        spike_threshold: float = 0.3,
        window_size: int = 5,
    ):
        """
        Initialize entropy monitor.

        Args:
            threshold: Absolute entropy threshold (normalized 0-1)
            spike_threshold: Maximum allowed entropy increase between steps
            window_size: Window for smoothing entropy measurements
        """
        self.threshold = threshold
        self.spike_threshold = spike_threshold
        self.window_size = window_size
        self.history: List[float] = []

    def compute_entropy(
        self,
        probabilities: List[float],
        normalize: bool = True,
    ) -> float:
        """
        Compute semantic entropy.

        Formula: Hₛₑₘ = -Σ pₖ log pₖ
        """
        probs = np.array(probabilities) + 1e-10
        probs = probs / probs.sum()

        entropy = -np.sum(probs * np.log(probs))

        if normalize:
            # Normalize by max entropy (log of vocabulary/dimension size)
            max_entropy = np.log(len(probabilities))
            entropy = entropy / max_entropy

        return float(entropy)

    def update(self, probabilities: List[float]) -> float:
        """
        Update entropy history and return current entropy.
        """
        entropy = self.compute_entropy(probabilities)
        self.history.append(entropy)

        # Keep window size
        if len(self.history) > self.window_size * 2:
            self.history = self.history[-self.window_size * 2:]

        return entropy

    def get_entropy_trend(self) -> float:
        """
        Get entropy trend (positive = increasing = bad).

        Returns derivative approximation.
        """
        if len(self.history) < 2:
            return 0.0

        recent = self.history[-self.window_size:] if len(self.history) >= self.window_size else self.history
        if len(recent) < 2:
            return 0.0

        # Simple derivative: last - first
        trend = recent[-1] - recent[0]
        return float(trend)

    def detect_spike(self) -> bool:
        """
        Detect entropy spike (sudden increase).

        Spike = potential hallucination.
        """
        if len(self.history) < 2:
            return False

        current = self.history[-1]
        previous = self.history[-2]

        return (current - previous) > self.spike_threshold

    def detect_hallucination(
        self,
        probabilities: Optional[List[float]] = None,
    ) -> bool:
        """
        Detect potential hallucination.

        Hallucination indicators:
        1. High absolute entropy
        2. Entropy spike
        3. Increasing entropy trend (violates dH/dt ≤ 0)
        """
        if probabilities is not None:
            self.update(probabilities)

        if not self.history:
            return False

        current_entropy = self.history[-1]

        # Check absolute threshold
        if current_entropy > self.threshold:
            return True

        # Check for spike
        if self.detect_spike():
            return True

        # Check trend (should be decreasing for coherent generation)
        trend = self.get_entropy_trend()
        if trend > self.spike_threshold:
            return True

        return False

    def get_confidence(self) -> float:
        """
        Get confidence in current generation (inverse of hallucination risk).

        Returns value in [0, 1] where 1 = high confidence, 0 = likely hallucination.
        """
        if not self.history:
            return 0.5

        current = self.history[-1]

        # Confidence decreases with entropy
        base_confidence = 1.0 - current

        # Penalize spikes
        if self.detect_spike():
            base_confidence *= 0.5

        # Penalize increasing trend
        trend = self.get_entropy_trend()
        if trend > 0:
            base_confidence *= (1.0 - min(trend, 1.0))

        return float(np.clip(base_confidence, 0.0, 1.0))

    def reset(self):
        """Reset entropy history."""
        self.history = []


# =============================================================================
# BCVF VERIFIER (Complete System)
# =============================================================================

@dataclass
class VerifiedCandidate:
    """A candidate with its verification scores."""
    text: str
    index: int
    forward_score: float
    backward_score: float
    lagrangian: float
    consistency_weight: float
    normalized_weight: float
    hallucination_risk: float
    quality_category: str
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class VerificationResult:
    """Result of BCVF verification."""
    candidates: List[VerifiedCandidate]
    best_index: int
    best_candidate: VerifiedCandidate
    mean_forward_score: float
    mean_backward_score: float
    mean_consistency: float
    hallucination_detected: bool

    def get_top_k(self, k: int = 3) -> List[VerifiedCandidate]:
        """Get top-k candidates by normalized weight."""
        sorted_candidates = sorted(
            self.candidates,
            key=lambda c: c.normalized_weight,
            reverse=True
        )
        return sorted_candidates[:k]


class BCVFVerifier:
    """
    Complete BCVF verification system.

    Integrates:
    - Consistency Lagrangian (B1-B3)
    - Forward Scorer (sf)
    - Backward Scorer (sb)
    - Semantic Entropy Monitor (S5)

    Usage:
        verifier = BCVFVerifier()

        # Verify candidates
        result = verifier.verify(
            candidates=["answer1", "answer2", "answer3"],
            query="What is 2+2?",
            goal="Provide the correct numerical answer"
        )

        print(f"Best: {result.best_candidate.text}")
        print(f"Score: {result.best_candidate.consistency_weight:.3f}")
    """

    def __init__(self, config: Optional[BCVFConfig] = None):
        self.config = config or BCVFConfig()
        self.lagrangian = ConsistencyLagrangian(self.config)
        self.forward_scorer = ForwardScorer(
            use_ontological=self.config.use_ontological_coherence
        )
        self.backward_scorer = BackwardScorer()
        self.entropy_monitor = SemanticEntropyMonitor(
            threshold=self.config.hallucination_entropy_threshold
        )

    def verify_single(
        self,
        text: str,
        goal: str,
        ontological_probs: Optional[List[float]] = None,
        goal_ontological_probs: Optional[List[float]] = None,
        bhava_coherence: Optional[float] = None,
        constraints: Optional[List[Callable[[str], bool]]] = None,
    ) -> Tuple[float, float, ConsistencyScore]:
        """
        Verify a single candidate.

        Returns:
            (forward_score, backward_score, consistency_score)
        """
        # Forward score
        sf = self.forward_scorer.score(
            text=text,
            ontological_probs=ontological_probs,
            bhava_coherence=bhava_coherence,
        )

        # Backward score
        sb = self.backward_scorer.score(
            text=text,
            goal=goal,
            text_ontological_probs=ontological_probs,
            goal_ontological_probs=goal_ontological_probs,
            constraints=constraints,
        )

        # Consistency score
        score = self.lagrangian.score_candidate(sf, sb)

        return sf, sb, score

    def verify(
        self,
        candidates: List[str],
        query: str,
        goal: Optional[str] = None,
        ontological_probs_list: Optional[List[List[float]]] = None,
        goal_ontological_probs: Optional[List[float]] = None,
        bhava_coherences: Optional[List[float]] = None,
        constraints: Optional[List[Callable[[str], bool]]] = None,
    ) -> VerificationResult:
        """
        Verify multiple candidates and select the best.

        Args:
            candidates: List of candidate texts
            query: The original query
            goal: Goal description (defaults to query)
            ontological_probs_list: 12D probs for each candidate
            goal_ontological_probs: 12D probs for goal
            bhava_coherences: Bhava coherence for each candidate
            constraints: Constraint functions

        Returns:
            VerificationResult with ranked candidates
        """
        goal = goal or query
        n = len(candidates)

        # Score each candidate
        forward_scores = []
        backward_scores = []

        for i, text in enumerate(candidates):
            onto_probs = ontological_probs_list[i] if ontological_probs_list else None
            bhava_coh = bhava_coherences[i] if bhava_coherences else None

            sf = self.forward_scorer.score(
                text=text,
                ontological_probs=onto_probs,
                bhava_coherence=bhava_coh,
            )

            sb = self.backward_scorer.score(
                text=text,
                goal=goal,
                text_ontological_probs=onto_probs,
                goal_ontological_probs=goal_ontological_probs,
                constraints=constraints,
            )

            forward_scores.append(sf)
            backward_scores.append(sb)

            # Update entropy monitor
            if onto_probs:
                self.entropy_monitor.update(onto_probs)

        # Compute consistency scores
        consistency_scores = self.lagrangian.score_candidates(
            forward_scores, backward_scores
        )

        # Build verified candidates
        verified = []
        for i, (text, score) in enumerate(zip(candidates, consistency_scores)):
            onto_probs = ontological_probs_list[i] if ontological_probs_list else None

            # Hallucination risk
            if onto_probs:
                self.entropy_monitor.reset()
                self.entropy_monitor.update(onto_probs)
                halluc_risk = 1.0 - self.entropy_monitor.get_confidence()
            else:
                halluc_risk = 0.5

            verified.append(VerifiedCandidate(
                text=text,
                index=i,
                forward_score=score.forward_score,
                backward_score=score.backward_score,
                lagrangian=score.lagrangian,
                consistency_weight=score.consistency_weight,
                normalized_weight=score.normalized_weight,
                hallucination_risk=halluc_risk,
                quality_category=score.quality_category,
            ))

        # Find best
        best_idx = max(range(n), key=lambda i: verified[i].normalized_weight)

        # Check for hallucination
        halluc_detected = any(v.hallucination_risk > 0.7 for v in verified)

        return VerificationResult(
            candidates=verified,
            best_index=best_idx,
            best_candidate=verified[best_idx],
            mean_forward_score=sum(forward_scores) / n,
            mean_backward_score=sum(backward_scores) / n,
            mean_consistency=sum(1.0 - abs(sf - sb) for sf, sb in zip(forward_scores, backward_scores)) / n,
            hallucination_detected=halluc_detected,
        )


# =============================================================================
# PYTORCH MODULE (for training)
# =============================================================================

if PYTORCH_AVAILABLE:

    class BCVFLoss(nn.Module):
        """
        Differentiable BCVF loss for training.

        Implements the Consistency Lagrangian as a training objective.

        Usage:
            loss_fn = BCVFLoss()
            loss = loss_fn(forward_scores, backward_scores)
        """

        def __init__(
            self,
            lambda_forward: float = 1.0,
            lambda_backward: float = 1.0,
            lambda_consistency: float = 0.5,
        ):
            super().__init__()
            self.lambda_f = nn.Parameter(torch.tensor(lambda_forward), requires_grad=False)
            self.lambda_b = nn.Parameter(torch.tensor(lambda_backward), requires_grad=False)
            self.lambda_c = nn.Parameter(torch.tensor(lambda_consistency), requires_grad=False)

        def forward(
            self,
            forward_scores: torch.Tensor,
            backward_scores: torch.Tensor,
        ) -> torch.Tensor:
            """
            Compute BCVF loss.

            Args:
                forward_scores: (batch,) sf values in [0,1]
                backward_scores: (batch,) sb values in [0,1]

            Returns:
                Scalar loss value
            """
            # Clamp to valid range
            sf = torch.clamp(forward_scores, 0.0, 1.0)
            sb = torch.clamp(backward_scores, 0.0, 1.0)

            # Lagrangian components
            forward_penalty = (1.0 - sf) ** 2
            backward_penalty = (1.0 - sb) ** 2
            consistency_penalty = (sf - sb) ** 2

            # Weighted sum
            L = (
                self.lambda_f * forward_penalty +
                self.lambda_b * backward_penalty +
                self.lambda_c * consistency_penalty
            )

            return L.mean()

    class SemanticEntropyLoss(nn.Module):
        """
        Semantic entropy regularization loss.

        Encourages low, stable entropy during generation.
        """

        def __init__(
            self,
            target_entropy: float = 0.3,
            stability_weight: float = 0.1,
        ):
            super().__init__()
            self.target_entropy = target_entropy
            self.stability_weight = stability_weight

        def forward(
            self,
            probabilities: torch.Tensor,
            previous_entropy: Optional[torch.Tensor] = None,
        ) -> torch.Tensor:
            """
            Compute entropy loss.

            Args:
                probabilities: (batch, vocab) or (batch, dims) probability distribution
                previous_entropy: Optional previous entropy for stability

            Returns:
                Scalar loss
            """
            # Compute entropy
            probs = probabilities + 1e-10
            probs = probs / probs.sum(dim=-1, keepdim=True)
            entropy = -torch.sum(probs * torch.log(probs), dim=-1)

            # Normalize
            max_entropy = torch.log(torch.tensor(probs.shape[-1], dtype=torch.float32))
            normalized_entropy = entropy / max_entropy

            # Target entropy loss
            target_loss = (normalized_entropy - self.target_entropy) ** 2

            # Stability loss (entropy should not increase)
            if previous_entropy is not None:
                stability_loss = F.relu(normalized_entropy - previous_entropy)
                total_loss = target_loss + self.stability_weight * stability_loss
            else:
                total_loss = target_loss

            return total_loss.mean()


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

def verify_candidates(
    candidates: List[str],
    query: str,
    goal: Optional[str] = None,
    config: Optional[BCVFConfig] = None,
) -> VerificationResult:
    """
    Convenience function to verify candidates.

    Args:
        candidates: List of candidate texts
        query: Original query
        goal: Goal description (optional, defaults to query)
        config: BCVF configuration (optional)

    Returns:
        VerificationResult with ranked candidates

    Example:
        >>> candidates = ["4", "four", "2+2=4"]
        >>> result = verify_candidates(candidates, "What is 2+2?")
        >>> print(result.best_candidate.text)
    """
    verifier = BCVFVerifier(config)
    return verifier.verify(candidates, query, goal)


def compute_consistency_lagrangian(
    forward_score: float,
    backward_score: float,
    lambda_f: float = 1.0,
    lambda_b: float = 1.0,
    lambda_c: float = 0.5,
) -> float:
    """
    Compute the Consistency Lagrangian directly.

    Formula: L = λf(1-sf)² + λb(1-sb)² + λc(sf-sb)²

    Args:
        forward_score: sf ∈ [0,1]
        backward_score: sb ∈ [0,1]
        lambda_f, lambda_b, lambda_c: Penalty weights

    Returns:
        Lagrangian value (lower is better)
    """
    sf = np.clip(forward_score, 0.0, 1.0)
    sb = np.clip(backward_score, 0.0, 1.0)

    L = (
        lambda_f * (1.0 - sf) ** 2 +
        lambda_b * (1.0 - sb) ** 2 +
        lambda_c * (sf - sb) ** 2
    )

    return float(L)


def get_bcvf_summary() -> str:
    """Get summary of BCVF module."""
    return """
================================================================================
BCVF: Bidirectional Consistency Verification Framework
================================================================================

CORE FORMULA - Consistency Lagrangian (B1):
    L = λf(1 - sf)² + λb(1 - sb)² + λc(sf - sb)²

COMPONENTS:
    - sf: Forward feasibility score (linguistic coherence, factual grounding)
    - sb: Backward goal-achievement score (goal alignment, constraints)
    - λf, λb, λc: Penalty weights (default 1.0, 1.0, 0.5)

WEIGHT CONVERSION (B2):
    w = exp(-β × L)    # Lower Lagrangian → higher weight

NORMALIZATION (B3):
    W(i) = w(i) / Σⱼ w(j)    # Probability over candidates

HALLUCINATION DETECTION (S5):
    Hₛₑₘ(t) = -Σ pₖ log pₖ    # Semantic entropy
    Spike detection: dH/dt > threshold → hallucination risk

WHY THIS WORKS:
    1. Low sf → penalized (incoherent generation)
    2. Low sb → penalized (doesn't achieve goal)
    3. sf ≠ sb → penalized (inconsistent = hallucination indicator)

USAGE:
    from symbolu_core.ontological.bcvf import verify_candidates, BCVFVerifier

    # Quick verification
    result = verify_candidates(
        candidates=["answer1", "answer2"],
        query="What is 2+2?"
    )
    print(result.best_candidate.text)

    # Full control
    verifier = BCVFVerifier()
    result = verifier.verify(candidates, query, goal)

================================================================================
"""


if __name__ == "__main__":
    print(get_bcvf_summary())

    # Example usage
    print("\nExample Usage:")
    print("-" * 60)

    candidates = [
        "The answer is 4.",
        "2 plus 2 equals four, which is a natural number.",
        "Maybe it's 5? Or could be 3?",
        "4",
    ]

    result = verify_candidates(
        candidates=candidates,
        query="What is 2+2?",
        goal="Provide the correct numerical answer clearly"
    )

    print(f"Best candidate: '{result.best_candidate.text}'")
    print(f"  Forward score (sf): {result.best_candidate.forward_score:.3f}")
    print(f"  Backward score (sb): {result.best_candidate.backward_score:.3f}")
    print(f"  Lagrangian (L): {result.best_candidate.lagrangian:.3f}")
    print(f"  Weight: {result.best_candidate.normalized_weight:.3f}")
    print(f"  Quality: {result.best_candidate.quality_category}")

    print("\nAll candidates ranked:")
    for c in result.get_top_k(4):
        print(f"  [{c.index}] '{c.text[:40]}...' W={c.normalized_weight:.3f}")
