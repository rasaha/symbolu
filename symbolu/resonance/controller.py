"""
Sattvic Controller — Dynamic CSR Regulation
============================================

╔═══════════════════════════════════════════════════════════════════════════════╗
║                         SATTVIC LAMBDA CONTROLLER                              ║
║                                                                                ║
║  Manages the influence of CSR (Constraint-Structure-Resonance) signal         ║
║  based on the model's training health and entropy dynamics.                   ║
╚═══════════════════════════════════════════════════════════════════════════════╝

The Sattvic Controller implements a "Knowledge-Based Release" pattern:

    1. WARMUP PHASE (steps 0-500):
       - Maintain λ = 0.5 to "prime" Authority layers with strong phonetic grounding

    2. SATTVIC DECAY PHASE (Knowledge-based):
       - As Knowledge Score rises toward 0.7, decay λ toward 0.1 floor
       - Model learns to internalize phonetic invariants

    3. EMERGENCY INTERVENTION:
       - If Entropy < 0.4 OR Entropy Variance < 0.001:
         → Multiply λ by 1.5 to "shatter" repetitive loops
         → Can exceed λ_max up to 1.0 for emergency recovery

This controller provides the "Sovereign Handshake" between:
    - The 12D Phoneme-Ontology Map (Sanskrit-calibrated)
    - The 6:6 Hybrid Neural Architecture (Quadratic + Phase layers)

Integration Points:
    - Pre-Block Bias: E_CSR added to input embeddings
    - Phase Gating: α_eff calculated from CSR confidence

Version: 1.0
Date: 2026-01-04
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any
from collections import deque
import warnings

try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False


# =============================================================================
# CONFIGURATION
# =============================================================================

@dataclass
class SattvicConfig:
    """Configuration for Sattvic Controller."""

    # Lambda bounds
    initial_lambda: float = 0.5      # Starting λ (strong guidance)
    floor_lambda: float = 0.1        # Minimum λ floor after decay
    max_lambda: float = 1.0          # Maximum λ during emergency boost

    # Warmup settings
    warmup_steps: int = 500          # Steps before decay begins

    # Knowledge-based decay
    know_threshold: float = 0.7      # Knowledge score for full decay

    # Entropy variance detection
    variance_window: int = 50        # Window size for variance calculation
    # V9.9.1 FIX: Increased threshold to 0.0001 - previous 0.01 was FAR too sensitive
    # during early training where entropy naturally has low variance as PPL drops smoothly.
    # The 0.01 threshold caused boost/release oscillation every 100 steps despite
    # healthy convergence (PPL dropping 15-17% per eval).
    variance_threshold: float = 0.0001  # Variance below this = stagnation (reduced from 0.01)
    variance_release_threshold: float = 0.001  # Variance must exceed this to release
    entropy_floor: float = 0.40      # Entropy below this = mode collapse

    # Boost settings
    boost_factor: float = 1.5        # Multiplier when boosting λ
    boost_cooldown: int = 200        # Steps before boost can trigger again (increased from 100)
    collapse_release_buffer: float = 0.05  # Entropy must exceed floor + buffer to release collapse boost

    # Decay curve
    decay_type: str = "cosine"       # linear, cosine, exponential


# =============================================================================
# SATTVIC CONTROLLER
# =============================================================================

class SattvicController:
    """
    Sattvic Controller for Dynamic CSR Regulation.

    Manages the λ_csr (CSR injection strength) based on:
        1. Training step (warmup phase)
        2. Knowledge score (decay phase)
        3. Entropy variance (stagnation detection)
        4. Instantaneous entropy (mode collapse detection)

    The controller implements a "Sattvic Release" pattern:
        - Strong guidance initially to establish phonetic grounding
        - Gradual release as model develops Knowledge
        - Emergency boost to shatter repetitive loops

    Usage:
        controller = SattvicController()

        for step in training_steps:
            metrics = {'ent': entropy, 'know': knowledge}
            lambda_csr = controller.update(step, metrics)

            # Use lambda_csr in forward pass
            x = x + lambda_csr * E_CSR
    """

    def __init__(self, config: Optional[SattvicConfig] = None):
        """
        Initialize Sattvic Controller.

        Args:
            config: SattvicConfig with controller settings
        """
        self.config = config or SattvicConfig()

        # Current state
        self.lambda_csr = self.config.initial_lambda
        self.current_step = 0
        self.current_entropy = 1.0
        self.current_knowledge = 0.0

        # Stagnation detection state
        self.stagnation_detected = False
        self.mode_collapse_detected = False
        self.boost_active = False
        self.boost_trigger_type = None  # Track what caused the boost: "stagnation" or "collapse"
        self.last_boost_step = -self.config.boost_cooldown  # Allow immediate boost
        self.steps_since_boost_start = 0  # Track duration of boost for hysteresis

        # Entropy history for variance calculation
        self.entropy_history: deque = deque(maxlen=self.config.variance_window)
        self.variance_history: List[float] = []

        # Full history for analysis
        self.history: List[Dict[str, Any]] = []

    def update(self, step: int, metrics: Dict[str, float]) -> float:
        """
        Update λ_csr based on current training state.

        Args:
            step: Current training step
            metrics: Dictionary with 'ent' (entropy) and 'know' (knowledge)

        Returns:
            Updated λ_csr value
        """
        self.current_step = step
        entropy = metrics.get('ent', metrics.get('entropy', 1.0))
        knowledge = metrics.get('know', metrics.get('knowledge', 0.0))

        self.current_entropy = entropy
        self.current_knowledge = knowledge

        # Track entropy history
        self.entropy_history.append(entropy)

        # 1. WARMUP CHECK: Maintain high guidance initially
        if step < self.config.warmup_steps:
            self.lambda_csr = self.config.initial_lambda
            self._record_history(step, "warmup")
            return self.lambda_csr

        # 2. STAGNATION DETECTION: Entropy Variance Collapse
        entropy_variance = self._compute_entropy_variance()
        self.variance_history.append(entropy_variance)

        stagnation_trigger = (
            len(self.entropy_history) == self.config.variance_window and
            entropy_variance < self.config.variance_threshold
        )

        collapse_trigger = entropy < self.config.entropy_floor

        # Check if we should boost
        if (stagnation_trigger or collapse_trigger) and self._can_boost(step):
            self.stagnation_detected = stagnation_trigger
            self.mode_collapse_detected = collapse_trigger
            self.boost_active = True
            self.last_boost_step = step
            self.steps_since_boost_start = 0  # Reset counter

            # Track what triggered the boost
            if collapse_trigger:
                self.boost_trigger_type = "collapse"
            else:
                self.boost_trigger_type = "stagnation"

            # EMERGENCY BOOST: Force-shatter the loop
            # λ can exceed initial_lambda (up to 1.0) during emergency
            self.lambda_csr = min(
                self.config.max_lambda,
                self.lambda_csr * self.config.boost_factor
            )

            trigger_reason = []
            if stagnation_trigger:
                trigger_reason.append(f"variance={entropy_variance:.6f}")
            if collapse_trigger:
                trigger_reason.append(f"entropy={entropy:.3f}")

            print(f"  🔥 [SATTVIC BOOST] Step {step}: {', '.join(trigger_reason)} (type={self.boost_trigger_type})")
            print(f"     λ increased to {self.lambda_csr:.3f}")

            self._record_history(step, "boost")
            return self.lambda_csr

        # Check if boost should be released - with hysteresis and proper variance checking
        if self.boost_active:
            self.steps_since_boost_start += 1

            if self._check_release_condition(entropy, entropy_variance, step):
                self.boost_active = False
                self.stagnation_detected = False
                self.mode_collapse_detected = False
                self.boost_trigger_type = None
                self.steps_since_boost_start = 0

        # 3. SATTVIC DECAY: Knowledge-Based Release
        if knowledge >= self.config.know_threshold:
            # Full decay - model has learned
            self.lambda_csr = self.config.floor_lambda
        else:
            # Gradual decay based on knowledge progress
            decay_progress = min(1.0, knowledge / self.config.know_threshold)
            decay_factor = self._compute_decay_factor(decay_progress)

            lambda_range = self.config.initial_lambda - self.config.floor_lambda
            self.lambda_csr = self.config.floor_lambda + (lambda_range * decay_factor)

        # Ensure we don't go below floor
        self.lambda_csr = max(self.config.floor_lambda, self.lambda_csr)

        self._record_history(step, "decay" if not self.boost_active else "boost_active")
        return self.lambda_csr

    def _compute_entropy_variance(self) -> float:
        """Compute variance of entropy over the history window."""
        if len(self.entropy_history) < 2:
            return 1.0  # High variance = no stagnation

        values = list(self.entropy_history)

        if HAS_NUMPY:
            return float(np.var(values))
        else:
            # Pure Python variance calculation
            n = len(values)
            mean = sum(values) / n
            variance = sum((x - mean) ** 2 for x in values) / n
            return variance

    @property
    def entropy_variance(self) -> float:
        """Property accessor for entropy variance (used by SGP controller)."""
        return self._compute_entropy_variance()

    def _compute_decay_factor(self, progress: float) -> float:
        """Compute decay factor based on progress (0→1)."""
        # progress: 0 = no knowledge, 1 = at threshold
        # Returns: 1 = full guidance, 0 = floor

        if self.config.decay_type == "linear":
            return 1.0 - progress

        elif self.config.decay_type == "cosine":
            # Smoother transition
            return 0.5 * (1.0 + math.cos(math.pi * progress))

        elif self.config.decay_type == "exponential":
            # Faster initial decay
            return math.exp(-3.0 * progress)

        else:
            return 1.0 - progress  # Default to linear

    def _can_boost(self, step: int) -> bool:
        """Check if boost is allowed (cooldown elapsed)."""
        return (step - self.last_boost_step) >= self.config.boost_cooldown

    def _check_release_condition(self, current_entropy: float, current_variance: float, step: int) -> bool:
        """
        Check if boost should be released.

        Uses hysteresis and variance-based detection to prevent 1-step cycles.

        Args:
            current_entropy: Current normalized entropy
            current_variance: Current entropy variance
            step: Current training step

        Returns:
            True if boost should be released, False otherwise
        """
        # 1. Enforce Minimum Duration (Hysteresis)
        # Prevent immediate release - must boost for at least 50 steps
        if self.steps_since_boost_start < 50:
            return False  # Keep boosting!

        # 2. Check if Stagnation is actually broken (Variance-based)
        # We want variance to be healthy again, not just entropy level.
        # Use 5x the trigger threshold to ensure variance has meaningfully increased
        is_stagnation_broken = current_variance > (self.config.variance_threshold * 5)

        # 3. Emergency Release (if Entropy gets too high/hallucination)
        # V9.9.1 FIX: Raised from 0.65 to 0.95 — during early training entropy is
        # naturally 0.9+ as PPL is high, which caused immediate release after every
        # 50-step hysteresis window. Only release for truly dangerous entropy levels.
        is_entropy_unsafe = current_entropy > 0.95

        if is_stagnation_broken or is_entropy_unsafe:
            reason = "stagnation broken" if is_stagnation_broken else "entropy unsafe"
            print(f"  ✅ [SATTVIC RELEASE] Step {step}: {reason} (variance={current_variance:.6f}, entropy={current_entropy:.3f}, duration={self.steps_since_boost_start})")
            return True  # Release

        return False  # Keep boosting

    def _record_history(self, step: int, phase: str):
        """Record state for analysis."""
        self.history.append({
            "step": step,
            "lambda_csr": self.lambda_csr,
            "entropy": self.current_entropy,
            "knowledge": self.current_knowledge,
            "variance": self.variance_history[-1] if self.variance_history else None,
            "phase": phase,
            "stagnation": self.stagnation_detected,
            "collapse": self.mode_collapse_detected,
            "boost_active": self.boost_active,
        })

    def get_phase_authority_factor(self) -> float:
        """
        Compute α_eff for Phase Attention gating.

        Returns a factor [0, 1] that modulates Phase layer authority
        based on CSR confidence.

        Higher λ_csr → Lower Phase authority (structure over reasoning)
        Lower λ_csr → Higher Phase authority (reasoning takes over)
        """
        # Normalize lambda to [0, 1] range
        lambda_normalized = (self.lambda_csr - self.config.floor_lambda) / (
            self.config.initial_lambda - self.config.floor_lambda
        )
        lambda_normalized = max(0.0, min(1.0, lambda_normalized))

        # Invert: high λ → low authority factor
        return 1.0 - lambda_normalized

    def should_increase_guidance(self) -> bool:
        """Check if guidance should be increased (stagnation/collapse detected)."""
        return self.stagnation_detected or self.mode_collapse_detected

    def get_status(self) -> Dict[str, Any]:
        """Get current controller status."""
        entropy_variance = self._compute_entropy_variance()

        return {
            "step": self.current_step,
            "lambda_csr": self.lambda_csr,
            "entropy": self.current_entropy,
            "knowledge": self.current_knowledge,
            "entropy_variance": entropy_variance,
            "stagnation_detected": self.stagnation_detected,
            "mode_collapse_detected": self.mode_collapse_detected,
            "boost_active": self.boost_active,
            "phase": self._get_phase_name(),
            "phase_authority_factor": self.get_phase_authority_factor(),
        }

    def _get_phase_name(self) -> str:
        """Get human-readable phase name."""
        if self.current_step < self.config.warmup_steps:
            return "WARMUP"
        elif self.boost_active:
            return "EMERGENCY_BOOST"
        elif self.current_knowledge >= self.config.know_threshold:
            return "SATTVIC_FLOOR"
        else:
            return "SATTVIC_DECAY"

    def print_status(self):
        """Print current controller status."""
        status = self.get_status()

        print(f"\n  ╔══════════════════════════════════════════════════╗")
        print(f"  ║         SATTVIC CONTROLLER STATUS                ║")
        print(f"  ╠══════════════════════════════════════════════════╣")
        print(f"  ║  Phase:           {status['phase']:>20}         ║")
        print(f"  ║  Step:            {status['step']:>20}         ║")
        print(f"  ║  λ_csr:           {status['lambda_csr']:>20.4f}         ║")
        print(f"  ║  Entropy:         {status['entropy']:>20.4f}         ║")
        print(f"  ║  Knowledge:       {status['knowledge']:>20.4f}         ║")
        print(f"  ║  Ent. Variance:   {status['entropy_variance']:>20.6f}         ║")
        print(f"  ║  Boost Active:    {'YES' if status['boost_active'] else 'NO':>20}         ║")
        print(f"  ║  Phase Authority: {status['phase_authority_factor']:>20.4f}         ║")
        print(f"  ╚══════════════════════════════════════════════════╝")

    def get_metric_targets(self) -> Dict[str, Tuple[float, float]]:
        """
        Get expected metric ranges for current λ_csr.

        Returns target ranges for monitoring training health.
        """
        λ = self.lambda_csr

        if λ >= 0.4:
            # Strong guidance phase
            return {
                "entropy": (0.52, 0.60),
                "coherence": (0.82, 0.88),
                "sa_ratio": (0.5, 0.7),
            }
        elif λ >= 0.2:
            # Moderate guidance
            return {
                "entropy": (0.48, 0.58),
                "coherence": (0.78, 0.85),
                "sa_ratio": (0.45, 0.65),
            }
        else:
            # Light guidance (high knowledge)
            return {
                "entropy": (0.45, 0.55),
                "coherence": (0.75, 0.82),
                "sa_ratio": (0.4, 0.6),
            }

    def get_diagnostics(self) -> Dict[str, Any]:
        """Get detailed diagnostics for debugging."""
        return {
            "config": {
                "initial_lambda": self.config.initial_lambda,
                "floor_lambda": self.config.floor_lambda,
                "max_lambda": self.config.max_lambda,
                "warmup_steps": self.config.warmup_steps,
                "know_threshold": self.config.know_threshold,
                "variance_window": self.config.variance_window,
                "variance_threshold": self.config.variance_threshold,
                "entropy_floor": self.config.entropy_floor,
                "boost_factor": self.config.boost_factor,
            },
            "state": self.get_status(),
            "history_length": len(self.history),
            "entropy_window": list(self.entropy_history),
            "variance_history": self.variance_history[-10:] if self.variance_history else [],
        }

    def get_state(self) -> Dict[str, Any]:
        """Get serializable state for checkpoint saving."""
        return {
            "lambda_csr": self.lambda_csr,
            "current_step": self.current_step,
            "current_entropy": self.current_entropy,
            "current_knowledge": self.current_knowledge,
            "stagnation_detected": self.stagnation_detected,
            "mode_collapse_detected": self.mode_collapse_detected,
            "boost_active": self.boost_active,
            "boost_trigger_type": self.boost_trigger_type,
            "last_boost_step": self.last_boost_step,
            "steps_since_boost_start": self.steps_since_boost_start,
            "entropy_history": list(self.entropy_history),
            "variance_history": self.variance_history.copy(),
        }

    def load_state(self, state: Dict[str, Any]):
        """Restore state from checkpoint."""
        self.lambda_csr = state.get("lambda_csr", self.config.initial_lambda)
        self.current_step = state.get("current_step", 0)
        self.current_entropy = state.get("current_entropy", 1.0)
        self.current_knowledge = state.get("current_knowledge", 0.0)
        self.stagnation_detected = state.get("stagnation_detected", False)
        self.mode_collapse_detected = state.get("mode_collapse_detected", False)
        self.boost_active = state.get("boost_active", False)
        self.boost_trigger_type = state.get("boost_trigger_type", None)
        self.last_boost_step = state.get("last_boost_step", -self.config.boost_cooldown)
        self.steps_since_boost_start = state.get("steps_since_boost_start", 0)
        # Restore entropy history
        self.entropy_history.clear()
        for ent in state.get("entropy_history", []):
            self.entropy_history.append(ent)
        self.variance_history = state.get("variance_history", []).copy()
        print(f"    ✓ Sattvic Controller state restored (λ={self.lambda_csr:.3f}, step={self.current_step})")


# =============================================================================
# FACTORY FUNCTION
# =============================================================================

def create_sattvic_controller(
    initial_lambda: float = 0.5,
    floor_lambda: float = 0.1,
    warmup_steps: int = 500,
    know_threshold: float = 0.7,
    variance_window: int = 50,
    decay_type: str = "cosine",
) -> SattvicController:
    """
    Create a Sattvic Controller with custom settings.

    Args:
        initial_lambda: Starting λ (strong guidance)
        floor_lambda: Minimum λ after decay
        warmup_steps: Steps before decay begins
        know_threshold: Knowledge score for full decay
        variance_window: Window for variance calculation
        decay_type: Decay curve (linear, cosine, exponential)

    Returns:
        Configured SattvicController
    """
    config = SattvicConfig(
        initial_lambda=initial_lambda,
        floor_lambda=floor_lambda,
        warmup_steps=warmup_steps,
        know_threshold=know_threshold,
        variance_window=variance_window,
        decay_type=decay_type,
    )
    return SattvicController(config)


# =============================================================================
# PHASE ATTENTION INTEGRATION
# =============================================================================

def compute_alpha_effective(
    base_alpha: float,
    csr_confidence: float,
    coherence: float,
    perplexity: float,
    controller: Optional[SattvicController] = None,
) -> float:
    """
    Compute effective α for Phase Attention gating.

    This prevents "Ego-Reasoning Conflict" by ensuring Phase layers
    only take control when ontological resonance is high.

    Formula:
        α_eff = α * g(csr_confidence, coherence, perplexity)

    Where g() is a gating function that:
        - Increases with CSR confidence
        - Increases with coherence
        - Decreases with perplexity

    Args:
        base_alpha: Scheduled α value from training
        csr_confidence: CSR embedding confidence [0, 1]
        coherence: Current coherence metric [0, 1]
        perplexity: Current perplexity (lower = better)
        controller: Optional SattvicController for λ-based modulation

    Returns:
        Effective α for Phase layer blending
    """
    # Normalize perplexity to [0, 1] (assuming typical range 1-100)
    ppl_normalized = 1.0 - min(1.0, perplexity / 100.0)

    # Compute gating function
    # Higher confidence + coherence + low perplexity → higher gate
    gate = (csr_confidence * 0.4 + coherence * 0.4 + ppl_normalized * 0.2)

    # Apply controller modulation if available
    if controller is not None:
        phase_factor = controller.get_phase_authority_factor()
        gate = gate * phase_factor

    # Clamp to valid range
    gate = max(0.0, min(1.0, gate))

    return base_alpha * gate


# =============================================================================
# PUBLIC EXPORTS
# =============================================================================

__all__ = [
    # Configuration
    "SattvicConfig",
    # Main controller
    "SattvicController",
    "create_sattvic_controller",
    # Integration helpers
    "compute_alpha_effective",
]


# =============================================================================
# TESTING
# =============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("  SATTVIC CONTROLLER TEST")
    print("=" * 60)

    # Create controller
    controller = SattvicController()

    print("\n  Simulating training progression...")
    print("  " + "-" * 50)

    # Simulate training
    test_scenarios = [
        # (step, entropy, knowledge, description)
        (0, 0.8, 0.0, "Initial state"),
        (100, 0.7, 0.05, "Early training"),
        (250, 0.6, 0.15, "Mid warmup"),
        (500, 0.55, 0.25, "End warmup"),
        (750, 0.52, 0.35, "Early decay"),
        (1000, 0.50, 0.45, "Mid decay"),
        (1250, 0.48, 0.55, "Late decay"),
        (1500, 0.35, 0.60, "Mode collapse trigger"),
        (1600, 0.55, 0.65, "Recovery"),
        (2000, 0.50, 0.75, "High knowledge"),
    ]

    for step, entropy, knowledge, desc in test_scenarios:
        lambda_csr = controller.update(step, {'ent': entropy, 'know': knowledge})
        status = controller.get_status()

        print(f"\n  Step {step:4d}: {desc}")
        print(f"    Entropy={entropy:.2f}, Knowledge={knowledge:.2f}")
        print(f"    λ_csr={lambda_csr:.3f}, Phase={status['phase']}")

    print("\n" + "=" * 60)
    print("  STAGNATION DETECTION TEST")
    print("=" * 60)

    # Reset and test stagnation detection
    stag_controller = SattvicController()

    # Fill with constant entropy to trigger stagnation
    print("\n  Filling entropy window with constant value (0.5)...")
    for i in range(55):
        step = 500 + i
        lambda_csr = stag_controller.update(step, {'ent': 0.50, 'know': 0.3})

    status = stag_controller.get_status()
    print(f"\n  Final status after {55} steps:")
    print(f"    Entropy Variance: {status['entropy_variance']:.6f}")
    print(f"    Stagnation Detected: {status['stagnation_detected']}")
    print(f"    Boost Active: {status['boost_active']}")
    print(f"    λ_csr: {status['lambda_csr']:.3f}")

    print("\n" + "=" * 60)
