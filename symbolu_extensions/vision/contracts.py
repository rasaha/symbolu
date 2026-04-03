"""
No-Write Contract enforcement for Phase-Quad Image Generator.

The no-write contract ensures Phase remains a continuous integrator that
cannot be hijacked by content injection. Control signals modulate computation
but never write token-specific embeddings.

Allowed control signal shapes (broadcastable, low-dimensional):
- [] - scalar
- [H] - per-head
- [B, H] - per-batch per-head
- [B, H, 1] - per-batch per-head with broadcast dim

Forbidden shapes:
- [B, N, D] - token-position-specific content
- [B, N] - token-position-specific scalars
- Any shape that varies by token position
"""

from typing import Optional

import torch
from torch import Tensor


class ContractViolationError(Exception):
    """
    Raised when a control signal violates the no-write contract.

    The no-write contract ensures that control signals cannot inject
    token-position-specific content into the Phase integrator. This
    maintains Phase as a continuous accumulator rather than a content
    injection point.
    """
    pass


def assert_control_shape(
    control: Optional[Tensor],
    name: str,
    num_heads: int,
    batch_size: Optional[int] = None,
) -> None:
    """
    Validate control signal adheres to no-write contract.

    This function enforces that control signals are low-dimensional
    and broadcastable, preventing token-position-specific content
    injection into the Phase integrator.

    Args:
        control: The control tensor to validate. If None, validation passes.
        name: Name of the control signal for error messages.
        num_heads: Number of attention heads H.
        batch_size: Optional batch size B for additional validation.

    Raises:
        ContractViolationError: If control shape is token-position-specific
            or otherwise violates the no-write contract.

    Examples:
        Valid shapes:
        - [] (scalar)
        - [12] (per-head with H=12)
        - [8, 12] (per-batch per-head with B=8, H=12)
        - [8, 12, 1] (per-batch per-head with broadcast dim)

        Invalid shapes:
        - [8, 256, 768] (token-position-specific content)
        - [8, 256] (token-position-specific scalars)
        - [256] (position-specific, could be confused with per-head)
    """
    if control is None:
        return

    if not isinstance(control, Tensor):
        raise ContractViolationError(
            f"{name} must be a Tensor or None, got {type(control).__name__}"
        )

    shape = control.shape
    ndim = len(shape)

    # Allowed: [] (scalar)
    if ndim == 0:
        return

    # Allowed: [H] (per-head)
    if ndim == 1:
        if shape[0] == num_heads:
            return
        raise ContractViolationError(
            f"{name} has shape {list(shape)}, which violates no-write contract. "
            f"For 1D tensor, expected per-head shape [{num_heads}], "
            f"but got [{shape[0]}]. "
            f"Token-position-specific scalars like [N] are forbidden."
        )

    # Allowed: [B, H] (per-batch per-head)
    if ndim == 2:
        if shape[1] == num_heads:
            if batch_size is not None and shape[0] != batch_size:
                raise ContractViolationError(
                    f"{name} has shape {list(shape)}, but batch size is {batch_size}. "
                    f"Expected shape [{batch_size}, {num_heads}]."
                )
            return
        raise ContractViolationError(
            f"{name} has shape {list(shape)}, which violates no-write contract. "
            f"For 2D tensor, expected per-batch per-head shape [B, {num_heads}], "
            f"but got shape with dim[1]={shape[1]}. "
            f"Shapes like [B, N] are forbidden as they are token-position-specific."
        )

    # Allowed: [B, H, 1] (per-batch per-head with broadcast dim)
    if ndim == 3:
        if shape[1] == num_heads and shape[2] == 1:
            if batch_size is not None and shape[0] != batch_size:
                raise ContractViolationError(
                    f"{name} has shape {list(shape)}, but batch size is {batch_size}. "
                    f"Expected shape [{batch_size}, {num_heads}, 1]."
                )
            return
        raise ContractViolationError(
            f"{name} has shape {list(shape)}, which violates no-write contract. "
            f"For 3D tensor, expected per-batch per-head with broadcast dim "
            f"[B, {num_heads}, 1], but got shape with dim[1]={shape[1]}, dim[2]={shape[2]}. "
            f"Shapes like [B, N, D] are forbidden as they are token-position-specific."
        )

    # Any other dimensionality is forbidden
    raise ContractViolationError(
        f"{name} has shape {list(shape)} with {ndim} dimensions, "
        f"which violates no-write contract. "
        f"Expected [], [{num_heads}], [B, {num_heads}], or [B, {num_heads}, 1]. "
        f"Higher-dimensional shapes are forbidden as they may be token-position-specific."
    )


def validate_control_batch(
    controls: dict,
    num_heads: int,
    batch_size: Optional[int] = None,
) -> None:
    """
    Validate multiple control signals at once.

    Args:
        controls: Dictionary mapping control names to tensors.
        num_heads: Number of attention heads.
        batch_size: Optional batch size for validation.

    Raises:
        ContractViolationError: If any control violates the contract.
    """
    for name, control in controls.items():
        assert_control_shape(control, name, num_heads, batch_size)


def is_valid_control_shape(
    control: Optional[Tensor],
    num_heads: int,
) -> bool:
    """
    Check if a control signal has a valid shape without raising.

    Args:
        control: The control tensor to check.
        num_heads: Number of attention heads.

    Returns:
        True if the shape is valid, False otherwise.
    """
    try:
        assert_control_shape(control, "control", num_heads)
        return True
    except ContractViolationError:
        return False
