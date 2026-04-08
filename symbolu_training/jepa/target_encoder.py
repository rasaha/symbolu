"""
Target Encoder with Exponential Moving Average (EMA) for the Ontological State Predictor.

The Target Encoder provides slowly-moving targets for the predictor,
preventing representation collapse without requiring negative samples.

Inspired by the EMA target encoder from JEPA (LeCun, 2022) and
BYOL (Grill et al., 2020), adapted for 32D Sovereign State prediction.

References:
    - HYBRID_PHASE_JEPA_DESIGN.md §3.3
"""

import copy
import torch
import torch.nn as nn
from typing import Optional, Callable


class TargetEncoder(nn.Module):
    """
    EMA-updated copy of the context encoder.

    The target encoder's weights are updated via exponential moving average
    of the context encoder's weights. This provides stable targets that
    change slowly, preventing the model from collapsing to trivial solutions.

    θ_target ← α × θ_target + (1 - α) × θ_context

    Where α (momentum) is typically 0.996-0.999.

    Args:
        context_encoder: The context encoder to copy and track
        momentum: EMA momentum (higher = slower updates)
        momentum_schedule: Optional callable(step) -> momentum for scheduling
    """

    def __init__(
        self,
        context_encoder: nn.Module,
        momentum: float = 0.996,
        momentum_schedule: Optional[Callable[[int], float]] = None,
    ):
        super().__init__()

        # Deep copy the context encoder
        self.encoder = copy.deepcopy(context_encoder)

        # Freeze target encoder - no gradients
        for param in self.encoder.parameters():
            param.requires_grad = False

        self.base_momentum = momentum
        self.momentum = momentum
        self.momentum_schedule = momentum_schedule
        self.update_count = 0

    @torch.no_grad()
    def update(self, context_encoder: nn.Module, step: Optional[int] = None):
        """
        Update target encoder weights via EMA.

        Args:
            context_encoder: Current context encoder
            step: Optional step number for momentum scheduling
        """
        # Update momentum if schedule provided
        if self.momentum_schedule is not None and step is not None:
            self.momentum = self.momentum_schedule(step)
        else:
            self.momentum = self.base_momentum

        # EMA update: θ_target ← α × θ_target + (1 - α) × θ_context
        for target_param, context_param in zip(
            self.encoder.parameters(),
            context_encoder.parameters()
        ):
            target_param.data.mul_(self.momentum).add_(
                context_param.data, alpha=(1 - self.momentum)
            )

        self.update_count += 1

    @torch.no_grad()
    def forward(self, x: torch.Tensor, **kwargs) -> torch.Tensor:
        """
        Forward pass through target encoder.

        Note: This is wrapped in no_grad since target encoder
        should never receive gradients.

        Args:
            x: Input tensor
            **kwargs: Additional arguments passed to encoder

        Returns:
            Encoded representation
        """
        return self.encoder(x, **kwargs)

    def get_momentum(self) -> float:
        """Get current momentum value."""
        return self.momentum

    def get_update_count(self) -> int:
        """Get number of EMA updates performed."""
        return self.update_count

    def copy_weights_from(self, context_encoder: nn.Module):
        """
        Hard copy weights from context encoder (for initialization).

        Use this at the start of training to ensure target and context
        start with identical weights.
        """
        with torch.no_grad():
            for target_param, context_param in zip(
                self.encoder.parameters(),
                context_encoder.parameters()
            ):
                target_param.data.copy_(context_param.data)


def cosine_momentum_schedule(
    base_momentum: float = 0.996,
    final_momentum: float = 1.0,
    total_steps: int = 100000,
) -> Callable[[int], float]:
    """
    Cosine schedule for EMA momentum.

    Momentum increases from base_momentum to final_momentum following
    a cosine curve. Higher momentum at later stages means the target
    encoder changes more slowly as training progresses.

    Args:
        base_momentum: Starting momentum
        final_momentum: Final momentum
        total_steps: Total training steps

    Returns:
        Callable that takes step number and returns momentum
    """
    import math

    def schedule(step: int) -> float:
        if step >= total_steps:
            return final_momentum
        # Cosine increase from base to final
        progress = step / total_steps
        return final_momentum - (final_momentum - base_momentum) * (
            1 + math.cos(math.pi * progress)
        ) / 2

    return schedule


def linear_momentum_schedule(
    base_momentum: float = 0.996,
    final_momentum: float = 0.999,
    warmup_steps: int = 10000,
) -> Callable[[int], float]:
    """
    Linear warmup schedule for EMA momentum.

    Momentum increases linearly from base to final over warmup_steps,
    then stays constant.

    Args:
        base_momentum: Starting momentum
        final_momentum: Final momentum after warmup
        warmup_steps: Steps over which to increase momentum

    Returns:
        Callable that takes step number and returns momentum
    """
    def schedule(step: int) -> float:
        if step >= warmup_steps:
            return final_momentum
        # Linear increase
        progress = step / warmup_steps
        return base_momentum + (final_momentum - base_momentum) * progress

    return schedule


class TargetEncoderWrapper(nn.Module):
    """
    Wrapper that manages both context and target encoders together.

    Provides a clean interface for ontological state prediction training
    with automatic EMA updates.

    Args:
        encoder_class: Class to instantiate for context encoder
        encoder_kwargs: Kwargs for encoder instantiation
        momentum: EMA momentum
        momentum_schedule: Optional momentum schedule
    """

    def __init__(
        self,
        encoder_class: type,
        encoder_kwargs: dict,
        momentum: float = 0.996,
        momentum_schedule: Optional[Callable[[int], float]] = None,
    ):
        super().__init__()

        # Context encoder (trainable)
        self.context_encoder = encoder_class(**encoder_kwargs)

        # Target encoder (EMA, frozen)
        self.target_encoder = TargetEncoder(
            self.context_encoder,
            momentum=momentum,
            momentum_schedule=momentum_schedule,
        )

    def encode_context(self, x: torch.Tensor, **kwargs) -> torch.Tensor:
        """Encode with context encoder (receives gradients)."""
        return self.context_encoder(x, **kwargs)

    def encode_target(self, x: torch.Tensor, **kwargs) -> torch.Tensor:
        """Encode with target encoder (no gradients)."""
        return self.target_encoder(x, **kwargs)

    def update_target(self, step: Optional[int] = None):
        """Update target encoder via EMA."""
        self.target_encoder.update(self.context_encoder, step)

    def forward(
        self,
        context_input: torch.Tensor,
        target_input: torch.Tensor,
        **kwargs
    ):
        """
        Forward pass through both encoders.

        Args:
            context_input: Input for context encoder
            target_input: Input for target encoder

        Returns:
            Tuple of (context_encoding, target_encoding)
        """
        context_enc = self.encode_context(context_input, **kwargs)

        with torch.no_grad():
            target_enc = self.encode_target(target_input, **kwargs)

        return context_enc, target_enc
