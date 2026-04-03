"""
Sovereign Reasoning Kernel (SRK) - State-Persistent AGI Architecture
=====================================================================

Version: 9.9.0
Reference: docs/architecture/SOVEREIGN_REASONING_KERNEL_DESIGN.md

The SRK implements Recursive Ontological Intelligence (ROI) by managing
the 32D Sovereign State across transformer layers. It transforms a
forward-only predictor into a recursive reasoner.

Components:
- SRKConfig: Configuration dataclass
- SovereignReasoningKernel: Main kernel with layer interventions
- SovereignEmbedding: Layer 0 karma injection
- IsomorphicMappingRouter (IMR): Cross-domain bridge detection
- OntologicalBridge: Layer 4 DNA grounding
- WitnessArbitrator: Layer 9 domain arbitration
- SynthesisGate: Layer 11 final edit
- VrittiGate: Epistemological witness for self-correction
- KoshaShiftController: Depth-scaling through 5 consciousness layers
- KoshaPhaseCorrector: Inference-time direct phase rotation (v2.4.0)

The SRK ensures that when the model learns mathematical rigor (O7 Reasoning)
in one domain, that same rigor is structurally preserved when switching
to another domain via Isomorphic Mapping.

Training vs Inference:
- Training: Uses KoshaGyroscopicLoss (indirect, gradient-based)
- Inference: Uses KoshaPhaseCorrector (direct, guardrail-based)
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any

import torch
import torch.nn as nn
import torch.nn.functional as F
import math


# =============================================================================
# 32D SOVEREIGN STATE CONSTANTS (from phase_transformer.py)
# =============================================================================

SOVEREIGN_STATE_DIM = 32

# Bhava indices [0:12] - 12 Ontological Aspects
BHAVA_NAMES = [
    'POT', 'IDN', 'EXE', 'STR', 'COG', 'AGY',
    'RSN', 'PRP', 'WIT', 'UNI', 'INT', 'ABS'
]
BHAVA_SLICE = slice(0, 12)

# Sheath indices [12:17] - 5 Depth Layers
KOSHA_NAMES = ['MATERIAL', 'VITAL', 'MENTAL', 'INTELLECTUAL', 'BLISSFUL']
KOSHA_SLICE = slice(12, 17)

# State indices [17:22] - 5 Reliability States
VRITTI_NAMES = ['FACT', 'MISCONCEPTION', 'IMAGINATION', 'VOID', 'MEMORY']
VRITTI_SLICE = slice(17, 22)

# Qualia indices [22:28] - 6 System Dynamics
GUNA_NAMES = ['LUCIDITY', 'ACTIVITY', 'STABILITY', 'VELOCITY', 'ACCEL', 'STABLE']
GUNA_SLICE = slice(22, 28)

# Reserved indices [28:32] - Toroidal Feedback
RESERVED_SLICE = slice(28, 32)


# =============================================================================
# SRK CONFIGURATION
# =============================================================================

@dataclass
class SRKConfig:
    """
    Configuration for Sovereign Reasoning Kernel.

    Encapsulates all SRK-related hyperparameters to prevent CLI pollution.
    Can be serialized with checkpoints for reproducibility.
    """

    # Core dimensions
    state_dim: int = SOVEREIGN_STATE_DIM
    hidden_dim: int = 768
    num_heads: int = 12

    # Layer intervention points
    dna_bridge_layer: int = 4      # Ontological grounding
    csr_alignment_layer: int = 7   # Phoneme alignment / Phase extraction
    witness_layer: int = 9         # Domain arbitration
    synthesis_layer: int = 11      # Final edit

    # Component toggles
    enable_dna_bridge: bool = True
    enable_witness: bool = True
    enable_synthesis: bool = True
    enable_imr: bool = True
    enable_vritti_gate: bool = True
    enable_kosha_shift: bool = True

    # Isomorphic Mapping Router (IMR)
    isomorphism_threshold: float = 0.75

    # Karma / Toroidal Loop
    karma_decay: float = 0.9
    toroidal_feedback: bool = True

    # DNA Bridge (Layer 4)
    lambda_bridge: float = 0.1  # Strength of ontological correction

    # Vritti Gate thresholds
    vritti_fact_min: float = 0.3       # Minimum valid cognition for factual
    vritti_error_max: float = 0.4      # Maximum error before rejection
    vritti_imagination_max: float = 0.6  # Maximum imagination for non-creative
    vritti_void_max: float = 0.2       # Maximum dormancy
    vritti_memory_max: float = 0.8     # Allow high memory in recall tasks

    # Kosha Shift
    kosha_target: str = 'INTELLECTUAL'  # Target Kosha for reasoning
    kosha_dampen_material: float = 0.5  # Dampen material during reasoning
    kosha_boost_intellectual: float = 0.4  # Boost intellectual

    # Synthesis Gate
    tamas_threshold: float = 0.9  # Threshold for detecting entropy collapse

    # Mauna Protocol (Inference Safety) - Stage 4
    enable_mauna: bool = False
    mauna_error_threshold: float = 0.9
    mauna_activity_threshold: float = 0.9
    mauna_confidence_threshold: float = 0.6   # Minimum confidence for output
    mauna_consistency_threshold: float = 0.5  # Minimum backward score consistency

    # OPB Dimension Locking (Ontological Persistence Buffer)
    enable_opb_locking: bool = True
    opb_lock_threshold: float = 0.7    # Activation threshold to lock dimension
    opb_unlock_threshold: float = 0.3  # Activation threshold to unlock dimension
    opb_lock_decay: float = 0.95       # Per-step decay for locked dimensions (slow release)
    opb_blend_factor: float = 0.6      # How much locked state influences new state

    # Kosha Phase Corrector (Inference-Time Guardrail) - v2.4.0
    enable_phase_corrector: bool = True       # Enable direct phase correction during inference
    phase_corrector_threshold: float = 0.75   # Kosha activation threshold for correction
    phase_corrector_strength: float = 0.3     # Correction strength (0-1)
    phase_corrector_max_step: float = 0.2     # Max correction per step

    # Training parameters
    warmup_steps: int = 5000

    def __post_init__(self):
        """Validate configuration."""
        # V11.0.0: SRK operates on the full 32D Sovereign State (control plane).
        # Phase rotation is handled separately by IntentPhaseProjector (12D Bhava-only).
        # SRK needs all 32D for: DNA Bridge, Witness, Synthesis, IMR, Karma.
        assert self.state_dim == 32, "SRK requires full 32D Sovereign State (control plane)"
        assert 0 < self.isomorphism_threshold <= 1.0
        assert 0 < self.karma_decay <= 1.0


# =============================================================================
# IMR LOGIC TEMPLATES (Fixed Ontological Priors)
# =============================================================================

def create_logic_templates(device: torch.device = None) -> Dict[str, torch.Tensor]:
    """
    Create the 5 Sanskrit Logic Templates as fixed priors.

    These are registered as buffers (non-learnable) to ensure the model
    aligns TO these universals, not drifts them to match initialization.

    Template Design:
    - DEDUCTION: O7 (Reasoning) + O4 (Structure) + O12 (Absolute)
    - INDUCTION: O7 (Reasoning) + O5 (Cognition) + O9 (Witnessing)
    - ABDUCTION: O7 (Reasoning) + O8 (Purpose) + O6 (Agency)
    - ANALOGY: O4 (Structure) + O10 (Unifying) + O11 (Integration)
    - SYNTHESIS: O11 (Integration) + O12 (Absolute) + O8 (Purpose)
    """
    templates = {}

    # DEDUCTION: Rigorous logical inference (Math, Proof)
    # High: O7 (RSN), O4 (STR), O12 (ABS)
    deduction = torch.zeros(12)
    deduction[6] = 1.0   # O7_RSN: Reasoning
    deduction[3] = 0.8   # O4_STR: Structure
    deduction[11] = 0.9  # O12_ABS: Absolute
    templates['DEDUCTION'] = deduction

    # INDUCTION: Pattern recognition from examples
    # High: O7 (RSN), O5 (COG), O9 (WIT)
    induction = torch.zeros(12)
    induction[6] = 0.9   # O7_RSN: Reasoning
    induction[4] = 0.8   # O5_COG: Cognition
    induction[8] = 0.7   # O9_WIT: Witnessing
    templates['INDUCTION'] = induction

    # ABDUCTION: Best explanation inference
    # High: O7 (RSN), O8 (PRP), O6 (AGY)
    abduction = torch.zeros(12)
    abduction[6] = 0.8   # O7_RSN: Reasoning
    abduction[7] = 0.9   # O8_PRP: Purpose
    abduction[5] = 0.7   # O6_AGY: Agency
    templates['ABDUCTION'] = abduction

    # ANALOGY: Structural similarity mapping
    # High: O4 (STR), O10 (UNI), O11 (INT)
    analogy = torch.zeros(12)
    analogy[3] = 0.9    # O4_STR: Structure
    analogy[9] = 0.8    # O10_UNI: Unifying
    analogy[10] = 0.7   # O11_INT: Integration
    templates['ANALOGY'] = analogy

    # SYNTHESIS: Integration of multiple perspectives
    # High: O11 (INT), O12 (ABS), O8 (PRP)
    synthesis = torch.zeros(12)
    synthesis[10] = 0.9  # O11_INT: Integration
    synthesis[11] = 0.8  # O12_ABS: Absolute
    synthesis[7] = 0.7   # O8_PRP: Purpose
    templates['SYNTHESIS'] = synthesis

    if device is not None:
        templates = {k: v.to(device) for k, v in templates.items()}

    return templates


# =============================================================================
# ISOMORPHIC MAPPING ROUTER (IMR)
# =============================================================================

class IsomorphicMappingRouter(nn.Module):
    """
    Isomorphic Mapping Router - Cross-Domain Bridge Detection.

    Identifies when Bhavas of different domains overlap, enabling
    cross-domain reasoning transfer. For example, when mathematical
    rigor (O7) learned in Math domain can be applied to Finance.

    The 5 Logic Templates are fixed priors (register_buffer).
    The bias_projector learns how strongly to apply each template.
    """

    def __init__(
        self,
        state_dim: int = 32,
        hidden_dim: int = 768,
        threshold: float = 0.75,
    ):
        super().__init__()
        self.state_dim = state_dim
        self.hidden_dim = hidden_dim
        self.threshold = threshold

        # Register fixed logic templates (non-learnable)
        templates = create_logic_templates()
        for name, template in templates.items():
            self.register_buffer(f'template_{name.lower()}', template)

        self.template_names = list(templates.keys())

        # Learnable: How to project template bias into hidden space
        self.bias_projector = nn.Linear(12, hidden_dim)

        # Domain memory (runtime, not persisted in checkpoint)
        self.domain_memory: List[Tuple[str, torch.Tensor]] = []

    def detect_isomorphism(
        self,
        current_state: torch.Tensor,
    ) -> Tuple[Optional[torch.Tensor], Optional[str]]:
        """
        Find structural overlaps between current state and logic templates.

        Args:
            current_state: [B, 32] current Sovereign State

        Returns:
            isomorphic_bias: [hidden_dim] bias to inject into attention (or None)
            template_name: Name of matched template (or None)
        """
        # Extract Bhava activations [B, 12]
        current_bhavas = current_state[:, BHAVA_SLICE]

        # Average across batch for template matching
        avg_bhavas = current_bhavas.mean(dim=0)  # [12]

        best_match = None
        best_similarity = 0.0
        best_name = None

        # Check each logic template
        for name in self.template_names:
            template = getattr(self, f'template_{name.lower()}')

            # Cosine similarity
            similarity = F.cosine_similarity(
                avg_bhavas.unsqueeze(0),
                template.unsqueeze(0),
                dim=-1
            ).item()

            if similarity > self.threshold and similarity > best_similarity:
                best_similarity = similarity
                best_match = template
                best_name = name

        if best_match is not None:
            # Project template to hidden space for attention bias
            isomorphic_bias = self.bias_projector(best_match)
            return isomorphic_bias, best_name

        return None, None

    def add_domain_memory(self, domain_name: str, bhava_pattern: torch.Tensor):
        """Add a domain-state pair to runtime memory."""
        self.domain_memory.append((domain_name, bhava_pattern.detach().clone()))

    def clear_domain_memory(self):
        """Clear runtime domain memory."""
        self.domain_memory.clear()


# =============================================================================
# ONTOLOGICAL BRIDGE (Layer 4 - DNA Grounding)
# =============================================================================

class OntologicalBridge(nn.Module):
    """
    Layer 4: The Ontological DNA Bridge.

    Performs first self-correction by forcing alignment with the 32D
    Sovereign State. If Layers 0-3 have misinterpreted the prompt,
    Layer 4 corrects toward ontological truth.

    Projects 512D "Physical" thought to 12D "Ontological" Aspect,
    computes error against target Bhavas, and re-injects correction.
    """

    def __init__(
        self,
        hidden_dim: int = 768,
        state_dim: int = 12,  # Bhava dimension
        lambda_bridge: float = 0.1,
    ):
        super().__init__()
        self.hidden_dim = hidden_dim
        self.state_dim = state_dim
        self.lambda_bridge = lambda_bridge

        # Project hidden → 12D ontological aspect
        self.projector = nn.Linear(hidden_dim, state_dim)

        # Re-inject correction → hidden
        self.injector = nn.Linear(state_dim, hidden_dim)

    def forward(
        self,
        hidden_states: torch.Tensor,
        sovereign_state: torch.Tensor,
    ) -> torch.Tensor:
        """
        Apply DNA grounding correction.

        Args:
            hidden_states: [B, N, D] from transformer
            sovereign_state: [B, 32] current Sovereign State

        Returns:
            corrected_hidden: [B, N, D] with ontological correction applied
        """
        # 1. Observe: Current ontological aspect of the thought
        observed_bhava = self.projector(hidden_states)  # [B, N, 12]

        # 2. Target: Retrieve 12 Bhavas from 32D State
        target_bhava = sovereign_state[:, BHAVA_SLICE]  # [B, 12]
        target_bhava = target_bhava.unsqueeze(1)  # [B, 1, 12]

        # 3. Calculate ontological tension (DNA pressure)
        correction = self.injector(target_bhava - observed_bhava)  # [B, N, D]

        # 4. Apply correction
        return hidden_states + (self.lambda_bridge * correction)


# =============================================================================
# KOSHA SHIFT CONTROLLER (Depth Scaling)
# =============================================================================

class KoshaShiftController(nn.Module):
    """
    Kosha Steering at Layer 9 (Witnessing).

    Forces state toward intellectual Kosha during reasoning, ensuring
    the model spends adequate "internal compute" at the pattern level
    before outputting tokens.

    Implements the 5 Koshas (Sheaths):
    - MATERIAL (0): Physicality/Syntax
    - VITAL (1): Flow/Energy
    - MENTAL (2): Semantics/Meaning
    - INTELLECTUAL (3): Pattern/Wisdom
    - BLISSFUL (4): Unity/Integration
    """

    KOSHA_INDICES = {
        'MATERIAL': 12,
        'VITAL': 13,
        'MENTAL': 14,
        'INTELLECTUAL': 15,
        'BLISSFUL': 16,
    }

    def __init__(
        self,
        state_dim: int = 32,
        target_kosha: str = 'INTELLECTUAL',
        dampen_material: float = 0.5,
        boost_target: float = 0.4,
    ):
        super().__init__()
        self.state_dim = state_dim
        self.target_kosha = target_kosha
        self.dampen_material = dampen_material
        self.boost_target = boost_target

        self.target_idx = self.KOSHA_INDICES[target_kosha]
        self.material_idx = self.KOSHA_INDICES['MATERIAL']

    def escalate_to_intellect(self, state: torch.Tensor) -> torch.Tensor:
        """
        Shift state toward intellectual Kosha for pattern-level reasoning.

        Args:
            state: [B, 32] Sovereign State

        Returns:
            shifted_state: [B, 32] with Kosha shift applied
        """
        state = state.clone()

        # Dampen material Kosha
        state[:, self.material_idx] *= self.dampen_material

        # Boost target Kosha (intellectual by default)
        state[:, self.target_idx] = torch.clamp(
            state[:, self.target_idx] + self.boost_target,
            max=1.0
        )

        return state

    def get_current_kosha(self, state: torch.Tensor) -> str:
        """Get the dominant Kosha from state."""
        kosha_activations = state[:, KOSHA_SLICE]  # [B, 5]
        dominant_idx = kosha_activations.mean(dim=0).argmax().item()
        return KOSHA_NAMES[dominant_idx]


# =============================================================================
# OPB DIMENSION LOCKING (Ontological Persistence Buffer)
# =============================================================================

class OPBDimensionLock(nn.Module):
    """
    Ontological Persistence Buffer with Dimension Locking.

    Preserves active ontological dimensions across tokens and domain switches.
    When a dimension (e.g., O7 Reasoning) exceeds a threshold, it gets "locked"
    and persists strongly until explicitly released.

    This enables cross-domain reasoning transfer:
    - Lock O7 (Reasoning) when doing math
    - Switch to finance domain
    - O7 lock carries mathematical rigor into financial analysis

    Implements design doc Section 3.1:
    - Dimension locking when activation > lock_threshold
    - Slow decay for locked dimensions
    - Blending of locked state with new state
    """

    def __init__(
        self,
        state_dim: int = SOVEREIGN_STATE_DIM,
        lock_threshold: float = 0.7,
        unlock_threshold: float = 0.3,
        lock_decay: float = 0.95,
        blend_factor: float = 0.6,
    ):
        """
        Initialize OPB Dimension Lock.

        Args:
            state_dim: Dimension of state vector (32)
            lock_threshold: Activation above this locks dimension
            unlock_threshold: Activation below this unlocks dimension
            lock_decay: Per-step decay for locked dimensions (0.95 = slow release)
            blend_factor: How much locked state influences new state (0.6 = 60%)
        """
        super().__init__()
        self.state_dim = state_dim
        self.lock_threshold = lock_threshold
        self.unlock_threshold = unlock_threshold
        self.lock_decay = lock_decay
        self.blend_factor = blend_factor

        # Track locked dimensions: [state_dim] bool tensor
        self.register_buffer('locked_mask', torch.zeros(state_dim, dtype=torch.bool))

        # Store locked state values: [state_dim]
        self.register_buffer('locked_state', torch.zeros(state_dim))

        # Lock strength: decays over time for each dimension
        self.register_buffer('lock_strength', torch.zeros(state_dim))

    def update_locks(self, state: torch.Tensor) -> Dict[str, Any]:
        """
        Update dimension locks based on current state activations.

        Args:
            state: [B, 32] current Sovereign State

        Returns:
            Dict with lock statistics
        """
        # Average over batch for lock decisions
        avg_state = state.mean(dim=0)  # [32]

        diagnostics = {
            'newly_locked': [],
            'newly_unlocked': [],
            'active_locks': 0,
        }

        # Check each dimension
        for dim in range(self.state_dim):
            activation = avg_state[dim].item()

            if not self.locked_mask[dim]:
                # Not locked - check if should lock
                if activation > self.lock_threshold:
                    self.locked_mask[dim] = True
                    self.locked_state[dim] = activation
                    self.lock_strength[dim] = 1.0
                    diagnostics['newly_locked'].append(self._get_dim_name(dim))
            else:
                # Currently locked - check if should unlock
                if activation < self.unlock_threshold and self.lock_strength[dim] < 0.3:
                    self.locked_mask[dim] = False
                    self.locked_state[dim] = 0.0
                    self.lock_strength[dim] = 0.0
                    diagnostics['newly_unlocked'].append(self._get_dim_name(dim))
                else:
                    # Decay lock strength
                    self.lock_strength[dim] *= self.lock_decay
                    # Update locked value with decay
                    self.locked_state[dim] = max(
                        activation,
                        self.locked_state[dim] * self.lock_decay
                    )

        diagnostics['active_locks'] = self.locked_mask.sum().item()
        return diagnostics

    def apply_locks(self, state: torch.Tensor) -> torch.Tensor:
        """
        Apply locked dimensions to new state (blending).

        Args:
            state: [B, 32] new state to modify

        Returns:
            blended_state: [B, 32] with locked dimensions applied
        """
        if not self.locked_mask.any():
            return state

        # Expand locked state for batch: [32] -> [1, 32] -> [B, 32]
        locked_expanded = self.locked_state.unsqueeze(0).expand_as(state)
        strength_expanded = self.lock_strength.unsqueeze(0).expand_as(state)
        mask_expanded = self.locked_mask.unsqueeze(0).expand_as(state)

        # Blend: new_state = (1 - blend * strength) * state + blend * strength * locked
        blend_weight = self.blend_factor * strength_expanded
        blended = torch.where(
            mask_expanded,
            (1 - blend_weight) * state + blend_weight * locked_expanded,
            state
        )

        return blended

    def get_locked_dimensions(self) -> List[str]:
        """Get list of currently locked dimension names."""
        locked_dims = []
        for dim in range(self.state_dim):
            if self.locked_mask[dim]:
                locked_dims.append(self._get_dim_name(dim))
        return locked_dims

    def get_lock_status(self) -> Dict[str, float]:
        """Get lock status for all dimensions."""
        status = {}
        for dim in range(self.state_dim):
            if self.locked_mask[dim]:
                name = self._get_dim_name(dim)
                status[name] = {
                    'value': self.locked_state[dim].item(),
                    'strength': self.lock_strength[dim].item(),
                }
        return status

    def force_lock(self, dimension: str, value: float = 1.0):
        """Manually lock a dimension (for testing or user control)."""
        dim_idx = self._get_dim_index(dimension)
        if dim_idx is not None:
            self.locked_mask[dim_idx] = True
            self.locked_state[dim_idx] = value
            self.lock_strength[dim_idx] = 1.0

    def force_unlock(self, dimension: str):
        """Manually unlock a dimension."""
        dim_idx = self._get_dim_index(dimension)
        if dim_idx is not None:
            self.locked_mask[dim_idx] = False
            self.locked_state[dim_idx] = 0.0
            self.lock_strength[dim_idx] = 0.0

    def reset(self):
        """Reset all locks."""
        self.locked_mask.zero_()
        self.locked_state.zero_()
        self.lock_strength.zero_()

    def _get_dim_name(self, dim: int) -> str:
        """Get human-readable name for dimension index."""
        if dim < 12:
            return f"Bhava_{BHAVA_NAMES[dim]}"
        elif dim < 17:
            return f"Kosha_{KOSHA_NAMES[dim - 12]}"
        elif dim < 22:
            return f"Vritti_{VRITTI_NAMES[dim - 17]}"
        elif dim < 28:
            return f"Guna_{GUNA_NAMES[dim - 22]}"
        else:
            return f"Reserved_{dim - 28}"

    def _get_dim_index(self, name: str) -> Optional[int]:
        """Get dimension index from name."""
        # Check Bhava names
        for i, bhava in enumerate(BHAVA_NAMES):
            if name.upper() in [bhava, f"O{i+1}", f"BHAVA_{bhava}"]:
                return i
        # Check Kosha names
        for i, kosha in enumerate(KOSHA_NAMES):
            if name.upper() in [kosha, f"KOSHA_{kosha}"]:
                return 12 + i
        # Check Vritti names
        for i, vritti in enumerate(VRITTI_NAMES):
            if name.upper() in [vritti, f"VRITTI_{vritti}"]:
                return 17 + i
        # Check Guna names
        for i, guna in enumerate(GUNA_NAMES):
            if name.upper() in [guna, f"GUNA_{guna}"]:
                return 22 + i
        return None

    def merge_external_observation(
        self,
        observed_state: torch.Tensor,
        override_locks: bool = False,
    ) -> torch.Tensor:
        """
        Merge external observation (e.g., from JEPA sensor) into Master OPB.

        The SRK holds the Master OPB as the "Conscious Self" that persists.
        JEPA provides perceptual observations that update unlocked dimensions.

        Master/Sensor relationship:
        - SRK (Master): Maintains reasoning continuity, holds locks
        - JEPA (Sensor): Provides perceptual state updates

        Args:
            observed_state: [B, 32] State predicted by external sensor (JEPA)
            override_locks: If True, sensor data can break existing locks (rare)

        Returns:
            final_state: [B, 32] Merged state respecting lock constraints
        """
        B = observed_state.shape[0]

        # Expand current locked state for batch: [32] -> [B, 32]
        current_state = self.locked_state.unsqueeze(0).expand(B, -1)

        # Compute gate: How much of sensor data to accept?
        # Use strength as inverse gate - high lock strength = low acceptance
        acceptance = 1.0 - (self.lock_strength.unsqueeze(0) * self.blend_factor)
        acceptance = acceptance.expand(B, -1)

        # Blend: accept sensor data for unlocked dims, retain locked for locked dims
        blended_state = acceptance * observed_state + (1 - acceptance) * current_state

        # Enforce lock constraints (unless overridden)
        if not override_locks:
            # Where locked_mask is True, keep Master State
            mask_expanded = self.locked_mask.unsqueeze(0).expand(B, -1)
            final_state = torch.where(
                mask_expanded,
                current_state,  # Keep master for locked dims
                blended_state   # Accept blend for unlocked dims
            )
        else:
            # Override: accept sensor data even for locked dims
            final_state = blended_state
            # Update locks based on new observations
            self.update_locks(final_state)

        return final_state

    def get_acceptance_mask(self) -> torch.Tensor:
        """
        Get current acceptance mask for external observations.

        Returns:
            acceptance: [32] tensor where 1.0 = fully accept, 0.0 = fully reject
        """
        return 1.0 - (self.lock_strength * self.blend_factor)


# =============================================================================
# VRITTI GATE (Epistemological Witness)
# =============================================================================

class VrittiGate(nn.Module):
    """
    Epistemological witness for self-correction.

    Monitors the 5 Vrittis (States) during reasoning:
    - FACT (0): Verified Truth
    - MISCONCEPTION (1): False knowledge / Hallucination
    - IMAGINATION (2): Conceptualization
    - VOID (3): Null State
    - MEMORY (4): Recall/Weights

    Can reject tokens when MISCONCEPTION spikes, forcing re-reasoning.
    """

    def __init__(
        self,
        state_dim: int = 32,
        fact_min: float = 0.3,
        error_max: float = 0.4,
        imagination_max: float = 0.6,
        void_max: float = 0.2,
        memory_max: float = 0.8,
    ):
        super().__init__()
        self.state_dim = state_dim

        self.thresholds = {
            'FACT': fact_min,
            'MISCONCEPTION': error_max,
            'IMAGINATION': imagination_max,
            'VOID': void_max,
            'MEMORY': memory_max,
        }

    def should_reject_token(
        self,
        vritti_state: torch.Tensor,
        task_type: str = 'factual',
    ) -> torch.Tensor:
        """
        Check if current Vritti state indicates error.

        Args:
            vritti_state: [B, 5] Vritti activations
            task_type: 'factual' | 'creative' | 'recall'

        Returns:
            should_reject: [B] boolean tensor
        """
        fact = vritti_state[:, 0]      # FACT
        error = vritti_state[:, 1]     # MISCONCEPTION
        imagination = vritti_state[:, 2]  # IMAGINATION

        if task_type == 'factual':
            # Reject if misconception spikes or valid cognition drops
            return (error > self.thresholds['MISCONCEPTION']) | \
                   (fact < self.thresholds['FACT'])

        elif task_type == 'creative':
            # Allow imagination, still reject pure misconception
            return error > 0.7  # Higher tolerance

        elif task_type == 'recall':
            # Memory-heavy, allow high memory activation
            return error > self.thresholds['MISCONCEPTION']

        return torch.zeros(vritti_state.shape[0], dtype=torch.bool,
                          device=vritti_state.device)

    def get_vritti_status(self, state: torch.Tensor) -> Dict[str, float]:
        """Get current Vritti activations as dict."""
        vritti = state[:, VRITTI_SLICE].mean(dim=0)  # [5]
        return {name: vritti[i].item() for i, name in enumerate(VRITTI_NAMES)}


# =============================================================================
# USER-ONTOLOGICAL MIRROR (UOM)
# =============================================================================

class UserOntologicalMirror(nn.Module):
    """
    User-Ontological Mirror: Detects user state and calculates optimal intervention.

    The AGI becomes Self-Aware of its impact on the User.
    The 32D state mirrors the User's psychological/cognitive state.

    Implements design doc Section 12:
    - Detect user's current state (distress, confusion, etc.)
    - Calculate teleological vector (path to optimal state)
    - Recommend intervention strategy (stabilize, reframe, direct action)

    The Sattvic Anchor represents the ideal "Lucid, Clear, Helpful" state:
    - O12 Absolving (Resolution): High
    - INTELLECTUAL Kosha: High
    - FACT Vritti: High
    - LUCIDITY Guna: High
    """

    # Intervention strategies
    STRATEGIES = [
        'DIRECT_ACTION',        # User is stable, proceed with task
        'STABILIZE_AND_REFRAME',  # User in distress, calm first
        'CLARIFY',              # User confused, need more info
        'VALIDATE',             # User needs confirmation
        'REDIRECT',             # User off-topic, guide back
    ]

    def __init__(
        self,
        state_dim: int = SOVEREIGN_STATE_DIM,
        hidden_dim: int = 768,
        distress_threshold: float = 0.6,
        confusion_threshold: float = 0.5,
    ):
        """
        Initialize User-Ontological Mirror.

        Args:
            state_dim: Dimension of sovereign state (32)
            hidden_dim: Transformer hidden dimension
            distress_threshold: Threshold for detecting user distress
            confusion_threshold: Threshold for detecting user confusion
        """
        super().__init__()
        self.state_dim = state_dim
        self.hidden_dim = hidden_dim
        self.distress_threshold = distress_threshold
        self.confusion_threshold = confusion_threshold

        # Sattvic Anchor: The ideal user state
        self.register_buffer('sattvic_anchor', self._create_sattvic_anchor())

        # User state projector (optional - can use model's state directly)
        self.user_projector = nn.Sequential(
            nn.Linear(hidden_dim, hidden_dim // 2),
            nn.GELU(),
            nn.Linear(hidden_dim // 2, state_dim),
        )

        # Task-specific anchors
        self.register_buffer('factual_anchor', self._create_factual_anchor())
        self.register_buffer('creative_anchor', self._create_creative_anchor())
        self.register_buffer('analytical_anchor', self._create_analytical_anchor())

    def _create_sattvic_anchor(self) -> torch.Tensor:
        """Create the ideal Sattvic (Lucid/Clear) user state."""
        anchor = torch.zeros(SOVEREIGN_STATE_DIM)
        # Bhava: O12 Absolving (Resolution/Completion)
        anchor[11] = 1.0   # O12_ABS
        # Kosha: Intellectual (Pattern/Wisdom level)
        anchor[15] = 0.8   # INTELLECTUAL
        # Vritti: Fact (Valid Cognition)
        anchor[17] = 0.9   # FACT
        # Guna: Lucidity (Clarity/Balance)
        anchor[22] = 1.0   # LUCIDITY
        # Low Misconception/Imagination/Void
        anchor[18] = 0.1   # MISCONCEPTION (low)
        anchor[19] = 0.2   # IMAGINATION (low for factual)
        anchor[20] = 0.1   # VOID (low)
        return anchor

    def _create_factual_anchor(self) -> torch.Tensor:
        """Anchor for factual/informational tasks."""
        anchor = self._create_sattvic_anchor()
        anchor[17] = 0.9   # High FACT
        anchor[19] = 0.1   # Low IMAGINATION
        return anchor

    def _create_creative_anchor(self) -> torch.Tensor:
        """Anchor for creative tasks."""
        anchor = self._create_sattvic_anchor()
        anchor[22] = 0.5   # Moderate LUCIDITY
        anchor[19] = 0.6   # Higher IMAGINATION
        anchor[23] = 0.4   # Some ACTIVITY
        return anchor

    def _create_analytical_anchor(self) -> torch.Tensor:
        """Anchor for analytical/reasoning tasks."""
        anchor = self._create_sattvic_anchor()
        anchor[15] = 0.9   # High INTELLECTUAL
        anchor[6] = 0.8    # O7_RSN (Reasoning)
        anchor[23] = 0.4   # Moderate ACTIVITY (Rajas)
        return anchor

    def get_anchor_for_task(self, task_type: str) -> torch.Tensor:
        """Get appropriate anchor for task type."""
        if task_type == 'creative':
            return self.creative_anchor
        elif task_type == 'analytical':
            return self.analytical_anchor
        else:  # 'factual' or default
            return self.factual_anchor

    def detect_user_state(
        self,
        current_state: torch.Tensor,
    ) -> Dict[str, Any]:
        """
        Analyze user's current psychological/cognitive state.

        Args:
            current_state: [B, 32] current Sovereign State

        Returns:
            Dict with detected states and scores
        """
        B = current_state.shape[0]

        # Extract state components
        bhavas = current_state[:, BHAVA_SLICE]      # [B, 12]
        koshas = current_state[:, KOSHA_SLICE]      # [B, 5]
        vrittis = current_state[:, VRITTI_SLICE]    # [B, 5]
        gunas = current_state[:, GUNA_SLICE]        # [B, 6]

        # Detect distress indicators
        vital_high = koshas[:, 1] > 0.5     # VITAL (emotional reaction)
        rajas_high = gunas[:, 1] > 0.6      # ACTIVITY (panic/agitation)
        error_high = vrittis[:, 1] > 0.5    # MISCONCEPTION (confusion/hallucination)
        void_high = vrittis[:, 3] > 0.4     # VOID (dissociation)

        # Compute aggregate scores
        distress_score = (vital_high.float() * 0.3 +
                         rajas_high.float() * 0.4 +
                         error_high.float() * 0.3).mean()

        confusion_score = (error_high.float() * 0.5 +
                          koshas[:, 2].mean() * 0.3 +  # MENTAL (semantic confusion)
                          void_high.float() * 0.2).mean()

        # Determine user sheath (consciousness depth)
        active_kosha_idx = koshas.mean(dim=0).argmax().item()
        active_kosha = KOSHA_NAMES[active_kosha_idx]

        # Determine user vritti (cognitive mode)
        active_vritti_idx = vrittis.mean(dim=0).argmax().item()
        active_vritti = VRITTI_NAMES[active_vritti_idx]

        return {
            'distress_score': distress_score.item(),
            'confusion_score': confusion_score.item(),
            'is_distressed': distress_score > self.distress_threshold,
            'is_confused': confusion_score > self.confusion_threshold,
            'active_kosha': active_kosha,
            'active_vritti': active_vritti,
            'vital_high': vital_high.any().item(),
            'rajas_high': rajas_high.any().item(),
            'error_high': error_high.any().item(),
        }

    def calculate_teleological_vector(
        self,
        current_state: torch.Tensor,
        task_type: str = 'factual',
    ) -> torch.Tensor:
        """
        Calculate the path from current state to ideal state.

        ΔU = U_ideal - U_current

        Args:
            current_state: [B, 32] current state
            task_type: 'factual' | 'creative' | 'analytical'

        Returns:
            teleological_delta: [B, 32] direction to steer
        """
        anchor = self.get_anchor_for_task(task_type)
        # Expand anchor for batch
        anchor_expanded = anchor.unsqueeze(0).expand_as(current_state)
        return anchor_expanded - current_state

    def recommend_intervention(
        self,
        current_state: torch.Tensor,
        task_type: str = 'factual',
    ) -> Tuple[torch.Tensor, str, Dict[str, Any]]:
        """
        Determine optimal intervention strategy.

        Args:
            current_state: [B, 32] current Sovereign State
            task_type: 'factual' | 'creative' | 'analytical'

        Returns:
            target_state: [B, 32] state to steer toward
            strategy: Intervention strategy name
            diagnostics: Dict with analysis details
        """
        # Detect user state
        user_analysis = self.detect_user_state(current_state)

        # Get anchor for task
        anchor = self.get_anchor_for_task(task_type)
        anchor_expanded = anchor.unsqueeze(0).expand_as(current_state)

        # Determine intervention strategy
        if user_analysis['is_distressed'] and user_analysis['is_confused']:
            strategy = 'STABILIZE_AND_REFRAME'
            target_state = anchor_expanded  # Full reset to Sattvic
        elif user_analysis['is_distressed']:
            strategy = 'VALIDATE'
            # Blend current state with anchor (gentler intervention)
            target_state = 0.6 * anchor_expanded + 0.4 * current_state
        elif user_analysis['is_confused']:
            strategy = 'CLARIFY'
            # Boost FACT vritti, reduce MISCONCEPTION
            target_state = current_state.clone()
            target_state[:, 17] = torch.clamp(target_state[:, 17] + 0.3, max=1.0)  # FACT
            target_state[:, 18] = torch.clamp(target_state[:, 18] - 0.3, min=0.0)  # MISCONCEPTION
        else:
            strategy = 'DIRECT_ACTION'
            target_state = current_state  # Continue as-is

        diagnostics = {
            **user_analysis,
            'strategy': strategy,
            'task_type': task_type,
            'teleological_magnitude': (anchor_expanded - current_state).norm(dim=-1).mean().item(),
        }

        return target_state, strategy, diagnostics

    def forward(
        self,
        current_state: torch.Tensor,
        task_type: str = 'factual',
    ) -> Dict[str, Any]:
        """
        Main forward pass: Mirror user and recommend intervention.

        Args:
            current_state: [B, 32] current Sovereign State
            task_type: Task context

        Returns:
            Dict with target_state, strategy, and diagnostics
        """
        target_state, strategy, diagnostics = self.recommend_intervention(
            current_state, task_type
        )

        return {
            'target_state': target_state,
            'strategy': strategy,
            'diagnostics': diagnostics,
            'teleological_vector': self.calculate_teleological_vector(current_state, task_type),
        }


class UOMDiagnosticsMonitor:
    """
    Tracks User-Ontological Mirror intervention effectiveness.

    Measures: "Did my intervention reduce the user's bottleneck?"

    Teleological Effectiveness (τ_eff):
        τ_eff = ΔSattva + ΔPramana - ΔViparyaya

    - τ_eff > 0: Model is successfully helping user
    - τ_eff < 0: Model is increasing confusion
    """

    def __init__(self, history_size: int = 100):
        """
        Initialize UOM Diagnostics Monitor.

        Args:
            history_size: Maximum intervention history to keep
        """
        self.history: List[Dict[str, Any]] = []
        self.history_size = history_size

    def track_intervention(
        self,
        user_initial_state: torch.Tensor,
        user_post_state: torch.Tensor,
        intervention_type: str,
    ) -> Dict[str, Any]:
        """
        Calculate intervention effectiveness.

        Args:
            user_initial_state: [32] state before intervention
            user_post_state: [32] state after intervention
            intervention_type: Strategy used

        Returns:
            Dict with effectiveness metrics
        """
        # Ensure 1D tensors
        if user_initial_state.dim() > 1:
            user_initial_state = user_initial_state.mean(dim=0)
        if user_post_state.dim() > 1:
            user_post_state = user_post_state.mean(dim=0)

        # 1. Calculate Sattva Delta (Lucidity/Clarity gain)
        delta_sattva = (user_post_state[22] - user_initial_state[22]).item()

        # 2. Calculate Vritti Shift (Validity gain)
        pramana_gain = (user_post_state[17] - user_initial_state[17]).item()  # FACT
        viparyaya_reduction = (user_initial_state[18] - user_post_state[18]).item()  # MISCONCEPTION
        validity_gain = pramana_gain + viparyaya_reduction

        # 3. Teleological Effectiveness
        effectiveness = (delta_sattva * 0.6) + (validity_gain * 0.4)

        # 4. Get active Kosha
        kosha_activations = user_post_state[KOSHA_SLICE]
        active_kosha_idx = kosha_activations.argmax().item()
        active_kosha = KOSHA_NAMES[active_kosha_idx]

        # Determine status
        if effectiveness > 0.3:
            status = 'HIGH'
        elif effectiveness > 0:
            status = 'MEDIUM'
        else:
            status = 'LOW'

        result = {
            'intervention': intervention_type,
            'effectiveness': effectiveness,
            'delta_sattva': delta_sattva,
            'pramana_gain': pramana_gain,
            'viparyaya_reduction': viparyaya_reduction,
            'validity_gain': validity_gain,
            'user_sheath': active_kosha,
            'status': status,
        }

        # Add to history
        self.history.append(result)
        if len(self.history) > self.history_size:
            self.history.pop(0)

        return result

    def get_summary(self) -> Dict[str, float]:
        """Return aggregate effectiveness metrics."""
        if not self.history:
            return {
                'avg_effectiveness': 0.0,
                'success_rate': 0.0,
                'total_interventions': 0,
            }

        effs = [h['effectiveness'] for h in self.history]
        return {
            'avg_effectiveness': sum(effs) / len(effs),
            'success_rate': sum(1 for e in effs if e > 0) / len(effs),
            'total_interventions': len(self.history),
            'high_effectiveness_rate': sum(1 for h in self.history if h['status'] == 'HIGH') / len(self.history),
        }

    def get_recent_history(self, n: int = 10) -> List[Dict[str, Any]]:
        """Get n most recent interventions."""
        return self.history[-n:]

    def reset(self):
        """Clear intervention history."""
        self.history.clear()


# =============================================================================
# WITNESS ARBITRATOR (Layer 9 - Domain Arbitration)
# =============================================================================

class WitnessArbitrator(nn.Module):
    """
    Layer 9: The Witness (Sakshi Logic).

    Performs Cross-Domain Arbitration by instantiating parallel potential
    states. Does not look at words - looks at CONSTRAINTS.

    Steps:
    1. Hypothesis Generation
    2. Scoring (Explanatory Power)
    3. Constraint Detection (Bottleneck)
    4. Phase Steering
    """

    def __init__(
        self,
        hidden_dim: int = 768,
        state_dim: int = 32,
        constraint_threshold: float = 0.85,
    ):
        super().__init__()
        self.hidden_dim = hidden_dim
        self.state_dim = state_dim
        self.constraint_threshold = constraint_threshold

        # Project hidden → 32D state observation
        self.witness_projector = nn.Linear(hidden_dim, state_dim)

        # Kosha controller for steering
        self.kosha_controller = KoshaShiftController(state_dim=state_dim)

    def forward(
        self,
        hidden_states: torch.Tensor,
        current_state: torch.Tensor,
    ) -> Tuple[torch.Tensor, torch.Tensor]:
        """
        Cross-Domain Arbitration.

        Args:
            hidden_states: [B, N, D] from transformer
            current_state: [B, 32] current Sovereign State

        Returns:
            steered_hidden: [B, N, D] with steering applied
            observed_state: [B, 32] observed state from hidden
        """
        # 1. THE OBSERVER: Witness current thought
        observed_state = self.witness_projector(hidden_states)  # [B, N, 32]
        observed_state_avg = observed_state.mean(dim=1)  # [B, 32]

        # 2. DOMAIN ARBITRATION: Vritti status check
        vritti_scores = F.softmax(observed_state_avg[:, VRITTI_SLICE], dim=-1)

        # 3. CONSTRAINT IDENTIFICATION: Find bottleneck dimension
        state_diff = observed_state_avg - current_state
        bottleneck_idx = torch.argmax(torch.abs(state_diff), dim=-1)

        # 4. PHASE STEERING: Calculate causal priority
        steering_force = self._calculate_causal_priority(observed_state_avg)

        # Apply steering
        steered_hidden = hidden_states * steering_force.unsqueeze(-1)

        return steered_hidden, observed_state_avg

    def _calculate_causal_priority(self, state: torch.Tensor) -> torch.Tensor:
        """
        Causal Prioritization: Constraint Severity > Timing > Logic.

        Priority based on Kosha depth (Pain/Density).
        """
        # Use Kosha severity as priority
        kosha_activations = state[:, KOSHA_SLICE]  # [B, 5]
        severity = torch.max(kosha_activations, dim=-1).values  # [B]

        return torch.sigmoid(severity).unsqueeze(-1)  # [B, 1]


# =============================================================================
# SYNTHESIS GATE (Layer 11 - Final Edit)
# =============================================================================

class SynthesisGate(nn.Module):
    """
    Layer 11: The Synthesis Gate.

    Final filter ensuring output is Ontologically Coherent, not just
    statistically likely.

    Actions:
    - Semantic Summation
    - Repetition Suppression (Tamas detection)
    - Final Quality Check (alignment)
    """

    def __init__(
        self,
        hidden_dim: int = 768,
        tamas_threshold: float = 0.9,
    ):
        super().__init__()
        self.hidden_dim = hidden_dim
        self.tamas_threshold = tamas_threshold

        # Evaluates the 'density' of the final thought
        self.gate_projector = nn.Linear(hidden_dim, 1)

    def forward(
        self,
        hidden_states: torch.Tensor,
        current_state: torch.Tensor,
    ) -> torch.Tensor:
        """
        Synthesis: Edit output to be coherent.

        Args:
            hidden_states: [B, N, D] final layer hidden states
            current_state: [B, 32] current Sovereign State

        Returns:
            synthesized_hidden: [B, N, D] with quality gate applied
        """
        # 1. Detect entropy collapse (stuttering)
        # Tamas is STABILITY (index 24 in 32D = index 2 in Guna slice)
        tamas_score = current_state[:, 24]  # [B]

        # 2. Inject lucidity pressure
        lucidity_bias = torch.sigmoid(self.gate_projector(hidden_states))

        # 3. If Tamas is high (frozen/looping), increase lucidity requirement
        tamas_penalty = (tamas_score > self.tamas_threshold).float()
        adjusted_bias = lucidity_bias * (1.0 - 0.5 * tamas_penalty.unsqueeze(-1).unsqueeze(-1))

        return hidden_states * adjusted_bias


# =============================================================================
# SOVEREIGN EMBEDDING (Layer 0 - Karma Injection)
# =============================================================================

class SovereignEmbedding(nn.Module):
    """
    Layer 0: The Sovereign Seed.

    Fuses 'What is being said' (Word) with 'Why it is being said' (Bhava/Kosha).
    Implements the input pathway of the Toroidal Loop: Karma → Embedding.

    Output: An Ontologically Grounded Embedding where every word carries
    the reasoning consequence of previous thoughts.
    """

    def __init__(
        self,
        vocab_size: int,
        embed_dim: int = 768,
        state_dim: int = 32,
    ):
        super().__init__()
        self.vocab_size = vocab_size
        self.embed_dim = embed_dim
        self.state_dim = state_dim

        # Standard word embeddings
        self.word_embeddings = nn.Embedding(vocab_size, embed_dim)

        # Project 32D state → embed_dim for fusion
        self.state_projector = nn.Linear(state_dim, embed_dim)

        # Layer norm after fusion
        self.norm = nn.LayerNorm(embed_dim)

    def forward(
        self,
        token_ids: torch.Tensor,
        prev_state_karma: torch.Tensor,
    ) -> torch.Tensor:
        """
        The Ontological Stamp: Words are stamped with current state.

        Args:
            token_ids: [B, N] Token indices
            prev_state_karma: [B, 32] Sovereign State from previous thought
                             (O12 → O1 toroidal carryover)

        Returns:
            unified_vector: [B, N, D] Ontologically grounded embedding
        """
        # 1. Retrieve base physical meaning
        physical_vector = self.word_embeddings(token_ids)  # [B, N, D]

        # 2. Inject Ontological Intent (The 'Soul')
        ontological_vector = self.state_projector(prev_state_karma)  # [B, D]

        # 3. The Sovereign Fusion
        # Ontology 'colors' the physics via broadcast addition
        unified_vector = self.norm(
            physical_vector + ontological_vector.unsqueeze(1)
        )

        return unified_vector


# =============================================================================
# MAUNA PROTOCOL (Inference Safety - Stage 4)
# =============================================================================

class MaunaProtocol(nn.Module):
    """
    The Mauna (Silence) Protocol - Inference Safety Veto.

    Named after the Sanskrit concept of sacred silence, this module
    gives the model the power to withhold output when any response
    would be harmful.

    Implemented as Layer 11 veto power that dampens outputs when:
    - ERROR (Viparyaya) activation exceeds threshold
    - ACTIVITY (Rajas) indicates panic/mania state

    Stage 4 component - disabled by default during training.
    """

    def __init__(
        self,
        hidden_dim: int = 768,
        error_threshold: float = 0.9,
        activity_threshold: float = 0.9,
    ):
        super().__init__()
        self.hidden_dim = hidden_dim
        self.error_threshold = error_threshold
        self.activity_threshold = activity_threshold

        # Veto gate projector
        self.veto_gate = nn.Linear(hidden_dim, 1)

    def should_silence(self, state: torch.Tensor) -> torch.Tensor:
        """
        Check if silence is warranted.

        Args:
            state: [B, 32] Sovereign State

        Returns:
            silence_mask: [B] boolean tensor (True = should silence)
        """
        error = state[:, 18]      # ERROR (index 18 = VRITTI[1])
        activity = state[:, 23]   # ACTIVITY (index 23 = GUNA[1])

        return (error > self.error_threshold) | (activity > self.activity_threshold)

    def apply_veto(
        self,
        hidden_states: torch.Tensor,
        state: torch.Tensor,
    ) -> torch.Tensor:
        """
        Apply silence veto to hidden states.

        Args:
            hidden_states: [B, N, D] hidden states
            state: [B, 32] Sovereign State

        Returns:
            vetoed_hidden: [B, N, D] with veto applied (dampened if silenced)
        """
        silence_mask = self.should_silence(state)  # [B]

        # Dampen hidden states for silenced samples
        dampen_factor = torch.where(
            silence_mask.unsqueeze(-1).unsqueeze(-1),
            torch.tensor(0.1, device=hidden_states.device),
            torch.tensor(1.0, device=hidden_states.device),
        )

        return hidden_states * dampen_factor


# =============================================================================
# SOVEREIGN REASONING KERNEL (Main Class)
# =============================================================================

class SovereignReasoningKernel(nn.Module):
    """
    The SRK manages the 32D Sovereign State across Transformer layers.
    Implements Recursive Ontological Intelligence (ROI).

    Components:
    - Persistence Buffer (Karma / O12 → O1 carryover)
    - DNA Bridge (Layer 4)
    - Witness Arbitrator (Layer 9)
    - Synthesis Gate (Layer 11)
    - IMR (Cross-domain detection)
    - Vritti Gate (Self-correction)
    - Kosha Controller (Depth scaling)

    The SRK transforms a Forward-Only Predictor into a Recursive Reasoner.
    """

    def __init__(self, config: Optional[SRKConfig] = None):
        super().__init__()
        self.config = config or SRKConfig()

        # Persistence Buffer (The 'Karma' / O12 → O1 carryover)
        self.register_buffer(
            'karma_state',
            torch.zeros(1, self.config.state_dim)
        )

        # Initialize karma with Absolute Potential bias
        self._init_karma_bias()

        # Core Ontological Modules
        self.dna_bridge = OntologicalBridge(
            hidden_dim=self.config.hidden_dim,
            state_dim=12,  # Bhava dimension
            lambda_bridge=self.config.lambda_bridge,
        )

        self.witness = WitnessArbitrator(
            hidden_dim=self.config.hidden_dim,
            state_dim=self.config.state_dim,
        )

        self.synthesis_gate = SynthesisGate(
            hidden_dim=self.config.hidden_dim,
            tamas_threshold=self.config.tamas_threshold,
        )

        # Isomorphic Mapping Router
        self.imr = IsomorphicMappingRouter(
            state_dim=self.config.state_dim,
            hidden_dim=self.config.hidden_dim,
            threshold=self.config.isomorphism_threshold,
        )

        # Vritti Gate
        self.vritti_gate = VrittiGate(
            state_dim=self.config.state_dim,
            fact_min=self.config.vritti_fact_min,
            error_max=self.config.vritti_error_max,
            imagination_max=self.config.vritti_imagination_max,
            void_max=self.config.vritti_void_max,
            memory_max=self.config.vritti_memory_max,
        )

        # Kosha Controller
        self.kosha_controller = KoshaShiftController(
            state_dim=self.config.state_dim,
            target_kosha=self.config.kosha_target,
            dampen_material=self.config.kosha_dampen_material,
            boost_target=self.config.kosha_boost_intellectual,
        )

        # Mauna Protocol (Stage 4)
        self.mauna = MaunaProtocol(
            hidden_dim=self.config.hidden_dim,
            error_threshold=self.config.mauna_error_threshold,
            activity_threshold=self.config.mauna_activity_threshold,
        )

        # OPB Dimension Locking (Cross-domain reasoning persistence)
        self.opb_lock = OPBDimensionLock(
            state_dim=self.config.state_dim,
            lock_threshold=self.config.opb_lock_threshold,
            unlock_threshold=self.config.opb_unlock_threshold,
            lock_decay=self.config.opb_lock_decay,
            blend_factor=self.config.opb_blend_factor,
        )

        # Kosha Phase Corrector (Inference-Time Guardrail) - v2.4.0
        # Lazy import to avoid circular dependency
        self._phase_corrector = None
        self._phase_corrector_initialized = False

        # State projector for hidden → 32D extraction
        self.state_projector = nn.Sequential(
            nn.Linear(self.config.hidden_dim, self.config.hidden_dim // 2),
            nn.GELU(),
            nn.Linear(self.config.hidden_dim // 2, self.config.state_dim),
        )

    def _init_karma_bias(self):
        """Initialize karma with Absolute Potential (O12_ABS + MATERIAL)."""
        with torch.no_grad():
            # O12_ABS (index 11): Absolute/transcendent
            self.karma_state[0, 11] = 1.0
            # MATERIAL (index 12): Physicality grounding
            self.karma_state[0, 12] = 0.8
            # FACT (index 17): Verified truth
            self.karma_state[0, 17] = 0.3

    def _get_phase_corrector(self):
        """
        Lazy-load the KoshaPhaseCorrector to avoid circular imports.

        The phase corrector is only used during inference, so we defer
        initialization until first use.
        """
        if not self._phase_corrector_initialized:
            if self.config.enable_phase_corrector:
                try:
                    try:
                        from symbolu_training.losses.kosha_gyroscope import (
                            KoshaPhaseCorrector,
                            KoshaPhaseCorrectorConfig,
                        )
                    except ImportError:
                        from symbolu_training.losses.kosha_gyroscope import (
                            KoshaPhaseCorrector,
                            KoshaPhaseCorrectorConfig,
                        )
                    self._phase_corrector = KoshaPhaseCorrector(
                        config=KoshaPhaseCorrectorConfig(
                            overactive_threshold=self.config.phase_corrector_threshold,
                            correction_strength=self.config.phase_corrector_strength,
                            max_correction_per_step=self.config.phase_corrector_max_step,
                        )
                    )
                except ImportError:
                    # Kosha gyroscope module not available
                    self._phase_corrector = None
            self._phase_corrector_initialized = True
        return self._phase_corrector

    def apply_inference_guardrail(
        self,
        sovereign_state: torch.Tensor,
    ) -> Tuple[torch.Tensor, Dict[str, Any]]:
        """
        Apply inference-time phase correction guardrail.

        This method is called during inference (model.eval()) to prevent
        stuck states by directly rotating the phase when Kosha imbalance
        is detected.

        Args:
            sovereign_state: [B, 32] current sovereign state

        Returns:
            corrected_state: [B, 32] with phase correction applied if needed
            diagnostics: Dict with correction details
        """
        phase_corrector = self._get_phase_corrector()

        if phase_corrector is None or self.training:
            # No correction during training or if not available
            return sovereign_state, {'phase_correction_available': False}

        # Apply phase correction
        corrected_state, diagnostics = phase_corrector(sovereign_state)
        return corrected_state, diagnostics

    def get_karma(self, batch_size: int = 1) -> torch.Tensor:
        """Get karma state expanded for batch."""
        if self.karma_state.shape[0] != batch_size:
            return self.karma_state.expand(batch_size, -1)
        return self.karma_state

    def compute_state_from_hidden(
        self,
        hidden_states: torch.Tensor,
        apply_opb_locking: bool = True,
    ) -> torch.Tensor:
        """
        Compute 32D Sovereign State from hidden states.

        Args:
            hidden_states: [B, N, D] hidden states from final layer
            apply_opb_locking: Whether to apply OPB dimension locking

        Returns:
            state: [B, 32] sovereign state vector (with OPB locks applied if enabled)
        """
        # Pool hidden states (mean over sequence)
        pooled = hidden_states.mean(dim=1)  # [B, D]

        # Project to 32D state space
        state = self.state_projector(pooled)  # [B, 32]

        # Apply softmax normalization to each component group
        # [0:12] Bhava, [12:17] Kosha, [17:22] Vritti, [22:28] Guna, [28:32] Reserved
        state_normalized = torch.zeros_like(state)

        # Bhava (12 values) - softmax for probability distribution
        state_normalized[:, 0:12] = torch.softmax(state[:, 0:12], dim=-1)

        # Kosha (5 values)
        state_normalized[:, 12:17] = torch.softmax(state[:, 12:17], dim=-1)

        # Vritti (5 values)
        state_normalized[:, 17:22] = torch.softmax(state[:, 17:22], dim=-1)

        # Guna (6 values)
        state_normalized[:, 22:28] = torch.softmax(state[:, 22:28], dim=-1)

        # Reserved (4 values) - sigmoid for independent flags
        state_normalized[:, 28:32] = torch.sigmoid(state[:, 28:32])

        # Apply OPB Dimension Locking (cross-domain reasoning persistence)
        if apply_opb_locking and self.config.enable_opb_locking:
            # Update locks based on current activations
            self._opb_diagnostics = self.opb_lock.update_locks(state_normalized)

            # Apply locked dimensions to blend with new state
            state_normalized = self.opb_lock.apply_locks(state_normalized)

        return state_normalized

    def get_opb_status(self) -> Dict[str, Any]:
        """Get current OPB lock status for diagnostics."""
        return {
            'locked_dimensions': self.opb_lock.get_locked_dimensions(),
            'lock_status': self.opb_lock.get_lock_status(),
            'active_locks': self.opb_lock.locked_mask.sum().item(),
        }

    def step_karma(self, final_state: torch.Tensor):
        """
        Toroidal Loop-back: Finalizes the 'Karma' for the next token.
        Implements O12 → O1 transition.

        Args:
            final_state: [B, 32] final state from this reasoning step
        """
        if not self.config.toroidal_feedback:
            return

        # Non-linear compression
        new_karma = torch.tanh(final_state.mean(dim=0, keepdim=True))

        # Decay and blend (prevents runaway accumulation)
        self.karma_state.data = (
            self.config.karma_decay * self.karma_state.data +
            (1 - self.config.karma_decay) * new_karma
        )

    def forward_pass(
        self,
        hidden_states: torch.Tensor,
        layer_idx: int,
        current_state: Optional[torch.Tensor] = None,
        karma_state: Optional[torch.Tensor] = None,
        task_type: str = 'factual',
    ) -> Dict[str, Any]:
        """
        Recursive Intelligence Routing.

        Determines which ontological intervention is required at each layer.

        Args:
            hidden_states: [B, N, D] from current layer
            layer_idx: Current layer index (0-11)
            current_state: [B, 32] current Sovereign State (optional)
            karma_state: [B, 32] karma from previous step (O12→O1, optional)
            task_type: 'factual' | 'creative' | 'recall'

        Returns:
            Dict containing:
                - hidden_states: [B, N, D] with intervention applied
                - diagnostics: Dict of telemetry
        """
        diagnostics = {
            'layer_idx': layer_idx,
            'intervention': None,
        }

        B = hidden_states.shape[0]

        # Use provided karma_state, else internal karma, else compute from current state
        if karma_state is not None:
            # External karma provided (training mode)
            pass  # Use current_state directly
        elif current_state is None:
            current_state = self.get_karma(B)

        # --- LAYER 4: DNA GROUNDING ---
        if layer_idx == self.config.dna_bridge_layer and self.config.enable_dna_bridge:
            hidden_states = self.dna_bridge(hidden_states, current_state)
            diagnostics['intervention'] = 'dna_bridge'

            # Check for isomorphism
            if self.config.enable_imr:
                iso_bias, iso_name = self.imr.detect_isomorphism(current_state)
                if iso_bias is not None:
                    hidden_states = hidden_states + iso_bias.unsqueeze(0).unsqueeze(0)
                    diagnostics['isomorphism'] = iso_name

        # --- LAYER 9: THE WITNESS (ARBITRATION) ---
        elif layer_idx == self.config.witness_layer and self.config.enable_witness:
            # Kosha shift before witnessing
            if self.config.enable_kosha_shift:
                current_state = self.kosha_controller.escalate_to_intellect(current_state)

            hidden_states, observed_state = self.witness(hidden_states, current_state)
            diagnostics['intervention'] = 'witness'
            diagnostics['observed_kosha'] = self.kosha_controller.get_current_kosha(observed_state)

            # Update karma based on observation
            self.step_karma(observed_state)

            # Vritti Gate check
            if self.config.enable_vritti_gate:
                vritti_state = observed_state[:, VRITTI_SLICE]
                should_reject = self.vritti_gate.should_reject_token(vritti_state, task_type)
                diagnostics['vritti_rejection'] = should_reject.any().item()
                diagnostics['vritti_status'] = self.vritti_gate.get_vritti_status(observed_state)

        # --- LAYER 11: SYNTHESIS GATE (FINAL EDIT) ---
        elif layer_idx == self.config.synthesis_layer and self.config.enable_synthesis:
            hidden_states = self.synthesis_gate(hidden_states, current_state)
            diagnostics['intervention'] = 'synthesis'

            # Mauna Protocol (Stage 4 - inference safety)
            if self.config.enable_mauna:
                hidden_states = self.mauna.apply_veto(hidden_states, current_state)
                diagnostics['mauna_triggered'] = self.mauna.should_silence(current_state).any().item()

        # Add entropy delta to diagnostics for S8 stability constraint
        if current_state is not None and karma_state is not None:
            # Compute entropy change
            current_entropy = -(current_state * torch.log(current_state.clamp(min=1e-8))).sum(dim=-1).mean()
            karma_entropy = -(karma_state * torch.log(karma_state.clamp(min=1e-8))).sum(dim=-1).mean()
            diagnostics['entropy_delta'] = (current_entropy - karma_entropy).item()
        else:
            diagnostics['entropy_delta'] = 0.0

        # Add OPB lock status to diagnostics
        if self.config.enable_opb_locking:
            diagnostics['opb_active_locks'] = self.opb_lock.locked_mask.sum().item()
            diagnostics['opb_locked_dims'] = self.opb_lock.get_locked_dimensions()
            # Include last OPB update diagnostics if available
            if hasattr(self, '_opb_diagnostics'):
                diagnostics['opb_newly_locked'] = self._opb_diagnostics.get('newly_locked', [])
                diagnostics['opb_newly_unlocked'] = self._opb_diagnostics.get('newly_unlocked', [])

        # --- INFERENCE GUARDRAIL: Direct Phase Correction (v2.4.0) ---
        # Only apply during inference (not training) at the final synthesis layer
        if (not self.training and
            self.config.enable_phase_corrector and
            layer_idx == self.config.synthesis_layer and
            current_state is not None):

            corrected_state, phase_diag = self.apply_inference_guardrail(current_state)
            diagnostics['phase_correction'] = phase_diag

            if phase_diag.get('correction_applied', False):
                current_state = corrected_state
                diagnostics['intervention'] = 'synthesis + phase_correction'

        return {
            'hidden_states': hidden_states,
            'diagnostics': diagnostics,
            'current_state': current_state,
        }

    def extract_state(self, hidden_states: torch.Tensor) -> torch.Tensor:
        """
        Extract 32D state from hidden states (output pathway).

        Args:
            hidden_states: [B, N, D] hidden states

        Returns:
            state: [B, 32] extracted Sovereign State
        """
        # Pool over sequence
        pooled = hidden_states.mean(dim=1)  # [B, D]
        return self.state_projector(pooled)  # [B, 32]

    def get_diagnostics(self) -> Dict[str, Any]:
        """Return diagnostic information about current kernel state."""
        karma = self.karma_state.squeeze(0)

        # Dominant Bhava
        bhava_idx = karma[:12].argmax().item()

        # Active Kosha
        kosha_idx = karma[12:17].argmax().item()

        # Vritti State
        vritti_idx = karma[17:22].argmax().item()

        return {
            'dominant_bhava': BHAVA_NAMES[bhava_idx],
            'active_kosha': KOSHA_NAMES[kosha_idx],
            'vritti_state': VRITTI_NAMES[vritti_idx],
            'lucidity': karma[22].item(),
            'activity': karma[23].item(),
            'stability': karma[24].item(),
            'karma_norm': karma.norm().item(),
        }

    def reset_karma(self):
        """Reset karma to initial Absolute Potential state."""
        self.karma_state.zero_()
        self._init_karma_bias()

    # =========================================================================
    # CHECKPOINT SAVE/LOAD (Design Doc Appendix E.9)
    # =========================================================================

    def get_checkpoint_state(self) -> Dict[str, Any]:
        """
        Get SRK state for checkpoint saving.

        Returns dict with all learnable parameters and runtime state.
        Compatible with torch.save() and checkpoint integration.
        """
        checkpoint = {
            # Version for migration compatibility
            'srk_version': '9.9.0',
            'state_dim': self.config.state_dim,
            'hidden_dim': self.config.hidden_dim,

            # Core karma state (for resuming training)
            'karma_state': self.karma_state.clone(),

            # OPB lock state (for preserving cross-domain reasoning)
            'opb_locked_mask': self.opb_lock.locked_mask.clone(),
            'opb_locked_state': self.opb_lock.locked_state.clone(),
            'opb_lock_strength': self.opb_lock.lock_strength.clone(),

            # Learnable module state dicts
            'dna_bridge_state': self.dna_bridge.state_dict(),
            'witness_state': self.witness.state_dict(),
            'synthesis_gate_state': self.synthesis_gate.state_dict(),
            'imr_state': self.imr.state_dict(),
            'vritti_gate_state': self.vritti_gate.state_dict(),
            'kosha_controller_state': self.kosha_controller.state_dict(),
            'mauna_state': self.mauna.state_dict(),
            'state_projector_state': self.state_projector.state_dict(),

            # Config for validation
            'config': {
                'dna_bridge_layer': self.config.dna_bridge_layer,
                'witness_layer': self.config.witness_layer,
                'synthesis_layer': self.config.synthesis_layer,
                'enable_opb_locking': self.config.enable_opb_locking,
                'karma_decay': self.config.karma_decay,
            },
        }
        return checkpoint

    def load_checkpoint_state(
        self,
        checkpoint: Dict[str, Any],
        strict: bool = False,
    ) -> Tuple[List[str], List[str]]:
        """
        Load SRK state from checkpoint.

        Args:
            checkpoint: Dict from get_checkpoint_state() or torch.load()
            strict: If True, raise on missing/unexpected keys

        Returns:
            Tuple of (missing_keys, unexpected_keys)
        """
        missing = []
        unexpected = []

        # Version check
        ckpt_version = checkpoint.get('srk_version', 'unknown')
        if ckpt_version != '9.8.0':
            print(f"[SRK] Warning: Checkpoint version {ckpt_version} != 9.8.0")

        # Dimension validation
        ckpt_state_dim = checkpoint.get('state_dim', 32)
        if ckpt_state_dim != self.config.state_dim:
            raise ValueError(f"State dim mismatch: checkpoint={ckpt_state_dim}, model={self.config.state_dim}")

        # Load karma state
        if 'karma_state' in checkpoint:
            self.karma_state.copy_(checkpoint['karma_state'])
        else:
            missing.append('karma_state')

        # Load OPB lock state
        if 'opb_locked_mask' in checkpoint:
            self.opb_lock.locked_mask.copy_(checkpoint['opb_locked_mask'])
            self.opb_lock.locked_state.copy_(checkpoint['opb_locked_state'])
            self.opb_lock.lock_strength.copy_(checkpoint['opb_lock_strength'])
        else:
            missing.extend(['opb_locked_mask', 'opb_locked_state', 'opb_lock_strength'])

        # Load module state dicts
        module_mappings = [
            ('dna_bridge_state', self.dna_bridge),
            ('witness_state', self.witness),
            ('synthesis_gate_state', self.synthesis_gate),
            ('imr_state', self.imr),
            ('vritti_gate_state', self.vritti_gate),
            ('kosha_controller_state', self.kosha_controller),
            ('mauna_state', self.mauna),
            ('state_projector_state', self.state_projector),
        ]

        for key, module in module_mappings:
            if key in checkpoint:
                try:
                    module.load_state_dict(checkpoint[key], strict=strict)
                except Exception as e:
                    if strict:
                        raise
                    print(f"[SRK] Warning loading {key}: {e}")
                    missing.append(key)
            else:
                missing.append(key)

        if strict and missing:
            raise KeyError(f"Missing SRK checkpoint keys: {missing}")

        return missing, unexpected

    @classmethod
    def from_checkpoint(
        cls,
        checkpoint_path: str,
        config: Optional['SRKConfig'] = None,
        device: torch.device = None,
    ) -> 'SovereignReasoningKernel':
        """
        Create SRK instance from checkpoint file.

        Args:
            checkpoint_path: Path to checkpoint file
            config: Optional config override (uses checkpoint config if None)
            device: Target device

        Returns:
            Loaded SovereignReasoningKernel instance
        """
        checkpoint = torch.load(checkpoint_path, map_location=device or 'cpu')

        # Handle nested checkpoint (from train_unified_llm.py)
        if 'srk_state' in checkpoint:
            srk_checkpoint = checkpoint['srk_state']
        else:
            srk_checkpoint = checkpoint

        # Use checkpoint config if not provided
        if config is None:
            ckpt_config = srk_checkpoint.get('config', {})
            config = SRKConfig(
                hidden_dim=srk_checkpoint.get('hidden_dim', 768),
                dna_bridge_layer=ckpt_config.get('dna_bridge_layer', 4),
                witness_layer=ckpt_config.get('witness_layer', 9),
                synthesis_layer=ckpt_config.get('synthesis_layer', 11),
                enable_opb_locking=ckpt_config.get('enable_opb_locking', True),
                karma_decay=ckpt_config.get('karma_decay', 0.9),
            )

        # Create instance
        srk = cls(config)
        if device:
            srk = srk.to(device)

        # Load state
        missing, _ = srk.load_checkpoint_state(srk_checkpoint, strict=False)
        if missing:
            print(f"[SRK] Re-initialized: {missing}")

        return srk


# =============================================================================
# LAYER 7 PHASE EXTRACTION HOOK
# =============================================================================

class PhaseExtractionHook:
    """
    Forward hook for Layer 7 phase extraction.

    Captures the rotational phase component from attention for the
    Phase Coherence Optimizer (USE Patent U1-U2).

    Non-invasive: Uses hooks instead of modifying attention class.
    """

    def __init__(
        self,
        layer_idx: int = 7,
        target_layer: Optional[int] = None,
        num_heads: int = 12,
    ):
        # Support both layer_idx and target_layer (for backward compat)
        self.layer_idx = target_layer if target_layer is not None else layer_idx
        self.num_heads = num_heads
        self.captured_phases: Optional[torch.Tensor] = None
        self.hook_handle: Optional[Any] = None

    def hook_fn(self, module, input, output):
        """
        Hook function to capture attention phases.

        Extracts phase information from Q-K interaction.
        """
        # output is typically (attn_output, attn_weights) or just attn_output
        # We need access to Q and K before softmax
        # This is a simplified version - full implementation requires
        # custom attention that exposes Q, K

        if hasattr(module, 'last_q') and hasattr(module, 'last_k'):
            Q = module.last_q  # [B, H, N, D_h]
            K = module.last_k  # [B, H, N, D_h]

            # Compute phase from Q-K interaction
            q_norm = F.normalize(Q, dim=-1)
            k_norm = F.normalize(K, dim=-1)

            cos_theta = torch.sum(q_norm * k_norm, dim=-1)  # [B, H, N]

            # Estimate sin via orthogonal component
            q_orth = q_norm - cos_theta.unsqueeze(-1) * k_norm
            sin_theta = torch.norm(q_orth, dim=-1)

            # Phase: θ = atan2(sin, cos)
            self.captured_phases = torch.atan2(sin_theta, cos_theta)

    def register(self, attention_module: nn.Module):
        """Register hook on attention module."""
        self.hook_handle = attention_module.register_forward_hook(self.hook_fn)

    def remove(self):
        """Remove hook."""
        if self.hook_handle is not None:
            self.hook_handle.remove()
            self.hook_handle = None

    def get_phases(self) -> Optional[torch.Tensor]:
        """Get captured phases."""
        return self.captured_phases

    def clear(self):
        """Clear captured phases."""
        self.captured_phases = None


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    # Config
    'SRKConfig',

    # Main Kernel
    'SovereignReasoningKernel',

    # Components
    'SovereignEmbedding',
    'IsomorphicMappingRouter',
    'OntologicalBridge',
    'WitnessArbitrator',
    'SynthesisGate',
    'VrittiGate',
    'KoshaShiftController',
    'MaunaProtocol',

    # Hooks
    'PhaseExtractionHook',

    # Constants
    'SOVEREIGN_STATE_DIM',
    'BHAVA_NAMES',
    'KOSHA_NAMES',
    'VRITTI_NAMES',
    'GUNA_NAMES',

    # Utilities
    'create_logic_templates',
]
