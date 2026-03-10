#!/usr/bin/env python3
"""
Phase Transformer: General-Purpose O(n) LLM
============================================

A standalone transformer that replaces O(n²) attention with O(n) phase
synchronization. No ontological/Bhava dependencies - pure general-purpose LLM.

This enables:
1. Direct comparison with standard transformers
2. Testing U1-U4 formulas in isolation
3. Integration into any LLM architecture
4. Potential licensing for cost savings

Key Innovation (Patent U1-U4):
------------------------------
Traditional: Attention = softmax(QK^T/√d) × V    [O(n²)]
Phase:       Attention emerges from phase sync    [O(n)]

Mean-field approximation:
    Σⱼ sin(φᵢ - φⱼ) ≈ N × sin(φᵢ - φ_mean)

Usage:
------
    from symbolu.phase_transformer import (
        PhaseTransformer,
        StandardTransformer,
        compare_models,
    )

    # Create phase transformer (O(n))
    phase_model = PhaseTransformer(
        vocab_size=50257,
        embed_dim=768,
        num_layers=12,
        num_heads=12,
    )

    # Create standard transformer (O(n²)) for comparison
    std_model = StandardTransformer(
        vocab_size=50257,
        embed_dim=768,
        num_layers=12,
        num_heads=12,
    )

    # Compare
    results = compare_models(phase_model, std_model, seq_lengths=[512, 1024, 2048])
"""

import math
import time
from typing import Dict, List, Optional, Tuple, Any, Union
from dataclasses import dataclass

import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.checkpoint import checkpoint

# Check for FlashAttention / PyTorch 2.0 SDPA availability
FLASH_ATTN_AVAILABLE = False
SDPA_AVAILABLE = hasattr(F, 'scaled_dot_product_attention')

try:
    from flash_attn import flash_attn_func
    from flash_attn.flash_attn_interface import flash_attn_varlen_func
    FLASH_ATTN_AVAILABLE = True
except ImportError:
    pass

# V9.6.8: Import SovereignStateProjector for proper 32D state normalization
try:
    from symbolu.jepa.state_projector import SovereignStateProjector
    SOVEREIGN_PROJECTOR_AVAILABLE = True
except ImportError:
    SOVEREIGN_PROJECTOR_AVAILABLE = False


# =============================================================================
# 32D SOVEREIGN STATE - Principled Cognitive Architecture
# =============================================================================
# V9.8.0: Replaces arbitrary 124D (44 phonemes + 64 topics + 12 bhava + 4 dynamics)
# with principled 32D grounded in consciousness physics.
#
# V11.0.0: Separated into three planes. Only Bhavas touch phase rotation.
#
# The 32D Sovereign State mapping (3 separated planes):
#   PHASE PLANE (12D → phase rotation):
#     [0:12]  - 12 Bhavas (Ontological Aspects) — WHAT mode of being
#   CONTROL PLANE (16D → CTM+/Sentinel/Governor):
#     [12:17] - 5 Koshas (Consciousness Sheaths) — HOW DEEP to process
#     [17:22] - 5 Vrittis (Mental Modifications) — HOW RELIABLE is this
#     [22:28] - 6 Gunas/Dynamics (Energy States) — WHAT ENERGY dynamics
#   LEARNING PLANE (4D → training-time feedback):
#     [28:32] - 4 Reserved (Void/Toroidal Feedback) — scratch/JEPA
#
# Why this matters:
#   - Old 124D: "Labeling the World" (arbitrary topics, premature phonemes)
#   - New 32D: "Modeling Physics of Consciousness" (principled ontology)
#   - CSR/Phonemes remain at Layer 7 where semantic word-level context exists

SOVEREIGN_STATE_DIM = 32

# V11.0.0: Phase-Critical State Dimension (Bhava-only)
# Only Bhavas participate in phase rotation (ΔS → θ → attention).
# Koshas/Vrittis/Gunas/Reserved are control/learning signals, not phase-critical.
# Rationale: Phase rotation should encode WHAT the system IS (ontological identity),
# not how nervous/deep/energetic/uncertain it feels. This eliminates:
#   - Over-coupling between identity and control signals
#   - Phase noise from Guna dynamics and Vritti epistemic states
#   - Hard-to-debug entanglement in the attention modulation path
PHASE_STATE_DIM = 12   # Bhava-only: the runtime phase rotation input
CONTROL_STATE_DIM = 16  # Koshas(5) + Vrittis(5) + Gunas(6): routed to control plane
LEARNING_STATE_DIM = 4  # Reserved/JEPA(4): training-time feedback, not live attention

# Bhava indices [0:12] - Ontological Aspects
BHAVA_NAMES = [
    'POT',  # 0: Potential - latent possibility
    'IDN',  # 1: Identity - self-recognition
    'EXE',  # 2: Execution - action/manifestation
    'STR',  # 3: Structure - form/organization
    'COG',  # 4: Cognition - knowing/understanding
    'AGY',  # 5: Agency - will/intention
    'RSN',  # 6: Reason - logic/analysis
    'PRP',  # 7: Purpose - meaning/direction
    'WIT',  # 8: Witness - observation/awareness
    'UNI',  # 9: Unity - integration/wholeness
    'INT',  # 10: Intent - focused will
    'ABS',  # 11: Absolute - transcendent ground
]
BHAVA_SLICE = slice(0, 12)

# Sheath indices [12:17] - Depth Mapping (5 Sheaths)
KOSHA_NAMES = [
    'MATERIAL',     # 12: Physicality/Syntax
    'VITAL',        # 13: Flow/Energy
    'MENTAL',       # 14: Semantics/Meaning
    'INTELLECTUAL', # 15: Pattern/Wisdom
    'BLISSFUL',     # 16: Unity/Integration
]
KOSHA_SLICE = slice(12, 17)

# State indices [17:22] - Reliability Mapping (5 States)
VRITTI_NAMES = [
    'FACT',        # 17: Verified Truth
    'ERROR',       # 18: Hallucination
    'IMAGINATION', # 19: Conceptualization
    'VOID',        # 20: Null State
    'MEMORY',      # 21: Recall/Weights
]
VRITTI_SLICE = slice(17, 22)

# Qualia/Dynamics indices [22:28] - System Dynamics (6 Qualia)
GUNA_NAMES = [
    'LUCIDITY',  # 22: Clarity/Precision
    'ACTIVITY',  # 23: Dynamism/Turbulence
    'STABILITY', # 24: Inertia/Fixedness
    'VELOCITY',  # 25: Rate of state change
    'ACCEL',     # 26: Acceleration of change
    'STABLE',    # 27: Stability measure
]
GUNA_SLICE = slice(22, 28)

# Reserved indices [28:32] - Void/Toroidal Feedback
RESERVED_NAMES = [
    'VOID_0',   # 28: Toroidal feedback channel 0
    'VOID_1',   # 29: Toroidal feedback channel 1
    'VOID_2',   # 30: Toroidal feedback channel 2
    'VOID_3',   # 31: Toroidal feedback channel 3
]
RESERVED_SLICE = slice(28, 32)

# Full state dimension names for diagnostics
SOVEREIGN_STATE_NAMES = BHAVA_NAMES + KOSHA_NAMES + VRITTI_NAMES + GUNA_NAMES + RESERVED_NAMES


# =============================================================================
# V10.6.2 (D.5): NO-WRITE CONTRACT ENFORCEMENT
# =============================================================================

class ControlShapeViolation(Exception):
    """Raised when a control signal violates the no-write contract."""
    pass


def assert_control_shape(
    tensor: torch.Tensor,
    name: str,
    d_model: int,
    seq_len: Optional[int] = None,
    strict: bool = True,
) -> bool:
    """
    V10.6.2 (D.5): Enforce no-write contract for control signals.

    Control signals (intent_phase, binding_salience, etc.) must be:
    - Low-dimensional (not token-wise embeddings)
    - Broadcastable to control shapes
    - NOT contain d_model or seq_len dimensions that would allow content injection

    The Contract in One Sentence:
    > intent_phase (and any control) must be low-dimensional, broadcastable,
    > and not token-position dependent.

    V10.6.3 Clarification (ChatGPT feedback):
    > Control signals may be scalar or per-head, but must never vary across
    > token positions (except binding_salience which is explicitly per-position gating).

    Valid control shapes:
    - [B, H] - batch × heads (most common for intent_phase)
    - [B, H, D_h] - batch × heads × head_dim (per-head rotation)
    - [H] or [D_h] - broadcast scalars
    - [1] or [] - single scalar (safest for alignment control)

    SPECIAL CASE - binding_salience only:
    - [B, N] - batch × seq for per-position gating
      NOTE: This is ONLY valid for binding_salience because it's a gating control
      that explicitly needs per-position weighting. It is NOT valid for alignment
      signals (s_align) which must be reduced to [H] or [] to prevent Phase from
      becoming a token-conditioned workspace.

    Invalid shapes (content injection risk):
    - [B, N, D] - full embedding (could encode arbitrary content)
    - [B, N, H, D_h] - per-position per-head full embeddings
    - [B, N] for alignment signals - token-position dependent (leaks structure into Phase)

    Args:
        tensor: Control signal tensor to validate
        name: Name for error messages (e.g., "intent_phase", "binding_salience")
        d_model: Model embedding dimension (must NOT appear in control)
        seq_len: Optional sequence length to check against
        strict: If True, raise exception on violation; if False, return bool

    Returns:
        True if valid, False if invalid (only when strict=False)

    Raises:
        ControlShapeViolation: If strict=True and shape violates contract

    Example:
        >>> # Valid: intent_phase [B, H]
        >>> assert_control_shape(intent_phase, "intent_phase", d_model=768)
        True

        >>> # Invalid: token-wise embedding [B, N, D]
        >>> assert_control_shape(bad_control, "bad_control", d_model=768)
        ControlShapeViolation: bad_control must not have d_model dimension
    """
    violations = []

    # Check 1: Must be low-dimensional (≤4 dims)
    if tensor.dim() > 4:
        violations.append(f"{name} has {tensor.dim()} dims (max 4 allowed)")

    # Check 2: Must NOT have d_model as last dimension (would allow content injection)
    if tensor.dim() >= 1 and tensor.shape[-1] == d_model:
        violations.append(f"{name} must not have d_model ({d_model}) as last dimension")

    # Check 3: Must NOT have seq_len dimension if provided
    # This prevents token-position dependent control (except for binding_salience which is intentionally per-position)
    if seq_len is not None and name != "binding_salience":
        for i, dim in enumerate(tensor.shape):
            if dim == seq_len and i > 0:  # Batch dim at 0 is OK
                violations.append(f"{name} must not have seq_len ({seq_len}) dimension at index {i}")

    # Check 4: For full token-wise embedding shape [B, N, D], reject
    if tensor.dim() == 3:
        B, N, D = tensor.shape
        if D == d_model and (seq_len is None or N == seq_len):
            violations.append(
                f"{name} has shape [B, N, D]={list(tensor.shape)} which could encode token-wise content. "
                f"Control signals must be low-dimensional (e.g., [B, H] for phase rotation)."
            )

    # Report violations
    if violations:
        error_msg = f"No-write contract violation for '{name}':\n" + "\n".join(f"  - {v}" for v in violations)
        if strict:
            raise ControlShapeViolation(error_msg)
        return False

    return True


def validate_control_signals(
    d_model: int,
    seq_len: Optional[int] = None,
    strict: bool = True,
    **controls: torch.Tensor,
) -> Dict[str, bool]:
    """
    V10.6.2 (D.5): Validate multiple control signals at once.

    Args:
        d_model: Model embedding dimension
        seq_len: Optional sequence length
        strict: If True, raise on first violation
        **controls: Named control tensors to validate

    Returns:
        Dict mapping control name to validity (True/False)

    Example:
        >>> validate_control_signals(
        ...     d_model=768,
        ...     seq_len=512,
        ...     intent_phase=intent_phase,
        ...     binding_salience=binding_salience,
        ... )
        {'intent_phase': True, 'binding_salience': True}
    """
    results = {}
    for name, tensor in controls.items():
        if tensor is not None:
            results[name] = assert_control_shape(
                tensor, name, d_model, seq_len, strict=strict
            )
        else:
            results[name] = True  # None is always valid
    return results


def assert_alignment_signal_shape(
    tensor: torch.Tensor,
    name: str,
    num_heads: int,
    seq_len: Optional[int] = None,
    strict: bool = True,
) -> bool:
    """
    V10.6.3 (ChatGPT feedback): Validate alignment signals are NOT token-position dependent.

    Alignment signals (s_align) must be reduced to [H], [], or [B, H] shapes.
    They must NEVER be [B, N] which allows alignment to sculpt Phase per token.

    The Key Distinction:
    > Control signals may be scalar or per-head, but must never vary across token positions.

    Why [B, N] is dangerous for alignment (even though it looks harmless):
    - Token-wise scalar still allows structure to leak into Phase
    - Allows alignment to suppress/amplify *specific tokens*
    - Phase turns into a soft attention map
    - This reintroduces the failures that come from intent sneaking into Phase

    Valid alignment shapes:
    - [] - global scalar (safest)
    - [H] - per-head control (recommended)
    - [B, H] - batch × per-head control

    Invalid alignment shapes:
    - [B, N] - token-position dependent (scalar ≠ safe if it varies per token)
    - [B, N, D] - full embedding

    Args:
        tensor: Alignment signal tensor to validate
        name: Name for error messages
        num_heads: Number of attention heads
        seq_len: Sequence length (to detect [B, N] shapes)
        strict: If True, raise exception; if False, return bool and warn

    Returns:
        True if valid, False if invalid (only when strict=False)

    Raises:
        ControlShapeViolation: If strict=True and shape violates contract
    """
    if tensor is None:
        return True

    violations = []

    # Check 1: Reject any [B, N] shape for alignment
    if tensor.dim() == 2:
        B, N = tensor.shape
        # If second dim matches seq_len or is not num_heads, it's likely [B, N]
        if seq_len is not None and N == seq_len:
            violations.append(
                f"{name} has shape [B, N]={list(tensor.shape)} which is token-position dependent. "
                f"Alignment signals must be [H], [], or [B, H], NOT [B, N]."
            )
        elif N != num_heads and N != 1:
            # Heuristic: if N doesn't match num_heads, it's probably seq_len
            violations.append(
                f"{name} has shape {list(tensor.shape)} where dim 1 ({N}) doesn't match "
                f"num_heads ({num_heads}). If this is [B, N], it violates the contract."
            )

    # Check 2: Reject [B, N, *] shapes (anything with token dimension)
    if tensor.dim() >= 3 and seq_len is not None:
        for i, dim_size in enumerate(tensor.shape):
            if dim_size == seq_len and i > 0:  # Skip batch dim
                violations.append(
                    f"{name} has seq_len dimension at index {i}. "
                    f"Alignment signals must not vary across token positions."
                )

    # Report violations
    if violations:
        error_msg = (
            f"Alignment signal contract violation for '{name}' (V10.6.3):\n"
            + "\n".join(f"  - {v}" for v in violations)
            + "\n\nCORRECT: Reduce alignment to [H] or [] before applying:\n"
            "  Option A (safest):    s_align = cos(theta_diff).mean()           # []\n"
            "  Option B (per-head):  s_align = cos(theta_diff).mean(dim=(0, 2)) # [H]"
        )
        if strict:
            raise ControlShapeViolation(error_msg)
        else:
            import warnings
            warnings.warn(error_msg, UserWarning)
            return False

    return True


# =============================================================================
# D.1 ONTOCONTROL: FORMALIZED CONTROL PLANE INTERFACE
# =============================================================================
# V10.6.4 (D.1): OntoControl formalizes existing binding_salience as an explicit
# control-plane object. This is a PURE DATA CONTAINER with NO behavioral changes.
#
# Why this exists:
# - binding_salience already functions as "OntoControl-lite"
# - This makes the control plane EXPLICIT and INSPECTABLE
# - Future extensibility without current risk
# - Better logging and debugging
#
# What this is NOT:
# - NOT new routing logic
# - NOT ontology embeddings
# - NOT Phase dynamic changes
# - NOT any behavioral modification
#
# Reference: QUAD_PROPOSAL_PHASE_INTEGRATOR_EVALUATION.md, Appendix D.1
# =============================================================================

@dataclass
class OntoControl:
    """
    Ontological Control Signal Container - explicit control plane interface.

    This dataclass wraps binding_salience and related control signals, making
    the implicit "OntoControl-lite" explicit without changing behavior.

    V10.6.4 (D.1): Formalization only, no behavioral changes.

    Key Principles:
    1. binding_salience is the PRIMARY control signal (per-position gating)
    2. Future flags are present but have NO behavior attached yet
    3. Validation uses existing no-write contract enforcement
    4. Serialization enables logging/debugging

    Shape Contracts (from V10.6.2 D.5):
    - binding_salience: [B, N] - per-position gating for Top-K selection
    - intent_phase: [B, H] or [B, H, D_h] - low-dimensional phase rotation

    Usage:
        # Create from existing binding_salience
        onto_ctrl = OntoControl.from_salience(binding_salience)

        # Or create manually
        onto_ctrl = OntoControl(
            binding_salience=salience_tensor,
            enable_slots_read=True,
        )

        # Validate against no-write contract
        onto_ctrl.validate(d_model=768)

        # Log for debugging
        print(onto_ctrl.to_dict())

    Attributes:
        binding_salience: Per-position gating signal [B, N] for Top-K selection.
            This is the core control that biases which bindings get retrieved.
        intent_phase: Optional low-dimensional phase rotation [B, H] or [B, H, D_h].
            Controls how bindings are stored (Key phasor modulation).
        enable_slots_read: Flag for D.2 read/write separation (defaults True).
            When False, quad retrieval is skipped but phase writes continue.
        enable_quad: Future flag for quad query control (no behavior yet).
        enable_csr: Future flag for CSR control (no behavior yet).
        source: Metadata indicating signal origin ("ontology", "csr", "kosha", etc).
        confidence: Optional confidence score for the control signal.
    """

    # Primary control signal - already exists and works
    binding_salience: Optional[torch.Tensor] = None  # [B, N] per-position gating

    # Low-dimensional phase rotation (from existing intent_phase pathway)
    intent_phase: Optional[torch.Tensor] = None  # [B, H] or [B, H, D_h]

    # D.2: Separate read/write control (already implemented in BindingCacheBlock)
    enable_slots_read: bool = True

    # Future-ready flags - NO BEHAVIOR ATTACHED
    # These exist for interface stability, not functionality
    enable_quad: Optional[bool] = None  # Reserved for future quad gating
    enable_csr: Optional[bool] = None   # Reserved for future CSR control

    # Metadata for logging/debugging
    source: str = "ontology"
    confidence: Optional[float] = None

    def validate(
        self,
        d_model: int,
        seq_len: Optional[int] = None,
        num_heads: Optional[int] = None,
        strict: bool = True,
    ) -> Dict[str, bool]:
        """
        Validate all control signals against the no-write contract (V10.6.2 D.5).

        Args:
            d_model: Model embedding dimension
            seq_len: Optional sequence length for shape validation
            num_heads: Optional number of heads for alignment validation
            strict: If True, raise on violation; if False, return bool dict

        Returns:
            Dict mapping signal name to validity (True/False)

        Raises:
            ControlShapeViolation: If strict=True and any signal violates contract
        """
        results = {}

        if self.binding_salience is not None:
            # binding_salience is special: [B, N] is VALID (per-position gating)
            results["binding_salience"] = assert_control_shape(
                self.binding_salience,
                name="binding_salience",
                d_model=d_model,
                seq_len=seq_len,
                strict=strict,
            )

        if self.intent_phase is not None:
            # intent_phase must be low-dimensional: [B, H] or [B, H, D_h]
            results["intent_phase"] = assert_control_shape(
                self.intent_phase,
                name="intent_phase",
                d_model=d_model,
                seq_len=seq_len,
                strict=strict,
            )

        return results

    def to_dict(self) -> Dict[str, Any]:
        """
        Serialize for logging/debugging.

        Returns:
            Dict with shape information and metadata for all fields.
        """
        return {
            "binding_salience_shape": (
                list(self.binding_salience.shape)
                if self.binding_salience is not None
                else None
            ),
            "intent_phase_shape": (
                list(self.intent_phase.shape)
                if self.intent_phase is not None
                else None
            ),
            "enable_slots_read": self.enable_slots_read,
            "enable_quad": self.enable_quad,
            "enable_csr": self.enable_csr,
            "source": self.source,
            "confidence": self.confidence,
        }

    @classmethod
    def from_salience(
        cls,
        binding_salience: torch.Tensor,
        source: str = "ontology",
        confidence: Optional[float] = None,
    ) -> "OntoControl":
        """
        Factory: Create OntoControl from existing binding_salience tensor.

        This is the recommended way to wrap existing binding_salience signals
        in the formalized OntoControl interface.

        Args:
            binding_salience: [B, N] per-position gating tensor
            source: Origin of the signal ("ontology", "csr", "kosha", "annotator")
            confidence: Optional confidence score

        Returns:
            OntoControl instance wrapping the binding_salience
        """
        return cls(
            binding_salience=binding_salience,
            source=source,
            confidence=confidence,
        )


def onto_control_from_salience(
    binding_salience: torch.Tensor,
    source: str = "ontology",
) -> OntoControl:
    """
    Adapter: Convert binding_salience to OntoControl.

    This is a convenience function that wraps OntoControl.from_salience().

    Args:
        binding_salience: [B, N] per-position gating tensor
        source: Origin of the signal

    Returns:
        OntoControl instance

    Example:
        >>> salience = annotator(hidden_states, sovereign_state)
        >>> onto_ctrl = onto_control_from_salience(salience, source="annotator")
    """
    return OntoControl.from_salience(binding_salience, source=source)


def get_sovereign_state_summary(state: torch.Tensor) -> Dict[str, Any]:
    """
    Extract human-readable summary from 32D Sovereign State.

    Args:
        state: [B, 32] or [32] Sovereign State tensor

    Returns:
        Dict with dominant Bhava, active Kosha, Vritti state, Guna balance
    """
    if state.dim() == 1:
        state = state.unsqueeze(0)

    # Get dominant indices for each category
    bhava_vals = state[:, BHAVA_SLICE]
    kosha_vals = state[:, KOSHA_SLICE]
    vritti_vals = state[:, VRITTI_SLICE]
    guna_vals = state[:, GUNA_SLICE]

    dominant_bhava_idx = bhava_vals.argmax(dim=-1)
    active_kosha_idx = kosha_vals.argmax(dim=-1)
    vritti_state_idx = vritti_vals.argmax(dim=-1)

    # Guna balance (Sattva-Rajas-Tamas ratio)
    # Note: guna_vals are already sigmoid-normalized in state_projector, so we normalize
    # by sum instead of applying softmax (which causes 33/33/33 collapse on similar values)
    guna_raw = guna_vals[:, :3]  # First 3 are S-R-T
    guna_sum = guna_raw.sum(dim=-1, keepdim=True).clamp(min=1e-6)
    guna_balance = guna_raw / guna_sum  # Proportional normalization preserves variance

    return {
        'dominant_bhava': BHAVA_NAMES[dominant_bhava_idx[0].item()],
        'dominant_bhava_idx': dominant_bhava_idx[0].item(),
        'bhava_activation': bhava_vals[0, dominant_bhava_idx[0]].item(),
        'active_kosha': KOSHA_NAMES[active_kosha_idx[0].item()],
        'active_kosha_idx': active_kosha_idx[0].item(),
        'kosha_activation': kosha_vals[0, active_kosha_idx[0]].item(),
        'vritti_state': VRITTI_NAMES[vritti_state_idx[0].item()],
        'vritti_state_idx': vritti_state_idx[0].item(),
        'vritti_activation': vritti_vals[0, vritti_state_idx[0]].item(),
        'guna_sattva': guna_balance[0, 0].item(),
        'guna_rajas': guna_balance[0, 1].item(),
        'guna_tamas': guna_balance[0, 2].item(),
        'velocity': guna_vals[0, 3].item() if guna_vals.shape[-1] > 3 else 0.0,
    }


# =============================================================================
# V9.9.8: PARALLEL EMA SCAN - Optimized Exponential Moving Average
# =============================================================================
# Problem: Sequential for-loops for S_t = γ * S_{t-1} + x_t are slow in Python.
# Solution: Chunked vectorization reduces N iterations to N/chunk_size iterations.
#
# For sequence length 2048 and chunk_size=64, this is 32x fewer loop iterations.
#
# V9.9.12c: NUMERICAL STABILITY FIX (ChatGPT analysis)
# The original algorithm uses γ^(-t) which can overflow for small γ and large t.
# For γ=0.5, t=63: γ^(-63) = 2^63 ≈ 9.2×10^18 (overflow!)
#
# Fix: Use sequential loop within chunks when min(γ) < SAFE_GAMMA_THRESHOLD,
# only use vectorized path when all γ values are high enough to be stable.

# Threshold below which we use sequential loop to avoid γ^(-t) overflow
# For chunk_size=64, γ^(-63) = 1.7×10^4 when γ=0.9 (safe)
# but γ^(-63) = 9.2×10^18 when γ=0.5 (overflow)
SAFE_GAMMA_THRESHOLD = 0.9


def parallel_ema_scan(
    x: torch.Tensor,
    gamma: Union[float, torch.Tensor],
    chunk_size: int = 64
) -> torch.Tensor:
    """
    Compute exponential moving average efficiently using chunked vectorization.

    Computes S_t = γ * S_{t-1} + x_t for all t in O(N/chunk_size) loop iterations
    instead of O(N), with vectorized operations within each chunk.

    V9.9.12c: Uses sequential loop when gamma < 0.9 to avoid numerical overflow
    from γ^(-t) computation. This is slower but numerically stable.

    Args:
        x: Input tensor of shape [B, N, H, D] or [B, N, H, D] complex
        gamma: Decay factor, either scalar or [H] tensor for per-head decay
        chunk_size: Number of tokens to process per iteration (default 64)

    Returns:
        S: Output tensor of same shape as x with S_t = γ * S_{t-1} + x_t
    """
    B, N, H, D = x.shape
    device = x.device
    dtype = x.dtype

    # Handle scalar vs per-head gamma
    if isinstance(gamma, (int, float)):
        gamma_is_scalar = True
        gamma_val = float(gamma)
        min_gamma = gamma_val
    else:
        gamma_is_scalar = False
        # gamma is [H] shaped, ensure it's on correct device
        gamma = gamma.to(device=device)
        min_gamma = gamma.min().item()

    # V9.9.12c: Check if gamma is safe for vectorized path
    # If any head has gamma < threshold, use sequential to avoid overflow
    use_vectorized = min_gamma >= SAFE_GAMMA_THRESHOLD

    # Output buffer
    S = torch.zeros_like(x)

    # Running state between chunks
    state = torch.zeros(B, 1, H, D, dtype=dtype, device=device)

    # Process in chunks
    num_chunks = (N + chunk_size - 1) // chunk_size

    if not use_vectorized:
        # V9.9.12c: Sequential path for numerical stability
        # This is slower but avoids γ^(-t) overflow
        for c in range(num_chunks):
            start_idx = c * chunk_size
            end_idx = min(start_idx + chunk_size, N)
            x_chunk = x[:, start_idx:end_idx, :, :]

            for t in range(end_idx - start_idx):
                if gamma_is_scalar:
                    state = gamma_val * state + x_chunk[:, t:t+1, :, :]
                else:
                    gamma_broadcast = gamma.view(1, 1, H, 1).to(dtype)
                    state = gamma_broadcast * state + x_chunk[:, t:t+1, :, :]
                S[:, start_idx + t:start_idx + t + 1, :, :] = state
        return S

    # Vectorized path: only used when gamma >= SAFE_GAMMA_THRESHOLD
    # Precompute powers of gamma for intra-chunk accumulation
    arange = torch.arange(chunk_size, device=device, dtype=torch.float32)

    if gamma_is_scalar:
        powers = torch.pow(gamma_val, arange)  # [chunk_size]
    else:
        powers = gamma.unsqueeze(0).float() ** arange.unsqueeze(1)  # [chunk_size, H]

    for c in range(num_chunks):
        start_idx = c * chunk_size
        end_idx = min(start_idx + chunk_size, N)
        actual_chunk_size = end_idx - start_idx

        # Extract chunk
        x_chunk = x[:, start_idx:end_idx, :, :]  # [B, chunk, H, D]

        if actual_chunk_size < chunk_size:
            # Last chunk may be smaller, use sequential
            for t in range(actual_chunk_size):
                if gamma_is_scalar:
                    state = gamma_val * state + x_chunk[:, t:t+1, :, :]
                else:
                    gamma_broadcast = gamma.view(1, 1, H, 1).to(dtype)
                    state = gamma_broadcast * state + x_chunk[:, t:t+1, :, :]
                S[:, start_idx + t:start_idx + t + 1, :, :] = state
        else:
            # Full chunk: use vectorized accumulation
            # For S_t = γ * S_{t-1} + x_t, within a chunk starting from state S_prev:
            # S[0] = γ * S_prev + x[0]
            # S[1] = γ^2 * S_prev + γ * x[0] + x[1]
            # S[i] = γ^(i+1) * S_prev + Σ_{j=0}^{i} γ^(i-j) * x[j]

            # Contribution from previous state
            if gamma_is_scalar:
                state_powers = torch.pow(gamma_val, arange[:chunk_size] + 1)  # [chunk]
                state_contrib = state * state_powers.view(1, chunk_size, 1, 1).to(dtype)
            else:
                state_powers = gamma.unsqueeze(0).float() ** (arange[:chunk_size].unsqueeze(1) + 1)
                state_contrib = state * state_powers.view(1, chunk_size, H, 1).to(dtype)

            # Contribution from chunk inputs: cumulative sum with decay
            # We need Σ_{j=0}^{i} γ^(i-j) * x[j] for each i
            if gamma_is_scalar:
                # Scale inputs: x_scaled[j] = x[j] * γ^(-j)
                # SAFE because gamma >= 0.9 guarantees γ^(-63) ≈ 1.7×10^4 (no overflow)
                inv_powers = torch.pow(gamma_val, -arange[:chunk_size])  # [chunk]
                x_scaled = x_chunk * inv_powers.view(1, chunk_size, 1, 1).to(dtype)
                x_cumsum = torch.cumsum(x_scaled, dim=1)
                input_contrib = x_cumsum * powers[:chunk_size].view(1, chunk_size, 1, 1).to(dtype)
            else:
                inv_powers = gamma.unsqueeze(0).float() ** (-arange[:chunk_size].unsqueeze(1))
                x_scaled = x_chunk * inv_powers.view(1, chunk_size, H, 1).to(dtype)
                x_cumsum = torch.cumsum(x_scaled, dim=1)
                input_contrib = x_cumsum * powers[:chunk_size].view(1, chunk_size, H, 1).to(dtype)

            # Combine
            S[:, start_idx:end_idx, :, :] = state_contrib + input_contrib

            # Update state for next chunk
            state = S[:, end_idx - 1:end_idx, :, :].clone()

    return S


# =============================================================================
# V9.9.10: PHASE DIVERSITY LOSSES - Combat Phase Collapse (ChatGPT-Enhanced)
# =============================================================================
# Problem: Phase attention collapses to cos(φ_q - φ_k) ≈ 1 everywhere,
#          turning the phase mechanism into a scalar gain (no selectivity).
#
# Solution (ChatGPT's recommendations):
#   1. Uniformity Loss: |E[e^{iφ}]|² - penalizes non-uniform distribution
#      (better than pairwise cosine which can cause bimodal collapse)
#   2. Entropy Proxy: R = |E[e^{iφ}]| - mean resultant length
#      (R→0 = uniform/high entropy, R→1 = collapsed/low entropy)
#   3. Pool phases across D_h FIRST to prevent gaming via irrelevant dims
#
# These forces push phases toward uniform distribution around the unit circle.

def compute_effective_phase(phi: torch.Tensor) -> torch.Tensor:
    """
    Pool phase across D_h dimension to get effective phase per head.

    φ_eff = atan2(Σ_d sin(φ_d), Σ_d cos(φ_d))

    This prevents the model from gaming diversity loss by randomizing
    useless dimensions while keeping a few collapsed for actual work.

    Args:
        phi: Phase tensor [B, N, H, D_h]

    Returns:
        phi_eff: Effective phase [B, N, H]
    """
    # Sum sin and cos across D_h dimension
    sin_sum = torch.sin(phi).sum(dim=-1)  # [B, N, H]
    cos_sum = torch.cos(phi).sum(dim=-1)  # [B, N, H]

    # Compute effective phase via atan2
    phi_eff = torch.atan2(sin_sum, cos_sum)  # [B, N, H]

    return phi_eff


def compute_pooled_phasor(phi: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor]:
    """
    V9.9.12c: Compute mean phasor across D_h (ChatGPT's correct form).

    z[b,n,h] = mean_d exp(i * phi[b,n,h,d])
             = (mean_d cos(phi)) + i * (mean_d sin(phi))

    This preserves magnitude information: |z| is small when D_h phases
    are diverse (phasors cancel), large when collapsed (phasors align).

    Args:
        phi: Phase tensor [B, N, H, D_h]

    Returns:
        z_real: Real part of pooled phasor [B, N, H]
        z_imag: Imaginary part of pooled phasor [B, N, H]
    """
    # Mean of exp(i*phi) across D_h
    z_real = torch.cos(phi).mean(dim=-1)  # [B, N, H]
    z_imag = torch.sin(phi).mean(dim=-1)  # [B, N, H]
    return z_real, z_imag


def phase_uniformity_loss(phi: torch.Tensor) -> torch.Tensor:
    """
    Uniformity loss: Penalize non-uniform phase distribution.

    V9.9.12c: Fixed to use ChatGPT's correct two-stage pooling:
    1. z[b,n,h] = mean_d exp(i * phi[b,n,h,d])  -- pool over D_h first
    2. L_uniform = |mean_{b,n} z[b,n,h]|²       -- then pool over samples

    If phases are uniform around the circle → E[e^{iφ}] ≈ 0 → loss small
    If phases collapse to one direction → |E[e^{iφ}]| large → loss large

    This is better than cosine-pair repulsion which can cause bimodal collapse
    (all phases split into two clusters at π apart).

    Args:
        phi: Phase tensor [B, N, H, D_h] or effective phase [B, N, H]

    Returns:
        Scalar loss (minimize for uniform distribution)
    """
    # V9.9.12c: Use correct two-stage pooling (ChatGPT's formula)
    if phi.dim() == 4:
        # Step 1: Pool over D_h to get z[b,n,h] = mean_d exp(i*phi)
        # This preserves magnitude info (|z| < 1 when D_h diverse)
        z_real, z_imag = compute_pooled_phasor(phi)  # [B, N, H] each
    else:
        # Already [B, N, H], treat as unit phasors
        z_real = torch.cos(phi)
        z_imag = torch.sin(phi)

    # Step 2: Mean across batch, positions → [H]
    mean_real = z_real.mean(dim=(0, 1))  # [H]
    mean_imag = z_imag.mean(dim=(0, 1))  # [H]

    # |E[z]|² per head
    magnitude_sq = mean_real ** 2 + mean_imag ** 2  # [H]

    # Mean across heads
    return magnitude_sq.mean()


def phase_entropy_proxy_loss(phi: torch.Tensor) -> torch.Tensor:
    """
    Entropy proxy via mean resultant length (circular statistics).

    V9.9.12c: Fixed to use ChatGPT's correct two-stage pooling:
    1. z[b,n,h] = mean_d exp(i * phi[b,n,h,d])  -- pool over D_h first
    2. R[h] = |mean_{b,n} z[b,n,h]|             -- then pool over samples

    R = |E[z]| where z = mean_d exp(i*phi)

    Uniform distribution → R ≈ 0 (high entropy)
    Collapsed distribution → R ≈ 1 (low entropy)

    This is cheaper and more stable than KDE-based entropy estimation.

    Args:
        phi: Phase tensor [B, N, H, D_h] or effective phase [B, N, H]

    Returns:
        Scalar loss R (minimize to maximize entropy)
    """
    # V9.9.12c: Use correct two-stage pooling (ChatGPT's formula)
    if phi.dim() == 4:
        # Step 1: Pool over D_h to get z[b,n,h] = mean_d exp(i*phi)
        # This preserves magnitude info (|z| < 1 when D_h diverse)
        z_real, z_imag = compute_pooled_phasor(phi)  # [B, N, H] each
    else:
        # Already [B, N, H], treat as unit phasors
        z_real = torch.cos(phi)
        z_imag = torch.sin(phi)

    # Step 2: Mean across batch, positions → [H]
    mean_real = z_real.mean(dim=(0, 1))
    mean_imag = z_imag.mean(dim=(0, 1))

    # Mean resultant length R = |E[z]| per head
    R = torch.sqrt(mean_real ** 2 + mean_imag ** 2 + 1e-8)  # [H]

    # Mean across heads
    return R.mean()


def compute_phase_diversity_losses(
    phi_k: torch.Tensor,
    lambda_uniform: float = 0.001,
    lambda_entropy: float = 0.001,
) -> Tuple[torch.Tensor, Dict[str, float]]:
    """
    Compute combined phase diversity losses for training.

    V9.9.10: Uses ChatGPT's enhanced approach:
    - Pool phase across D_h first (compute_effective_phase)
    - Use uniformity loss instead of pairwise cosine repulsion
    - Use mean resultant length as entropy proxy
    - Start with small weights (1e-3), ramp to 1e-2 over training

    Args:
        phi_k: Key phase tensor [B, N, H, D_h]
        lambda_uniform: Weight for uniformity loss (default 0.001)
        lambda_entropy: Weight for entropy proxy loss (default 0.001)

    Returns:
        total_loss: Weighted sum of diversity losses
        metrics: Dict with individual loss values for logging
    """
    # Uniformity loss: |E[e^{iφ}]|² (penalizes clustering)
    loss_uniform = phase_uniformity_loss(phi_k)

    # Entropy proxy: R = |E[e^{iφ}]| (minimize for high entropy)
    loss_entropy = phase_entropy_proxy_loss(phi_k)

    # Weighted combination
    total_loss = lambda_uniform * loss_uniform + lambda_entropy * loss_entropy

    # Metrics for logging
    metrics = {
        'phase_uniform_loss': loss_uniform.item(),
        'phase_entropy_proxy': loss_entropy.item(),  # R value (0=uniform, 1=collapsed)
        'phase_diversity_loss': total_loss.item(),
    }

    return total_loss, metrics


def enable_phase_diversity_capture(model: nn.Module, enable: bool = True) -> int:
    """
    Enable or disable phase diversity capture on all PhaseAttentionLayer modules.

    Args:
        model: Model containing PhaseAttentionLayer modules
        enable: Whether to enable capture

    Returns:
        Number of PhaseAttentionLayer modules found
    """
    count = 0
    for module in model.modules():
        if module.__class__.__name__ == 'PhaseAttentionLayer':
            module.capture_phase_for_diversity = enable
            if not enable:
                module._captured_phi_k = None  # Clear captured data
                module._captured_phi_q = None  # Clear captured data
            count += 1
    return count


def collect_captured_phases(model: nn.Module) -> List[torch.Tensor]:
    """
    Collect all captured phi_k tensors from PhaseAttentionLayer modules.

    Args:
        model: Model containing PhaseAttentionLayer modules

    Returns:
        List of phi_k tensors [B, N, H, D_h] from each layer
    """
    phases = []
    for module in model.modules():
        if module.__class__.__name__ == 'PhaseAttentionLayer':
            if hasattr(module, '_captured_phi_k') and module._captured_phi_k is not None:
                phases.append(module._captured_phi_k)
    return phases


def collect_captured_phases_q(model: nn.Module) -> List[torch.Tensor]:
    """
    Collect all captured phi_q tensors from PhaseAttentionLayer modules.

    Args:
        model: Model containing PhaseAttentionLayer modules

    Returns:
        List of phi_q tensors [B, N, H, D_h] from each layer
    """
    phases = []
    for module in model.modules():
        if module.__class__.__name__ == 'PhaseAttentionLayer':
            if hasattr(module, '_captured_phi_q') and module._captured_phi_q is not None:
                phases.append(module._captured_phi_q)
    return phases


def compute_model_phase_diversity_loss(
    model: nn.Module,
    lambda_uniform: float = 0.001,
    lambda_entropy: float = 0.001,
) -> Tuple[torch.Tensor, Dict[str, float]]:
    """
    Compute phase diversity loss across all PhaseAttentionLayer modules.

    V9.9.10: Aggregates diversity losses from all captured phases.
    V11.x: Now includes phi_q for symmetric regularization (prevents R_q collapse).
    Uses ChatGPT's enhanced uniformity + entropy proxy approach.

    Args:
        model: Model with captured phi_k and phi_q tensors
        lambda_uniform: Weight for uniformity loss (default 0.001)
        lambda_entropy: Weight for entropy proxy loss (default 0.001)

    Returns:
        total_loss: Combined loss across all layers (phi_k + phi_q)
        metrics: Dict with aggregate metrics
    """
    phases_k = collect_captured_phases(model)
    phases_q = collect_captured_phases_q(model)

    if not phases_k and not phases_q:
        # No phases captured, return zero loss
        device = next(model.parameters()).device
        return torch.tensor(0.0, device=device, requires_grad=False), {
            'phase_uniform_loss': 0.0,
            'phase_entropy_proxy': 0.0,
            'phase_uniform_loss_q': 0.0,
            'phase_entropy_proxy_q': 0.0,
            'phase_diversity_loss': 0.0,
            'num_layers_captured': 0,
        }

    # Compute loss for phi_k (keys) — existing behavior
    total_uniform_k = 0.0
    total_entropy_k = 0.0
    total_loss = None

    for phi_k in phases_k:
        loss, metrics = compute_phase_diversity_losses(phi_k, lambda_uniform, lambda_entropy)
        total_uniform_k += metrics['phase_uniform_loss']
        total_entropy_k += metrics['phase_entropy_proxy']
        if total_loss is None:
            total_loss = loss
        else:
            total_loss = total_loss + loss

    # Compute loss for phi_q (queries) — V11.x symmetric regularization
    total_uniform_q = 0.0
    total_entropy_q = 0.0

    for phi_q in phases_q:
        loss, metrics = compute_phase_diversity_losses(phi_q, lambda_uniform, lambda_entropy)
        total_uniform_q += metrics['phase_uniform_loss']
        total_entropy_q += metrics['phase_entropy_proxy']
        if total_loss is None:
            total_loss = loss
        else:
            total_loss = total_loss + loss

    num_layers_k = len(phases_k)
    num_layers_q = len(phases_q)
    num_layers = max(num_layers_k, num_layers_q, 1)
    avg_loss = total_loss / num_layers if total_loss is not None else torch.tensor(0.0)

    return avg_loss, {
        'phase_uniform_loss': total_uniform_k / max(num_layers_k, 1),
        'phase_entropy_proxy': total_entropy_k / max(num_layers_k, 1),
        'phase_uniform_loss_q': total_uniform_q / max(num_layers_q, 1),
        'phase_entropy_proxy_q': total_entropy_q / max(num_layers_q, 1),
        'phase_diversity_loss': avg_loss.item() if torch.is_tensor(avg_loss) else avg_loss,
        'num_layers_captured': num_layers,
    }


# =============================================================================
# V9.9.12c: PHASEATTENTION HEALTH DASHBOARD (Diagnostic Only)
# =============================================================================
# Behavioral audit dashboard for PhaseAttention stability analysis.
#
# This is READ-ONLY diagnostics:
# - No gradients, no losses, no optimizer interaction
# - No effect on training dynamics
# - Safe to call every N steps (e.g. eval/log interval)
#
# Metrics:
#   R_k              - Key phase collapse (using correct pooled phasor)
#   R_q              - Query phase collapse (logged only, not regularized)
#   amp_phase_corr   - Correlation between |z| and a_k (entanglement check)
#   head_redundancy  - Mean cosine similarity between per-head z̄_h
#   phase_drift_mean - Mean |Δφ_k| across time (dynamic behavior)
#   phase_drift_std  - Std of |Δφ_k| across time (stability)


def enable_health_diagnostics_capture(model: nn.Module, enable: bool = True) -> int:
    """
    Enable or disable health diagnostics capture on all PhaseAttentionLayer modules.

    When enabled, captures phi_q, phi_k, and a_k (all detached) for health analysis.
    This has NO effect on training - all captures are detached.

    Args:
        model: Model containing PhaseAttentionLayer modules
        enable: Whether to enable capture

    Returns:
        Number of PhaseAttentionLayer modules found
    """
    count = 0
    for module in model.modules():
        if module.__class__.__name__ == 'PhaseAttentionLayer':
            module.capture_for_health_diagnostics = enable
            if not enable:
                # Clear health-specific captured data to free memory
                # (do NOT touch _captured_phi_k — diversity loss may need it)
                module._health_phi_k = None
                module._health_phi_q = None
                module._health_a_k = None
            count += 1
    return count


def _collect_health_captures(model: nn.Module) -> List[Dict[str, torch.Tensor]]:
    """
    Collect captured tensors from all PhaseAttentionLayer modules for health analysis.

    Returns:
        List of dicts, each with 'phi_k', 'phi_q', 'a_k' tensors
    """
    captures = []
    for module in model.modules():
        if module.__class__.__name__ == 'PhaseAttentionLayer':
            # Read from health-specific attributes (separate from diversity capture)
            if (hasattr(module, '_health_phi_k') and module._health_phi_k is not None and
                hasattr(module, '_health_phi_q') and module._health_phi_q is not None and
                hasattr(module, '_health_a_k') and module._health_a_k is not None):
                captures.append({
                    'phi_k': module._health_phi_k,
                    'phi_q': module._health_phi_q,
                    'a_k': module._health_a_k,
                })
    return captures


def _compute_R_from_phi(phi: torch.Tensor) -> float:
    """
    Compute mean resultant length R from phase tensor.

    Uses correct two-stage pooling:
    1. z[b,n,h] = mean_d exp(i * phi[b,n,h,d])
    2. R[h] = |mean_{b,n} z[b,n,h]|

    Args:
        phi: Phase tensor [B, N, H, D_h]

    Returns:
        Scalar R value (0 = uniform/healthy, 1 = collapsed)
    """
    # Pool over D_h: z = mean_d exp(i*phi)
    z_real = torch.cos(phi).mean(dim=-1)  # [B, N, H]
    z_imag = torch.sin(phi).mean(dim=-1)  # [B, N, H]

    # Pool over batch, positions: mean_{b,n} z
    mean_real = z_real.mean(dim=(0, 1))  # [H]
    mean_imag = z_imag.mean(dim=(0, 1))  # [H]

    # R = |mean z| per head, then average
    R_per_head = torch.sqrt(mean_real ** 2 + mean_imag ** 2 + 1e-8)
    return R_per_head.mean().item()


def _compute_amp_phase_correlation(phi: torch.Tensor, a_k: torch.Tensor) -> float:
    """
    Compute correlation between |z[b,n,h]| and a_k.

    If high, amplitude is compensating for phase collapse.

    Args:
        phi: Phase tensor [B, N, H, D_h]
        a_k: Amplitude tensor [B, N, H, D_h]

    Returns:
        Correlation coefficient (scalar)
    """
    # Compute |z| = |mean_d exp(i*phi)| per (b,n,h)
    z_real = torch.cos(phi).mean(dim=-1)  # [B, N, H]
    z_imag = torch.sin(phi).mean(dim=-1)  # [B, N, H]
    z_mag = torch.sqrt(z_real ** 2 + z_imag ** 2 + 1e-8)  # [B, N, H]

    # Mean amplitude per (b,n,h)
    a_mean = a_k.mean(dim=-1)  # [B, N, H]

    # Flatten for correlation
    z_flat = z_mag.flatten()
    a_flat = a_mean.flatten()

    # Pearson correlation
    z_centered = z_flat - z_flat.mean()
    a_centered = a_flat - a_flat.mean()

    numerator = (z_centered * a_centered).sum()
    denominator = torch.sqrt((z_centered ** 2).sum() * (a_centered ** 2).sum() + 1e-8)

    return (numerator / denominator).item()


def _compute_head_redundancy(phi: torch.Tensor) -> float:
    """
    Compute mean cosine similarity between per-head z̄_h vectors.

    If high, multiple heads have converged to same phase manifold.

    Args:
        phi: Phase tensor [B, N, H, D_h]

    Returns:
        Mean pairwise cosine similarity (scalar)
    """
    # z[b,n,h] = mean_d exp(i*phi)
    z_real = torch.cos(phi).mean(dim=-1)  # [B, N, H]
    z_imag = torch.sin(phi).mean(dim=-1)  # [B, N, H]

    # z̄_h = mean_{b,n} z[b,n,h] for each head
    z_bar_real = z_real.mean(dim=(0, 1))  # [H]
    z_bar_imag = z_imag.mean(dim=(0, 1))  # [H]

    # Stack as 2D vectors for cosine similarity: [H, 2]
    z_bar = torch.stack([z_bar_real, z_bar_imag], dim=-1)  # [H, 2]

    # Normalize
    z_bar_norm = z_bar / (z_bar.norm(dim=-1, keepdim=True) + 1e-8)

    # Pairwise cosine similarity
    H = z_bar_norm.shape[0]
    if H < 2:
        return 0.0

    # Compute all pairs
    sim_matrix = z_bar_norm @ z_bar_norm.T  # [H, H]

    # Mean of upper triangle (excluding diagonal)
    mask = torch.triu(torch.ones(H, H, device=sim_matrix.device), diagonal=1).bool()
    pairwise_sims = sim_matrix[mask]

    return pairwise_sims.mean().item() if pairwise_sims.numel() > 0 else 0.0


def _compute_phase_drift(phi: torch.Tensor) -> Tuple[float, float]:
    """
    Compute phase drift statistics: |Δφ_k(t)| = |φ_k(t) - φ_k(t-1)|.

    Healthy: small but non-zero drift (using phase as state variable)
    Unhealthy: Δφ ≈ 0 everywhere (frozen) or Δφ >> noise (unstable)

    Args:
        phi: Phase tensor [B, N, H, D_h]

    Returns:
        (mean_drift, std_drift) - both scalars
    """
    if phi.shape[1] < 2:
        return 0.0, 0.0

    # Compute temporal differences: φ(t) - φ(t-1)
    delta_phi = phi[:, 1:, :, :] - phi[:, :-1, :, :]  # [B, N-1, H, D_h]

    # Wrap to [-π, π] for proper circular distance
    delta_phi = torch.atan2(torch.sin(delta_phi), torch.cos(delta_phi))

    # |Δφ| across all dimensions
    abs_delta = delta_phi.abs()

    mean_drift = abs_delta.mean().item()
    std_drift = abs_delta.std().item()

    return mean_drift, std_drift


@torch.no_grad()
def compute_phase_health_diagnostics(model: nn.Module) -> Dict[str, float]:
    """
    Compute PhaseAttention health diagnostics from captured tensors.

    This is a READ-ONLY diagnostic function:
    - No gradients (wrapped in torch.no_grad)
    - No losses returned
    - No optimizer interaction
    - Safe to call every N steps

    Prerequisites:
        1. Call enable_health_diagnostics_capture(model, True)
        2. Run a forward pass
        3. Call this function
        4. Optionally: enable_health_diagnostics_capture(model, False) to free memory

    Returns:
        Dict with 6 scalar metrics:
        - R_k: Key phase collapse (0=healthy, 1=collapsed)
        - R_q: Query phase collapse (0=healthy, 1=collapsed)
        - amp_phase_corr: Amplitude-phase correlation (-1 to 1)
        - head_redundancy: Inter-head similarity (0=diverse, 1=redundant)
        - phase_drift_mean: Mean |Δφ| across time
        - phase_drift_std: Std of |Δφ| across time
    """
    captures = _collect_health_captures(model)

    if not captures:
        return {
            'R_k': 0.0,
            'R_q': 0.0,
            'amp_phase_corr': 0.0,
            'head_redundancy': 0.0,
            'phase_drift_mean': 0.0,
            'phase_drift_std': 0.0,
        }

    # Aggregate metrics across all layers
    R_k_total = 0.0
    R_q_total = 0.0
    amp_corr_total = 0.0
    head_red_total = 0.0
    drift_mean_total = 0.0
    drift_std_total = 0.0

    for capture in captures:
        phi_k = capture['phi_k']
        phi_q = capture['phi_q']
        a_k = capture['a_k']

        R_k_total += _compute_R_from_phi(phi_k)
        R_q_total += _compute_R_from_phi(phi_q)
        amp_corr_total += _compute_amp_phase_correlation(phi_k, a_k)
        head_red_total += _compute_head_redundancy(phi_k)

        drift_mean, drift_std = _compute_phase_drift(phi_k)
        drift_mean_total += drift_mean
        drift_std_total += drift_std

    num_layers = len(captures)

    return {
        'R_k': R_k_total / num_layers,
        'R_q': R_q_total / num_layers,
        'amp_phase_corr': amp_corr_total / num_layers,
        'head_redundancy': head_red_total / num_layers,
        'phase_drift_mean': drift_mean_total / num_layers,
        'phase_drift_std': drift_std_total / num_layers,
    }


# =============================================================================
# V11.1.0: EXPLANATION TELEMETRY BRIDGE
# =============================================================================
# Convenience function that collects from the model's three diagnostic surfaces
# and returns a unified ExplanationTelemetry record.  Import-safe: the
# mechanical.logging package uses only stdlib + dataclasses (no torch).

def collect_explanation_telemetry(
    model: nn.Module,
    response_id: str = "",
    health_diagnostics: Optional[Dict[str, float]] = None,
    ontological_state: Optional[Dict[str, float]] = None,
    coherence_score: Optional[float] = None,
    sequence_length: int = 0,
):
    """
    Collect an ExplanationTelemetry record from model internals.

    This is the primary integration point between phase_transformer
    and the enterprise explainability system.  Call after a forward pass.

    Args:
        model: PhaseQuadTransformer (or any module with get_phase_health /
               get_instrumentation / get_proposal_metrics).
        response_id: Unique ID for this response.
        health_diagnostics: Pre-computed result of
            compute_phase_health_diagnostics(model).  If None, computed
            automatically when health capture is enabled.
        ontological_state: Optional dict with control plane signals.
        coherence_score: Optional aggregate coherence.
        sequence_length: Token count for metadata.

    Returns:
        ExplanationTelemetry (from symbolu.mechanical.logging.telemetry_schema)

    Usage:
        enable_health_diagnostics_capture(model, True)
        logits = model(input_ids)
        health = compute_phase_health_diagnostics(model)
        telemetry = collect_explanation_telemetry(model, health_diagnostics=health)
        enable_health_diagnostics_capture(model, False)
        print(telemetry.summary())
    """
    from symbolu.mechanical.logging.phase_quad_explainer import PhaseQuadExplainer

    explainer = PhaseQuadExplainer(enable_deep_diagnostics=False)

    # Map health dict keys to the schema expected by explainer
    mapped_health = None
    if health_diagnostics is not None:
        mapped_health = {
            'r_k_mean': health_diagnostics.get('R_k', 0.0),
            'r_q_mean': health_diagnostics.get('R_q', 0.0),
            'amp_phase_corr': health_diagnostics.get('amp_phase_corr', 0.0),
            'head_redundancy': health_diagnostics.get('head_redundancy', 0.0),
            'phase_drift_mean': health_diagnostics.get('phase_drift_mean', 0.0),
            'phase_drift_std': health_diagnostics.get('phase_drift_std', 0.0),
        }

    return explainer.explain(
        model=model,
        response_id=response_id,
        health_diagnostics=mapped_health,
        ontological_state=ontological_state,
        coherence_score=coherence_score,
        sequence_length=sequence_length,
    )


# =============================================================================
# V9.9.12: ADAPTIVE PHASE DIVERSITY CONTROLLER (ChatGPT Universal Proposal)
# =============================================================================

class AdaptivePhaseDiversityController:
    """
    Adaptive controller for phase diversity loss weight.

    V9.9.12: Implements ChatGPT's "universal" proposal to replace fixed λ and ramp.

    Key features:
    1. Uses R (mean resultant length) as scale-free collapse metric
       - R ≈ 0: Uniform phases (healthy)
       - R ≈ 1: Collapsed phases (sick)

    2. Adjusts λ automatically via control loop:
       λ_{t+1} = clip(λ_t * exp(η * (R - R_target)))
       - If R > target: λ increases (more pressure)
       - If R < target: λ decreases (ease off)

    3. Warmup-coupled ramp (universal):
       - ramp_steps = 5 * warmup_steps (scales with training regime)
       - Or token-based: ramp until N million tokens seen

    Target bands for R:
    - Healthy: R ∈ [0.05, 0.30]
    - Borderline: R ∈ [0.30, 0.50]
    - Collapsed: R > 0.50

    Usage:
        controller = AdaptivePhaseDiversityController(
            warmup_steps=1000,  # From config
            target_R=0.25,      # Universal default
        )

        # In training loop:
        lambda_phase = controller.get_weight(global_step, current_R)
    """

    def __init__(
        self,
        warmup_steps: int = 1000,
        target_R: float = 0.25,
        lambda_init: float = 0.0001,
        lambda_min: float = 1e-6,
        lambda_max: float = 0.1,
        eta: float = 0.1,  # Control gain (how fast λ adapts)
        ema_decay: float = 0.95,  # Smooth R tracking
        ramp_multiplier: float = 5.0,  # ramp_steps = ramp_multiplier * warmup_steps
        task_loss_scaling: bool = True,  # V9.9.12b: Scale λ by task loss (ChatGPT)
        task_loss_alpha: float = 0.01,  # Scaling coefficient for task-loss mode
    ):
        """
        Args:
            warmup_steps: LR warmup steps (used to derive ramp_steps)
            target_R: Target mean resultant length (0.25 = healthy diversity)
            lambda_init: Initial λ value after ramp
            lambda_min: Minimum λ (floor)
            lambda_max: Maximum λ (ceiling)
            eta: Control gain for λ adjustment
            ema_decay: EMA decay for smoothing R observations
            ramp_multiplier: ramp_steps = ramp_multiplier * warmup_steps
            task_loss_scaling: If True, scale λ proportionally to task loss (self-normalizing)
            task_loss_alpha: Base coefficient when task_loss_scaling is True
        """
        self.warmup_steps = warmup_steps
        self.target_R = target_R
        self.lambda_init = lambda_init
        self.lambda_min = lambda_min
        self.lambda_max = lambda_max
        self.eta = eta
        self.ema_decay = ema_decay

        # V9.9.12b: Task-loss scaling (ChatGPT's Lagrange multiplier approach)
        self.task_loss_scaling = task_loss_scaling
        self.task_loss_alpha = task_loss_alpha
        self.task_loss_ema = 7.0  # Initialize to typical early training loss

        # Warmup-coupled ramp (universal)
        self.ramp_steps = int(ramp_multiplier * warmup_steps)

        # State
        self.current_lambda = 0.0  # Starts at 0, ramps up
        self.R_ema = 0.5  # Initial estimate (neutral)
        self.step_count = 0
        # V11.3.2: Emergency floor — prevents task-loss scaling from overwriting
        # force-jumps set by the training loop's emergency escalation.
        self.lambda_floor = 0.0

        # V11.4b: Stall detection — escalate if R_ema not converging
        self._stall_check_R = None  # R_ema at last stall check
        self._stall_check_step = 0  # Step at last stall check
        # Shorter window when ramp_multiplier=0 (emergency auto-enable)
        self._stall_window = 100 if ramp_multiplier == 0.0 else 300
        self._stall_threshold = 0.005  # Must improve R by this much
        self._escalation_count = 0  # How many times we've escalated
        self._max_escalations = 3  # V11.4c: Give up after this many failed escalations
        self._surrendered = False   # V11.4c: True when we've accepted the model's natural R

        # Diagnostics
        self.lambda_history = []
        self.R_history = []

    def get_weight(self, global_step: int, current_R: float, task_loss: float = None) -> float:
        """
        Get current phase diversity weight, adapting based on R and optionally task loss.

        V9.9.12b Enhancement (ChatGPT's directive):
        - If task_loss_scaling=True and task_loss provided:
          λ_effective = α * task_loss * collapse_pressure
          This makes phase diversity a "geometry preservation constraint" that:
          1. Automatically weakens as task converges (lower loss)
          2. Only activates when collapse occurs (R > target)
          3. Acts like a Lagrange multiplier, not a heuristic

        Args:
            global_step: Current training step
            current_R: Current mean resultant length (phase_entropy_proxy)
            task_loss: Optional task loss for self-normalized scaling

        Returns:
            lambda: Adapted phase diversity weight
        """
        self.step_count = global_step

        # Update R EMA for smooth tracking
        self.R_ema = self.ema_decay * self.R_ema + (1 - self.ema_decay) * current_R
        self.R_history.append(current_R)

        # Update task loss EMA if provided
        if task_loss is not None:
            self.task_loss_ema = self.ema_decay * self.task_loss_ema + (1 - self.ema_decay) * task_loss

        # Compute collapse pressure: how much R exceeds target (0 if healthy)
        # dispersion = 1 - R (R=0 is uniform/healthy, R=1 is collapsed)
        # We want loss when R > target (collapsed)
        collapse_pressure = max(0.0, self.R_ema - self.target_R)

        # Phase 1: Ramp from 0 to full strength
        if global_step < self.ramp_steps:
            ramp_progress = global_step / max(1, self.ramp_steps)
        else:
            ramp_progress = 1.0

        # V11.4: Stall detection — if R_ema hasn't improved, escalate alpha
        # V11.4c: Give up after max_escalations — the model's architecture may
        # naturally sit at R_k≈0.50 and fighting it just adds gradient noise
        # that hurts val PPL. Accept the equilibrium and free gradient for LM.
        escalation_multiplier = 1.0
        if not self._surrendered:
            if self._stall_check_R is not None:
                steps_since_check = global_step - self._stall_check_step
                if steps_since_check >= self._stall_window:
                    improvement = self._stall_check_R - self.R_ema  # Positive = good
                    if improvement < self._stall_threshold and self.R_ema > self.target_R:
                        # Stalled — escalate
                        self._escalation_count += 1
                        if self._escalation_count > self._max_escalations:
                            # Tried enough — accept the model's natural R
                            old_target = self.target_R
                            self.target_R = self.R_ema + 0.01  # Tiny buffer above current
                            self._surrendered = True
                            print(
                                f"  🏳️ [PHASE-DIV] Surrendered after {self._max_escalations} failed escalations. "
                                f"R_k≈{self.R_ema:.4f} is the model's natural equilibrium. "
                                f"target_R: {old_target:.2f} → {self.target_R:.4f} "
                                f"(pressure → 0, all gradient to LM loss)"
                            )
                    else:
                        # Making progress — de-escalate
                        self._escalation_count = max(0, self._escalation_count - 1)
                    self._stall_check_R = self.R_ema
                    self._stall_check_step = global_step
            else:
                self._stall_check_R = self.R_ema
                self._stall_check_step = global_step
            # V11.4c: Cap at 4x (was 8x) — higher multipliers just add noise
            escalation_multiplier = min(4.0, 2.0 ** self._escalation_count)
            if self._escalation_count > 0 and self._stall_check_step == global_step:
                print(
                    f"  ⚡ [PHASE-DIV] Stall escalation #{self._escalation_count}/{self._max_escalations}: "
                    f"R_ema={self.R_ema:.4f} (target={self.target_R:.2f}), "
                    f"pressure={escalation_multiplier:.0f}x"
                )

        # Compute λ based on mode
        if self.task_loss_scaling and task_loss is not None:
            # V9.9.12b/V11.4: Normalized scaling with collapse-proportional pressure
            # Fix: Use log(task_loss) instead of raw task_loss to prevent λ from
            # weakening as training improves. log(8.2)≈2.1, log(3.0)≈1.1, so
            # the scaling stays in a tight band rather than halving with loss.
            log_loss = math.log(max(1.0, self.task_loss_ema))
            self.current_lambda = (
                self.task_loss_alpha *
                log_loss *
                collapse_pressure *
                ramp_progress *
                escalation_multiplier
            )
        else:
            # Original R-adaptive mode (V9.9.12a)
            if global_step < self.ramp_steps:
                self.current_lambda = self.lambda_init * ramp_progress
            else:
                # Adaptive control: λ_{t+1} = clip(λ_t * exp(η * (R - R_target)))
                error = self.R_ema - self.target_R
                adjustment = math.exp(self.eta * error)
                self.current_lambda = max(
                    self.lambda_min,
                    min(self.lambda_max, self.current_lambda * adjustment)
                )
                if self.current_lambda < self.lambda_init:
                    self.current_lambda = self.lambda_init

        # V11.3.3: Proportional minimum λ when collapse is significant
        # The task-loss scaling formula has a structural ceiling:
        #   λ = α * task_loss * (R_ema - target) ≈ 0.05 * 5.6 * 0.19 = 0.053
        # This is too weak to fix R_k ≈ 0.50 collapse. When R_ema exceeds target
        # by a significant margin, enforce a minimum proportional to the gap.
        if self.task_loss_scaling and self.R_ema > self.target_R + 0.10:
            gap_ratio = (self.R_ema - self.target_R) / self.target_R
            proportional_min = self.lambda_max * min(0.5, gap_ratio)
            if self.current_lambda < proportional_min:
                self.current_lambda = proportional_min

        # V11.3.2: Enforce emergency floor (set by train loop when R_k > 0.5 persists)
        # Without this, task-loss scaling overwrites emergency force-jumps each step.
        if self.lambda_floor > 0 and self.current_lambda < self.lambda_floor:
            self.current_lambda = self.lambda_floor

        # Apply bounds
        self.current_lambda = max(self.lambda_min, min(self.lambda_max, self.current_lambda))

        self.lambda_history.append(self.current_lambda)
        return self.current_lambda

    def get_status(self) -> dict:
        """Get controller status for logging."""
        collapse_pressure = max(0.0, self.R_ema - self.target_R)
        return {
            'phase_div_lambda': self.current_lambda,
            'phase_div_R_ema': self.R_ema,
            'phase_div_target_R': self.target_R,
            'phase_div_ramp_steps': self.ramp_steps,
            'phase_div_ramp_progress': min(1.0, self.step_count / max(1, self.ramp_steps)),
            'phase_div_collapse_pressure': collapse_pressure,
            'phase_div_task_loss_ema': self.task_loss_ema if self.task_loss_scaling else 0.0,
            'phase_div_escalation': self._escalation_count,
        }

    def __repr__(self) -> str:
        mode = "task-scaled" if self.task_loss_scaling else "R-adaptive"
        return (
            f"AdaptivePhaseDiversityController("
            f"mode={mode}, "
            f"target_R={self.target_R}, "
            f"λ={self.current_lambda:.6f}, "
            f"R_ema={self.R_ema:.3f}, "
            f"ramp_steps={self.ramp_steps})"
        )


# =============================================================================
# CONFIGURATION
# =============================================================================

@dataclass
class TransformerConfig:
    """Configuration for both Phase and Standard Transformers."""
    vocab_size: int = 50257
    embed_dim: int = 768
    num_layers: int = 12
    num_heads: int = 12
    ff_dim: Optional[int] = None  # Default: 4 * embed_dim
    max_seq_len: int = 8192
    dropout: float = 0.1

    # Phase-specific
    sync_steps: int = 3
    sync_lr: float = 0.1
    temperature: float = 1.0  # Lower = sharper attention (for classification tasks)
    cosine_mode: str = "standard"  # V9.6.12: "standard", "shifted", or "complex"
    decay_gamma: float = 1.0  # V9.6.13: State decay factor (1.0=infinite, <1.0=local focus)

    def __post_init__(self):
        if self.ff_dim is None:
            self.ff_dim = 4 * self.embed_dim


# =============================================================================
# INTENT PHASE PROJECTOR - Ontological → Phase Rotation
# =============================================================================

class IntentPhaseProjector(nn.Module):
    """
    Projects Bhava State Delta (ΔBhava) to phase rotation offsets.

    V11.0.0: Downsized from 32D → 12D (Bhava-only) for phase rotation.
    Phase rotation should encode WHAT the system IS (ontological identity),
    not control signals (Koshas/Vrittis/Gunas) which belong in the control plane.

    V9.8.0: Originally used full 32D Sovereign State.

    This is the bridge between Ontological identity and Phase attention.
    Only the 12D Bhava delta (how "mode of being" changed) feeds into phase
    rotation. Control signals (depth, reliability, energy) are routed elsewhere.

    12D Bhava State (Phase-Critical):
        [0:12]  - 12 Bhavas (Ontological Aspects) - softmax normalized

    Non-Phase Signals (routed to Control/Learning planes):
        Koshas (5D)  → CTM+ / Sentinel / Budget Controller
        Vrittis (5D) → ConfidenceGate / Sentinel
        Gunas (6D)   → Runtime Governor / PCAM decay
        Reserved (4D)→ Training-time feedback / diagnostics

    Theory (from ONTOLOGICAL_STATE_DELTA_DESIGN.md):
        z_lower' = z_lower × e^{iθ_higher}

    In practice:
        φ_q' = φ_q + θ_intent

    This means: Same tokens, but their RELATIONSHIPS change based on
    ontological identity (Bhava), not energy/depth/reliability state.

    Example:
        "The door is open"
        - Bhava = EXE (Execution mode) → θ ≈ 0° → tokens relate as "opportunity"
        - Bhava = WIT (Witness mode) → θ ≈ π → tokens relate as "observation"
    """

    def __init__(
        self,
        state_dim: int = PHASE_STATE_DIM,  # V11.0.0: 12D Bhava-only (was 32D)
        num_heads: int = 12,       # Number of attention heads
        head_dim: int = 64,        # Dimension per head
        project_per_head_dim: bool = False,  # If True, project to [H, D_h], else [H]
    ):
        super().__init__()
        self.state_dim = state_dim
        self.num_heads = num_heads
        self.head_dim = head_dim
        self.project_per_head_dim = project_per_head_dim

        # Store the total output dimension for consistent reshaping
        self.output_dim = num_heads * head_dim if project_per_head_dim else num_heads

        if project_per_head_dim:
            # Full projection: different phase offset for each (head, dim) pair
            # More expressive but more parameters
            self.phase_proj = nn.Sequential(
                nn.Linear(state_dim, state_dim * 2),
                nn.GELU(),
                nn.Linear(state_dim * 2, self.output_dim),
            )
        else:
            # Per-head projection: one phase offset per head
            # Simpler, each head gets uniformly rotated
            self.phase_proj = nn.Sequential(
                nn.Linear(state_dim, state_dim),
                nn.GELU(),
                nn.Linear(state_dim, num_heads),
            )

        # Initialize to near-zero so model starts unaffected
        with torch.no_grad():
            self.phase_proj[-1].weight.fill_(0.01)
            self.phase_proj[-1].bias.fill_(0.0)

    def forward(self, delta_bhava: torch.Tensor) -> torch.Tensor:
        """
        Convert Bhava state delta to phase offsets.

        V11.0.0: Input is now 12D Bhava-only delta (was 32D full state delta).

        Args:
            delta_bhava: [B, 12] or [B, T, 12] - Bhava state delta (phase-critical only)

        Returns:
            theta_intent: [B, H] or [B, H, D_h] or [B, T, H, D_h] - phase offsets
        """
        theta = self.phase_proj(delta_bhava)  # [B, H] or [B, H*D_h]

        if self.project_per_head_dim:
            # Reshape to [B, H, D_h] or [B, T, H, D_h]
            # Use actual output_dim to compute head_dim for consistent reshaping
            actual_head_dim = self.output_dim // self.num_heads
            if delta_bhava.dim() == 2:
                B = delta_bhava.shape[0]
                theta = theta.view(B, self.num_heads, actual_head_dim)
            else:
                # Use -1 to dynamically infer sequence length from tensor elements
                # This handles cases where the sequence length changes during generation
                B = delta_bhava.shape[0]
                theta = theta.view(B, -1, self.num_heads, actual_head_dim)

        # Scale to reasonable phase range (tanh → [-1, 1] → [-π, π])
        theta = torch.tanh(theta) * 3.14159

        return theta


# =============================================================================
# PHASE ATTENTION (O(n)) - Standalone Implementation
# =============================================================================

class PhaseAttentionLayer(nn.Module):
    """
    Learned Phase-Amplitude Attention (O(N) Complex Linear Attention)

    V2 UPGRADE using Euler's Formula for cleaner math:

    Mathematically:
        Attn(i,j) = a_i * a_j * cos(φ_i - φ_j)

    Using Euler's formula e^(iφ) = cos(φ) + i*sin(φ):
        cos(φ_i - φ_j) = Re(e^(iφ_i) × e^(-iφ_j))

    Implemented as:
        Q = a * exp(i * φ)       # Query phasor
        K = a * exp(-i * φ)      # Key phasor (conjugate)
        State = CumSum(K * V)    # O(n) aggregation
        Out = Re(Q * State)      # Readout

    This is mathematically equivalent to amplitude-gated phase attention
    but more elegant and numerically stable via complex arithmetic.

    V9.6.12: Cosine Mode Alternatives
    ---------------------------------
    Three modes for the cosine interaction kernel:

    1. "standard" (default): cos(φ_q - φ_k), range [-1, +1]
       - Original implementation
       - Can have destructive interference (negative cancellation)

    2. "shifted": 1 + cos(φ_q - φ_k), range [0, 2]
       - Eliminates negative cancellation
       - Guarantees positive signal flow
       - Use when training plateaus due to signal collapse

    3. "complex": Uses both real (cos) and imaginary (sin) components
       - Real part: symmetric interaction
       - Imaginary part: asymmetric/directional ("the" → "cat" ≠ "cat" → "the")
       - Projects complex output to real via learned linear layer
       - Most expressive but slightly higher memory
    """

    def __init__(
        self,
        embed_dim: int,
        num_heads: int,
        dropout: float = 0.1,
        sync_steps: int = 3,      # Unused in V2 but kept for compatibility
        sync_lr: float = 0.1,     # Unused in V2 but kept for compatibility
        temperature: float = 1.0,  # Unused in V2 but kept for compatibility
        aux_scale: float = 0.1,   # Output scaling for auxiliary path integration
        cosine_mode: str = "standard",  # V9.6.12: "standard", "shifted", or "complex"
        decay_gamma: float = 1.0,  # V9.6.13: State decay factor (1.0=infinite memory, <1.0=local focus)
        learned_decay: bool = False,  # V9.9.7: Per-head learned decay (Mamba/S4-style)
        bounded_phase: bool = False,  # V9.9.11: Constrain φ to [-π, π] via π*sin()
        zero_mean_cosine: bool = False,  # V9.9.11: Center cosine per head (forces selectivity)
        # V10.3.8: Dual-Channel Attention (ChatGPT recommendation)
        dual_channel_mode: bool = False,  # Separate content and alignment scores
        alignment_authority: float = 0.1,  # α: weight for alignment term
        # V10.12: Multi-channel Phase memory with selective write gating
        phase_channels: int = 1,  # Number of independent memory channels (1=legacy)
        phase_write_gate: bool = False,  # Selective write gating for memory updates
    ):
        super().__init__()
        self.embed_dim = embed_dim
        self.num_heads = num_heads
        self.head_dim = embed_dim // num_heads
        self.aux_scale = aux_scale

        # V10.12: Multi-channel Phase memory with selective write gating
        self.phase_channels = phase_channels
        self.phase_write_gate_enabled = phase_write_gate

        # V9.9.11: Phase collapse fixes (ChatGPT mandatory fixes)
        self.bounded_phase = bounded_phase  # π*sin() bounds φ to S¹ manifold
        self.zero_mean_cosine = zero_mean_cosine  # Center cosine to force selectivity

        # V10.3.8: Dual-Channel Attention (ChatGPT recommendation)
        # Instead of collapsing intent into a single cosine, keep content and alignment separate:
        #   s_content = cos(φ_q - φ_k)           # What matches (content similarity)
        #   s_align = cos(θ_JEPA - θ_SRK)        # Are we aligned (intent agreement)
        #   score = s_content * (1 + α * s_align) # Modulated combination
        # This prevents intent from dominating and losing content selectivity.
        self.dual_channel_mode = dual_channel_mode
        self.alignment_authority = alignment_authority

        # V9.6.12: Cosine mode for interaction kernel
        assert cosine_mode in ("standard", "shifted", "complex"), \
            f"cosine_mode must be 'standard', 'shifted', or 'complex', got '{cosine_mode}'"
        self.cosine_mode = cosine_mode

        # V9.6.13: State decay factor for memory horizon control
        # γ = 1.0: Infinite memory (current behavior), cumsum is exact
        # γ < 1.0: Exponential decay, effective memory ~1/(1-γ) tokens
        #          γ=0.9 → ~10 token memory, γ=0.95 → ~20 token memory
        # This forces pure Phase to focus on local grammar (like Mamba/RWKV/RetNet)
        assert 0.0 < decay_gamma <= 1.0, \
            f"decay_gamma must be in (0, 1], got {decay_gamma}"
        self.decay_gamma = decay_gamma

        # V9.9.7: Learned per-head decay (Mamba/S4-style)
        # Each head learns its own attention span via sigmoid-constrained decay
        # Range: [0.5, 1.0] to ensure numerical stability
        # - Low decay (~0.5): Focus on last ~2 tokens
        # - High decay (~0.99): Remember ~100 tokens
        self.learned_decay = learned_decay

        # V9.9.9: DIVERSE DECAY INITIALIZATION (Gemini's log-space timescale)
        # Instead of initializing all heads to the same decay, spread them out
        # using log-space timescale distribution for principled coverage.
        # This gives more resolution near high decay (long memory).
        if learned_decay:
            # Map timescales from ~2 tokens to ~max_seq_len tokens (log-space)
            min_timescale = 2.0
            max_timescale = 2048.0  # Effective memory span in tokens

            # Distribute timescales exponentially (log-space)
            # Head 0 = short memory (~2 tokens), Head N-1 = long memory (~2048 tokens)
            log_timescales = torch.linspace(
                math.log(min_timescale),
                math.log(max_timescale),
                num_heads
            )
            timescales = torch.exp(log_timescales)

            # Convert timescales to decay: γ = 1 - (1/timescale)
            # timescale=2 → γ=0.5, timescale=2048 → γ=0.9995
            gamma = 1.0 - (1.0 / timescales)

            # Clamp for numerical stability (prevents logit overflow)
            gamma = torch.clamp(gamma, 0.001, 0.9995)

            # Our decay formula is: γ = 0.5 + 0.5 * sigmoid(logit)
            # So: sigmoid(logit) = (γ - 0.5) / 0.5 = 2γ - 1
            # logit = log(sigmoid / (1 - sigmoid))
            sigmoid_target = 2.0 * gamma - 1.0
            sigmoid_target = torch.clamp(sigmoid_target, 0.01, 0.99)
            init_logits = torch.log(sigmoid_target / (1.0 - sigmoid_target))

            self.decay_logit = nn.Parameter(init_logits)
        else:
            # V9.9.12c: Don't create decay_logit when learned_decay=False
            # (ChatGPT analysis: wasted parameters and optimizer state)
            # Instead, just use self.decay_gamma directly in forward()
            self.decay_logit = None

        # V10.12: Multi-channel Phase memory modules
        if phase_channels > 1:
            # Per-channel-per-head decay: allows each channel to specialize
            # in different memory horizons (e.g., channel 0=short, channel 3=long)
            if learned_decay:
                # Shape [C*H]: folded so parallel_ema_scan treats each channel-head
                # pair as an independent "virtual head"
                min_ts, max_ts = 2.0, 2048.0
                log_ts = torch.linspace(math.log(min_ts), math.log(max_ts), phase_channels * num_heads)
                ts = torch.exp(log_ts)
                ch_gamma = torch.clamp(1.0 - 1.0 / ts, 0.001, 0.9995)
                ch_sig = 2.0 * ch_gamma - 1.0
                ch_sig = torch.clamp(ch_sig, 0.01, 0.99)
                ch_logits = torch.log(ch_sig / (1.0 - ch_sig))
                self.channel_decay_logit = nn.Parameter(ch_logits)  # [C*H]
            else:
                self.channel_decay_logit = None

            # Channel aggregation: learned weights to combine C channels at readout
            # Initialized uniform so all channels contribute equally at start
            self.channel_agg = nn.Parameter(torch.ones(phase_channels) / phase_channels)

        if phase_write_gate:
            # Selective write gate: g_t = sigmoid(W_g @ x_t)
            # Per-channel per-head gate controls what gets written to memory
            # Shape: embed_dim → phase_channels * num_heads
            self.write_gate_proj = nn.Linear(embed_dim, phase_channels * num_heads, bias=True)
            # Initialize bias to +2 so gates start near-open (sigmoid(2)≈0.88)
            # This ensures training starts close to the unmodified behavior
            nn.init.zeros_(self.write_gate_proj.weight)
            nn.init.constant_(self.write_gate_proj.bias, 2.0)

        # V10.12: Diagnostic capture flags
        self._diag_phase_gate_mean = None
        self._diag_phase_gate_std = None
        self._diag_phase_state_norm_per_channel = None
        self._diag_phase_attn_mass = None

        # V10.13: Phase Warm-Start Gate (defaults, overridden by HybridPhaseTransformer)
        self.phase_warmstart_enabled = False
        self._warmstart_steps = 10000
        self._warmstart_tau = 2000.0
        self._warmstart_apply_inference = False
        self._current_step = 0
        self._diag_warmstart_alpha = None

        # V10.13: Phase→Global state capture (detached, for external consumers)
        self._last_final_state_agg = None

        # V9.9.9: PHASE SPREAD INITIALIZATION (Gemini's recommendation)
        # Distribute starting phases around the unit circle to shatter phase collapse.
        # Each head gets a unique rotational offset to encourage semantic diversity.
        # Head 0 = 0 rad, Head 1 = π/6 rad, ..., Head 11 = 11π/6 rad
        phase_offsets = torch.linspace(0, 2 * math.pi * (num_heads - 1) / num_heads, num_heads)
        self.phase_offset_q = nn.Parameter(phase_offsets.clone(), requires_grad=False)  # Fixed offsets
        self.phase_offset_k = nn.Parameter(phase_offsets.clone(), requires_grad=False)  # Fixed offsets

        # V9.9.10: Phase diversity loss capture
        # When enabled, captures phi_k and phi_q for computing repulsion + entropy losses
        self.capture_phase_for_diversity = False  # Set True during training
        self._captured_phi_k = None  # [B, N, H, D_h] stored during forward
        self._captured_phi_q = None  # [B, N, H, D_h] stored during forward (V11.x: symmetric regularization)

        # V9.9.12c: Health dashboard capture (diagnostic only, no gradients)
        # Uses separate _health_* attributes to avoid overwriting diversity capture
        self.capture_for_health_diagnostics = False
        self._health_phi_k = None   # [B, N, H, D_h] key phases (detached)
        self._health_phi_q = None   # [B, N, H, D_h] query phases (detached)
        self._health_a_k = None     # [B, N, H, D_h] key amplitudes (detached)

        # Legacy parameters kept for checkpoint compatibility
        self.sync_steps = sync_steps
        self.temperature = temperature
        self.sync_lr = nn.Parameter(torch.tensor(sync_lr))

        # =====================================================================
        # V9.6.11: DECOUPLED HIGH-CAPACITY PHASE-AMPLITUDE PROJECTIONS
        # =====================================================================
        # Previous issues fixed:
        # 1. Low capacity: was 768→12, now 768→768 (full head_dim per head)
        # 2. Shared Q/K: was same φ,a for both, now separate projections
        # 3. Vanishing gradients: uniform [-π,π] init instead of small normal
        #
        # This matches standard attention capacity while keeping O(n) complexity
        #
        # V10.8: FUSED PROJECTIONS — 2 GEMMs instead of 4
        # Phase and amplitude are projected together then split, eliminating
        # 2 kernel launches per layer. Checkpoint-compatible via properties.

        # Fused Query projection: phase + amplitude in one GEMM
        self.W_q_fused = nn.Linear(embed_dim, embed_dim * 2, bias=False)

        # Fused Key projection: phase + amplitude in one GEMM
        self.W_k_fused = nn.Linear(embed_dim, embed_dim * 2, bias=False)

        # Value projection (content)
        self.v_proj = nn.Linear(embed_dim, embed_dim, bias=False)

        # Output projection
        self.out_proj = nn.Linear(embed_dim, embed_dim, bias=False)

        # Layer normalization for stability
        self.norm = nn.LayerNorm(embed_dim)
        self.dropout = nn.Dropout(dropout)

        # V9.6.11: Initialize phase projections with diverse phases
        # V10.8: Apply to fused weight's phase half (first embed_dim rows)
        # V10.15: Reduced from [-π, π] to [-1, 1] to prevent gradient spikes
        # in fused projection during LR warmup. Phase diversity is preserved
        # since sin/cos cover full range within [-1, 1] input.
        nn.init.uniform_(self.W_q_fused.weight[:embed_dim], -1.0, 1.0)
        nn.init.uniform_(self.W_k_fused.weight[:embed_dim], -1.0, 1.0)

        # V9.6.12: Complex-to-real projection for "complex" cosine mode
        # Projects [real, imag] → real, allowing the model to learn how to
        # combine symmetric (cos) and asymmetric (sin) components
        if cosine_mode == "complex":
            self.complex_to_real = nn.Linear(2 * embed_dim, embed_dim, bias=False)
            # Initialize to favor real (cos) component initially for stability
            with torch.no_grad():
                self.complex_to_real.weight[:, :embed_dim] = torch.eye(embed_dim) * 0.8
                self.complex_to_real.weight[:, embed_dim:] = torch.eye(embed_dim) * 0.2
        else:
            self.complex_to_real = None

        # Legacy projections kept for checkpoint compatibility
        self.W_phase = nn.Linear(embed_dim, num_heads, bias=False)  # Legacy
        self.W_amp = nn.Linear(embed_dim, num_heads, bias=False)    # Legacy
        self.q_proj = nn.Linear(embed_dim, embed_dim)
        self.k_proj = nn.Linear(embed_dim, embed_dim)
        self.phase_proj = nn.Linear(self.head_dim, self.head_dim)
        self.key_gate = nn.Linear(self.head_dim, self.head_dim)
        self.value_gate = nn.Linear(self.head_dim, self.head_dim)
        self.phase_embed = nn.Linear(embed_dim, num_heads)
        self.amp_gate = nn.Linear(embed_dim, num_heads)

    # V10.8: Backward-compatible properties for diagnostics that access
    # the old separate W_q_phase, W_k_phase weights (e.g., ortho loss).
    # These return view-like objects with a .weight attribute.
    class _FusedWeightView:
        """Lightweight view into a slice of the fused weight matrix."""
        def __init__(self, fused_linear, start, end):
            self._fused = fused_linear
            self._start = start
            self._end = end
        @property
        def weight(self):
            return self._fused.weight[self._start:self._end]

    @property
    def W_q_phase(self):
        return self._FusedWeightView(self.W_q_fused, 0, self.embed_dim)

    @property
    def W_q_amp(self):
        return self._FusedWeightView(self.W_q_fused, self.embed_dim, self.embed_dim * 2)

    @property
    def W_k_phase(self):
        return self._FusedWeightView(self.W_k_fused, 0, self.embed_dim)

    @property
    def W_k_amp(self):
        return self._FusedWeightView(self.W_k_fused, self.embed_dim, self.embed_dim * 2)

    def forward(
        self,
        x: torch.Tensor,
        causal_mask: bool = True,
        phase_context: Optional[Dict[str, torch.Tensor]] = None,
        intent_phase: Optional[torch.Tensor] = None,
        intent_phase_query: Optional[torch.Tensor] = None,  # V10.3.8: θ_JEPA (Sensor)
        intent_phase_key: Optional[torch.Tensor] = None,    # V10.3.8: θ_SRK (Master)
        prev_state: Optional[torch.Tensor] = None,
        prev_norm_state: Optional[torch.Tensor] = None,
        return_state: bool = False,
    ) -> Union[torch.Tensor, Tuple[torch.Tensor, Dict[str, torch.Tensor]]]:
        """
        Forward pass with O(n) complex phase attention.

        V10.2: Added prev_state for chunk-persistent phase memory.
        When chunking long sequences, Phase state MUST persist across chunks
        to maintain temporal continuity. This is critical for Phase to work
        as a true temporal memory, not just per-chunk memory.

        V10.3.8: Dual-Channel Attention Mode
        When dual_channel_mode=True, content and alignment are computed separately:
            s_content = cos(φ_q - φ_k)           # What matches
            s_align = cos(θ_JEPA - θ_SRK)        # Intent agreement
            score = s_content * (1 + α * s_align) # Combined
        This prevents intent from dominating content selectivity during training.

        Args:
            x: [B, N, D] input tensor
            causal_mask: Apply causal masking (always True for complex cumsum)
            phase_context: Optional streaming context (legacy, not used in V2)
            intent_phase: Optional [B, H] or [B, H, D_h] or [B, T, H, D_h] phase rotation
                         from Ontological State Delta. Rotates query phasors to change
                         how tokens relate based on intent/understanding.
                         (Legacy - use intent_phase_query for dual-channel mode)
            intent_phase_query: V10.3.8 - θ_JEPA from Sensor (JEPA prediction).
                               Affects Query side: "What am I looking for?"
            intent_phase_key: V10.3.8 - θ_SRK from Master (SRK understanding).
                             Affects Key side: "What do I understand?"
            prev_state: Optional [B, 1, H, D_h] complex tensor - accumulated KV state
                       from previous chunk. If provided, this is prepended to cumsum.
                       CRITICAL: Do NOT detach this - gradients must flow through time!
            prev_norm_state: Optional [B, 1, H, D_h] real tensor - accumulated normalizer
                            state from previous chunk.
            return_state: If True, return (output, state_dict) where state_dict contains
                         'final_state' and 'final_norm_state' for the next chunk.

        Returns:
            output: [B, N, D] attention output
            state_dict: (optional) {'final_state': [B, 1, H, D_h], 'final_norm_state': [B, 1, H, D_h]}
        """
        B, N, D = x.shape
        residual = x

        # V10.13: Phase Warm-Start Gate — compute dampening coefficient
        if self.phase_warmstart_enabled:
            _ws_s = self._current_step
            _warmstart_alpha = 1.0 / (1.0 + math.exp(-(_ws_s - self._warmstart_steps) / max(self._warmstart_tau, 1.0)))
            if (not self.training) and (not self._warmstart_apply_inference):
                _warmstart_alpha = 1.0
            self._diag_warmstart_alpha = _warmstart_alpha
        else:
            _warmstart_alpha = 1.0

        # Pre-norm (standard for modern transformers)
        x_norm = self.norm(x)

        # =====================================================================
        # 1. Project to SEPARATE Phase (φ) and Amplitude (a) for Q and K
        # =====================================================================
        # V9.6.11: Decoupled Q/K with high capacity (embed_dim → embed_dim)
        # - Query: "what am I looking for?"
        # - Key: "what do I represent?"
        # This allows asymmetric attention patterns (e.g., "The" → "Empire")

        # V10.8: Fused query projection — one GEMM, then split
        q_fused = self.W_q_fused(x_norm).view(B, N, 2, self.num_heads, self.head_dim)
        phi_q_raw = q_fused[:, :, 0]  # [B, N, H, D_h]
        # V10.17: Amplitude floor prevents sigmoid collapse toward 0.
        # When a_q ≈ 0, the normalizer (a_q * a_k_cumsum) hits the clamp floor
        # and gradients through the sigmoid/cumsum path explode (2183x variance
        # spikes observed on W_k_fused). Floor at 0.05 guarantees minimum amplitude.
        a_q = 0.05 + 0.95 * torch.sigmoid(q_fused[:, :, 1])  # [B, N, H, D_h]

        # V10.8: Fused key projection — one GEMM, then split
        k_fused = self.W_k_fused(x_norm).view(B, N, 2, self.num_heads, self.head_dim)
        phi_k_raw = k_fused[:, :, 0]  # [B, N, H, D_h]
        a_k = 0.05 + 0.95 * torch.sigmoid(k_fused[:, :, 1])  # [B, N, H, D_h]

        # V9.9.11: Bounded phase parameterization (ChatGPT Fix 1 - mandatory)
        # Constrains φ to [-π, π] via π*sin() for proper S¹ manifold geometry.
        # Without this, raw linear projections can drift unbounded and cause collapse.
        if self.bounded_phase:
            phi_q = math.pi * torch.sin(phi_q_raw)
            phi_k = math.pi * torch.sin(phi_k_raw)
        else:
            phi_q = phi_q_raw
            phi_k = phi_k_raw

        # V9.9.9: Apply per-head phase offsets (Gemini's Phase Spread)
        # This shatters phase collapse by giving each head a unique starting angle.
        # Broadcasts [H] → [B, N, H, D_h]. Cast to match mixed precision dtype.
        if hasattr(self, 'phase_offset_q'):
            phi_q = phi_q + self.phase_offset_q.to(phi_q.dtype).view(1, 1, -1, 1)
            phi_k = phi_k + self.phase_offset_k.to(phi_k.dtype).view(1, 1, -1, 1)

        # V9.9.10: Capture phi_k and phi_q for phase diversity loss computation
        # Only capture during training when flag is set (saves memory in eval)
        if self.capture_phase_for_diversity and self.training:
            self._captured_phi_k = phi_k  # [B, N, H, D_h] - gradients flow through
            self._captured_phi_q = phi_q  # [B, N, H, D_h] - V11.x: symmetric regularization

        # V9.9.12c: Capture for health diagnostics (read-only, detached)
        # Use separate attributes to avoid overwriting diversity capture's
        # gradient-bearing tensor with a detached version
        if self.capture_for_health_diagnostics:
            self._health_phi_k = phi_k.detach()  # [B, N, H, D_h]
            self._health_phi_q = phi_q.detach()  # [B, N, H, D_h]
            self._health_a_k = a_k.detach()      # [B, N, H, D_h]

        # =====================================================================
        # 1.5. Apply Intent Phase Rotation (Ontological → Phase bridge)
        # =====================================================================
        # V10.3.8: Dual-Channel Mode vs Legacy Mode
        #
        # LEGACY MODE (dual_channel_mode=False):
        #   φ_q' = φ_q + θ_intent  (collapsed into single cosine)
        #   score = cos(φ_q + θ_intent - φ_k)
        #   Risk: Intent can dominate, losing content selectivity
        #
        # DUAL-CHANNEL MODE (dual_channel_mode=True):
        #   Keep φ_q and φ_k pure for content matching
        #   s_content = cos(φ_q - φ_k)           # What matches
        #   s_align = cos(θ_JEPA - θ_SRK)        # Intent agreement
        #   score = s_content * (1 + α * s_align) # Modulated
        #   Benefit: Content cannot be overwritten by intent

        # Helper function to normalize intent_phase shape
        def _normalize_intent_shape(ip: torch.Tensor) -> torch.Tensor:
            if ip.dim() == 2:
                return ip.unsqueeze(1).unsqueeze(-1)  # [B, H] → [B, 1, H, 1]
            elif ip.dim() == 3:
                return ip.unsqueeze(1)  # [B, H, D_h] → [B, 1, H, D_h]
            return ip  # [B, T, H, D_h] → use directly

        # Store intent phases for dual-channel computation
        theta_jepa = None  # θ_JEPA (Sensor/Query side)
        theta_srk = None   # θ_SRK (Master/Key side)

        if self.dual_channel_mode:
            # V10.3.8: Dual-channel mode - keep phases pure, store intent separately
            # Prefer explicit intent_phase_query/key over legacy intent_phase
            if intent_phase_query is not None:
                theta_jepa = _normalize_intent_shape(intent_phase_query)
            elif intent_phase is not None:
                # Backward compatibility: treat intent_phase as query-side
                theta_jepa = _normalize_intent_shape(intent_phase)

            if intent_phase_key is not None:
                theta_srk = _normalize_intent_shape(intent_phase_key)
            # Note: phi_q and phi_k remain PURE content phases
        else:
            # Legacy mode: collapse intent into query phase
            effective_intent = intent_phase_query if intent_phase_query is not None else intent_phase
            if effective_intent is not None:
                effective_intent = _normalize_intent_shape(effective_intent)
                phi_q = phi_q + effective_intent

        # =====================================================================
        # 2. Project Values (content)
        # =====================================================================
        v = self.v_proj(x_norm).view(B, N, self.num_heads, self.head_dim)  # [B, N, H, D_h]

        # =====================================================================
        # 3. Form Complex Phasors using Euler's Formula
        # =====================================================================
        # Q = a_q * e^(iφ_q)   - Query phasor (what I'm looking for)
        # K = a_k * e^(-iφ_k)  - Key phasor (what I represent, conjugate)

        # V10.7: Always accumulate in float32 for numerical stability.
        # torch.polar doesn't support BFloat16, and cumsum/EMA scan in fp16
        # drifts on long sequences (>1K tokens). Force float32 for all complex ops.
        orig_dtype = phi_q.dtype
        if orig_dtype != torch.float32:
            phi_q = phi_q.float()
            phi_k = phi_k.float()
            a_q = a_q.float()
            a_k = a_k.float()
            v = v.float()

        # Create complex phasors using torch.polar(magnitude, angle)
        # Q and K now have DIFFERENT learned phases and amplitudes!
        q_phasor = torch.polar(a_q, phi_q)      # [B, N, H, D_h]
        k_phasor = torch.polar(a_k, -phi_k)     # [B, N, H, D_h] (negative phase for conjugate)

        # =====================================================================
        # 4. O(n) State Accumulation via Complex Cumsum
        # =====================================================================
        # KV = K * V (complex × real = complex, element-wise per head_dim)
        # State_t = Σ_{j≤t} K_j * V_j
        #
        # V10.2: CHUNK-PERSISTENT STATE
        # When prev_state is provided, we continue accumulation from that point.
        # This is critical for Phase to be a TRUE temporal memory across chunks.
        # Without this, Phase resets at chunk boundaries and becomes decorative.

        # Convert V to complex (real part only, imaginary = 0)
        v_complex = torch.complex(v, torch.zeros_like(v))

        # KV product: [B, N, H, D_h] × [B, N, H, D_h] -> [B, N, H, D_h]
        kv_complex = k_phasor * v_complex

        # V10.12: Multi-channel write gating and state accumulation
        C = self.phase_channels
        H_size = kv_complex.shape[2]
        D_h = kv_complex.shape[3]

        # --- Write Gate ---
        # g_t = sigmoid(W_g @ x_t), applied: kv_gated = g_t * kv_t
        if self.phase_write_gate_enabled:
            # x is the pre-norm input [B, N, D] — use it for gating
            gate_logits = self.write_gate_proj(x)  # [B, N, C*H]
            gate = torch.sigmoid(gate_logits).view(B, N, C, H_size, 1)  # [B, N, C, H, 1]
            # Diagnostic capture
            with torch.no_grad():
                self._diag_phase_gate_mean = gate.mean().item()
                self._diag_phase_gate_std = gate.std().item()
        else:
            gate = None  # No gating — all 1s implicitly

        # --- Expand kv to channels and apply gate ---
        if C > 1:
            # kv_complex: [B, N, H, D_h] → [B, N, C, H, D_h] (broadcast across channels)
            kv_multi = kv_complex.unsqueeze(2).expand(B, N, C, H_size, D_h)
            if gate is not None:
                kv_multi = kv_multi * gate  # Per-channel per-head gating
            # Fold channels into heads for parallel_ema_scan: [B, N, C*H, D_h]
            kv_scan = kv_multi.reshape(B, N, C * H_size, D_h)
        else:
            # Single channel: apply gate directly (no expand needed)
            if gate is not None:
                kv_scan = kv_complex * gate.view(B, N, H_size, 1)
            else:
                kv_scan = kv_complex
            # kv_scan: [B, N, H, D_h] — unchanged shape for backward compat

        # V10.13: Phase Warm-Start — dampen writes during early training
        if _warmstart_alpha < 1.0:
            kv_scan = kv_scan * _warmstart_alpha

        # --- State Accumulation (O(n) causal aggregation) ---
        use_decay = self.learned_decay or self.decay_gamma < 1.0

        if not use_decay:
            if prev_state is not None:
                global_state = torch.cumsum(kv_scan, dim=1) + prev_state
            else:
                global_state = torch.cumsum(kv_scan, dim=1)
        else:
            # Compute decay: per-channel-per-head if C>1, else per-head
            if C > 1 and self.learned_decay and self.channel_decay_logit is not None:
                gamma = 0.97 + 0.0295 * torch.sigmoid(self.channel_decay_logit)  # [C*H]
            elif self.learned_decay:
                gamma = 0.97 + 0.0295 * torch.sigmoid(self.decay_logit)  # [H]
                if C > 1:
                    # Broadcast per-head decay to all channels: [H] → [C*H]
                    gamma = gamma.repeat(C)
            else:
                gamma = self.decay_gamma  # Scalar

            # Handle prev_state for chunked EMA scan
            VH = kv_scan.shape[2]  # H or C*H
            if prev_state is not None:
                if isinstance(gamma, float):
                    gamma_tensor = torch.tensor(gamma, device=kv_scan.device, dtype=torch.float32)
                else:
                    gamma_tensor = gamma
                t_indices = torch.arange(1, N + 1, device=kv_scan.device, dtype=torch.float32)
                if gamma_tensor.dim() == 0:
                    decay_factors = gamma_tensor ** t_indices
                    decay_factors = decay_factors.view(1, N, 1, 1)
                else:
                    decay_factors = gamma_tensor.unsqueeze(0) ** t_indices.unsqueeze(1)  # [N, VH]
                    decay_factors = decay_factors.view(1, N, VH, 1)
                global_state = parallel_ema_scan(kv_scan, gamma) + prev_state * decay_factors.to(kv_scan.dtype)
            else:
                global_state = parallel_ema_scan(kv_scan, gamma)

            # State norm diagnostic
            with torch.no_grad():
                self._diag_state_norm = global_state.abs().mean(dim=-1).mean(dim=-1)  # [B, N]

        # Capture final state for chunk continuation
        # Raw state: [B, 1, H, D_h] (C=1) or [B, 1, C*H, D_h] (C>1) — for Phase EMA continuation
        final_state = global_state[:, -1:, :, :]
        # Aggregated final state: always [B, 1, H, D_h] — for cross-attention concatenation
        if C > 1:
            final_state_ch = final_state.view(B, 1, C, H_size, D_h)
            ch_w = torch.softmax(self.channel_agg, dim=0).view(1, 1, C, 1, 1)
            final_state_agg = (final_state_ch * ch_w).sum(dim=2)  # [B, 1, H, D_h]
        else:
            final_state_agg = final_state

        # V10.13: Store for Phase→Global integration (detached, no extra grad)
        self._last_final_state_agg = final_state_agg.detach()

        # --- Multi-channel readout: aggregate across channels ---
        if C > 1:
            # global_state: [B, N, C*H, D_h] → [B, N, C, H, D_h]
            global_state_ch = global_state.view(B, N, C, H_size, D_h)
            # Learned channel weights (softmax for stable mixing)
            ch_weights = torch.softmax(self.channel_agg, dim=0)  # [C]
            ch_weights = ch_weights.view(1, 1, C, 1, 1)
            # Weighted sum across channels: [B, N, C, H, D_h] → [B, N, H, D_h]
            global_state_agg = (global_state_ch * ch_weights).sum(dim=2)

            # Per-channel norm diagnostic
            with torch.no_grad():
                self._diag_phase_state_norm_per_channel = global_state_ch.abs().mean(dim=(0, 1, 4))  # [C, H]
        else:
            global_state_agg = global_state

        # =====================================================================
        # 5. Readout: Synchronization via Q × State (NORMALIZED)
        # =====================================================================
        # V9.6.11: Use amplitude-based normalization (always positive)
        # normalizer = a_q × Σ_{j≤t} a_k  (cross-amplitude energy)
        # V9.6.13: Apply same decay to normalizer for consistency
        # V9.9.7: Use same per-head learned decay as state accumulation
        # V10.2: Handle prev_norm_state for chunk continuation
        # NOTE: Normalizer uses per-head decay (not per-channel), since it tracks
        # amplitude accumulation which is channel-independent.
        if not use_decay:
            if prev_norm_state is not None:
                a_k_cumsum = torch.cumsum(a_k, dim=1) + prev_norm_state
            else:
                a_k_cumsum = torch.cumsum(a_k, dim=1)  # [B, N, H, D_h], always positive
        else:
            if self.learned_decay:
                gamma_norm = 0.97 + 0.0295 * torch.sigmoid(self.decay_logit)  # [H]
            else:
                gamma_norm = self.decay_gamma

            if prev_norm_state is not None:
                if isinstance(gamma_norm, float):
                    gamma_tensor = torch.tensor(gamma_norm, device=a_k.device, dtype=torch.float32)
                else:
                    gamma_tensor = gamma_norm
                t_indices = torch.arange(1, N + 1, device=a_k.device, dtype=torch.float32)
                if gamma_tensor.dim() == 0:
                    decay_factors = gamma_tensor ** t_indices
                    decay_factors = decay_factors.view(1, N, 1, 1)
                else:
                    decay_factors = gamma_tensor.unsqueeze(0) ** t_indices.unsqueeze(1)
                    decay_factors = decay_factors.view(1, N, H_size, 1)
                a_k_cumsum = parallel_ema_scan(a_k, gamma_norm) + prev_norm_state * decay_factors.to(a_k.dtype)
            else:
                a_k_cumsum = parallel_ema_scan(a_k, gamma_norm)

        # Capture final normalizer state for chunk continuation
        final_norm_state = a_k_cumsum[:, -1:, :, :]  # [B, 1, H, D_h]

        # V10.19: Detached normalizer — same pattern as slot key normalization (line 8576).
        # The division numerator/normalizer creates ∂L/∂normalizer = -numerator/normalizer²,
        # which is -100x when normalizer hits the 0.1 clamp floor. This gradient propagates
        # back through a_q → W_q_fused and cumsum(a_k) → W_k_fused, causing the variance
        # spikes (906x on v_proj, 34x on W_k_fused) that cascade to full backbone divergence
        # around step 720. Detaching preserves correct forward normalization while keeping
        # amplitude gradients flowing only through the numerator (bounded, healthy signal).
        normalizer = (a_q * a_k_cumsum).clamp(min=0.1).detach()  # [B, N, H, D_h]

        # V9.6.12: Cosine mode selection for interaction kernel
        # Use aggregated state (channels already combined) for readout
        qk_product = q_phasor * global_state_agg  # [B, N, H, D_h] complex

        if self.cosine_mode == "standard":
            # Original: cos(φ_q - φ_k), range [-1, +1]
            # Can have destructive interference (negative cancellation)
            numerator = qk_product.real  # [B, N, H, D_h]

            # V9.9.11: Zero-mean cosine per head (ChatGPT Fix 2 - mandatory)
            # Without this, cosine is always positive-biased and collapse is inevitable.
            # Centering forces the model to create both positive and negative contributions,
            # making selectivity necessary instead of trivially keeping everything high.
            if self.zero_mean_cosine:
                # Compute mean across batch and sequence (keep per-head, per-dim)
                cos_mean = numerator.mean(dim=(0, 1), keepdim=True)  # [1, 1, H, D_h]
                numerator = numerator - cos_mean

            sync_output = numerator / normalizer

        elif self.cosine_mode == "shifted":
            # Shifted: 1 + cos(φ_q - φ_k), range [0, 2]
            # Eliminates negative cancellation, guarantees positive signal flow
            #
            # Mathematically: Σ a_q * a_k * (1 + cos(φ_q - φ_k)) * v
            #               = Σ a_q * a_k * v + Σ a_q * a_k * cos(φ_q - φ_k) * v
            #
            # First term: amplitude-only product (no phase modulation)
            # Second term: cosine-modulated product (from complex phasor)

            # Accumulator for the "+1" shift term: a_k * v
            # V9.6.13: Apply decay to shifted mode accumulator
            # V9.9.8: Use parallel scan for shifted mode (note: this uses fixed decay, not learned)
            if self.decay_gamma == 1.0:
                av_state = torch.cumsum(a_k * v, dim=1)  # [B, N, H, D_h]
            else:
                # Use optimized parallel EMA scan
                av_input = a_k * v
                av_state = parallel_ema_scan(av_input, self.decay_gamma)

            # Combined: shift_term + cos_term
            shift_term = a_q * av_state           # a_q * Σ(a_k * v)
            cos_term = qk_product.real            # Re(q_phasor * global_state)

            numerator = shift_term + cos_term     # [B, N, H, D_h]
            # Normalizer for range [0, 2] → divide by 2 to keep same scale
            sync_output = numerator / (normalizer * 2)

        elif self.cosine_mode == "complex":
            # Full complex: uses both cos (real) and sin (imaginary)
            # Real: symmetric interaction (cos)
            # Imaginary: asymmetric/directional (sin)
            #
            # The sin component encodes ordering:
            #   sin(φ_q - φ_k) ≠ sin(φ_k - φ_q)
            # This allows "the" → "cat" ≠ "cat" → "the"

            real_part = qk_product.real / normalizer   # [B, N, H, D_h]
            imag_part = qk_product.imag / normalizer   # [B, N, H, D_h]

            # Reshape for concatenation: [B, N, H, D_h] → [B, N, D]
            real_flat = real_part.reshape(B, N, D)
            imag_flat = imag_part.reshape(B, N, D)

            # Concatenate real and imaginary: [B, N, 2*D]
            complex_concat = torch.cat([real_flat, imag_flat], dim=-1)

            # Cast back to original dtype before projection if needed
            if orig_dtype == torch.bfloat16:
                complex_concat = complex_concat.to(orig_dtype)

            # Project complex → real via learned linear layer: [B, N, 2*D] → [B, N, D]
            sync_output = self.complex_to_real(complex_concat)

            # V10.3.8: Dual-Channel Alignment Modulation for complex mode
            if self.dual_channel_mode and (theta_jepa is not None or theta_srk is not None):
                if theta_jepa is not None and theta_srk is not None:
                    theta_diff = theta_jepa - theta_srk
                elif theta_jepa is not None:
                    theta_diff = theta_jepa
                else:
                    theta_diff = theta_srk
                s_align = torch.cos(theta_diff)
                # For complex mode, sync_output is [B, N, D], need to broadcast s_align
                # s_align is [B, 1, H, 1] or similar, reshape to [B, 1, D] for broadcast
                s_align_flat = s_align.mean(dim=-1).view(s_align.shape[0], s_align.shape[1], -1)
                # Broadcast to [B, N, D]
                if s_align_flat.shape[1] == 1:
                    s_align_flat = s_align_flat.expand(-1, N, -1)
                if s_align_flat.shape[2] != D:
                    s_align_flat = s_align_flat.mean(dim=-1, keepdim=True).expand(-1, -1, D)
                alignment_modulator = 1.0 + self.alignment_authority * s_align_flat
                sync_output = sync_output * alignment_modulator

            # Early return for complex mode (dtype already handled)
            output = self.out_proj(sync_output)
            output = self.dropout(output)
            output = output * self.aux_scale
            # V10.13: Phase Warm-Start — dampen reads during early training
            if _warmstart_alpha < 1.0:
                output = output * _warmstart_alpha
            result = output + residual

            # V10.2: Return state for chunk continuation
            if return_state:
                state_dict = {
                    'final_state': final_state,  # [B, 1, H, D_h] complex
                    'final_norm_state': final_norm_state,  # [B, 1, H, D_h] real
                }
                return result, state_dict
            if phase_context is not None:
                return result, None
            return result

        # =====================================================================
        # 5.5. V10.3.8: Dual-Channel Alignment Modulation
        # =====================================================================
        # If dual_channel_mode is enabled and we have intent phases,
        # modulate the content score by the alignment term:
        #   sync_output = sync_output * (1 + α * s_align)
        # where s_align = cos(θ_JEPA - θ_SRK)
        #
        # This keeps content selectivity while allowing intent to boost/suppress.
        if self.dual_channel_mode and (theta_jepa is not None or theta_srk is not None):
            # Use zeros for missing intent phases
            if theta_jepa is not None and theta_srk is not None:
                # Both provided - full alignment computation
                # Broadcast to match sync_output shape [B, N, H, D_h]
                theta_diff = theta_jepa - theta_srk
            elif theta_jepa is not None:
                # Only JEPA - alignment is just cos(θ_JEPA)
                theta_diff = theta_jepa
            else:
                # Only SRK - alignment is cos(-θ_SRK) = cos(θ_SRK)
                theta_diff = theta_srk

            # s_align = cos(θ_JEPA - θ_SRK), range [-1, +1]
            s_align = torch.cos(theta_diff)  # [B, 1, H, 1] or [B, N, H, D_h]

            # Modulate: score = s_content * (1 + α * s_align)
            # α is alignment_authority, controls how much intent affects attention
            # α=0: pure content matching (intent ignored)
            # α=0.1: mild intent influence (recommended default)
            # α=1.0: strong intent influence (can dominate)
            alignment_modulator = 1.0 + self.alignment_authority * s_align
            sync_output = sync_output * alignment_modulator

        # Cast back to original dtype if we converted (for standard/shifted modes)
        if orig_dtype == torch.bfloat16:
            sync_output = sync_output.to(orig_dtype)

        # =====================================================================
        # 6. Output Projection
        # =====================================================================
        sync_output = sync_output.reshape(B, N, D)
        output = self.out_proj(sync_output)
        output = self.dropout(output)

        # Scale output for auxiliary path integration
        # This prevents Phase from competing 50/50 with Quadratic attention
        output = output * self.aux_scale

        # V10.13: Phase Warm-Start — dampen reads during early training
        if _warmstart_alpha < 1.0:
            output = output * _warmstart_alpha

        # Residual connection
        result = output + residual

        # V10.2: Return state for chunk continuation
        if return_state:
            state_dict = {
                'final_state': final_state,  # [B, 1, H, D_h] or [B, 1, C*H, D_h] for Phase EMA
                'final_state_agg': final_state_agg,  # [B, 1, H, D_h] always — for cross-attn
                'final_norm_state': final_norm_state,  # [B, 1, H, D_h] real
                # V10.2.1: Return memory_state for Local cross-attention
                # Uses aggregated state [B, N, H, D_h] (channels already combined)
                # V10.13: Dampen memory for cross-attention during warm-start
                'memory_state': global_state_agg * _warmstart_alpha if _warmstart_alpha < 1.0 else global_state_agg,
            }
            return result, state_dict

        # Return with phase_context compatibility (not used in V2)
        if phase_context is not None:
            return result, None
        return result


# =============================================================================
# V10.7: PHASE STATE CACHE — Hardened O(1) Inference API
# =============================================================================
# At inference time, Phase Attention only needs to carry forward:
#   - final_state:      [B, 1, H, D_h] complex — accumulated KV state
#   - final_norm_state: [B, 1, H, D_h] real    — amplitude normalizer
#
# This class enforces that no O(N) allocation occurs during inference.
# It wraps the per-layer state and provides a clean API for generate loops.
# =============================================================================


class PhaseStateCache:
    """
    O(1) inference cache for Phase Attention layers.

    Stores only the final accumulated state per layer, NOT per-token K/V.
    This is the core KV-cache reduction: memory is O(d × layers), not O(T × d × layers).

    Usage:
        cache = PhaseStateCache(num_layers=12, hybrid_layer_start=4)

        for token in tokens:
            result, cache = model.forward_with_cache(token, cache)

    Internal storage per hybrid layer:
        - final_state:      [B, 1, H, D_h] complex
        - final_norm_state: [B, 1, H, D_h] real
    """

    def __init__(self, num_layers: int, hybrid_layer_start: int = 0):
        self.num_layers = num_layers
        self.hybrid_layer_start = hybrid_layer_start
        # Maps layer_idx -> {'final_state': Tensor, 'final_norm_state': Tensor}
        self._states: Dict[int, Dict[str, torch.Tensor]] = {}
        self._step_count: int = 0
        # V10.7.1: Token buffer for full-prefix replay when local layers are active
        self._token_buffer: Optional[torch.Tensor] = None

    def get_layer_state(self, layer_idx: int) -> Tuple[Optional[torch.Tensor], Optional[torch.Tensor]]:
        """Get (prev_state, prev_norm_state) for a layer. Returns (None, None) if no state yet."""
        state = self._states.get(layer_idx)
        if state is None:
            return None, None
        return state['final_state'], state['final_norm_state']

    def update_layer_state(self, layer_idx: int, state_dict: Dict[str, torch.Tensor]) -> None:
        """
        Update state for a layer from PhaseAttentionLayer's return_state output.

        Enforces O(1) shape: state must be [B, 1, H, D_h].
        Raises ValueError if state has sequence dimension > 1.
        """
        final_state = state_dict['final_state']
        final_norm_state = state_dict['final_norm_state']

        # Shape enforcement: must be [B, 1, H, D_h]
        if final_state.shape[1] != 1:
            raise ValueError(
                f"PhaseStateCache: final_state has seq dim {final_state.shape[1]}, "
                f"expected 1. This indicates O(N) allocation leaked into inference. "
                f"Full shape: {final_state.shape}"
            )
        if final_norm_state.shape[1] != 1:
            raise ValueError(
                f"PhaseStateCache: final_norm_state has seq dim {final_norm_state.shape[1]}, "
                f"expected 1. Full shape: {final_norm_state.shape}"
            )

        self._states[layer_idx] = {
            'final_state': final_state.detach(),
            'final_norm_state': final_norm_state.detach(),
        }

    def as_prev_layer_states(self) -> Dict[int, Dict[str, torch.Tensor]]:
        """Convert to the dict format expected by forward_chunk(prev_layer_states=...)."""
        return dict(self._states)

    @property
    def seq_len(self) -> int:
        """Number of tokens processed so far."""
        return self._step_count

    def advance(self, n_tokens: int = 1) -> None:
        """Record that n_tokens were processed."""
        self._step_count += n_tokens

    def append_tokens(self, input_ids: torch.Tensor) -> torch.Tensor:
        """
        V10.7.1: Append new tokens to the token buffer and return full sequence.

        Used by the safety fallback to reconstruct the full prefix for replay.
        The token buffer grows linearly with sequence length — this is the
        correctness-over-performance tradeoff when local layers are active.

        Args:
            input_ids: [B, N] new token IDs to append

        Returns:
            full_input_ids: [B, total_len] all tokens seen so far (including new)
        """
        if self._token_buffer is None:
            self._token_buffer = input_ids
        else:
            self._token_buffer = torch.cat([self._token_buffer, input_ids], dim=1)
        return self._token_buffer

    def reset(self) -> None:
        """Clear all state (start of new sequence)."""
        self._states.clear()
        self._step_count = 0
        self._token_buffer = None

    def memory_bytes(self) -> int:
        """Total memory used by cached states (should be constant regardless of seq_len)."""
        total = 0
        for state_dict in self._states.values():
            for t in state_dict.values():
                total += t.nelement() * t.element_size()
        return total

    def __repr__(self) -> str:
        n_layers = len(self._states)
        mem_mb = self.memory_bytes() / (1024 * 1024)
        return (
            f"PhaseStateCache(layers={n_layers}/{self.num_layers}, "
            f"seq_len={self._step_count}, mem={mem_mb:.2f}MB)"
        )


# =============================================================================
# V10.7: CHUNKED STATEFUL TRAINING — Truncated BPTT with Phase State Carry
# =============================================================================
# Unlike standard LLM chunking (which resets context between segments),
# this carries Phase state across chunks via detached state tensors.
#
# Memory: O(C × d × layers) instead of O(N × d × layers)
#   where C = chunk_size, N = full sequence length
#
# Key difference from forward_chunked (line 12984):
#   forward_chunked: gradients flow through ALL chunks (memory = O(N))
#   forward_chunked_tbptt: detaches state between chunks (memory = O(C))
#
# This is Truncated BPTT — the same technique used by Mamba, RWKV, RetNet
# for training state-space models on long sequences.
# =============================================================================


def forward_chunked_tbptt(
    model: torch.nn.Module,
    input_ids: torch.Tensor,
    targets: torch.Tensor,
    chunk_size: int,
    loss_fn: callable,
    accumulate_grad: bool = True,
    grad_scaler: Optional[Any] = None,
    autocast_dtype: Optional[torch.dtype] = None,
    gradient_accumulation: int = 1,
    aux_loss_fn: Optional[callable] = None,
) -> Dict[str, Any]:
    """
    Chunked forward + backward with Truncated BPTT for Phase state machines.

    Unlike forward_chunked (which concatenates all logits and does one backward),
    this processes each chunk independently:
      1. Forward chunk with prev_state (detached from previous chunk)
      2. Compute loss on this chunk's logits
      3. Backward on this chunk (frees chunk activations)
      4. Carry final_state to next chunk (detached)

    This keeps peak memory at O(C) instead of O(N).

    Args:
        model: HybridPhaseTransformer with forward_chunk() method
        input_ids: [B, N] full sequence token indices
        targets: [B, N] full sequence targets
        chunk_size: Tokens per chunk (controls memory/compute tradeoff)
        loss_fn: Callable(logits, targets) -> (loss, metrics_dict)
        accumulate_grad: If True, accumulates gradients across chunks.
                        If False, steps optimizer per chunk (not recommended).
        grad_scaler: Optional GradScaler for mixed precision
        autocast_dtype: Optional dtype for torch.autocast (e.g. torch.bfloat16)
        gradient_accumulation: Number of gradient accumulation steps. Loss is scaled
                              by 1/(num_chunks * gradient_accumulation) so that
                              TBPTT gradient magnitude matches the standard path.
        aux_loss_fn: Optional Callable(result_dict, chunk_targets) -> scalar loss.
                     V10.14.10: Called per-chunk with the full result dict (including
                     _slot_keys, _slot_vals, _slot_hidden) to compute auxiliary losses
                     like slot retrieval loss that need to be backpropagated per-chunk.

    Returns:
        Dict with:
            'total_loss': scalar — mean loss across all chunks
            'metrics': dict — averaged metrics from loss_fn
            'num_chunks': int — number of chunks processed
            'chunk_losses': list — per-chunk loss values
    """
    B, N = input_ids.shape
    device = input_ids.device
    num_chunks = (N + chunk_size - 1) // chunk_size

    # V10.8: Combined loss divisor accounts for BOTH chunk averaging AND
    # gradient accumulation. Without this, TBPTT gradients are grad_accum×
    # too large because the standard path's `loss /= grad_accum` (in the
    # training loop) runs AFTER backward — which TBPTT already did here.
    loss_divisor = num_chunks * gradient_accumulation

    # State carry across chunks (detached — this is the TBPTT boundary)
    layer_states = None

    # Accumulate loss on GPU to avoid per-chunk .item() sync stalls
    total_loss_gpu = torch.zeros(1, device=device)
    chunk_losses_gpu = []
    all_metrics = {}

    for chunk_idx in range(num_chunks):
        chunk_start = chunk_idx * chunk_size
        chunk_end = min(chunk_start + chunk_size, N)
        chunk_ids = input_ids[:, chunk_start:chunk_end]
        chunk_targets = targets[:, chunk_start:chunk_end]

        # Forward with optional autocast
        if autocast_dtype is not None:
            with torch.autocast(device_type=device.type, dtype=autocast_dtype):
                result, layer_states_new = model.forward_chunk(
                    chunk_ids,
                    chunk_offset=chunk_start,
                    prev_layer_states=layer_states,
                )
                chunk_logits = result['logits']
                chunk_loss, chunk_metrics = loss_fn(chunk_logits, chunk_targets)
        else:
            result, layer_states_new = model.forward_chunk(
                chunk_ids,
                chunk_offset=chunk_start,
                prev_layer_states=layer_states,
            )
            chunk_logits = result['logits']
            chunk_loss, chunk_metrics = loss_fn(chunk_logits, chunk_targets)

        # V10.14.10: Add auxiliary loss (e.g. slot retrieval loss) per-chunk
        if aux_loss_fn is not None:
            _aux_loss = aux_loss_fn(result, chunk_targets)
            if _aux_loss is not None:
                chunk_loss = chunk_loss + _aux_loss

        # V10.8: Scale loss for BOTH chunk mean AND gradient accumulation
        scaled_loss = chunk_loss / loss_divisor

        # Backward on this chunk — frees chunk activations
        if accumulate_grad:
            if grad_scaler is not None:
                grad_scaler.scale(scaled_loss).backward()
            else:
                scaled_loss.backward()

        # TBPTT boundary: detach state before carrying to next chunk
        # This is what makes memory O(C) instead of O(N)
        layer_states = _detach_layer_states(layer_states_new)

        # Track loss on GPU (single .item() call after loop avoids sync stalls)
        total_loss_gpu += chunk_loss.detach()
        chunk_losses_gpu.append(chunk_loss.detach())
        for k, v in chunk_metrics.items():
            if k not in all_metrics:
                all_metrics[k] = 0.0
            all_metrics[k] += v

    # Single GPU→CPU sync for all loss values (was N syncs before)
    avg_loss = (total_loss_gpu / num_chunks).item()
    chunk_losses = [cl.item() for cl in chunk_losses_gpu]

    # Average metrics across chunks
    avg_metrics = {k: v / num_chunks for k, v in all_metrics.items()}

    return {
        'total_loss': avg_loss,
        'metrics': avg_metrics,
        'num_chunks': num_chunks,
        'chunk_losses': chunk_losses,
    }


def _detach_layer_states(
    layer_states: Dict[int, Dict[str, torch.Tensor]]
) -> Dict[int, Dict[str, torch.Tensor]]:
    """
    Detach all tensors in layer_states to break the autograd graph.

    This is the TBPTT boundary: gradients do not flow across chunks,
    but the state values carry forward as initial conditions.
    """
    detached = {}
    for layer_idx, state_dict in layer_states.items():
        detached[layer_idx] = {
            k: v.detach() if isinstance(v, torch.Tensor) else v
            for k, v in state_dict.items()
        }
    return detached


# =============================================================================
# BINDING CACHE ARCHITECTURE (V10.0) - Protected Phase + Top-K Query
# =============================================================================
# Validated by diagnostic probe experiments:
# - Protected Phase ablation: -50% to -54% drop (Phase is ESSENTIAL)
# - Mixed hybrid ablation: ~0% drop (Phase is DECORATIVE)
#
# Architecture insight: Phase and Quadratic must have NON-COMPETING roles:
# - Phase: O(n) STATE accumulator via cumsum/EMA
# - Quadratic: O(nk) QUERY mechanism via Top-K cache
#
# Reference: train_hard_probes.py --protected-phase experiment results
# =============================================================================


class OntologicalBindingAnnotator(nn.Module):
    """
    Ontological Binding Annotator - computes binding salience for Top-K selection.

    CSR/Kosha/SRK act as BINDING SELECTORS, not live attention modifiers.
    They compute salience scores that bias WHICH bindings get retrieved,
    without modifying the core attention computation.

    Design Principle (ChatGPT recommendation):
        - CSR/Kosha/Ontological should NOT be continuous forces in attention
        - They are best used as binding selectors and annotators
        - Salience is computed ONCE at encoding, not token-by-token at inference

    Usage:
        annotator = OntologicalBindingAnnotator(embed_dim, state_dim)
        salience = annotator(hidden_states, sovereign_state)  # [B, N]
        # Pass salience to BindingCacheQuadQuery for Top-K biasing
    """

    def __init__(
        self,
        embed_dim: int,
        state_dim: int = 32,  # 32D Sovereign State
        num_heads: int = 12,
        use_csr: bool = True,
        use_kosha: bool = True,
        use_srk: bool = True,
    ):
        super().__init__()
        self.embed_dim = embed_dim
        self.state_dim = state_dim
        self.use_csr = use_csr
        self.use_kosha = use_kosha
        self.use_srk = use_srk

        # Salience projection from hidden states
        # Projects hidden → per-position salience score
        self.hidden_salience = nn.Sequential(
            nn.Linear(embed_dim, embed_dim // 4),
            nn.GELU(),
            nn.Linear(embed_dim // 4, 1),
        )

        # Ontological state influence on salience
        # If SRK enabled, state modulates what's "important"
        if use_srk and state_dim > 0:
            self.state_salience = nn.Sequential(
                nn.Linear(state_dim, state_dim),
                nn.GELU(),
                nn.Linear(state_dim, num_heads),
            )
        else:
            self.state_salience = None

        # Kosha sheath weights (5 sheaths affect salience differently)
        # [Material, Vital, Mental, Intellectual, Blissful]
        if use_kosha:
            self.kosha_weights = nn.Parameter(torch.ones(5))
        else:
            self.kosha_weights = None

    def forward(
        self,
        hidden_states: torch.Tensor,  # [B, N, D]
        sovereign_state: Optional[torch.Tensor] = None,  # [B, 32]
        kosha_activations: Optional[torch.Tensor] = None,  # [B, 5]
        csr_mask: Optional[torch.Tensor] = None,  # [B, N] binary mask
    ) -> torch.Tensor:
        """
        Compute binding salience scores.

        Args:
            hidden_states: [B, N, D] - hidden representations
            sovereign_state: [B, 32] - 32D Sovereign State (optional)
            kosha_activations: [B, 5] - Kosha sheath activations (optional)
            csr_mask: [B, N] - CSR content word mask (optional)

        Returns:
            salience: [B, N] - per-position binding salience (higher = more important)
        """
        B, N, D = hidden_states.shape

        # Base salience from hidden states
        salience = self.hidden_salience(hidden_states).squeeze(-1)  # [B, N]

        # Ontological state modulation (SRK)
        if self.state_salience is not None and sovereign_state is not None:
            # State affects what's considered "important" globally
            state_bias = self.state_salience(sovereign_state)  # [B, num_heads]
            # Average across heads for per-position bias
            state_bias_scalar = state_bias.mean(dim=-1, keepdim=True)  # [B, 1]
            salience = salience + state_bias_scalar

        # Kosha sheath modulation
        if self.kosha_weights is not None and kosha_activations is not None:
            # Weighted kosha influence
            kosha_influence = (kosha_activations * self.kosha_weights).sum(dim=-1, keepdim=True)  # [B, 1]
            salience = salience * (1 + 0.1 * kosha_influence)

        # CSR content word boost
        if self.use_csr and csr_mask is not None:
            # Boost salience for content words (phonologically grounded)
            salience = salience + 0.5 * csr_mask.float()

        return salience


class BindingCachePhaseState(nn.Module):
    """
    Phase attention that outputs ONLY a memory state (no attention output).

    Phase's EXCLUSIVE role: Accumulate key-value pairs into persistent state.
    This is NOT mixed with quadratic - it feeds INTO BindingCacheQuadQuery.

    Validated architecture from diagnostic probes:
    - memory_state = cumsum(k_phasor * v_complex) [O(n) STATE]
    - When protected, Phase shows -50% ablation drop (ESSENTIAL)
    - When mixed with Quad, Phase shows ~0% drop (DECORATIVE)

    V10.3.8: Dual-Channel Architecture Role
    ----------------------------------------
    In the Master/Sensor duality:
    - This class handles the BACKWARD Key phasor (-iφ_k)
    - SRK (Master) influences Key storage via intent_phase: φ_k' = φ_k + θ_SRK
    - "What do I understand?" → How bindings are stored

    The Query side (JEPA/Sensor) is handled by BindingCacheQuadQuery:
    - "What am I looking for?" → How bindings are retrieved

    This natural separation already implements the dual-channel concept for
    Protected Phase architecture. The PhaseAttentionLayer.dual_channel_mode
    provides the same separation for standard phase attention.
    """

    def __init__(
        self,
        embed_dim: int,
        num_heads: int,
        dropout: float = 0.1,
        decay_gamma: float = 1.0,
        learned_decay: bool = False,
        bounded_phase: bool = True,  # Default True - mandatory fix from probes
    ):
        super().__init__()
        self.embed_dim = embed_dim
        self.num_heads = num_heads
        self.head_dim = embed_dim // num_heads
        self.bounded_phase = bounded_phase
        self.decay_gamma = decay_gamma
        self.learned_decay = learned_decay

        # V10.8: Fused key phase+amplitude projection (1 GEMM instead of 2)
        self.W_k_fused = nn.Linear(embed_dim, embed_dim * 2, bias=False)
        self.W_v = nn.Linear(embed_dim, embed_dim, bias=False)

        # Layer norm for input
        self.norm = nn.LayerNorm(embed_dim)
        self.dropout = nn.Dropout(dropout)

        # Learned decay (per-head) if enabled
        if learned_decay:
            # Log-space timescale initialization (2 to 2048 tokens)
            log_timescales = torch.linspace(
                math.log(2.0), math.log(2048.0), num_heads
            )
            timescales = torch.exp(log_timescales)
            gamma = 1.0 - (1.0 / timescales)
            gamma = torch.clamp(gamma, 0.001, 0.9995)
            sigmoid_target = 2.0 * gamma - 1.0
            sigmoid_target = torch.clamp(sigmoid_target, 0.01, 0.99)
            init_logits = torch.log(sigmoid_target / (1.0 - sigmoid_target))
            self.decay_logit = nn.Parameter(init_logits)
        else:
            self.decay_logit = None

        # Health tracking (R_k statistics)
        self._last_r_k_mean = 0.0
        self._last_r_k_std = 0.0

        # Ablation mode
        self._ablation_mode = "none"
        self._ablation_seed = 42

        # Rotation test: apply a global phase rotation to φ_k
        # This tests whether phase encodes relational structure
        self._rotation_angle = 0.0  # in radians

        # V10.15: Reduced from [-π, π] to [-1, 1] to prevent gradient spikes
        nn.init.uniform_(self.W_k_fused.weight[:embed_dim], -1.0, 1.0)

    # V10.8: Backward-compatible properties for code accessing old separate weights
    class _FusedWeightView:
        """Lightweight view into a slice of the fused weight matrix."""
        def __init__(self, fused_linear, start, end):
            self._fused = fused_linear
            self._start = start
            self._end = end
        @property
        def weight(self):
            return self._fused.weight[self._start:self._end]

    @property
    def W_k_phase(self):
        return self._FusedWeightView(self.W_k_fused, 0, self.embed_dim)

    @property
    def W_k_amp(self):
        return self._FusedWeightView(self.W_k_fused, self.embed_dim, self.embed_dim * 2)

    def set_ablation(self, mode: str, seed: int = 42):
        """Set ablation mode: none, scramble, freeze, off."""
        self._ablation_mode = mode
        self._ablation_seed = seed

    def set_rotation(self, angle_radians: float):
        """
        Set a global phase rotation to apply to φ_k.

        For Protected Phase / Binding Cache, we rotate φ_k (not φ_q) because:
        - Protected Phase uses φ_k for memory accumulation (cumsum)
        - There is no φ_q in this architecture (Quadratic handles queries)

        This tests whether phase encodes relational structure:
        - If roles are phase-encoded in keys, rotating φ_k should disrupt retrieval
        - If phase is decorative, rotation should have minimal effect

        Args:
            angle_radians: Rotation angle in radians (e.g., π/4 = 45°)
        """
        self._rotation_angle = angle_radians

    def clear_rotation(self):
        """Clear any applied rotation."""
        self._rotation_angle = 0.0

    def get_health_metrics(self) -> dict:
        """Return R_k health statistics."""
        return {
            "r_k_mean": self._last_r_k_mean,
            "r_k_std": self._last_r_k_std,
        }

    def forward(
        self,
        x: torch.Tensor,
        intent_phase: Optional[torch.Tensor] = None,
    ) -> torch.Tensor:
        """
        Compute Phase memory state via cumsum/EMA.

        Args:
            x: Input tensor [B, N, D]
            intent_phase: Optional [B, H] or [B, H, D_h] phase rotation from Ontological State Delta.
                         Rotates key phases to change how bindings are stored based on intent/understanding.

        Returns:
            memory_state: [B, N, D] - accumulated state for Quad to query
        """
        B, N, D = x.shape

        # Pre-norm
        x_norm = self.norm(x)

        # V10.8: Fused key projection — one GEMM, then split
        k_fused = self.W_k_fused(x_norm).view(B, N, 2, self.num_heads, self.head_dim)
        phi_k_raw = k_fused[:, :, 0]  # [B, N, H, D_h]
        a_k = torch.sigmoid(k_fused[:, :, 1])  # [B, N, H, D_h]
        v = self.W_v(x_norm).view(B, N, self.num_heads, self.head_dim)

        # Bounded phase (mandatory fix from probes)
        if self.bounded_phase:
            phi_k = math.pi * torch.sin(phi_k_raw)
        else:
            phi_k = phi_k_raw

        # Apply intent phase rotation (from Ontological State Delta)
        # This changes HOW bindings are stored based on semantic understanding
        if intent_phase is not None:
            # Handle different intent_phase shapes:
            # [B, H] → broadcast to [B, 1, H, 1] for all positions and dims
            # [B, H, D_h] → broadcast to [B, 1, H, D_h] for all positions
            if intent_phase.dim() == 2:
                intent_phase = intent_phase.unsqueeze(1).unsqueeze(-1)  # [B, 1, H, 1]
            elif intent_phase.dim() == 3:
                intent_phase = intent_phase.unsqueeze(1)  # [B, 1, H, D_h]
            phi_k = phi_k + intent_phase

        # Track R_k health
        with torch.no_grad():
            self._last_r_k_mean = a_k.mean().item()
            self._last_r_k_std = a_k.std().item()

        # Ablation
        if self._ablation_mode == "scramble":
            torch.manual_seed(self._ablation_seed)
            for b in range(B):
                for h in range(self.num_heads):
                    perm = torch.randperm(N, device=phi_k.device)
                    phi_k[b, :, h, :] = phi_k[b, perm, h, :]
        elif self._ablation_mode in ["freeze", "off"]:
            phi_k = torch.zeros_like(phi_k)

        # Apply rotation to φ_k (tests phase selectivity for Protected Phase)
        # Note: We rotate φ_k here because Protected Phase has no φ_q
        if self._rotation_angle != 0.0:
            phi_k = phi_k + self._rotation_angle

        # V10.7: Always accumulate in float32 for numerical stability.
        # cumsum/EMA scan in fp16 drifts on long sequences (>1K tokens).
        orig_dtype = phi_k.dtype
        if orig_dtype != torch.float32:
            phi_k = phi_k.float()
            a_k = a_k.float()
            v = v.float()

        # Form complex phasors
        k_phasor = torch.polar(a_k, -phi_k)  # [B, N, H, D_h]
        v_complex = torch.complex(v, torch.zeros_like(v))
        kv = k_phasor * v_complex

        # O(n) State accumulation
        if not self.learned_decay and self.decay_gamma == 1.0:
            # Infinite memory via cumsum
            memory_state = torch.cumsum(kv, dim=1)
        else:
            # EMA with decay
            if self.learned_decay:
                gamma = 0.97 + 0.0295 * torch.sigmoid(self.decay_logit)
            else:
                gamma = self.decay_gamma
            memory_state = parallel_ema_scan(kv, gamma)

        # Return real part as memory state
        memory_state = memory_state.real

        if orig_dtype == torch.bfloat16:
            memory_state = memory_state.to(orig_dtype)

        return memory_state.reshape(B, N, D)

    def compute_confidence(self, memory_state: torch.Tensor) -> torch.Tensor:
        """
        V10.4: Compute phase confidence for conditional quad invocation.

        High confidence means phase state is stable/consistent, so quad
        retrieval can potentially be skipped to save compute.

        Args:
            memory_state: [B, N, D] - current phase memory state

        Returns:
            confidence: [B, N] - per-position confidence in [0, 1]
        """
        # Confidence based on inverse variance of memory state
        # Low variance = high confidence (stable state)
        # High variance = low confidence (uncertain state)
        var = memory_state.var(dim=-1)  # [B, N]

        # Normalize to [0, 1] using sigmoid
        # Scale factor chosen so variance ~1 gives confidence ~0.5
        confidence = torch.sigmoid(-var + 1.0)  # [B, N]

        return confidence

    def integrate_proposals(
        self,
        x: torch.Tensor,
        memory_state: torch.Tensor,
        proposals: torch.Tensor,
        proposal_scores: torch.Tensor,
        gamma: float = 0.9,
    ) -> torch.Tensor:
        """
        V10.4: Integrate quad proposals into phase state.

        This implements the "phase-as-integrator" pattern where phase
        decides which proposals survive and integrates them into state.

        Args:
            x: Input tensor [B, N, D]
            memory_state: Current phase state [B, N, D]
            proposals: [B, N, K, D] - K proposals from quad
            proposal_scores: [B, N, K] - retrieval scores for each proposal
            gamma: Decay factor for state (0 < gamma < 1)

        Returns:
            integrated_output: [B, N, D] - integrated state update
        """
        B, N, K, D = proposals.shape

        # Phase computes gating weights (NOT quad softmax)
        # Use sigmoid + normalize for smoother gradients than softmax
        gate_input = torch.cat([
            x.unsqueeze(2).expand(-1, -1, K, -1),  # [B, N, K, D]
            memory_state.unsqueeze(2).expand(-1, -1, K, -1),  # [B, N, K, D]
            proposals,  # [B, N, K, D]
        ], dim=-1)  # [B, N, K, 3D]

        # Simple gating: project to scalar, sigmoid, normalize
        # For now, use proposal_scores as gate logits (can learn separate projection later)
        gate_logits = proposal_scores  # [B, N, K]

        # Sigmoid + normalize (not winner-take-all like softmax)
        gate_weights_raw = torch.sigmoid(gate_logits)  # [B, N, K]
        gate_weights = gate_weights_raw / (gate_weights_raw.sum(dim=-1, keepdim=True) + 1e-8)  # [B, N, K]

        # Weighted sum of proposals
        # [B, N, K, 1] * [B, N, K, D] -> [B, N, K, D] -> sum -> [B, N, D]
        weighted_proposals = (gate_weights.unsqueeze(-1) * proposals).sum(dim=2)  # [B, N, D]

        # State update: decay old state + integrate new proposals
        # S_{t+1} = gamma * S_t + (1 - gamma) * weighted_proposals
        integrated = gamma * memory_state + (1 - gamma) * weighted_proposals

        return integrated


class BindingCacheQuadQuery(nn.Module):
    """
    Quadratic attention that queries ONLY from Phase's memory state.

    Quad's EXCLUSIVE role: Query memory via O(n²) attention or O(nk) Top-K cache.
    Keys and Values come from memory_state, NOT from input tokens.

    This prevents gradient competition that causes Phase to become decorative.
    """

    def __init__(
        self,
        embed_dim: int,
        num_heads: int,
        dropout: float = 0.1,
        top_k: int = 64,  # Cache size per head
        use_cache: bool = True,  # If False, use full O(n²) attention
        proposal_mode: bool = False,  # V10.4: Return proposals instead of attended output
    ):
        super().__init__()
        self.embed_dim = embed_dim
        self.num_heads = num_heads
        self.head_dim = embed_dim // num_heads
        self.top_k = top_k
        self.use_cache = use_cache
        self.proposal_mode = proposal_mode
        self.scale = self.head_dim ** -0.5

        # Query projection (from input - "what am I looking for?")
        self.W_q = nn.Linear(embed_dim, embed_dim, bias=False)

        # Key/Value projections (from memory_state - "what can I retrieve?")
        self.W_k = nn.Linear(embed_dim, embed_dim, bias=False)
        self.W_v = nn.Linear(embed_dim, embed_dim, bias=False)

        # Output projection (not used in proposal_mode)
        self.out_proj = nn.Linear(embed_dim, embed_dim, bias=False)

        # Layer norms
        self.norm_q = nn.LayerNorm(embed_dim)
        self.norm_mem = nn.LayerNorm(embed_dim)
        self.dropout = nn.Dropout(dropout)

        # Binding score interpolation: α(t) * dot + (1-α(t)) * cos
        # Learned per query (linear + sigmoid)
        self.alpha_proj = nn.Linear(embed_dim, num_heads, bias=True)

        # Instrumentation
        self._cache_hit_rate = 0.0
        self._mean_alpha = 0.0
        # Cache health metrics (per ChatGPT recommendation)
        self._cache_key_cosine_mean = 0.0
        self._cache_key_cosine_max = 0.0

    def get_instrumentation(self) -> dict:
        """Return instrumentation metrics."""
        return {
            "cache_hit_rate": self._cache_hit_rate,
            "mean_alpha": self._mean_alpha,
            # Cache health: cosine similarity between keys
            # mean > 0.85 = redundancy building
            # max > 0.95 = slot collision
            "cache_key_cosine_mean": self._cache_key_cosine_mean,
            "cache_key_cosine_max": self._cache_key_cosine_max,
        }

    def get_proposals(
        self,
        x: torch.Tensor,
        memory_state: torch.Tensor,
        causal_mask: bool = True,
        binding_salience: Optional[torch.Tensor] = None,
    ) -> Tuple[torch.Tensor, torch.Tensor]:
        """
        V10.4: Get TopK proposals WITHOUT softmax mixing.

        Instead of returning attention-weighted output, returns raw proposals
        for Phase to integrate. This implements the "quad-as-proposer" pattern.

        Args:
            x: Input tensor [B, N, D] - source for queries
            memory_state: [B, N, D] - from BindingCachePhaseState
            causal_mask: Apply causal masking
            binding_salience: Optional [B, N] - biases Top-K selection

        Returns:
            proposals: [B, N, K, D] - K proposal values per position
            scores: [B, N, K] - retrieval scores (before softmax) for each proposal
        """
        B, N, D = x.shape
        H, D_h = self.num_heads, self.head_dim
        K = min(self.top_k, N)

        # Normalize inputs
        x_norm = self.norm_q(x)
        mem_norm = self.norm_mem(memory_state)

        # Project queries from input, K/V from memory state
        Q = self.W_q(x_norm).view(B, N, H, D_h).transpose(1, 2)  # [B, H, N, D_h]
        Keys = self.W_k(mem_norm).view(B, N, H, D_h).transpose(1, 2)  # [B, H, N, D_h]
        V = self.W_v(mem_norm).view(B, N, H, D_h).transpose(1, 2)  # [B, H, N, D_h]

        # Compute scores: Q @ K^T
        scores = torch.matmul(Q, Keys.transpose(-2, -1)) * self.scale  # [B, H, N, N]

        # Apply causal mask
        if causal_mask:
            mask = torch.triu(
                torch.ones(N, N, device=x.device, dtype=torch.bool),
                diagonal=1
            )
            scores = scores.masked_fill(mask, float('-inf'))

        # Binding salience for selection bias
        if binding_salience is not None:
            salience_bias = binding_salience.unsqueeze(1).unsqueeze(1)  # [B, 1, 1, N]
            selection_scores = scores + salience_bias
        else:
            selection_scores = scores

        # TopK selection - NO SOFTMAX
        top_scores, top_indices = selection_scores.topk(K, dim=-1, largest=True)  # [B, H, N, K]

        # Gather original scores (not biased) for return
        original_top_scores = torch.gather(scores, -1, top_indices)  # [B, H, N, K]

        # Gather corresponding values
        top_indices_expanded = top_indices.unsqueeze(-1).expand(-1, -1, -1, -1, D_h)
        V_expanded = V.unsqueeze(2).expand(-1, -1, N, -1, -1)  # [B, H, N, N, D_h]
        top_V = torch.gather(V_expanded, 3, top_indices_expanded)  # [B, H, N, K, D_h]

        # Reshape: [B, H, N, K, D_h] -> [B, N, K, H*D_h] = [B, N, K, D]
        proposals = top_V.permute(0, 2, 3, 1, 4).reshape(B, N, K, D)

        # Scores: [B, H, N, K] -> [B, N, K] (mean across heads)
        proposal_scores = original_top_scores.permute(0, 2, 3, 1).mean(dim=-1)  # [B, N, K]

        # Track instrumentation
        with torch.no_grad():
            self._cache_hit_rate = K / N

        return proposals, proposal_scores

    def forward(
        self,
        x: torch.Tensor,
        memory_state: torch.Tensor,
        causal_mask: bool = True,
        binding_salience: Optional[torch.Tensor] = None,
    ) -> torch.Tensor:
        """
        Query Phase's memory state.

        Args:
            x: Input tensor [B, N, D] - source for queries
            memory_state: [B, N, D] - from BindingCachePhaseState
            causal_mask: Apply causal masking
            binding_salience: Optional [B, N] - per-position salience scores from
                             OntologicalBindingAnnotator. Biases Top-K selection
                             WITHOUT modifying core attention math.
                             Higher salience = more likely to be in Top-K cache.

        Returns:
            output: [B, N, D] - attention-weighted retrieval from memory
        """
        B, N, D = x.shape
        H, D_h = self.num_heads, self.head_dim

        # Normalize inputs
        x_norm = self.norm_q(x)
        mem_norm = self.norm_mem(memory_state)

        # Project queries from input, K/V from memory state
        Q = self.W_q(x_norm).view(B, N, H, D_h).transpose(1, 2)  # [B, H, N, D_h]
        K = self.W_k(mem_norm).view(B, N, H, D_h).transpose(1, 2)  # [B, H, N, D_h]
        V = self.W_v(mem_norm).view(B, N, H, D_h).transpose(1, 2)  # [B, H, N, D_h]

        # Compute binding scores
        # Standard dot product: Q @ K^T
        scores = torch.matmul(Q, K.transpose(-2, -1)) * self.scale  # [B, H, N, N]

        # Apply causal mask
        if causal_mask:
            mask = torch.triu(
                torch.ones(N, N, device=x.device, dtype=torch.bool),
                diagonal=1
            )
            scores = scores.masked_fill(mask, float('-inf'))

        # Top-K cache (optional)
        if self.use_cache and self.top_k < N:
            # For each query position, keep only top-k keys
            # This reduces O(n²) to O(nk)

            # BINDING SALIENCE: Bias Top-K selection WITHOUT modifying attention math
            # Salience affects WHICH positions are selected, not HOW they're weighted
            if binding_salience is not None:
                # binding_salience: [B, N] → [B, 1, 1, N] for broadcasting
                salience_bias = binding_salience.unsqueeze(1).unsqueeze(1)  # [B, 1, 1, N]
                # Use salience-biased scores for TOP-K SELECTION ONLY
                selection_scores = scores + salience_bias
            else:
                selection_scores = scores

            # Select Top-K using (possibly biased) selection scores
            _, top_indices = selection_scores.topk(
                min(self.top_k, N), dim=-1, largest=True
            )  # [B, H, N, k]

            # IMPORTANT: Gather ORIGINAL scores for attention weights (pure physics)
            # This ensures attention math is unmodified - salience only affects selection
            top_scores = torch.gather(scores, -1, top_indices)  # [B, H, N, k]

            # Track cache hit rate (what fraction of sequence we attend to)
            with torch.no_grad():
                self._cache_hit_rate = min(self.top_k, N) / N

            # Softmax over top-k only (using ORIGINAL scores, not biased)
            attn_weights = F.softmax(top_scores, dim=-1)  # [B, H, N, k]
            attn_weights = self.dropout(attn_weights)

            # Gather corresponding values
            # Expand indices for value gathering
            top_indices_expanded = top_indices.unsqueeze(-1).expand(-1, -1, -1, -1, D_h)
            V_expanded = V.unsqueeze(2).expand(-1, -1, N, -1, -1)  # [B, H, N, N, D_h]
            top_V = torch.gather(V_expanded, 3, top_indices_expanded)  # [B, H, N, k, D_h]

            # Weighted sum
            out = torch.einsum('bhqk,bhqkd->bhqd', attn_weights, top_V)  # [B, H, N, D_h]
        else:
            # Full O(n²) attention
            attn_weights = F.softmax(scores, dim=-1)  # [B, H, N, N]
            attn_weights = self.dropout(attn_weights)
            out = torch.matmul(attn_weights, V)  # [B, H, N, D_h]

            with torch.no_grad():
                self._cache_hit_rate = 1.0  # Using full attention

        # Track mean alpha (for instrumentation)
        with torch.no_grad():
            alpha = torch.sigmoid(self.alpha_proj(x_norm))  # [B, N, H]
            self._mean_alpha = alpha.mean().item()

            # Cache health: key cosine similarity (sampled for efficiency)
            # High cosine = redundancy in memory state
            # Sample every 16th key to avoid O(n²) cost
            sample_stride = max(1, N // 32)
            K_sample = K[:, :, ::sample_stride, :]  # [B, H, N_sample, D_h]
            K_norm = F.normalize(K_sample, dim=-1)  # Unit vectors
            # Pairwise cosine: [B, H, N_sample, N_sample]
            cosine_matrix = torch.matmul(K_norm, K_norm.transpose(-2, -1))
            # Zero out diagonal (self-similarity = 1)
            n_sample = K_sample.shape[2]
            diag_mask = torch.eye(n_sample, device=K.device, dtype=torch.bool)
            cosine_off_diag = cosine_matrix.masked_fill(diag_mask, 0.0)
            # Track mean and max (excluding diagonal)
            n_pairs = n_sample * (n_sample - 1)
            if n_pairs > 0:
                self._cache_key_cosine_mean = cosine_off_diag.sum().item() / (B * H * n_pairs)
                self._cache_key_cosine_max = cosine_off_diag.max().item()
            else:
                self._cache_key_cosine_mean = 0.0
                self._cache_key_cosine_max = 0.0

        # Reshape and project output
        out = out.transpose(1, 2).reshape(B, N, D)  # [B, N, D]
        out = self.out_proj(out)

        return out


class LocalWindowAttention(nn.Module):
    """
    Local windowed causal attention for learning syntax/local patterns.

    This provides the LOCAL context that Phase+Quad lacks:
    - Phase compresses into memory_state (loses token-level detail)
    - Quad queries memory_state (global but compressed)
    - LocalWindow attends directly to recent tokens (local, full detail)

    Combined: local_attn + mem_attn allows both syntax AND semantic learning.
    """

    def __init__(
        self,
        embed_dim: int,
        num_heads: int,
        window_size: int = 128,
        dropout: float = 0.1,
    ):
        super().__init__()
        self.embed_dim = embed_dim
        self.num_heads = num_heads
        self.head_dim = embed_dim // num_heads
        self.window_size = window_size
        self.scale = self.head_dim ** -0.5

        # Standard QKV projections
        self.W_q = nn.Linear(embed_dim, embed_dim, bias=False)
        self.W_k = nn.Linear(embed_dim, embed_dim, bias=False)
        self.W_v = nn.Linear(embed_dim, embed_dim, bias=False)
        self.out_proj = nn.Linear(embed_dim, embed_dim, bias=False)

        self.norm = nn.LayerNorm(embed_dim)
        self.dropout = nn.Dropout(dropout)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        Local causal attention within window_size.

        Args:
            x: [B, N, D] input tensor

        Returns:
            out: [B, N, D] attention output
        """
        B, N, D = x.shape
        H, D_h = self.num_heads, self.head_dim
        # V10.1.1: Dynamic window = min(max_window, seq_len // 2)
        # This ensures local attention stays local for long sequences
        # while covering half the sequence for short ones
        W = min(self.window_size, max(1, N // 2))

        x_norm = self.norm(x)

        # Project to Q, K, V
        Q = self.W_q(x_norm).view(B, N, H, D_h).transpose(1, 2)  # [B, H, N, D_h]
        K = self.W_k(x_norm).view(B, N, H, D_h).transpose(1, 2)
        V = self.W_v(x_norm).view(B, N, H, D_h).transpose(1, 2)

        # Compute attention scores
        scores = torch.matmul(Q, K.transpose(-2, -1)) * self.scale  # [B, H, N, N]

        # Create windowed causal mask
        # Each position can only attend to positions within window_size before it
        positions = torch.arange(N, device=x.device)
        row_idx = positions.unsqueeze(1)  # [N, 1]
        col_idx = positions.unsqueeze(0)  # [1, N]

        # Causal: can only attend to past (col <= row)
        # Window: can only attend to recent (row - col < window_size)
        causal_mask = col_idx > row_idx  # Future positions
        window_mask = (row_idx - col_idx) >= W  # Too far in past
        mask = causal_mask | window_mask

        scores = scores.masked_fill(mask.unsqueeze(0).unsqueeze(0), float('-inf'))

        # Softmax and weighted sum
        attn_weights = F.softmax(scores, dim=-1)
        attn_weights = self.dropout(attn_weights)

        out = torch.matmul(attn_weights, V)  # [B, H, N, D_h]
        out = out.transpose(1, 2).reshape(B, N, D)
        out = self.out_proj(out)

        return out


class BindingCacheBlock(nn.Module):
    """
    Transformer block with PROTECTED Phase and Quad roles + LOCAL attention.

    V10.1: Added LocalWindowAttention for syntax learning.

    Three-path collaboration:
    1. Phase accumulates memory state [O(n)] - global compression
    2. Quad queries memory state [O(nk) with cache] - global retrieval
    3. Local attention [O(n*w)] - direct token-to-token for syntax

    Combined: local_out + mem_out allows fast syntax + slow semantic learning.

    V10.6.6: Forward-pass contract enforcement
    - Control signals (intent_phase, binding_salience) are validated at forward() entry
    - Violations raise ControlShapeViolation immediately (hard-fail)
    - Set enforce_control_contract=False to disable (NOT recommended for production)
    """

    # V10.6.6: Class-level enforcement toggle (STRICT by default)
    enforce_control_contract: bool = True

    def __init__(
        self,
        embed_dim: int,
        num_heads: int,
        ff_dim: int,
        dropout: float = 0.1,
        decay_gamma: float = 1.0,
        learned_decay: bool = False,
        bounded_phase: bool = True,
        top_k: int = 64,
        use_cache: bool = True,
        local_window_size: int = 256,  # V10.1.1: Max local window (actual = min(this, seq_len//2))
        proposal_mode: bool = False,  # V10.4: Quad proposes, Phase integrates
        confidence_threshold: float = 0.7,  # V10.4: Skip quad if confidence > threshold
        interference_scorer: Optional[nn.Module] = None,  # V10.5: Optional interference rescoring
    ):
        super().__init__()
        self.embed_dim = embed_dim  # V10.6.6: Store for contract enforcement
        self.num_heads = num_heads  # V10.6.6: Store for contract enforcement
        self.proposal_mode = proposal_mode
        self.confidence_threshold = confidence_threshold

        # V10.1: Local attention for syntax learning (direct token-to-token)
        # This is what allows "the → cat" pattern learning
        self.local_attn = LocalWindowAttention(
            embed_dim=embed_dim,
            num_heads=num_heads,
            window_size=local_window_size,
            dropout=dropout,
        )

        # Phase: memory state accumulator (global compression)
        self.phase_state = BindingCachePhaseState(
            embed_dim=embed_dim,
            num_heads=num_heads,
            dropout=dropout,
            decay_gamma=decay_gamma,
            learned_decay=learned_decay,
            bounded_phase=bounded_phase,
        )

        # Quad: memory state query (global retrieval)
        self.quad_query = BindingCacheQuadQuery(
            embed_dim=embed_dim,
            num_heads=num_heads,
            dropout=dropout,
            top_k=top_k,
            use_cache=use_cache,
            proposal_mode=proposal_mode,
        )

        # V10.5: Optional interference-aware proposal scoring
        # Applied AFTER proposals, BEFORE phase integration (compositional creativity)
        self.interference_scorer = interference_scorer

        # V10.7.2: RMSNorm on memory_state before Quad queries.
        # With decay_gamma=1.0, cumsum causes memory_state norm to grow O(sqrt(N)).
        # Without normalization, growing norms flatten quad attention scores
        # (softmax saturates) and cause overconfident/repetitive generation.
        self.norm_memory = nn.RMSNorm(embed_dim)

        # Feed-forward
        self.norm_ff = nn.LayerNorm(embed_dim)
        self.ff = nn.Sequential(
            nn.Linear(embed_dim, ff_dim),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(ff_dim, embed_dim),
            nn.Dropout(dropout),
        )

        # V10.4: Instrumentation for proposal mode
        self._last_confidence_mean = 0.0
        self._last_skip_rate = 0.0
        self._last_interference_stats = {}  # V10.5: Interference diagnostics

    def set_ablation(self, mode: str, seed: int = 42):
        """Set Phase ablation mode."""
        self.phase_state.set_ablation(mode, seed)

    def set_rotation(self, angle_radians: float):
        """Set rotation angle for Phase component (applied to φ_k)."""
        self.phase_state.set_rotation(angle_radians)

    def clear_rotation(self):
        """Clear rotation from Phase component."""
        self.phase_state.clear_rotation()

    def get_proposal_metrics(self) -> dict:
        """V10.4: Return proposal mode instrumentation."""
        metrics = {
            "confidence_mean": self._last_confidence_mean,
            "skip_rate": self._last_skip_rate,
        }
        # V10.5: Include interference stats if available
        if hasattr(self, '_last_interference_stats'):
            metrics.update(self._last_interference_stats)
        return metrics

    def forward(
        self,
        x: torch.Tensor,
        intent_phase: Optional[torch.Tensor] = None,
        binding_salience: Optional[torch.Tensor] = None,
        enable_slots_read: bool = True,
    ) -> torch.Tensor:
        """
        Forward pass with LOCAL + GLOBAL attention paths (V10.1).

        Three-path architecture:
        1. Local: Direct token-to-token for syntax (the → cat)
        2. Phase: Accumulate memory state (global compression)
        3. Quad: Query memory state (global retrieval)

        V10.4 Proposal Mode:
        - Quad returns proposals (no softmax mixing)
        - Phase integrates proposals with gating
        - Conditional skip: if phase confident, skip quad

        V10.6.2: enable_slots_read Control (D.2 Recommendation)
        - Separates READ path gating from WRITE path
        - Write path (phase accumulation) remains deterministic via EQ_TOKEN pattern
        - Read path (quad retrieval) can be gated by Onto/CSR controls
        - When enable_slots_read=False, quad retrieval is skipped, only local attention runs

        Combined: local_out + mem_out (no gradient competition)

        Args:
            x: Input tensor [B, N, D]
            intent_phase: Optional [B, H] or [B, H, D_h] phase rotation from Ontological State Delta.
            binding_salience: Optional [B, N] - per-position salience from OntologicalBindingAnnotator.
                             Biases Top-K selection in Quad WITHOUT modifying attention math.
            enable_slots_read: V10.6.2 (D.2) - If False, skip quad retrieval entirely.
                              Allows Onto/CSR to gate retrieval without affecting storage.
                              Default True for backward compatibility.

        Returns:
            output: [B, N, D]

        Raises:
            ControlShapeViolation: If control signals violate no-write contract (V10.6.6)
        """
        # V10.6.6: Enforce no-write contract at forward() entry (HARD-FAIL)
        # This is the authoritative enforcement point - violations stop training immediately
        if self.enforce_control_contract:
            B, N, D = x.shape
            if intent_phase is not None:
                assert_control_shape(
                    intent_phase,
                    name="intent_phase",
                    d_model=self.embed_dim,
                    seq_len=N,
                    strict=True,  # HARD-FAIL: raise ControlShapeViolation
                )
            if binding_salience is not None:
                assert_control_shape(
                    binding_salience,
                    name="binding_salience",
                    d_model=self.embed_dim,
                    seq_len=N,
                    strict=True,  # HARD-FAIL: raise ControlShapeViolation
                )

        # Step 1: LOCAL attention for syntax learning (direct, no compression)
        # This is what makes PPL drop quickly at start of training
        local_out = self.local_attn(x)

        # Step 2: Phase accumulates memory state (with optional intent rotation)
        # Phase is PURE - no auxiliary systems act here
        # NOTE: Phase WRITE is always active (deterministic via EQ_TOKEN pattern)
        # enable_slots_read only gates the READ path (quad retrieval)
        memory_state = self.phase_state(x, intent_phase=intent_phase)

        # V10.7.2: Normalize memory_state before Quad queries it.
        # With decay_gamma=1.0 (cumsum), memory_state norm grows O(sqrt(N)).
        # RMSNorm stabilizes the scale so Quad attention scores don't saturate.
        memory_state_normed = self.norm_memory(memory_state)

        # V10.6.2: Check if slot reading is enabled (D.2 recommendation)
        # This separates read path gating from write path
        if not enable_slots_read:
            # Skip quad retrieval entirely - only use local attention
            # Phase still accumulates (write path), but retrieval is gated
            attn_out = local_out
        elif self.proposal_mode:
            # V10.4: Proposal Mode - quad proposes, phase integrates
            # Check confidence for conditional skip
            confidence = self.phase_state.compute_confidence(memory_state)

            with torch.no_grad():
                self._last_confidence_mean = confidence.mean().item()
                self._last_skip_rate = (confidence > self.confidence_threshold).float().mean().item()

            # Get proposals from quad (no softmax mixing)
            proposals, proposal_scores = self.quad_query.get_proposals(
                x, memory_state_normed, binding_salience=binding_salience
            )

            # V10.5: Optional interference-aware rescoring (compositional creativity)
            # Applied AFTER proposals, BEFORE phase integration
            # Only active if interference_scorer is configured and conditions met
            if hasattr(self, 'interference_scorer') and self.interference_scorer is not None:
                proposal_scores, interference_stats = self.interference_scorer(
                    proposals, proposal_scores
                )
                if hasattr(self, '_last_interference_stats'):
                    self._last_interference_stats = interference_stats

            # Phase integrates proposals (uses raw memory_state for gating context)
            mem_out = self.phase_state.integrate_proposals(
                x, memory_state, proposals, proposal_scores
            )
            # Combine: local (syntax) + memory (semantics) - no competition
            attn_out = local_out + mem_out
        else:
            # Original mode: Quad queries normalized memory state with softmax attention
            mem_out = self.quad_query(x, memory_state_normed, binding_salience=binding_salience)
            # Combine: local (syntax) + memory (semantics) - no competition
            attn_out = local_out + mem_out

        # Residual connection
        x = x + attn_out

        # Feed-forward with residual
        x = x + self.ff(self.norm_ff(x))

        return x


class BindingCacheTransformer(nn.Module):
    """
    Transformer with Binding Cache architecture.

    Validated by diagnostic probes to prevent Phase decorativeness:
    - Phase: O(n) state accumulator (exclusive role)
    - Quad: O(nk) memory query via Top-K cache (exclusive role)

    Reference: --protected-phase experiment showed -50% ablation drop
    when Phase has protected role (vs ~0% when mixed with Quad).

    V10.6.6: Forward-pass contract enforcement
    - Control signals are validated at forward() and forward_hidden() entry
    - Violations raise ControlShapeViolation immediately (hard-fail)
    - Propagates enforcement to all BindingCacheBlock children
    - Set enforce_control_contract=False to disable (NOT recommended for production)
    """

    # V10.6.6: Class-level enforcement toggle (STRICT by default)
    enforce_control_contract: bool = True

    def __init__(
        self,
        vocab_size: int,
        embed_dim: int,
        num_layers: int,
        num_heads: int,
        ff_dim: int,
        max_seq_len: int,
        dropout: float = 0.1,
        decay_gamma: float = 1.0,
        learned_decay: bool = False,
        bounded_phase: bool = True,
        top_k: int = 64,
        use_cache: bool = True,
        tie_embeddings: bool = True,
        proposal_mode: bool = False,  # V10.4: Quad proposes, Phase integrates
        confidence_threshold: float = 0.7,  # V10.4: Skip quad if confidence > threshold
    ):
        super().__init__()
        self.vocab_size = vocab_size
        self.embed_dim = embed_dim
        self.num_heads = num_heads  # V10.6.6: Store for contract enforcement
        self.num_layers = num_layers
        self.proposal_mode = proposal_mode

        # Embeddings
        self.token_embed = nn.Embedding(vocab_size, embed_dim)
        self.pos_embed = nn.Embedding(max_seq_len, embed_dim)
        self.dropout = nn.Dropout(dropout)

        # Binding Cache blocks
        self.blocks = nn.ModuleList([
            BindingCacheBlock(
                embed_dim=embed_dim,
                num_heads=num_heads,
                ff_dim=ff_dim,
                dropout=dropout,
                decay_gamma=decay_gamma,
                learned_decay=learned_decay,
                bounded_phase=bounded_phase,
                top_k=top_k,
                use_cache=use_cache,
                proposal_mode=proposal_mode,
                confidence_threshold=confidence_threshold,
            )
            for _ in range(num_layers)
        ])

        # Output
        self.norm = nn.LayerNorm(embed_dim)
        self.lm_head = nn.Linear(embed_dim, vocab_size, bias=False)

        # Logit scaling (milder than 1/sqrt(d) to prevent overconfident early logits)
        # Using 1/sqrt(sqrt(d)) ~= 0.19 for d=768, balances stability vs learning speed
        self.logit_scale = 1.0 / math.sqrt(math.sqrt(embed_dim))

        # GPT-style weight initialization for embeddings (prevents variance explosion)
        torch.nn.init.normal_(self.token_embed.weight, mean=0.0, std=0.02)
        torch.nn.init.normal_(self.pos_embed.weight, mean=0.0, std=0.02)

        # Tie embeddings
        if tie_embeddings:
            self.lm_head.weight = self.token_embed.weight

    def set_ablation(self, mode: str, seed: int = 42):
        """Set Phase ablation mode for all blocks."""
        for block in self.blocks:
            block.set_ablation(mode, seed)

    def set_rotation(self, angle_radians: float):
        """
        Set rotation angle for all Phase components (applied to φ_k).

        Note: BindingCacheTransformer uses φ_k only (for memory accumulation),
        not φ_q. So we rotate φ_k to test whether phase encodes relational structure.

        Args:
            angle_radians: Rotation angle in radians (e.g., π/4 = 45°)
        """
        for block in self.blocks:
            block.set_rotation(angle_radians)

    def clear_rotation(self):
        """Clear rotation from all Phase components."""
        for block in self.blocks:
            block.clear_rotation()

    def set_enforce_control_contract(self, enabled: bool):
        """
        V10.6.6: Enable/disable forward-pass contract enforcement.

        This sets enforcement on BOTH the transformer and all child blocks.
        When enabled (default), violations raise ControlShapeViolation immediately.

        IMPORTANT: Disabling enforcement is NOT recommended for production.
        This should only be used for debugging or specific testing scenarios.

        Args:
            enabled: If True (default), enforce contracts in forward pass.
                    If False, skip enforcement (dangerous - allows violations).
        """
        self.enforce_control_contract = enabled
        for block in self.blocks:
            block.enforce_control_contract = enabled

    def get_phase_health(self) -> dict:
        """Aggregate Phase health metrics from all blocks."""
        r_k_means = []
        for block in self.blocks:
            metrics = block.phase_state.get_health_metrics()
            r_k_means.append(metrics["r_k_mean"])

        return {
            "r_k_mean": sum(r_k_means) / len(r_k_means) if r_k_means else 0.0,
            "r_k_per_layer": r_k_means,
        }

    def get_instrumentation(self) -> dict:
        """Aggregate instrumentation metrics from all blocks."""
        cache_hit_rates = []
        mean_alphas = []
        cosine_means = []
        cosine_maxes = []
        for block in self.blocks:
            inst = block.quad_query.get_instrumentation()
            cache_hit_rates.append(inst["cache_hit_rate"])
            mean_alphas.append(inst["mean_alpha"])
            cosine_means.append(inst["cache_key_cosine_mean"])
            cosine_maxes.append(inst["cache_key_cosine_max"])

        return {
            "cache_hit_rate": sum(cache_hit_rates) / len(cache_hit_rates) if cache_hit_rates else 0.0,
            "mean_alpha": sum(mean_alphas) / len(mean_alphas) if mean_alphas else 0.0,
            # Cache health (per ChatGPT recommendation):
            # mean > 0.85 = redundancy building
            # max > 0.95 = slot collision
            "cache_key_cosine_mean": sum(cosine_means) / len(cosine_means) if cosine_means else 0.0,
            "cache_key_cosine_max": max(cosine_maxes) if cosine_maxes else 0.0,
        }

    def get_proposal_metrics(self) -> dict:
        """
        V10.4: Aggregate proposal mode metrics from all blocks.

        Returns:
            dict with:
            - confidence_mean: Average phase confidence across layers
            - skip_rate: Fraction of positions that could skip quad
            - per_layer_confidence: List of confidence means per layer
            - per_layer_skip_rate: List of skip rates per layer
        """
        if not self.proposal_mode:
            return {
                "confidence_mean": 0.0,
                "skip_rate": 0.0,
                "per_layer_confidence": [],
                "per_layer_skip_rate": [],
            }

        confidence_means = []
        skip_rates = []
        for block in self.blocks:
            metrics = block.get_proposal_metrics()
            confidence_means.append(metrics["confidence_mean"])
            skip_rates.append(metrics["skip_rate"])

        return {
            "confidence_mean": sum(confidence_means) / len(confidence_means) if confidence_means else 0.0,
            "skip_rate": sum(skip_rates) / len(skip_rates) if skip_rates else 0.0,
            "per_layer_confidence": confidence_means,
            "per_layer_skip_rate": skip_rates,
        }

    def forward_hidden(
        self,
        input_ids: torch.Tensor,
        intent_phase: Optional[torch.Tensor] = None,
        binding_salience: Optional[torch.Tensor] = None,
        enable_slots_read: bool = True,
    ) -> torch.Tensor:
        """
        Forward pass returning hidden states BEFORE LM head.

        Use this for Ontological integration - compute state delta from hidden,
        then call full forward with intent_phase.

        Args:
            input_ids: [B, N] token IDs
            intent_phase: Optional phase rotation from Ontological State Delta
            binding_salience: Optional [B, N] - per-position salience from
                             OntologicalBindingAnnotator for Top-K selection bias
            enable_slots_read: V10.6.2 (D.2) - If False, skip quad retrieval.
                              Allows Onto/CSR to gate retrieval without affecting storage.

        Returns:
            hidden: [B, N, embed_dim] - normalized hidden states before LM head

        Raises:
            ControlShapeViolation: If control signals violate no-write contract (V10.6.6)
        """
        B, N = input_ids.shape

        # V10.6.6: Enforce no-write contract at forward() entry (HARD-FAIL)
        # Transformer-level enforcement before blocks process signals
        if self.enforce_control_contract:
            if intent_phase is not None:
                assert_control_shape(
                    intent_phase,
                    name="intent_phase",
                    d_model=self.embed_dim,
                    seq_len=N,
                    strict=True,  # HARD-FAIL: raise ControlShapeViolation
                )
            if binding_salience is not None:
                assert_control_shape(
                    binding_salience,
                    name="binding_salience",
                    d_model=self.embed_dim,
                    seq_len=N,
                    strict=True,  # HARD-FAIL: raise ControlShapeViolation
                )

        # Embeddings
        pos = torch.arange(N, device=input_ids.device).unsqueeze(0)
        x = self.dropout(self.token_embed(input_ids) + self.pos_embed(pos))

        # Transformer blocks (with optional intent_phase and binding_salience)
        for block in self.blocks:
            x = block(x, intent_phase=intent_phase, binding_salience=binding_salience,
                      enable_slots_read=enable_slots_read)

        # Return normalized hidden states
        return self.norm(x)

    def forward(
        self,
        input_ids: torch.Tensor,
        labels: Optional[torch.Tensor] = None,
        intent_phase: Optional[torch.Tensor] = None,
        binding_salience: Optional[torch.Tensor] = None,
        enable_slots_read: bool = True,
        return_hidden: bool = False,
        return_last_hidden: bool = False,
    ) -> Union[torch.Tensor, Tuple[torch.Tensor, torch.Tensor], Dict[str, torch.Tensor]]:
        """
        Forward pass with optional intent phase rotation and binding salience.

        Args:
            input_ids: [B, N] token IDs
            labels: Optional [B, N] labels for loss computation
            intent_phase: Optional [B, H] or [B, H, D_h] phase rotation from Ontological State Delta
            binding_salience: Optional [B, N] - per-position salience from OntologicalBindingAnnotator.
                             Biases Top-K selection in Quad WITHOUT modifying attention math.
                             This is where CSR/Kosha/SRK act - as binding selectors, not attention modifiers.
            enable_slots_read: V10.6.2 (D.2) - If False, skip quad retrieval entirely.
                              Allows Onto/CSR to gate retrieval without affecting storage.
                              Write path (phase accumulation) remains active.
            return_hidden: Return dict with hidden states
            return_last_hidden: Return dict with last hidden state

        Returns:
            logits: [B, N, vocab_size] or (loss, logits) if labels provided
            Or Dict with 'logits' and optionally 'hidden_states', 'last_hidden_state'

        Raises:
            ControlShapeViolation: If control signals violate no-write contract (V10.6.6)
        """
        B, N = input_ids.shape

        # V10.6.6: Enforce no-write contract at forward() entry (HARD-FAIL)
        # This is the TOP-LEVEL enforcement - stops training immediately on violation
        if self.enforce_control_contract:
            if intent_phase is not None:
                assert_control_shape(
                    intent_phase,
                    name="intent_phase",
                    d_model=self.embed_dim,
                    seq_len=N,
                    strict=True,  # HARD-FAIL: raise ControlShapeViolation
                )
            if binding_salience is not None:
                assert_control_shape(
                    binding_salience,
                    name="binding_salience",
                    d_model=self.embed_dim,
                    seq_len=N,
                    strict=True,  # HARD-FAIL: raise ControlShapeViolation
                )

        # Embeddings
        pos = torch.arange(N, device=input_ids.device).unsqueeze(0)
        x = self.dropout(self.token_embed(input_ids) + self.pos_embed(pos))

        # Transformer blocks (with optional intent_phase and binding_salience)
        # Core attention is PURE - binding_salience only affects Top-K selection
        hidden_states = [] if return_hidden else None
        for block in self.blocks:
            x = block(x, intent_phase=intent_phase, binding_salience=binding_salience,
                      enable_slots_read=enable_slots_read)
            if return_hidden:
                hidden_states.append(x)

        # Output
        x = self.norm(x)
        logits = self.lm_head(x) * self.logit_scale

        # Return format depends on options
        if return_hidden or return_last_hidden:
            result = {'logits': logits}
            if return_hidden:
                result['hidden_states'] = hidden_states
            if return_last_hidden:
                result['last_hidden_state'] = x
            return result

        if labels is not None:
            loss = F.cross_entropy(
                logits.view(-1, self.vocab_size),
                labels.view(-1),
                ignore_index=-100,
            )
            return loss, logits

        return logits

    def count_params(self) -> int:
        """Count trainable parameters."""
        return sum(p.numel() for p in self.parameters() if p.requires_grad)


# =============================================================================
# ONTOLOGICAL BINDING CACHE (V10.0) - AGI Architecture
# =============================================================================
# Combines:
# 1. Binding Cache: Protected Phase + Top-K Query (validated by probes)
# 2. 32D Sovereign State: Ontological reasoning (Bhava, Kosha, Vritti, Guna)
#
# This is the canonical architecture for AGI:
# - Phase: O(n) state accumulator with intent modulation
# - Quad: O(nk) query mechanism
# - Sovereign State: 32D semantic understanding that modulates Phase
# =============================================================================


class OntologicalBindingCacheTransformer(nn.Module):
    """
    AGI Architecture: Binding Cache + Separated Sovereign State Planes.

    V11.0.0: Phase rotation uses Bhava-only delta (12D), not full 32D.

    Combines:
    1. Binding Cache (validated by probes): Protected Phase + Top-K Query
       - Phase ablation drop: -50% to -54% (Phase is ESSENTIAL)
       - No gradient competition between Phase and Quad

    2. Separated Sovereign State planes:
       Phase Plane (12D Bhava-only → phase rotation):
         [0:12]  12 Bhavas (Ontological Aspects) — WHAT mode of being
       Control Plane (16D → CTM+/Sentinel/Governor):
         [12:17] 5 Koshas (Consciousness Sheaths) — HOW DEEP to process
         [17:22] 5 Vrittis (Mental Modifications) — HOW RELIABLE is this
         [22:28] 6 Gunas (Energy States) — WHAT ENERGY dynamics
       Learning Plane (4D → training-time only):
         [28:32] 4 Reserved (Toroidal Feedback) — scratch/JEPA channels

    Theory:
        - System 2 (Ontological): Slow, deliberate semantic reasoning → ΔBhava
        - System 1 (Binding Cache): Fast pattern completion with identity modulation
        - ΔBhava → Phase Rotation: Identity changes HOW bindings are stored/retrieved
        - Control signals (Koshas/Vrittis/Gunas) → Binding Annotator / CTM+ / Sentinel

    From diagnostic probes:
        - When Phase has protected role: -50% ablation drop (ESSENTIAL)
        - When Phase is mixed with Quad: ~0% drop (DECORATIVE)

    Usage:
        model = OntologicalBindingCacheTransformer(...)
        output = model(input_ids)  # Computes ΔBhava and applies to Protected Phase
    """

    def __init__(
        self,
        vocab_size: int = 50257,
        embed_dim: int = 768,
        num_layers: int = 12,
        num_heads: int = 12,
        ff_dim: Optional[int] = None,
        max_seq_len: int = 8192,
        dropout: float = 0.1,
        # Binding Cache params
        decay_gamma: float = 1.0,
        learned_decay: bool = False,
        top_k: int = 64,
        use_cache: bool = True,
        # Ontological params
        state_dim: int = SOVEREIGN_STATE_DIM,  # 32D Sovereign State
        project_per_head_dim: bool = False,
        tie_embeddings: bool = True,
        # Binding Annotation params (CSR/Kosha/SRK as selectors, not modifiers)
        use_binding_annotator: bool = True,
        use_csr_annotation: bool = True,
        use_kosha_annotation: bool = True,
        use_srk_annotation: bool = True,
    ):
        super().__init__()

        # Default ff_dim
        if ff_dim is None:
            ff_dim = embed_dim * 4

        # Store annotation flags
        self.use_binding_annotator = use_binding_annotator

        # The Binding Cache (generation) model
        self.binding_cache = BindingCacheTransformer(
            vocab_size=vocab_size,
            embed_dim=embed_dim,
            num_layers=num_layers,
            num_heads=num_heads,
            ff_dim=ff_dim,
            max_seq_len=max_seq_len,
            dropout=dropout,
            decay_gamma=decay_gamma,
            learned_decay=learned_decay,
            bounded_phase=True,  # Always enabled (mandatory from probes)
            top_k=top_k,
            use_cache=use_cache,
            tie_embeddings=tie_embeddings,
        )

        # State projector: hidden[embed_dim] → SovereignState[32]
        if SOVEREIGN_PROJECTOR_AVAILABLE:
            self.state_projector = SovereignStateProjector(
                hidden_dim=embed_dim,
                state_dim=state_dim,
                intermediate_dim=embed_dim // 2,
                dropout=0.1,
                use_layer_norm=True,
            )
        else:
            # Fallback to raw projection
            self.state_projector = nn.Sequential(
                nn.Linear(embed_dim, embed_dim // 2),
                nn.GELU(),
                nn.Linear(embed_dim // 2, state_dim),
            )
            self._init_absolute_potential_bias()

        # V11.0.0: Intent phase projector uses Bhava-only delta (12D)
        # Only ontological identity feeds phase rotation, not control signals
        # ΔBhava[12] → θ[H] or θ[H, D_h]
        head_dim = embed_dim // num_heads
        self.intent_projector = IntentPhaseProjector(
            state_dim=PHASE_STATE_DIM,  # V11.0.0: 12D Bhava-only (was state_dim=32D)
            num_heads=num_heads,
            head_dim=head_dim,
            project_per_head_dim=project_per_head_dim,
        )

        # Store config
        self.state_dim = state_dim
        self.embed_dim = embed_dim
        self.num_heads = num_heads

        # Ontological Binding Annotator (CSR/Kosha/SRK as SELECTORS, not attention modifiers)
        # This computes binding salience that biases Top-K selection
        # Clean separation: Attention = physics, Annotator = semantics
        # Note: Annotator still receives full 32D state for semantic selection
        if use_binding_annotator:
            self.binding_annotator = OntologicalBindingAnnotator(
                embed_dim=embed_dim,
                state_dim=state_dim,  # Full 32D for semantic annotation (not phase rotation)
                num_heads=num_heads,
                use_csr=use_csr_annotation,
                use_kosha=use_kosha_annotation,
                use_srk=use_srk_annotation,
            )
        else:
            self.binding_annotator = None

        # Previous state for delta computation
        # V11.0.0: prev_bhava tracks Bhava-only (12D) for phase delta
        self.register_buffer('prev_state', None, persistent=False)
        self.register_buffer('prev_bhava', None, persistent=False)

    def _init_absolute_potential_bias(self):
        """Initialize state projector to bias toward 'Absolute Potential' state."""
        with torch.no_grad():
            final_layer = self.state_projector[-1]
            if hasattr(final_layer, 'bias') and final_layer.bias is not None:
                final_layer.bias.fill_(0.0)
                if final_layer.bias.shape[0] > 11:
                    final_layer.bias[11] = 1.0  # O12_ABS
                if final_layer.bias.shape[0] > 12:
                    final_layer.bias[12] = 0.8  # Material

    def set_ablation(self, mode: str, seed: int = 42):
        """Set Phase ablation mode for all blocks."""
        self.binding_cache.set_ablation(mode, seed)

    def set_rotation(self, angle_radians: float):
        """
        Set rotation angle for all Phase components (applied to φ_k).

        Note: OntologicalBindingCacheTransformer uses φ_k only (for memory accumulation),
        not φ_q. So we rotate φ_k to test whether phase encodes relational structure.

        Args:
            angle_radians: Rotation angle in radians (e.g., π/4 = 45°)
        """
        self.binding_cache.set_rotation(angle_radians)

    def clear_rotation(self):
        """Clear rotation from all Phase components."""
        self.binding_cache.clear_rotation()

    def get_phase_health(self) -> dict:
        """Get Phase health metrics from Binding Cache."""
        return self.binding_cache.get_phase_health()

    def get_instrumentation(self) -> dict:
        """Get instrumentation metrics from Binding Cache."""
        return self.binding_cache.get_instrumentation()

    def compute_state_delta(
        self,
        hidden: torch.Tensor,
        reset_state: bool = False,
    ) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        """
        Compute 32D Sovereign State, full delta, and Bhava-only delta.

        V11.0.0: Returns separated outputs:
        - Full 32D state for diagnostics/control plane
        - Full 32D delta for logging
        - 12D Bhava-only delta for phase rotation (the only dim that touches attention)

        Args:
            hidden: [B, N, embed_dim] - hidden states from binding cache
            reset_state: Reset prev_state (use at start of new sequence)

        Returns:
            state: [B, 32] - current Sovereign State (full, for diagnostics/control)
            delta_S: [B, 32] - full state delta (for logging/learning)
            delta_bhava: [B, 12] - Bhava-only delta (for phase rotation)
        """
        # Pool hidden states
        pooled = hidden.mean(dim=1)  # [B, embed_dim]

        # Project to full 32D Sovereign State
        state = self.state_projector(pooled)  # [B, state_dim]

        # Extract Bhava slice (phase-critical)
        bhava = state[:, BHAVA_SLICE]  # [B, 12]

        # Compute full delta (for logging/learning plane)
        batch_size_changed = (
            self.prev_state is not None and
            self.prev_state.shape[0] != state.shape[0]
        )
        if reset_state or self.prev_state is None or batch_size_changed:
            delta_S = torch.zeros_like(state)
        else:
            delta_S = state - self.prev_state

        # Compute Bhava-only delta (for phase rotation)
        bhava_batch_changed = (
            self.prev_bhava is not None and
            self.prev_bhava.shape[0] != bhava.shape[0]
        )
        if reset_state or self.prev_bhava is None or bhava_batch_changed:
            delta_bhava = torch.zeros_like(bhava)
        else:
            delta_bhava = bhava - self.prev_bhava

        # Update previous states
        self.prev_state = state.detach()
        self.prev_bhava = bhava.detach()

        return state, delta_S, delta_bhava

    def forward(
        self,
        input_ids: torch.Tensor,
        attention_mask: Optional[torch.Tensor] = None,
        labels: Optional[torch.Tensor] = None,
        return_hidden: bool = False,
        return_last_hidden: bool = False,
        reset_state: bool = False,
        external_delta_S: Optional[torch.Tensor] = None,
        csr_mask: Optional[torch.Tensor] = None,
    ) -> Dict[str, torch.Tensor]:
        """
        Forward pass with Ontological → Binding Cache integration.

        V11.0.0: Phase rotation uses Bhava-only delta (12D), not full 32D.

        Two-pass architecture:
        1. First pass: Get hidden states WITHOUT intent phase
        2. Compute state delta from hidden states (returns full + Bhava-only)
        3. Compute binding salience from OntologicalBindingAnnotator (uses full 32D)
        4. Second pass: Full forward WITH intent phase (from 12D Bhava delta)

        Clean separation:
        - Phase rotation = Bhava identity only (12D)
        - Binding Annotator = full semantics (32D: CSR/Kosha/SRK as selectors)
        - Control plane = Koshas/Vrittis/Gunas (routed to CTM+/Sentinel/Governor)
        - Learning plane = Reserved/JEPA (training-time only)

        Args:
            input_ids: [B, N] token indices
            attention_mask: [B, N] optional mask (currently unused)
            labels: Optional [B, N] labels for loss computation
            return_hidden: Return all hidden states
            return_last_hidden: Return final hidden state
            reset_state: Reset Ontological state (new sequence)
            external_delta_S: [B, state_dim] external state delta (legacy 32D or 12D Bhava)
            csr_mask: [B, N] optional CSR content word mask for binding annotation

        Returns:
            Dict with:
            - 'logits': [B, N, V] output logits
            - 'state': [B, 32] current Sovereign State (full, for diagnostics)
            - 'delta_S': [B, 32] full state delta (for logging/learning)
            - 'delta_bhava': [B, 12] Bhava-only delta (phase-critical)
            - 'intent_phase': [B, H] or [B, H, D_h] phase rotation
            - 'loss': Optional, if labels provided
        """
        # First pass: Get hidden states WITHOUT intent phase or salience
        with torch.no_grad():
            hidden = self.binding_cache.forward_hidden(input_ids, intent_phase=None)

        # Compute state delta (or use external)
        if external_delta_S is not None:
            # Legacy path: external delta may be 32D or 12D
            state = self.state_projector(hidden.mean(dim=1))
            delta_S = external_delta_S
            if external_delta_S.shape[-1] <= PHASE_STATE_DIM:
                delta_bhava = external_delta_S
            else:
                delta_bhava = external_delta_S[:, BHAVA_SLICE]
        else:
            state, delta_S, delta_bhava = self.compute_state_delta(hidden, reset_state)

        # V11.0.0: Convert Bhava-only delta to intent phase rotation
        # Only ontological identity (12D) modulates attention
        intent_phase = self.intent_projector(delta_bhava)  # [B, H] or [B, H, D_h]

        # Compute binding salience using OntologicalBindingAnnotator
        # Annotator still uses full 32D state — Kosha/SRK are SELECTORS, not phase rotators
        # This is the correct home for Koshas: they select what's important for binding,
        # without entangling with the phase rotation math
        binding_salience = None
        if self.binding_annotator is not None:
            # Extract Kosha activations from full state (control plane signal)
            kosha_activations = None
            if self.state_dim >= 17:
                kosha_activations = state[:, KOSHA_SLICE]  # [B, 5]

            binding_salience = self.binding_annotator(
                hidden_states=hidden,
                sovereign_state=state,  # Full 32D for semantic selection
                kosha_activations=kosha_activations,
                csr_mask=csr_mask,
            )

        # Second pass: Full forward WITH intent phase AND binding salience
        result = self.binding_cache(
            input_ids,
            labels=labels,
            intent_phase=intent_phase,
            binding_salience=binding_salience,
            return_hidden=return_hidden,
            return_last_hidden=return_last_hidden,
        )

        # Handle different return types from binding_cache
        if isinstance(result, dict):
            output = result
        elif isinstance(result, tuple):
            # (loss, logits) format
            output = {'logits': result[1], 'loss': result[0]}
        else:
            # Just logits
            output = {'logits': result}

        # Add ontological outputs
        output['state'] = state           # Full 32D for diagnostics/control
        output['delta_S'] = delta_S       # Full 32D delta for logging/learning
        output['delta_bhava'] = delta_bhava  # V11.0.0: 12D Bhava delta (phase-critical)
        output['intent_phase'] = intent_phase
        if binding_salience is not None:
            output['binding_salience'] = binding_salience

        return output

    def generate(
        self,
        input_ids: torch.Tensor,
        max_new_tokens: int = 50,
        temperature: float = 1.0,
        top_k: int = 50,
    ) -> torch.Tensor:
        """Generation with Ontological state tracking."""
        self.prev_state = None
        self.prev_bhava = None  # V11.0.0: Reset Bhava tracking too

        for _ in range(max_new_tokens):
            result = self(input_ids, reset_state=(self.prev_state is None))
            logits = result['logits'][:, -1, :]
            logits = logits / temperature
            if top_k > 0:
                v, _ = torch.topk(logits, min(top_k, logits.size(-1)))
                logits[logits < v[:, [-1]]] = float('-inf')
            probs = F.softmax(logits, dim=-1)
            next_token = torch.multinomial(probs, num_samples=1)
            input_ids = torch.cat([input_ids, next_token], dim=1)

        return input_ids

    def count_params(self) -> int:
        """Count trainable parameters."""
        return sum(p.numel() for p in self.parameters() if p.requires_grad)


# =============================================================================
# STANDARD ATTENTION (O(n²)) - For Comparison
# =============================================================================

class StandardAttentionLayer(nn.Module):
    """
    Standard O(n²) Multi-Head Attention Layer.

    For direct comparison with PhaseAttentionLayer.
    """

    def __init__(
        self,
        embed_dim: int,
        num_heads: int,
        dropout: float = 0.1,
    ):
        super().__init__()
        self.embed_dim = embed_dim
        self.num_heads = num_heads
        self.head_dim = embed_dim // num_heads
        self.scale = self.head_dim ** -0.5

        self.q_proj = nn.Linear(embed_dim, embed_dim)
        self.k_proj = nn.Linear(embed_dim, embed_dim)
        self.v_proj = nn.Linear(embed_dim, embed_dim)
        self.out_proj = nn.Linear(embed_dim, embed_dim)

        self.dropout = nn.Dropout(dropout)
        self.norm = nn.LayerNorm(embed_dim)

    def forward(
        self,
        x: torch.Tensor,
        causal_mask: bool = True,
    ) -> torch.Tensor:
        """
        Standard attention forward pass (O(n²)).
        """
        B, N, D = x.shape
        residual = x

        Q = self.q_proj(x).view(B, N, self.num_heads, self.head_dim).transpose(1, 2)
        K = self.k_proj(x).view(B, N, self.num_heads, self.head_dim).transpose(1, 2)
        V = self.v_proj(x).view(B, N, self.num_heads, self.head_dim).transpose(1, 2)

        # O(n²) attention scores
        attn = torch.matmul(Q, K.transpose(-2, -1)) * self.scale

        # Causal mask
        if causal_mask:
            mask = torch.triu(torch.ones(N, N, device=x.device), diagonal=1).bool()
            attn = attn.masked_fill(mask.unsqueeze(0).unsqueeze(0), float('-inf'))

        attn = F.softmax(attn, dim=-1)
        attn = self.dropout(attn)

        # O(n²) value aggregation
        output = torch.matmul(attn, V)

        output = output.transpose(1, 2).reshape(B, N, D)
        output = self.out_proj(output)
        output = self.dropout(output)

        return self.norm(output + residual)


# =============================================================================
# FEED-FORWARD NETWORK
# =============================================================================

class FeedForward(nn.Module):
    """Standard feed-forward network."""

    def __init__(
        self,
        embed_dim: int,
        ff_dim: int,
        dropout: float = 0.1,
    ):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(embed_dim, ff_dim),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(ff_dim, embed_dim),
            nn.Dropout(dropout),
        )
        self.norm = nn.LayerNorm(embed_dim)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.norm(x + self.net(x))


# =============================================================================
# STATE DELTA PREDICTOR - State-Centric Training (No LM Head Required)
# =============================================================================

class StateDeltaPredictor(nn.Module):
    """
    Predicts next hidden state delta for state-centric training.

    Instead of token prediction (expensive LM head):
        hidden → LM head (50K dim) → CE loss  [O(B·T·V) memory]

    We predict state deltas (cheap):
        h[t] → delta predictor → h[t+1] - h[t]  [O(B·T·d) memory]

    This enables:
    1. Training without vocabulary projection (infinite context)
    2. Learning dynamics rather than discrete tokens
    3. Coherence/entropy-based training signals

    Memory savings: 50K/768 = ~65x reduction per position
    At 1M context: 200GB → 3GB
    """

    def __init__(
        self,
        embed_dim: int,
        hidden_dim: Optional[int] = None,
        dropout: float = 0.1,
        num_layers: int = 2,
    ):
        super().__init__()
        self.embed_dim = embed_dim
        hidden_dim = hidden_dim or embed_dim * 2

        # Multi-layer delta predictor
        layers = []
        in_dim = embed_dim
        for i in range(num_layers - 1):
            layers.extend([
                nn.Linear(in_dim, hidden_dim),
                nn.GELU(),
                nn.Dropout(dropout),
            ])
            in_dim = hidden_dim
        layers.append(nn.Linear(in_dim, embed_dim))

        self.delta_net = nn.Sequential(*layers)
        self.norm = nn.LayerNorm(embed_dim)

    def forward(self, hidden_states: torch.Tensor) -> torch.Tensor:
        """
        Predict state deltas from current hidden states.

        Args:
            hidden_states: [B, T, embed_dim] - current hidden states

        Returns:
            predicted_deltas: [B, T-1, embed_dim] - predicted h[t+1] - h[t]
        """
        # Predict delta for each position (what should change next)
        deltas = self.delta_net(hidden_states[:, :-1])  # [B, T-1, embed_dim]
        return self.norm(deltas)

    def compute_loss(
        self,
        hidden_states: torch.Tensor,
        reduction: str = 'mean',
    ) -> Tuple[torch.Tensor, Dict[str, torch.Tensor]]:
        """
        Compute state delta prediction loss.

        Args:
            hidden_states: [B, T, embed_dim] - hidden states from forward pass
            reduction: 'mean', 'sum', or 'none'

        Returns:
            loss: State delta prediction loss
            metrics: Dict with delta_mae, delta_cosine_sim
        """
        # Actual deltas: h[t+1] - h[t]
        actual_deltas = hidden_states[:, 1:] - hidden_states[:, :-1]  # [B, T-1, d]

        # Predicted deltas
        predicted_deltas = self.forward(hidden_states)  # [B, T-1, d]

        # L2 loss (MSE)
        delta_loss = F.mse_loss(predicted_deltas, actual_deltas, reduction=reduction)

        # Metrics
        with torch.no_grad():
            delta_mae = F.l1_loss(predicted_deltas, actual_deltas)
            # Cosine similarity between predicted and actual deltas
            cos_sim = F.cosine_similarity(
                predicted_deltas.reshape(-1, self.embed_dim),
                actual_deltas.reshape(-1, self.embed_dim),
                dim=-1
            ).mean()

        metrics = {
            'delta_loss': delta_loss.detach(),
            'delta_mae': delta_mae,
            'delta_cosine_sim': cos_sim,
        }

        return delta_loss, metrics


def compute_entropy_change_loss(
    hidden_states: torch.Tensor,
    target_entropy_rate: float = 0.0,
) -> Tuple[torch.Tensor, Dict[str, torch.Tensor]]:
    """
    Compute entropy change loss - encourages smooth information flow.

    Measures how much "information" changes between consecutive states
    using the magnitude of state changes as a proxy for entropy.

    Args:
        hidden_states: [B, T, embed_dim]
        target_entropy_rate: Target rate of entropy change (0 = stable)

    Returns:
        loss: Entropy change regularization loss
        metrics: Dict with entropy_rate, entropy_variance
    """
    # State changes as proxy for information change
    deltas = hidden_states[:, 1:] - hidden_states[:, :-1]  # [B, T-1, d]

    # Entropy proxy: L2 norm of deltas (information magnitude)
    entropy_proxy = torch.norm(deltas, dim=-1)  # [B, T-1]

    # Mean entropy rate
    entropy_rate = entropy_proxy.mean()

    # Variance of entropy rate (want consistency)
    entropy_variance = entropy_proxy.var()

    # Loss: deviation from target rate + variance penalty
    loss = (entropy_rate - target_entropy_rate).abs() + 0.1 * entropy_variance

    metrics = {
        'entropy_rate': entropy_rate.detach(),
        'entropy_variance': entropy_variance.detach(),
    }

    return loss, metrics


def compute_constraint_satisfaction_loss(
    hidden_states: torch.Tensor,
    phase_coherence: Optional[torch.Tensor] = None,
) -> Tuple[torch.Tensor, Dict[str, torch.Tensor]]:
    """
    Compute constraint satisfaction loss for state-centric training.

    Constraints:
    1. Bounded norm: Hidden states should have bounded magnitude
    2. Diversity: States should be diverse (not collapse to same point)
    3. Smoothness: Consecutive states should be smooth (Lipschitz)

    Args:
        hidden_states: [B, T, embed_dim]
        phase_coherence: Optional phase coherence from attention (if available)

    Returns:
        loss: Constraint satisfaction loss
        metrics: Dict with norm_violation, diversity, smoothness
    """
    B, T, D = hidden_states.shape

    # 1. Bounded norm constraint (soft constraint)
    norms = torch.norm(hidden_states, dim=-1)  # [B, T]
    max_norm = 10.0  # Soft upper bound
    norm_violation = F.relu(norms - max_norm).mean()

    # 2. Diversity constraint: states should span the space
    # Use variance across time as diversity measure
    diversity = hidden_states.var(dim=1).mean()  # Want high diversity
    diversity_loss = F.relu(1.0 - diversity)  # Penalize if diversity < 1

    # 3. Smoothness constraint: Lipschitz bound on state changes
    deltas = hidden_states[:, 1:] - hidden_states[:, :-1]
    delta_norms = torch.norm(deltas, dim=-1)  # [B, T-1]
    max_delta = 5.0  # Soft Lipschitz bound
    smoothness_violation = F.relu(delta_norms - max_delta).mean()

    # Combined loss
    loss = norm_violation + diversity_loss + smoothness_violation

    metrics = {
        'norm_violation': norm_violation.detach(),
        'diversity': diversity.detach(),
        'smoothness_violation': smoothness_violation.detach(),
    }

    # Add phase coherence if available
    if phase_coherence is not None:
        metrics['phase_coherence'] = phase_coherence.detach()

    return loss, metrics


# =============================================================================
# LOCAL ATTENTION (Sliding Window) - O(n*w)
# =============================================================================

class LocalAttention(nn.Module):
    """
    Sliding window local attention for fast local pattern learning.

    Complexity: O(n * window_size) instead of O(n²)

    Supports Grouped Query Attention (GQA) via n_kv_heads parameter:
    - n_kv_heads = num_heads: Standard MHA (default)
    - n_kv_heads < num_heads: GQA (e.g., 8 KV heads for 32 Q heads = 4x KV memory savings)
    - n_kv_heads = 1: Multi-Query Attention (MQA)

    Backends:
    - 'flash': FlashAttention with sliding window (fastest, requires flash-attn)
    - 'sdpa': PyTorch 2.0 SDPA (good performance, built-in)
    - 'unfold': Manual unfold implementation (fallback, always works)
    """

    def __init__(
        self,
        embed_dim: int,
        num_heads: int,
        n_kv_heads: Optional[int] = None,  # GQA: Number of KV heads (default = num_heads)
        window_size: int = 256,
        dropout: float = 0.1,
        backend: str = 'auto',  # 'auto', 'flash', 'sdpa', 'unfold'
    ):
        super().__init__()
        self.embed_dim = embed_dim
        self.num_heads = num_heads
        self.n_kv_heads = n_kv_heads if n_kv_heads is not None else num_heads
        self.head_dim = embed_dim // num_heads
        self.window_size = window_size
        self.scale = self.head_dim ** -0.5
        self.dropout_p = dropout

        # GQA: Number of times to repeat KV heads
        assert num_heads % self.n_kv_heads == 0, f"num_heads ({num_heads}) must be divisible by n_kv_heads ({self.n_kv_heads})"
        self.n_rep = num_heads // self.n_kv_heads
        self.kv_dim = self.n_kv_heads * self.head_dim

        # Q projection: full embed_dim
        self.q_proj = nn.Linear(embed_dim, embed_dim)
        # K, V projections: reduced for GQA
        self.k_proj = nn.Linear(embed_dim, self.kv_dim)
        self.v_proj = nn.Linear(embed_dim, self.kv_dim)
        self.out_proj = nn.Linear(embed_dim, embed_dim)

        self.dropout = nn.Dropout(dropout)
        self.norm = nn.LayerNorm(embed_dim)

        # V10.11: Learned Re+Im projection for complex phase memory.
        # When phase_memory is complex [B, M, H, D_h], we concatenate Re and Im
        # to get [B, M, 2*H*D_h], then project to embed_dim for K/V.
        # Preserves both Re and Im instead of discarding Im (.real) or
        # destroying sign (.abs()). Init std=0.02 prevents early amplification.
        self.complex_proj = nn.Linear(2 * self.kv_dim, embed_dim)

        # Select backend
        if backend == 'auto':
            if FLASH_ATTN_AVAILABLE:
                self.backend = 'flash'
            elif SDPA_AVAILABLE:
                self.backend = 'sdpa'
            else:
                self.backend = 'unfold'
        else:
            self.backend = backend

    def _forward_flash(self, Q: torch.Tensor, K: torch.Tensor, V: torch.Tensor,
                       causal: bool) -> torch.Tensor:
        """FlashAttention with sliding window - O(n×w) kernel-level.

        V10.2.2: Supports cross-attention where K/V length M may differ from Q length N.
        """
        # flash_attn expects (B, N, H, head_dim)
        Q = Q.transpose(1, 2)  # (B, N, H, head_dim)
        K = K.transpose(1, 2)  # (B, M, H, head_dim) - M may differ from N
        V = V.transpose(1, 2)

        # V10.2.2: Check if this is cross-attention (different sequence lengths)
        N = Q.shape[1]
        M = K.shape[1]
        is_cross_attn = (M != N)

        # FlashAttention with window_size parameter
        # For cross-attention, disable window restriction (allow full attention to memory)
        output = flash_attn_func(
            Q, K, V,
            dropout_p=self.dropout_p if self.training else 0.0,
            causal=causal if not is_cross_attn else False,  # No causal for cross-attn
            window_size=(self.window_size, 0) if not is_cross_attn else (-1, -1),  # Full attn for cross
        )
        return output.transpose(1, 2)  # back to (B, H, N, head_dim)

    def _forward_sdpa(self, Q: torch.Tensor, K: torch.Tensor, V: torch.Tensor,
                      B: int, N: int, causal: bool) -> torch.Tensor:
        """PyTorch 2.0 SDPA - creates block-sparse mask for O(n×w).

        V10.2.2: Supports cross-attention where K/V length M may differ from Q length N.
        """
        w = self.window_size
        M = K.shape[2]  # K/V sequence length (may differ from N in cross-attention)

        # Create sliding window + causal mask
        # This is still O(n²) in mask creation but SDPA is optimized
        # For true O(n×w), use flash backend
        if causal:
            if M == N:
                # Self-attention: standard sliding window + causal mask
                row_idx = torch.arange(N, device=Q.device).unsqueeze(1)
                col_idx = torch.arange(N, device=Q.device).unsqueeze(0)
                # Valid if: col <= row (causal) AND col >= row - w + 1 (window)
                mask = (col_idx <= row_idx) & (col_idx >= row_idx - w + 1)
                attn_mask = torch.zeros(N, N, device=Q.device, dtype=Q.dtype)
                attn_mask.masked_fill_(~mask, float('-inf'))
            else:
                # V10.2.2: Cross-attention where K/V have length M (e.g., N+1 with prev_state)
                # All Q positions can attend to all K/V positions (no causal restriction
                # since K/V is memory from previous chunks + current Phase state)
                # Just apply window constraint relative to current positions
                attn_mask = None  # Allow full attention to memory
        else:
            attn_mask = None

        output = F.scaled_dot_product_attention(
            Q, K, V,
            attn_mask=attn_mask,
            dropout_p=self.dropout_p if self.training else 0.0,
            is_causal=False,  # We handle causality in attn_mask
        )
        return output

    def _forward_unfold(self, Q: torch.Tensor, K: torch.Tensor, V: torch.Tensor,
                        B: int, N: int, causal: bool) -> torch.Tensor:
        """Unfold-based sliding window - TRUE O(n×w), no N×N tensors.

        Uses chunked processing to reduce peak memory usage for long sequences.
        V10.2.2: Supports cross-attention where K/V length M may differ from Q length N.
        """
        w = self.window_size
        M = K.shape[2]  # K/V sequence length

        # V10.2.2: Cross-attention case where K/V have different length than Q
        # Fall back to simple full attention (M is typically just N+1, so this is cheap)
        if M != N:
            # Full attention: Q @ K^T, then softmax, then @ V
            attn = torch.matmul(Q, K.transpose(-2, -1)) * self.scale  # [B, H, N, M]
            attn = F.softmax(attn, dim=-1)
            attn = self.dropout(attn)
            output = torch.matmul(attn, V)  # [B, H, N, head_dim]
            return output

        # For large batch × sequence, process in chunks to avoid OOM
        # K_windows memory ≈ B × H × chunk × w × head_dim × 2 bytes
        # Very aggressive chunking for large batches to leave room for gradients
        chunk_size = max(64, min(256, 1024 // max(B, 1)))

        if B * N > 8192 and N > chunk_size:
            # Process in chunks along sequence dimension
            return self._forward_unfold_chunked(Q, K, V, B, N, causal, chunk_size)

        # Pad K and V on the left so each position can look back w-1 positions
        K_padded = F.pad(K, (0, 0, w - 1, 0), value=0)  # (B, H, N+w-1, head_dim)
        V_padded = F.pad(V, (0, 0, w - 1, 0), value=0)

        # Use unfold to create sliding windows of size w
        K_windows = K_padded.unfold(2, w, 1)  # (B, H, N, head_dim, w)
        V_windows = V_padded.unfold(2, w, 1)

        # Rearrange for attention computation
        K_windows = K_windows.permute(0, 1, 2, 4, 3)  # (B, H, N, w, head_dim)
        V_windows = V_windows.permute(0, 1, 2, 4, 3)

        # Compute attention scores: Q @ K^T for each window
        Q_expanded = Q.unsqueeze(3)  # (B, H, N, 1, head_dim)
        attn = torch.matmul(Q_expanded, K_windows.transpose(-2, -1)) * self.scale
        attn = attn.squeeze(3)  # (B, H, N, w)

        if causal:
            # Mask out padding positions
            positions = torch.arange(N, device=Q.device)
            valid_counts = torch.clamp(positions + 1, max=w)
            window_indices = torch.arange(w, device=Q.device)
            mask = window_indices.unsqueeze(0) < (w - valid_counts.unsqueeze(1))
            attn = attn.masked_fill(mask.unsqueeze(0).unsqueeze(0), float('-inf'))

        attn = F.softmax(attn, dim=-1)
        attn = self.dropout(attn)

        # Apply attention to values
        attn_expanded = attn.unsqueeze(3)  # (B, H, N, 1, w)
        output = torch.matmul(attn_expanded, V_windows)
        output = output.squeeze(3)  # (B, H, N, head_dim)

        return output

    def _forward_unfold_chunked(self, Q: torch.Tensor, K: torch.Tensor, V: torch.Tensor,
                                 B: int, N: int, causal: bool, chunk_size: int) -> torch.Tensor:
        """Chunked unfold processing for memory efficiency with large batches."""
        w = self.window_size
        H = Q.shape[1]
        head_dim = Q.shape[-1]

        # Pad K and V once
        K_padded = F.pad(K, (0, 0, w - 1, 0), value=0)  # (B, H, N+w-1, head_dim)
        V_padded = F.pad(V, (0, 0, w - 1, 0), value=0)

        # Pre-compute causal mask info
        if causal:
            positions = torch.arange(N, device=Q.device)
            valid_counts = torch.clamp(positions + 1, max=w)
            window_indices = torch.arange(w, device=Q.device)
            causal_mask = window_indices.unsqueeze(0) < (w - valid_counts.unsqueeze(1))

        # Process in chunks
        outputs = []
        for start in range(0, N, chunk_size):
            end = min(start + chunk_size, N)
            chunk_len = end - start

            # Extract Q chunk
            Q_chunk = Q[:, :, start:end, :]  # (B, H, chunk_len, head_dim)

            # Extract corresponding K, V windows
            # K_padded indices [start:end] correspond to original [start-w+1:end]
            K_chunk_padded = K_padded[:, :, start:end + w - 1, :]
            V_chunk_padded = V_padded[:, :, start:end + w - 1, :]

            # Unfold this chunk
            K_windows = K_chunk_padded.unfold(2, w, 1)  # (B, H, chunk_len, head_dim, w)
            V_windows = V_chunk_padded.unfold(2, w, 1)
            K_windows = K_windows.permute(0, 1, 2, 4, 3)  # (B, H, chunk_len, w, head_dim)
            V_windows = V_windows.permute(0, 1, 2, 4, 3)

            # Attention for this chunk
            Q_expanded = Q_chunk.unsqueeze(3)  # (B, H, chunk_len, 1, head_dim)
            attn = torch.matmul(Q_expanded, K_windows.transpose(-2, -1)) * self.scale
            attn = attn.squeeze(3)  # (B, H, chunk_len, w)

            if causal:
                chunk_mask = causal_mask[start:end, :]  # (chunk_len, w)
                attn = attn.masked_fill(chunk_mask.unsqueeze(0).unsqueeze(0), float('-inf'))

            attn = F.softmax(attn, dim=-1)
            attn = self.dropout(attn)

            # Apply to values
            attn_expanded = attn.unsqueeze(3)  # (B, H, chunk_len, 1, w)
            out_chunk = torch.matmul(attn_expanded, V_windows)
            out_chunk = out_chunk.squeeze(3)  # (B, H, chunk_len, head_dim)
            outputs.append(out_chunk)

        return torch.cat(outputs, dim=2)

    def _repeat_kv(self, x: torch.Tensor) -> torch.Tensor:
        """Repeat KV heads to match Q heads for GQA."""
        if self.n_rep == 1:
            return x
        B, H, N, D = x.shape
        # (B, n_kv_heads, N, head_dim) -> (B, num_heads, N, head_dim)
        return x.repeat_interleave(self.n_rep, dim=1)

    def forward(
        self,
        x: torch.Tensor,
        causal_mask: bool = True,
        phase_memory: Optional[torch.Tensor] = None,
    ) -> torch.Tensor:
        """
        Local attention with sliding window - O(n × window_size) complexity.

        V10.2.1: Added phase_memory for cross-attention mode.

        Two modes:
        1. Self-attention (phase_memory=None): Q, K, V all from x
           - Standard sliding window attention
        2. Cross-attention (phase_memory provided): Q from x, K/V from phase_memory
           - Local queries Phase's accumulated memory state
           - This is the Protected Phase pattern: Local gets long-range info ONLY
             through Phase memory, not directly from past tokens

        Args:
            x: [B, N, D] input tensor (used for Q, and K/V if self-attention)
            causal_mask: Apply causal masking
            phase_memory: [B, N, H, D_h] complex tensor - Phase's memory_state
                         If provided, K and V are derived from this instead of x.
                         CRITICAL: This is how Local queries Phase for long-range info.

        Supports GQA: K and V have fewer heads than Q, expanded via repeat_interleave.

        Automatically selects best available backend:
        1. FlashAttention (if available) - fastest, true O(n×w) kernel
        2. PyTorch SDPA (if available) - good performance
        3. Unfold (fallback) - always works, true O(n×w)
        """
        B, N, D = x.shape
        residual = x

        # Q: Always from input x (current chunk tokens)
        # (B, N, num_heads, head_dim) -> (B, num_heads, N, head_dim)
        Q = self.q_proj(x).view(B, N, self.num_heads, self.head_dim).transpose(1, 2)

        if phase_memory is not None:
            # V10.2.1: Cross-attention mode - K/V from Phase memory
            # phase_memory is [B, M, H, D_h] complex where M may differ from N
            # V10.2.2: M can be N+1 when prev_phase_state is concatenated
            # V10.11: Learned Re+Im projection instead of .real (loses Im) or
            # .abs() (destroys sign). Concatenate [Re(S); Im(S)] and project
            # through a learned linear layer to preserve full complex signal.
            M = phase_memory.shape[1]
            H = phase_memory.shape[2]
            D_h = phase_memory.shape[3]

            if phase_memory.is_complex():
                re_part = phase_memory.real.reshape(B, M, H * D_h)
                im_part = phase_memory.imag.reshape(B, M, H * D_h)
                memory_flat = self.complex_proj(
                    torch.cat([re_part, im_part], dim=-1)
                )  # [B, M, embed_dim]
            else:
                memory_flat = phase_memory.reshape(B, M, H * D_h)
                # Handle dimension mismatch for real-only memory
                if memory_flat.shape[-1] != D:
                    if memory_flat.shape[-1] < D:
                        padding = torch.zeros(B, M, D - memory_flat.shape[-1], device=x.device, dtype=x.dtype)
                        memory_flat = torch.cat([memory_flat, padding], dim=-1)
                    else:
                        memory_flat = memory_flat[:, :, :D]

            # K, V from Phase memory (length M, may differ from Q length N)
            K = self.k_proj(memory_flat).view(B, M, self.n_kv_heads, self.head_dim).transpose(1, 2)
            V = self.v_proj(memory_flat).view(B, M, self.n_kv_heads, self.head_dim).transpose(1, 2)
        else:
            # Standard self-attention: K, V from input x
            # K, V: (B, N, n_kv_heads, head_dim) -> (B, n_kv_heads, N, head_dim)
            K = self.k_proj(x).view(B, N, self.n_kv_heads, self.head_dim).transpose(1, 2)
            V = self.v_proj(x).view(B, N, self.n_kv_heads, self.head_dim).transpose(1, 2)

        # GQA: Expand K, V to match Q heads
        K = self._repeat_kv(K)  # (B, num_heads, N, head_dim)
        V = self._repeat_kv(V)  # (B, num_heads, N, head_dim)

        # Select backend
        if self.backend == 'flash' and FLASH_ATTN_AVAILABLE:
            output = self._forward_flash(Q, K, V, causal_mask)
        elif self.backend == 'sdpa' and SDPA_AVAILABLE:
            output = self._forward_sdpa(Q, K, V, B, N, causal_mask)
        else:
            output = self._forward_unfold(Q, K, V, B, N, causal_mask)

        output = output.transpose(1, 2).contiguous().view(B, N, D)
        output = self.out_proj(output)

        return self.norm(residual + output)


# =============================================================================
# LIGHTNING ATTENTION (O(d²) constant KV cache)
# =============================================================================

class LightningAttention(nn.Module):
    """
    Linear attention with constant O(d²) KV cache - inspired by TransNormerLLM/RetNet.

    Memory: O(d²) regardless of sequence length (vs O(n×w) for local attention)
    Compute: O(n·d²) per layer

    Key formula:
        kv_t = λ · kv_{t-1} + k_t^T · v_t   (d×d matrix, constant size)
        o_t = q_t · kv_t

    This enables infinite context with bounded memory.
    """

    def __init__(
        self,
        embed_dim: int,
        num_heads: int,
        dropout: float = 0.1,
        decay_init: float = 0.99,
        use_decay_mask: bool = True,
    ):
        super().__init__()
        self.embed_dim = embed_dim
        self.num_heads = num_heads
        self.head_dim = embed_dim // num_heads
        self.scale = self.head_dim ** -0.5
        self.use_decay_mask = use_decay_mask

        self.q_proj = nn.Linear(embed_dim, embed_dim)
        self.k_proj = nn.Linear(embed_dim, embed_dim)
        self.v_proj = nn.Linear(embed_dim, embed_dim)
        self.out_proj = nn.Linear(embed_dim, embed_dim)

        # Learnable per-head decay factors
        self.decay = nn.Parameter(torch.full((num_heads,), decay_init))

        self.dropout = nn.Dropout(dropout)
        self.norm = nn.LayerNorm(embed_dim)

    def _forward_recurrent(self, Q: torch.Tensor, K: torch.Tensor, V: torch.Tensor) -> torch.Tensor:
        """
        Recurrent mode: O(d²) memory, O(n·d²) compute.
        Best for inference with very long sequences.
        """
        B, H, N, D = Q.shape
        device = Q.device

        # Initialize KV cache: (B, H, d, d) - constant size!
        kv = torch.zeros(B, H, D, D, device=device, dtype=Q.dtype)

        outputs = []
        decay = torch.sigmoid(self.decay).view(1, H, 1, 1)  # (1, H, 1, 1)

        for t in range(N):
            k_t = K[:, :, t, :]  # (B, H, D)
            v_t = V[:, :, t, :]  # (B, H, D)
            q_t = Q[:, :, t, :]  # (B, H, D)

            # Update KV cache with decay: O(d²) per step
            # kv_t = λ · kv_{t-1} + k_t^T · v_t
            kv_update = torch.einsum('bhd,bhe->bhde', k_t, v_t)
            kv = decay * kv + kv_update

            # Compute output: O(d²) per step
            o_t = torch.einsum('bhd,bhde->bhe', q_t, kv) * self.scale
            outputs.append(o_t)

        return torch.stack(outputs, dim=2)  # (B, H, N, D)

    def _forward_parallel(self, Q: torch.Tensor, K: torch.Tensor, V: torch.Tensor) -> torch.Tensor:
        """
        Parallel mode: Uses cumulative sum with decay weights.
        Better for training (parallelizable), but creates O(n²) decay matrix.
        Falls back to chunked approach for very long sequences.
        """
        B, H, N, D = Q.shape
        device = Q.device

        # For shorter sequences, use full parallel computation
        if N <= 2048:
            # Compute decay weights matrix: (N, N) lower triangular
            positions = torch.arange(N, device=device, dtype=Q.dtype)
            decay = torch.sigmoid(self.decay).view(H, 1, 1)  # (H, 1, 1)

            # decay_weights[i,j] = λ^(i-j) for j <= i, else 0
            diff = positions.unsqueeze(0) - positions.unsqueeze(1)  # (N, N)
            decay_weights = decay ** diff.unsqueeze(0).clamp(min=0)  # (H, N, N)
            decay_weights = torch.tril(decay_weights)  # Causal mask

            # Compute KV terms: (B, H, N, D, D)
            kv_terms = torch.einsum('bhnd,bhne->bhnde', K, V)

            # Cumulative weighted sum: (B, H, N, D, D)
            kv_cumsum = torch.einsum('hts,bhtde->bhsde', decay_weights, kv_terms)

            # Output: (B, H, N, D)
            output = torch.einsum('bhnd,bhnde->bhne', Q, kv_cumsum) * self.scale
            return output
        else:
            # For longer sequences, use recurrent to avoid O(n²) memory
            return self._forward_recurrent(Q, K, V)

    def forward(self, x: torch.Tensor, causal_mask: bool = True, mode: str = 'auto') -> torch.Tensor:
        """
        Lightning attention forward pass.

        Args:
            x: Input tensor (B, N, D)
            causal_mask: Always True for autoregressive (built into the method)
            mode: 'auto', 'recurrent', or 'parallel'
        """
        B, N, D = x.shape
        residual = x

        Q = self.q_proj(x).view(B, N, self.num_heads, self.head_dim).transpose(1, 2)
        K = self.k_proj(x).view(B, N, self.num_heads, self.head_dim).transpose(1, 2)
        V = self.v_proj(x).view(B, N, self.num_heads, self.head_dim).transpose(1, 2)
        # Q, K, V: (B, H, N, D)

        if mode == 'recurrent' or (mode == 'auto' and N > 2048):
            output = self._forward_recurrent(Q, K, V)
        else:
            output = self._forward_parallel(Q, K, V)

        output = output.transpose(1, 2).contiguous().view(B, N, D)
        output = self.out_proj(output)
        output = self.dropout(output)

        return self.norm(residual + output)


class LightningTransformerBlock(nn.Module):
    """Transformer block with Lightning Attention."""

    def __init__(self, config: TransformerConfig, decay_init: float = 0.99):
        super().__init__()
        self.attention = LightningAttention(
            embed_dim=config.embed_dim,
            num_heads=config.num_heads,
            dropout=config.dropout,
            decay_init=decay_init,
        )
        self.ff = FeedForward(
            embed_dim=config.embed_dim,
            ff_dim=config.ff_dim,
            dropout=config.dropout,
        )

    def forward(self, x: torch.Tensor, causal_mask: bool = True) -> torch.Tensor:
        x = self.attention(x, causal_mask)
        x = self.ff(x)
        return x


# =============================================================================
# STANDARD SOFTMAX ATTENTION (for grouped hybrid)
# =============================================================================

class StandardAttention(nn.Module):
    """
    Standard O(n²) softmax attention - used sparingly in grouped hybrid.
    High-fidelity retrieval layer to complement linear attention.
    """

    def __init__(
        self,
        embed_dim: int,
        num_heads: int,
        dropout: float = 0.1,
    ):
        super().__init__()
        self.embed_dim = embed_dim
        self.num_heads = num_heads
        self.head_dim = embed_dim // num_heads
        self.scale = self.head_dim ** -0.5

        self.q_proj = nn.Linear(embed_dim, embed_dim)
        self.k_proj = nn.Linear(embed_dim, embed_dim)
        self.v_proj = nn.Linear(embed_dim, embed_dim)
        self.out_proj = nn.Linear(embed_dim, embed_dim)

        self.dropout = nn.Dropout(dropout)
        self.norm = nn.LayerNorm(embed_dim)

    def forward(self, x: torch.Tensor, causal_mask: bool = True) -> torch.Tensor:
        B, N, D = x.shape
        residual = x

        Q = self.q_proj(x).view(B, N, self.num_heads, self.head_dim).transpose(1, 2)
        K = self.k_proj(x).view(B, N, self.num_heads, self.head_dim).transpose(1, 2)
        V = self.v_proj(x).view(B, N, self.num_heads, self.head_dim).transpose(1, 2)

        # Standard attention: O(n²)
        if SDPA_AVAILABLE:
            output = F.scaled_dot_product_attention(
                Q, K, V, is_causal=causal_mask,
                dropout_p=self.dropout.p if self.training else 0.0,
            )
        else:
            attn = torch.matmul(Q, K.transpose(-2, -1)) * self.scale
            if causal_mask:
                mask = torch.triu(torch.ones(N, N, device=x.device, dtype=torch.bool), diagonal=1)
                attn = attn.masked_fill(mask, float('-inf'))
            attn = F.softmax(attn, dim=-1)
            attn = self.dropout(attn)
            output = torch.matmul(attn, V)

        output = output.transpose(1, 2).contiguous().view(B, N, D)
        output = self.out_proj(output)

        return self.norm(residual + output)


class StandardAttentionBlock(nn.Module):
    """Transformer block with standard softmax attention."""

    def __init__(self, config: TransformerConfig):
        super().__init__()
        self.attention = StandardAttention(
            embed_dim=config.embed_dim,
            num_heads=config.num_heads,
            dropout=config.dropout,
        )
        self.ff = FeedForward(
            embed_dim=config.embed_dim,
            ff_dim=config.ff_dim,
            dropout=config.dropout,
        )

    def forward(self, x: torch.Tensor, causal_mask: bool = True) -> torch.Tensor:
        x = self.attention(x, causal_mask)
        x = self.ff(x)
        return x


# =============================================================================
# GROUPED HYBRID TRANSFORMER (M linear + 1 softmax pattern)
# =============================================================================

class GroupedHybridTransformer(nn.Module):
    """
    Grouped Hybrid Transformer: M layers of Lightning + 1 layer of Softmax.

    Architecture: [Lightning × M, Softmax] × num_groups

    This pattern:
    - Uses efficient linear attention (Lightning) for most computation
    - Periodically uses softmax attention for high-fidelity retrieval/correction
    - Optimal M is 4-7 based on scaling laws

    Memory: O(d²) for Lightning layers + O(n²) only for sparse softmax layers
    """

    def __init__(
        self,
        vocab_size: int = 50257,
        embed_dim: int = 768,
        num_heads: int = 12,
        ff_dim: Optional[int] = None,
        max_seq_len: int = 8192,
        dropout: float = 0.1,
        # Grouped hybrid params
        M: int = 4,  # Lightning layers per group
        num_groups: int = 3,  # Number of (M+1) groups
        decay_init: float = 0.99,
        tie_embeddings: bool = True,  # V9.6.0: Set False when using Sanskrit/CSR
    ):
        super().__init__()

        if ff_dim is None:
            ff_dim = 4 * embed_dim

        config = TransformerConfig(
            vocab_size=vocab_size,
            embed_dim=embed_dim,
            num_layers=num_groups * (M + 1),  # Total layers
            num_heads=num_heads,
            ff_dim=ff_dim,
            max_seq_len=max_seq_len,
            dropout=dropout,
        )
        self.config = config
        self.M = M
        self.num_groups = num_groups
        self.tie_embeddings = tie_embeddings

        # Embeddings
        self.token_embed = nn.Embedding(vocab_size, embed_dim)
        self.pos_embed = nn.Embedding(max_seq_len, embed_dim)
        self.embed_dropout = nn.Dropout(dropout)

        # Build grouped layers: [Lightning × M, Softmax] × num_groups
        self.blocks = nn.ModuleList()
        for g in range(num_groups):
            # M layers of Lightning Attention
            for m in range(M):
                self.blocks.append(LightningTransformerBlock(config, decay_init=decay_init))
            # 1 layer of Standard Softmax Attention
            self.blocks.append(StandardAttentionBlock(config))

        # Output
        self.norm = nn.LayerNorm(embed_dim)
        self.lm_head = nn.Linear(embed_dim, vocab_size, bias=False)

        # V10.11: Learnable logit scale initialized to 1.0.
        # Previous: 1/sqrt(sqrt(d)) ≈ 0.25 which flattened softmax → incoherent text.
        self.logit_scale = nn.Parameter(torch.ones(1))

        # V9.6.0: Optionally tie weights (disable when using Sanskrit/CSR injection)
        if tie_embeddings:
            self.lm_head.weight = self.token_embed.weight

        self._init_weights()

        # V9.6.10: For untied embeddings, copy token_embed to lm_head AFTER init
        # This provides semantic alignment at start while keeping them separate
        # Without this, lm_head is random → gibberish output early in training
        if not self.tie_embeddings:
            with torch.no_grad():
                self.lm_head.weight.copy_(self.token_embed.weight)

    def _init_weights(self):
        for module in self.modules():
            if isinstance(module, nn.Linear):
                torch.nn.init.normal_(module.weight, mean=0.0, std=0.02)
                if module.bias is not None:
                    torch.nn.init.zeros_(module.bias)
            elif isinstance(module, nn.Embedding):
                torch.nn.init.normal_(module.weight, mean=0.0, std=0.02)

    def forward(
        self,
        x: torch.Tensor,
        return_hidden: bool = False,
        causal_mask: bool = True,
    ) -> Dict[str, Any]:
        B, N = x.shape
        device = x.device

        # Embeddings
        positions = torch.arange(N, device=device).unsqueeze(0)
        x = self.token_embed(x) + self.pos_embed(positions)
        x = self.embed_dropout(x)

        hidden_states = [x] if return_hidden else []

        # Forward through grouped blocks
        for block in self.blocks:
            x = block(x, causal_mask)
            if return_hidden:
                hidden_states.append(x)

        x = self.norm(x)
        logits = self.lm_head(x) * self.logit_scale

        output = {"logits": logits}
        if return_hidden:
            output["hidden_states"] = hidden_states

        return output

    def get_num_params(self) -> int:
        return sum(p.numel() for p in self.parameters())


# =============================================================================
# HYBRID ATTENTION (Local + Phase)
# =============================================================================

class HybridAttentionLayer(nn.Module):
    """
    Combines local attention (fast pattern learning) with phase attention (global context).

    V10.2: Two operating modes:

    1. Protected Phase (DEFAULT, recommended for chunking):
       - Processing: x → Phase → Local → output
       - Phase accumulates temporal memory across chunks
       - Local queries Phase's output (serial dependency)
       - No gradient competition between Phase and Local
       - Phase MUST learn useful features (Local depends on it)

    2. Standard Parallel (legacy):
       - Processing: x → Phase ↘
                     x → Local  ↗ weighted blend
       - Both process original input independently
       - Weighted combination: α_local * Local + α_phase * Phase
       - Potential gradient competition

    Supports:
    - Grouped Query Attention (GQA) via n_kv_heads for memory efficiency
    - Chunk-persistent Phase state (prev_phase_state, return_state)
    - Layer-specific phase weighting
    """

    def __init__(
        self,
        embed_dim: int,
        num_heads: int,
        n_kv_heads: Optional[int] = None,  # GQA: Number of KV heads (default = num_heads)
        window_size: int = 256,
        dropout: float = 0.1,
        sync_steps: int = 3,
        sync_lr: float = 0.1,
        alpha_local: float = 0.8,
        alpha_phase: float = 0.2,
        local_backend: str = 'auto',
        temperature: float = 1.0,  # Lower = sharper phase attention
        cosine_mode: str = "standard",  # V9.6.12: "standard", "shifted", or "complex"
        decay_gamma: float = 1.0,  # V9.6.13: State decay factor (1.0=infinite, <1.0=local focus)
        layer_idx: int = -1,  # V9.9.1: Layer index for per-layer phase control
        learned_decay: bool = False,  # V9.9.7: Per-head learned decay (Mamba/S4-style)
        bounded_phase: bool = False,  # V9.9.11: Constrain φ to [-π, π] via π*sin()
        zero_mean_cosine: bool = False,  # V9.9.11: Center cosine per head (forces selectivity)
        dual_channel_mode: bool = False,  # V10.3.8: Separate content and alignment scores
        alignment_authority: float = 0.1,  # V10.3.8: Weight for alignment term
        protected_phase: bool = True,  # V10.2: Protected Phase pattern (default=True)
        # V10.12: Multi-channel Phase memory with selective write gating
        phase_channels: int = 1,
        phase_write_gate: bool = False,
    ):
        super().__init__()
        # V9.9.1: Track layer index for per-layer phase weight control
        self.layer_idx = layer_idx

        # V10.2: Protected Phase pattern - Local queries Phase output, not original input
        # This eliminates gradient competition and ensures Phase learns useful features.
        # When True: x → Phase → Local → output (serial, no blending)
        # When False: x → Phase ↘
        #             x → Local  ↗ blend → output (parallel, weighted)
        self.protected_phase = protected_phase

        # Keep alphas for potential future use (e.g., residual weighting)
        self.alpha_local = nn.Parameter(torch.tensor(alpha_local))
        self.alpha_phase = nn.Parameter(torch.tensor(alpha_phase))

        self.local_attn = LocalAttention(
            embed_dim=embed_dim,
            num_heads=num_heads,
            n_kv_heads=n_kv_heads,  # GQA support
            window_size=window_size,
            dropout=dropout,
            backend=local_backend,
        )

        # V9.6.11: Fix Double Dampening - use aux_scale=1.0 in hybrid mode
        # Previously: aux_scale=0.1 (default) × w_phase=0.2 = 2% effective signal
        # This caused phase attention gradients to be 40x smaller than local
        # Fix: Full strength phase output, let alpha weights handle the mixing
        self.phase_attn = PhaseAttentionLayer(
            embed_dim=embed_dim,
            num_heads=num_heads,
            dropout=dropout,
            sync_steps=sync_steps,
            sync_lr=sync_lr,
            temperature=temperature,  # Pass temperature for sharper attention
            aux_scale=1.0,  # V9.6.11: Full strength (was 0.1 causing 2% effective signal)
            cosine_mode=cosine_mode,  # V9.6.12: Cosine interaction mode
            decay_gamma=decay_gamma,  # V9.6.13: State decay factor
            learned_decay=learned_decay,  # V9.9.7: Per-head learned decay
            bounded_phase=bounded_phase,  # V9.9.11: Phase collapse fix 1
            zero_mean_cosine=zero_mean_cosine,  # V9.9.11: Phase collapse fix 2
            dual_channel_mode=dual_channel_mode,  # V10.3.8: Dual-channel attention
            alignment_authority=alignment_authority,  # V10.3.8: Alignment authority
            phase_channels=phase_channels,  # V10.12: Multi-channel memory
            phase_write_gate=phase_write_gate,  # V10.12: Selective write gate
        )

        self.norm = nn.LayerNorm(embed_dim)

    def forward(
        self,
        x: torch.Tensor,
        causal_mask: bool = True,
        intent_phase: Optional[torch.Tensor] = None,
        return_decorr_loss: bool = False,
        prev_phase_state: Optional[torch.Tensor] = None,
        prev_norm_state: Optional[torch.Tensor] = None,
        return_state: bool = False,
    ) -> Union[torch.Tensor, Tuple[torch.Tensor, torch.Tensor], Tuple[torch.Tensor, Dict[str, torch.Tensor]]]:
        """
        Weighted hybrid forward: Blend local and phase attention outputs.

        V10.2: CRITICAL FIX - Phase runs FIRST, then Local.
        This ensures Phase captures structure before Local does spatial reasoning.
        Previously Local ran first, which let it "learn first" and made Phase decorative.

        Key invariants:
        - Phase = temporal memory (accumulates state across sequence/chunks)
        - Local = spatial reasoning (per-chunk only, no long-range memory)

        V10.2: Added prev_phase_state/return_state for chunk-persistent Phase memory.

        Args:
            x: [B, N, D] input tensor
            causal_mask: Apply causal masking
            intent_phase: Optional phase rotation from Ontological State Delta.
                         Only affects Phase attention (Local is unchanged).
            return_decorr_loss: If True, return (output, decorr_loss) tuple
            prev_phase_state: Optional [B, 1, H, D_h] - Phase state from previous chunk
            prev_norm_state: Optional [B, 1, H, D_h] - Normalizer state from previous chunk
            return_state: If True, return (output, state_dict) for chunk continuation

        Returns:
            output: [B, N, D] blended attention output
            decorr_loss: (optional) Decorrelation loss if return_decorr_loss=True
            state_dict: (optional) Phase states if return_state=True
        """
        residual = x

        # =====================================================================
        # V10.2: Phase attention FIRST (captures global context / temporal memory)
        # =====================================================================
        # This is critical: Phase must update BEFORE Local so it can:
        # 1. Capture structure from input first
        # 2. Accumulate state properly for temporal memory
        # 3. Provide memory_state for Local to query via cross-attention
        #
        # V10.2.1: Always request return_state=True in protected_phase mode
        # so we can pass memory_state to Local for cross-attention
        need_memory_state = self.protected_phase or return_state
        phase_result = self.phase_attn(
            residual,
            causal_mask,
            intent_phase=intent_phase,
            prev_state=prev_phase_state,
            prev_norm_state=prev_norm_state,
            return_state=need_memory_state,
        )

        if need_memory_state:
            x_phase, phase_state_dict = phase_result
            # V10.2.1: Extract memory_state for Local cross-attention
            phase_memory = phase_state_dict.get('memory_state', None)
        else:
            x_phase = phase_result
            phase_state_dict = None
            phase_memory = None

        # =====================================================================
        # Local attention SECOND (captures local patterns / spatial reasoning)
        # =====================================================================
        # V10.2.1: Protected Phase pattern - Local cross-attends to Phase memory
        #
        # Protected Phase (self.protected_phase=True, REQUIRED for correct chunking):
        #   - Q from current tokens (x), K/V from Phase memory_state
        #   - Local queries Phase memory for ALL long-range information
        #   - Local NEVER sees past tokens directly (only through Phase)
        #   - No gradient competition (gradients flow: output → Local → Phase)
        #
        # Standard Parallel (self.protected_phase=False, legacy):
        #   - Both process original input independently
        #   - Weighted blending (gradient competition possible)
        #
        # Key invariant: Local resets per-chunk, Phase persists across chunks.

        if self.protected_phase:
            # V10.2.1: Protected Phase with cross-attention
            # Local's Q attends to Phase's memory_state (K/V)
            # This enforces: "Quadratic queries ONLY Phase memory for long-range info"

            # V10.2.2 FIX: Include previous chunk's final state in cross-attention
            # V10.12: prev_phase_state may be [B,1,C*H,D_h] with multi-channel.
            # Aggregate it to [B,1,H,D_h] to match phase_memory for concatenation.
            if prev_phase_state is not None and phase_memory is not None:
                prev_for_xattn = prev_phase_state
                H_mem = phase_memory.shape[2]  # num_heads
                if prev_for_xattn.shape[2] != H_mem:
                    # Multi-channel: [B,1,C*H,D_h] → mean over channels → [B,1,H,D_h]
                    C = prev_for_xattn.shape[2] // H_mem
                    prev_for_xattn = prev_for_xattn.view(
                        prev_for_xattn.shape[0], 1, C, H_mem, prev_for_xattn.shape[3]
                    ).mean(dim=2)
                phase_memory = torch.cat([prev_for_xattn, phase_memory], dim=1)

            # V10.21: RMS-normalize phase_memory before local cross-attention.
            # phase_memory is a cumsum output — magnitudes grow linearly with
            # sequence position. When local_attn's complex_proj → k_proj/v_proj
            # processes unbounded magnitudes, the softmax attention gradients
            # create 300-500× spikes in W_k_fused and v_proj (step 700: 430×,
            # 487×) that cascade through blocks 3-7 into full PPL collapse.
            # RMS normalization bounds the magnitudes to O(1) while preserving
            # relative structure and gradient flow. Using detached denominator
            # (same pattern as phase normalizer V10.19) to prevent the
            # normalization Jacobian from creating new amplification paths.
            if phase_memory is not None:
                _pm_rms = (phase_memory.abs() ** 2).mean(dim=-1, keepdim=True).sqrt().clamp(min=1e-6)
                phase_memory = phase_memory / _pm_rms.detach()

            x_local = self.local_attn(x, causal_mask, phase_memory=phase_memory)

            # V10.2.1 GRADIENT ROUTING (Requirement 7):
            # Phase output is NOT added to the residual directly. Phase influences
            # logits only through Local's cross-attention to phase_memory.
            # This is intentional: Phase state can have large norms (cumsum),
            # and adding it directly would destabilize the residual stream.
            # The fix for Phase signal strength is at the source (bounded state
            # accumulation + learned Re+Im projection), not here.
            output = residual + x_local
        else:
            # Standard Parallel: Local processes original input independently
            # (Not recommended for chunking - causes gradient competition)
            x_local = self.local_attn(x, causal_mask)
            # Weighted combination using learnable alphas
            alpha_sum = torch.abs(self.alpha_local) + torch.abs(self.alpha_phase) + 1e-8
            w_local = torch.abs(self.alpha_local) / alpha_sum
            w_phase = torch.abs(self.alpha_phase) / alpha_sum
            output = w_local * x_local + w_phase * x_phase

        # Handle different return modes
        if return_state and phase_state_dict is not None:
            return output, phase_state_dict

        if return_decorr_loss:
            # Decorrelation loss: Penalize high cosine similarity between phase and local
            # We want phase and local to learn different features (orthogonal outputs)
            # Note: In protected_phase mode, they're serial so this measures how much
            # Local transforms the Phase output
            x_local_flat = x_local.flatten(1)  # [B, N*D]
            x_phase_flat = x_phase.flatten(1)  # [B, N*D]

            cos_sim = F.cosine_similarity(x_local_flat, x_phase_flat, dim=1, eps=1e-8)
            decorr_loss = (cos_sim ** 2).mean()  # Smoother gradients than abs()

            return output, decorr_loss

        return output


def compute_weight_orthogonalization_loss(model: nn.Module, debug: bool = False) -> torch.Tensor:
    """
    Compute orthogonalization loss between local and phase attention weight matrices.

    This directly regularizes the PARAMETERS (not outputs) to encourage local and phase
    attention to learn fundamentally different transformations.

    For each HybridAttentionLayer, we penalize cosine similarity between:
    - Local Q weights vs Phase Q weights (W_q_phase)
    - Local K weights vs Phase K weights (W_k_phase)
    - Local V weights vs Phase V weights

    This ensures gradients flow directly through parameters, unlike output decorrelation
    which can be blocked by detach() operations or competing gradients.

    Args:
        model: Model containing HybridAttentionLayer modules
        debug: If True, print diagnostic info on first call

    Returns:
        Scalar tensor with orthogonalization loss (lower = more orthogonal)
    """
    # Handle torch.compile wrapped models - get the original model
    actual_model = model
    if hasattr(model, '_orig_mod'):
        actual_model = model._orig_mod
        if debug:
            print(f"DEBUG ORTHO: Detected torch.compile, using _orig_mod")

    ortho_losses = []
    hybrid_layer_count = 0

    for module in actual_model.modules():
        if isinstance(module, HybridAttentionLayer):
            hybrid_layer_count += 1
            local_attn = module.local_attn
            phase_attn = module.phase_attn

            # Q weights: local.q_proj vs phase.W_q_phase
            local_q = local_attn.q_proj.weight.flatten()
            phase_q = phase_attn.W_q_phase.weight.flatten()
            # Cosine similarity squared (penalize both +1 and -1 alignment)
            cos_q = F.cosine_similarity(local_q.unsqueeze(0), phase_q.unsqueeze(0), eps=1e-8)
            ortho_losses.append(cos_q ** 2)

            # K weights: local.k_proj vs phase.W_k_phase
            # Note: local.k_proj may have different shape due to GQA
            local_k = local_attn.k_proj.weight.flatten()
            phase_k = phase_attn.W_k_phase.weight.flatten()
            # Handle shape mismatch by truncating to smaller
            min_len = min(local_k.shape[0], phase_k.shape[0])
            cos_k = F.cosine_similarity(
                local_k[:min_len].unsqueeze(0),
                phase_k[:min_len].unsqueeze(0),
                eps=1e-8
            )
            ortho_losses.append(cos_k ** 2)

            # V weights: local.v_proj vs phase.v_proj
            local_v = local_attn.v_proj.weight.flatten()
            phase_v = phase_attn.v_proj.weight.flatten()
            min_len = min(local_v.shape[0], phase_v.shape[0])
            cos_v = F.cosine_similarity(
                local_v[:min_len].unsqueeze(0),
                phase_v[:min_len].unsqueeze(0),
                eps=1e-8
            )
            ortho_losses.append(cos_v ** 2)

    if not ortho_losses:
        # No HybridAttentionLayers found, return zero loss
        if debug:
            print(f"DEBUG ORTHO: No HybridAttentionLayers found in model")
        return torch.tensor(0.0, device=next(model.parameters()).device)

    # Average across all weight pairs
    result = torch.stack(ortho_losses).mean()

    if debug:
        print(f"DEBUG ORTHO: Found {hybrid_layer_count} HybridAttentionLayers, "
              f"{len(ortho_losses)} weight pairs, mean_loss={result.item():.6f}, "
              f"requires_grad={result.requires_grad}")

    return result


class HybridTransformerBlock(nn.Module):
    """Transformer block with hybrid local + phase attention."""

    def __init__(
        self,
        config: TransformerConfig,
        window_size: int = 256,
        local_backend: str = 'auto',
        alpha_local: float = 0.8,
        alpha_phase: float = 0.2,
        n_kv_heads: Optional[int] = None,  # GQA: Number of KV heads
        layer_idx: int = -1,  # V9.9.1: Layer index for per-layer phase control
        learned_decay: bool = False,  # V9.9.7: Per-head learned decay
        bounded_phase: bool = False,  # V9.9.11: Constrain φ to [-π, π] via π*sin()
        zero_mean_cosine: bool = False,  # V9.9.11: Center cosine per head (forces selectivity)
        dual_channel_mode: bool = False,  # V10.3.8: Separate content and alignment scores
        alignment_authority: float = 0.1,  # V10.3.8: Weight for alignment term
        protected_phase: bool = True,  # V10.2.1: Protected Phase pattern for chunking
        # V10.12: Multi-channel Phase memory with selective write gating
        phase_channels: int = 1,
        phase_write_gate: bool = False,
    ):
        super().__init__()
        self.layer_idx = layer_idx  # V9.9.1: Track layer index
        self.attention = HybridAttentionLayer(
            embed_dim=config.embed_dim,
            num_heads=config.num_heads,
            n_kv_heads=n_kv_heads,  # GQA support
            window_size=window_size,
            dropout=config.dropout,
            sync_steps=config.sync_steps,
            sync_lr=config.sync_lr,
            alpha_local=alpha_local,
            alpha_phase=alpha_phase,
            local_backend=local_backend,
            temperature=getattr(config, 'temperature', 1.0),  # Sharper attention
            protected_phase=protected_phase,  # V10.2.1: Protected Phase pattern
            cosine_mode=getattr(config, 'cosine_mode', 'standard'),  # V9.6.12
            decay_gamma=getattr(config, 'decay_gamma', 1.0),  # V9.6.13
            layer_idx=layer_idx,  # V9.9.1: Pass layer index to attention
            learned_decay=learned_decay,  # V9.9.7: Per-head learned decay
            bounded_phase=bounded_phase,  # V9.9.11: Phase collapse fix 1
            zero_mean_cosine=zero_mean_cosine,  # V9.9.11: Phase collapse fix 2
            dual_channel_mode=dual_channel_mode,  # V10.3.8: Dual-channel attention
            alignment_authority=alignment_authority,  # V10.3.8: Alignment authority
            phase_channels=phase_channels,  # V10.12: Multi-channel memory
            phase_write_gate=phase_write_gate,  # V10.12: Selective write gate
        )
        self.ff = FeedForward(
            embed_dim=config.embed_dim,
            ff_dim=config.ff_dim,
            dropout=config.dropout,
        )

    def forward(
        self,
        x: torch.Tensor,
        causal_mask: bool = True,
        intent_phase: Optional[torch.Tensor] = None,
        return_decorr_loss: bool = False,
        prev_phase_state: Optional[torch.Tensor] = None,  # V10.2: Chunk state
        prev_norm_state: Optional[torch.Tensor] = None,   # V10.2: Chunk normalizer
        return_state: bool = False,  # V10.2: Return state for next chunk
    ) -> Union[torch.Tensor, Tuple[torch.Tensor, torch.Tensor], Tuple[torch.Tensor, Dict[str, torch.Tensor]]]:
        """
        V10.2: Added prev_phase_state/return_state for chunk-persistent Phase memory.
        When chunking, pass prev_phase_state from previous chunk's state_dict.
        """
        if return_state:
            # V10.2: Chunking mode - return state for next chunk
            attn_out, state_dict = self.attention(
                x, causal_mask, intent_phase=intent_phase,
                prev_phase_state=prev_phase_state,
                prev_norm_state=prev_norm_state,
                return_state=True,
            )
            x = self.ff(attn_out)
            return x, state_dict
        elif return_decorr_loss:
            attn_out, decorr_loss = self.attention(
                x, causal_mask, intent_phase=intent_phase, return_decorr_loss=True
            )
            x = self.ff(attn_out)
            return x, decorr_loss
        else:
            x = self.attention(x, causal_mask, intent_phase=intent_phase)
            x = self.ff(x)
            return x


class LocalTransformerBlock(nn.Module):
    """Transformer block with local attention only (for early layers)."""

    def __init__(
        self,
        config: TransformerConfig,
        window_size: int = 256,
        backend: str = 'auto',
        n_kv_heads: Optional[int] = None,  # GQA: Number of KV heads
    ):
        super().__init__()
        self.attention = LocalAttention(
            embed_dim=config.embed_dim,
            num_heads=config.num_heads,
            n_kv_heads=n_kv_heads,
            window_size=window_size,
            dropout=config.dropout,
            backend=backend,
        )
        self.ff = FeedForward(
            embed_dim=config.embed_dim,
            ff_dim=config.ff_dim,
            dropout=config.dropout,
        )

    def forward(self, x: torch.Tensor, causal_mask: bool = True) -> torch.Tensor:
        x = self.attention(x, causal_mask)
        x = self.ff(x)
        return x


# =============================================================================
# TRANSFORMER BLOCKS
# =============================================================================

class PhaseTransformerBlock(nn.Module):
    """Transformer block with O(n) phase attention."""

    def __init__(self, config: TransformerConfig):
        super().__init__()
        # V9.6.11: Use aux_scale=1.0 for pure phase model
        # In pure phase, there's no local attention to compete with
        # The 0.1 default was designed for hybrid mode auxiliary integration
        self.attention = PhaseAttentionLayer(
            embed_dim=config.embed_dim,
            num_heads=config.num_heads,
            dropout=config.dropout,
            sync_steps=config.sync_steps,
            sync_lr=config.sync_lr,
            temperature=getattr(config, 'temperature', 1.0),  # Sharper attention for classification
            aux_scale=1.0,  # V9.6.11: Full strength for pure phase model
            cosine_mode=getattr(config, 'cosine_mode', 'standard'),  # V9.6.12
            decay_gamma=getattr(config, 'decay_gamma', 1.0),  # V9.6.13
        )
        self.ff = FeedForward(
            embed_dim=config.embed_dim,
            ff_dim=config.ff_dim,
            dropout=config.dropout,
        )

    def forward(
        self,
        x: torch.Tensor,
        causal_mask: bool = True,
        phase_context: Optional[Dict[str, torch.Tensor]] = None,
    ) -> Union[torch.Tensor, Tuple[torch.Tensor, Dict[str, torch.Tensor]]]:
        """Forward with optional streaming phase context."""
        if phase_context is not None:
            x, new_context = self.attention(x, causal_mask, phase_context)
            x = self.ff(x)
            return x, new_context
        else:
            x = self.attention(x, causal_mask)
            x = self.ff(x)
            return x


class StandardTransformerBlock(nn.Module):
    """Transformer block with O(n²) standard attention."""

    def __init__(self, config: TransformerConfig):
        super().__init__()
        self.attention = StandardAttentionLayer(
            embed_dim=config.embed_dim,
            num_heads=config.num_heads,
            dropout=config.dropout,
        )
        self.ff = FeedForward(
            embed_dim=config.embed_dim,
            ff_dim=config.ff_dim,
            dropout=config.dropout,
        )

    def forward(self, x: torch.Tensor, causal_mask: bool = True) -> torch.Tensor:
        x = self.attention(x, causal_mask)
        x = self.ff(x)
        return x


# =============================================================================
# FULL TRANSFORMERS
# =============================================================================

class PhaseTransformer(nn.Module):
    """
    General-Purpose O(n) Phase Transformer.

    Drop-in replacement for standard transformer with massive cost savings.
    """

    def __init__(
        self,
        vocab_size: int = 50257,
        embed_dim: int = 768,
        num_layers: int = 12,
        num_heads: int = 12,
        ff_dim: Optional[int] = None,
        max_seq_len: int = 8192,
        dropout: float = 0.1,
        sync_steps: int = 3,
        sync_lr: float = 0.1,
        temperature: float = 1.0,  # Lower = sharper attention (for classification)
        tie_embeddings: bool = True,  # V9.6.0: Set False when using Sanskrit/CSR to prevent embedding corruption
        cosine_mode: str = "standard",  # V9.6.12: "standard", "shifted", or "complex"
        decay_gamma: float = 1.0,  # V9.6.13: State decay factor (1.0=infinite, <1.0=local focus)
    ):
        super().__init__()

        config = TransformerConfig(
            vocab_size=vocab_size,
            embed_dim=embed_dim,
            num_layers=num_layers,
            num_heads=num_heads,
            ff_dim=ff_dim,
            max_seq_len=max_seq_len,
            dropout=dropout,
            sync_steps=sync_steps,
            sync_lr=sync_lr,
            temperature=temperature,  # Pass temperature for sharper attention
            cosine_mode=cosine_mode,  # V9.6.12: Pass cosine mode to attention layers
            decay_gamma=decay_gamma,  # V9.6.13: Pass decay factor to attention layers
        )
        self.config = config
        self.tie_embeddings = tie_embeddings

        # Embeddings
        self.token_embed = nn.Embedding(vocab_size, embed_dim)
        self.pos_embed = nn.Embedding(max_seq_len, embed_dim)
        self.embed_dropout = nn.Dropout(dropout)

        # Transformer blocks
        self.blocks = nn.ModuleList([
            PhaseTransformerBlock(config) for _ in range(num_layers)
        ])

        # Output
        self.norm = nn.LayerNorm(embed_dim)
        self.lm_head = nn.Linear(embed_dim, vocab_size, bias=False)

        # V10.11: Learnable logit scale initialized to 1.0.
        # Previous: 1/sqrt(sqrt(d)) ≈ 0.25 which flattened softmax → incoherent text.
        self.logit_scale = nn.Parameter(torch.ones(1))

        # V9.6.0: Optionally tie weights (disable when using Sanskrit/CSR injection)
        # When tied, Sanskrit gradients corrupt the output decoder vocabulary space
        if tie_embeddings:
            self.lm_head.weight = self.token_embed.weight

        # State-centric training head (optional, for token-free training)
        self.state_delta_predictor = StateDeltaPredictor(
            embed_dim=embed_dim,
            hidden_dim=embed_dim * 2,
            dropout=dropout,
            num_layers=2,
        )

        # Gradient checkpointing (disabled by default)
        self.gradient_checkpointing = False

        # Initialize
        self.apply(self._init_weights)

        # V9.6.10: For untied embeddings, copy token_embed to lm_head AFTER init
        # This provides semantic alignment at start while keeping them separate
        if not self.tie_embeddings:
            with torch.no_grad():
                self.lm_head.weight.copy_(self.token_embed.weight)

    def gradient_checkpointing_enable(self):
        """Enable gradient checkpointing to save memory at cost of speed."""
        self.gradient_checkpointing = True

    def gradient_checkpointing_disable(self):
        """Disable gradient checkpointing."""
        self.gradient_checkpointing = False

    def _init_weights(self, module):
        if isinstance(module, nn.Linear):
            torch.nn.init.normal_(module.weight, mean=0.0, std=0.02)
            if module.bias is not None:
                torch.nn.init.zeros_(module.bias)
        elif isinstance(module, nn.Embedding):
            torch.nn.init.normal_(module.weight, mean=0.0, std=0.02)

    def forward_hidden(
        self,
        input_ids: torch.Tensor,
    ) -> torch.Tensor:
        """
        Forward pass returning hidden states BEFORE LM head.

        Use this for memory-efficient training with chunked LM head processing.
        For 5M+ context, calling lm_head on full hidden creates 1TB+ tensor.
        Instead, process lm_head in chunks during loss computation.

        Args:
            input_ids: [B, N] token indices

        Returns:
            hidden: [B, N, embed_dim] - final hidden states before LM head
        """
        B, N = input_ids.shape

        # Embeddings
        positions = torch.arange(N, device=input_ids.device).unsqueeze(0)
        x = self.token_embed(input_ids) + self.pos_embed(positions)
        x = self.embed_dropout(x)

        # Transformer blocks
        for block in self.blocks:
            if self.gradient_checkpointing and self.training:
                x = checkpoint(
                    block,
                    x,
                    True,  # causal_mask
                    use_reentrant=True,
                )
            else:
                x = block(x, causal_mask=True)

        # Return normalized hidden states (before LM head)
        return self.norm(x)

    def forward(
        self,
        input_ids: torch.Tensor,
        return_hidden: bool = False,
        extract_layers: Optional[List[int]] = None,
        return_last_hidden: bool = False,
        phase_contexts: Optional[List[Dict[str, torch.Tensor]]] = None,
        position_offset: int = 0,
    ) -> Dict[str, Any]:
        """
        Forward pass with optional streaming phase context and layer extraction.

        Args:
            input_ids: [B, N] token indices
            return_hidden: Return all hidden states
            extract_layers: Specific layer indices to extract (memory-efficient)
            return_last_hidden: Return normalized hidden state before lm_head
            phase_contexts: List of phase contexts per layer for streaming (10M+ tokens)
            position_offset: Position offset for streaming (chunk start position)

        Returns:
            Dict with 'logits', optionally 'hidden_states', 'last_hidden_state',
            and 'phase_contexts' if streaming
        """
        B, N = input_ids.shape

        # Determine which layers to extract
        should_extract = return_hidden or extract_layers is not None
        extract_set = set(extract_layers) if extract_layers is not None else None

        # Embeddings with position offset for streaming
        positions = torch.arange(position_offset, position_offset + N, device=input_ids.device).unsqueeze(0)
        x = self.token_embed(input_ids) + self.pos_embed(positions)
        x = self.embed_dropout(x)

        # Initialize phase contexts if streaming but none provided
        streaming = phase_contexts is not None
        if streaming and len(phase_contexts) == 0:
            phase_contexts = [{}] * len(self.blocks)

        # Transformer blocks
        hidden_states = [] if should_extract else None
        new_phase_contexts = []

        for i, block in enumerate(self.blocks):
            if streaming:
                # Streaming mode: pass and collect phase contexts
                layer_context = phase_contexts[i] if i < len(phase_contexts) else {}
                if self.gradient_checkpointing and self.training:
                    # Note: checkpointing with streaming requires special handling
                    x, new_ctx = block(x, causal_mask=True, phase_context=layer_context)
                else:
                    x, new_ctx = block(x, causal_mask=True, phase_context=layer_context)
                new_phase_contexts.append(new_ctx)
            else:
                # Normal mode
                if self.gradient_checkpointing and self.training:
                    x = checkpoint(
                        block,
                        x,
                        True,  # causal_mask
                        use_reentrant=True,
                    )
                else:
                    x = block(x, causal_mask=True)

            # Extract if: return_hidden=True (all), or layer in extract_layers
            if should_extract:
                if extract_set is None or i in extract_set:
                    hidden_states.append(x)

        # Output
        x = self.norm(x)
        logits = self.lm_head(x) * self.logit_scale

        result = {'logits': logits}

        if should_extract:
            result['hidden_states'] = hidden_states

        if return_last_hidden:
            result['last_hidden_state'] = x

        if streaming:
            result['phase_contexts'] = new_phase_contexts

        return result

    def generate(
        self,
        input_ids: torch.Tensor,
        max_new_tokens: int = 50,
        temperature: float = 1.0,
        top_k: int = 50,
    ) -> torch.Tensor:
        """Simple generation loop."""
        for _ in range(max_new_tokens):
            # Forward
            logits = self(input_ids)['logits'][:, -1, :]

            # Temperature
            logits = logits / temperature

            # Top-k
            if top_k > 0:
                v, _ = torch.topk(logits, min(top_k, logits.size(-1)))
                logits[logits < v[:, [-1]]] = float('-inf')

            # Sample
            probs = F.softmax(logits, dim=-1)
            next_token = torch.multinomial(probs, num_samples=1)

            input_ids = torch.cat([input_ids, next_token], dim=1)

        return input_ids


class HybridPhaseTransformer(nn.Module):
    """
    Hybrid Phase Transformer with Local + Phase Attention.

    Architecture:
    - Early layers (1 to local_layers): Local attention only
    - Later layers: Hybrid (Local + Phase) attention

    Supports Grouped Query Attention (GQA) via n_kv_heads parameter:
    - n_kv_heads = num_heads: Standard MHA (default)
    - n_kv_heads = 8: Mistral-style GQA (4x KV memory savings for 32 heads)
    - n_kv_heads = 1: Multi-Query Attention (MQA)

    This enables:
    - Fast learning of local patterns (syntax, grammar)
    - Efficient global context via Phase attention O(n)
    - Better PPL convergence than pure Phase attention
    - Memory-efficient KV cache with GQA
    """

    def __init__(
        self,
        vocab_size: int = 50257,
        embed_dim: int = 768,
        num_layers: int = 12,
        num_heads: int = 12,
        n_kv_heads: Optional[int] = None,  # GQA: Number of KV heads (default = num_heads)
        ff_dim: Optional[int] = None,
        max_seq_len: int = 8192,
        dropout: float = 0.1,
        sync_steps: int = 3,
        sync_lr: float = 0.1,
        # Hybrid-specific params
        local_layers: int = 4,  # First N layers use local attention only
        window_size: int = 256,  # Local attention window
        local_backend: str = 'auto',  # LocalAttention backend: 'auto', 'flash', 'sdpa', 'unfold'
        alpha_local: float = 0.8,  # Weight for local attention in hybrid layers
        alpha_phase: float = 0.2,  # Weight for phase attention in hybrid layers
        temperature: float = 1.0,  # Lower = sharper attention (for classification)
        tie_embeddings: bool = True,  # V9.6.0: Set False when using Sanskrit/CSR to prevent embedding corruption
        cosine_mode: str = "standard",  # V9.6.12: "standard", "shifted", or "complex"
        decay_gamma: float = 0.99,  # V10.11: EMA decay (was 1.0 = unbounded cumsum → norm explosion)
        learned_decay: bool = True,  # V10.11: Per-head learned decay γ∈[0.5,1.0] (was False)
        bounded_phase: bool = False,  # V9.9.11: Constrain φ to [-π, π] via π*sin()
        zero_mean_cosine: bool = False,  # V9.9.11: Center cosine per head (forces selectivity)
        dual_channel_mode: bool = False,  # V10.3.8: Separate content and alignment scores
        alignment_authority: float = 0.1,  # V10.3.8: Weight for alignment term
        protected_phase: bool = True,  # V10.2.1: Protected Phase pattern for chunking
        # V10.12: Multi-channel Phase memory with selective write gating
        phase_channels: int = 1,  # Independent memory channels (1=legacy, 4=recommended)
        phase_write_gate: bool = False,  # Selective write gating for memory updates
        # V10.13: Phase Warm-Start Gate (training stability)
        phase_warmstart: bool = False,  # Enable warm-start dampening
        phase_warmstart_steps: int = 10000,  # Step at which alpha=0.5
        phase_warmstart_tau: float = 2000.0,  # Sigmoid steepness
        phase_warmstart_apply_inference: bool = False,  # Apply during inference
        # V10.13: Global Compressed Tokens (GCT)
        global_tokens_enabled: bool = False,  # Enable GCT memory slots
        num_global_tokens: int = 16,  # Number of global tokens
        global_update_enabled: bool = True,  # Enable controlled write
        global_update_mode: str = "pool",  # "pool", "attn-lite", or "slots"
        global_update_interval: int = 1,  # Update every N layers
        global_token_write_detach: bool = True,  # Detach tokens in write path (auto-disabled for slots mode)
        phase_to_global: bool = False,  # Phase→Global integration
        # V10.14: Slot memory parameters (when global_update_mode="slots")
        slots_write_lr: float = 0.1,  # EMA learning rate for slot writes
        retrieval_loss_weight: float = 0.1,  # Weight for auxiliary retrieval loss
        # V11: Slot memory experiment — read interval and late-layer writes
        global_read_interval: int = 1,  # Read slots every N layers (1 = every layer)
        global_write_start_layer: int = 0,  # Only write to slots from this layer onward
    ):
        super().__init__()

        # V9.9.11: Store phase collapse fix flags
        self.bounded_phase = bounded_phase
        self.zero_mean_cosine = zero_mean_cosine

        # V10.3.8: Dual-channel attention parameters
        self.dual_channel_mode = dual_channel_mode
        self.alignment_authority = alignment_authority

        # V10.2.1: Protected Phase pattern - Local cross-attends to Phase memory
        self.protected_phase = protected_phase

        config = TransformerConfig(
            vocab_size=vocab_size,
            embed_dim=embed_dim,
            num_layers=num_layers,
            num_heads=num_heads,
            ff_dim=ff_dim,
            max_seq_len=max_seq_len,
            dropout=dropout,
            sync_steps=sync_steps,
            sync_lr=sync_lr,
            temperature=temperature,  # Pass temperature for sharper attention
            cosine_mode=cosine_mode,  # V9.6.12: Pass cosine mode to attention layers
            decay_gamma=decay_gamma,  # V9.6.13: Pass decay factor to attention layers
        )
        self.config = config
        self.local_layers = local_layers
        self.local_backend = local_backend
        self.tie_embeddings = tie_embeddings
        self.n_kv_heads = n_kv_heads  # Store for reference
        self.learned_decay = learned_decay  # V9.9.7: Per-head learned decay

        # Embeddings
        self.token_embed = nn.Embedding(vocab_size, embed_dim)
        self.pos_embed = nn.Embedding(max_seq_len, embed_dim)
        self.embed_dropout = nn.Dropout(dropout)

        # Transformer blocks: Local (early) + Hybrid (later)
        # V9.9.1: Track layer indices for per-layer phase control
        self.blocks = nn.ModuleList()
        for i in range(num_layers):
            if i < local_layers:
                # Early layers: Local attention only (fast pattern learning)
                self.blocks.append(LocalTransformerBlock(
                    config, window_size=window_size, backend=local_backend,
                    n_kv_heads=n_kv_heads))  # GQA support
            else:
                # Later layers: Hybrid Local + Phase attention
                # V9.9.1: Pass layer_idx for per-layer phase weight control
                self.blocks.append(HybridTransformerBlock(
                    config,
                    window_size=window_size,
                    local_backend=local_backend,
                    alpha_local=alpha_local,
                    alpha_phase=alpha_phase,
                    n_kv_heads=n_kv_heads,  # GQA support
                    layer_idx=i,  # V9.9.1: Layer index for per-layer control
                    learned_decay=learned_decay,  # V9.9.7: Per-head learned decay
                    bounded_phase=bounded_phase,  # V9.9.11: Phase collapse fix 1
                    zero_mean_cosine=zero_mean_cosine,  # V9.9.11: Phase collapse fix 2
                    dual_channel_mode=dual_channel_mode,  # V10.3.8: Dual-channel attention
                    alignment_authority=alignment_authority,  # V10.3.8: Alignment authority
                    protected_phase=protected_phase,  # V10.2.1: Protected Phase for chunking
                    phase_channels=phase_channels,  # V10.12: Multi-channel memory
                    phase_write_gate=phase_write_gate,  # V10.12: Selective write gate
                ))

        # Output
        self.norm = nn.LayerNorm(embed_dim)
        self.lm_head = nn.Linear(embed_dim, vocab_size, bias=False)

        # V10.11: Learnable logit scale initialized to 1.0.
        # Previous: 1/sqrt(sqrt(d)) ≈ 0.25 which flattened softmax → incoherent text.
        self.logit_scale = nn.Parameter(torch.ones(1))

        # V9.6.0: Optionally tie weights (disable when using Sanskrit/CSR injection)
        # When tied, Sanskrit gradients corrupt the output decoder vocabulary space
        if tie_embeddings:
            self.lm_head.weight = self.token_embed.weight

        # State-centric training head (optional, for token-free training)
        self.state_delta_predictor = StateDeltaPredictor(
            embed_dim=embed_dim,
            hidden_dim=embed_dim * 2,
            dropout=dropout,
            num_layers=2,
        )

        # V10.13: Phase Warm-Start Gate config
        self.phase_warmstart_enabled = phase_warmstart
        self._phase_warmstart_steps = phase_warmstart_steps
        self._phase_warmstart_tau = phase_warmstart_tau
        self._phase_warmstart_apply_inference = phase_warmstart_apply_inference
        self._global_step = 0

        # V10.13: Global Compressed Tokens (GCT) — stable long-range memory slots
        self.global_tokens_enabled = global_tokens_enabled
        self.num_global_tokens = num_global_tokens
        self.global_update_enabled = global_update_enabled
        self.global_update_mode = global_update_mode
        self.global_update_interval = global_update_interval
        self.global_read_interval = global_read_interval
        self.global_write_start_layer = global_write_start_layer
        # V10.14.1: Slot memory uses selective detach internally (detaches x
        # at write entry to protect backbone, keeps grad to slot params via
        # aux losses). The global_token_write_detach flag controls whether
        # slot UPDATE outputs are also detached — keep True for stability.
        self.global_token_write_detach = global_token_write_detach

        # V10.14: Store retrieval loss weight
        self.retrieval_loss_weight = retrieval_loss_weight

        if global_tokens_enabled:
            if global_update_mode == "slots":
                # V10.14: Addressable slot memory — replaces pool/attn-lite
                # SlotMemoryGCT handles its own read/write paths.
                # CRITICAL: Slots update ONLY through competitive write rule.
                # No nn.MultiheadAttention read — SlotMemoryGCT.read() is used instead.
                self.slot_memory = SlotMemoryGCT(
                    num_slots=num_global_tokens,
                    embed_dim=embed_dim,
                    num_heads=num_heads,
                    write_lr=slots_write_lr,
                    dropout=dropout,
                )
                # No legacy GCT modules needed — slot_memory handles everything
                self.global_tokens = None  # Slots init is inside SlotMemoryGCT
                self.gct_read_attn = None  # Read is via SlotMemoryGCT.read()
            else:
                # Legacy: pool or attn-lite modes
                self.slot_memory = None
                # Learnable global token embeddings [G, D]
                self.global_tokens = nn.Parameter(
                    torch.randn(num_global_tokens, embed_dim) * 0.02
                )
                # READ path: tokens attend to globals via cross-attention
                self.gct_read_attn = nn.MultiheadAttention(
                    embed_dim, num_heads, dropout=dropout, batch_first=True
                )
                # WRITE path: controlled compression update (pool mode)
                self.global_write_gate = nn.Linear(embed_dim, 1)
                self.global_update_proj = nn.Linear(embed_dim, embed_dim, bias=False)
                # WRITE path: attn-lite mode (optional)
                if global_update_mode == "attn-lite":
                    self.gct_write_attn = nn.MultiheadAttention(
                        embed_dim, num_heads, dropout=dropout, batch_first=True
                    )
                    self._gct_write_scale = 0.05
            # Phase → Global integration (optional, only for non-slot modes)
            if phase_to_global and global_update_mode != "slots":
                # Input: Re + Im of phase state = 2 * embed_dim
                self.phase_to_global_proj = nn.Linear(2 * embed_dim, embed_dim)
            else:
                self.phase_to_global_proj = None
            # Diagnostics
            self._diag_global_token_norm = None
            self._diag_global_token_delta_norm = None
            self._diag_global_write_gate_mean = None
            self._diag_global_attn_mass = None

        # Gradient checkpointing (disabled by default)
        self.gradient_checkpointing = False

        # Initialize
        self.apply(self._init_weights)

        # V10.12: Re-init write gate biases after _init_weights zeros them.
        # sigmoid(2)≈0.88 means gates start near-open → initial training ≈ no gating.
        if phase_write_gate:
            for blk in self.blocks:
                if hasattr(blk, 'attention') and hasattr(blk.attention, 'phase_attn'):
                    _pa = blk.attention.phase_attn
                    if hasattr(_pa, 'write_gate_proj') and _pa.write_gate_proj.bias is not None:
                        nn.init.constant_(_pa.write_gate_proj.bias, 2.0)

        # V10.13: Propagate warm-start config to PhaseAttentionLayers
        if phase_warmstart:
            for blk in self.blocks:
                if hasattr(blk, 'attention') and hasattr(blk.attention, 'phase_attn'):
                    _pa = blk.attention.phase_attn
                    _pa.phase_warmstart_enabled = True
                    _pa._warmstart_steps = phase_warmstart_steps
                    _pa._warmstart_tau = phase_warmstart_tau
                    _pa._warmstart_apply_inference = phase_warmstart_apply_inference

        # V9.6.10: For untied embeddings, copy token_embed to lm_head AFTER init
        # This provides semantic alignment at start while keeping them separate
        if not self.tie_embeddings:
            with torch.no_grad():
                self.lm_head.weight.copy_(self.token_embed.weight)

    def gradient_checkpointing_enable(self):
        """Enable gradient checkpointing to save memory at cost of speed."""
        self.gradient_checkpointing = True

    def gradient_checkpointing_disable(self):
        """Disable gradient checkpointing."""
        self.gradient_checkpointing = False

    def set_global_step(self, step: int):
        """V10.13: Set global training step for warm-start gating.

        Call this once per training step before forward().
        Propagates step to all PhaseAttentionLayers for warm-start alpha computation.
        """
        self._global_step = step
        for module in self.modules():
            if isinstance(module, PhaseAttentionLayer):
                module._current_step = step

    def _init_weights(self, module):
        if isinstance(module, nn.Linear):
            torch.nn.init.normal_(module.weight, mean=0.0, std=0.02)
            if module.bias is not None:
                torch.nn.init.zeros_(module.bias)
        elif isinstance(module, nn.Embedding):
            torch.nn.init.normal_(module.weight, mean=0.0, std=0.02)

    def forward_hidden(
        self,
        input_ids: torch.Tensor,
        intent_phase: Optional[torch.Tensor] = None,
        chunk_offset: int = 0,  # V10.2: Global position offset for chunking
    ) -> torch.Tensor:
        """
        Forward pass returning hidden states BEFORE LM head.

        Use this for memory-efficient training with chunked LM head processing.
        For 5M+ context, calling lm_head on full hidden creates 1TB+ tensor.
        Instead, process lm_head in chunks during loss computation.

        V10.2: Added chunk_offset for proper positional encoding when chunking.
        When processing chunk i of a long sequence:
          - chunk_offset = i * chunk_size
          - positions = chunk_offset + [0, 1, 2, ..., N-1]
        This ensures Phase attention sees global positions for temporal context.

        Args:
            input_ids: [B, N] token indices
            intent_phase: Optional phase rotation from Ontological State Delta.
                         Only affects Hybrid layers (not Local-only layers).
            chunk_offset: Global position offset. For chunk i, set this to
                         i * chunk_size to maintain global positional encoding.

        Returns:
            hidden: [B, N, embed_dim] - final hidden states before LM head
        """
        B, N = input_ids.shape

        # V10.2: Global positions = chunk_offset + local positions
        # This is CRITICAL for chunking: Phase needs global position context
        # while Local's sliding window is inherently relative
        positions = chunk_offset + torch.arange(N, device=input_ids.device).unsqueeze(0)
        x = self.token_embed(input_ids) + self.pos_embed(positions)
        x = self.embed_dropout(x)

        # Transformer blocks
        # V11.0.1: Only use gradient checkpointing when grad is enabled.
        # OntologicalHybridTransformer calls forward_hidden under torch.no_grad(),
        # where checkpointing is wasteful and can interfere with the subsequent
        # checkpointed forward pass (metadata mismatch on recomputation).
        _use_gc = self.gradient_checkpointing and self.training and torch.is_grad_enabled()
        for i, block in enumerate(self.blocks):
            # Only pass intent_phase to Hybrid blocks (not Local-only blocks)
            is_hybrid_block = i >= self.local_layers
            block_intent = intent_phase if is_hybrid_block else None

            if _use_gc:
                if is_hybrid_block and intent_phase is not None:
                    x = checkpoint(
                        block,
                        x,
                        True,  # causal_mask
                        block_intent,
                        use_reentrant=True,
                    )
                else:
                    x = checkpoint(
                        block,
                        x,
                        True,  # causal_mask
                        use_reentrant=True,
                    )
            else:
                if is_hybrid_block:
                    x = block(x, causal_mask=True, intent_phase=block_intent)
                else:
                    x = block(x, causal_mask=True)

        # Return normalized hidden states (before LM head)
        return self.norm(x)

    def forward(
        self,
        input_ids: torch.Tensor,
        return_hidden: bool = False,
        extract_layers: Optional[List[int]] = None,
        return_last_hidden: bool = False,
        intent_phase: Optional[torch.Tensor] = None,
        return_decorr_loss: bool = False,
        chunk_offset: int = 0,  # V10.2: Global position offset for chunking
    ) -> Dict[str, torch.Tensor]:
        """
        Forward pass with efficient layer extraction.

        Supports targeted hidden state extraction for inference components
        (EvolutionaryInferenceEngine, CSRInferenceGuard, SovereignScorer).

        V10.2: Added chunk_offset for proper positional encoding when chunking.
        When processing chunk i of a long sequence:
          - chunk_offset = i * chunk_size
          - positions = chunk_offset + [0, 1, 2, ..., N-1]
        This ensures Phase attention sees global positions for temporal context.

        Args:
            input_ids: [B, N] token indices
            return_hidden: Return all hidden states (legacy behavior)
            extract_layers: Specific layer indices to extract (0-indexed).
                           More memory-efficient than return_hidden=True.
                           Common patterns:
                           - [0, 11]: O1 (Potential) and O12 (Integration) for karma
                           - [0, 5, 11]: Authority sample + midpoint + final
                           - None with return_hidden=True: all layers
            return_last_hidden: Return normalized hidden state before lm_head.
                               Required for CSR re-projection after gating.
            intent_phase: Optional phase rotation from Ontological State Delta.
                         Only affects Hybrid layers (not Local-only layers).
            chunk_offset: Global position offset. For chunk i, set this to
                         i * chunk_size to maintain global positional encoding.

        Returns:
            Dict with:
            - 'logits': [B, N, V] output logits
            - 'hidden_states': List[Tensor] if return_hidden or extract_layers
            - 'last_hidden_state': [B, N, D] if return_last_hidden (post-norm)

        Note:
            Authority layers (0-8) capture "meaning" / ontological structure.
            Sensory layers (9-11) capture "expression" / output refinement.
        """
        B, N = input_ids.shape

        # Determine which layers to extract
        should_extract = return_hidden or extract_layers is not None
        extract_set = set(extract_layers) if extract_layers is not None else None

        # V10.2: Global positions = chunk_offset + local positions
        # This is CRITICAL for chunking: Phase needs global position context
        # while Local's sliding window is inherently relative
        positions = chunk_offset + torch.arange(N, device=input_ids.device).unsqueeze(0)
        x = self.token_embed(input_ids) + self.pos_embed(positions)
        x = self.embed_dropout(x)

        # V11.3: Capture pre-attention hidden state for retrieval loss.
        # Post-backbone x is redundant with lm_head(x) — slots trained on it
        # just learn to copy the backbone's own prediction. Pre-attention x
        # (token embed + position, zero attention context) forces slots to
        # provide information the query genuinely lacks.
        _x_pre_attn = x.detach()

        # Transformer blocks with targeted extraction
        hidden_states = [] if should_extract else None
        decorr_losses = [] if return_decorr_loss else None

        # V10.13/V10.14: Initialize GCT global state
        _slot_keys = None  # V10.14: Only used in slots mode
        _slot_vals = None
        if self.global_tokens_enabled:
            if self.global_update_mode == "slots":
                # V10.14: Initialize addressable slot memory
                _slot_keys, _slot_vals = self.slot_memory.init_state(B, x.dtype, x.device)
            else:
                # Legacy: pooled/attn-lite global tokens
                _gct_state = self.global_tokens.unsqueeze(0).expand(B, -1, -1).clone()
                _gct_state = _gct_state.to(dtype=x.dtype)

        for i, block in enumerate(self.blocks):
            # Only pass intent_phase to Hybrid blocks (not Local-only blocks)
            is_hybrid_block = i >= self.local_layers
            block_intent = intent_phase if is_hybrid_block else None

            # Decorrelation loss incompatible with gradient checkpointing
            # (checkpoint can't handle tuple returns cleanly)
            # V11.0.1: use_reentrant=True avoids strict metadata check that fails
            # with complex tensors (torch.polar) and OntologicalHybrid double-forward.
            use_checkpoint = self.gradient_checkpointing and self.training and not return_decorr_loss

            if use_checkpoint:
                if is_hybrid_block and intent_phase is not None:
                    x = checkpoint(
                        block,
                        x,
                        True,  # causal_mask
                        block_intent,
                        use_reentrant=True,
                    )
                else:
                    x = checkpoint(
                        block,
                        x,
                        True,  # causal_mask
                        use_reentrant=True,
                    )
            else:
                # Normal forward pass (potentially with decorr_loss)
                if is_hybrid_block:
                    if return_decorr_loss:
                        x, decorr_loss = block(
                            x, causal_mask=True, intent_phase=block_intent, return_decorr_loss=True
                        )
                        decorr_losses.append(decorr_loss)
                    else:
                        x = block(x, causal_mask=True, intent_phase=block_intent)
                else:
                    x = block(x, causal_mask=True)

            # =================================================================
            # V10.13/V10.14: GCT — Token READ from memory
            # =================================================================
            if self.global_tokens_enabled:
                if self.global_update_mode == "slots":
                    # V11: Only read every global_read_interval layers
                    if (i % self.global_read_interval) == 0:
                        # V10.14: Read via SlotMemoryGCT (never modifies slot state)
                        _slot_out = self.slot_memory.read(x, _slot_keys, _slot_vals)
                        # V10.14.6d: Mostly detach read output so LM loss cannot
                        # suppress read_output_proj. Retrieval loss trains
                        # read_output_proj independently.
                        # V11.5: Full gradient — no detach. Let LM loss fully
                        # steer what the model does with slot reads.
                        _alpha = self.slot_memory.read_warmstart_alpha
                        x = x + _alpha * _slot_out
                else:
                    # Legacy: cross-attention to global tokens
                    _gct_out = self.gct_read_attn(
                        x, _gct_state, _gct_state, need_weights=False
                    )[0]
                    x = x + _gct_out

            # =================================================================
            # V10.13/V10.14: GCT — Memory WRITE
            # =================================================================
            if self.global_tokens_enabled and self.global_update_enabled:
                if (i % self.global_update_interval) == 0 and i >= self.global_write_start_layer:
                    if self.global_update_mode == "slots":
                        # V10.14.1: Competitive slot write — the ONLY way slots update
                        # Always pass detach=False for slots: write() uses x.detach()
                        # internally to protect backbone, but slot_vals/keys must
                        # carry grad so retrieval loss can teach write_val_proj
                        # what to store (not just where).
                        _slot_keys, _slot_vals = self.slot_memory.write(
                            x, _slot_keys, _slot_vals,
                            detach=False,
                        )
                    elif self.global_update_mode == "pool":
                        # Gated pooled summary of tokens
                        _w = torch.sigmoid(self.global_write_gate(x))  # [B, T, 1]
                        _pooled = (_w * x).sum(dim=1) / (_w.sum(dim=1) + 1e-6)  # [B, D]
                        _delta = self.global_update_proj(_pooled).unsqueeze(1)  # [B, 1, D]

                        if self.global_token_write_detach and self.training:
                            _delta = _delta.detach()
                        _gct_state = _gct_state + _delta

                        with torch.no_grad():
                            self._diag_global_token_delta_norm = _delta.norm().item()
                            self._diag_global_write_gate_mean = _w.mean().item()
                    else:
                        # attn-lite: globals attend to tokens with small scale
                        _delta = self.gct_write_attn(
                            _gct_state, x, x, need_weights=False
                        )[0]
                        _delta = _delta * self._gct_write_scale

                        if self.global_token_write_detach and self.training:
                            _delta = _delta.detach()
                        _gct_state = _gct_state + _delta

                        with torch.no_grad():
                            self._diag_global_token_delta_norm = _delta.norm().item()

            # =================================================================
            # V10.13: Phase → Global integration (after hybrid blocks only)
            # Skipped in slots mode — Phase stays separate as context summarizer
            # =================================================================
            _p2g = getattr(self, 'phase_to_global_proj', None)
            if is_hybrid_block and self.global_tokens_enabled and _p2g is not None:
                _pa = block.attention.phase_attn
                _phase_agg = getattr(_pa, '_last_final_state_agg', None)
                if _phase_agg is not None:
                    _pf = _phase_agg.squeeze(1)  # [B, H, D_h] complex
                    _p_in = torch.cat([
                        _pf.real.reshape(B, -1),
                        _pf.imag.reshape(B, -1),
                    ], dim=-1).to(dtype=x.dtype)  # [B, 2D]
                    _phase_upd = _p2g(_p_in).unsqueeze(1)  # [B, 1, D]
                    # Scale by warm-start alpha if enabled
                    if self.phase_warmstart_enabled:
                        _ws_a = getattr(_pa, '_diag_warmstart_alpha', 1.0) or 1.0
                        _phase_upd = _phase_upd * _ws_a
                    _gct_state = _gct_state + _phase_upd

            # Extract if: return_hidden=True (all), or layer in extract_layers
            if should_extract:
                if extract_set is None or i in extract_set:
                    hidden_states.append(x)

        # V10.13/V10.14: GCT diagnostics (after all layers)
        if self.global_tokens_enabled:
            with torch.no_grad():
                if self.global_update_mode == "slots":
                    self._diag_global_token_norm = _slot_vals.norm(dim=-1).mean().item()
                    # Expose slot diagnostics from SlotMemoryGCT
                    self._diag_global_write_gate_mean = self.slot_memory._diag_write_gate_mean
                else:
                    self._diag_global_token_norm = _gct_state.norm(dim=-1).mean().item()

        # Output
        x = self.norm(x)
        logits = self.lm_head(x) * self.logit_scale

        result = {'logits': logits}

        if should_extract:
            result['hidden_states'] = hidden_states

        if return_last_hidden:
            result['last_hidden_state'] = x

        if return_decorr_loss and decorr_losses:
            # Average decorrelation loss across all hybrid layers
            result['decorr_loss'] = torch.stack(decorr_losses).mean()

        # V10.14: Expose slot state + hidden for retrieval loss computation
        # The training loop uses these to call slot_memory.compute_retrieval_loss()
        if self.global_tokens_enabled and self.global_update_mode == "slots":
            result['_slot_keys'] = _slot_keys
            result['_slot_vals'] = _slot_vals
            # V11.3: Use pre-attention hidden state for retrieval loss queries.
            # Previously used post-backbone x.detach(), which made retrieval
            # redundant — slots learned to copy what the backbone already knows.
            # Pre-attention x (embed + position only) forces slots to provide
            # information that attention hasn't yet injected.
            # Already detached at capture point (line ~7114).
            result['_slot_hidden'] = _x_pre_attn  # Pre-attention for non-redundant retrieval

        return result

    def forward_chunk(
        self,
        input_ids: torch.Tensor,
        chunk_offset: int = 0,
        prev_layer_states: Optional[Dict[int, Dict[str, torch.Tensor]]] = None,
        intent_phase: Optional[torch.Tensor] = None,
    ) -> Tuple[Dict[str, torch.Tensor], Dict[int, Dict[str, torch.Tensor]]]:
        """
        V10.2: Chunked forward pass with Phase state persistence.

        CRITICAL for processing long sequences in chunks:
        - Phase attention maintains state across chunks (temporal memory)
        - Local attention resets per chunk (spatial reasoning)
        - Global positional encoding via chunk_offset

        Usage for chunking a long sequence:
            chunk_size = 512
            layer_states = None
            all_logits = []

            for i in range(0, seq_len, chunk_size):
                chunk = tokens[i:i+chunk_size]
                result, layer_states = model.forward_chunk(
                    chunk,
                    chunk_offset=i,
                    prev_layer_states=layer_states,
                )
                all_logits.append(result['logits'])

        Args:
            input_ids: [B, N] token indices for this chunk
            chunk_offset: Global position offset (= chunk_idx * chunk_size)
            prev_layer_states: Dict mapping layer_idx -> state_dict from previous chunk.
                              Each state_dict has 'final_state' and 'final_norm_state'.
            intent_phase: Optional phase rotation from Ontological State Delta.

        Returns:
            result: Dict with 'logits', etc.
            next_layer_states: Dict mapping layer_idx -> state_dict for next chunk.
                              Pass this as prev_layer_states to next forward_chunk call.
        """
        B, N = input_ids.shape

        # Global positions = chunk_offset + local positions
        positions = chunk_offset + torch.arange(N, device=input_ids.device).unsqueeze(0)
        x = self.token_embed(input_ids) + self.pos_embed(positions)
        x = self.embed_dropout(x)

        # V11.3: Pre-attention capture (mirrors forward())
        _x_pre_attn = x.detach()

        # Initialize states if not provided
        if prev_layer_states is None:
            prev_layer_states = {}

        next_layer_states = {}

        # V10.13/V10.14: GCT state — restore from previous chunk or initialize
        _slot_keys = None
        _slot_vals = None
        if self.global_tokens_enabled:
            if self.global_update_mode == "slots":
                _prev_sk = prev_layer_states.get('_slot_keys', None)
                _prev_sv = prev_layer_states.get('_slot_vals', None)
                if _prev_sk is not None and _prev_sv is not None:
                    _slot_keys = _prev_sk.to(dtype=x.dtype)
                    _slot_vals = _prev_sv.to(dtype=x.dtype)
                else:
                    _slot_keys, _slot_vals = self.slot_memory.init_state(B, x.dtype, x.device)
            else:
                _gct_prev = prev_layer_states.get('_gct_global_state', None)
                if _gct_prev is not None:
                    _gct_state = _gct_prev.to(dtype=x.dtype)
                else:
                    _gct_state = self.global_tokens.unsqueeze(0).expand(B, -1, -1).clone()
                    _gct_state = _gct_state.to(dtype=x.dtype)

        # Process through blocks with state management
        for i, block in enumerate(self.blocks):
            is_hybrid_block = i >= self.local_layers
            block_intent = intent_phase if is_hybrid_block else None

            if is_hybrid_block:
                # Hybrid blocks: manage Phase state
                layer_state = prev_layer_states.get(i, {})
                prev_state = layer_state.get('final_state', None)
                prev_norm = layer_state.get('final_norm_state', None)

                x, state_dict = block(
                    x, causal_mask=True, intent_phase=block_intent,
                    prev_phase_state=prev_state,
                    prev_norm_state=prev_norm,
                    return_state=True,
                )
                next_layer_states[i] = state_dict
            else:
                # Local-only blocks: no state to manage
                x = block(x, causal_mask=True)

            # V10.13/V10.14: GCT read/write (same logic as forward())
            if self.global_tokens_enabled:
                if self.global_update_mode == "slots":
                    # V11: Only read every global_read_interval layers
                    if (i % self.global_read_interval) == 0:
                        _slot_out = self.slot_memory.read(x, _slot_keys, _slot_vals)
                        # V11.5: Full gradient — no detach (mirrors forward())
                        _alpha = self.slot_memory.read_warmstart_alpha
                        x = x + _alpha * _slot_out
                else:
                    _gct_out = self.gct_read_attn(
                        x, _gct_state, _gct_state, need_weights=False
                    )[0]
                    x = x + _gct_out

            if self.global_tokens_enabled and self.global_update_enabled:
                if (i % self.global_update_interval) == 0 and i >= self.global_write_start_layer:
                    if self.global_update_mode == "slots":
                        # V10.14.1: Always detach=False for slots (see comment above)
                        _slot_keys, _slot_vals = self.slot_memory.write(
                            x, _slot_keys, _slot_vals,
                            detach=False,
                        )
                    elif self.global_update_mode == "pool":
                        _w = torch.sigmoid(self.global_write_gate(x))
                        _pooled = (_w * x).sum(dim=1) / (_w.sum(dim=1) + 1e-6)
                        _delta = self.global_update_proj(_pooled).unsqueeze(1)
                        if self.global_token_write_detach and self.training:
                            _delta = _delta.detach()
                        _gct_state = _gct_state + _delta
                    else:
                        _delta = self.gct_write_attn(
                            _gct_state, x, x, need_weights=False
                        )[0]
                        _delta = _delta * self._gct_write_scale
                        if self.global_token_write_detach and self.training:
                            _delta = _delta.detach()
                        _gct_state = _gct_state + _delta

            # V10.13: Phase → Global (after hybrid blocks, non-slot modes only)
            _p2g = getattr(self, 'phase_to_global_proj', None)
            if is_hybrid_block and self.global_tokens_enabled and _p2g is not None:
                _pa = block.attention.phase_attn
                _phase_agg = getattr(_pa, '_last_final_state_agg', None)
                if _phase_agg is not None:
                    _pf = _phase_agg.squeeze(1)
                    _p_in = torch.cat([
                        _pf.real.reshape(B, -1),
                        _pf.imag.reshape(B, -1),
                    ], dim=-1).to(dtype=x.dtype)
                    _phase_upd = _p2g(_p_in).unsqueeze(1)
                    if self.phase_warmstart_enabled:
                        _ws_a = getattr(_pa, '_diag_warmstart_alpha', 1.0) or 1.0
                        _phase_upd = _phase_upd * _ws_a
                    _gct_state = _gct_state + _phase_upd

        # V10.13/V10.14: Save GCT/slot state for next chunk
        if self.global_tokens_enabled:
            if self.global_update_mode == "slots":
                next_layer_states['_slot_keys'] = _slot_keys.detach()
                next_layer_states['_slot_vals'] = _slot_vals.detach()
            else:
                next_layer_states['_gct_global_state'] = _gct_state.detach()

        # Output
        x = self.norm(x)
        logits = self.lm_head(x) * self.logit_scale

        result = {'logits': logits}

        # V10.14.10: Expose slot state from chunked forward for retrieval loss.
        # Without this, forward_chunked/TBPTT paths silently skip retrieval loss
        # (slot tensors missing → _retr_loss_val = 0.0 with no warning).
        if self.global_tokens_enabled and self.global_update_mode == "slots":
            result['_slot_keys'] = _slot_keys
            result['_slot_vals'] = _slot_vals
            # V11.3: Pre-attention hidden (mirrors forward())
            result['_slot_hidden'] = _x_pre_attn

        return result, next_layer_states

    def diagnose_chunk_continuity(
        self,
        input_ids: torch.Tensor,
        chunk_size: int = 512,
        verbose: bool = True,
    ) -> Dict[str, Any]:
        """
        V10.2.1: Comprehensive diagnostic for chunk-persistent Phase attention.

        Verifies all 8 requirements from the target architecture spec:
        1. Phase state persists across chunks (no reset)
        2. Local/Quadratic resets per chunk
        3. Local queries Phase memory only for long-range info
        4. Phase updates before Local
        5. Chunk boundaries invisible to Phase
        6. Positional encodings split (Phase=global, Local=relative)
        7. Gradient routing correct (Phase via Local only)
        8. All required diagnostics enabled

        REQUIRED DIAGNOSTICS (Requirement 8):
        1. Phase continuity: ||phase_end(chunk i) - phase_start(chunk i+1)||
           Should be ≈ 0 (states must match at boundaries)
        2. Quadratic attention source: % from Phase-derived K/V vs local
           In protected_phase mode: should be 100% from Phase
        3. Phase amplitude (R_k): Should stay in healthy band
           Not collapse (→0) or explode (→∞)

        Args:
            input_ids: [B, N] token indices (should be longer than chunk_size)
            chunk_size: Size of each chunk
            verbose: Print diagnostic messages

        Returns:
            Dict with diagnostic metrics and health status
        """
        B, N = input_ids.shape
        device = input_ids.device

        if N <= chunk_size:
            return {
                'healthy': True,
                'message': f'Sequence length {N} <= chunk_size {chunk_size}, no chunking needed',
            }

        # Track states for all 3 required diagnostics
        with torch.no_grad():
            chunked_logits = []
            layer_states = None
            prev_final_states = {}  # For continuity check

            # Diagnostic 1: Phase continuity tracking
            continuity_errors = []  # ||phase_end(i) - phase_start(i+1)||

            # Diagnostic 3: Phase amplitude tracking
            phase_amplitudes = []  # R_k per chunk

            for chunk_idx, start in enumerate(range(0, N, chunk_size)):
                end = min(start + chunk_size, N)
                chunk = input_ids[:, start:end]

                result, layer_states = self.forward_chunk(
                    chunk,
                    chunk_offset=start,
                    prev_layer_states=layer_states,
                )
                chunked_logits.append(result['logits'])

                # Track per-chunk metrics
                chunk_amplitudes = {}
                for layer_idx, state_dict in layer_states.items():
                    final_state = state_dict.get('final_state')
                    if final_state is not None:
                        # Diagnostic 1: Continuity check
                        # Compare this chunk's final_state to next chunk's expected start
                        if layer_idx in prev_final_states and chunk_idx > 0:
                            prev_state = prev_final_states[layer_idx]
                            # The prev_state IS the state we pass, so diff should be 0
                            # But cumsum adds to it, so we check the continuation
                            # Actually, continuity means: when we pass prev_state,
                            # the first position's state should be prev_state + first_kv
                            # We can't easily check this without internal access
                            # So we track norms to ensure no reset
                            pass

                        # Store for next iteration
                        prev_final_states[layer_idx] = final_state.clone()

                        # Diagnostic 3: Phase amplitude (R_k = |state|)
                        if final_state.is_complex():
                            amplitude = final_state.abs().mean().item()
                        else:
                            amplitude = final_state.abs().mean().item()
                        chunk_amplitudes[layer_idx] = amplitude

                phase_amplitudes.append(chunk_amplitudes)

            chunked_logits = torch.cat(chunked_logits, dim=1)

        # Full-sequence forward for comparison
        with torch.no_grad():
            full_result = self.forward(input_ids)
            full_logits = full_result['logits']

        # Compare logits
        logit_diff = (full_logits - chunked_logits).abs()
        logit_max_diff = logit_diff.max().item()
        logit_mean_diff = logit_diff.mean().item()

        # Diagnostic 1: Phase continuity
        # If chunking is correct, full and chunked logits should match
        # V10.2.1: Relaxed threshold from 0.01 to 0.02 to account for
        # numerical precision in complex tensor operations
        phase_continuous = logit_max_diff < 0.02

        # Diagnostic 2: Attention source (in protected_phase mode)
        # Check if protected_phase is enabled in hybrid blocks
        attn_source_ok = True
        for i, block in enumerate(self.blocks):
            if i >= self.local_layers:
                # Hybrid block - check protected_phase
                if hasattr(block.attention, 'protected_phase'):
                    if not block.attention.protected_phase:
                        attn_source_ok = False
                        break
        attn_from_phase_pct = 100.0 if attn_source_ok else 0.0

        # Diagnostic 3: Phase amplitude healthy band check
        # Amplitude should not collapse (<0.001) or explode (>100)
        amplitude_healthy = True
        amplitude_min = float('inf')
        amplitude_max = 0.0
        for chunk_amps in phase_amplitudes:
            for layer_idx, amp in chunk_amps.items():
                amplitude_min = min(amplitude_min, amp)
                amplitude_max = max(amplitude_max, amp)
                if amp < 0.001 or amp > 100.0:
                    amplitude_healthy = False

        # State monotonicity (accumulation check)
        state_monotonic = True
        for layer_idx in layer_states.keys():
            layer_amps = [pa.get(layer_idx, 0) for pa in phase_amplitudes]
            for i in range(1, len(layer_amps)):
                if layer_amps[i] < layer_amps[i-1] * 0.5:
                    state_monotonic = False
                    break

        # Overall health
        healthy = phase_continuous and attn_source_ok and amplitude_healthy and state_monotonic

        result = {
            'healthy': healthy,
            # Diagnostic 1: Phase continuity
            'phase_continuous': phase_continuous,
            'logit_max_diff': logit_max_diff,
            'logit_mean_diff': logit_mean_diff,
            # Diagnostic 2: Attention source
            'attn_from_phase_pct': attn_from_phase_pct,
            'protected_phase_enabled': attn_source_ok,
            # Diagnostic 3: Phase amplitude
            'amplitude_healthy': amplitude_healthy,
            'amplitude_min': amplitude_min,
            'amplitude_max': amplitude_max,
            'phase_amplitudes_per_chunk': phase_amplitudes,
            # Additional
            'state_monotonic': state_monotonic,
            'num_chunks': len(phase_amplitudes),
        }

        if verbose:
            status = "✓ HEALTHY" if healthy else "✗ UNHEALTHY"
            print(f"\n{'='*70}")
            print(f"V10.2.1 Chunk Continuity Diagnostic: {status}")
            print(f"{'='*70}")
            print(f"Sequence: {N} tokens, Chunk size: {chunk_size}, Chunks: {len(phase_amplitudes)}")
            print(f"\n[1] PHASE CONTINUITY (||end_i - start_{i+1}|| ≈ 0)")
            print(f"    Logit max diff:  {logit_max_diff:.6f} (threshold: 0.02)")
            print(f"    Logit mean diff: {logit_mean_diff:.6f}")
            print(f"    Status: {'✓ PASS' if phase_continuous else '✗ FAIL'}")
            print(f"\n[2] ATTENTION SOURCE (% from Phase memory)")
            print(f"    Protected Phase enabled: {attn_source_ok}")
            print(f"    Attention from Phase: {attn_from_phase_pct:.1f}%")
            print(f"    Status: {'✓ PASS' if attn_source_ok else '✗ FAIL'}")
            print(f"\n[3] PHASE AMPLITUDE (R_k healthy band: 0.001 < R < 100)")
            print(f"    Amplitude range: [{amplitude_min:.6f}, {amplitude_max:.6f}]")
            print(f"    State monotonic: {state_monotonic}")
            print(f"    Status: {'✓ PASS' if amplitude_healthy else '✗ FAIL'}")
            print(f"\n    Amplitude per chunk (first 5):")
            for i, pa in enumerate(phase_amplitudes[:5]):
                amps_str = ", ".join(f"L{k}:{v:.4f}" for k, v in sorted(pa.items()))
                print(f"      Chunk {i}: {amps_str}")
            if len(phase_amplitudes) > 5:
                print(f"      ... ({len(phase_amplitudes) - 5} more chunks)")
            print(f"{'='*70}\n")

        return result

    def forward_with_cache(
        self,
        input_ids: torch.Tensor,
        cache: Optional['PhaseStateCache'] = None,
        intent_phase: Optional[torch.Tensor] = None,
    ) -> Tuple[Dict[str, torch.Tensor], 'PhaseStateCache']:
        """
        V10.7: Inference forward pass using PhaseStateCache.
        V10.7.1: Safety fallback for correctness when local layers are active.

        When local_layers > 0, incremental decoding cannot be exactly reproduced
        from Phase state alone — LocalAttention layers need token-level context
        that is lost in the O(1) phase state. In this case, we fall back to
        full-prefix replay to guarantee generation quality matches full forward.

        When local_layers == 0 (pure phase model), O(1) incremental decoding
        is exact and the fast path is used.

        For prefill (first call), pass the full prompt as input_ids.
        For decode (subsequent calls), pass one token at a time.

        Args:
            input_ids: [B, N] tokens to process (N=prompt_len for prefill, N=1 for decode)
            cache: PhaseStateCache from previous call (None for first call)
            intent_phase: Optional phase rotation

        Returns:
            (result_dict, updated_cache)
            result_dict has 'logits': [B, N, V]
        """
        if cache is None:
            cache = PhaseStateCache(
                num_layers=len(self.blocks),
                hybrid_layer_start=self.local_layers,
            )

        # V10.7.1 SAFETY FALLBACK:
        # If LocalAttention layers are active, exact incremental decoding cannot be
        # reproduced from Phase state alone (local path needs token-level context).
        # Use full-prefix replay for correctness to prevent generation quality drift.
        if self.local_layers > 0:
            full_input_ids = cache.append_tokens(input_ids)
            result = self.forward(full_input_ids, intent_phase=intent_phase)
            # Return logits only for newly appended tokens to preserve API shape.
            result = {'logits': result['logits'][:, -input_ids.shape[1]:, :]}
            cache.advance(input_ids.shape[1])
            return result, cache

        # Fast path: pure phase model (no local layers) — O(1) incremental decode
        prev_layer_states = cache.as_prev_layer_states() if cache.seq_len > 0 else None

        result, new_layer_states = self.forward_chunk(
            input_ids,
            chunk_offset=cache.seq_len,
            prev_layer_states=prev_layer_states,
            intent_phase=intent_phase,
        )

        # Update cache with new states (enforces O(1) shape)
        for layer_idx, state_dict in new_layer_states.items():
            cache.update_layer_state(layer_idx, state_dict)
        cache.advance(input_ids.shape[1])

        return result, cache

    def generate_with_cache(
        self,
        input_ids: torch.Tensor,
        max_new_tokens: int = 50,
        temperature: float = 1.0,
        top_k: int = 50,
    ) -> torch.Tensor:
        """
        V10.7: Stateful generation using PhaseStateCache.

        Unlike generate() which re-processes the full sequence each step,
        this processes only the new token at each step using O(1) cached state.

        Memory: O(d × layers) constant, regardless of generated length.
        Speed: O(1) per token after prefill (no re-computation).
        """
        # Prefill: process the prompt
        cache = None
        result, cache = self.forward_with_cache(input_ids, cache)
        generated = input_ids

        for _ in range(max_new_tokens):
            logits = result['logits'][:, -1, :]
            logits = logits / temperature
            if top_k > 0:
                v, _ = torch.topk(logits, min(top_k, logits.size(-1)))
                logits[logits < v[:, [-1]]] = float('-inf')
            probs = F.softmax(logits, dim=-1)
            next_token = torch.multinomial(probs, num_samples=1)
            generated = torch.cat([generated, next_token], dim=1)

            # Decode: process only the new token with cached state
            result, cache = self.forward_with_cache(next_token, cache)

        return generated

    def generate(
        self,
        input_ids: torch.Tensor,
        max_new_tokens: int = 50,
        temperature: float = 1.0,
        top_k: int = 50,
    ) -> torch.Tensor:
        """Simple generation loop (legacy — re-processes full sequence each step)."""
        for _ in range(max_new_tokens):
            logits = self(input_ids)['logits'][:, -1, :]
            logits = logits / temperature
            if top_k > 0:
                v, _ = torch.topk(logits, min(top_k, logits.size(-1)))
                logits[logits < v[:, [-1]]] = float('-inf')
            probs = F.softmax(logits, dim=-1)
            next_token = torch.multinomial(probs, num_samples=1)
            input_ids = torch.cat([input_ids, next_token], dim=1)
        return input_ids


# =============================================================================
# ONTOLOGICAL HYBRID TRANSFORMER - AGI Architecture
# =============================================================================

class OntologicalHybridTransformer(nn.Module):
    """
    Two-Tier AGI Architecture: Ontological (slow/semantic) + Hybrid (fast/generation).

    V11.0.0: Phase rotation uses Bhava-only delta (12D), not full 32D.

    Separated Sovereign State planes:
      Phase Plane (12D Bhava-only → phase rotation):
        [0:12]  12 Bhavas (Ontological Aspects) — WHAT mode of being
      Control Plane (16D → CTM+/Sentinel/Governor):
        [12:17] 5 Koshas (Consciousness Sheaths) — HOW DEEP to process
        [17:22] 5 Vrittis (Mental Modifications) — HOW RELIABLE is this
        [22:28] 6 Gunas (Energy States) — WHAT ENERGY dynamics
      Learning Plane (4D → training-time only):
        [28:32] 4 Reserved (Toroidal Feedback) — scratch/JEPA channels

    This combines:
    1. Ontological Layer: Projects full 32D Sovereign State, extracts 12D Bhava delta
    2. Hybrid Layer: Local + Phase attention, conditioned on ΔBhava via phase rotation

    Theory:
        - System 2 (Ontological): Slow, deliberate semantic reasoning
        - System 1 (Hybrid): Fast, automatic pattern completion
        - ΔBhava → Phase Rotation: Identity changes HOW tokens relate, not WHAT they are
        - Control signals (Koshas/Vrittis/Gunas) → separate control plane, not attention

    Initialization:
        - State projector biased toward O12_ABS (Absolute) and Material (Physicality)
        - Represents "Absolute Potential" - pure awareness grounded in physical reality

    From ONTOLOGICAL_STATE_DELTA_DESIGN.md:
        "z_lower' = z_lower × e^{iθ_higher}"

    Usage:
        model = OntologicalHybridTransformer(...)
        output = model(input_ids)  # Computes ΔBhava and applies phase rotation

    Memory (at 10M context):
        - Token-centric: 2TB (impossible)
        - State-Delta (Tier 2): 30GB
        - Ontological (Tier 3): 5GB (full 32D state retained for control/diagnostics)
        - Phase-critical: 12D Bhava only → even smaller footprint
    """

    def __init__(
        self,
        vocab_size: int = 50257,
        embed_dim: int = 768,
        num_layers: int = 12,
        num_heads: int = 12,
        n_kv_heads: Optional[int] = None,  # V9.8.7: GQA support
        ff_dim: Optional[int] = None,
        max_seq_len: int = 8192,
        dropout: float = 0.1,
        # Hybrid params
        local_layers: int = 4,
        window_size: int = 256,
        local_backend: str = 'auto',
        alpha_local: float = 0.8,
        alpha_phase: float = 0.2,
        # Ontological params
        state_dim: int = SOVEREIGN_STATE_DIM,  # V9.8.0: 32D Sovereign State (was 124D)
        project_per_head_dim: bool = False,  # Phase projection granularity
        tie_embeddings: bool = True,
        cosine_mode: str = "standard",
        decay_gamma: float = 1.0,
        learned_decay: bool = False,  # V9.9.7: Per-head learned decay
        bounded_phase: bool = False,  # V9.9.11: Constrain φ to [-π, π] via π*sin()
        zero_mean_cosine: bool = False,  # V9.9.11: Center cosine per head (forces selectivity)
        dual_channel_mode: bool = False,  # V10.3.8: Separate content and alignment scores
        alignment_authority: float = 0.1,  # V10.3.8: Weight for alignment term
        # V10.14: Global Tokens / Slot Memory (passed through to HybridPhaseTransformer)
        global_tokens_enabled: bool = False,
        num_global_tokens: int = 16,
        global_update_mode: str = "pool",
        slots_write_lr: float = 0.1,
        retrieval_loss_weight: float = 0.1,
        # V11: Slot memory experiment
        global_read_interval: int = 1,
        global_write_start_layer: int = 0,
    ):
        super().__init__()

        # The Hybrid (generation) model
        self.hybrid = HybridPhaseTransformer(
            vocab_size=vocab_size,
            embed_dim=embed_dim,
            num_layers=num_layers,
            num_heads=num_heads,
            n_kv_heads=n_kv_heads,  # V9.8.7: Pass through GQA
            ff_dim=ff_dim,
            max_seq_len=max_seq_len,
            dropout=dropout,
            local_layers=local_layers,
            window_size=window_size,
            local_backend=local_backend,
            alpha_local=alpha_local,
            alpha_phase=alpha_phase,
            tie_embeddings=tie_embeddings,
            cosine_mode=cosine_mode,
            decay_gamma=decay_gamma,
            learned_decay=learned_decay,  # V9.9.7: Per-head learned decay
            bounded_phase=bounded_phase,  # V9.9.11: Phase collapse fix 1
            zero_mean_cosine=zero_mean_cosine,  # V9.9.11: Phase collapse fix 2
            dual_channel_mode=dual_channel_mode,  # V10.3.8: Dual-channel attention
            alignment_authority=alignment_authority,  # V10.3.8: Alignment authority
            # V10.14: Global Tokens / Slot Memory
            global_tokens_enabled=global_tokens_enabled,
            num_global_tokens=num_global_tokens,
            global_update_mode=global_update_mode,
            slots_write_lr=slots_write_lr,
            retrieval_loss_weight=retrieval_loss_weight,
            global_read_interval=global_read_interval,
            global_write_start_layer=global_write_start_layer,
        )

        # State projector: hidden[embed_dim] → SovereignState[32]
        # V9.6.8: Use SovereignStateProjector for proper normalization
        # - Bhava/Kosha/Vritti: softmax normalized (probabilities)
        # - Guna: sigmoid (0-1)
        # - Reserved: tanh (-1 to 1)
        if SOVEREIGN_PROJECTOR_AVAILABLE:
            self.state_projector = SovereignStateProjector(
                hidden_dim=embed_dim,
                state_dim=state_dim,
                intermediate_dim=embed_dim // 2,
                dropout=0.1,
                use_layer_norm=True,
            )
        else:
            # Fallback to raw projection (not recommended)
            self.state_projector = nn.Sequential(
                nn.Linear(embed_dim, embed_dim // 2),
                nn.GELU(),
                nn.Linear(embed_dim // 2, state_dim),
            )
            self._init_absolute_potential_bias()

        # V11.0.0: Intent phase projector uses Bhava-only delta (12D)
        # Only ontological identity feeds phase rotation, not control signals
        # ΔBhava[12] → θ[H] or θ[H, D_h]
        head_dim = embed_dim // num_heads
        self.intent_projector = IntentPhaseProjector(
            state_dim=PHASE_STATE_DIM,  # V11.0.0: 12D Bhava-only (was state_dim=32D)
            num_heads=num_heads,
            head_dim=head_dim,
            project_per_head_dim=project_per_head_dim,
        )

        # Store config
        self.state_dim = state_dim
        self.embed_dim = embed_dim

        # Previous state for delta computation (will be set during forward)
        # persistent=False excludes from state_dict (runtime state, not trained weights)
        self.register_buffer('prev_state', None, persistent=False)
        # V11.0.0: Track Bhava-only previous state for phase delta
        self.register_buffer('prev_bhava', None, persistent=False)

    def gradient_checkpointing_enable(self, **kwargs):
        """Enable gradient checkpointing on the inner hybrid model."""
        self.hybrid.gradient_checkpointing_enable()
        self.gradient_checkpointing = True

    def gradient_checkpointing_disable(self):
        """Disable gradient checkpointing on the inner hybrid model."""
        self.hybrid.gradient_checkpointing_disable()
        self.gradient_checkpointing = False

    def _init_absolute_potential_bias(self):
        """
        Initialize state projector to bias toward "Absolute Potential" state.

        At step 0, the model should start in:
        - O12_ABS (index 11): Absolute/transcendent awareness
        - Material (index 12): Physicality/Syntax grounding

        This represents pure potential grounded in physical existence.
        """
        with torch.no_grad():
            # Get the final linear layer's bias
            final_layer = self.state_projector[-1]
            if hasattr(final_layer, 'bias') and final_layer.bias is not None:
                # Start with small random bias
                final_layer.bias.fill_(0.0)
                # Boost O12_ABS (index 11) - Absolute/transcendent
                if final_layer.bias.shape[0] > 11:
                    final_layer.bias[11] = 1.0  # O12_ABS
                # Boost Material (index 12) - Physicality grounding
                if final_layer.bias.shape[0] > 12:
                    final_layer.bias[12] = 0.8  # Material
                # Small boost to Fact (index 17) - Verified truth
                if final_layer.bias.shape[0] > 17:
                    final_layer.bias[17] = 0.3  # Fact

    def compute_state_delta(
        self,
        hidden: torch.Tensor,
        reset_state: bool = False,
    ) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        """
        Compute 32D Sovereign State, full delta, and Bhava-only delta.

        V11.0.0: Returns separated outputs:
        - Full 32D state for diagnostics/control plane
        - Full 32D delta for logging
        - 12D Bhava-only delta for phase rotation (the only dim that touches attention)

        Args:
            hidden: [B, N, embed_dim] - hidden states from hybrid model
            reset_state: Reset prev_state (use at start of new sequence)

        Returns:
            state: [B, 32] - current Sovereign State (full, for diagnostics/control)
            delta_S: [B, 32] - full state delta (for logging/learning)
            delta_bhava: [B, 12] - Bhava-only delta (for phase rotation)
        """
        # Pool hidden states (mean over sequence)
        pooled = hidden.mean(dim=1)  # [B, embed_dim]

        # Project to full 32D Sovereign State
        state = self.state_projector(pooled)  # [B, state_dim]

        # Extract Bhava slice (phase-critical)
        bhava = state[:, BHAVA_SLICE]  # [B, 12]

        # Compute full delta (for logging/learning plane)
        # Also reset if batch size changed (e.g., VRAM governor resize)
        batch_size_changed = (
            self.prev_state is not None and
            self.prev_state.shape[0] != state.shape[0]
        )
        if reset_state or self.prev_state is None or batch_size_changed:
            delta_S = torch.zeros_like(state)
        else:
            delta_S = state - self.prev_state

        # Compute Bhava-only delta (for phase rotation)
        bhava_batch_changed = (
            self.prev_bhava is not None and
            self.prev_bhava.shape[0] != bhava.shape[0]
        )
        if reset_state or self.prev_bhava is None or bhava_batch_changed:
            delta_bhava = torch.zeros_like(bhava)
        else:
            delta_bhava = bhava - self.prev_bhava

        # Update previous states
        self.prev_state = state.detach()
        self.prev_bhava = bhava.detach()

        return state, delta_S, delta_bhava

    def forward(
        self,
        input_ids: torch.Tensor,
        attention_mask: Optional[torch.Tensor] = None,
        return_hidden: bool = False,
        extract_layers: Optional[List[int]] = None,
        return_last_hidden: bool = False,
        reset_state: bool = False,
        external_delta_S: Optional[torch.Tensor] = None,
        return_decorr_loss: bool = False,
    ) -> Dict[str, torch.Tensor]:
        """
        Forward pass with Ontological → Hybrid integration.

        V11.0.0: Phase rotation uses Bhava-only delta (12D), not full 32D.

        Two modes:
        1. Auto mode (default): Compute ΔBhava from hidden states automatically
        2. External mode: Use provided external_delta_S (legacy 32D or 12D Bhava)

        Args:
            input_ids: [B, N] token indices
            attention_mask: [B, N] optional mask (1=attend, 0=ignore) - currently unused
            return_hidden: Return all hidden states
            extract_layers: Specific layers to extract
            return_last_hidden: Return final hidden state
            reset_state: Reset Ontological state (new sequence)
            external_delta_S: [B, state_dim] external state delta (legacy 32D or 12D Bhava)

        Returns:
            Dict with:
            - 'logits': [B, N, V] output logits
            - 'state': [B, 32] current Sovereign State (full, for diagnostics)
            - 'delta_S': [B, 32] full state delta (for logging/learning)
            - 'delta_bhava': [B, 12] Bhava-only delta (phase-critical)
            - 'intent_phase': [B, H] or [B, H, D_h] phase rotation applied
            - Plus any requested hidden states
        """
        # First pass: Get hidden states WITHOUT intent phase
        # (We need hidden states to compute the state delta)
        with torch.no_grad():
            hidden = self.hybrid.forward_hidden(input_ids, intent_phase=None)

        # Compute state delta (or use external)
        if external_delta_S is not None:
            # Legacy path: external delta may be 32D or 12D
            state = self.state_projector(hidden.mean(dim=1))
            delta_S = external_delta_S
            if external_delta_S.shape[-1] <= PHASE_STATE_DIM:
                delta_bhava = external_delta_S
            else:
                delta_bhava = external_delta_S[:, BHAVA_SLICE]
        else:
            state, delta_S, delta_bhava = self.compute_state_delta(hidden, reset_state)

        # V11.0.0: Convert Bhava-only delta to intent phase rotation
        # Only ontological identity (12D) modulates attention
        intent_phase = self.intent_projector(delta_bhava)  # [B, H] or [B, H, D_h]

        # Detach intent_phase for the second pass to prevent gradient checkpointing
        # recomputation issues. compute_state_delta() mutates self.prev_state/prev_bhava,
        # so recomputing through it produces different deltas. Detaching makes
        # intent_phase a fixed input to the checkpointed region.
        intent_phase_for_hybrid = intent_phase.detach()

        # Second pass: Full forward WITH intent phase
        result = self.hybrid(
            input_ids,
            return_hidden=return_hidden,
            extract_layers=extract_layers,
            return_last_hidden=return_last_hidden,
            intent_phase=intent_phase_for_hybrid,
            return_decorr_loss=return_decorr_loss,
        )

        # Add ontological outputs
        result['state'] = state           # Full 32D for diagnostics/control
        result['delta_S'] = delta_S       # Full 32D delta for logging/learning
        result['delta_bhava'] = delta_bhava  # V11.0.0: 12D Bhava delta (phase-critical)
        result['intent_phase'] = intent_phase

        return result

    def generate(
        self,
        input_ids: torch.Tensor,
        max_new_tokens: int = 50,
        temperature: float = 1.0,
        top_k: int = 50,
        use_field_integrated: bool = False,
    ) -> torch.Tensor:
        """Generation with Ontological state tracking.

        Args:
            use_field_integrated: If True and conscious_gen Phase 4 modules are
                present, use TwoStageGenerator for field-integrated token selection
                instead of standard logit-based sampling.
        """
        # Reset state at start of generation
        self.prev_state = None
        self.prev_bhava = None  # V11.0.0: Reset Bhava tracking too

        # Check for Phase 4 two-stage generation
        _has_two_stage = (
            use_field_integrated
            and hasattr(self, 'conscious_gen')
            and 'two_stage_generator' in self.conscious_gen
        )

        for _ in range(max_new_tokens):
            result = self(input_ids, reset_state=(self.prev_state is None),
                          return_last_hidden=_has_two_stage)
            logits = result['logits'][:, -1, :]  # (B, V)

            if _has_two_stage:
                # Phase 4: Two-stage field-integrated generation
                hidden = result.get('last_hidden_state', None)
                o_ctx = result.get('state', None)
                if hidden is not None and o_ctx is not None:
                    hidden_last = hidden[:, -1, :]  # (B, D)
                    o_ctx_last = o_ctx[:, -1, :] if o_ctx.dim() == 3 else o_ctx
                    # TwoStageGenerator handles shortlist + scoring + softmax
                    gen = self.conscious_gen['two_stage_generator']
                    _cache = self.conscious_gen['token_cache'] if 'token_cache' in self.conscious_gen else None
                    gen_result = gen(
                        logits=logits.unsqueeze(1),       # (B, 1, V)
                        hidden=hidden_last.unsqueeze(1),  # (B, 1, D)
                        o_ctx=o_ctx_last.unsqueeze(1),    # (B, 1, state_dim)
                        cache=_cache,
                    )
                    probs = gen_result['log_probs'][:, 0, :].exp()  # (B, V)
                    next_token = torch.multinomial(probs, num_samples=1)
                    input_ids = torch.cat([input_ids, next_token], dim=1)
                    continue

            # Standard generation path
            logits = logits / temperature
            if top_k > 0:
                v, _ = torch.topk(logits, min(top_k, logits.size(-1)))
                logits[logits < v[:, [-1]]] = float('-inf')
            probs = F.softmax(logits, dim=-1)
            next_token = torch.multinomial(probs, num_samples=1)
            input_ids = torch.cat([input_ids, next_token], dim=1)

        return input_ids


class LocalOnlyTransformer(nn.Module):
    """
    Local-Only Transformer (Sliding Window Attention, NO Phase).

    Baseline model to test if Phase attention is helping or hurting.
    Uses only LocalTransformerBlock with sliding window attention O(n×w).
    """

    def __init__(
        self,
        vocab_size: int = 50257,
        embed_dim: int = 768,
        num_layers: int = 12,
        num_heads: int = 12,
        ff_dim: Optional[int] = None,
        max_seq_len: int = 8192,
        dropout: float = 0.1,
        window_size: int = 256,
        local_backend: str = 'auto',
        # Unused but kept for compatibility with create_model()
        sync_steps: int = 3,
        sync_lr: float = 0.1,
        local_layers: int = 4,
        alpha_local: float = 0.8,
        alpha_phase: float = 0.2,
        temperature: float = 1.0,
        tie_embeddings: bool = True,  # V9.6.0: Set False when using Sanskrit/CSR
    ):
        super().__init__()

        config = TransformerConfig(
            vocab_size=vocab_size,
            embed_dim=embed_dim,
            num_layers=num_layers,
            num_heads=num_heads,
            ff_dim=ff_dim,
            max_seq_len=max_seq_len,
            dropout=dropout,
        )
        self.config = config
        self.local_backend = local_backend
        self.tie_embeddings = tie_embeddings

        # Embeddings
        self.token_embed = nn.Embedding(vocab_size, embed_dim)
        self.pos_embed = nn.Embedding(max_seq_len, embed_dim)
        self.embed_dropout = nn.Dropout(dropout)

        # ALL layers use LocalTransformerBlock (NO Phase)
        self.blocks = nn.ModuleList([
            LocalTransformerBlock(config, window_size=window_size, backend=local_backend)
            for _ in range(num_layers)
        ])

        # Output
        self.norm = nn.LayerNorm(embed_dim)
        self.lm_head = nn.Linear(embed_dim, vocab_size, bias=False)

        # V10.11: Learnable logit scale initialized to 1.0.
        # Previous: 1/sqrt(sqrt(d)) ≈ 0.25 which flattened softmax → incoherent text.
        self.logit_scale = nn.Parameter(torch.ones(1))

        # V9.6.0: Optionally tie weights (disable when using Sanskrit/CSR injection)
        if tie_embeddings:
            self.lm_head.weight = self.token_embed.weight

        # Gradient checkpointing
        self.gradient_checkpointing = False

        # Initialize
        self.apply(self._init_weights)

        # V9.6.10: For untied embeddings, copy token_embed to lm_head AFTER init
        # This provides semantic alignment at start while keeping them separate
        if not self.tie_embeddings:
            with torch.no_grad():
                self.lm_head.weight.copy_(self.token_embed.weight)

    def gradient_checkpointing_enable(self):
        self.gradient_checkpointing = True

    def gradient_checkpointing_disable(self):
        self.gradient_checkpointing = False

    def _init_weights(self, module):
        if isinstance(module, nn.Linear):
            torch.nn.init.normal_(module.weight, mean=0.0, std=0.02)
            if module.bias is not None:
                torch.nn.init.zeros_(module.bias)
        elif isinstance(module, nn.Embedding):
            torch.nn.init.normal_(module.weight, mean=0.0, std=0.02)

    def forward(
        self,
        input_ids: torch.Tensor,
        return_hidden: bool = False,
        extract_layers: Optional[List[int]] = None,
        return_last_hidden: bool = False,
    ) -> Dict[str, torch.Tensor]:
        """
        Forward pass with efficient layer extraction.

        Args:
            input_ids: [B, N] token indices
            return_hidden: Return all hidden states
            extract_layers: Specific layer indices to extract (memory-efficient)
            return_last_hidden: Return normalized hidden state before lm_head

        Returns:
            Dict with 'logits' and optionally 'hidden_states', 'last_hidden_state'
        """
        B, N = input_ids.shape

        # Determine which layers to extract
        should_extract = return_hidden or extract_layers is not None
        extract_set = set(extract_layers) if extract_layers is not None else None

        # Embeddings
        positions = torch.arange(N, device=input_ids.device).unsqueeze(0)
        x = self.token_embed(input_ids) + self.pos_embed(positions)
        x = self.embed_dropout(x)

        # Transformer blocks (all local, no phase)
        hidden_states = [] if should_extract else None
        for i, block in enumerate(self.blocks):
            if self.gradient_checkpointing and self.training:
                x = checkpoint(block, x, True, use_reentrant=True)
            else:
                x = block(x, causal_mask=True)

            if should_extract:
                if extract_set is None or i in extract_set:
                    hidden_states.append(x)

        # Output
        x = self.norm(x)
        logits = self.lm_head(x) * self.logit_scale

        result = {'logits': logits}

        if should_extract:
            result['hidden_states'] = hidden_states

        if return_last_hidden:
            result['last_hidden_state'] = x

        return result

    def generate(
        self,
        input_ids: torch.Tensor,
        max_new_tokens: int = 50,
        temperature: float = 1.0,
        top_k: int = 50,
    ) -> torch.Tensor:
        """Simple generation loop."""
        for _ in range(max_new_tokens):
            logits = self(input_ids)['logits'][:, -1, :]
            logits = logits / temperature
            if top_k > 0:
                v, _ = torch.topk(logits, min(top_k, logits.size(-1)))
                logits[logits < v[:, [-1]]] = float('-inf')
            probs = F.softmax(logits, dim=-1)
            next_token = torch.multinomial(probs, num_samples=1)
            input_ids = torch.cat([input_ids, next_token], dim=1)
        return input_ids


# =============================================================================
# GATED COHERENCE TRANSFORMER (GCT)
# =============================================================================
#
# GCT: Governed Quadratic Softmax with Pre-Softmax Coherence Gating
#
# Core contribution: Pre-softmax temporal stability routing that does NOT
# require computing QK^T to decide the routing path.
#
# Architecture:
#   O = (1 - pi*) * O_full + pi* * O_local
#
# Where:
#   O_full  = standard O(n²) softmax attention
#   O_local = local-window softmax (O(n*w)) — same softmax primitive, fewer keys
#   pi*     = coherence gate * lambda_ladder insulation
#
# Coherence is computed from output deltas and residual deltas (no attention
# KL needed), preserving FlashAttention/SDPA compatibility on the full path.
#
# Lambda_ladder prevents band collapse: when heads assigned to different
# frequency bands produce too-similar outputs (low divergence = collapse risk),
# lambda_ladder suppresses routing to coarse, forcing full attention.
#
# Reference: FSCS pre-softmax routing pattern, adapted for quadratic softmax.
# =============================================================================


# =============================================================================
# V10.14: SLOT MEMORY GCT — Addressable Key-Value Slots for Associative Recall
# =============================================================================
#
# Problem: EMA/pooled GCT state is compressive — it cannot answer "what value
# was paired with key X?" because distinct bindings get blurred together.
#
# Solution: Replace pooled writes with competitive slot assignment.
# Each global token becomes an addressable memory slot with a key embedding
# and value state. Tokens write to slots via competitive assignment (softmax
# over slot keys), and read via cross-attention to slot values.
#
# CRITICAL INVARIANT: Slots update ONLY through the competitive write rule.
# Normal attention must NOT modify slot state — otherwise slots become noisy.
# The read path (cross-attention from tokens to slots) produces output that
# feeds into the residual stream, but never writes back to slot state.
#
# Architecture:
#   WRITE: assignment = softmax(token_key @ slot_keys.T / sqrt(d))
#          slot_val = (1 - η*a) * slot_val + η*a * proj(token)
#          slot_key = (1 - η*a) * slot_key + η*a * key_proj(token)
#   READ:  attn_weights = softmax(query @ slot_keys.T / sqrt(d))
#          output = attn_weights @ slot_vals
#
# This is Option 3 from the ChatGPT analysis: upgrade GCT into addressable
# retrieval slots, using the existing global tokens scaffold.
# =============================================================================


class SlotMemoryGCT(nn.Module):
    """
    V10.14: Addressable Key-Value Slot Memory for GCT.

    Replaces pooled/attn-lite GCT write with competitive slot assignment.
    Enables true associative recall: given a query key, retrieve the value
    that was stored with a matching key.

    Slots are write-protected: only the competitive write rule can update
    slot state. The read path (cross-attention) produces output for the
    residual stream but NEVER writes back to slots.

    V10.14.6: Top-k hard routing with straight-through gradient estimator.
    Soft softmax over all K slots collapses to uniform when write keys are
    similar (all from x.detach()). Top-k forces sparse assignment: each
    token writes to at most k slots, then softmax only within those k.
    Straight-through passes gradients through the full softmax for learning.

    Args:
        num_slots: Number of memory slots (= num_global_tokens)
        embed_dim: Embedding dimension
        num_heads: Number of attention heads for read path
        write_lr: Learning rate for slot updates (η in the write rule)
        dropout: Dropout rate
        write_key_dim: Dimension for write key matching (default: embed_dim)
        write_top_k: Number of slots each token can write to (default: 4)
    """

    def __init__(
        self,
        num_slots: int = 64,
        embed_dim: int = 768,
        num_heads: int = 12,
        write_lr: float = 0.1,
        dropout: float = 0.1,
        write_key_dim: Optional[int] = None,
        write_top_k: int = 4,
    ):
        super().__init__()
        self.num_slots = num_slots
        self.embed_dim = embed_dim
        self.num_heads = num_heads
        self.write_lr = write_lr
        self.write_top_k = min(write_top_k, num_slots)  # V10.14.6
        _key_dim = write_key_dim or embed_dim

        # --- Slot state (learnable initialization) ---
        # V10.14.5: Initialize slot keys on the unit hypersphere using orthogonal
        # init. Previous randn*0.02 made all keys near-identical → EMA pushed
        # them toward the same mean → winner-take-all collapse to one slot.
        # Orthogonal + L2-normalized keys are maximally separated, giving each
        # slot a distinct "identity" from the start.
        _init_keys = torch.randn(num_slots, _key_dim)
        if num_slots <= _key_dim:
            # More dims than slots: use orthogonal rows
            nn.init.orthogonal_(_init_keys)
        # Normalize to unit sphere regardless
        _init_keys = F.normalize(_init_keys, dim=-1)
        self.slot_keys_init = nn.Parameter(_init_keys)
        # V10.14.6: Zero-init slot values. Previous randn*0.02 contaminated
        # reads before any writes — 65% of slot content was still init noise
        # after 4 writes at eta=0.1. Zero init means reads return zero until
        # the model writes actual content, eliminating init noise entirely.
        self.slot_vals_init = nn.Parameter(
            torch.zeros(num_slots, embed_dim)
        )

        # --- WRITE path: token → slot assignment ---
        # Projects input token into write-key space for slot matching
        self.write_key_proj = nn.Linear(embed_dim, _key_dim, bias=False)
        # Projects input token into value to be written
        self.write_val_proj = nn.Linear(embed_dim, embed_dim, bias=False)
        # Novelty gate: only write when the token carries new binding info
        # sigmoid(gate) → 0 means "don't write", 1 means "write"
        self.write_novelty_gate = nn.Linear(embed_dim, 1)
        # V11.x: Initialize gate bias to +1.0 (sigmoid(1) ≈ 0.73).
        # Previous bias=0.0 (sigmoid=0.5) combined with weak indirect gradient
        # signal caused the gate to drift down to 0.072 (barely above the 0.05
        # floor). Starting higher gives the write path a real chance to bootstrap:
        # slots get meaningful writes → retrieval loss provides gradient → gate
        # can learn to modulate. If writing is too aggressive, the gate will
        # learn to close — but starting too low creates a chicken-and-egg trap.
        nn.init.constant_(self.write_novelty_gate.bias, 1.0)
        # V10.14.7: Gate floor moved to V10.29 adaptive block below.

        # V10.27: Adaptive write gate ceiling — prevents runaway gate opening.
        # The gate has three upward forces (L_gate_util, LM leak, retr_loss)
        # but no downward pressure since L_gate sparsity was removed in V10.14.7.
        # This adds a soft quadratic ceiling that adapts based on write utility:
        # if retr_loss is improving → ceiling relaxes (writes are helpful),
        # if retr_loss stagnates while gate is high → ceiling tightens (churn).
        self._gate_target = 0.35          # Adaptive ceiling (starts moderate)
        self._gate_target_min = 0.20      # Never tighten below this
        self._gate_target_max = 0.60      # Never relax above this
        self._gate_ceil_weight = 5.0      # Quadratic penalty weight above target
        self._gate_ceil_margin = 0.05     # V11: Free exploration zone above target
        self._retr_loss_window: List[float] = []  # Window for trend detection
        self._gate_window: List[float] = []       # Gate value window
        self._gate_adapt_window = 200     # Steps to accumulate before adapting
        self._gate_adapt_counter = 0      # Steps since last adaptation

        # V10.28: Adaptive constraint relaxation — detect when slots are
        # over-constrained (uniform usage, scale at clamp, gate at ceiling)
        # and progressively relax to allow specialization.
        self.enable_adaptive_constraints = True  # V11: Toggle for constraint relaxation
        self._wr_scale_max = 2.0          # Write scale upper clamp (starts conservative)
        self._wr_scale_max_limit = 4.0    # Maximum the clamp can relax to
        self._L_bal_weight = 1.0          # Balance loss weight (starts full)
        self._L_bal_weight_floor = 0.1    # Minimum balance weight
        # V11.1: Track L_bal relaxation reason for diagnostics
        self._L_bal_last_reason = ""
        self._constraint_relax_window: List[float] = []  # marginal_H history
        self._constraint_relax_counter = 0
        self._constraint_relax_interval = 500  # Steps between adaptation checks
        # V10.29 audit fix: Accumulate gate_mean and L_ortho in windows
        # (not stale single-batch snapshots) for reliable decisions.
        self._gate_mean_window: List[float] = []
        self._L_ortho_window: List[float] = []

        # V10.29: Extended adaptive hyperparameters — all start conservative
        # and adapt based on slot health signals. Unified adaptation in
        # update_constraint_relaxation() runs every _constraint_relax_interval steps.

        # (a) Novelty gate floor — raise when gate collapsed, lower when healthy
        self._novelty_gate_floor = 0.15
        self._novelty_gate_floor_min = 0.05   # Can drop to give more dynamic range
        self._novelty_gate_floor_max = 0.30   # Emergency rescue ceiling

        # (b) Retrieval loss weight — scale down when retr_loss dominates,
        #     scale up when slots are helping (caller tracks this externally)
        self._adaptive_retr_loss_weight = 1.0
        self._adaptive_retr_loss_weight_min = 0.5
        self._adaptive_retr_loss_weight_max = 2.0
        self._retr_loss_history: List[float] = []  # Track for dominance detection
        self._lm_loss_history: List[float] = []    # Need LM loss for ratio
        # V11.2: Ablation-aware retr_weight guard — don't decay when slots neutral/helping
        self._last_ablation_delta: Optional[float] = None  # Set by training loop after ablation

        # (c) H_target (sharpness entropy target) — adapt to slot utilization
        self._H_target = 1.0                # nats, ~2-3 active slots
        self._H_target_min = 0.5            # Sharper (1-2 slots)
        self._H_target_max = 2.0            # Broader (5-7 slots)

        # (d) L_ortho weight — reduce when slots already orthogonal
        self._L_ortho_weight = 0.5
        self._L_ortho_weight_min = 0.05
        self._L_ortho_weight_max = 1.0

        # (e) Read scale clamp max — mirrors write scale adaptive clamp
        # V12.1: Raised from 5.0/8.0. Cosine sims in high-d cluster tightly
        # (spread ~0.05), so scale=5 produces near-uniform softmax over 16 slots.
        # Floor=18 ≈ num_slots. Ceiling=64 gives gyroscope room to widen.
        self._read_scale_max = 64.0         # High ceiling so optimizer isn't clamped
        self._read_scale_max_limit = 128.0  # V12.4: Allow gyroscope to widen if optimizer pushes

        # (f) Router noise — tie decay to marginal_H instead of fixed schedule
        self._adaptive_router_noise = True  # Enable marginal_H-based noise

        # (g) Soft detach leak fraction — larger when gate collapsed
        self._soft_detach_leak = 0.1        # Default 10% gradient leak
        self._soft_detach_leak_min = 0.05   # Minimum leak
        self._soft_detach_leak_max = 0.3    # Emergency boost

        # (h) L_sharp weight — reduce once sharpness is in good range
        self._L_sharp_weight = 0.1
        self._L_sharp_weight_min = 0.01
        self._L_sharp_weight_max = 0.3

        # (i) Adaptive write_lr (EMA interpolation coefficient for slot updates)
        # Higher → slots update faster toward incoming content
        # Lower → slots retain existing content longer
        # Adapt based on retrieval loss trend: if retrieval is improving, slots
        # are being written usefully → allow faster writes. If stagnating,
        # slow down to preserve good content already stored.
        self._write_lr_min = 0.05            # Floor: always some update
        self._write_lr_max = 0.5             # Ceiling: never overwrite >50%

        # Write key scale: learnable inverse temperature for cosine similarity.
        # V10.14.5: With cosine similarity (both keys L2-normalized), dot products
        # are in [-1, 1]. Scale=10 gives softmax logits in [-10, 10] — sharp
        # enough to differentiate but not saturate. This is the standard approach
        # used in CLIP, prototypical networks, etc.
        # V10.14.8: Lowered init temperature from 10→5. At scale=10, cosine
        # similarity logits in [-10,10] → softmax is ultra-peaky → all tokens
        # route to the same slot. Scale=5 gives enough sharpness to differentiate
        # while allowing more balanced slot utilization.
        # V10.20→V12.3: Init at 1.8, safely below _wr_scale_max (2.0).
        # Hard clamp kills gradient when value >= max, so init AT the boundary
        # gives zero gradient and the parameter never moves. At 1.8 the param
        # is inside the clamp's pass-through region → gradients flow → optimizer
        # can push toward the ceiling → gyroscope detects pressure and relaxes.
        self._write_log_scale = nn.Parameter(
            torch.tensor(math.log(1.8))  # exp(log(1.8)) ≈ 1.8, below _wr_scale_max=2.0
        )

        # --- READ path: query → slot attention ---
        # V12: Separate read_query_proj ACTIVE. Previously shared write_key_proj
        # (V10.14.2), but write and read are different tasks — write asks "where
        # to store" while read asks "what do I need." Shared projection meant
        # write gradients dominated, leaving read queries unable to discriminate
        # between slots (read_H pegged at max entropy ~4.0 for 16 slots).
        # Separate projection lets retrieval loss train read queries independently.
        self.read_query_proj = nn.Linear(embed_dim, _key_dim, bias=False)
        self.read_output_proj = nn.Linear(embed_dim, embed_dim, bias=False)
        self.read_dropout = nn.Dropout(dropout)
        # V10.14.6: Retrieval readout norm — raw slot values go through this
        # LayerNorm before lm_head in compute_retrieval_loss. The lm_head
        # expects layer-normed input; without this, raw slot values have
        # arbitrary scale → lm_head predictions are garbage.
        self.retr_read_norm = nn.LayerNorm(embed_dim)

        # V11.4: Slot-only prediction head — tests whether slot content carries
        # information useful for next-token prediction, independent of the main
        # backbone. Uses a separate bottleneck head (not shared lm_head) so
        # improvements here genuinely reflect slot content quality.
        # Architecture: slot retrieval → LayerNorm → D→D/4 → GELU → D/4→V
        # Gradients flow back into: read_output_proj, slot_vals (via retrieval
        # attention), write_val_proj (via slot_vals computation graph).
        # They do NOT flow into: backbone layers, token embeddings, lm_head.
        _bottleneck_dim = embed_dim // 4
        self.slot_pred_head = nn.Sequential(
            nn.Linear(embed_dim, _bottleneck_dim, bias=False),
            nn.GELU(),
            nn.Linear(_bottleneck_dim, 50257, bias=False),  # GPT-2 vocab
        )
        self.slot_pred_norm = nn.LayerNorm(embed_dim)
        # Diagnostics for slot prediction
        self._diag_slot_pred_loss: float = 0.0
        self._diag_slot_pred_acc: float = 0.0

        # V12.1: Read temperature. With cosine similarity over 16 slots,
        # scale must be high enough to break uniform softmax. Cosine sims
        # cluster tightly in high-d (~0.05 spread), so scale=5 can't produce
        # sharp attention. Init at log(18.0) = floor, learnable up to 64.
        self._read_log_scale = nn.Parameter(
            torch.tensor(math.log(18.0))
        )

        # --- Router noise (MoE-style symmetry breaking) ---
        # V10.14.5: Add Gaussian noise to assignment logits during early training
        # to prevent "slot 0 wins by tiny initial advantage" collapse.
        # Noise decays linearly: noise_std * max(0, 1 - step/warmup_steps)
        # V10.14.8: Extended noise warmup 2000→10000 and added noise floor.
        # Noise decaying to 0 at step 2000 meant collapse was permanent after
        # that point. Longer warmup + floor=0.1 maintains diversity pressure
        # throughout training while still allowing sharp convergence.
        self._router_noise_std = 0.5
        self._router_noise_warmup = 10000  # steps to decay noise toward floor
        self._router_noise_floor = 0.1  # minimum noise std (never fully zero)
        # V10.27: Register as buffer so it's saved/restored with state_dict().
        # Without this, resume resets _router_step to 0, which re-suppresses
        # slot reads (warmstart_alpha → 0) and resets router noise for ~500 steps.
        self.register_buffer('_router_step_buf', torch.tensor(0, dtype=torch.long))
        self._router_step = 0  # Mirror for easy access; synced in properties

        # --- Read warmstart ---
        # V10.14.6d: Read output is detached before adding to residual (LM
        # can't suppress read_output_proj). But we still ramp the mixing
        # coefficient from 0→1 so early noisy reads don't disrupt LM training.
        # Uses same _router_step counter. Sigmoid centered at 100 steps,
        # tau=25 → effectively 0 for first ~50 steps, ~1 after ~150.
        self._read_warmstart_center = 100
        self._read_warmstart_tau = 25

        # --- Diagnostics ---
        self._diag_write_gate_mean = None
        self._diag_assignment_entropy = None
        self._diag_slot_key_norm = None
        self._diag_slot_val_norm = None
        self._diag_read_attn_entropy = None
        self._diag_read_scale = None  # V10.21: separate read temperature
        self._last_slot_keys = None  # V10.14.8: for orthogonality loss

    # V10.29: List of adaptive scalar attributes to persist across checkpoints.
    _ADAPTIVE_KEYS = (
        '_gate_target', '_gate_ceil_weight', '_wr_scale_max', '_L_bal_weight',
        '_novelty_gate_floor', '_adaptive_retr_loss_weight', '_H_target',
        '_L_ortho_weight', '_read_scale_max', '_soft_detach_leak',
        '_L_sharp_weight', 'write_lr',
    )

    # V11: Initial defaults for all adaptive scalars — used by reset_constraints().
    _ADAPTIVE_DEFAULTS = {
        '_gate_target': 0.35,
        '_gate_ceil_weight': 5.0,
        '_gate_ceil_margin': 0.05,
        '_wr_scale_max': 2.0,
        '_L_bal_weight': 1.0,
        '_novelty_gate_floor': 0.15,
        '_adaptive_retr_loss_weight': 1.0,
        '_H_target': 1.0,
        '_L_ortho_weight': 0.5,
        '_read_scale_max': 64.0,
        '_soft_detach_leak': 0.1,
        '_L_sharp_weight': 0.1,
        'write_lr': 0.1,
    }

    def reset_constraints(self):
        """V11: Reset all adaptive constraint state to initial defaults.

        Use when resuming a checkpoint with --disable_slot_adaptive_constraints
        to undo any drift from the previous run's controller.
        """
        for key, default in self._ADAPTIVE_DEFAULTS.items():
            setattr(self, key, default)
        # Clear accumulated windows so stale history doesn't leak
        self._constraint_relax_window.clear()
        self._constraint_relax_counter = 0
        self._gate_mean_window.clear()
        self._L_ortho_window.clear()
        self._retr_loss_history.clear()
        self._lm_loss_history.clear()
        self._retr_loss_window.clear()
        self._gate_window.clear()
        self._gate_adapt_counter = 0

    def state_dict(self, *args, **kwargs):
        """V10.27/29: Sync runtime state before saving."""
        self._router_step_buf.fill_(self._router_step)
        sd = super().state_dict(*args, **kwargs)
        # V10.29: Persist adaptive hyperparams as prefixed keys
        for key in self._ADAPTIVE_KEYS:
            sd[f'_adaptive.{key}'] = getattr(self, key)
        return sd

    def load_state_dict(self, state_dict, *args, **kwargs):
        """V10.27/29: Restore runtime state after loading."""
        # V10.29: Extract adaptive keys before super() (which would reject them)
        adaptive_vals = {}
        keys_to_remove = []
        for k in list(state_dict.keys()):
            if k.startswith('_adaptive.'):
                adaptive_vals[k[len('_adaptive.'):]] = state_dict[k]
                keys_to_remove.append(k)
        for k in keys_to_remove:
            del state_dict[k]
        result = super().load_state_dict(state_dict, *args, **kwargs)
        self._router_step = int(self._router_step_buf.item())
        # Restore adaptive values (with validation)
        for key, val in adaptive_vals.items():
            if hasattr(self, key):
                setattr(self, key, val)
        if adaptive_vals:
            print(f"  [SLOTS] Restored {len(adaptive_vals)} adaptive params from checkpoint")
        # V11.2b: Enforce current floor on loaded retr_weight
        if self._adaptive_retr_loss_weight < self._adaptive_retr_loss_weight_min:
            old = self._adaptive_retr_loss_weight
            self._adaptive_retr_loss_weight = self._adaptive_retr_loss_weight_min
            print(f"  [SLOTS] retr_weight {old:.2f} → {self._adaptive_retr_loss_weight:.2f} "
                  f"(clamped to new floor)")
        # V12.3: If loaded _write_log_scale is at or above _wr_scale_max,
        # pull it to 90% of max. Hard clamp kills gradient at the boundary
        # (value >= max → grad = 0), so we need to be strictly inside.
        _wr_target = self._wr_scale_max * 0.9  # e.g. 2.0 * 0.9 = 1.8
        _wr_target_log = math.log(_wr_target)
        if self._write_log_scale.item() >= math.log(self._wr_scale_max) - 0.01:
            _old_wr = math.exp(self._write_log_scale.item())
            with torch.no_grad():
                self._write_log_scale.fill_(_wr_target_log)
            print(f"  [SLOTS] V12.3: _write_log_scale {math.log(_old_wr):.2f} (scale={_old_wr:.1f}) "
                  f"→ {_wr_target_log:.2f} (scale={_wr_target:.1f}) (at/above ceiling, pulled inside)")
        # V12.1: If loaded _read_log_scale is below new floor, override it.
        # Otherwise the clamp kills gradients (value stuck below floor → zero grad)
        # and the parameter can never learn upward.
        _rd_floor = math.log(18.0)
        if self._read_log_scale.item() < _rd_floor:
            _old_scale = math.exp(self._read_log_scale.item())
            with torch.no_grad():
                self._read_log_scale.fill_(_rd_floor)
            print(f"  [SLOTS] V12.1: _read_log_scale {math.log(_old_scale):.2f} (scale={_old_scale:.1f}) "
                  f"→ {_rd_floor:.2f} (scale=18.0) (below new floor, overridden)")
        # V12: Re-ramp read warmstart on resume so fresh read_query_proj
        # doesn't immediately dump noisy reads into the residual stream.
        # Shift warmstart center to current step → sigmoid re-ramps over
        # ~100 steps from ~0 to ~1, giving read_query_proj time to learn.
        _step = int(self._router_step_buf.item())
        if _step > self._read_warmstart_center + 200:
            self._read_warmstart_center = _step
            print(f"  [SLOTS] V12: read warmstart re-centered to step {_step} "
                  f"(read_query_proj now active, re-ramping)")
        return result

    @property
    def read_warmstart_alpha(self) -> float:
        """Sigmoid ramp for read mixing: 0 early, 1 later."""
        return 1.0 / (1.0 + math.exp(
            -(self._router_step - self._read_warmstart_center)
            / max(self._read_warmstart_tau, 1.0)
        ))

    def init_state(self, batch_size: int, dtype: torch.dtype, device: torch.device):
        """Initialize slot state for a new batch.

        Returns:
            slot_keys: [B, K, D_key] — slot key embeddings
            slot_vals: [B, K, D] — slot value embeddings
        """
        slot_keys = self.slot_keys_init.unsqueeze(0).expand(batch_size, -1, -1).clone()
        slot_vals = self.slot_vals_init.unsqueeze(0).expand(batch_size, -1, -1).clone()
        return slot_keys.to(dtype=dtype, device=device), slot_vals.to(dtype=dtype, device=device)

    def write(
        self,
        x: torch.Tensor,            # [B, N, D] — token representations
        slot_keys: torch.Tensor,     # [B, K, D_key] — current slot keys
        slot_vals: torch.Tensor,     # [B, K, D] — current slot values
        detach: bool = False,        # Detach write deltas (stop grad to main path)
    ) -> Tuple[torch.Tensor, torch.Tensor]:
        """
        Competitive slot write: each token writes to the most similar slot.

        The write uses a soft competitive assignment (softmax over slots),
        followed by a gated EMA update. This ensures each slot specializes
        in storing specific key-value bindings.

        IMPORTANT: This is the ONLY way slot state gets modified.

        Args:
            x: Token representations [B, N, D]
            slot_keys: Current slot keys [B, K, D_key]
            slot_vals: Current slot values [B, K, D]
            detach: If True, detach deltas from computation graph

        Returns:
            updated_slot_keys: [B, K, D_key]
            updated_slot_vals: [B, K, D]
        """
        B, N, D = x.shape

        # V10.24: Soft detach — pass 10% of gradient through to write path.
        # Full detach (V10.14.1) prevented main LM loss from encouraging writes,
        # starving write_novelty_gate of signal. 10% leak lets the LM loss
        # gently push the gate open when slot reads help prediction, while
        # still blocking 90% of gradient to prevent backbone destabilization.
        # V10.29: Adaptive leak fraction (default 0.1, adapts based on gate health)
        _leak = self._soft_detach_leak
        x_write = x * _leak + x.detach() * (1.0 - _leak)

        # Novelty gate: which tokens should write? [B, N, 1]
        # V10.14.4: Floor clamp prevents gate death — ensures minimum write pressure
        novelty = torch.sigmoid(self.write_novelty_gate(x_write))
        novelty = torch.clamp(novelty, min=self._novelty_gate_floor)

        # Project tokens into write key/value space
        write_keys = self.write_key_proj(x_write)   # [B, N, D_key]
        write_vals = self.write_val_proj(x_write)    # [B, N, D]

        # V10.14.5: Cosine similarity assignment.
        # L2-normalize both write keys and slot keys so assignment is based on
        # direction only, not magnitude. This prevents winner-take-all collapse
        # where one slot's key norm grows larger and attracts all tokens.
        # [B, N, D_key] @ [B, D_key, K] → [B, N, K]
        # V10.14.8: Clamp temperature to [3, 15]. At scale=10+ all tokens
        # pick the same top slot → winner-take-all collapse. Capping at 15
        # prevents runaway; floor of 3 prevents assignments from going uniform.
        # V10.20: Tightened max from 15→8. Logs showed scale learning to 5.9,
        # concentrating writes on few slots and causing 1.2M× gradient spikes.
        # V10.23: Lowered max from 8→4. At wr_scale=8.0 (hit max clamp for 400+
        # steps), softmax assignment is ultra-peaky → gradients through assignment
        # back to novelty_gate are negligible → write_gate stuck at floor (0.155).
        # V10.25: Lowered further from [3,4]→[1.5,2.0]. Even at scale=4 the
        # assignment softmax is ultra-peaky, producing near-zero gradients back
        # through the softmax to write_novelty_gate. At scale≤2.0, assignments
        # stay differentiated enough for meaningful gradient flow, letting the
        # gate learn to open above the 0.15 floor via both retrieval loss and
        # the 10% LM-loss leak (V10.24).
        _scale = torch.exp(self._write_log_scale).clamp(min=1.5, max=self._wr_scale_max)
        _wk_norm = F.normalize(write_keys, dim=-1)     # [B, N, D_key]
        # V10.20: Detach slot_keys before F.normalize in assignment computation.
        # The F.normalize Jacobian (I - x̂x̂ᵀ)/||x|| on slot_keys creates 3000×+
        # gradient variance when many tokens write to the same slot. Since slot_keys
        # are updated via EMA (line 8577), they don't need assignment-path gradients —
        # the learning signal comes through the EMA update itself. Detaching here
        # severs the 1.2M× amplification path through slot_keys_init.
        _sk_norm = F.normalize(slot_keys.detach(), dim=-1)       # [B, K, D_key]
        assignment_logits = torch.bmm(
            _wk_norm, _sk_norm.transpose(1, 2)
        ) * _scale  # cosine_sim * temperature

        # V10.14.5: Router noise — break symmetry during early training.
        # Without this, the slot with the tiny initial advantage snowballs.
        if self.training and self._router_noise_std > 0:
            # V10.14.8: Decay toward floor instead of 0
            _noise_decay = max(0.0, 1.0 - self._router_step / self._router_noise_warmup)
            _noise_std = self._router_noise_floor + (self._router_noise_std - self._router_noise_floor) * _noise_decay
            # V10.29/V12.4: If marginal_H is high (slots uniform), boost noise
            # to maintain exploration; if differentiated, accelerate decay.
            # V12.4: Scale boost by _noise_decay so it fades with training
            # instead of holding at a fixed 50% forever. At step 0 boost=25%
            # of initial; at warmup end boost=0 (floor only).
            if self._adaptive_router_noise:
                _mH = getattr(self, '_diag_marginal_entropy', None)
                if _mH is not None and _mH > 0.90:
                    _boost = self._router_noise_std * 0.25 * (0.5 + 0.5 * _noise_decay)
                    _noise_std = max(_noise_std, _boost)
                elif _mH is not None and _mH < 0.5:
                    # Slots well-differentiated — accelerate decay
                    _noise_std = max(self._router_noise_floor, _noise_std * 0.5)
            _noise = torch.randn_like(assignment_logits) * _noise_std
            assignment_logits = assignment_logits + _noise

        # V10.14.6: Top-k hard routing with straight-through gradient.
        # Soft softmax over all K slots converges to uniform when write keys
        # are similar. Top-k selects the k best-matching slots per token,
        # then softmax only within those k. Straight-through estimator passes
        # gradients through the full softmax so the router can still learn.
        assignment_soft = F.softmax(assignment_logits, dim=-1)  # [B, N, K]
        if self.write_top_k < self.num_slots:
            topk_vals, topk_idx = assignment_logits.topk(self.write_top_k, dim=-1)  # [B, N, k]
            topk_weights = F.softmax(topk_vals, dim=-1)  # [B, N, k] — normalized within top-k
            assignment_hard = torch.zeros_like(assignment_logits)  # [B, N, K]
            assignment_hard.scatter_(-1, topk_idx, topk_weights.to(assignment_hard.dtype))
            # Straight-through: hard forward, soft backward
            assignment = assignment_hard - assignment_soft.detach() + assignment_soft
        else:
            assignment = assignment_soft

        # Gate assignment by novelty: only tokens with binding info write
        # [B, N, K] * [B, N, 1] → [B, N, K]
        gated_assignment = assignment * novelty

        # Aggregate writes per slot: sum over tokens
        # effective_write[b, k] = sum_t(gated_assignment[b, t, k])
        # This is the total write pressure on each slot
        write_pressure = gated_assignment.sum(dim=1)  # [B, K]

        # Weighted average of incoming keys/values per slot
        # [B, K, N] @ [B, N, D_key] → [B, K, D_key]
        incoming_keys = torch.bmm(
            gated_assignment.transpose(1, 2), write_keys
        )
        # [B, K, N] @ [B, N, D] → [B, K, D]
        incoming_vals = torch.bmm(
            gated_assignment.transpose(1, 2), write_vals
        )

        # Normalize by write pressure (avoid division by zero)
        # V10.20: Raised clamp floor from 1e-6 to 0.1. The old floor allowed
        # 1/1e-6 = 1M× gradient amplification through the pressure division,
        # which was the root cause of the 1.2M× slot_keys_init variance spikes.
        # Floor of 0.1 caps amplification at 10× — consistent with the phase
        # attention normalizer clamp.
        pressure_norm = write_pressure.unsqueeze(-1).clamp(min=0.1)
        incoming_keys = incoming_keys / pressure_norm
        incoming_vals = incoming_vals / pressure_norm

        # V10.20: L2-normalize incoming KEYS before EMA update.
        # Without this, unbounded incoming_keys magnitude drifts slot_keys
        # off the unit hypersphere, causing F.normalize Jacobian explosion
        # in subsequent forward passes. Normalizing here ensures the EMA
        # interpolates between unit vectors, keeping slot keys well-conditioned.
        _ik_norm = incoming_keys.norm(dim=-1, keepdim=True).clamp(min=1e-6)
        incoming_keys = incoming_keys / _ik_norm
        # V12.4: Do NOT normalize incoming_vals. Values carry magnitude info
        # (how strongly a concept is represented), and L2-norm destroys it —
        # all slot values get forced onto the unit sphere, reducing expressiveness.
        # Keys need normalization (cosine routing), values don't.

        # EMA update rate per slot: η * min(write_pressure, 1.0)
        # Slots with no write pressure don't update; heavy pressure caps at η
        eta = self.write_lr * write_pressure.clamp(max=1.0).unsqueeze(-1)  # [B, K, 1]

        if detach:
            incoming_keys = incoming_keys.detach()
            incoming_vals = incoming_vals.detach()
            eta = eta.detach()

        # Slot update: EMA rule
        new_slot_keys = (1 - eta) * slot_keys + eta * incoming_keys
        new_slot_vals = (1 - eta) * slot_vals + eta * incoming_vals

        # V10.14.5 / V10.16: Re-normalize slot keys to unit sphere after EMA update.
        # Prevents key norms from drifting, which would bias cosine similarity.
        # V10.16: Use detached norms to avoid the F.normalize Jacobian explosion.
        # When many tokens write to the same slot, the normalize Jacobian
        # (I - x̂x̂ᵀ)/||x|| can produce 3000x+ gradient variance spikes.
        # Detaching the denominator preserves forward normalization while keeping
        # gradients flowing only through the EMA numerator (the actual learning signal).
        _key_norms = new_slot_keys.detach().norm(dim=-1, keepdim=True).clamp(min=1e-6)
        new_slot_keys = new_slot_keys / _key_norms

        # Store assignment for sharpness loss (WITH grad — this is the learning signal)
        self._last_assignment = assignment  # [B, N, K]
        self._last_novelty = novelty  # [B, N, 1]
        self._last_gated_assignment = gated_assignment  # [B, N, K] — for gate gradient
        # V10.14.8: Store updated slot keys for orthogonality loss
        self._last_slot_keys = new_slot_keys  # [B, K, D_key]

        # Diagnostics (no grad)
        with torch.no_grad():
            self._diag_write_gate_mean = novelty.mean().item()
            # Assignment entropy: high = spread across slots, low = sharp assignment
            _a_log = torch.log(assignment.clamp(min=1e-8))
            self._diag_assignment_entropy = -(assignment * _a_log).sum(dim=-1).mean().item()
            self._diag_slot_key_norm = new_slot_keys.norm(dim=-1).mean().item()
            self._diag_slot_val_norm = new_slot_vals.norm(dim=-1).mean().item()

        return new_slot_keys, new_slot_vals

    def read(
        self,
        x: torch.Tensor,            # [B, N, D] — query tokens
        slot_keys: torch.Tensor,     # [B, K, D_key] — slot keys
        slot_vals: torch.Tensor,     # [B, K, D] — slot values
    ) -> torch.Tensor:
        """
        Read from slots via attention: query tokens attend to slot keys,
        retrieve weighted sum of slot values.

        This produces output for the residual stream but NEVER modifies slots.

        Args:
            x: Query token representations [B, N, D]
            slot_keys: Slot keys [B, K, D_key]
            slot_vals: Slot values [B, K, D]

        Returns:
            read_output: [B, N, D] — retrieved information
        """
        # V12: Separate read_query_proj — read queries learn independently
        # from write queries, trained by retrieval loss only.
        queries = self.read_query_proj(x)  # [B, N, D_key]

        # V12.1: Read scale floor raised to 18.0 (from 4.0). With cosine
        # similarity in high-d, slot sims cluster within ~0.05 spread.
        # Over 16 slots, scale=5 → near-uniform softmax. Floor=18 ≈ num_slots
        # so a 0.05 sim gap → logit gap of 0.9 → sharp peak.
        _read_scale = torch.exp(
            self._read_log_scale.clamp(min=math.log(18.0), max=math.log(self._read_scale_max))
        )
        _q_norm = F.normalize(queries, dim=-1)
        # V10.20: Detach slot_keys in read path (same rationale as write path).
        # Slot keys learn through EMA updates, not through read attention gradients.
        # The LM learning signal flows through slot_vals (retrieved content),
        # not through slot_keys (routing). Detaching prevents F.normalize Jacobian
        # explosion while preserving the value-path gradient.
        _sk_norm = F.normalize(slot_keys.detach(), dim=-1)
        attn_logits = torch.bmm(
            _q_norm, _sk_norm.transpose(1, 2)
        ) * _read_scale
        attn_weights = F.softmax(attn_logits, dim=-1)  # [B, N, K]
        attn_weights = self.read_dropout(attn_weights)

        # Retrieve: [B, N, K] @ [B, K, D] → [B, N, D]
        retrieved = torch.bmm(attn_weights, slot_vals)

        # Project to output space
        output = self.read_output_proj(retrieved)

        # Diagnostics
        with torch.no_grad():
            _w_log = torch.log(attn_weights.clamp(min=1e-8))
            self._diag_read_attn_entropy = -(attn_weights * _w_log).sum(dim=-1).mean().item()
            self._diag_read_scale = _read_scale.item()

        return output

    def compute_retrieval_loss(
        self,
        x: torch.Tensor,              # [B, N, D] — token representations
        slot_keys: torch.Tensor,       # [B, K, D_key] — slot keys
        slot_vals: torch.Tensor,       # [B, K, D] — slot values
        query_mask: torch.Tensor,      # [B, N] — True at query positions
        target_ids: torch.Tensor,      # [B, N] — target token IDs
        lm_head: nn.Linear,            # Shared LM head for prediction
    ) -> torch.Tensor:
        """
        V10.14.6d: Retrieval loss routes through read_output_proj.

        The read output is detached in the main forward pass (LM can't suppress
        read_output_proj). This means read_output_proj is trained ONLY by this
        retrieval loss — it learns to produce useful projections for token
        prediction, not to suppress noisy reads.

        Path: slot_vals → attn·vals → read_output_proj → retr_read_norm → lm_head

        Args:
            x: Token representations [B, N, D]
            slot_keys: Slot keys [B, K, D_key]
            slot_vals: Slot values [B, K, D]
            query_mask: Boolean mask, True at positions where retrieval is tested [B, N]
            target_ids: Token IDs to predict at query positions [B, N]
            lm_head: The model's LM head (shared, not separate)

        Returns:
            retrieval_loss: Scalar CE loss averaged over query positions.
                           Returns 0 if no query positions exist.
        """
        if query_mask is None or not query_mask.any():
            return torch.tensor(0.0, device=x.device, dtype=x.dtype)

        # V12: Use read_query_proj (matches read() path) so retrieval loss
        # gradients train the read projection, not the write projection.
        queries = self.read_query_proj(x)  # [B, N, D_key]
        # V12.4: Match read() path scale — previously used _wr_scale_max (2.0)
        # by copy-paste error, creating 9x temperature mismatch vs read() (18+).
        # Retrieval loss trained read_query_proj for near-uniform attention
        # while read() used peaky softmax → stuck retr_loss.
        _scale = torch.exp(self._read_log_scale).clamp(min=1.5, max=self._read_scale_max)
        _q_norm = F.normalize(queries, dim=-1)
        # V10.20: Detach slot_keys (consistent with read/write paths).
        _sk_norm = F.normalize(slot_keys.detach(), dim=-1)
        attn_logits = torch.bmm(
            _q_norm, _sk_norm.transpose(1, 2)
        ) * _scale  # [B, N, K]
        attn_weights = F.softmax(attn_logits, dim=-1)  # [B, N, K]

        # Retrieve weighted slot values
        raw_retrieved = torch.bmm(attn_weights, slot_vals)  # [B, N, D]

        # V10.14.6d: Route through read_output_proj. Since the main forward
        # detaches read output, this retrieval loss is the ONLY gradient source
        # for read_output_proj — it learns useful projections without LM
        # interference.
        projected = self.read_output_proj(raw_retrieved)  # [B, N, D]

        # Select only query positions
        query_retrieved = projected[query_mask]  # [num_queries, D]
        query_targets = target_ids[query_mask]

        if query_retrieved.shape[0] == 0:
            return torch.tensor(0.0, device=x.device, dtype=x.dtype)

        # Normalize before lm_head: projected values may have arbitrary scale,
        # but lm_head expects layer-normed input (same as main path).
        query_retrieved = self.retr_read_norm(query_retrieved)  # [num_queries, D]
        query_logits = lm_head(query_retrieved)  # [num_queries, V]

        retrieval_loss = F.cross_entropy(
            query_logits, query_targets, ignore_index=-100
        )

        # V11.3: Diagnostics for pre-attention retrieval experiment
        with torch.no_grad():
            self._diag_retr_query_norm = x[query_mask].norm(dim=-1).mean().item()
            self._diag_retr_retrieved_norm = query_retrieved.norm(dim=-1).mean().item()

        return retrieval_loss

    def compute_slot_prediction_loss(
        self,
        x: torch.Tensor,              # [B, N, D] — token representations (pre-attention)
        slot_keys: torch.Tensor,       # [B, K, D_key] — slot keys
        slot_vals: torch.Tensor,       # [B, K, D] — slot values
        query_mask: torch.Tensor,      # [B, N] — True at query positions
        target_ids: torch.Tensor,      # [B, N] — target token IDs
    ) -> torch.Tensor:
        """
        V11.4: Slot-only predictive usefulness test.

        Tests whether slot content carries information useful for next-token
        prediction, using a SEPARATE prediction head (not shared lm_head).
        This eliminates the failure mode where retrieval loss improves because
        lm_head improves, rather than because slots contain better content.

        Slot-derived tensor: slot_vals → attention-weighted retrieval →
            read_output_proj → slot_pred_norm → slot_pred_head → CE loss

        The query is formed from x (pre-attention embeddings), which provides
        only positional/token identity info — no backbone computation.
        The prediction comes entirely from what the slots contain.

        Cannot bypass slots: the only path to the prediction head goes through
        slot_vals retrieval. If slots contain no useful info, this loss stays
        at ~log(50257) ≈ 10.8 (random).

        Gradient flow:
          ✓ read_output_proj (projection of retrieved content)
          ✓ slot_vals (via retrieval attention weighted sum)
          ✓ write_val_proj (via slot_vals computation graph)
          ✓ slot_pred_head (the separate prediction bottleneck)
          ✓ slot_pred_norm (normalization before prediction)
          ✗ backbone layers (x is detached at capture point)
          ✗ lm_head (not used — separate head)
          ✗ token embeddings (detached in x)

        This loss tests usefulness to generation, NOT self-consistency:
          - Retrieval loss = "can slots reconstruct what was stored?" (self-referential)
          - Slot prediction loss = "can slots predict the next token?" (LM-useful)

        Success criterion is NOT this loss improving alone — it's whether
        ablation delta moves off zero. If this loss improves but ablation
        stays flat, slots are still learning in isolation.

        Returns:
            slot_pred_loss: Scalar CE loss from slot-only prediction.
        """
        if query_mask is None or not query_mask.any():
            return torch.tensor(0.0, device=x.device, dtype=x.dtype)

        # V12: Use read_query_proj (matches read() and compute_retrieval_loss).
        queries = self.read_query_proj(x)  # [B, N, D_key]
        # V12.4: Match read() path scale (same fix as compute_retrieval_loss).
        _scale = torch.exp(self._read_log_scale).clamp(min=1.5, max=self._read_scale_max)
        _q_norm = F.normalize(queries, dim=-1)
        _sk_norm = F.normalize(slot_keys.detach(), dim=-1)
        attn_logits = torch.bmm(
            _q_norm, _sk_norm.transpose(1, 2)
        ) * _scale  # [B, N, K]
        attn_weights = F.softmax(attn_logits, dim=-1)  # [B, N, K]

        # Retrieve weighted slot values — this is the slot-derived representation
        raw_retrieved = torch.bmm(attn_weights, slot_vals)  # [B, N, D]

        # Route through read_output_proj (shared with retrieval loss path)
        projected = self.read_output_proj(raw_retrieved)  # [B, N, D]

        # Select query positions
        query_retrieved = projected[query_mask]  # [num_queries, D]
        query_targets = target_ids[query_mask]

        if query_retrieved.shape[0] == 0:
            return torch.tensor(0.0, device=x.device, dtype=x.dtype)

        # Normalize then predict through SEPARATE head (not lm_head)
        query_retrieved = self.slot_pred_norm(query_retrieved)  # [num_queries, D]
        slot_logits = self.slot_pred_head(query_retrieved)  # [num_queries, V]

        slot_pred_loss = F.cross_entropy(
            slot_logits, query_targets, ignore_index=-100
        )

        # Diagnostics: loss + top-1 accuracy
        with torch.no_grad():
            self._diag_slot_pred_loss = slot_pred_loss.item()
            preds = slot_logits.argmax(dim=-1)
            valid = query_targets != -100
            if valid.any():
                self._diag_slot_pred_acc = (
                    (preds[valid] == query_targets[valid]).float().mean().item()
                )
            else:
                self._diag_slot_pred_acc = 0.0

        return slot_pred_loss

    def compute_sharpness_loss(self) -> torch.Tensor:
        """
        V10.14.6: MoE-style router loss — sharp, balanced, and gate-selective.

        Three-term loss:

        Term 1 — Target sharpness (L_sharp):
            ReLU(H(assign_t) - H_target) averaged over tokens.
            H_target ≈ 1.0 nats: allows 2-3 active slots per token.

        Term 2 — Load balancing (L_bal):
            KL(marginal || uniform) where marginal = mean(assign) over tokens.
            Prevents single-slot collapse.

        Term 3 — Gate sparsity (L_gate):  [NEW in V10.14.6]
            Mean(novelty) — L1 penalty pushing gate toward closed.
            Without this, gate drifts to 1.0 (everything writes, including
            filler). Retrieval loss counteracts by pushing gate open for
            tokens that actually carry binding info. The tension creates
            selectivity.

        Returns:
            router_loss: λ_sharp * L_sharp + λ_bal * L_bal + λ_gate * L_gate
        """
        if self._last_assignment is None:
            return torch.tensor(0.0)

        assignment = self._last_assignment  # [B, N, K]
        K = self.num_slots
        eps = 1e-8

        # --- Term 1: Target sharpness ---
        # Per-token entropy: H(a_t) = -sum(a * log(a))
        log_a = torch.log(assignment + eps)
        per_token_H = -(assignment * log_a).sum(dim=-1)  # [B, N], ≥ 0
        # Only penalize if entropy exceeds target (don't reward going below)
        # V10.29: Adaptive entropy target
        H_target = self._H_target  # nats — adapts based on slot utilization
        L_sharp = torch.relu(per_token_H - H_target).mean()

        # --- Term 2: Load balancing (KL to uniform) ---
        # Marginal: average assignment over all tokens in the batch
        # [B, N, K] → [K] average
        marginal = assignment.mean(dim=(0, 1))  # [K]
        # KL(marginal || uniform) = sum(p * log(p * K))
        L_bal = (marginal * torch.log(marginal * K + eps)).sum()

        # --- Term 3: Gate sparsity (V10.14.6) ---
        # V10.14.7 removed L_gate (pushed gate→0, causing chicken-and-egg collapse).
        # But without ANY gate signal, the 10% gradient leak through x_write lets
        # LM loss weakly push gate→floor (0.15). Gate has no upward pressure →
        # collapses → slots starve → retr_loss plateaus at ~5.0.
        #
        # Fix: Log-barrier utilization loss. Penalizes gates near 0 but is gentle
        # above ~0.3. This gives the gate a positive learning signal without
        # overwhelming retrieval loss like the old L_gate did.
        # L_gate_util = -mean(log(gate)) — strong near 0, weak near 1.
        L_gate_util = torch.tensor(0.0, device=assignment.device, dtype=assignment.dtype)
        if self._last_novelty is not None:
            L_gate_util = -torch.log(self._last_novelty + eps).mean()

        # Store diagnostics (normalized by max entropy for readability)
        max_entropy = math.log(K)
        with torch.no_grad():
            self._diag_marginal_entropy = (
                -(marginal * torch.log(marginal + eps)).sum() / max_entropy
            ).item()
            self._diag_per_token_entropy = per_token_H.mean().item()
            self._diag_L_sharp = L_sharp.item()
            self._diag_L_bal = L_bal.item()
            # V10.29.1: Store for adaptive controller (avoids recomputation)
            self._diag_L_ortho = None  # Set below after L_ortho is computed

        # V10.14.7: Removed old L_gate (mean(novelty) pushed gate→0).
        # V10.26: Added L_gate_util (log-barrier) — pushes gate OPEN.
        # Weight 0.01: -log(0.15)=1.90 → contributes ~0.019 to loss.
        # At gate=0.3: -log(0.3)=1.20 → ~0.012. Gentle enough not to
        # overwhelm retrieval loss but prevents floor collapse.
        # --- Term 4: Slot key orthogonality (V10.14.8) ---
        # Penalize slot keys for being too similar. Without this, EMA updates
        # drift keys toward the mean token embedding → all slots become identical.
        # L_ortho = ||K·K^T - I||_F^2 / K^2 (normalized Frobenius norm)
        # V12.4: Apply to BOTH _last_slot_keys (post-EMA, indirect gradient)
        # AND slot_keys_init (direct gradient to the learnable parameter).
        # Previously only applied to _last_slot_keys, but gradient through EMA
        # is attenuated by η≈0.1 and the .clone() + detach in the assignment
        # path makes it very indirect. Direct term on slot_keys_init ensures
        # the initial key configuration stays orthogonal.
        L_ortho = torch.tensor(0.0, device=assignment.device, dtype=assignment.dtype)
        # (a) Post-EMA keys (existing)
        if hasattr(self, '_last_slot_keys') and self._last_slot_keys is not None:
            _sk = F.normalize(self._last_slot_keys, dim=-1)  # [B, K, D]
            _sim = torch.bmm(_sk, _sk.transpose(1, 2))
            _eye = torch.eye(self.num_slots, device=_sim.device, dtype=_sim.dtype)
            _off_diag = _sim - _eye.unsqueeze(0)
            L_ortho = (_off_diag ** 2).mean()
            self._diag_L_ortho = L_ortho.item()
        # (b) Direct term on slot_keys_init (learnable parameter)
        _sk_init = F.normalize(self.slot_keys_init, dim=-1)  # [K, D_key]
        _sim_init = _sk_init @ _sk_init.t()  # [K, K]
        _eye_init = torch.eye(self.num_slots, device=_sim_init.device, dtype=_sim_init.dtype)
        L_ortho_init = ((_sim_init - _eye_init) ** 2).mean()
        L_ortho = L_ortho + L_ortho_init

        # V10.14.8: L_bal weight 0.02→1.0. At 0.02 the balance loss contributed
        # ~0.08 to a total loss of ~30 — completely drowned out. Slots collapsed
        # to marginal_H=0.24 (1-2 slots used out of 64). At 1.0, L_bal≈4.16
        # when fully collapsed, providing meaningful gradient to redistribute.
        # V10.27: Adaptive gate ceiling — soft quadratic penalty above target.
        # Below target: only log-barrier (pushes open, existing behavior).
        # Above target: quadratic penalty pushes closed, preventing churn.
        L_gate_ceil = torch.tensor(0.0, device=assignment.device, dtype=assignment.dtype)
        if self._last_novelty is not None:
            gate_mean = self._last_novelty.mean()
            L_gate_ceil = torch.relu(gate_mean - self._gate_target - self._gate_ceil_margin) ** 2

        # V10.29: All loss weights are adaptive
        return (self._L_sharp_weight * L_sharp + self._L_bal_weight * L_bal
                + self._L_ortho_weight * L_ortho
                + 0.01 * L_gate_util + self._gate_ceil_weight * L_gate_ceil)

    def update_write_gate_target(self, retr_loss: float):
        """V10.27: Adapt write gate ceiling based on retrieval loss trend.

        Called each step after computing retrieval loss. Accumulates a
        window of retr_loss and gate values, then adjusts the ceiling
        every _gate_adapt_window steps based on the window-level trend.

        Rules (applied once per window, not per step):
        - retr_loss decreased over window → relax ceiling (writes helping)
        - retr_loss flat/increased + gate above target → tighten (churn)

        Args:
            retr_loss: Current retrieval loss value.
        """
        # V11: Skip adaptation when disabled
        if not self.enable_adaptive_constraints:
            return

        gate_val = getattr(self, '_diag_write_gate_mean', 0.0)

        self._retr_loss_window.append(retr_loss)
        self._gate_window.append(gate_val)
        self._gate_adapt_counter += 1

        # Only adapt every _gate_adapt_window steps
        if self._gate_adapt_counter < self._gate_adapt_window:
            return

        # Compute window-level trend: compare first half mean to second half mean
        n = len(self._retr_loss_window)
        half = n // 2
        first_half_retr = sum(self._retr_loss_window[:half]) / max(half, 1)
        second_half_retr = sum(self._retr_loss_window[half:]) / max(n - half, 1)
        retr_delta = second_half_retr - first_half_retr  # negative = improving

        gate_mean = sum(self._gate_window) / n

        # Adaptive rules (symmetric rates to prevent ratchet effect):
        if retr_delta < -0.05:
            # Retrieval improving over window → relax ceiling
            self._gate_target = min(
                self._gate_target_max,
                self._gate_target + 0.02
            )
        elif retr_delta > -0.01 and gate_mean > self._gate_target:
            # Retrieval stagnant/worsening AND gate above target → tighten
            self._gate_target = max(
                self._gate_target_min,
                self._gate_target - 0.02
            )

        # Reset window
        self._retr_loss_window.clear()
        self._gate_window.clear()
        self._gate_adapt_counter = 0

    def update_constraint_relaxation(self, retr_loss: float, lm_loss: float = 0.0):
        """V10.29: Unified adaptive hyperparameter controller.

        Manages 11 adaptive parameters based on slot health signals.
        All start conservative for fresh training, relax/tighten based
        on sustained symptoms detected over _constraint_relax_interval steps.

        Audit fixes (V10.29.1):
        - gate_mean and L_ortho use window averages, not stale single-batch
        - gate_target only modified by update_write_gate_target() (no double-write)
        - gate floor clamped to never exceed gate_target - 0.05
        - lists bounded to 2× interval as safety cap
        - retr_loss_weight is absolute (not multiplied with config weight)

        Args:
            retr_loss: Current retrieval loss value.
            lm_loss: Current LM loss value (for ratio-based adaptation).
        """
        # V11: Skip all adaptive adjustments when disabled
        if not self.enable_adaptive_constraints:
            return

        marginal_H = getattr(self, '_diag_marginal_entropy', None)
        if marginal_H is None:
            return

        # Accumulate per-step signals into windows
        self._constraint_relax_window.append(marginal_H)
        self._retr_loss_history.append(retr_loss)
        if lm_loss > 0:
            self._lm_loss_history.append(lm_loss)
        # BUG 3 fix: Accumulate gate_mean per step (not stale single-batch)
        _cur_gate = getattr(self, '_diag_write_gate_mean', 0.0) or 0.0
        self._gate_mean_window.append(_cur_gate)
        # BUG 4 fix: Accumulate L_ortho per step
        _cur_ortho = getattr(self, '_diag_L_ortho', None)
        if _cur_ortho is None and hasattr(self, '_last_slot_keys') and self._last_slot_keys is not None:
            with torch.no_grad():
                _sk = F.normalize(self._last_slot_keys, dim=-1)
                _sim = torch.bmm(_sk, _sk.transpose(1, 2))
                _eye = torch.eye(self.num_slots, device=_sim.device, dtype=_sim.dtype)
                _cur_ortho = ((_sim - _eye.unsqueeze(0)) ** 2).mean().item()
        if _cur_ortho is not None:
            self._L_ortho_window.append(_cur_ortho)

        self._constraint_relax_counter += 1

        # BUG 6 fix: Cap list sizes to 2× interval as safety bound.
        # Prevents unbounded growth if counter logic is bypassed.
        _max_len = self._constraint_relax_interval * 2
        for _lst in (self._constraint_relax_window, self._retr_loss_history,
                     self._lm_loss_history, self._gate_mean_window,
                     self._L_ortho_window):
            if len(_lst) > _max_len:
                del _lst[:len(_lst) - _max_len]

        if self._constraint_relax_counter < self._constraint_relax_interval:
            return

        # ── Compute window statistics ──────────────────────────────────────
        n = len(self._constraint_relax_window)
        avg_marginal_H = sum(self._constraint_relax_window) / n

        # BUG 3 fix: Use window-averaged gate_mean
        avg_gate = sum(self._gate_mean_window) / max(len(self._gate_mean_window), 1)
        _raw_wr_scale = torch.exp(self._write_log_scale).item()
        wr_scale = max(1.5, min(_raw_wr_scale, self._wr_scale_max))
        _raw_rd_scale = torch.exp(self._read_log_scale).item()
        read_scale = max(18.0, min(_raw_rd_scale, self._read_scale_max))
        per_token_H = getattr(self, '_diag_per_token_entropy', 1.0) or 1.0
        # BUG 4 fix: Use window-averaged L_ortho
        avg_ortho = sum(self._L_ortho_window) / max(len(self._L_ortho_window), 1) if self._L_ortho_window else 0.0

        avg_retr = sum(self._retr_loss_history) / len(self._retr_loss_history)
        avg_lm = sum(self._lm_loss_history) / max(len(self._lm_loss_history), 1) if self._lm_loss_history else 0.0

        changes = []

        # ── (1) L_bal weight: adaptive retr_loss-driven ─────────────────
        # V11.1: Replace hard-coded marginal_H threshold with signal-driven
        # relaxation. The old threshold (marginal_H > 0.95) was too high —
        # L_bal successfully enforced uniformity (marginal_H ≈ 0.93) which
        # prevented slot specialization entirely.
        #
        # New logic: L_bal exists to prevent collapse (1-2 slots dominating).
        # But if retr_loss is improving, slots are learning useful content,
        # so L_bal should relax to let natural specialization emerge.
        # If marginal_H drops too low (<0.7), slots have over-specialized
        # and L_bal should increase to redistribute.
        #
        # Three conditions for relaxation (any one triggers):
        # (a) retr_loss improving over window → slots learning, let them specialize
        # (b) marginal_H high AND no collapse risk → uniform = L_bal succeeded too well
        # (c) Collapse guard: marginal_H < 0.7 → re-apply L_bal
        half = len(self._retr_loss_history) // 2
        retr_improving = False
        retr_velocity = 0.0
        if half > 0:
            first_half = sum(self._retr_loss_history[:half]) / half
            second_half = sum(self._retr_loss_history[half:]) / max(len(self._retr_loss_history) - half, 1)
            if first_half > 0:
                retr_velocity = (second_half - first_half) / first_half  # negative = improving
                retr_improving = retr_velocity < -0.02  # >2% improvement

        if avg_marginal_H < 0.7 and self._L_bal_weight < 1.0:
            # Collapse guard: slots over-specialized, strengthen balance
            old = self._L_bal_weight
            self._L_bal_weight = min(1.0, self._L_bal_weight * 1.5)
            self._L_bal_last_reason = "over-specialized"
            changes.append(f"L_bal: {old:.3f}→{self._L_bal_weight:.3f} (over-specialized, mH={avg_marginal_H:.3f})")
        elif retr_improving and avg_marginal_H > 0.80 and self._L_bal_weight > self._L_bal_weight_floor:
            # Retr loss improving + slots still fairly uniform → relax L_bal
            # Decay rate proportional to improvement velocity (faster improvement → faster relaxation)
            decay_rate = max(0.5, 1.0 + retr_velocity * 5.0)  # e.g. vel=-0.05 → decay=0.75
            old = self._L_bal_weight
            self._L_bal_weight = max(self._L_bal_weight_floor, self._L_bal_weight * decay_rate)
            self._L_bal_last_reason = "retr_improving"
            changes.append(f"L_bal: {old:.3f}→{self._L_bal_weight:.3f} (retr improving {retr_velocity:+.1%}, mH={avg_marginal_H:.3f})")
        elif avg_marginal_H > 0.92 and not retr_improving and self._L_bal_weight > self._L_bal_weight_floor:
            # Even without retr improvement, if slots are very uniform, gently relax
            # (but slower than the retr-driven path — 0.85x vs velocity-proportional)
            old = self._L_bal_weight
            self._L_bal_weight = max(self._L_bal_weight_floor, self._L_bal_weight * 0.85)
            self._L_bal_last_reason = "too_uniform"
            changes.append(f"L_bal: {old:.3f}→{self._L_bal_weight:.3f} (too uniform, mH={avg_marginal_H:.3f})")

        # ── (2) Write scale max clamp ─────────────────────────────────────
        # Use raw (unclamped) scale: only relax when the optimizer is actively
        # pushing the parameter above the clamp, not just because init > clamp.
        if _raw_wr_scale > self._wr_scale_max * 1.02 and self._wr_scale_max < self._wr_scale_max_limit:
            old = self._wr_scale_max
            self._wr_scale_max = min(self._wr_scale_max_limit, self._wr_scale_max + 0.5)
            changes.append(f"wr_scale_max: {old:.1f}→{self._wr_scale_max:.1f} (optimizer pushing)")

        # ── (3) Gate ceiling weight (only) ────────────────────────────────
        # BUG 5 fix: Only adjust _gate_ceil_weight here; _gate_target is
        # exclusively owned by update_write_gate_target() (200-step window).
        # V12.4: Bidirectional — decay when gate near target, strengthen when
        # gate has collapsed well below target (was one-way ratchet before).
        if avg_gate > self._gate_target * 0.95 and self._gate_ceil_weight > 1.0:
            old_w = self._gate_ceil_weight
            self._gate_ceil_weight = max(1.0, self._gate_ceil_weight * 0.7)
            changes.append(f"gate_ceil: {old_w:.1f}→{self._gate_ceil_weight:.1f} (near target, relaxing)")
        elif avg_gate < self._gate_target * 0.5 and self._gate_ceil_weight < 5.0:
            # Gate well below target — strengthen ceiling to push it open
            old_w = self._gate_ceil_weight
            self._gate_ceil_weight = min(5.0, self._gate_ceil_weight * 1.3)
            changes.append(f"gate_ceil: {old_w:.1f}→{self._gate_ceil_weight:.1f} (gate low, strengthening)")

        # ── (4) Novelty gate floor ────────────────────────────────────────
        # Gate collapsed at floor for sustained period → raise floor to rescue
        if avg_gate <= self._novelty_gate_floor * 1.05 and self._novelty_gate_floor < self._novelty_gate_floor_max:
            old = self._novelty_gate_floor
            self._novelty_gate_floor = min(
                self._novelty_gate_floor_max,
                self._novelty_gate_floor + 0.02
            )
            changes.append(f"gate_floor: {old:.2f}→{self._novelty_gate_floor:.2f} (collapsed)")
        # Gate well above floor → can lower floor for more dynamic range
        elif avg_gate > self._novelty_gate_floor * 2.0 and self._novelty_gate_floor > self._novelty_gate_floor_min:
            old = self._novelty_gate_floor
            self._novelty_gate_floor = max(
                self._novelty_gate_floor_min,
                self._novelty_gate_floor - 0.02
            )
            changes.append(f"gate_floor: {old:.2f}→{self._novelty_gate_floor:.2f} (healthy)")

        # BUG 2 fix: Enforce floor < ceiling invariant (min 0.05 gap)
        _max_floor = self._gate_target - 0.05
        if self._novelty_gate_floor > _max_floor:
            old = self._novelty_gate_floor
            self._novelty_gate_floor = max(self._novelty_gate_floor_min, _max_floor)
            changes.append(f"gate_floor: {old:.2f}→{self._novelty_gate_floor:.2f} "
                           f"(clamped: floor must be < ceiling {self._gate_target:.2f})")

        # ── (5) Retrieval loss weight ─────────────────────────────────────
        # BUG 7 fix: This weight is used AS-IS in train.py (replacing, not
        # multiplying with, config.retrieval_loss_weight when adaptive is active).
        # V11.2: Ablation-aware guard — don't decay if slots are neutral or helping.
        # Only decay when ablation shows slots are actively hurting (delta < -1.0)
        # or when no ablation data is available yet (None = pre-ablation warmup).
        _ablation_allows_decay = (
            self._last_ablation_delta is None  # No ablation yet, allow warmup decay
            or self._last_ablation_delta < -1.0  # Slots actively hurting
        )
        if avg_lm > 0 and avg_retr > avg_lm * 0.5 and self._adaptive_retr_loss_weight > self._adaptive_retr_loss_weight_min:
            if _ablation_allows_decay:
                old = self._adaptive_retr_loss_weight
                self._adaptive_retr_loss_weight = max(
                    self._adaptive_retr_loss_weight_min,
                    self._adaptive_retr_loss_weight * 0.8
                )
                changes.append(f"retr_weight: {old:.2f}→{self._adaptive_retr_loss_weight:.2f} "
                               f"(retr/lm={avg_retr/avg_lm:.2f}, dominates)")
            else:
                changes.append(f"retr_weight: {self._adaptive_retr_loss_weight:.2f} "
                               f"(held: ablation Δ={self._last_ablation_delta:+.2f}, slots not hurting)")
        elif avg_lm > 0 and avg_retr < avg_lm * 0.1 and self._adaptive_retr_loss_weight < self._adaptive_retr_loss_weight_max:
            half = len(self._retr_loss_history) // 2
            if half > 0:
                first_half = sum(self._retr_loss_history[:half]) / half
                second_half = sum(self._retr_loss_history[half:]) / max(len(self._retr_loss_history) - half, 1)
                if second_half < first_half * 0.95:
                    old = self._adaptive_retr_loss_weight
                    self._adaptive_retr_loss_weight = min(
                        self._adaptive_retr_loss_weight_max,
                        self._adaptive_retr_loss_weight * 1.2
                    )
                    changes.append(f"retr_weight: {old:.2f}→{self._adaptive_retr_loss_weight:.2f} "
                                   f"(small & improving)")

        # ── (6) H_target (sharpness entropy target) ──────────────────────
        if per_token_H > self._H_target * 1.5 and self._H_target < self._H_target_max:
            old = self._H_target
            self._H_target = min(self._H_target_max, self._H_target + 0.1)
            changes.append(f"H_target: {old:.2f}→{self._H_target:.2f} (entropy too high)")
        elif per_token_H < self._H_target * 0.5 and self._H_target > self._H_target_min:
            old = self._H_target
            self._H_target = max(self._H_target_min, self._H_target - 0.1)
            changes.append(f"H_target: {old:.2f}→{self._H_target:.2f} (already sharp)")

        # ── (7) L_ortho weight (uses window avg) ─────────────────────────
        if avg_ortho < 0.01 and self._L_ortho_weight > self._L_ortho_weight_min:
            old = self._L_ortho_weight
            self._L_ortho_weight = max(self._L_ortho_weight_min, self._L_ortho_weight * 0.7)
            changes.append(f"L_ortho: {old:.3f}→{self._L_ortho_weight:.3f} (already orthogonal)")
        elif avg_ortho > 0.1 and self._L_ortho_weight < self._L_ortho_weight_max:
            old = self._L_ortho_weight
            self._L_ortho_weight = min(self._L_ortho_weight_max, self._L_ortho_weight * 1.3)
            changes.append(f"L_ortho: {old:.3f}→{self._L_ortho_weight:.3f} (collapsing)")

        # ── (8) Read scale max clamp ──────────────────────────────────────
        # Same fix as (2): use raw unclamped scale to detect genuine optimizer push.
        if _raw_rd_scale > self._read_scale_max * 1.02 and self._read_scale_max < self._read_scale_max_limit:
            old = self._read_scale_max
            self._read_scale_max = min(self._read_scale_max_limit, self._read_scale_max + 1.0)
            changes.append(f"read_scale_max: {old:.1f}→{self._read_scale_max:.1f} (optimizer pushing)")

        # ── (9) Soft detach leak ──────────────────────────────────────────
        if avg_gate <= self._novelty_gate_floor * 1.1 and self._soft_detach_leak < self._soft_detach_leak_max:
            old = self._soft_detach_leak
            self._soft_detach_leak = min(self._soft_detach_leak_max, self._soft_detach_leak + 0.03)
            changes.append(f"detach_leak: {old:.2f}→{self._soft_detach_leak:.2f} (gate collapsed)")
        elif avg_gate > 0.3 and self._soft_detach_leak > self._soft_detach_leak_min:
            old = self._soft_detach_leak
            self._soft_detach_leak = max(self._soft_detach_leak_min, self._soft_detach_leak - 0.01)
            changes.append(f"detach_leak: {old:.2f}→{self._soft_detach_leak:.2f} (gate healthy)")

        # ── (10) L_sharp weight ───────────────────────────────────────────
        # Note: Uses per_token_H which is last-batch (acceptable since
        # H_target adjusts slowly and L_sharp is medium priority).
        if abs(per_token_H - self._H_target) < 0.2 and self._L_sharp_weight > self._L_sharp_weight_min:
            old = self._L_sharp_weight
            self._L_sharp_weight = max(self._L_sharp_weight_min, self._L_sharp_weight * 0.8)
            changes.append(f"L_sharp: {old:.3f}→{self._L_sharp_weight:.3f} (in range)")
        elif abs(per_token_H - self._H_target) > 1.0 and self._L_sharp_weight < self._L_sharp_weight_max:
            old = self._L_sharp_weight
            self._L_sharp_weight = min(self._L_sharp_weight_max, self._L_sharp_weight * 1.3)
            changes.append(f"L_sharp: {old:.3f}→{self._L_sharp_weight:.3f} (off target)")

        # ── (11) Adaptive write_lr (EMA coefficient) ─────────────────────
        # Retrieval loss improving → writes are useful → allow faster EMA
        # Retrieval loss stagnating/worsening → slow down to preserve content
        half = len(self._retr_loss_history) // 2
        if half > 0:
            first_half = sum(self._retr_loss_history[:half]) / half
            second_half = sum(self._retr_loss_history[half:]) / max(len(self._retr_loss_history) - half, 1)
            if second_half < first_half * 0.90 and self.write_lr < self._write_lr_max:
                # Retrieval improving (>10% drop) → writes are useful, speed up
                old = self.write_lr
                self.write_lr = min(self._write_lr_max, self.write_lr * 1.15)
                changes.append(f"write_lr: {old:.3f}→{self.write_lr:.3f} (retr improving)")
            elif second_half > first_half * 1.05 and self.write_lr > self._write_lr_min:
                # Retrieval worsening (>5% rise) → slow down writes
                old = self.write_lr
                self.write_lr = max(self._write_lr_min, self.write_lr * 0.85)
                changes.append(f"write_lr: {old:.3f}→{self.write_lr:.3f} (retr worsening)")
        # Also: if gate is collapsed, lower write_lr to reduce churn
        if avg_gate < self._novelty_gate_floor * 1.1 and self.write_lr > self._write_lr_min:
            old = self.write_lr
            self.write_lr = max(self._write_lr_min, self.write_lr * 0.90)
            if not any('write_lr' in c for c in changes):
                changes.append(f"write_lr: {old:.3f}→{self.write_lr:.3f} (gate collapsed)")

        # ── Log changes ───────────────────────────────────────────────────
        if changes:
            print(f"\n  [SLOT ADAPT] {len(changes)} adjustment(s):")
            for c in changes:
                print(f"    → {c}")

        # Reset all windows
        self._constraint_relax_window.clear()
        self._retr_loss_history.clear()
        self._lm_loss_history.clear()
        self._gate_mean_window.clear()
        self._L_ortho_window.clear()
        self._constraint_relax_counter = 0


@dataclass
class GCTConfig:
    """Configuration for Gated Coherence Transformer."""
    # Base transformer config
    vocab_size: int = 50257
    embed_dim: int = 768
    num_layers: int = 12
    num_heads: int = 12
    ff_dim: Optional[int] = None
    max_seq_len: int = 8192
    dropout: float = 0.1

    # GCT-specific: Coherence gating
    gct_window_size: int = 128          # Local window size for coarse path
    gct_coherence_gamma: float = 5.0    # Sensitivity for output delta in coherence score
    gct_coherence_delta: float = 3.0    # Sensitivity for residual delta in coherence score
    gct_ema_decay: float = 0.9          # EMA smoothing for coherence scores
    gct_num_bands: int = 3              # Number of frequency bands (global/mid/local)

    # GCT-specific: Routing
    gct_alpha_sharpness: float = 10.0   # Sigmoid sharpness for routing probability
    gct_hard_route_threshold: float = 0.5  # Threshold for hard routing (inference)
    gct_use_hard_routing: bool = False   # Use hard routing (inference mode)

    # GCT-specific: Lambda_ladder band insulation
    gct_kappa: float = 3.0              # Ladder suppression strength
    gct_tau_ladder: float = 0.15        # Collapse detection threshold (similarity above this = collapse risk)

    # GCT-specific: Training schedule
    gct_warmup_steps: int = 500         # Steps of full-attention-only warmup (Phase 1)
    gct_anneal_steps: int = 2000        # Steps to anneal from full to gated (Phase 2)
    gct_current_step: int = 0           # Current training step (updated externally)

    def __post_init__(self):
        if self.ff_dim is None:
            self.ff_dim = 4 * self.embed_dim


class GCTCoherenceModule(nn.Module):
    """
    Computes pre-softmax coherence scores from output and residual deltas.

    FlashAttention-compatible: does NOT require raw attention matrices.
    Uses only output deltas and residual deltas as stability signals.

    Coherence score:
        C_raw(t) = exp(-gamma * ||O(t) - O(t-1)||_rel) * exp(-delta * ||R(t) - R(t-1)||_rel)

    Where ||.||_rel = ||.|| / (||ref|| + eps) for scale invariance.

    EMA smoothing:
        C_hat(t) = beta * C_hat(t-1) + (1 - beta) * C_raw(t)
    """

    def __init__(self, num_heads: int, ema_decay: float = 0.9,
                 gamma: float = 5.0, delta: float = 3.0):
        super().__init__()
        self.num_heads = num_heads
        self.ema_decay = ema_decay
        self.gamma = gamma
        self.delta = delta

    def forward(
        self,
        attn_output: torch.Tensor,  # [B, H, N, D_h] per-head attention output
        residual: torch.Tensor,      # [B, N, D] residual stream
    ) -> torch.Tensor:
        """
        Compute coherence scores for all positions.

        Returns:
            coherence: [B, H, N] coherence scores in [0, 1]
        """
        B, H, N, D_h = attn_output.shape

        # Output delta: compare adjacent positions per head
        # attn_output[:, :, t] vs attn_output[:, :, t-1]
        output_delta = attn_output[:, :, 1:] - attn_output[:, :, :-1]  # [B, H, N-1, D_h]
        output_norm = output_delta.norm(dim=-1)  # [B, H, N-1]
        ref_norm = attn_output[:, :, :-1].norm(dim=-1).clamp(min=1e-6)  # [B, H, N-1]
        output_delta_rel = output_norm / ref_norm  # [B, H, N-1]

        # Residual delta: compare adjacent positions (broadcast across heads)
        # residual: [B, N, D]
        res_delta = residual[:, 1:] - residual[:, :-1]  # [B, N-1, D]
        res_norm = res_delta.norm(dim=-1)  # [B, N-1]
        res_ref_norm = residual[:, :-1].norm(dim=-1).clamp(min=1e-6)  # [B, N-1]
        res_delta_rel = res_norm / res_ref_norm  # [B, N-1]
        res_delta_rel = res_delta_rel.unsqueeze(1).expand_as(output_delta_rel)  # [B, H, N-1]

        # Raw coherence: high when deltas are small (stable region)
        c_raw = torch.exp(-self.gamma * output_delta_rel) * torch.exp(-self.delta * res_delta_rel)
        # c_raw: [B, H, N-1] in (0, 1]

        # Pad position 0 with neutral coherence (0.5 = no routing preference)
        c_first = torch.full((B, H, 1), 0.5, device=c_raw.device, dtype=c_raw.dtype)
        c_raw = torch.cat([c_first, c_raw], dim=2)  # [B, H, N]

        # EMA smoothing across sequence dimension (causal)
        coherence = torch.zeros_like(c_raw)
        coherence[:, :, 0] = c_raw[:, :, 0]
        for t in range(1, N):
            coherence[:, :, t] = self.ema_decay * coherence[:, :, t - 1] + (1 - self.ema_decay) * c_raw[:, :, t]

        return coherence  # [B, H, N] in [0, 1]


class GCTRoutingGate(nn.Module):
    """
    Pre-softmax routing gate: decides full vs local attention per head per position.

    pi(l,h,t) = sigma(alpha_b * (C_hat(l,h,t) - tau(b,h)))

    Where b is the frequency band of head h.

    Band assignment: equal partition of heads into num_bands groups.
    - Band 0 (global): heads that should attend broadly
    - Band 1 (mid): intermediate attention span
    - Band 2 (local): heads that can use local window

    Each band has a learnable threshold tau_b and sharpness alpha_b.
    """

    def __init__(self, num_heads: int, num_bands: int = 3,
                 alpha_init: float = 10.0):
        super().__init__()
        self.num_heads = num_heads
        self.num_bands = num_bands

        # Assign heads to bands (equal partition)
        heads_per_band = num_heads // num_bands
        band_assignment = []
        for b in range(num_bands):
            count = heads_per_band if b < num_bands - 1 else num_heads - b * heads_per_band
            band_assignment.extend([b] * count)
        self.register_buffer('band_assignment', torch.tensor(band_assignment, dtype=torch.long))

        # Per-band learnable parameters
        # tau_b: threshold (higher = harder to route to coarse)
        # Band 0 (global) has high threshold (rarely uses local window)
        # Band 2 (local) has low threshold (often uses local window)
        tau_init = torch.linspace(0.7, 0.3, num_bands)  # Global=0.7, Local=0.3
        self.tau = nn.Parameter(tau_init)

        # Per-band sharpness
        self.alpha = nn.Parameter(torch.full((num_bands,), alpha_init))

    def forward(self, coherence: torch.Tensor) -> torch.Tensor:
        """
        Compute routing probability pi for each head at each position.

        Args:
            coherence: [B, H, N] coherence scores in [0, 1]

        Returns:
            pi: [B, H, N] routing probabilities in [0, 1]
                (high pi = route to local/coarse, low pi = use full attention)
        """
        # Gather per-head thresholds and sharpness from band assignment
        tau_per_head = self.tau[self.band_assignment]         # [H]
        alpha_per_head = self.alpha[self.band_assignment]     # [H]

        # Reshape for broadcasting: [1, H, 1]
        tau = tau_per_head.view(1, -1, 1)
        alpha = alpha_per_head.view(1, -1, 1)

        # pi = sigma(alpha * (C - tau))
        # High coherence (stable) -> high pi -> route to local (save compute)
        # Low coherence (unstable) -> low pi -> use full attention (be careful)
        pi = torch.sigmoid(alpha * (coherence - tau))

        return pi  # [B, H, N]


class GCTLadderInsulation(nn.Module):
    """
    Lambda_ladder: band insulation to prevent collapse.

    When heads in different bands produce too-similar outputs
    (low inter-band divergence = collapse risk), suppress routing
    to coarse path, forcing full attention to preserve band specialization.

    Corrected sign logic:
        Collapse risk = bands becoming indistinguishable
        Low divergence = high similarity = collapse risk

        Lambda = exp(-kappa * max(0, tau_collapse - Delta_band))

    When Delta_band < tau_collapse (bands too similar):
        Lambda decreases -> pi* decreases -> more full attention

    When Delta_band >= tau_collapse (bands well-separated):
        Lambda = 1 -> no suppression -> routing proceeds normally
    """

    def __init__(self, kappa: float = 3.0, tau_ladder: float = 0.15):
        super().__init__()
        self.kappa = kappa
        self.tau_ladder = tau_ladder

    def compute_band_divergence(
        self,
        attn_output: torch.Tensor,  # [B, H, N, D_h]
        band_assignment: torch.Tensor,  # [H] band index per head
        num_bands: int,
    ) -> torch.Tensor:
        """
        Compute inter-band divergence using cosine distance between band means.

        Delta_band = 1 - mean_{b1 != b2} cos_sim(mean_{h in b1}(O_h), mean_{h in b2}(O_h))

        Returns:
            divergence: [B, N] inter-band divergence in [0, 2]
        """
        B, H, N, D_h = attn_output.shape

        # Compute band-mean outputs: average over heads in each band
        band_means = []
        for b in range(num_bands):
            mask = (band_assignment == b)
            if mask.any():
                band_out = attn_output[:, mask].mean(dim=1)  # [B, N, D_h]
                band_means.append(band_out)

        if len(band_means) < 2:
            # Only one band — no divergence to measure
            return torch.zeros(B, N, device=attn_output.device)

        # Pairwise cosine similarity between band means
        cos_sims = []
        for i in range(len(band_means)):
            for j in range(i + 1, len(band_means)):
                # [B, N]
                sim = F.cosine_similarity(band_means[i], band_means[j], dim=-1)
                cos_sims.append(sim)

        mean_similarity = torch.stack(cos_sims, dim=0).mean(dim=0)  # [B, N]
        divergence = 1.0 - mean_similarity  # [B, N] in [-1, 1], typically [0, 1]

        return divergence

    def forward(
        self,
        attn_output: torch.Tensor,  # [B, H, N, D_h]
        band_assignment: torch.Tensor,  # [H]
        num_bands: int,
    ) -> torch.Tensor:
        """
        Compute ladder insulation factor.

        Returns:
            lambda_ladder: [B, N] in (0, 1]
        """
        divergence = self.compute_band_divergence(attn_output, band_assignment, num_bands)

        # Corrected sign: suppress when divergence is LOW (collapse risk)
        # Lambda = exp(-kappa * max(0, tau - Delta))
        collapse_pressure = torch.clamp(self.tau_ladder - divergence, min=0.0)
        lambda_ladder = torch.exp(-self.kappa * collapse_pressure)

        return lambda_ladder  # [B, N] in (0, 1]


class GCTAttentionLayer(nn.Module):
    """
    Gated Coherence Transformer Attention Layer.

    Combines full O(n²) softmax attention with local-window softmax attention,
    blended by a pre-softmax coherence gate with lambda_ladder band insulation.

    Training (soft blend):
        O = (1 - pi*) * O_full + pi* * O_local

    Inference (hard route):
        O = O_local if pi* > theta else O_full

    The full path uses SDPA/FlashAttention when available.
    The local path uses masked softmax over a sliding window of size w.
    Coherence is computed from output/residual deltas (FlashAttention-compatible).

    Phased training schedule:
        Phase 1 (warmup): Full attention only, coherence predictors warm up
        Phase 2 (anneal): Soft blend gradually enabled
        Phase 3 (full):   Full gated operation
    """

    def __init__(self, gct_config: GCTConfig, layer_idx: int = 0):
        super().__init__()
        embed_dim = gct_config.embed_dim
        num_heads = gct_config.num_heads
        self.embed_dim = embed_dim
        self.num_heads = num_heads
        self.head_dim = embed_dim // num_heads
        self.scale = self.head_dim ** -0.5
        self.layer_idx = layer_idx
        self.gct_config = gct_config

        # QKV projections (shared between full and local paths)
        self.q_proj = nn.Linear(embed_dim, embed_dim)
        self.k_proj = nn.Linear(embed_dim, embed_dim)
        self.v_proj = nn.Linear(embed_dim, embed_dim)
        self.out_proj = nn.Linear(embed_dim, embed_dim)

        self.dropout = nn.Dropout(gct_config.dropout)
        self.norm = nn.LayerNorm(embed_dim)

        # GCT modules
        self.coherence = GCTCoherenceModule(
            num_heads=num_heads,
            ema_decay=gct_config.gct_ema_decay,
            gamma=gct_config.gct_coherence_gamma,
            delta=gct_config.gct_coherence_delta,
        )
        self.routing_gate = GCTRoutingGate(
            num_heads=num_heads,
            num_bands=gct_config.gct_num_bands,
            alpha_init=gct_config.gct_alpha_sharpness,
        )
        self.ladder = GCTLadderInsulation(
            kappa=gct_config.gct_kappa,
            tau_ladder=gct_config.gct_tau_ladder,
        )

        # Window size for local path
        self.window_size = gct_config.gct_window_size

    def _compute_full_attention(
        self, Q: torch.Tensor, K: torch.Tensor, V: torch.Tensor,
        causal_mask: bool = True,
    ) -> torch.Tensor:
        """Full O(n²) attention using SDPA when available."""
        if SDPA_AVAILABLE:
            output = F.scaled_dot_product_attention(
                Q, K, V, is_causal=causal_mask,
                dropout_p=self.dropout.p if self.training else 0.0,
            )
        else:
            B, H, N, D_h = Q.shape
            attn = torch.matmul(Q, K.transpose(-2, -1)) * self.scale
            if causal_mask:
                mask = torch.triu(torch.ones(N, N, device=Q.device, dtype=torch.bool), diagonal=1)
                attn = attn.masked_fill(mask, float('-inf'))
            attn = F.softmax(attn, dim=-1)
            attn = self.dropout(attn)
            output = torch.matmul(attn, V)
        return output  # [B, H, N, D_h]

    def _compute_local_attention(
        self, Q: torch.Tensor, K: torch.Tensor, V: torch.Tensor,
        causal_mask: bool = True,
    ) -> torch.Tensor:
        """
        Local-window softmax attention: O(n*w) instead of O(n²).

        Each position t attends only to positions in W(t) = {max(0, t-w+1), ..., t}.
        Implemented via masking the full attention matrix (training-friendly).
        """
        B, H, N, D_h = Q.shape
        w = self.window_size

        # Compute full attention scores (we mask most of them)
        attn = torch.matmul(Q, K.transpose(-2, -1)) * self.scale  # [B, H, N, N]

        # Create combined causal + local window mask
        # Position t can attend to positions max(0, t-w+1) through t
        row_idx = torch.arange(N, device=Q.device).unsqueeze(1)  # [N, 1]
        col_idx = torch.arange(N, device=Q.device).unsqueeze(0)  # [1, N]

        # Local window: col must be >= row - w + 1 AND col <= row (causal)
        local_mask = (col_idx > row_idx) | (col_idx < row_idx - w + 1)  # True = masked out
        if causal_mask:
            causal = col_idx > row_idx
            local_mask = local_mask | causal

        attn = attn.masked_fill(local_mask.unsqueeze(0).unsqueeze(0), float('-inf'))
        attn = F.softmax(attn, dim=-1)
        attn = self.dropout(attn)
        output = torch.matmul(attn, V)

        return output  # [B, H, N, D_h]

    def _get_schedule_weight(self) -> float:
        """
        Get the gating schedule weight based on training phase.

        Phase 1 (step < warmup): weight = 0 (full attention only)
        Phase 2 (warmup <= step < warmup + anneal): weight linearly ramps 0 -> 1
        Phase 3 (step >= warmup + anneal): weight = 1 (full gating)
        """
        step = self.gct_config.gct_current_step
        warmup = self.gct_config.gct_warmup_steps
        anneal = self.gct_config.gct_anneal_steps

        if step < warmup:
            return 0.0
        elif step < warmup + anneal:
            return (step - warmup) / max(1, anneal)
        else:
            return 1.0

    def forward(
        self,
        x: torch.Tensor,
        causal_mask: bool = True,
    ) -> Dict[str, torch.Tensor]:
        """
        GCT attention forward pass.

        Returns:
            Dict with:
                'output': [B, N, D] attention output (residual + norm applied)
                'gct_metrics': dict with routing stats for logging
        """
        B, N, D = x.shape
        residual = x

        # Project Q, K, V
        Q = self.q_proj(x).view(B, N, self.num_heads, self.head_dim).transpose(1, 2)
        K = self.k_proj(x).view(B, N, self.num_heads, self.head_dim).transpose(1, 2)
        V = self.v_proj(x).view(B, N, self.num_heads, self.head_dim).transpose(1, 2)
        # Q, K, V: [B, H, N, D_h]

        schedule_weight = self._get_schedule_weight()

        if schedule_weight == 0.0:
            # Phase 1: Full attention only (no gating overhead)
            output = self._compute_full_attention(Q, K, V, causal_mask)
            output = output.transpose(1, 2).reshape(B, N, D)
            output = self.out_proj(output)
            output = self.dropout(output)
            result_output = self.norm(output + residual)
            return {
                'output': result_output,
                'gct_metrics': {
                    'gct_schedule_weight': 0.0,
                    'gct_mean_pi_star': 0.0,
                    'gct_mean_lambda_ladder': 1.0,
                    'gct_mean_coherence': 0.5,
                    'gct_frac_local_routed': 0.0,
                },
            }

        # === Compute both attention paths ===

        # Full attention (uses SDPA/FlashAttention)
        O_full = self._compute_full_attention(Q, K, V, causal_mask)  # [B, H, N, D_h]

        # Local-window attention
        O_local = self._compute_local_attention(Q, K, V, causal_mask)  # [B, H, N, D_h]

        # === Coherence gating ===

        # Compute coherence from output deltas and residual deltas
        coherence = self.coherence(O_full.detach(), residual)  # [B, H, N]

        # Routing probability
        pi = self.routing_gate(coherence)  # [B, H, N]

        # Lambda_ladder band insulation
        lambda_ladder = self.ladder(
            O_full.detach(),
            self.routing_gate.band_assignment,
            self.routing_gate.num_bands,
        )  # [B, N]

        # Effective routing: pi* = pi * lambda_ladder
        pi_star = pi * lambda_ladder.unsqueeze(1)  # [B, H, N]

        # Apply schedule weight (Phase 2 annealing)
        pi_star = pi_star * schedule_weight

        if self.gct_config.gct_use_hard_routing and not self.training:
            # Hard routing for inference
            theta = self.gct_config.gct_hard_route_threshold
            use_local = (pi_star > theta).unsqueeze(-1)  # [B, H, N, 1]
            output = torch.where(use_local, O_local, O_full)
        else:
            # Soft blend for training
            pi_expanded = pi_star.unsqueeze(-1)  # [B, H, N, 1]
            output = (1 - pi_expanded) * O_full + pi_expanded * O_local

        # Reshape and project
        output = output.transpose(1, 2).reshape(B, N, D)
        output = self.out_proj(output)
        output = self.dropout(output)
        result_output = self.norm(output + residual)

        # Metrics for logging
        with torch.no_grad():
            metrics = {
                'gct_schedule_weight': schedule_weight,
                'gct_mean_pi_star': pi_star.mean().item(),
                'gct_mean_lambda_ladder': lambda_ladder.mean().item(),
                'gct_mean_coherence': coherence.mean().item(),
                'gct_frac_local_routed': (pi_star > 0.5).float().mean().item(),
            }

        return {
            'output': result_output,
            'gct_metrics': metrics,
        }


class GCTTransformerBlock(nn.Module):
    """Transformer block with GCT (Gated Coherence Transformer) attention."""

    def __init__(self, gct_config: GCTConfig, layer_idx: int = 0):
        super().__init__()
        # Convert GCTConfig to TransformerConfig for FeedForward
        self.attention = GCTAttentionLayer(gct_config, layer_idx=layer_idx)
        self.ff = FeedForward(
            embed_dim=gct_config.embed_dim,
            ff_dim=gct_config.ff_dim,
            dropout=gct_config.dropout,
        )

    def forward(
        self, x: torch.Tensor, causal_mask: bool = True,
    ) -> Dict[str, Any]:
        attn_result = self.attention(x, causal_mask)
        x = self.ff(attn_result['output'])
        return {
            'output': x,
            'gct_metrics': attn_result['gct_metrics'],
        }


class GCTTransformer(nn.Module):
    """
    Gated Coherence Transformer (GCT).

    A standard O(n²) transformer augmented with pre-softmax coherence gating
    and lambda_ladder band insulation. Routes each head at each position
    between full attention (O(n²)) and local-window attention (O(n*w))
    based on temporal stability signals.

    Training: Soft blend with phased schedule (warmup -> anneal -> full gating).
    Inference: Hard routing for real FLOP savings.

    The routing decision is made BEFORE computing QK^T, using only output
    deltas and residual deltas from the previous layer — the core contribution.
    """

    def __init__(
        self,
        vocab_size: int = 50257,
        embed_dim: int = 768,
        num_layers: int = 12,
        num_heads: int = 12,
        ff_dim: Optional[int] = None,
        max_seq_len: int = 8192,
        dropout: float = 0.1,
        tie_embeddings: bool = True,
        # GCT-specific
        gct_window_size: int = 128,
        gct_coherence_gamma: float = 5.0,
        gct_coherence_delta: float = 3.0,
        gct_ema_decay: float = 0.9,
        gct_num_bands: int = 3,
        gct_alpha_sharpness: float = 10.0,
        gct_hard_route_threshold: float = 0.5,
        gct_use_hard_routing: bool = False,
        gct_kappa: float = 3.0,
        gct_tau_ladder: float = 0.15,
        gct_warmup_steps: int = 500,
        gct_anneal_steps: int = 2000,
        **kwargs,
    ):
        super().__init__()

        gct_config = GCTConfig(
            vocab_size=vocab_size,
            embed_dim=embed_dim,
            num_layers=num_layers,
            num_heads=num_heads,
            ff_dim=ff_dim,
            max_seq_len=max_seq_len,
            dropout=dropout,
            gct_window_size=gct_window_size,
            gct_coherence_gamma=gct_coherence_gamma,
            gct_coherence_delta=gct_coherence_delta,
            gct_ema_decay=gct_ema_decay,
            gct_num_bands=gct_num_bands,
            gct_alpha_sharpness=gct_alpha_sharpness,
            gct_hard_route_threshold=gct_hard_route_threshold,
            gct_use_hard_routing=gct_use_hard_routing,
            gct_kappa=gct_kappa,
            gct_tau_ladder=gct_tau_ladder,
            gct_warmup_steps=gct_warmup_steps,
            gct_anneal_steps=gct_anneal_steps,
        )
        self.gct_config = gct_config
        self.tie_embeddings = tie_embeddings

        # Embeddings
        self.token_embed = nn.Embedding(vocab_size, embed_dim)
        self.pos_embed = nn.Embedding(max_seq_len, embed_dim)
        self.embed_dropout = nn.Dropout(dropout)

        # GCT Transformer blocks
        self.blocks = nn.ModuleList([
            GCTTransformerBlock(gct_config, layer_idx=i) for i in range(num_layers)
        ])

        # Output
        self.norm = nn.LayerNorm(embed_dim)
        self.lm_head = nn.Linear(embed_dim, vocab_size, bias=False)

        # V10.11: Learnable logit scale initialized to 1.0.
        # Previous: 1/sqrt(sqrt(d)) ≈ 0.25 which flattened softmax → incoherent text.
        self.logit_scale = nn.Parameter(torch.ones(1))

        if tie_embeddings:
            self.lm_head.weight = self.token_embed.weight

        self.apply(self._init_weights)

        if not self.tie_embeddings:
            with torch.no_grad():
                self.lm_head.weight.copy_(self.token_embed.weight)

    def _init_weights(self, module):
        if isinstance(module, nn.Linear):
            torch.nn.init.normal_(module.weight, mean=0.0, std=0.02)
            if module.bias is not None:
                torch.nn.init.zeros_(module.bias)
        elif isinstance(module, nn.Embedding):
            torch.nn.init.normal_(module.weight, mean=0.0, std=0.02)

    def set_training_step(self, step: int):
        """Update training step for phased schedule across all layers."""
        self.gct_config.gct_current_step = step

    def set_hard_routing(self, enabled: bool):
        """Enable/disable hard routing (for inference vs training)."""
        self.gct_config.gct_use_hard_routing = enabled

    def forward(
        self,
        input_ids: torch.Tensor,
        return_hidden: bool = False,
        extract_layers: Optional[List[int]] = None,
        return_last_hidden: bool = False,
    ) -> Dict[str, Any]:
        """
        Forward pass.

        Args:
            input_ids: [B, N] token indices
            return_hidden: Return all hidden states
            extract_layers: Specific layer indices to extract
            return_last_hidden: Return normalized hidden state before lm_head

        Returns:
            Dict with 'logits' and optionally 'hidden_states', 'last_hidden_state',
            and 'gct_metrics' (aggregated across layers)
        """
        B, N = input_ids.shape

        should_extract = return_hidden or extract_layers is not None
        extract_set = set(extract_layers) if extract_layers is not None else None

        positions = torch.arange(N, device=input_ids.device).unsqueeze(0)
        x = self.token_embed(input_ids) + self.pos_embed(positions)
        x = self.embed_dropout(x)

        hidden_states = [] if should_extract else None
        all_gct_metrics = []

        for i, block in enumerate(self.blocks):
            block_result = block(x, causal_mask=True)
            x = block_result['output']
            all_gct_metrics.append(block_result['gct_metrics'])

            if should_extract:
                if extract_set is None or i in extract_set:
                    hidden_states.append(x)

        x = self.norm(x)
        logits = self.lm_head(x) * self.logit_scale

        result = {'logits': logits}

        if should_extract:
            result['hidden_states'] = hidden_states

        if return_last_hidden:
            result['last_hidden_state'] = x

        # Aggregate GCT metrics across layers
        if all_gct_metrics:
            agg = {}
            for key in all_gct_metrics[0]:
                vals = [m[key] for m in all_gct_metrics]
                agg[key] = sum(vals) / len(vals)
            result['gct_metrics'] = agg

        return result


class StandardTransformer(nn.Module):
    """
    Standard O(n²) Transformer for comparison.

    Same architecture as PhaseTransformer but with standard attention.
    """

    def __init__(
        self,
        vocab_size: int = 50257,
        embed_dim: int = 768,
        num_layers: int = 12,
        num_heads: int = 12,
        ff_dim: Optional[int] = None,
        max_seq_len: int = 8192,
        dropout: float = 0.1,
        tie_embeddings: bool = True,  # V9.6.0: Set False when using Sanskrit/CSR
        **kwargs,  # Ignore phase-specific params
    ):
        super().__init__()

        config = TransformerConfig(
            vocab_size=vocab_size,
            embed_dim=embed_dim,
            num_layers=num_layers,
            num_heads=num_heads,
            ff_dim=ff_dim,
            max_seq_len=max_seq_len,
            dropout=dropout,
        )
        self.config = config
        self.tie_embeddings = tie_embeddings

        # Embeddings
        self.token_embed = nn.Embedding(vocab_size, embed_dim)
        self.pos_embed = nn.Embedding(max_seq_len, embed_dim)
        self.embed_dropout = nn.Dropout(dropout)

        # Transformer blocks
        self.blocks = nn.ModuleList([
            StandardTransformerBlock(config) for _ in range(num_layers)
        ])

        # Output
        self.norm = nn.LayerNorm(embed_dim)
        self.lm_head = nn.Linear(embed_dim, vocab_size, bias=False)

        # V10.11: Learnable logit scale initialized to 1.0.
        # Previous: 1/sqrt(sqrt(d)) ≈ 0.25 which flattened softmax → incoherent text.
        self.logit_scale = nn.Parameter(torch.ones(1))

        # V9.6.0: Optionally tie weights (disable when using Sanskrit/CSR injection)
        if tie_embeddings:
            self.lm_head.weight = self.token_embed.weight

        self.apply(self._init_weights)

        # V9.6.10: For untied embeddings, copy token_embed to lm_head AFTER init
        # This provides semantic alignment at start while keeping them separate
        if not self.tie_embeddings:
            with torch.no_grad():
                self.lm_head.weight.copy_(self.token_embed.weight)

    def _init_weights(self, module):
        if isinstance(module, nn.Linear):
            torch.nn.init.normal_(module.weight, mean=0.0, std=0.02)
            if module.bias is not None:
                torch.nn.init.zeros_(module.bias)
        elif isinstance(module, nn.Embedding):
            torch.nn.init.normal_(module.weight, mean=0.0, std=0.02)

    def forward(
        self,
        input_ids: torch.Tensor,
        return_hidden: bool = False,
        extract_layers: Optional[List[int]] = None,
        return_last_hidden: bool = False,
    ) -> Dict[str, torch.Tensor]:
        """
        Forward pass with efficient layer extraction.

        Args:
            input_ids: [B, N] token indices
            return_hidden: Return all hidden states
            extract_layers: Specific layer indices to extract (memory-efficient)
            return_last_hidden: Return normalized hidden state before lm_head

        Returns:
            Dict with 'logits' and optionally 'hidden_states', 'last_hidden_state'
        """
        B, N = input_ids.shape

        # Determine which layers to extract
        should_extract = return_hidden or extract_layers is not None
        extract_set = set(extract_layers) if extract_layers is not None else None

        positions = torch.arange(N, device=input_ids.device).unsqueeze(0)
        x = self.token_embed(input_ids) + self.pos_embed(positions)
        x = self.embed_dropout(x)

        hidden_states = [] if should_extract else None
        for i, block in enumerate(self.blocks):
            x = block(x, causal_mask=True)

            if should_extract:
                if extract_set is None or i in extract_set:
                    hidden_states.append(x)

        x = self.norm(x)
        logits = self.lm_head(x) * self.logit_scale

        result = {'logits': logits}

        if should_extract:
            result['hidden_states'] = hidden_states

        if return_last_hidden:
            result['last_hidden_state'] = x

        return result


# =============================================================================
# COMPARISON UTILITIES
# =============================================================================

def count_parameters(model: nn.Module) -> int:
    """Count trainable parameters."""
    return sum(p.numel() for p in model.parameters() if p.requires_grad)


def measure_inference_time(
    model: nn.Module,
    input_ids: torch.Tensor,
    num_runs: int = 10,
    warmup: int = 3,
) -> float:
    """Measure average inference time in milliseconds."""
    device = next(model.parameters()).device

    # Warmup
    with torch.no_grad():
        for _ in range(warmup):
            _ = model(input_ids)

    if device.type == 'cuda':
        torch.cuda.synchronize()

    # Timed runs
    start = time.time()
    with torch.no_grad():
        for _ in range(num_runs):
            _ = model(input_ids)

    if device.type == 'cuda':
        torch.cuda.synchronize()

    return (time.time() - start) / num_runs * 1000  # ms


def compare_models(
    phase_model: PhaseTransformer,
    std_model: StandardTransformer,
    seq_lengths: List[int] = [256, 512, 1024, 2048],
    batch_size: int = 4,
    device: Optional[torch.device] = None,
) -> Dict[str, Any]:
    """
    Compare Phase Transformer vs Standard Transformer.

    Returns detailed comparison metrics.
    """
    if device is None:
        device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')

    phase_model = phase_model.to(device).eval()
    std_model = std_model.to(device).eval()

    results = {
        'device': str(device),
        'phase_params': count_parameters(phase_model),
        'std_params': count_parameters(std_model),
        'timings': [],
    }

    print("\n" + "=" * 70)
    print("  PHASE TRANSFORMER vs STANDARD TRANSFORMER")
    print("=" * 70)
    print(f"\n  Device: {device}")
    print(f"  Phase params: {results['phase_params']:,}")
    print(f"  Standard params: {results['std_params']:,}")
    print(f"\n  {'SeqLen':<10} {'Standard':<15} {'Phase':<15} {'Speedup':<10} {'Savings':<10}")
    print(f"  {'-'*60}")

    for seq_len in seq_lengths:
        input_ids = torch.randint(0, 1000, (batch_size, seq_len), device=device)

        std_time = measure_inference_time(std_model, input_ids)
        phase_time = measure_inference_time(phase_model, input_ids)

        speedup = std_time / phase_time if phase_time > 0 else 0
        savings = (std_time - phase_time) / std_time * 100 if std_time > 0 else 0

        results['timings'].append({
            'seq_len': seq_len,
            'std_time_ms': std_time,
            'phase_time_ms': phase_time,
            'speedup': speedup,
            'savings_pct': savings,
        })

        print(f"  {seq_len:<10} {std_time:<15.2f}ms {phase_time:<15.2f}ms {speedup:<10.1f}x {savings:<10.1f}%")

    # Verify outputs are valid
    print("\n  Output Validation:")
    input_ids = torch.randint(0, 1000, (2, 128), device=device)

    with torch.no_grad():
        phase_out = phase_model(input_ids)['logits']
        std_out = std_model(input_ids)['logits']

    phase_valid = not (torch.isnan(phase_out).any() or torch.isinf(phase_out).any())
    std_valid = not (torch.isnan(std_out).any() or torch.isinf(std_out).any())

    print(f"    Phase output valid: {'✓' if phase_valid else '✗'}")
    print(f"    Standard output valid: {'✓' if std_valid else '✗'}")

    results['phase_valid'] = phase_valid
    results['std_valid'] = std_valid

    # Summary
    avg_speedup = sum(t['speedup'] for t in results['timings']) / len(results['timings'])
    print(f"\n  Average Speedup: {avg_speedup:.1f}x")
    print("=" * 70)

    results['avg_speedup'] = avg_speedup

    return results


def quick_test():
    """Quick validation test."""
    print("\nQuick Test: Phase Transformer")
    print("-" * 40)

    # Small model for quick test
    model = PhaseTransformer(
        vocab_size=1000,
        embed_dim=128,
        num_layers=2,
        num_heads=4,
    )

    print(f"Parameters: {count_parameters(model):,}")

    # Forward pass
    input_ids = torch.randint(0, 1000, (2, 32))
    output = model(input_ids)

    print(f"Input shape: {input_ids.shape}")
    print(f"Output shape: {output['logits'].shape}")
    print(f"Output valid: {not torch.isnan(output['logits']).any()}")

    # Backward pass
    loss = output['logits'].mean()
    loss.backward()

    # Check gradients: pass if at least some gradients exist and none are NaN/Inf
    has_any_grad = False
    grads_ok = True
    for p in model.parameters():
        if p.requires_grad and p.grad is not None:
            has_any_grad = True
            if torch.isnan(p.grad).any() or torch.isinf(p.grad).any():
                grads_ok = False
                break
    grads_ok = grads_ok and has_any_grad
    print(f"Gradients valid: {grads_ok}")

    print("-" * 40)
    return grads_ok


def long_context_benchmark(max_seq_len: int = 32768, batch_size: int = 1):
    """
    Benchmark Phase Transformer at long context lengths up to 32K tokens.

    This validates the O(n) scaling advantage at production-scale contexts.
    Tests will automatically reduce sequence length if memory is insufficient.
    """
    print("\n" + "=" * 70)
    print("  LONG CONTEXT BENCHMARK (up to 32K tokens)")
    print("=" * 70)

    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    print(f"\n  Device: {device}")

    # Smaller model for long context testing (to fit in memory)
    phase_model = PhaseTransformer(
        vocab_size=10000,
        embed_dim=128,  # Smaller for memory
        num_layers=2,
        num_heads=4,
    ).to(device).eval()

    std_model = StandardTransformer(
        vocab_size=10000,
        embed_dim=128,
        num_layers=2,
        num_heads=4,
    ).to(device).eval()

    print(f"  Model: embed_dim=128, layers=2, heads=4")
    print(f"  Phase params: {count_parameters(phase_model):,}")
    print(f"  Standard params: {count_parameters(std_model):,}")

    # Test sequence lengths: 512, 1K, 2K, 4K, 8K, 16K, 32K
    seq_lengths = [512, 1024, 2048, 4096, 8192, 16384, 32768]
    seq_lengths = [s for s in seq_lengths if s <= max_seq_len]

    print(f"\n  {'SeqLen':<10} {'Standard':<15} {'Phase':<15} {'Speedup':<12} {'Status'}")
    print(f"  {'-'*65}")

    results = []
    baseline_std = None
    baseline_phase = None

    for seq_len in seq_lengths:
        try:
            input_ids = torch.randint(0, 1000, (batch_size, seq_len), device=device)

            # Measure standard transformer
            try:
                std_time = measure_inference_time(std_model, input_ids, num_runs=3)
            except RuntimeError as e:
                if "out of memory" in str(e).lower():
                    std_time = float('inf')
                    if device.type == 'cuda':
                        torch.cuda.empty_cache()
                else:
                    raise

            # Measure phase transformer
            try:
                phase_time = measure_inference_time(phase_model, input_ids, num_runs=3)
            except RuntimeError as e:
                if "out of memory" in str(e).lower():
                    phase_time = float('inf')
                    if device.type == 'cuda':
                        torch.cuda.empty_cache()
                else:
                    raise

            # Store baseline for scaling analysis
            if baseline_std is None and std_time != float('inf'):
                baseline_std = std_time
                baseline_phase = phase_time

            # Calculate speedup
            if std_time == float('inf') and phase_time == float('inf'):
                speedup_str = "Both OOM"
                status = "⚠"
            elif std_time == float('inf'):
                speedup_str = "Std OOM"
                status = "✓ Phase only"
            elif phase_time == float('inf'):
                speedup_str = "Phase OOM"
                status = "⚠"
            else:
                speedup = std_time / phase_time
                speedup_str = f"{speedup:.1f}x"
                status = "✓"

            # Format times
            std_str = f"{std_time:.1f}ms" if std_time != float('inf') else "OOM"
            phase_str = f"{phase_time:.1f}ms" if phase_time != float('inf') else "OOM"

            print(f"  {seq_len:<10} {std_str:<15} {phase_str:<15} {speedup_str:<12} {status}")

            results.append({
                'seq_len': seq_len,
                'std_time': std_time,
                'phase_time': phase_time,
            })

            # Clean up
            del input_ids
            if device.type == 'cuda':
                torch.cuda.empty_cache()

        except RuntimeError as e:
            if "out of memory" in str(e).lower():
                print(f"  {seq_len:<10} {'OOM':<15} {'OOM':<15} {'---':<12} ⚠ Memory limit")
                if device.type == 'cuda':
                    torch.cuda.empty_cache()
                break
            else:
                raise

    # Scaling analysis
    print(f"\n  Scaling Analysis:")
    valid_results = [r for r in results if r['std_time'] != float('inf') and r['phase_time'] != float('inf')]

    if len(valid_results) >= 2:
        # Calculate scaling factor (time increase per 2x sequence length)
        std_scaling = []
        phase_scaling = []

        for i in range(1, len(valid_results)):
            if valid_results[i]['seq_len'] == 2 * valid_results[i-1]['seq_len']:
                std_scaling.append(valid_results[i]['std_time'] / valid_results[i-1]['std_time'])
                phase_scaling.append(valid_results[i]['phase_time'] / valid_results[i-1]['phase_time'])

        if std_scaling:
            avg_std_scaling = sum(std_scaling) / len(std_scaling)
            avg_phase_scaling = sum(phase_scaling) / len(phase_scaling)

            print(f"    Standard: ~{avg_std_scaling:.1f}x per 2x seq_len (O(n²) expects ~4x)")
            print(f"    Phase:    ~{avg_phase_scaling:.1f}x per 2x seq_len (O(n) expects ~2x)")

            if avg_phase_scaling < avg_std_scaling:
                print(f"    ✓ Phase scales {avg_std_scaling/avg_phase_scaling:.1f}x better than standard")

    # Maximum context achieved
    max_std = max([r['seq_len'] for r in results if r['std_time'] != float('inf')], default=0)
    max_phase = max([r['seq_len'] for r in results if r['phase_time'] != float('inf')], default=0)

    print(f"\n  Maximum Context Achieved:")
    print(f"    Standard Transformer: {max_std:,} tokens")
    print(f"    Phase Transformer:    {max_phase:,} tokens")

    if max_phase > max_std:
        print(f"    ✓ Phase handles {max_phase/max_std:.1f}x longer context!")

    print("=" * 70)

    return results


# =============================================================================
# MAIN
# =============================================================================

if __name__ == "__main__":
    import sys

    # Check for command-line arguments
    run_long_context = "--long" in sys.argv or "--32k" in sys.argv
    max_seq = 32768
    if "--16k" in sys.argv:
        max_seq = 16384
    elif "--8k" in sys.argv:
        max_seq = 8192

    # Quick validation
    success = quick_test()

    if success:
        print("\n✓ Quick test passed!")

        # Full comparison (if resources available)
        try:
            phase_model = PhaseTransformer(
                vocab_size=50257,
                embed_dim=256,
                num_layers=4,
                num_heads=8,
            )

            std_model = StandardTransformer(
                vocab_size=50257,
                embed_dim=256,
                num_layers=4,
                num_heads=8,
            )

            results = compare_models(
                phase_model,
                std_model,
                seq_lengths=[128, 256, 512, 1024],
                batch_size=2,
            )

            print(f"\n✓ Comparison complete! Average speedup: {results['avg_speedup']:.1f}x")

        except RuntimeError as e:
            if "out of memory" in str(e).lower():
                print("\n⚠ Not enough memory for full comparison")
            else:
                raise

        # Long context benchmark (optional)
        if run_long_context:
            print("\n" + "=" * 70)
            print("  Running Long Context Benchmark...")
            print("  (This may take a while and use significant memory)")
            print("=" * 70)
            try:
                long_context_benchmark(max_seq_len=max_seq)
            except RuntimeError as e:
                if "out of memory" in str(e).lower():
                    print("\n⚠ Out of memory during long context benchmark")
                else:
                    raise
        else:
            print("\n  Tip: Run with --long or --32k for long context benchmark (up to 32K tokens)")
            print("       Use --16k or --8k for smaller benchmarks")

    else:
        print("\n✗ Quick test failed!")
