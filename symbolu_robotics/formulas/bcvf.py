# Symbolu Robotics - BCVF Formulas
"""
BCVF: Bidirectional Consistency Verification Framework for Robotics

Adapted from the main Symbolu BCVF for action selection in robotic systems.

Core Formulas:

B1 - Consistency Lagrangian:
    L = λf(1 - sf)² + λb(1 - sb)² + λc(sf - sb)²

    Where for robotics:
    - sf: Forward feasibility score (is action physically executable?)
    - sb: Backward goal-achievement score (does action achieve goal?)
    - λf, λb, λc: Penalty weights for forward, backward, consistency

B2 - Weight Conversion:
    w = exp(-β × L)

    Lower Lagrangian → higher weight → better action candidate.

B3 - Normalization:
    W(i) = w(i) / Σⱼ w(j)

    Softmax-style probability over action candidates.

Usage in Robotics:
    - Action selection in deliberative tier
    - Multi-action planning evaluation
    - Grasp candidate ranking
    - Path segment scoring
"""

import numpy as np
from typing import List, Tuple, Optional, Any, Dict
from dataclasses import dataclass


@dataclass
class BCVFConfig:
    """Configuration for BCVF scoring."""
    lambda_forward: float = 1.0      # Weight for forward feasibility penalty
    lambda_backward: float = 1.0     # Weight for backward goal penalty
    lambda_consistency: float = 0.5  # Weight for forward-backward consistency
    beta: float = 2.0                # Temperature for exponential weighting


@dataclass
class ActionScore:
    """Score for a single action candidate."""
    forward_score: float    # sf: Physical feasibility
    backward_score: float   # sb: Goal achievement
    lagrangian: float       # L: Consistency Lagrangian
    weight: float           # w: Raw weight
    normalized_weight: float = 0.0  # W: Normalized probability


def compute_consistency_lagrangian(
    forward_score: float,
    backward_score: float,
    lambda_f: float = 1.0,
    lambda_b: float = 1.0,
    lambda_c: float = 0.5,
) -> float:
    """
    Compute the Consistency Lagrangian (B1).

    Formula:
        L = λf(1 - sf)² + λb(1 - sb)² + λc(sf - sb)²

    Args:
        forward_score: sf ∈ [0,1] - action feasibility
        backward_score: sb ∈ [0,1] - goal achievement
        lambda_f: Forward penalty weight
        lambda_b: Backward penalty weight
        lambda_c: Consistency penalty weight

    Returns:
        Lagrangian value L ≥ 0 (lower is better)

    Example:
        >>> L = compute_consistency_lagrangian(0.9, 0.8)
        >>> print(f"Lagrangian: {L:.4f}")  # Low value = good action
    """
    sf = np.clip(forward_score, 0.0, 1.0)
    sb = np.clip(backward_score, 0.0, 1.0)

    # Three penalty terms
    forward_penalty = (1.0 - sf) ** 2
    backward_penalty = (1.0 - sb) ** 2
    consistency_penalty = (sf - sb) ** 2

    # B1: Weighted sum
    L = (
        lambda_f * forward_penalty +
        lambda_b * backward_penalty +
        lambda_c * consistency_penalty
    )

    return float(L)


def compute_bcvf_weight(
    lagrangian: float,
    beta: float = 2.0,
) -> float:
    """
    Convert Lagrangian to weight (B2).

    Formula:
        w = exp(-β × L)

    Lower Lagrangian produces higher weight.

    Args:
        lagrangian: L value from B1
        beta: Temperature parameter (higher = more selective)

    Returns:
        Weight w ∈ (0, 1]
    """
    return float(np.exp(-beta * lagrangian))


def normalize_bcvf_weights(weights: List[float]) -> List[float]:
    """
    Normalize weights across candidates (B3).

    Formula:
        W(i) = w(i) / Σⱼ w(j)

    Args:
        weights: List of raw weights from B2

    Returns:
        Normalized weights summing to 1.0
    """
    total = sum(weights) + 1e-10
    return [w / total for w in weights]


def score_action_candidates(
    forward_scores: List[float],
    backward_scores: List[float],
    config: Optional[BCVFConfig] = None,
) -> List[ActionScore]:
    """
    Score multiple action candidates using BCVF.

    Applies B1, B2, B3 to rank action candidates.

    Args:
        forward_scores: List of sf values for each candidate
        backward_scores: List of sb values for each candidate
        config: BCVF configuration

    Returns:
        List of ActionScore with normalized weights

    Example:
        >>> forward = [0.9, 0.7, 0.5]  # Feasibility scores
        >>> backward = [0.8, 0.9, 0.6]  # Goal achievement scores
        >>> scores = score_action_candidates(forward, backward)
        >>> best = max(scores, key=lambda s: s.normalized_weight)
    """
    if len(forward_scores) != len(backward_scores):
        raise ValueError("Forward and backward score lists must have same length")

    config = config or BCVFConfig()

    scores = []
    for sf, sb in zip(forward_scores, backward_scores):
        # B1: Compute Lagrangian
        L = compute_consistency_lagrangian(
            sf, sb,
            config.lambda_forward,
            config.lambda_backward,
            config.lambda_consistency
        )

        # B2: Convert to weight
        w = compute_bcvf_weight(L, config.beta)

        scores.append(ActionScore(
            forward_score=sf,
            backward_score=sb,
            lagrangian=L,
            weight=w,
        ))

    # B3: Normalize weights
    raw_weights = [s.weight for s in scores]
    normalized = normalize_bcvf_weights(raw_weights)

    for score, norm_w in zip(scores, normalized):
        score.normalized_weight = norm_w

    return scores


class BCVFScorer:
    """
    Complete BCVF scorer for robotic action selection.

    Integrates with the deliberative tier for multi-action evaluation.

    Usage:
        scorer = BCVFScorer()

        # Score grasp candidates
        candidates = [grasp1, grasp2, grasp3]
        forward_scores = [compute_feasibility(g) for g in candidates]
        backward_scores = [compute_goal_achievement(g) for g in candidates]

        best_idx, best_score = scorer.select_best(
            candidates, forward_scores, backward_scores
        )
    """

    def __init__(self, config: Optional[BCVFConfig] = None):
        self.config = config or BCVFConfig()

    def score(
        self,
        forward_score: float,
        backward_score: float,
    ) -> ActionScore:
        """Score a single action."""
        L = compute_consistency_lagrangian(
            forward_score, backward_score,
            self.config.lambda_forward,
            self.config.lambda_backward,
            self.config.lambda_consistency
        )
        w = compute_bcvf_weight(L, self.config.beta)

        return ActionScore(
            forward_score=forward_score,
            backward_score=backward_score,
            lagrangian=L,
            weight=w,
        )

    def score_candidates(
        self,
        forward_scores: List[float],
        backward_scores: List[float],
    ) -> List[ActionScore]:
        """Score multiple candidates with normalization."""
        return score_action_candidates(
            forward_scores, backward_scores, self.config
        )

    def select_best(
        self,
        candidates: List[Any],
        forward_scores: List[float],
        backward_scores: List[float],
    ) -> Tuple[int, ActionScore]:
        """
        Select the best candidate.

        Returns:
            (best_index, best_score)
        """
        scores = self.score_candidates(forward_scores, backward_scores)
        best_idx = max(range(len(scores)), key=lambda i: scores[i].normalized_weight)
        return best_idx, scores[best_idx]

    def compute_forward_score(
        self,
        action: Dict[str, Any],
        robot_state: Dict[str, Any],
    ) -> float:
        """
        Compute forward feasibility score for robotics.

        Considers:
        - Joint limits
        - Collision risk
        - Energy requirements
        - Execution time

        Override this for specific robot implementations.
        """
        score = 1.0

        # Check joint limits (if applicable)
        if 'target_positions' in action and 'joint_limits' in robot_state:
            targets = np.array(action['target_positions'])
            limits = robot_state['joint_limits']
            for i, (t, (lo, hi)) in enumerate(zip(targets, limits)):
                if t < lo or t > hi:
                    score *= 0.5  # Penalty for limit violation

        # Check collision risk (if applicable)
        if 'collision_risk' in action:
            score *= (1.0 - action['collision_risk'])

        # Check energy (if applicable)
        if 'energy_required' in action and 'energy_available' in robot_state:
            if action['energy_required'] > robot_state['energy_available']:
                score *= 0.3

        return float(np.clip(score, 0.0, 1.0))

    def compute_backward_score(
        self,
        action: Dict[str, Any],
        goal: Dict[str, Any],
    ) -> float:
        """
        Compute backward goal-achievement score for robotics.

        Considers:
        - Position accuracy
        - Orientation alignment
        - Task completion potential

        Override this for specific robot implementations.
        """
        score = 1.0

        # Check position goal
        if 'target_position' in goal and 'result_position' in action:
            target = np.array(goal['target_position'])
            result = np.array(action['result_position'])
            dist = np.linalg.norm(target - result)
            tolerance = goal.get('tolerance', 0.01)
            if dist < tolerance:
                score *= 1.0
            else:
                score *= max(0.0, 1.0 - dist / (tolerance * 10))

        # Check orientation goal (if applicable)
        if 'target_orientation' in goal and 'result_orientation' in action:
            # Simple angle difference (in radians)
            angle_diff = abs(goal['target_orientation'] - action['result_orientation'])
            score *= max(0.0, 1.0 - angle_diff / np.pi)

        # Check task completion
        if 'completes_task' in action:
            if not action['completes_task']:
                score *= 0.5

        return float(np.clip(score, 0.0, 1.0))
