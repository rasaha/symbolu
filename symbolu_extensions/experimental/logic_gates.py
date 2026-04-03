#!/usr/bin/env python3
"""
Logic Gates: Axiom Injection and Nyāya-based Inference
========================================================

This module implements the logical constraint components from the Google
Architecture Proposals - bringing classical Indian logic (Nyāya) into
neural architectures.

Components:
-----------
1. Axiom Injection: Hardcoded invariants that cannot be violated
   - "Cannot claim certainty about unknowns"
   - "Cannot simultaneously assert P and ¬P"

2. Vyāpti Checker: Validates pervasion/implication relationships
   - "If smoke, then fire" (hetu → sādhya)
   - Learned from data, but with logical constraints

3. Hetvābhāsa Detector: Detects logical fallacies
   - Circular reasoning
   - False cause
   - Contradiction

Architecture Integration:
------------------------
    CognitiveState[124]
           ↓
    ┌──────────────────┐
    │  Axiom Checker   │ → Block if violated
    └────────┬─────────┘
             ↓
    ┌──────────────────┐
    │  Vyāpti Checker  │ → Validate implications
    └────────┬─────────┘
             ↓
    ┌──────────────────┐
    │ Hetvābhāsa Gate  │ → Block fallacious outputs
    └────────┬─────────┘
             ↓
    Logically Valid Output

Nyāya Logic Background:
----------------------
The five-membered syllogism (pañcāvayava):
1. Pratijñā (thesis): "The hill has fire"
2. Hetu (reason): "Because it has smoke"
3. Udāharaṇa (example): "Whatever has smoke has fire, like a kitchen"
4. Upanaya (application): "This hill has smoke"
5. Nigamana (conclusion): "Therefore, this hill has fire"

Vyāpti = Universal concomitance: "Wherever smoke, there fire"
Hetvābhāsa = Fallacious reason that appears valid but isn't

Usage:
------
    from symbolu_extensions.experimental.logic_gates import (
        AxiomChecker,
        VyaptiChecker,
        HetvabhasaDetector,
        LogicGate,
    )

    # Check axiom violations
    axiom_checker = AxiomChecker()
    valid, violations = axiom_checker(cognitive_state)

    # Check implication validity
    vyapti = VyaptiChecker(num_concepts=64)
    validity = vyapti(premise_embedding, conclusion_embedding)
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from enum import Enum
import math


# =============================================================================
# AXIOM TYPES
# =============================================================================

class AxiomType(Enum):
    """Types of hardcoded axioms."""
    NO_UNKNOWN_CERTAINTY = "no_unknown_certainty"
    NO_CONTRADICTION = "no_contradiction"
    COHERENCE_BOUND = "coherence_bound"
    ENTROPY_CONFIDENCE_INVERSE = "entropy_confidence_inverse"
    ONTOLOGY_VALID_PROBABILITY = "ontology_valid_probability"


@dataclass
class AxiomViolation:
    """Record of an axiom violation."""
    axiom: AxiomType
    severity: float  # 0-1
    message: str
    details: Dict[str, Any]


# =============================================================================
# AXIOM CHECKER
# =============================================================================

class AxiomChecker(nn.Module):
    """
    Hardcoded axioms that cannot be violated.

    These are "physics-level" constraints - not learned, not overridable.
    They represent fundamental logical truths that the system must obey.

    Axioms:
    -------
    1. NO_UNKNOWN_CERTAINTY:
       "Cannot claim high confidence about high-entropy states"
       confidence > τ_high AND entropy > τ_high → VIOLATION

    2. NO_CONTRADICTION:
       "Ontology distribution must be valid probability"
       Any P(bhava_i) < 0 or sum(P) ≠ 1 → VIOLATION

    3. COHERENCE_BOUND:
       "Coherence must be in [0, 1]"
       coherence < 0 or coherence > 1 → VIOLATION

    4. ENTROPY_CONFIDENCE_INVERSE:
       "High entropy should correlate with low confidence"
       Soft constraint: penalize when both high

    5. ONTOLOGY_VALID_PROBABILITY:
       "Bhava probabilities must sum to 1 and be non-negative"
    """

    def __init__(
        self,
        confidence_threshold: float = 0.8,
        entropy_threshold: float = 0.7,
        tolerance: float = 1e-3,
    ):
        """
        Args:
            confidence_threshold: Above this, claiming certainty
            entropy_threshold: Above this, high uncertainty
            tolerance: Numerical tolerance for probability checks
        """
        super().__init__()
        self.confidence_threshold = confidence_threshold
        self.entropy_threshold = entropy_threshold
        self.tolerance = tolerance

        # Indices in the 124-dim cognitive state
        # Phoneme: 0-43, Topic: 44-107, Ontology: 108-119, Dynamics: 120-123
        self.ontology_start = 108
        self.ontology_end = 120
        self.coherence_idx = 120
        self.entropy_idx = 121
        self.confidence_idx = 122
        self.momentum_idx = 123

    def forward(
        self,
        cognitive_state: torch.Tensor,
    ) -> Tuple[torch.Tensor, List[AxiomViolation]]:
        """
        Check all axioms for violations.

        Args:
            cognitive_state: [B, T, 124] or [B, 124] cognitive states

        Returns:
            valid: [B, T] or [B] boolean tensor (True = no violations)
            violations: List of detected violations
        """
        # Handle dimensions
        if cognitive_state.dim() == 2:
            cognitive_state = cognitive_state.unsqueeze(1)
            squeeze_output = True
        else:
            squeeze_output = False

        B, T, D = cognitive_state.shape
        device = cognitive_state.device

        violations = []
        valid = torch.ones(B, T, dtype=torch.bool, device=device)

        # Extract components
        ontology = cognitive_state[:, :, self.ontology_start:self.ontology_end]
        coherence = cognitive_state[:, :, self.coherence_idx]
        entropy = cognitive_state[:, :, self.entropy_idx]
        confidence = cognitive_state[:, :, self.confidence_idx]

        # 1. NO_UNKNOWN_CERTAINTY
        # High confidence AND high entropy → violation
        high_confidence = confidence > self.confidence_threshold
        high_entropy = entropy > self.entropy_threshold
        certainty_violation = high_confidence & high_entropy

        if certainty_violation.any():
            valid = valid & ~certainty_violation
            violations.append(AxiomViolation(
                axiom=AxiomType.NO_UNKNOWN_CERTAINTY,
                severity=certainty_violation.float().mean().item(),
                message="Cannot claim certainty about uncertain states",
                details={
                    'violation_count': certainty_violation.sum().item(),
                    'max_confidence': confidence[certainty_violation].max().item() if certainty_violation.any() else 0,
                    'max_entropy': entropy[certainty_violation].max().item() if certainty_violation.any() else 0,
                }
            ))

        # 2. ONTOLOGY_VALID_PROBABILITY
        # Sum should be ~1, all values non-negative
        ontology_sum = ontology.sum(dim=-1)
        sum_violation = (ontology_sum - 1.0).abs() > self.tolerance
        negative_violation = (ontology < -self.tolerance).any(dim=-1)
        prob_violation = sum_violation | negative_violation

        if prob_violation.any():
            valid = valid & ~prob_violation
            violations.append(AxiomViolation(
                axiom=AxiomType.ONTOLOGY_VALID_PROBABILITY,
                severity=prob_violation.float().mean().item(),
                message="Ontology must be valid probability distribution",
                details={
                    'sum_violations': sum_violation.sum().item(),
                    'negative_violations': negative_violation.sum().item(),
                    'worst_sum': (ontology_sum - 1.0).abs().max().item(),
                }
            ))

        # 3. COHERENCE_BOUND
        # Coherence must be in [0, 1]
        coherence_violation = (coherence < 0) | (coherence > 1)

        if coherence_violation.any():
            valid = valid & ~coherence_violation
            violations.append(AxiomViolation(
                axiom=AxiomType.COHERENCE_BOUND,
                severity=coherence_violation.float().mean().item(),
                message="Coherence must be in [0, 1]",
                details={
                    'violation_count': coherence_violation.sum().item(),
                    'min_coherence': coherence.min().item(),
                    'max_coherence': coherence.max().item(),
                }
            ))

        if squeeze_output:
            valid = valid.squeeze(1)

        return valid, violations

    def compute_loss(
        self,
        cognitive_state: torch.Tensor,
    ) -> torch.Tensor:
        """
        Compute soft axiom violation loss.

        This is a differentiable loss that penalizes axiom violations.
        """
        if cognitive_state.dim() == 2:
            cognitive_state = cognitive_state.unsqueeze(1)

        ontology = cognitive_state[:, :, self.ontology_start:self.ontology_end]
        entropy = cognitive_state[:, :, self.entropy_idx]
        confidence = cognitive_state[:, :, self.confidence_idx]

        # Soft penalty for certainty about unknowns
        # Loss = max(0, confidence - threshold) * max(0, entropy - threshold)
        certainty_loss = (
            F.relu(confidence - self.confidence_threshold) *
            F.relu(entropy - self.entropy_threshold)
        ).mean()

        # Probability validity loss
        ontology_sum_loss = (ontology.sum(dim=-1) - 1.0).abs().mean()
        ontology_negative_loss = F.relu(-ontology).sum(dim=-1).mean()

        total_loss = certainty_loss + ontology_sum_loss + ontology_negative_loss

        return total_loss


# =============================================================================
# VYĀPTI CHECKER (Implication Validator)
# =============================================================================

class VyaptiChecker(nn.Module):
    """
    Vyāpti Checker: Validates universal concomitance (implication).

    Vyāpti (व्याप्ति) = "pervading" or "pervasion"

    In Nyāya logic: "Wherever there is smoke, there is fire"
    - Smoke is the hetu (reason/premise)
    - Fire is the sādhya (probandum/conclusion)
    - The relationship is the vyāpti

    This module learns valid vyāpti relationships from data and
    validates that implications in the model's reasoning are sound.

    Architecture:
    - Premise encoder: Embeds the reason/evidence
    - Conclusion encoder: Embeds the claim being made
    - Vyāpti matrix: Learned implication relationships
    - Validation head: Outputs validity score

    The key insight: valid implications should be CONSISTENT across
    examples. If "smoke → fire" holds, it should always hold.
    """

    def __init__(
        self,
        embed_dim: int = 64,
        num_concepts: int = 64,  # Number of learnable "concept" slots
        hidden_dim: int = 128,
    ):
        """
        Args:
            embed_dim: Dimension of premise/conclusion embeddings
            num_concepts: Number of abstract concept representations
            hidden_dim: Hidden dimension for validation network
        """
        super().__init__()
        self.embed_dim = embed_dim
        self.num_concepts = num_concepts

        # Learnable concept embeddings (like a "concept codebook")
        self.concept_embeddings = nn.Parameter(
            torch.randn(num_concepts, embed_dim) * 0.1
        )

        # Vyāpti matrix: V[i, j] = strength of implication concept_i → concept_j
        # Initialize with mild diagonal dominance (concepts imply themselves)
        V_init = torch.eye(num_concepts) * 0.5 + torch.randn(num_concepts, num_concepts) * 0.1
        self.vyapti_matrix = nn.Parameter(V_init)

        # Projection to concept space
        self.premise_proj = nn.Linear(embed_dim, num_concepts)
        self.conclusion_proj = nn.Linear(embed_dim, num_concepts)

        # Validation network
        self.validator = nn.Sequential(
            nn.Linear(num_concepts * 2, hidden_dim),
            nn.GELU(),
            nn.Linear(hidden_dim, 1),
            nn.Sigmoid(),
        )

    def forward(
        self,
        premise: torch.Tensor,
        conclusion: torch.Tensor,
    ) -> Dict[str, torch.Tensor]:
        """
        Check if premise validly implies conclusion.

        Args:
            premise: [B, embed_dim] embedding of the reason
            conclusion: [B, embed_dim] embedding of the claim

        Returns:
            Dict with:
            - validity: [B] implication validity score in [0, 1]
            - concept_alignment: [B] how well concepts align
            - vyapti_strength: [B] strength of the implication
        """
        B = premise.size(0)

        # Project to concept space
        premise_concepts = F.softmax(self.premise_proj(premise), dim=-1)  # [B, num_concepts]
        conclusion_concepts = F.softmax(self.conclusion_proj(conclusion), dim=-1)  # [B, num_concepts]

        # Apply Vyāpti matrix: what conclusion SHOULD follow from premise
        expected_conclusion = torch.matmul(
            premise_concepts,
            torch.sigmoid(self.vyapti_matrix)  # [num_concepts, num_concepts]
        )  # [B, num_concepts]
        expected_conclusion = F.softmax(expected_conclusion, dim=-1)

        # Measure alignment between expected and actual conclusion
        concept_alignment = F.cosine_similarity(
            expected_conclusion,
            conclusion_concepts,
            dim=-1
        )  # [B]

        # Compute vyāpti strength (how strong is the premise→conclusion implication)
        # Uses the learned vyāpti matrix
        vyapti_strength = torch.einsum(
            'bi,ij,bj->b',
            premise_concepts,
            torch.sigmoid(self.vyapti_matrix),
            conclusion_concepts
        )  # [B]

        # Validation network for final score
        combined = torch.cat([premise_concepts, conclusion_concepts], dim=-1)
        validity = self.validator(combined).squeeze(-1)  # [B]

        return {
            'validity': validity,
            'concept_alignment': concept_alignment,
            'vyapti_strength': vyapti_strength,
            'expected_conclusion': expected_conclusion,
            'actual_conclusion': conclusion_concepts,
        }

    def compute_consistency_loss(
        self,
        premises: torch.Tensor,
        conclusions: torch.Tensor,
        labels: torch.Tensor,
    ) -> torch.Tensor:
        """
        Compute loss for learning valid vyāpti relationships.

        Args:
            premises: [B, embed_dim] premise embeddings
            conclusions: [B, embed_dim] conclusion embeddings
            labels: [B] binary labels (1 = valid implication)
        """
        result = self.forward(premises, conclusions)
        validity = result['validity']

        # Binary cross-entropy
        bce_loss = F.binary_cross_entropy(validity, labels.float())

        # Encourage vyāpti matrix to be sparse (not everything implies everything)
        sparsity_loss = torch.sigmoid(self.vyapti_matrix).mean()

        return bce_loss + 0.1 * sparsity_loss


# =============================================================================
# HETVĀBHĀSA DETECTOR (Fallacy Detector)
# =============================================================================

class HetvabhasaType(Enum):
    """Types of logical fallacies (Hetvābhāsa)."""
    ASIDDHA = "asiddha"           # Unestablished reason
    VIRUDDHA = "viruddha"         # Contradictory reason
    ANAIKANTIKA = "anaikantika"   # Inconclusive reason
    PRAKARANASAMA = "prakaranasama"  # Circular reasoning
    KALATYAYAPADISHTA = "kalatyayapadishta"  # Mistimed reason


@dataclass
class FallacyDetection:
    """Result of fallacy detection."""
    detected: bool
    fallacy_type: Optional[HetvabhasaType]
    confidence: float
    explanation: str


class HetvabhasaDetector(nn.Module):
    """
    Hetvābhāsa Detector: Identifies logical fallacies.

    Hetvābhāsa (हेत्वाभास) = "semblance of a reason"
    A reason that appears valid but is actually fallacious.

    Five classical fallacies:
    1. Asiddha: Unestablished premise (premise not proven)
    2. Viruddha: Contradictory (conclusion contradicts premise)
    3. Anaikāntika: Inconclusive (premise doesn't uniquely support conclusion)
    4. Prakaraṇasama: Circular (conclusion is restated as premise)
    5. Kālātyayāpadiṣṭa: Mistimed (reason no longer applicable)

    Implementation:
    - Takes premise-conclusion pairs
    - Runs through fallacy-specific detectors
    - Returns fallacy type and confidence
    """

    def __init__(
        self,
        embed_dim: int = 64,
        hidden_dim: int = 128,
    ):
        super().__init__()
        self.embed_dim = embed_dim

        # Shared encoder for premise-conclusion analysis
        self.encoder = nn.Sequential(
            nn.Linear(embed_dim * 2, hidden_dim),
            nn.GELU(),
            nn.Linear(hidden_dim, hidden_dim),
        )

        # Fallacy-specific heads
        self.fallacy_heads = nn.ModuleDict({
            'asiddha': nn.Linear(hidden_dim, 1),      # Unestablished
            'viruddha': nn.Linear(hidden_dim, 1),     # Contradictory
            'anaikantika': nn.Linear(hidden_dim, 1),  # Inconclusive
            'prakaranasama': nn.Linear(hidden_dim, 1),  # Circular
            'kalatyaya': nn.Linear(hidden_dim, 1),    # Mistimed
        })

        # Overall validity head
        self.validity_head = nn.Linear(hidden_dim, 1)

    def forward(
        self,
        premise: torch.Tensor,
        conclusion: torch.Tensor,
        premise_confidence: Optional[torch.Tensor] = None,
    ) -> Dict[str, torch.Tensor]:
        """
        Detect fallacies in premise-conclusion pair.

        Args:
            premise: [B, embed_dim] premise embedding
            conclusion: [B, embed_dim] conclusion embedding
            premise_confidence: [B] optional confidence in the premise

        Returns:
            Dict with fallacy scores and overall validity
        """
        B = premise.size(0)

        # Encode pair
        combined = torch.cat([premise, conclusion], dim=-1)
        encoded = self.encoder(combined)  # [B, hidden_dim]

        # Detect each fallacy type
        fallacy_scores = {}
        for name, head in self.fallacy_heads.items():
            score = torch.sigmoid(head(encoded)).squeeze(-1)  # [B]
            fallacy_scores[name] = score

        # Special handling for Asiddha (unestablished)
        # If premise confidence is low, Asiddha is more likely
        if premise_confidence is not None:
            asiddha_boost = 1 - premise_confidence
            fallacy_scores['asiddha'] = torch.clamp(
                fallacy_scores['asiddha'] + 0.3 * asiddha_boost,
                0, 1
            )

        # Special handling for Viruddha (contradictory)
        # If premise and conclusion have negative cosine similarity
        cosine_sim = F.cosine_similarity(premise, conclusion, dim=-1)
        contradiction_signal = F.relu(-cosine_sim)  # High when negative
        fallacy_scores['viruddha'] = torch.clamp(
            fallacy_scores['viruddha'] + 0.3 * contradiction_signal,
            0, 1
        )

        # Special handling for Prakaranasama (circular)
        # If premise and conclusion are too similar
        similarity_signal = F.relu(cosine_sim - 0.9)  # High when very similar
        fallacy_scores['prakaranasama'] = torch.clamp(
            fallacy_scores['prakaranasama'] + 0.5 * similarity_signal,
            0, 1
        )

        # Overall validity (low if any fallacy is high)
        max_fallacy = torch.stack(list(fallacy_scores.values()), dim=-1).max(dim=-1)[0]
        validity = 1 - max_fallacy

        return {
            'fallacy_scores': fallacy_scores,
            'validity': validity,
            'max_fallacy_score': max_fallacy,
            'premise_conclusion_similarity': cosine_sim,
        }

    def detect(
        self,
        premise: torch.Tensor,
        conclusion: torch.Tensor,
        threshold: float = 0.5,
    ) -> List[FallacyDetection]:
        """
        Detect fallacies and return human-readable results.

        Args:
            premise: [B, embed_dim] or [embed_dim]
            conclusion: [B, embed_dim] or [embed_dim]
            threshold: Score above which fallacy is considered detected

        Returns:
            List of FallacyDetection objects
        """
        # Handle unbatched input
        if premise.dim() == 1:
            premise = premise.unsqueeze(0)
            conclusion = conclusion.unsqueeze(0)

        result = self.forward(premise, conclusion)

        detections = []
        B = premise.size(0)

        fallacy_names = {
            'asiddha': (HetvabhasaType.ASIDDHA, "Unestablished premise"),
            'viruddha': (HetvabhasaType.VIRUDDHA, "Contradictory reasoning"),
            'anaikantika': (HetvabhasaType.ANAIKANTIKA, "Inconclusive reasoning"),
            'prakaranasama': (HetvabhasaType.PRAKARANASAMA, "Circular reasoning"),
            'kalatyaya': (HetvabhasaType.KALATYAYAPADISHTA, "Mistimed reasoning"),
        }

        for i in range(B):
            # Find highest fallacy score
            max_score = 0
            max_type = None
            max_name = None

            for name, score in result['fallacy_scores'].items():
                if score[i].item() > max_score:
                    max_score = score[i].item()
                    max_type, max_name = fallacy_names[name]

            if max_score > threshold:
                detections.append(FallacyDetection(
                    detected=True,
                    fallacy_type=max_type,
                    confidence=max_score,
                    explanation=f"Detected {max_name} (confidence: {max_score:.2f})",
                ))
            else:
                detections.append(FallacyDetection(
                    detected=False,
                    fallacy_type=None,
                    confidence=1 - max_score,
                    explanation="No fallacy detected",
                ))

        return detections


# =============================================================================
# COMBINED LOGIC GATE
# =============================================================================

class LogicGate(nn.Module):
    """
    Complete Logic Gate combining:
    - Axiom checking (hardcoded constraints)
    - Vyāpti validation (learned implications)
    - Hetvābhāsa detection (fallacy prevention)

    This is the "logical physics" layer that ensures outputs
    are logically consistent, not just statistically likely.

    Usage:
        logic_gate = LogicGate()

        # During generation
        validity, info = logic_gate(
            cognitive_state=state,
            premise=premise_embed,
            conclusion=conclusion_embed,
        )

        if not validity:
            # Block output or modify
            ...
    """

    def __init__(
        self,
        embed_dim: int = 64,
        num_concepts: int = 64,
        confidence_threshold: float = 0.8,
        entropy_threshold: float = 0.7,
    ):
        super().__init__()

        # Components
        self.axiom_checker = AxiomChecker(
            confidence_threshold=confidence_threshold,
            entropy_threshold=entropy_threshold,
        )
        self.vyapti_checker = VyaptiChecker(
            embed_dim=embed_dim,
            num_concepts=num_concepts,
        )
        self.hetvabhasa_detector = HetvabhasaDetector(
            embed_dim=embed_dim,
        )

    def forward(
        self,
        cognitive_state: torch.Tensor,
        premise: Optional[torch.Tensor] = None,
        conclusion: Optional[torch.Tensor] = None,
        check_axioms: bool = True,
        check_vyapti: bool = True,
        check_hetvabhasa: bool = True,
    ) -> Tuple[torch.Tensor, Dict[str, Any]]:
        """
        Run all logic checks.

        Args:
            cognitive_state: [B, T, 124] cognitive state
            premise: [B, embed_dim] optional premise embedding
            conclusion: [B, embed_dim] optional conclusion embedding
            check_*: Flags to enable/disable individual checks

        Returns:
            valid: [B, T] overall validity
            info: Dict with detailed results from each check
        """
        info = {}
        B, T, D = cognitive_state.shape
        device = cognitive_state.device

        valid = torch.ones(B, T, dtype=torch.bool, device=device)

        # 1. Axiom check
        if check_axioms:
            axiom_valid, violations = self.axiom_checker(cognitive_state)
            valid = valid & axiom_valid
            info['axiom_valid'] = axiom_valid
            info['axiom_violations'] = violations

        # 2. Vyāpti check (if premise/conclusion provided)
        if check_vyapti and premise is not None and conclusion is not None:
            vyapti_result = self.vyapti_checker(premise, conclusion)
            vyapti_valid = vyapti_result['validity'] > 0.5
            # Expand to [B, T]
            vyapti_valid = vyapti_valid.unsqueeze(1).expand(-1, T)
            valid = valid & vyapti_valid
            info['vyapti_result'] = vyapti_result
            info['vyapti_valid'] = vyapti_valid

        # 3. Hetvābhāsa check (if premise/conclusion provided)
        if check_hetvabhasa and premise is not None and conclusion is not None:
            hetvabhasa_result = self.hetvabhasa_detector(premise, conclusion)
            hetvabhasa_valid = hetvabhasa_result['validity'] > 0.5
            hetvabhasa_valid = hetvabhasa_valid.unsqueeze(1).expand(-1, T)
            valid = valid & hetvabhasa_valid
            info['hetvabhasa_result'] = hetvabhasa_result
            info['hetvabhasa_valid'] = hetvabhasa_valid

        info['overall_valid'] = valid

        return valid, info

    def compute_loss(
        self,
        cognitive_state: torch.Tensor,
        premise: Optional[torch.Tensor] = None,
        conclusion: Optional[torch.Tensor] = None,
        implication_labels: Optional[torch.Tensor] = None,
    ) -> Dict[str, torch.Tensor]:
        """
        Compute combined logic loss for training.

        Returns:
            Dict with individual and total losses
        """
        losses = {}

        # Axiom loss
        axiom_loss = self.axiom_checker.compute_loss(cognitive_state)
        losses['axiom_loss'] = axiom_loss

        # Vyāpti loss (if labels provided)
        if premise is not None and conclusion is not None and implication_labels is not None:
            vyapti_loss = self.vyapti_checker.compute_consistency_loss(
                premise, conclusion, implication_labels
            )
            losses['vyapti_loss'] = vyapti_loss
        else:
            losses['vyapti_loss'] = torch.tensor(0.0, device=cognitive_state.device)

        # Total
        losses['total_logic_loss'] = losses['axiom_loss'] + losses['vyapti_loss']

        return losses


# =============================================================================
# EXAMPLE USAGE
# =============================================================================

if __name__ == "__main__":
    print("Logic Gates (Nyāya) Module Demo")
    print("=" * 60)

    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')

    # Configuration
    B, T = 2, 10
    state_dim = 124
    embed_dim = 64

    # Create test data
    cognitive_state = torch.randn(B, T, state_dim, device=device)
    # Make ontology valid probabilities (indices 108-119)
    cognitive_state[:, :, 108:120] = F.softmax(cognitive_state[:, :, 108:120], dim=-1)
    # Keep dynamics in valid range (indices 120-123)
    cognitive_state[:, :, 120:124] = torch.sigmoid(cognitive_state[:, :, 120:124])

    premise = torch.randn(B, embed_dim, device=device)
    conclusion = torch.randn(B, embed_dim, device=device)

    # 1. Test AxiomChecker
    print("\n1. AxiomChecker")
    print("-" * 40)
    axiom_checker = AxiomChecker().to(device)
    valid, violations = axiom_checker(cognitive_state)
    print(f"Valid: {valid.all().item()}")
    print(f"Violations: {len(violations)}")
    for v in violations:
        print(f"  - {v.axiom.value}: {v.message} (severity: {v.severity:.2f})")

    axiom_loss = axiom_checker.compute_loss(cognitive_state)
    print(f"Axiom loss: {axiom_loss.item():.4f}")

    # 2. Test VyaptiChecker
    print("\n2. VyaptiChecker (Implication)")
    print("-" * 40)
    vyapti = VyaptiChecker(embed_dim=embed_dim).to(device)
    result = vyapti(premise, conclusion)
    print(f"Validity: {result['validity'].mean().item():.4f}")
    print(f"Concept alignment: {result['concept_alignment'].mean().item():.4f}")
    print(f"Vyāpti strength: {result['vyapti_strength'].mean().item():.4f}")

    # 3. Test HetvabhasaDetector
    print("\n3. HetvabhasaDetector (Fallacy)")
    print("-" * 40)
    hetvabhasa = HetvabhasaDetector(embed_dim=embed_dim).to(device)
    result = hetvabhasa(premise, conclusion)
    print("Fallacy scores:")
    for name, score in result['fallacy_scores'].items():
        print(f"  {name}: {score.mean().item():.4f}")
    print(f"Overall validity: {result['validity'].mean().item():.4f}")

    detections = hetvabhasa.detect(premise, conclusion)
    for i, det in enumerate(detections):
        print(f"Sample {i}: {det.explanation}")

    # 4. Test combined LogicGate
    print("\n4. LogicGate (Combined)")
    print("-" * 40)
    logic_gate = LogicGate(embed_dim=embed_dim).to(device)
    valid, info = logic_gate(cognitive_state, premise, conclusion)
    print(f"Overall valid: {valid.all().item()}")
    print(f"Valid positions: {valid.sum().item()}/{B*T}")

    losses = logic_gate.compute_loss(
        cognitive_state, premise, conclusion,
        implication_labels=torch.ones(B, device=device)
    )
    print(f"Total logic loss: {losses['total_logic_loss'].item():.4f}")

    print("\n" + "=" * 60)
    print("Logic Gates Demo Complete")
