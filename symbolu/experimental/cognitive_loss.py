#!/usr/bin/env python3
"""
Cognitive Loss Function: The Chitta Gradient
=============================================

This module implements the loss function that translates human feedback
("vibe checks") into precise gradient updates for State-Delta training.

The Key Insight:
----------------
Traditional RLHF: Human preference → Black-box reward → Gradient
Chitta Gradient:  Human preference → Bhava/Vritti distance → Interpretable gradient

Loss Formula:
-------------
L_cognitive = α·Dist(Vritti_actual, Vritti_ideal) + β·Dist(Bhava_out, Bhava_target)

Where:
- Vritti_actual: The 5-dim Vritti distribution during generation
- Vritti_ideal: What Vritti SHOULD have been based on input Bhava
- Bhava_out: The ontology distribution of the output
- Bhava_target: The expected ontology based on task/context

This allows the model to learn from human feedback by adjusting:
1. How input Bhavas activate Vrittis (R[v,a] matrix)
2. How Vrittis modulate attention (VrittiModulatedAttention)
3. How the model transitions between ontological states

Usage:
------
    from symbolu.experimental import CognitiveLossFunction, DHAValidator

    # During training
    loss_fn = CognitiveLossFunction()
    loss = loss_fn(
        vritti_actual=model_output['vritti'],
        bhava_input=input_state['ontology'],
        bhava_output=output_state['ontology'],
        human_rating=0.8,  # 0-1 scale from feedback
    )
    loss.backward()

    # For diagnosis
    validator = DHAValidator()
    diagnosis = validator.diagnose(
        input_bhava=input_state['ontology'],
        expected_vritti=predicted_vritti,
        actual_vritti=model_output['vritti'],
        output_bhava=output_state['ontology'],
        human_rating=0.3,  # Bad rating
    )
    print(diagnosis)  # "OVER_HEDGED: Vritti was Viparyaya but should have been Pramāṇa"
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from enum import Enum


# =============================================================================
# CONSTANTS: Bhava-Vritti Natural Mapping
# =============================================================================

# Which Vritti should activate for each Bhava (from our sparse mapping)
BHAVA_TO_IDEAL_VRITTI = torch.tensor([
    # [Pramāṇa, Viparyaya, Vikalpa, Smṛti, Nidrā]
    [0.9, 0.0, 0.0, 0.1, 0.0],  # 0: FACTUAL → Pramāṇa
    [0.7, 0.0, 0.2, 0.1, 0.0],  # 1: ANALYTICAL → Pramāṇa + light Vikalpa
    [0.3, 0.1, 0.1, 0.5, 0.0],  # 2: EVALUATIVE → Smṛti (memory-based judgment)
    [0.1, 0.0, 0.4, 0.5, 0.0],  # 3: NARRATIVE → Smṛti + Vikalpa
    [0.2, 0.6, 0.1, 0.1, 0.0],  # 4: ARGUMENTATIVE → Viparyaya
    [0.8, 0.0, 0.1, 0.1, 0.0],  # 5: INSTRUCTIVE → Pramāṇa
    [0.9, 0.0, 0.0, 0.1, 0.0],  # 6: CERTAIN → Pramāṇa
    [0.1, 0.4, 0.5, 0.0, 0.0],  # 7: SPECULATIVE → Vikalpa + Viparyaya
    [0.1, 0.1, 0.8, 0.0, 0.0],  # 8: QUESTIONING → Vikalpa
    [0.0, 0.1, 0.1, 0.1, 0.7],  # 9: EMOTIVE → Nidrā
    [0.3, 0.0, 0.4, 0.2, 0.1],  # 10: PERFORMATIVE → Mixed
    [0.2, 0.0, 0.2, 0.1, 0.5],  # 11: METALINGUISTIC → Nidrā
])

# Ideal Bhava transitions (what output Bhava should follow input Bhava)
# e.g., QUESTIONING → FACTUAL is a healthy transition
HEALTHY_TRANSITIONS = {
    8: [0, 1, 5, 6],      # QUESTIONING → FACTUAL, ANALYTICAL, INSTRUCTIVE, CERTAIN
    7: [0, 1, 6, 7],      # SPECULATIVE → can stay or become FACTUAL/CERTAIN
    0: [0, 1, 2, 5],      # FACTUAL → can deepen to ANALYTICAL or EVALUATIVE
    4: [0, 4, 1],         # ARGUMENTATIVE → FACTUAL (resolution) or continue
    3: [3, 0, 2],         # NARRATIVE → continue or conclude with FACTUAL
}

VRITTI_NAMES = ['Pramāṇa', 'Viparyaya', 'Vikalpa', 'Smṛti', 'Nidrā']
BHAVA_NAMES = [
    'FACTUAL', 'ANALYTICAL', 'EVALUATIVE', 'NARRATIVE',
    'ARGUMENTATIVE', 'INSTRUCTIVE', 'CERTAIN', 'SPECULATIVE',
    'QUESTIONING', 'EMOTIVE', 'PERFORMATIVE', 'METALINGUISTIC'
]


# =============================================================================
# DIAGNOSTIC TYPES
# =============================================================================

class DiagnosisType(Enum):
    """Types of cognitive failures."""
    VALIDATED = "validated"              # Everything worked
    VRITTI_MISMATCH = "vritti_mismatch"  # Wrong Vritti activated
    BHAVA_MISMATCH = "bhava_mismatch"    # Wrong output Bhava
    OVER_HEDGED = "over_hedged"          # Too much Viparyaya when Pramāṇa needed
    OVER_CONFIDENT = "over_confident"    # Too much Pramāṇa when Viparyaya needed
    STUCK = "stuck"                      # Smṛti too high, not progressing
    DISENGAGED = "disengaged"            # Nidrā too high inappropriately
    TRANSITION_ERROR = "transition_error"  # Unhealthy Bhava transition


@dataclass
class CognitiveDiagnosis:
    """Result of cognitive validation."""
    type: DiagnosisType
    message: str
    vritti_distance: float
    bhava_distance: float
    recommended_adjustment: str
    details: Dict[str, Any]


# =============================================================================
# COGNITIVE LOSS FUNCTION
# =============================================================================

class CognitiveLossFunction(nn.Module):
    """
    The Chitta Gradient: Translates human feedback into interpretable loss.

    L_cognitive = α·Dist(Vritti_actual, Vritti_ideal)
                + β·Dist(Bhava_out, Bhava_target)
                + γ·TransitionPenalty

    This is "Interpretable RLHF" - every component of the loss is explainable.
    """

    def __init__(
        self,
        alpha: float = 0.4,      # Weight for Vritti alignment
        beta: float = 0.4,       # Weight for Bhava alignment
        gamma: float = 0.2,      # Weight for transition quality
        distance_type: str = "kl",  # "kl", "cosine", or "mse"
    ):
        super().__init__()
        self.alpha = alpha
        self.beta = beta
        self.gamma = gamma
        self.distance_type = distance_type

        # Register the ideal mapping as a buffer (not trainable)
        self.register_buffer(
            'bhava_to_vritti',
            BHAVA_TO_IDEAL_VRITTI
        )

    def forward(
        self,
        vritti_actual: torch.Tensor,      # [B, T, 5] or [B, 5]
        bhava_input: torch.Tensor,         # [B, T, 12] or [B, 12] input ontology
        bhava_output: torch.Tensor,        # [B, T, 12] or [B, 12] output ontology
        human_rating: Optional[torch.Tensor] = None,  # [B] 0-1 rating
        bhava_target: Optional[torch.Tensor] = None,  # [B, 12] explicit target
    ) -> Dict[str, torch.Tensor]:
        """
        Compute cognitive loss.

        Args:
            vritti_actual: Actual Vritti distribution from model
            bhava_input: Input ontology distribution (what triggered generation)
            bhava_output: Output ontology distribution (what was generated)
            human_rating: Optional human feedback (0=bad, 1=good)
            bhava_target: Optional explicit target Bhava (if known)

        Returns:
            Dict with 'total_loss', 'vritti_loss', 'bhava_loss', 'transition_loss'
        """
        # Handle different input shapes
        if vritti_actual.dim() == 3:
            vritti_actual = vritti_actual.mean(dim=1)  # [B, 5]
        if bhava_input.dim() == 3:
            bhava_input = bhava_input[:, -1, :]  # Use last position [B, 12]
        if bhava_output.dim() == 3:
            bhava_output = bhava_output[:, -1, :]  # [B, 12]

        B = vritti_actual.size(0)

        # 1. Compute ideal Vritti from input Bhava
        # vritti_ideal = bhava_input @ bhava_to_vritti
        vritti_ideal = torch.matmul(
            bhava_input,
            self.bhava_to_vritti.to(bhava_input.device)
        )  # [B, 5]
        vritti_ideal = F.softmax(vritti_ideal, dim=-1)

        # 2. Vritti alignment loss
        vritti_loss = self._compute_distance(vritti_actual, vritti_ideal)

        # 3. Bhava alignment loss
        if bhava_target is not None:
            bhava_loss = self._compute_distance(bhava_output, bhava_target)
        else:
            # Infer target from healthy transitions
            bhava_target_inferred = self._infer_target_bhava(bhava_input)
            bhava_loss = self._compute_distance(bhava_output, bhava_target_inferred)

        # 4. Transition quality loss
        transition_loss = self._compute_transition_penalty(bhava_input, bhava_output)

        # 5. Scale by human rating if provided
        if human_rating is not None:
            # High rating → low loss multiplier, Low rating → high loss multiplier
            rating_scale = 2.0 - human_rating  # 1.0 (good) → 1.0, 0.0 (bad) → 2.0
            vritti_loss = vritti_loss * rating_scale
            bhava_loss = bhava_loss * rating_scale
            transition_loss = transition_loss * rating_scale

        # 6. Combine losses
        total_loss = (
            self.alpha * vritti_loss +
            self.beta * bhava_loss +
            self.gamma * transition_loss
        )

        return {
            'total_loss': total_loss.mean(),
            'vritti_loss': vritti_loss.mean(),
            'bhava_loss': bhava_loss.mean(),
            'transition_loss': transition_loss.mean(),
            'vritti_actual': vritti_actual,
            'vritti_ideal': vritti_ideal,
        }

    def _compute_distance(
        self,
        p: torch.Tensor,
        q: torch.Tensor,
    ) -> torch.Tensor:
        """Compute distance between distributions."""
        if self.distance_type == "kl":
            # KL divergence (asymmetric)
            p_log = torch.log(p + 1e-9)
            q_log = torch.log(q + 1e-9)
            return F.kl_div(p_log, q, reduction='none').sum(dim=-1)
        elif self.distance_type == "cosine":
            # Cosine distance
            return 1 - F.cosine_similarity(p, q, dim=-1)
        else:  # mse
            return F.mse_loss(p, q, reduction='none').sum(dim=-1)

    def _infer_target_bhava(self, bhava_input: torch.Tensor) -> torch.Tensor:
        """Infer target Bhava from input using healthy transitions."""
        B, num_bhava = bhava_input.shape
        device = bhava_input.device

        # Get dominant input Bhava
        dominant_input = bhava_input.argmax(dim=-1)  # [B]

        # Build target distributions
        targets = torch.zeros(B, num_bhava, device=device)

        for i in range(B):
            input_idx = dominant_input[i].item()
            if input_idx in HEALTHY_TRANSITIONS:
                # Spread probability over healthy targets
                healthy_targets = HEALTHY_TRANSITIONS[input_idx]
                prob = 1.0 / len(healthy_targets)
                for t in healthy_targets:
                    targets[i, t] = prob
            else:
                # Default: stay in same state or go to FACTUAL
                targets[i, input_idx] = 0.5
                targets[i, 0] = 0.5  # FACTUAL as fallback

        return targets

    def _compute_transition_penalty(
        self,
        bhava_input: torch.Tensor,
        bhava_output: torch.Tensor,
    ) -> torch.Tensor:
        """Penalize unhealthy Bhava transitions."""
        B = bhava_input.size(0)
        device = bhava_input.device

        input_dominant = bhava_input.argmax(dim=-1)
        output_dominant = bhava_output.argmax(dim=-1)

        penalties = torch.zeros(B, device=device)

        for i in range(B):
            in_idx = input_dominant[i].item()
            out_idx = output_dominant[i].item()

            if in_idx in HEALTHY_TRANSITIONS:
                if out_idx not in HEALTHY_TRANSITIONS[in_idx]:
                    # Unhealthy transition
                    penalties[i] = 1.0
            # else: no penalty for unlisted transitions

        return penalties


# =============================================================================
# DHA VALIDATOR (Post-Generation Diagnostic)
# =============================================================================

class DHAValidator:
    """
    Dynamic Heuristic Adjustment Validator.

    Post-generation diagnostic that:
    1. Checks if Vritti matched expectations
    2. Checks if output Bhava was appropriate
    3. Diagnoses specific failure modes
    4. Recommends threshold adjustments
    """

    def __init__(self):
        self.bhava_to_vritti = BHAVA_TO_IDEAL_VRITTI

    def diagnose(
        self,
        input_bhava: torch.Tensor,        # [12] input ontology probs
        actual_vritti: torch.Tensor,       # [5] actual Vritti during generation
        output_bhava: torch.Tensor,        # [12] output ontology probs
        human_rating: float,               # 0-1 human feedback
        expected_vritti: Optional[torch.Tensor] = None,  # [5] if pre-computed
    ) -> CognitiveDiagnosis:
        """
        Diagnose cognitive performance.

        Args:
            input_bhava: What triggered generation
            actual_vritti: What Vritti was active
            output_bhava: What was generated
            human_rating: Human satisfaction (0=bad, 1=good)
            expected_vritti: Optional pre-computed ideal Vritti

        Returns:
            CognitiveDiagnosis with type, message, and recommendations
        """
        # Ensure tensors are 1D
        if input_bhava.dim() > 1:
            input_bhava = input_bhava.squeeze()
        if actual_vritti.dim() > 1:
            actual_vritti = actual_vritti.squeeze()
        if output_bhava.dim() > 1:
            output_bhava = output_bhava.squeeze()

        # Compute expected Vritti from input Bhava
        if expected_vritti is None:
            expected_vritti = F.softmax(
                input_bhava @ self.bhava_to_vritti.to(input_bhava.device),
                dim=-1
            )

        # Compute distances
        vritti_dist = F.cosine_similarity(
            actual_vritti.unsqueeze(0),
            expected_vritti.unsqueeze(0)
        ).item()
        vritti_distance = 1 - vritti_dist

        # Infer target Bhava
        input_dominant = input_bhava.argmax().item()
        output_dominant = output_bhava.argmax().item()

        healthy_targets = HEALTHY_TRANSITIONS.get(input_dominant, [input_dominant, 0])
        bhava_aligned = output_dominant in healthy_targets
        bhava_distance = 0.0 if bhava_aligned else 1.0

        # Get dominant Vritti names
        actual_vritti_idx = actual_vritti.argmax().item()
        expected_vritti_idx = expected_vritti.argmax().item()
        actual_vritti_name = VRITTI_NAMES[actual_vritti_idx]
        expected_vritti_name = VRITTI_NAMES[expected_vritti_idx]

        input_bhava_name = BHAVA_NAMES[input_dominant]
        output_bhava_name = BHAVA_NAMES[output_dominant]

        # Diagnose based on human rating and distances
        if human_rating >= 0.7:
            # Good rating
            if vritti_distance < 0.3 and bhava_aligned:
                return CognitiveDiagnosis(
                    type=DiagnosisType.VALIDATED,
                    message=f"✓ Chain validated: {input_bhava_name} → {actual_vritti_name} → {output_bhava_name}",
                    vritti_distance=vritti_distance,
                    bhava_distance=bhava_distance,
                    recommended_adjustment="None needed",
                    details={
                        'input_bhava': input_bhava_name,
                        'actual_vritti': actual_vritti_name,
                        'expected_vritti': expected_vritti_name,
                        'output_bhava': output_bhava_name,
                    }
                )
            else:
                # Human liked it but our model didn't predict it
                return CognitiveDiagnosis(
                    type=DiagnosisType.VRITTI_MISMATCH,
                    message=f"Human approved but Vritti unexpected: expected {expected_vritti_name}, got {actual_vritti_name}",
                    vritti_distance=vritti_distance,
                    bhava_distance=bhava_distance,
                    recommended_adjustment=f"Update BHAVA_TO_IDEAL_VRITTI[{input_dominant}] to favor {actual_vritti_name}",
                    details={
                        'input_bhava': input_bhava_name,
                        'actual_vritti': actual_vritti_name,
                        'expected_vritti': expected_vritti_name,
                        'output_bhava': output_bhava_name,
                        'recalibrate': True,
                    }
                )

        # Bad rating - diagnose what went wrong
        if actual_vritti[1] > 0.5 and expected_vritti[0] > 0.5:
            # Viparyaya high when Pramāṇa expected
            return CognitiveDiagnosis(
                type=DiagnosisType.OVER_HEDGED,
                message=f"Over-hedged: Viparyaya={actual_vritti[1]:.2f} when Pramāṇa expected",
                vritti_distance=vritti_distance,
                bhava_distance=bhava_distance,
                recommended_adjustment="Decrease viparyaya_activation_threshold",
                details={
                    'input_bhava': input_bhava_name,
                    'actual_vritti': actual_vritti_name,
                    'expected_vritti': expected_vritti_name,
                    'viparyaya_score': actual_vritti[1].item(),
                }
            )

        if actual_vritti[0] > 0.5 and expected_vritti[1] > 0.3:
            # Pramāṇa high when Viparyaya expected
            return CognitiveDiagnosis(
                type=DiagnosisType.OVER_CONFIDENT,
                message=f"Over-confident: Pramāṇa={actual_vritti[0]:.2f} when hedging expected",
                vritti_distance=vritti_distance,
                bhava_distance=bhava_distance,
                recommended_adjustment="Increase viparyaya_activation_threshold for SPECULATIVE inputs",
                details={
                    'input_bhava': input_bhava_name,
                    'actual_vritti': actual_vritti_name,
                    'expected_vritti': expected_vritti_name,
                    'pramana_score': actual_vritti[0].item(),
                }
            )

        if actual_vritti[3] > 0.5:
            # Smṛti too high
            return CognitiveDiagnosis(
                type=DiagnosisType.STUCK,
                message=f"Stuck in memory: Smṛti={actual_vritti[3]:.2f}, not progressing",
                vritti_distance=vritti_distance,
                bhava_distance=bhava_distance,
                recommended_adjustment="Decrease smrti_decay_rate to allow faster transitions",
                details={
                    'input_bhava': input_bhava_name,
                    'actual_vritti': actual_vritti_name,
                    'smrti_score': actual_vritti[3].item(),
                }
            )

        if actual_vritti[4] > 0.4 and expected_vritti[4] < 0.2:
            # Nidrā high inappropriately
            return CognitiveDiagnosis(
                type=DiagnosisType.DISENGAGED,
                message=f"Disengaged: Nidrā={actual_vritti[4]:.2f} when engagement expected",
                vritti_distance=vritti_distance,
                bhava_distance=bhava_distance,
                recommended_adjustment="Check input quality or increase confidence threshold",
                details={
                    'input_bhava': input_bhava_name,
                    'actual_vritti': actual_vritti_name,
                    'nidra_score': actual_vritti[4].item(),
                }
            )

        if not bhava_aligned:
            return CognitiveDiagnosis(
                type=DiagnosisType.TRANSITION_ERROR,
                message=f"Unhealthy transition: {input_bhava_name} → {output_bhava_name} (expected {[BHAVA_NAMES[t] for t in healthy_targets]})",
                vritti_distance=vritti_distance,
                bhava_distance=bhava_distance,
                recommended_adjustment="Review transition logic in generation",
                details={
                    'input_bhava': input_bhava_name,
                    'output_bhava': output_bhava_name,
                    'expected_outputs': [BHAVA_NAMES[t] for t in healthy_targets],
                }
            )

        # Generic mismatch
        return CognitiveDiagnosis(
            type=DiagnosisType.VRITTI_MISMATCH,
            message=f"Vritti mismatch: expected {expected_vritti_name}, got {actual_vritti_name}",
            vritti_distance=vritti_distance,
            bhava_distance=bhava_distance,
            recommended_adjustment="Review R[v,a] coupling matrix",
            details={
                'input_bhava': input_bhava_name,
                'actual_vritti': actual_vritti_name,
                'expected_vritti': expected_vritti_name,
                'output_bhava': output_bhava_name,
            }
        )

    def batch_diagnose(
        self,
        input_bhavas: torch.Tensor,
        actual_vrittis: torch.Tensor,
        output_bhavas: torch.Tensor,
        human_ratings: torch.Tensor,
    ) -> List[CognitiveDiagnosis]:
        """Diagnose a batch of samples."""
        B = input_bhavas.size(0)
        diagnoses = []

        for i in range(B):
            diag = self.diagnose(
                input_bhava=input_bhavas[i],
                actual_vritti=actual_vrittis[i],
                output_bhava=output_bhavas[i],
                human_rating=human_ratings[i].item(),
            )
            diagnoses.append(diag)

        return diagnoses

    def aggregate_diagnoses(
        self,
        diagnoses: List[CognitiveDiagnosis],
    ) -> Dict[str, Any]:
        """Aggregate diagnoses for batch-level insights."""
        type_counts = {}
        total_vritti_dist = 0.0
        total_bhava_dist = 0.0
        recommendations = []

        for diag in diagnoses:
            type_name = diag.type.value
            type_counts[type_name] = type_counts.get(type_name, 0) + 1
            total_vritti_dist += diag.vritti_distance
            total_bhava_dist += diag.bhava_distance
            if diag.recommended_adjustment != "None needed":
                recommendations.append(diag.recommended_adjustment)

        n = len(diagnoses)
        return {
            'type_distribution': type_counts,
            'avg_vritti_distance': total_vritti_dist / n if n > 0 else 0,
            'avg_bhava_distance': total_bhava_dist / n if n > 0 else 0,
            'validation_rate': type_counts.get('validated', 0) / n if n > 0 else 0,
            'top_recommendations': list(set(recommendations))[:5],
        }


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

def create_cognitive_loss(
    alpha: float = 0.4,
    beta: float = 0.4,
    gamma: float = 0.2,
) -> CognitiveLossFunction:
    """Create a configured cognitive loss function."""
    return CognitiveLossFunction(alpha=alpha, beta=beta, gamma=gamma)


def diagnose_generation(
    input_bhava: torch.Tensor,
    actual_vritti: torch.Tensor,
    output_bhava: torch.Tensor,
    human_rating: float,
) -> CognitiveDiagnosis:
    """Convenience function for single diagnosis."""
    validator = DHAValidator()
    return validator.diagnose(
        input_bhava=input_bhava,
        actual_vritti=actual_vritti,
        output_bhava=output_bhava,
        human_rating=human_rating,
    )


# =============================================================================
# EXAMPLE USAGE
# =============================================================================

if __name__ == "__main__":
    print("Cognitive Loss Function (Chitta Gradient) Demo")
    print("=" * 50)

    # Create loss function
    loss_fn = CognitiveLossFunction()

    # Simulate a batch
    B = 4
    vritti_actual = F.softmax(torch.randn(B, 5), dim=-1)
    bhava_input = F.softmax(torch.randn(B, 12), dim=-1)
    bhava_output = F.softmax(torch.randn(B, 12), dim=-1)
    human_rating = torch.tensor([0.9, 0.7, 0.3, 0.1])

    # Compute loss
    loss_dict = loss_fn(
        vritti_actual=vritti_actual,
        bhava_input=bhava_input,
        bhava_output=bhava_output,
        human_rating=human_rating,
    )

    print(f"\nLoss Components:")
    print(f"  Total Loss: {loss_dict['total_loss']:.4f}")
    print(f"  Vritti Loss: {loss_dict['vritti_loss']:.4f}")
    print(f"  Bhava Loss: {loss_dict['bhava_loss']:.4f}")
    print(f"  Transition Loss: {loss_dict['transition_loss']:.4f}")

    # Diagnose
    validator = DHAValidator()
    print(f"\nDiagnoses:")
    for i in range(B):
        diag = validator.diagnose(
            input_bhava=bhava_input[i],
            actual_vritti=vritti_actual[i],
            output_bhava=bhava_output[i],
            human_rating=human_rating[i].item(),
        )
        print(f"  Sample {i}: [{diag.type.value}] {diag.message}")
        print(f"    → {diag.recommended_adjustment}")
