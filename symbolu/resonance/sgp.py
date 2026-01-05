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
    - When stagnation detected: SGP rate HALVES (25→12) for MORE FREQUENT hammering
    - This increases the frequency of the "Ontological Hammer," forcing
      the model to break the repetition basin faster
    - The SGP Rate (25 default) serves as "Toroidal Refresh Rate"
    - Persistence buffer stores running average of gradients with gamma coefficient

Version: 2.0
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

    # Base persistence rate (steps between gradient pulses)
    base_rate: int = 25              # Default SGP rate (Toroidal Refresh Rate)

    # Stagnation rate (HALVED for MORE FREQUENT hammering)
    stagnation_rate: int = 12        # Rate when stagnation detected (25→12)

    # Rate bounds
    min_rate: int = 8                # Minimum rate (very high-velocity)
    max_rate: int = 50               # Maximum rate (slow cement)

    # Persistence buffer coefficient
    gamma: float = 0.3               # Coefficient for persisted gradients: θ ← θ - η(∇θ + γ∇θ_persisted)

    # Gradient momentum
    momentum: float = 0.9            # EMA factor for gradient persistence
    momentum_floor: float = 0.7      # Minimum momentum during release

    # Layer-specific persistence (Authority = 0-8, Sensory = 9-11)
    authority_layers: tuple = (0, 1, 2, 3, 4, 5, 6, 7, 8)  # Authority layers get special treatment
    sensory_layers: tuple = (9, 10, 11)                     # Sensory layers
    authority_multiplier: float = 1.2  # Extra persistence for Authority layers (0-8)
    sensory_multiplier: float = 1.0    # Normal persistence for Sensory layers (9-11)

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
                if layer_idx in self.config.authority_layers:  # Authority layers (0-8)
                    rate = int(rate * self.config.authority_multiplier)
                else:  # Sensory layers (9-11)
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
    Implements the "cement" that locks the phonetic "blueprint" (CSR) into weights.

    The SGP rate determines how frequently gradient pulses are applied,
    forcing the model to internalize structural constraints.

    Integration with SattvicController:
        - Stagnation detected → SGP rate HALVES (25→12) for MORE FREQUENT hammering
        - Mode collapse → SGP rate HALVES (forces faster intervention)
        - Normal operation → SGP rate = 25 (standard Toroidal Refresh Rate)

    Persistence Buffer:
        - Stores running average of gradients for Authority Layers (0-8)
        - Formula: θ ← θ - η(∇θ + γ∇θ_persisted)
        - γ (gamma) = coefficient for persisted gradient contribution
    """

    def __init__(self, config: Optional[SGPConfig] = None):
        self.config = config or SGPConfig()

        # Current state
        self.current_rate = self.config.base_rate  # 25 default
        self.current_momentum = self.config.momentum
        self.step_count = 0

        # External controller reference
        self._sattvic_controller = None

        # Persistence buffer for Authority Layers (0-8)
        # Maps parameter -> running average of gradients
        self.persistence_buffer: Dict[Any, Any] = {}  # param -> tensor
        self.authority_params: List[Any] = []  # List of tracked authority parameters
        self.gamma = self.config.gamma  # Persistence coefficient

        # History tracking
        self.rate_history: List[Dict[str, Any]] = []
        self.stagnation_active = False
        self.last_pulse_step = 0

        # Gradient buffer (if torch available)
        if HAS_TORCH:
            self.gradient_buffer = SGPGradientBuffer(self.config)
        else:
            self.gradient_buffer = None

    def attach_sattvic_controller(self, controller):
        """Attach SattvicController for synchronized updates."""
        self._sattvic_controller = controller

    def register_authority_params(self, params: List[Any]):
        """
        Register parameters from Authority Layers (0-8) for gradient persistence.

        These parameters will have their gradients persisted and injected
        during SGP pulses.

        Args:
            params: List of torch parameters from layers 0-8
        """
        self.authority_params = list(params)
        if HAS_TORCH:
            import torch
            for p in self.authority_params:
                if p not in self.persistence_buffer:
                    self.persistence_buffer[p] = torch.zeros_like(p.data)

    def update_persistence_buffer(self):
        """
        Update the persistence buffer with current gradients.

        Called every step to maintain running average of gradients
        for Authority layers.
        """
        if not HAS_TORCH or not self.authority_params:
            return

        for p in self.authority_params:
            if p.grad is not None:
                # Running average with momentum
                self.persistence_buffer[p] = (
                    self.config.momentum * self.persistence_buffer[p] +
                    (1 - self.config.momentum) * p.grad.data.clone()
                )

    def sgp_metabolic_step(self, metrics: Optional[Dict[str, float]] = None) -> bool:
        """
        Perform SGP metabolic step with dynamic rate based on Sattvic Controller.

        This is the main training loop integration point. Call this every step.

        The metabolic step:
            1. Determines dynamic rate (12 if stagnation, else 25)
            2. Checks for persistence pulse (step_count % rate == 0)
            3. Injects persisted gradients into Authority layers
            4. Synchronizes Toroidal Bridge

        Args:
            metrics: Optional dict with 'entropy', 'variance', 'knowledge'

        Returns:
            True if a persistence pulse was applied, False otherwise
        """
        self.step_count += 1

        # 1. Determine Dynamic Rate based on Sattvic Controller
        if self._sattvic_controller is not None:
            status = self._sattvic_controller.get_status()
            stagnation = status.get('stagnation_detected', False)
            collapse = status.get('mode_collapse_detected', False)
        else:
            # Infer from provided metrics
            if metrics:
                variance = metrics.get('variance', 1.0)
                entropy = metrics.get('entropy', 1.0)
                stagnation = variance < 0.001
                collapse = entropy < 0.4
            else:
                stagnation = False
                collapse = False

        # Stagnation or collapse: HALVE rate for MORE FREQUENT hammering
        if stagnation or collapse:
            self.current_rate = self.config.stagnation_rate  # 12
            self.stagnation_active = True
            if collapse:
                print(f"  🔨 [SGP] Mode collapse → Rate halved to {self.current_rate} (FREQUENT HAMMERING)")
            elif stagnation:
                print(f"  🔨 [SGP] Stagnation → Rate halved to {self.current_rate} (FREQUENT HAMMERING)")
        else:
            self.current_rate = self.config.base_rate  # 25
            self.stagnation_active = False

        # Update persistence buffer every step
        self.update_persistence_buffer()

        # 2. Check for Persistence Pulse
        if self.step_count % self.current_rate == 0:
            # 3. Inject Persisted Gradients into Authority Layers (0-8)
            if HAS_TORCH and self.authority_params:
                for p in self.authority_params:
                    if p.grad is not None and p in self.persistence_buffer:
                        # θ ← θ - η(∇θ + γ∇θ_persisted)
                        # We add γ * persisted gradient to current gradient
                        p.grad.data.add_(self.persistence_buffer[p], alpha=self.gamma)

            # 4. Synchronize Toroidal Bridge
            self.toroidal_sync()

            self.last_pulse_step = self.step_count

            # Record history
            self.rate_history.append({
                "step": self.step_count,
                "rate": self.current_rate,
                "pulse": True,
                "stagnation_active": self.stagnation_active,
            })

            return True  # Pulse applied

        return False  # No pulse this step

    def toroidal_sync(self):
        """
        Synchronize the Toroidal Bridge between Authority and Sensory layers.

        Called every SGP pulse to ensure coherent information flow between
        the structural (Authority: 0-8) and perceptual (Sensory: 9-11) layers.

        This maintains the "circular flow" of the toroidal architecture.
        """
        if self._sattvic_controller is not None:
            # Get current CSR state from Sattvic Controller
            status = self._sattvic_controller.get_status()
            lambda_csr = status.get('lambda_csr', 0.5)

            # Log sync event
            print(f"  🔄 [SGP] Toroidal sync at step {self.step_count} (λ={lambda_csr:.3f})")

    def update(
        self,
        step: int,
        entropy: Optional[float] = None,
        variance: Optional[float] = None,
        knowledge: Optional[float] = None,
    ) -> int:
        """
        Legacy update method for backwards compatibility.

        Prefer using sgp_metabolic_step() for new code.

        Args:
            step: Current training step
            entropy: Current entropy
            variance: Entropy variance
            knowledge: Knowledge score

        Returns:
            Updated SGP rate
        """
        self.step_count = step

        # Pull from SattvicController if attached
        if self._sattvic_controller is not None:
            status = self._sattvic_controller.get_status()
            stagnation = status.get('stagnation_detected', False)
            collapse = status.get('mode_collapse_detected', False)
        else:
            # Infer from provided metrics
            stagnation = variance is not None and variance < 0.001
            collapse = entropy is not None and entropy < 0.4

        # Stagnation or collapse: HALVE rate for MORE FREQUENT hammering
        if stagnation or collapse:
            self.current_rate = self.config.stagnation_rate  # 12
            self.stagnation_active = True
        else:
            self.current_rate = self.config.base_rate  # 25
            self.stagnation_active = False

        # Clamp rate
        self.current_rate = max(
            self.config.min_rate,
            min(self.config.max_rate, self.current_rate)
        )

        return self.current_rate

    def get_effective_rate(self, layer_idx: Optional[int] = None) -> int:
        """
        Get effective SGP rate for a specific layer.

        Authority layers (0-8) get higher persistence to lock structure.
        Sensory layers (9-11) get normal persistence.
        """
        rate = self.current_rate

        if layer_idx is not None:
            if layer_idx in self.config.authority_layers:  # Authority (0-8)
                rate = int(rate * self.config.authority_multiplier)
            else:  # Sensory (9-11)
                rate = int(rate * self.config.sensory_multiplier)

        return max(self.config.min_rate, min(self.config.max_rate, rate))

    def get_status(self) -> Dict[str, Any]:
        """Get current SGP status."""
        return {
            "step": self.step_count,
            "rate": self.current_rate,
            "base_rate": self.config.base_rate,
            "stagnation_rate": self.config.stagnation_rate,
            "momentum": self.current_momentum,
            "gamma": self.gamma,
            "stagnation_active": self.stagnation_active,
            "authority_rate": self.get_effective_rate(0),
            "sensory_rate": self.get_effective_rate(9),
            "sattvic_attached": self._sattvic_controller is not None,
            "authority_params_count": len(self.authority_params),
            "last_pulse_step": self.last_pulse_step,
        }

    def print_status(self):
        """Print current SGP status."""
        status = self.get_status()
        print(f"\n  ╔═══════════════════════════════════════════════════════════════╗")
        print(f"  ║               SGP CONTROLLER STATUS                           ║")
        print(f"  ╠═══════════════════════════════════════════════════════════════╣")
        print(f"  ║  Step:             {status['step']:>20}             ║")
        print(f"  ║  Current Rate:     {status['rate']:>20}             ║")
        print(f"  ║  Base Rate:        {status['base_rate']:>20}             ║")
        print(f"  ║  Stagnation Rate:  {status['stagnation_rate']:>20}             ║")
        print(f"  ║  Gamma (γ):        {status['gamma']:>20.3f}             ║")
        print(f"  ║  Authority Rate:   {status['authority_rate']:>20}             ║")
        print(f"  ║  Sensory Rate:     {status['sensory_rate']:>20}             ║")
        print(f"  ║  Stagnation Mode:  {'YES' if status['stagnation_active'] else 'NO':>20}             ║")
        print(f"  ║  Authority Params: {status['authority_params_count']:>20}             ║")
        print(f"  ║  Last Pulse Step:  {status['last_pulse_step']:>20}             ║")
        print(f"  ╚═══════════════════════════════════════════════════════════════╝")

    def should_apply_gradients(self, accumulated_steps: int) -> bool:
        """Check if gradients should be applied (persistence threshold met)."""
        return accumulated_steps >= self.current_rate


# =============================================================================
# FACTORY FUNCTIONS
# =============================================================================

def create_sgp_controller(
    base_rate: int = 25,
    stagnation_rate: int = 12,
    gamma: float = 0.3,
    momentum: float = 0.9,
) -> SGPController:
    """
    Create an SGP Controller with custom settings.

    Args:
        base_rate: Default SGP rate (25 = Toroidal Refresh Rate)
        stagnation_rate: Rate when stagnation detected (12 = halved)
        gamma: Persistence coefficient for gradient injection
        momentum: Gradient momentum factor

    Returns:
        Configured SGPController
    """
    config = SGPConfig(
        base_rate=base_rate,
        stagnation_rate=stagnation_rate,
        gamma=gamma,
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
    # Use the new metabolic step
    pulse_applied = sgp_controller.sgp_metabolic_step({
        'entropy': entropy,
        'knowledge': knowledge,
    })

    # Check if we should apply gradients
    if pulse_applied:
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
    print("  SGP CONTROLLER TEST (v2.0)")
    print("=" * 60)

    # Create synchronized controllers
    from symbolu.resonance.controller import SattvicController

    sattvic = SattvicController()
    sgp = SGPController()
    sgp.attach_sattvic_controller(sattvic)

    print("\n  Controllers synchronized.")
    print(f"  Base Rate: {sgp.config.base_rate}")
    print(f"  Stagnation Rate: {sgp.config.stagnation_rate}")
    print(f"  Gamma: {sgp.gamma}")

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
        if sgp.stagnation_active:
            event = f"🔨 HALVED (12)"

        print(f"  {step:<8} {entropy:<10.2f} {sgp_rate:<10} {lambda_csr:<12.3f} {event}")

    print("\n" + "=" * 60)
    sgp.print_status()
    print("=" * 60)
