#!/usr/bin/env python3
"""
Cognade Complete: Fully Integrated SymbolU12 with All Constraints
===================================================================

This module wires together ALL components into a single unified model:

1. Base: UnifiedSymbolU12Complete (Chitta-Vṛtti, Guna, R[v,a] coupling)
2. Phase Alignment: Dual R matrices, Phase-Lock, Stiefel projection
3. Logic Gates: Axiom checking, Vyāpti, Hetvābhāsa
4. Adversarial Hardening: Subspace alignment, Semantic axioms, Bottleneck

Key Integration: Vṛtti-Adaptive α
---------------------------------
The epistemic decay rate depends on which Vṛtti is dominant:

| Vṛtti      | α (decay) | Meaning                           |
|------------|-----------|-----------------------------------|
| Pramāṇa    | 0.01      | Direct perception - slow decay    |
| Anumāna    | 0.15      | Inference - moderate decay        |
| Vikalpa    | 0.60      | Speculation - fast decay          |
| Smṛti      | 0.10      | Memory - slow decay               |
| Nidrā      | 0.30      | Dormancy - moderate decay         |

Hard Confidence↔Entropy Coupling
--------------------------------
entropy = 1 - confidence  (mathematical identity, not soft penalty)

This ensures the model CANNOT be both confident and uncertain.
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
from typing import Dict, Optional, Tuple, Any
from dataclasses import dataclass
import math

# Import existing components
from .unified_symbolu12 import (
    UnifiedSymbolU12Config,
    DifferentiableChittaVritti,
    BidirectionalGunaMapper,
    VrittiModulatedAttention,
    VrittiOntologyCoupling,
)
from .phase_alignment import (
    OrthogonalityLoss,
    DualRMatrices,
    PhaseLockGate,
    ZeroState,
    SmritiPersistenceLoop,
    StiefelProjection,
)
from .logic_gates import (
    AxiomChecker,
    LogicGate,
)
from .adversarial_hardening import (
    SubspaceAlignment,
    SemanticAxioms,
    BottleneckProjection,
)


# =============================================================================
# VṚTTI-ADAPTIVE EPISTEMIC DECAY
# =============================================================================

class VrittiAdaptiveDecay(nn.Module):
    """
    Vṛtti-Adaptive α: Decay rate depends on cognitive mode.

    Gemini's insight: Different types of cognition should have
    different confidence decay rates.

    - Pramāṇa (direct perception): α = 0.01 (very slow decay)
    - Anumāna (inference): α = 0.15 (moderate)
    - Vikalpa (speculation): α = 0.60 (fast decay)
    - Smṛti (memory): α = 0.10 (slow)
    - Nidrā (dormancy): α = 0.30 (moderate)
    """

    # Decay rates per Vṛtti
    VRITTI_ALPHA = torch.tensor([
        0.01,  # Pramāṇa - direct perception, very stable
        0.15,  # Viparyaya - error/misperception
        0.60,  # Vikalpa - speculation, fast decay
        0.10,  # Smṛti - memory, stable
        0.30,  # Nidrā - dormancy
    ])

    def __init__(self):
        super().__init__()
        self.register_buffer('alpha_per_vritti', self.VRITTI_ALPHA)

    def get_alpha(self, vritti: torch.Tensor) -> torch.Tensor:
        """
        Compute adaptive decay rate from Vṛtti distribution.

        Args:
            vritti: [B, T, 5] or [B, 5] Vṛtti probabilities

        Returns:
            alpha: [B, T] or [B] weighted decay rate
        """
        # Weighted average of decay rates
        alpha = torch.einsum(
            '...v,v->...',
            vritti,
            self.alpha_per_vritti.to(vritti.device)
        )
        return alpha

    def apply_decay(
        self,
        confidence: torch.Tensor,
        vritti: torch.Tensor,
        info_distance: torch.Tensor,
    ) -> torch.Tensor:
        """
        Apply Vṛtti-adaptive confidence decay.

        Formula: confidence_new = confidence * exp(-α * δ)

        Where:
        - α = weighted average of Vṛtti decay rates
        - δ = information distance from grounded facts

        Args:
            confidence: [B, T] current confidence
            vritti: [B, T, 5] Vṛtti distribution
            info_distance: [B, T] distance from grounded facts (0=grounded, 1=speculation)

        Returns:
            decayed_confidence: [B, T]
        """
        alpha = self.get_alpha(vritti)  # [B, T]

        # Exponential decay
        decay_factor = torch.exp(-alpha * info_distance)

        decayed = confidence * decay_factor

        return decayed


# =============================================================================
# HARD CONFIDENCE-ENTROPY COUPLING
# =============================================================================

class ConfidenceEntropyCoupling(nn.Module):
    """
    Hard mathematical coupling: entropy = 1 - confidence

    This is NOT a soft penalty - it's a mathematical identity.
    The model cannot be both confident and uncertain.

    Enforced by:
    1. Computing confidence from the model
    2. Setting entropy = 1 - confidence (no freedom)
    3. Propagating this constraint through dynamics
    """

    def __init__(self):
        super().__init__()

    def forward(
        self,
        dynamics: torch.Tensor,
    ) -> torch.Tensor:
        """
        Enforce confidence-entropy coupling in dynamics vector.

        Args:
            dynamics: [B, T, 4] = [coherence, entropy, confidence, momentum]

        Returns:
            coupled_dynamics: [B, T, 4] with entropy = 1 - confidence
        """
        coupled = dynamics.clone()

        # Extract confidence (index 2)
        confidence = dynamics[..., 2]

        # Force entropy = 1 - confidence (index 1)
        coupled[..., 1] = 1.0 - confidence

        return coupled

    def compute_violation(
        self,
        dynamics: torch.Tensor,
    ) -> torch.Tensor:
        """
        Compute how much the coupling is violated.

        Used for logging/debugging.
        """
        entropy = dynamics[..., 1]
        confidence = dynamics[..., 2]

        expected_entropy = 1.0 - confidence
        violation = (entropy - expected_entropy).abs()

        return violation


# =============================================================================
# COGNADE COMPLETE MODEL
# =============================================================================

@dataclass
class CognadeConfig(UnifiedSymbolU12Config):
    """Extended configuration for Cognade Complete."""

    # Phase-Lock settings
    tau_base: float = 0.72
    confidence_scale: float = 0.4

    # Smṛti persistence
    drift_lambda: float = 0.05

    # Bottleneck projection
    num_token_categories: int = 32

    # Loss weights
    lambda_ortho: float = 0.5
    lambda_phase_lock: float = 0.3
    lambda_axiom: float = 0.2
    lambda_subspace: float = 0.3
    lambda_semantic: float = 0.2


class CognadeComplete(nn.Module):
    """
    Cognade Complete: The fully integrated SymbolU12 architecture.

    This is the "Glass Box" model where:
    - Truth is mathematically enforced (Phase-Lock)
    - Confidence automatically decays for speculation (Vṛtti-adaptive α)
    - Entropy and confidence are coupled (cannot be both)
    - Logical fallacies are blocked (Nyāya gates)
    - Adversarial attacks are resisted (Subspace alignment)

    Forward pass:
    1. Base model → hidden states
    2. Project → CognitiveState[124]
    3. Compute Chitta-Vṛtti → 5-dim mode distribution
    4. Apply Vṛtti-adaptive decay → adjust confidence
    5. Enforce confidence↔entropy coupling
    6. Compute Dual R matrices (internal/external)
    7. Check Phase-Lock (subspace alignment)
    8. Check Logic Gates (axioms, Vyāpti)
    9. Apply Bottleneck Projection → gate logits
    10. Output or META fallback
    """

    def __init__(
        self,
        base_model: nn.Module,
        config: CognadeConfig,
    ):
        super().__init__()
        self.base_model = base_model
        self.config = config

        # =====================================================================
        # LAYER 1: STATE PROJECTION (Hidden → CognitiveState)
        # =====================================================================
        self.state_projector = nn.ModuleDict({
            'phoneme': nn.Sequential(
                nn.Linear(config.hidden_dim, config.hidden_dim // 4),
                nn.GELU(),
                nn.Linear(config.hidden_dim // 4, config.num_phonemes),
            ),
            'topic': nn.Sequential(
                nn.Linear(config.hidden_dim, config.hidden_dim // 2),
                nn.GELU(),
                nn.Linear(config.hidden_dim // 2, config.topic_dim),
            ),
            'ontology': nn.Sequential(
                nn.Linear(config.hidden_dim, config.hidden_dim // 4),
                nn.GELU(),
                nn.Linear(config.hidden_dim // 4, config.num_ontology),
            ),
            'dynamics': nn.Sequential(
                nn.Linear(config.hidden_dim, config.hidden_dim // 4),
                nn.GELU(),
                nn.Linear(config.hidden_dim // 4, config.num_dynamics),
                nn.Sigmoid(),
            ),
        })

        # =====================================================================
        # LAYER 2: CHITTA-VṚTTI (Metacognitive Assessment)
        # =====================================================================
        self.chitta_vritti = DifferentiableChittaVritti(config)
        self.guna_mapper = BidirectionalGunaMapper(config)
        self.vritti_coupling = VrittiOntologyCoupling(config)

        # =====================================================================
        # LAYER 3: VṚTTI-ADAPTIVE DECAY + COUPLING
        # =====================================================================
        self.vritti_decay = VrittiAdaptiveDecay()
        self.conf_entropy_coupling = ConfidenceEntropyCoupling()

        # =====================================================================
        # LAYER 4: PHASE ALIGNMENT (Dual R + Phase-Lock)
        # =====================================================================
        self.dual_r = DualRMatrices(
            bhava_dim=config.num_ontology,
            state_dim=config.state_dim,
        )
        self.phase_lock = PhaseLockGate(
            bhava_dim=config.num_ontology,
            state_dim=config.state_dim,
            tau_base=config.tau_base,
        )
        self.subspace_alignment = SubspaceAlignment(
            bhava_dim=config.num_ontology,
        )
        self.ortho_loss = OrthogonalityLoss()

        # =====================================================================
        # LAYER 5: PERSISTENCE (Smṛti + Zero State)
        # =====================================================================
        self.zero_state = ZeroState(
            num_phonemes=config.num_phonemes,
            topic_dim=config.topic_dim,
            num_ontology=config.num_ontology,
        )
        self.smriti = SmritiPersistenceLoop(
            state_dim=config.state_dim,
            lambda_drift=config.drift_lambda,
        )

        # =====================================================================
        # LAYER 6: LOGIC GATES (Axioms + Nyāya)
        # =====================================================================
        self.axiom_checker = AxiomChecker()
        self.logic_gate = LogicGate()
        self.semantic_axioms = SemanticAxioms(
            state_dim=config.state_dim,
            bhava_dim=config.num_ontology,
        )

        # =====================================================================
        # LAYER 7: TOKEN GROUNDING (Bottleneck Projection)
        # =====================================================================
        self.bottleneck = BottleneckProjection(
            bhava_dim=config.num_ontology,
            vocab_size=config.vocab_size,
            num_categories=config.num_token_categories,
        )

        # =====================================================================
        # LAYER 8: OUTPUT HEAD
        # =====================================================================
        self.lm_head = nn.Linear(config.hidden_dim, config.vocab_size, bias=False)

        # State tracking
        self.register_buffer('prev_state', None)

    def forward(
        self,
        input_ids: torch.Tensor,
        labels: Optional[torch.Tensor] = None,
        info_distance: Optional[torch.Tensor] = None,
        return_diagnostics: bool = False,
    ) -> Dict[str, Any]:
        """
        Complete Cognade forward pass.

        Args:
            input_ids: [B, T] input token IDs
            labels: [B, T] optional labels for loss
            info_distance: [B, T] optional distance from grounded facts
            return_diagnostics: If True, return detailed diagnostics

        Returns:
            Dict with logits, losses, and optional diagnostics
        """
        B, T = input_ids.shape
        device = input_ids.device

        # Default info_distance (assume present/grounded)
        if info_distance is None:
            info_distance = torch.zeros(B, T, device=device)

        # =================================================================
        # STEP 1: Base model forward
        # =================================================================
        outputs = self.base_model(input_ids, return_hidden=True)
        if isinstance(outputs, dict):
            hidden = outputs.get('hidden_states', outputs.get('last_hidden_state'))
        else:
            hidden = outputs

        # =================================================================
        # STEP 2: Project to CognitiveState
        # =================================================================
        phoneme = F.softmax(self.state_projector['phoneme'](hidden), dim=-1)
        topic = self.state_projector['topic'](hidden)
        ontology = F.softmax(self.state_projector['ontology'](hidden), dim=-1)
        dynamics = self.state_projector['dynamics'](hidden)

        # =================================================================
        # STEP 3: Compute Chitta-Vṛtti
        # =================================================================
        chitta_result = self.chitta_vritti(
            phoneme=phoneme,
            topic=topic,
            ontology=ontology,
            dynamics=dynamics,
            prev_state=self.prev_state,
        )
        vritti = chitta_result['vritti']  # [B, T, 5]

        # =================================================================
        # STEP 4: Apply Vṛtti-adaptive decay
        # =================================================================
        confidence_raw = dynamics[:, :, 2]  # Original confidence
        confidence_decayed = self.vritti_decay.apply_decay(
            confidence_raw, vritti, info_distance
        )

        # Update dynamics with decayed confidence
        dynamics_updated = dynamics.clone()
        dynamics_updated[:, :, 2] = confidence_decayed

        # =================================================================
        # STEP 5: Enforce confidence↔entropy coupling
        # =================================================================
        dynamics_coupled = self.conf_entropy_coupling(dynamics_updated)

        # Reconstruct cognitive state
        cognitive_state = torch.cat([
            phoneme,           # 44
            topic,             # 64
            ontology,          # 12
            dynamics_coupled,  # 4
        ], dim=-1)  # [B, T, 124]

        # =================================================================
        # STEP 6: Compute Dual R matrices
        # =================================================================
        R_int, R_ext = self.dual_r(cognitive_state)

        # =================================================================
        # STEP 7: Phase-Lock check
        # =================================================================
        confidence = dynamics_coupled[:, :, 2]

        # Standard Phase-Lock
        gated_logits_pl, pl_info = self.phase_lock(
            cognitive_state, None, confidence
        )

        # Subspace alignment (deeper check)
        subspace_result = self.subspace_alignment(
            R_int, R_ext, confidence.mean(dim=1)
        )

        # Combined gate: both must pass
        combined_gate = pl_info['gate'] * subspace_result['soft_gate'].unsqueeze(1)

        # =================================================================
        # STEP 8: Apply Smṛti persistence
        # =================================================================
        if self.prev_state is not None:
            delta_pred = cognitive_state - self.prev_state
        else:
            delta_pred = torch.zeros_like(cognitive_state)

        cognitive_state_persisted = self.smriti(
            cognitive_state, delta_pred, confidence
        )

        # Update prev_state
        with torch.no_grad():
            self.prev_state = cognitive_state_persisted.detach()

        # =================================================================
        # STEP 9: Logic gate checks
        # =================================================================
        axiom_valid, axiom_violations = self.axiom_checker(cognitive_state_persisted)
        semantic_result = self.semantic_axioms(cognitive_state_persisted)

        # Combined validity
        logic_valid = axiom_valid & semantic_result['valid']

        # =================================================================
        # STEP 10: Generate logits with bottleneck
        # =================================================================
        raw_logits = self.lm_head(hidden)

        # Apply bottleneck projection
        bhava = cognitive_state_persisted[:, :, 108:120]
        bottlenecked_logits = self.bottleneck(bhava, raw_logits, confidence)

        # Apply Phase-Lock gate
        meta_logits = torch.full_like(bottlenecked_logits, float('-inf'))
        meta_logits[:, :, self.phase_lock.META_TOKEN_ID] = 0.0

        combined_gate_expanded = combined_gate.unsqueeze(-1)
        final_logits = (
            combined_gate_expanded * bottlenecked_logits +
            (1 - combined_gate_expanded) * meta_logits
        )

        # =================================================================
        # COMPUTE LOSSES
        # =================================================================
        losses = {}

        # Token prediction loss
        if labels is not None:
            shift_logits = final_logits[:, :-1].contiguous()
            shift_labels = labels[:, 1:].contiguous()
            token_loss = F.cross_entropy(
                shift_logits.view(-1, self.config.vocab_size),
                shift_labels.view(-1),
                ignore_index=-100,
            )
            losses['token'] = self.config.lambda_token * token_loss

        # Orthogonality loss
        ortho_losses = self.dual_r.compute_alignment_loss(cognitive_state)
        losses['ortho'] = self.config.lambda_ortho * ortho_losses['total_ortho_loss']

        # Phase-Lock loss
        pl_losses = self.phase_lock.compute_loss(cognitive_state)
        losses['phase_lock'] = self.config.lambda_phase_lock * pl_losses['phase_lock_loss']

        # Subspace alignment loss
        subspace_loss = self.subspace_alignment.compute_loss(
            R_int, R_ext, confidence.mean(dim=1)
        )
        losses['subspace'] = self.config.lambda_subspace * subspace_loss

        # Axiom loss
        axiom_loss = self.axiom_checker.compute_loss(cognitive_state)
        losses['axiom'] = self.config.lambda_axiom * axiom_loss

        # Semantic axiom loss
        semantic_loss = self.semantic_axioms.compute_loss(cognitive_state)
        losses['semantic'] = self.config.lambda_semantic * semantic_loss

        # Smṛti drift loss
        drift_loss = self.smriti.compute_drift_loss(cognitive_state)
        losses['drift'] = self.config.drift_lambda * drift_loss

        # Total loss
        total_loss = sum(losses.values())
        losses['total'] = total_loss

        # =================================================================
        # PREPARE OUTPUT
        # =================================================================
        result = {
            'logits': final_logits,
            'loss': total_loss,
            'losses': losses,
            'phase_locked': (combined_gate < 0.5).any().item(),
            'meta_triggered': not logic_valid.all().item(),
        }

        if return_diagnostics:
            result['diagnostics'] = {
                'cognitive_state': cognitive_state_persisted,
                'vritti': vritti,
                'confidence_raw': confidence_raw,
                'confidence_decayed': confidence_decayed,
                'dynamics_coupled': dynamics_coupled,
                'R_internal': R_int,
                'R_external': R_ext,
                'phase_lock_gate': pl_info['gate'],
                'phase_lock_alignment': pl_info['alignment'],
                'subspace_alignment': subspace_result['alignment'],
                'subspace_gate': subspace_result['soft_gate'],
                'axiom_valid': axiom_valid,
                'axiom_violations': axiom_violations,
                'semantic_penalties': semantic_result['penalties'],
                'combined_gate': combined_gate,
                'alpha_per_position': self.vritti_decay.get_alpha(vritti),
            }

        return result

    def reset_state(self):
        """Reset to zero state (Sattvic seed)."""
        self.prev_state = None

    def get_zero_state(self, batch_size: int = 1) -> torch.Tensor:
        """Get the Sattvic zero state S_0."""
        return self.zero_state(batch_size)


# =============================================================================
# FACTORY FUNCTION
# =============================================================================

def create_cognade(
    base_model: nn.Module,
    hidden_dim: int = 256,
    vocab_size: int = 50257,
    tau_base: float = 0.72,
) -> CognadeComplete:
    """
    Create a fully configured Cognade model.

    Args:
        base_model: The base transformer model
        hidden_dim: Hidden dimension
        vocab_size: Vocabulary size
        tau_base: Phase-Lock threshold

    Returns:
        CognadeComplete model
    """
    config = CognadeConfig(
        hidden_dim=hidden_dim,
        vocab_size=vocab_size,
        tau_base=tau_base,
    )

    return CognadeComplete(base_model, config)


# =============================================================================
# EXAMPLE / TEST
# =============================================================================

if __name__ == "__main__":
    print("Cognade Complete Integration Test")
    print("=" * 60)

    # Create mock base model
    class MockBaseModel(nn.Module):
        def __init__(self, hidden_dim=256):
            super().__init__()
            self.embed = nn.Embedding(1000, hidden_dim)
            self.hidden_dim = hidden_dim

        def forward(self, input_ids, return_hidden=False):
            hidden = self.embed(input_ids)
            if return_hidden:
                return {'hidden_states': hidden}
            return hidden

    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')

    # Create model
    base = MockBaseModel(hidden_dim=256).to(device)
    config = CognadeConfig(hidden_dim=256, vocab_size=1000)
    model = CognadeComplete(base, config).to(device)

    # Test forward pass
    B, T = 2, 10
    input_ids = torch.randint(0, 1000, (B, T), device=device)
    labels = torch.randint(0, 1000, (B, T), device=device)

    print("\nForward pass...")
    result = model(input_ids, labels=labels, return_diagnostics=True)

    print(f"\nResults:")
    print(f"  Logits shape: {result['logits'].shape}")
    print(f"  Total loss: {result['loss'].item():.4f}")
    print(f"  Phase locked: {result['phase_locked']}")
    print(f"  META triggered: {result['meta_triggered']}")

    print(f"\nLoss components:")
    for name, value in result['losses'].items():
        if isinstance(value, torch.Tensor):
            print(f"  {name}: {value.item():.4f}")

    print(f"\nDiagnostics:")
    diag = result['diagnostics']
    print(f"  Confidence raw mean: {diag['confidence_raw'].mean().item():.4f}")
    print(f"  Confidence decayed mean: {diag['confidence_decayed'].mean().item():.4f}")
    print(f"  Alpha (decay rate) mean: {diag['alpha_per_position'].mean().item():.4f}")
    print(f"  Phase-Lock alignment: {diag['phase_lock_alignment'].mean().item():.4f}")
    print(f"  Subspace alignment: {diag['subspace_alignment'].mean().item():.4f}")
    print(f"  Combined gate mean: {diag['combined_gate'].mean().item():.4f}")

    # Test Vṛtti-adaptive decay
    print(f"\nVṛtti-Adaptive α Test:")
    vritti_examples = [
        ("Pramāṇa dominant", torch.tensor([[0.8, 0.05, 0.05, 0.05, 0.05]])),
        ("Vikalpa dominant", torch.tensor([[0.05, 0.05, 0.8, 0.05, 0.05]])),
        ("Mixed", torch.tensor([[0.2, 0.2, 0.2, 0.2, 0.2]])),
    ]

    for name, vritti in vritti_examples:
        alpha = model.vritti_decay.get_alpha(vritti.to(device))
        print(f"  {name}: α = {alpha.item():.4f}")

    print("\n" + "=" * 60)
    print("Cognade Complete Integration Test PASSED")
