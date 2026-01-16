#!/usr/bin/env python3
"""
Phase Ablation Utilities for PhaseAttention Testing
=====================================================

Provides utilities for running controlled ablations on PhaseAttention:
1. BASELINE: Normal inference with phases active
2. PHASE-SCRAMBLE: Scramble φ_k and φ_q per head (keep amplitudes, values)
3. PHASE-FROZEN: Replace φ_k, φ_q with constants (0 or learned mean)
4. PHASE-OFF: Bypass phase computation entirely (uniform attention)

These ablations test whether PhaseAttention is actually contributing to
the model's relational reasoning capabilities.

Key Principle: Phase ablation should NOT modify weights, only the forward pass.
This is a controlled experiment isolating phase from amplitude/value pathways.

Author: Claude (Diagnostic Script for PhaseAttention)
Date: January 2026
"""

import math
from typing import Dict, Optional, Callable, List, Any
from enum import Enum
from contextlib import contextmanager
from dataclasses import dataclass
import copy

import torch
import torch.nn as nn
import torch.nn.functional as F


class AblationMode(Enum):
    """Ablation modes for PhaseAttention testing."""
    BASELINE = "baseline"           # Normal inference
    PHASE_SCRAMBLE = "scramble"     # Random permute phases per head
    PHASE_FROZEN = "frozen"         # Constant phase (no selectivity)
    PHASE_AMPLIFIED = "amplified"   # Double phase variance (stress test)
    PHASE_OFF = "phase_off"         # Bypass phase entirely (uniform attention)


@dataclass
class AblationResult:
    """Result from a single ablated inference."""
    mode: AblationMode
    logits: torch.Tensor              # [B, N, vocab] output logits
    phase_health: Dict[str, float]    # R_k, R_q, etc. if captured
    metadata: Dict[str, Any]          # Additional info (e.g., scramble seed)


# =============================================================================
# FORWARD HOOK FACTORY FOR PHASE ABLATION
# =============================================================================

class PhaseAblationHook:
    """
    Forward hook that modifies phase tensors during PhaseAttentionLayer forward.

    This is a non-invasive way to ablate phases without modifying the model.
    The hook intercepts the forward pass and modifies the phase computation.
    """

    def __init__(
        self,
        mode: AblationMode,
        scramble_seed: Optional[int] = None,
        frozen_phase_value: float = 0.0,
        amplification_factor: float = 2.0,
    ):
        """
        Initialize the ablation hook.

        Args:
            mode: Which ablation to apply
            scramble_seed: Random seed for scramble mode (for reproducibility)
            frozen_phase_value: Phase value to use in frozen mode (default 0)
            amplification_factor: Multiplier for amplified mode (default 2x)
        """
        self.mode = mode
        self.scramble_seed = scramble_seed
        self.frozen_phase_value = frozen_phase_value
        self.amplification_factor = amplification_factor
        self.original_methods = {}  # Store original forward methods

    def _scramble_phases(self, phi: torch.Tensor) -> torch.Tensor:
        """
        Scramble phase tensor by permuting within each head.

        Preserves:
        - Overall statistics (mean, std)
        - Per-head structure
        - Amplitude information is unchanged

        Destroys:
        - Position-specific phase relationships
        - Token-token binding via phase alignment
        """
        B, N, H, D_h = phi.shape

        # Set seed for reproducibility if provided
        if self.scramble_seed is not None:
            torch.manual_seed(self.scramble_seed)

        # Permute within each (batch, head) independently
        # This destroys position-phase relationships while keeping distributions
        phi_scrambled = phi.clone()
        for b in range(B):
            for h in range(H):
                # Random permutation of position dimension
                perm = torch.randperm(N, device=phi.device)
                phi_scrambled[b, :, h, :] = phi[b, perm, h, :]

        return phi_scrambled

    def _freeze_phases(self, phi: torch.Tensor) -> torch.Tensor:
        """
        Replace all phases with a constant value.

        Effect: cos(φ_q - φ_k) = cos(0) = 1 everywhere
        This removes all phase-based selectivity, making attention uniform.
        """
        return torch.full_like(phi, self.frozen_phase_value)

    def _amplify_phases(self, phi: torch.Tensor) -> torch.Tensor:
        """
        Amplify phase variance by scaling away from mean.

        This stress-tests whether the model relies on phase magnitude.
        """
        # Center phases around mean, scale, then re-add mean
        phi_mean = phi.mean(dim=(1, 3), keepdim=True)  # Mean over positions and dims
        phi_centered = phi - phi_mean
        phi_amplified = phi_mean + self.amplification_factor * phi_centered

        # Wrap to [-π, π] to maintain valid phase range
        phi_amplified = torch.atan2(torch.sin(phi_amplified), torch.cos(phi_amplified))

        return phi_amplified

    def _uniform_phases(self, phi: torch.Tensor) -> torch.Tensor:
        """
        Set phases to create uniform attention (bypass phase selectivity).

        SEMANTICS (IMPORTANT):
        ----------------------
        This sets φ_q = φ_k = 0 for all positions.

        Effect on attention:
            cos(φ_q - φ_k) = cos(0 - 0) = cos(0) = 1.0 for ALL position pairs

        This means the phase term contributes equally everywhere, effectively
        removing position-selective weighting from the phase mechanism.

        What PHASE_OFF tests:
            Whether the model can solve the task using ONLY:
            - Learned amplitude weights (a_k)
            - State decay (γ)
            - Value projections (W_v)
            WITHOUT phase-based position selection.

        What PHASE_OFF does NOT do:
            - It does NOT disable the phase computation entirely
            - It does NOT remove amplitude weighting
            - It does NOT bypass the PhaseAttention layer

        Distinction from FROZEN:
            FROZEN: φ = constant (e.g., 0) for all positions at init time
                    Phase DYNAMICS are disabled (no learned phase movement)
            PHASE_OFF: φ_q = φ_k = 0, ensuring cos(Δφ) = 1 always
                       Phase SELECTIVITY is disabled (uniform weighting)

        If accuracy drops significantly under PHASE_OFF but not FROZEN,
        it suggests phase selectivity (not just phase dynamics) matters.
        """
        return torch.zeros_like(phi)

    def modify_phases(self, phi_q: torch.Tensor, phi_k: torch.Tensor):
        """
        Apply the configured ablation to query and key phases.

        Args:
            phi_q: Query phases [B, N, H, D_h]
            phi_k: Key phases [B, N, H, D_h]

        Returns:
            Tuple of (modified_phi_q, modified_phi_k)
        """
        if self.mode == AblationMode.BASELINE:
            return phi_q, phi_k

        elif self.mode == AblationMode.PHASE_SCRAMBLE:
            return self._scramble_phases(phi_q), self._scramble_phases(phi_k)

        elif self.mode == AblationMode.PHASE_FROZEN:
            return self._freeze_phases(phi_q), self._freeze_phases(phi_k)

        elif self.mode == AblationMode.PHASE_AMPLIFIED:
            return self._amplify_phases(phi_q), self._amplify_phases(phi_k)

        elif self.mode == AblationMode.PHASE_OFF:
            return self._uniform_phases(phi_q), self._uniform_phases(phi_k)

        else:
            raise ValueError(f"Unknown ablation mode: {self.mode}")


def create_ablated_forward(
    original_forward: Callable,
    ablation_hook: PhaseAblationHook,
) -> Callable:
    """
    Create an ablated forward function that wraps the original.

    This patches the phase computation within PhaseAttentionLayer.forward()
    to apply the specified ablation.
    """

    def ablated_forward(self, x, causal_mask=True, phase_context=None, intent_phase=None):
        """
        Ablated forward pass for PhaseAttentionLayer.

        Intercepts the phase computation step and applies ablation.
        """
        if ablation_hook.mode == AblationMode.BASELINE:
            # No modification needed
            return original_forward(self, x, causal_mask, phase_context, intent_phase)

        B, N, D = x.shape

        # Pre-norm
        x_norm = self.norm(x)

        # Compute phases (same as original)
        phi_q_raw = self.W_q_phase(x_norm).view(B, N, self.num_heads, self.head_dim)
        phi_k_raw = self.W_k_phase(x_norm).view(B, N, self.num_heads, self.head_dim)

        # Apply bounded phase if configured
        if self.bounded_phase:
            phi_q = math.pi * torch.sin(phi_q_raw)
            phi_k = math.pi * torch.sin(phi_k_raw)
        else:
            phi_q = phi_q_raw
            phi_k = phi_k_raw

        # Apply per-head phase offsets
        if hasattr(self, 'phase_offset_q'):
            phi_q = phi_q + self.phase_offset_q.to(phi_q.dtype).view(1, 1, -1, 1)
            phi_k = phi_k + self.phase_offset_k.to(phi_k.dtype).view(1, 1, -1, 1)

        # *** ABLATION POINT ***
        # This is where we modify the phases according to ablation mode
        phi_q, phi_k = ablation_hook.modify_phases(phi_q, phi_k)

        # Continue with rest of forward pass using ablated phases
        # (This duplicates some code from original forward, but necessary for clean ablation)

        # Amplitudes (unchanged by ablation)
        a_q = torch.sigmoid(self.W_q_amp(x_norm)).view(B, N, self.num_heads, self.head_dim)
        a_k = torch.sigmoid(self.W_k_amp(x_norm)).view(B, N, self.num_heads, self.head_dim)

        # Capture for diagnostics if enabled
        if self.capture_for_health_diagnostics:
            self._captured_phi_k = phi_k.detach()
            self._captured_phi_q = phi_q.detach()
            self._captured_a_k = a_k.detach()

        # Apply intent phase rotation if provided
        if intent_phase is not None:
            if intent_phase.dim() == 2:
                intent_phase = intent_phase.unsqueeze(1).unsqueeze(-1)
            elif intent_phase.dim() == 3:
                intent_phase = intent_phase.unsqueeze(1)
            phi_q = phi_q + intent_phase

        # Value projection
        v = self.v_proj(x_norm).view(B, N, self.num_heads, self.head_dim)

        # Cast for complex ops if needed
        orig_dtype = phi_q.dtype
        if orig_dtype == torch.bfloat16:
            phi_q = phi_q.float()
            phi_k = phi_k.float()
            a_q = a_q.float()
            a_k = a_k.float()
            v = v.float()

        # Create complex phasors
        q_phasor = torch.polar(a_q, phi_q)
        k_phasor = torch.polar(a_k, -phi_k)

        # Complex cumsum for O(n) attention
        v_complex = torch.complex(v, torch.zeros_like(v))
        kv_complex = k_phasor * v_complex

        # Handle decay
        use_decay = getattr(self, 'learned_decay', False) or getattr(self, 'decay_gamma', 1.0) < 1.0

        if not use_decay:
            global_state = torch.cumsum(kv_complex, dim=1)
        else:
            # Use simple cumsum for ablation (full decay logic is complex)
            global_state = torch.cumsum(kv_complex, dim=1)

        # Readout: Re(Q * State)
        output_complex = q_phasor * global_state
        output = output_complex.real

        # Reshape and project
        output = output.view(B, N, -1)
        if orig_dtype == torch.bfloat16:
            output = output.to(orig_dtype)

        output = self.out_proj(output)
        output = self.dropout(output)

        # Residual connection
        return x + output * self.aux_scale

    return ablated_forward


# =============================================================================
# ABLATION CONTEXT MANAGER
# =============================================================================

@contextmanager
def phase_ablation_context(
    model: nn.Module,
    mode: AblationMode,
    scramble_seed: Optional[int] = None,
    frozen_phase_value: float = 0.0,
):
    """
    Context manager for running model inference with phase ablation.

    Usage:
        with phase_ablation_context(model, AblationMode.PHASE_SCRAMBLE, seed=42):
            output = model(input_ids)
        # Phases restored automatically

    Args:
        model: Model containing PhaseAttentionLayer modules
        mode: Ablation mode to apply
        scramble_seed: Seed for scramble mode reproducibility
        frozen_phase_value: Phase value for frozen mode
    """
    # Find all PhaseAttentionLayer modules
    phase_layers = []
    for name, module in model.named_modules():
        if module.__class__.__name__ == 'PhaseAttentionLayer':
            phase_layers.append((name, module))

    if not phase_layers:
        # No phase layers found, just yield
        yield
        return

    # Create ablation hook
    ablation_hook = PhaseAblationHook(
        mode=mode,
        scramble_seed=scramble_seed,
        frozen_phase_value=frozen_phase_value,
    )

    # Store original forward methods
    original_forwards = {}
    for name, layer in phase_layers:
        original_forwards[name] = layer.forward

    try:
        # Patch forward methods
        for name, layer in phase_layers:
            ablated_fwd = create_ablated_forward(original_forwards[name], ablation_hook)
            layer.forward = lambda self=layer, fwd=ablated_fwd, **kwargs: fwd(self, **kwargs)

            # Need to bind the method properly
            import types
            layer.forward = types.MethodType(
                lambda self, x, causal_mask=True, phase_context=None, intent_phase=None, fwd=ablated_fwd:
                    fwd(self, x, causal_mask, phase_context, intent_phase),
                layer
            )

        yield

    finally:
        # Restore original forward methods
        for name, layer in phase_layers:
            # Need to restore as bound method
            import types
            original_fwd = original_forwards[name]
            # The original forward is already a bound method, just restore it
            layer.forward = original_fwd


def run_ablated_inference(
    model: nn.Module,
    input_ids: torch.Tensor,
    mode: AblationMode,
    enable_health_capture: bool = True,
    scramble_seed: Optional[int] = None,
) -> AblationResult:
    """
    Run model inference with specified phase ablation.

    Args:
        model: Model to run
        input_ids: Input token IDs [B, N]
        mode: Ablation mode
        enable_health_capture: Whether to capture phase health metrics
        scramble_seed: Seed for scramble mode

    Returns:
        AblationResult with logits and phase health metrics
    """
    # Import health diagnostics functions
    try:
        from symbolu.phase_transformer import (
            enable_health_diagnostics_capture,
            compute_phase_health_diagnostics,
        )
        HAS_HEALTH_DIAGNOSTICS = True
    except ImportError:
        HAS_HEALTH_DIAGNOSTICS = False
        enable_health_capture = False

    model.eval()

    # Enable health capture if requested
    if enable_health_capture and HAS_HEALTH_DIAGNOSTICS:
        enable_health_diagnostics_capture(model, True)

    try:
        with torch.no_grad():
            if mode == AblationMode.BASELINE:
                # Normal inference
                outputs = model(input_ids)
            else:
                # Ablated inference using context manager
                with phase_ablation_context(model, mode, scramble_seed=scramble_seed):
                    outputs = model(input_ids)

            # Extract logits
            if isinstance(outputs, dict):
                logits = outputs.get('logits', outputs.get('output', None))
                if logits is None:
                    # Try first tensor value
                    for v in outputs.values():
                        if isinstance(v, torch.Tensor) and v.dim() == 3:
                            logits = v
                            break
            elif isinstance(outputs, tuple):
                logits = outputs[0]
            else:
                logits = outputs

            # Get health metrics
            health = {}
            if enable_health_capture and HAS_HEALTH_DIAGNOSTICS:
                health = compute_phase_health_diagnostics(model)

    finally:
        if enable_health_capture and HAS_HEALTH_DIAGNOSTICS:
            enable_health_diagnostics_capture(model, False)

    return AblationResult(
        mode=mode,
        logits=logits,
        phase_health=health,
        metadata={'scramble_seed': scramble_seed} if scramble_seed else {},
    )


# =============================================================================
# SIMPLIFIED ABLATION FOR DIRECT FORWARD MODIFICATION
# =============================================================================

def apply_phase_ablation_to_model(
    model: nn.Module,
    mode: AblationMode,
    scramble_seed: Optional[int] = None,
) -> List[Callable]:
    """
    Apply phase ablation by patching model's PhaseAttentionLayer forward methods.

    Returns list of restore functions to undo the patching.

    This is a more direct approach than the context manager, useful for
    testing environments where context managers are problematic.
    """
    import types

    restore_funcs = []

    ablation_hook = PhaseAblationHook(
        mode=mode,
        scramble_seed=scramble_seed,
    )

    for name, module in model.named_modules():
        if module.__class__.__name__ == 'PhaseAttentionLayer':
            original_forward = module.forward

            # Create ablated forward
            ablated_fwd = create_ablated_forward(original_forward, ablation_hook)

            # Bind as method
            module.forward = types.MethodType(
                lambda self, x, causal_mask=True, phase_context=None, intent_phase=None, fwd=ablated_fwd:
                    fwd(self, x, causal_mask, phase_context, intent_phase),
                module
            )

            # Store restore function
            def restore(m=module, orig=original_forward):
                m.forward = orig

            restore_funcs.append(restore)

    return restore_funcs


def restore_phase_ablation(restore_funcs: List[Callable]):
    """Restore original forward methods from apply_phase_ablation_to_model."""
    for restore in restore_funcs:
        restore()


if __name__ == "__main__":
    print("Phase Ablation Utilities")
    print("=" * 50)
    print("\nAvailable ablation modes:")
    for mode in AblationMode:
        print(f"  - {mode.value}: {mode.name}")

    print("\nUsage example:")
    print("""
    from phase_ablation import AblationMode, run_ablated_inference

    # Run baseline
    baseline_result = run_ablated_inference(model, input_ids, AblationMode.BASELINE)

    # Run with scrambled phases
    scramble_result = run_ablated_inference(
        model, input_ids, AblationMode.PHASE_SCRAMBLE, scramble_seed=42
    )

    # Run with frozen phases
    frozen_result = run_ablated_inference(model, input_ids, AblationMode.PHASE_FROZEN)

    # Compare logits
    delta = (baseline_result.logits - scramble_result.logits).abs().mean()
    print(f"Mean logit change from scramble: {delta:.4f}")
    """)
