"""
Stochastic Gradient Persistence (SGP) — The "Cement" for Phoneme CSR
=====================================================================

╔═══════════════════════════════════════════════════════════════════════════════╗
║                     STOCHASTIC GRADIENT PERSISTENCE                            ║
║                                                                                ║
║  SGP transforms the deterministic Phoneme CSR "Blueprint" into permanent      ║
║  ontological structure by forcing gradients to persist in the Authority       ║
║  layers until the CSR constraints are physically "bent" into the weights.     ║
╚═══════════════════════════════════════════════════════════════════════════════╝

The Sovereign Interaction:
    ┌─────────────────────────────────────────────────────────────────────────┐
    │  COMPONENT          │  ROLE              │  INTERACTION                 │
    ├─────────────────────────────────────────────────────────────────────────┤
    │  Phoneme CSR        │  The Blueprint     │  Defines 12D "allowed" space │
    │  SGP                │  The Cement        │  Locks structure into weights│
    │  SattvicController  │  The Architect     │  Adjusts pressure based on   │
    │                     │                    │  loop detection (Variance)   │
    └─────────────────────────────────────────────────────────────────────────┘

Why SGP is Essential:
    1. Bridging the "Handshake" Gap:
       - Phoneme CSR is deterministic and non-trainable
       - Without SGP, Quadratic layers might treat CSR as "transient noise"
       - SGP forces gradients to persist, ensuring layers "bend" to CSR

    2. Acoustic Resonance vs. Statistical Noise:
       - Phonemes provide high-frequency signal (vibrational)
       - SGP acts as Low-Pass Filter, preserving "Acoustic Essence"

    3. Preventing "Ontological Drift":
       - During Sattvic Release, λ_csr decays from 0.5 → 0.1
       - SGP ensures "memory" of the 0.5 phase remains in weights

Key Dynamics:
    - When stagnation detected: SGP rate INCREASES (cement hardens)
    - During Sattvic Release: SGP rate can decrease (fluid learning)
    - The SGP Rate (20-25) serves as "Toroidal Refresh Rate"

Version: 1.0
Date: 2026-01-04
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any
from collections import deque

try:
    import torch
    import torch.nn as nn
    HAS_TORCH = True
except ImportError:
    HAS_TORCH = False


# =============================================================================
# CONFIGURATION
# =============================================================================

@dataclass
class SGPConfig:
    """Configuration for Stochastic Gradient Persistence."""

    # Base persistence rate (steps to accumulate gradients)
    base_rate: int = 20              # Default SGP rate

    # Rate bounds
    min_rate: int = 10               # Minimum rate (high-velocity learning)
    max_rate: int = 50               # Maximum rate (heavy cement during collapse)

    # Stagnation response
    stagnation_boost: float = 1.5    # Multiply rate when stagnation detected
    collapse_boost: float = 2.0      # Multiply rate during mode collapse

    # Decay settings
    decay_enabled: bool = True       # Allow rate to decay during Sattvic Release
    decay_factor: float = 0.9        # Rate multiplier per decay step

    # Gradient momentum
    momentum: float = 0.9            # EMA factor for gradient persistence
    momentum_floor: float = 0.7      # Minimum momentum during release

    # Layer-specific persistence
    authority_multiplier: float = 1.5  # Extra persistence for Authority layers (0-5)
    sensory_multiplier: float = 1.0    # Normal persistence for Sensory layers (6-11)

    # Integration with CSR
    csr_gradient_weight: float = 1.0   # Weight for CSR-derived gradients


# =============================================================================
# SGP GRADIENT BUFFER
# =============================================================================

if HAS_TORCH:
    class SGPGradientBuffer:
        """
        Gradient persistence buffer that maintains "memory" of CSR constraints.

        This implements the "cement" metaphor by accumulating gradients over
        multiple steps, forcing the model to internalize the phonetic structure.
        """

        def __init__(self, config: SGPConfig):
            self.config = config
            self.buffers: Dict[str, torch.Tensor] = {}
            self.step_counts: Dict[str, int] = {}
            self.momentum_state: Dict[str, torch.Tensor] = {}

        def accumulate(
            self,
            name: str,
            gradient: torch.Tensor,
            layer_idx: Optional[int] = None,
            current_rate: Optional[int] = None,
        ) -> torch.Tensor:
            """
            Accumulate gradient with persistence.

            Args:
                name: Parameter name
                gradient: Current gradient tensor
                layer_idx: Layer index (0-11) for layer-specific persistence
                current_rate: Override rate from controller

            Returns:
                Persisted gradient (accumulated + momentum)
            """
            rate = current_rate or self.config.base_rate

            # Apply layer-specific multiplier
            if layer_idx is not None:
                if layer_idx < 6:  # Authority layers
                    rate = int(rate * self.config.authority_multiplier)
                else:  # Sensory layers
                    rate = int(rate * self.config.sensory_multiplier)

            # Clamp rate
            rate = max(self.config.min_rate, min(self.config.max_rate, rate))

            # Initialize buffers if needed
            if name not in self.buffers:
                self.buffers[name] = torch.zeros_like(gradient)
                self.step_counts[name] = 0
                self.momentum_state[name] = torch.zeros_like(gradient)

            # Accumulate gradient
            self.buffers[name] += gradient
            self.step_counts[name] += 1

            # Apply momentum (EMA)
            momentum = self.config.momentum
            self.momentum_state[name] = (
                momentum * self.momentum_state[name] +
                (1 - momentum) * gradient
            )

            # Check if we should emit persisted gradient
            if self.step_counts[name] >= rate:
                # Combine accumulated buffer with momentum
                persisted = self.buffers[name] / rate + self.momentum_state[name]

                # Reset buffer
                self.buffers[name].zero_()
                self.step_counts[name] = 0

                return persisted
            else:
                # Return momentum-weighted current gradient
                return self.momentum_state[name]

        def get_persistence_status(self, name: str) -> Dict[str, Any]:
            """Get status of gradient buffer for a parameter."""
            if name not in self.buffers:
                return {"accumulated": 0, "steps": 0, "rate": self.config.base_rate}

            return {
                "accumulated": self.buffers[name].norm().item(),
                "steps": self.step_counts[name],
                "rate": self.config.base_rate,
                "momentum_norm": self.momentum_state[name].norm().item(),
            }

        def clear(self):
            """Clear all buffers."""
            self.buffers.clear()
            self.step_counts.clear()
            self.momentum_state.clear()


# =============================================================================
# SGP CONTROLLER
# =============================================================================

class SGPController:
    """
    Stochastic Gradient Persistence Controller.

    Manages the SGP rate based on training state and SattvicController signals.
    Implements the "cement" that hardens when the "blueprint" (CSR) detects failure.

    The SGP rate determines how long gradients persist before being applied,
    forcing the model to internalize structural constraints.

    Integration with SattvicController:
        - Stagnation detected → SGP rate INCREASES (cement hardens)
        - Mode collapse → SGP rate MAXIMIZES (emergency intervention)
        - Sattvic Release → SGP rate can DECREASE (fluid learning)
    """

    def __init__(self, config: Optional[SGPConfig] = None):
        self.config = config or SGPConfig()

        # Current state
        self.current_rate = self.config.base_rate
        self.current_momentum = self.config.momentum
        self.current_step = 0

        # External controller reference
        self._sattvic_controller = None

        # History tracking
        self.rate_history: List[Dict[str, Any]] = []
        self.boost_active = False
        self.boost_reason: Optional[str] = None

        # Gradient buffer (if torch available)
        if HAS_TORCH:
            self.gradient_buffer = SGPGradientBuffer(self.config)
        else:
            self.gradient_buffer = None

    def attach_sattvic_controller(self, controller):
        """Attach SattvicController for synchronized updates."""
        self._sattvic_controller = controller

    def update(
        self,
        step: int,
        entropy: Optional[float] = None,
        variance: Optional[float] = None,
        knowledge: Optional[float] = None,
    ) -> int:
        """
        Update SGP rate based on current training state.

        Can be called directly with metrics or will pull from attached
        SattvicController if available.

        Args:
            step: Current training step
            entropy: Current entropy (optional if controller attached)
            variance: Entropy variance (optional if controller attached)
            knowledge: Knowledge score (optional if controller attached)

        Returns:
            Updated SGP rate
        """
        self.current_step = step

        # Pull from SattvicController if attached
        if self._sattvic_controller is not None:
            status = self._sattvic_controller.get_status()
            stagnation = status.get('stagnation_detected', False)
            collapse = status.get('mode_collapse_detected', False)
            boost_active = status.get('boost_active', False)
            current_lambda = status.get('lambda_csr', 0.5)
        else:
            # Infer from provided metrics
            stagnation = variance is not None and variance < 0.001
            collapse = entropy is not None and entropy < 0.4
            boost_active = stagnation or collapse
            current_lambda = 0.5  # Default

        # Compute rate based on state
        if collapse:
            # Mode collapse: Maximum cement
            self.current_rate = int(self.config.base_rate * self.config.collapse_boost)
            self.boost_active = True
            self.boost_reason = "MODE_COLLAPSE"
            print(f"  🧱 [SGP] Mode collapse: Rate increased to {self.current_rate}")

        elif stagnation:
            # Stagnation: Heavy cement
            self.current_rate = int(self.config.base_rate * self.config.stagnation_boost)
            self.boost_active = True
            self.boost_reason = "STAGNATION"
            print(f"  🧱 [SGP] Stagnation: Rate increased to {self.current_rate}")

        elif self.config.decay_enabled and not boost_active:
            # Sattvic Release: Can reduce rate based on lambda
            if current_lambda < 0.3:
                # Low guidance = allow faster learning
                self.current_rate = int(self.config.base_rate * 0.7)
                self.current_momentum = max(
                    self.config.momentum_floor,
                    self.config.momentum * 0.9
                )
            else:
                # Normal operation
                self.current_rate = self.config.base_rate
                self.current_momentum = self.config.momentum

            self.boost_active = False
            self.boost_reason = None

        else:
            # Default
            self.current_rate = self.config.base_rate
            self.boost_active = False
            self.boost_reason = None

        # Clamp rate
        self.current_rate = max(
            self.config.min_rate,
            min(self.config.max_rate, self.current_rate)
        )

        # Update gradient buffer momentum if available
        if self.gradient_buffer is not None:
            self.gradient_buffer.config.momentum = self.current_momentum

        # Record history
        self.rate_history.append({
            "step": step,
            "rate": self.current_rate,
            "momentum": self.current_momentum,
            "boost_active": self.boost_active,
            "boost_reason": self.boost_reason,
        })

        return self.current_rate

    def get_effective_rate(self, layer_idx: Optional[int] = None) -> int:
        """
        Get effective SGP rate for a specific layer.

        Authority layers (0-5) get higher persistence to lock structure.
        Sensory layers (6-11) get normal persistence.
        """
        rate = self.current_rate

        if layer_idx is not None:
            if layer_idx < 6:  # Authority layers
                rate = int(rate * self.config.authority_multiplier)
            else:  # Sensory layers
                rate = int(rate * self.config.sensory_multiplier)

        return max(self.config.min_rate, min(self.config.max_rate, rate))

    def get_status(self) -> Dict[str, Any]:
        """Get current SGP status."""
        return {
            "step": self.current_step,
            "rate": self.current_rate,
            "momentum": self.current_momentum,
            "boost_active": self.boost_active,
            "boost_reason": self.boost_reason,
            "authority_rate": self.get_effective_rate(0),
            "sensory_rate": self.get_effective_rate(6),
            "sattvic_attached": self._sattvic_controller is not None,
        }

    def print_status(self):
        """Print current SGP status."""
        status = self.get_status()
        print(f"\n  ╔══════════════════════════════════════════════════╗")
        print(f"  ║           SGP CONTROLLER STATUS                  ║")
        print(f"  ╠══════════════════════════════════════════════════╣")
        print(f"  ║  Step:           {status['step']:>20}         ║")
        print(f"  ║  Base Rate:      {status['rate']:>20}         ║")
        print(f"  ║  Authority Rate: {status['authority_rate']:>20}         ║")
        print(f"  ║  Sensory Rate:   {status['sensory_rate']:>20}         ║")
        print(f"  ║  Momentum:       {status['momentum']:>20.3f}         ║")
        print(f"  ║  Boost Active:   {'YES' if status['boost_active'] else 'NO':>20}         ║")
        print(f"  ║  Boost Reason:   {status['boost_reason'] or 'NONE':>20}         ║")
        print(f"  ╚══════════════════════════════════════════════════╝")

    def should_apply_gradients(self, accumulated_steps: int) -> bool:
        """Check if gradients should be applied (persistence threshold met)."""
        return accumulated_steps >= self.current_rate


# =============================================================================
# FACTORY FUNCTIONS
# =============================================================================

def create_sgp_controller(
    base_rate: int = 20,
    stagnation_boost: float = 1.5,
    collapse_boost: float = 2.0,
    momentum: float = 0.9,
) -> SGPController:
    """
    Create an SGP Controller with custom settings.

    Args:
        base_rate: Default SGP rate (steps before gradient application)
        stagnation_boost: Rate multiplier during stagnation
        collapse_boost: Rate multiplier during mode collapse
        momentum: Gradient momentum factor

    Returns:
        Configured SGPController
    """
    config = SGPConfig(
        base_rate=base_rate,
        stagnation_boost=stagnation_boost,
        collapse_boost=collapse_boost,
        momentum=momentum,
    )
    return SGPController(config)


def create_synchronized_controllers(
    sattvic_config=None,
    sgp_config=None,
):
    """
    Create synchronized SattvicController and SGPController.

    This is the recommended way to set up the "Sovereign Handshake" where:
        - SattvicController manages λ_csr (the Blueprint pressure)
        - SGPController manages gradient persistence (the Cement)

    Returns:
        Tuple of (SattvicController, SGPController)
    """
    from symbolu.resonance.controller import SattvicController, SattvicConfig

    # Create controllers
    sattvic = SattvicController(sattvic_config or SattvicConfig())
    sgp = SGPController(sgp_config or SGPConfig())

    # Synchronize
    sgp.attach_sattvic_controller(sattvic)

    return sattvic, sgp


# =============================================================================
# TRAINING INTEGRATION HELPER
# =============================================================================

def apply_sgp_to_optimizer(
    optimizer,
    sgp_controller: SGPController,
    step: int,
    entropy: float,
    knowledge: float,
) -> bool:
    """
    Apply SGP logic to optimizer step.

    This should be called in the training loop to determine whether
    to apply gradients based on SGP persistence rate.

    Args:
        optimizer: PyTorch optimizer
        sgp_controller: SGP controller instance
        step: Current training step
        entropy: Current entropy metric
        knowledge: Current knowledge metric

    Returns:
        True if gradients were applied, False if still accumulating
    """
    # Update SGP rate
    sgp_controller.update(step, entropy=entropy, knowledge=knowledge)

    # Check if we should apply gradients
    accumulated = step % sgp_controller.current_rate
    if accumulated == 0:
        optimizer.step()
        optimizer.zero_grad()
        return True
    else:
        return False


# =============================================================================
# PUBLIC EXPORTS
# =============================================================================

__all__ = [
    # Configuration
    "SGPConfig",
    # Main controller
    "SGPController",
    "create_sgp_controller",
    # Integration
    "create_synchronized_controllers",
    "apply_sgp_to_optimizer",
]

if HAS_TORCH:
    __all__.append("SGPGradientBuffer")


# =============================================================================
# TESTING
# =============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("  SGP CONTROLLER TEST")
    print("=" * 60)

    # Create synchronized controllers
    from symbolu.resonance.controller import SattvicController

    sattvic = SattvicController()
    sgp = SGPController()
    sgp.attach_sattvic_controller(sattvic)

    print("\n  Controllers synchronized.")

    # Simulate training
    print("\n  Simulating training with SGP...")
    print(f"\n  {'Step':<8} {'Entropy':<10} {'SGP Rate':<10} {'Sattvic λ':<12} {'Event'}")
    print(f"  {'-'*55}")

    for step in range(0, 2001, 100):
        # Simulate metrics
        if 1400 <= step <= 1600:
            entropy = 0.35  # Mode collapse
        else:
            entropy = 0.55

        knowledge = min(0.8, step / 2500)

        # Update controllers
        lambda_csr = sattvic.update(step, {'ent': entropy, 'know': knowledge})
        sgp_rate = sgp.update(step)

        # Determine event
        event = ""
        if sgp.boost_active:
            event = f"🧱 {sgp.boost_reason}"

        print(f"  {step:<8} {entropy:<10.2f} {sgp_rate:<10} {lambda_csr:<12.3f} {event}")

    print("\n" + "=" * 60)
    sgp.print_status()
    print("=" * 60)
