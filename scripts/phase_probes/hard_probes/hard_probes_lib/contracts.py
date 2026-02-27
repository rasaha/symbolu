"""
No-write contract enforcement and shape validation (V10.6.2).

Enforces that control signals (intent phases, alignment scores)
are low-dimensional and broadcastable, not token-wise embeddings.
This prevents control from injecting content into Phase.

CLI Usage::

    # Enable enforcement (default)
    python train_hard_probes.py --enforce-no-write-contracts

    # Disable for debugging
    python train_hard_probes.py --no-enforce-no-write-contracts

    # Warn instead of raise on violations
    python train_hard_probes.py --no-strict-control-contract
"""

import torch
import warnings
from typing import Tuple, Dict, Optional

# Global flag to enable/disable contract enforcement (for performance)
_ENFORCE_NO_WRITE_CONTRACTS = True


def set_no_write_contract_enforcement(enabled: bool):
    """Enable or disable no-write contract enforcement globally."""
    global _ENFORCE_NO_WRITE_CONTRACTS
    _ENFORCE_NO_WRITE_CONTRACTS = enabled


def assert_control_shape(
    tensor: "torch.Tensor",
    name: str,
    d_model: int = None,
    seq_len: int = None,
    strict: bool = True,
) -> bool:
    """
    Enforce no-write contract: control signals must not be token-wise embeddings.

    V10.6.2: Prevents control signals from injecting content into Phase.

    Args:
        tensor: The control signal tensor to validate
        name: Human-readable name for error messages
        d_model: Model dimension (if known) - tensor must not have this as last dim
        seq_len: Sequence length (if known) - tensor must not have this dimension
        strict: If True, raises AssertionError; if False, returns bool and warns

    Returns:
        True if valid, False if invalid (only when strict=False)

    Raises:
        AssertionError: If tensor violates no-write contract and strict=True

    Contract Rules:
        1. Must be low-dimensional (dim <= 4)
        2. Must NOT have d_model as last dimension (would be embeddings)
        3. Must NOT have sequence length dimension (would be token-wise)
        4. Should be broadcastable to [B, H, 1, 1]-like shapes

    Examples:
        Valid:   [B, H]          - per-head control
        Valid:   [B, H, 1]       - broadcastable per-head
        Valid:   [H]             - shared per-head
        Valid:   []              - scalar
        Invalid: [B, N, D]       - token-wise embeddings (N=seq_len, D=d_model)
        Invalid: [B, H, N, D]    - full attention tensor
    """
    global _ENFORCE_NO_WRITE_CONTRACTS

    if not _ENFORCE_NO_WRITE_CONTRACTS:
        return True

    if tensor is None:
        return True

    violations = []

    # Rule 1: Must be low-dimensional
    if tensor.dim() > 4:
        violations.append(
            f"dim={tensor.dim()} > 4 (must be low-dimensional)"
        )

    # Rule 2: Must NOT have d_model as last dimension
    if d_model is not None and tensor.dim() >= 1:
        if tensor.shape[-1] == d_model:
            violations.append(
                f"last dim={tensor.shape[-1]} equals d_model={d_model} "
                f"(would be embeddings, not control)"
            )

    # Rule 3: Must NOT have sequence length dimension
    if seq_len is not None and seq_len > 1:
        for i, dim_size in enumerate(tensor.shape):
            if dim_size == seq_len:
                violations.append(
                    f"dimension {i} has size={dim_size} equals seq_len={seq_len} "
                    f"(would be token-position dependent)"
                )

    # Rule 4: Check for suspicious large dimensions that might be token-wise
    # Heuristic: any dimension > 64 that's not batch is suspicious
    if tensor.dim() >= 2:
        for i, dim_size in enumerate(tensor.shape[1:], start=1):  # Skip batch dim
            if dim_size > 512:  # Likely d_model or seq_len
                violations.append(
                    f"dimension {i} has suspicious size={dim_size} > 512 "
                    f"(may be token-wise or embedding dimension)"
                )

    if violations:
        msg = (
            f"\n{'='*70}\n"
            f"NO-WRITE CONTRACT VIOLATION (V10.6.2)\n"
            f"{'='*70}\n"
            f"Control signal '{name}' violates Phase control contract:\n"
            f"  Shape: {list(tensor.shape)}\n"
            f"  Violations:\n"
        )
        for v in violations:
            msg += f"    - {v}\n"
        msg += (
            f"\nContract: Control signals must be low-dimensional and broadcastable,\n"
            f"          NOT token-wise embeddings that could inject content.\n"
            f"\nValid shapes: [B, H], [B, H, 1], [H], [] (scalar)\n"
            f"Invalid shapes: [B, N, D], [B, H, N, D] (token-wise)\n"
            f"{'='*70}"
        )

        if strict:
            raise AssertionError(msg)
        else:
            import warnings
            warnings.warn(msg, UserWarning)
            return False

    return True


def validate_intent_phase_shapes(
    theta_jepa: "torch.Tensor" = None,
    theta_srk: "torch.Tensor" = None,
    d_model: int = None,
    seq_len: int = None,
    context: str = "unknown",
):
    """
    Validate that intent phase signals comply with no-write contracts.

    V10.6.2: Specialized validator for JEPA/SRK intent phases.

    Note: In the current implementation, intent phases ARE [B, N, D] tensors
    because they need to be computed per-position for alignment scoring.
    This is a known architectural decision - the key protection is that
    they only affect SCALAR modulation (s_align), not direct content injection.

    This function documents the contract and can be extended later if we
    want to enforce stricter constraints (e.g., per-head rather than per-token).

    Args:
        theta_jepa: JEPA intent phase tensor (query intent)
        theta_srk: SRK intent phase tensor (memory intent)
        d_model: Model dimension
        seq_len: Sequence length
        context: Description of where this is called from

    V10.6.3 Update (ChatGPT feedback):
        The previous implementation computed s_align as [B, N] (token-position dependent),
        which VIOLATES the no-write contract. Even a scalar per position allows:
        - Alignment to suppress/amplify specific tokens
        - Structure to leak into Phase
        - Phase to become a soft attention map

        CORRECTED architecture:
        1. Intent phases are [B, N, D] - computed per-position for scoring
        2. s_align is REDUCED to [H] or [] (NOT [B, N]):
           - Option A (safest): s_align = cos(θ_diff).mean() → []
           - Option B (recommended): s_align = cos(θ_diff).mean(dim=(0,1,3)) → [H]
        3. This modulates via: output * (1 + α * s_align) where α << 1
        4. The modulation is MULTIPLICATIVE on existing content, not additive injection

        The key contract:
        > Control signals may be scalar or per-head, but must NEVER vary across token positions.
    """
    # V10.6.3: We now enforce that final s_align is NOT token-position dependent
    # The protection is in the REDUCTION of intent phases to [H] or [], not their input shape
    pass

