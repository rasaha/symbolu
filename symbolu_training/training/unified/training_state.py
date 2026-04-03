"""
Training state tracking and Guna-based training dynamics.

Extracted from train_unified_llm.py. Contains:
- TrainingStateTracker: Track knowledge state across training runs
- GradNormEMA: Exponential moving average for gradient norms
- TrainingGunas: Map training dynamics to Sattva/Rajas/Tamas
- SattvicBrake: Lightweight confidence estimation via phase angle variance
"""

import json
import math
import torch
import torch.nn as nn
import torch.nn.functional as F
from typing import Dict, List, Optional, Any, Tuple

from symbolu_training.training.unified.utilities import get_pramana_weights

try:
    from agentic.guna_modulation.variance_confidence import (
        VarianceConfidence,
        VarianceConfidenceConfig,
    )
    VARIANCE_CONFIDENCE_AVAILABLE = True
except ImportError:
    VARIANCE_CONFIDENCE_AVAILABLE = False


class TrainingStateTracker:
    """
    v2.7 Training State Tracker - Track "knowledge state" across training runs.

    Maps training metrics to v2.7 Observables and uses bounded EMA state
    evolution to track the model's learning progress with persistence.

    Features:
    - Maps training metrics (loss, PPL, coherence, entropy) to Observables
    - Bounded EMA state evolution: θ_{t+1} = (1-α)·θ_t + α·θ*
    - Saves/loads state to training_state.json for cross-run continuity
    - Detects regression (model getting worse)
    - Provides confidence-based LR modifier

    Usage:
        tracker = TrainingStateTracker(state_path="checkpoints/training_state.json")
        knowledge = tracker.update(metrics, step=1000)
        if tracker.detect_regression():
            print("Model regressing!")
    """

    def __init__(
        self,
        state_path: str = "training_state.json",
        alpha: float = 0.1,  # EMA learning rate
        enabled: bool = True,
    ):
        self.state_path = state_path
        self.alpha = alpha
        self.enabled = enabled

        # State register θ_t (bounded [0, 1])
        self.state = {
            "cognitive_state": 0.5,    # Overall knowledge quality
            "confidence": 0.5,          # Model confidence
            "stability": 0.5,           # Training stability
            "tone_ema": 0.5,            # Tone (positive = good learning)
            "step_count": 0,
        }

        # History for regression detection
        self.history = []
        self.max_history = 100

        # Try to load existing state
        if enabled:
            self.load_state()

    def metrics_to_observables(self, metrics: dict) -> dict:
        """
        Convert training metrics to v2.7-style Observables.

        Mapping:
        - S (Salience): Inverse of loss (lower loss = higher salience)
        - R (Reliability): Coherence (how consistent the model is)
        - T (Tone): 1 - Entropy (low entropy = positive tone)
        - H (Hesitation): PPL normalized (high PPL = hesitation)
        - C_contr (Contradiction): S/A ratio deviation from ideal (0.35)
        """
        loss = metrics.get('loss', metrics.get('total_loss', 5.0))
        ppl = metrics.get('ppl', 100.0)
        coherence = metrics.get('coherence', metrics.get('gc', 0.5))
        entropy = metrics.get('onto_entropy', metrics.get('entropy', 0.5))
        sa_ratio = metrics.get('sa_ratio', 0.35)

        return {
            "S": max(0, min(1, 1.0 - loss / 10.0)),      # Salience: inverse loss
            "R": float(coherence) if coherence else 0.5, # Reliability: coherence
            "T": 1.0 - float(entropy),                   # Tone: inverse entropy
            "H": min(1, ppl / 500.0),                    # Hesitation: normalized PPL
            "C_contr": abs(sa_ratio - 0.35) * 2,         # Contradiction: S/A deviation
        }

    def compute_target_state(self, observables: dict) -> dict:
        """
        Compute target state θ* from observables.

        Target state represents "where we should be" based on current signals.
        """
        S, R, T, H, C = (
            observables["S"],
            observables["R"],
            observables["T"],
            observables["H"],
            observables["C_contr"],
        )

        # Cognitive state: weighted combination favoring reliability and salience
        cognitive_target = 0.4 * S + 0.3 * R + 0.2 * T + 0.1 * (1 - H)

        # Confidence: based on consistency (low contradiction, high reliability)
        confidence_target = R * (1 - C) * (1 - H)

        # Stability: based on low hesitation and contradiction
        stability_target = (1 - H) * (1 - C)

        # Tone: direct from observables
        tone_target = T

        return {
            "cognitive_state": max(0, min(1, cognitive_target)),
            "confidence": max(0, min(1, confidence_target)),
            "stability": max(0, min(1, stability_target)),
            "tone_ema": max(0, min(1, tone_target)),
        }

    def update(self, metrics: dict, step: int) -> dict:
        """
        Update knowledge state based on training metrics.

        Applies v2.7 EMA update: θ_{t+1} = (1-α)·θ_t + α·θ*

        Returns:
            Dict with current state and update info
        """
        if not self.enabled:
            return {"enabled": False}

        # Convert metrics to observables
        observables = self.metrics_to_observables(metrics)

        # Compute target state
        target = self.compute_target_state(observables)

        # Apply EMA update: θ_{t+1} = (1-α)·θ_t + α·θ*
        for key in ["cognitive_state", "confidence", "stability", "tone_ema"]:
            self.state[key] = (1 - self.alpha) * self.state[key] + self.alpha * target[key]

        self.state["step_count"] = step

        # Track history
        self.history.append({
            "step": step,
            "cognitive_state": self.state["cognitive_state"],
            "confidence": self.state["confidence"],
        })
        if len(self.history) > self.max_history:
            self.history = self.history[-self.max_history:]

        return {
            "cognitive_state": self.state["cognitive_state"],
            "confidence": self.state["confidence"],
            "stability": self.state["stability"],
            "tone": self.state["tone_ema"],
            "observables": observables,
        }

    def detect_regression(self, window: int = 20) -> bool:
        """
        Detect if model is regressing (knowledge declining).

        Compares recent cognitive_state to earlier values.
        """
        if len(self.history) < window * 2:
            return False

        recent = self.history[-window:]
        earlier = self.history[-(window * 2):-window]

        recent_avg = sum(h["cognitive_state"] for h in recent) / len(recent)
        earlier_avg = sum(h["cognitive_state"] for h in earlier) / len(earlier)

        # Regression if recent is significantly lower than earlier
        return recent_avg < earlier_avg - 0.1

    def get_lr_modifier(self) -> float:
        """
        Get learning rate modifier based on confidence.

        Low confidence → reduce LR (be more careful)
        High confidence → normal LR
        """
        if not self.enabled:
            return 1.0

        confidence = self.state["confidence"]
        if confidence < 0.3:
            return 0.6  # Very low confidence: 60% LR
        elif confidence < 0.5:
            return 0.8  # Low confidence: 80% LR
        return 1.0      # Normal confidence: 100% LR

    def save_state(self):
        """Persist state to disk for cross-run continuity."""
        if not self.enabled:
            return

        try:
            import json
            with open(self.state_path, 'w') as f:
                json.dump(self.state, f, indent=2)
        except Exception as e:
            print(f"  Warning: Could not save training state: {e}")

    def load_state(self):
        """Load persisted state from previous run."""
        try:
            import json
            with open(self.state_path, 'r') as f:
                loaded = json.load(f)
                self.state.update(loaded)
            print(f"  \U0001f4c2 Loaded v2.7 training state from step {self.state['step_count']}")
        except FileNotFoundError:
            print(f"  \U0001f195 Starting fresh v2.7 training state")
        except Exception as e:
            print(f"  Warning: Could not load training state: {e}")

    def format_status(self) -> str:
        """Format current state for logging."""
        return (
            f"Know:{self.state['cognitive_state']:.2f} "
            f"Conf:{self.state['confidence']:.2f} "
            f"Stab:{self.state['stability']:.2f}"
        )

    def update_with_gunas(self, s: float, r: float, t: float, step: int) -> dict:
        """
        Update knowledge state with Training Gunas.

        This bridges training physics (gradients/loss) with cognitive philosophy
        (Sattva/Rajas/Tamas), enabling the tracker to become a Guna-Aware Governor.

        Args:
            s: Sattva (clarity) - coherence × (1 - entropy)
            r: Rajas (action) - normalized gradient activity
            t: Tamas (inertia) - stability/stagnation measure

        Returns:
            Dict with Guna state and update info
        """
        if not self.enabled:
            return {"enabled": False}

        # Normalize to ensure sum = 1.0
        total = s + r + t
        if total > 0:
            s, r, t = s / total, r / total, t / total
        else:
            s, r, t = 0.33, 0.33, 0.34

        # Store Guna state
        if "gunas" not in self.state:
            self.state["gunas"] = {"s": 0.33, "r": 0.33, "t": 0.34}

        # EMA update for Gunas
        alpha = self.alpha
        self.state["gunas"]["s"] = (1 - alpha) * self.state["gunas"]["s"] + alpha * s
        self.state["gunas"]["r"] = (1 - alpha) * self.state["gunas"]["r"] + alpha * r
        self.state["gunas"]["t"] = (1 - alpha) * self.state["gunas"]["t"] + alpha * t

        # Map Gunas to cognitive state updates
        # High Sattva → increase cognitive_state
        # High Rajas → decrease stability (but may increase learning)
        # High Tamas → decrease confidence (stuck)
        guna_cognitive = 0.5 * s + 0.3 * (1 - t) + 0.2 * (1 - r * 0.5)
        guna_confidence = s * (1 - t)
        guna_stability = (1 - r) * (1 - t * 0.5)

        # Blend with existing state computation
        self.state["cognitive_state"] = (1 - alpha) * self.state["cognitive_state"] + alpha * guna_cognitive
        self.state["confidence"] = (1 - alpha) * self.state["confidence"] + alpha * guna_confidence
        self.state["stability"] = (1 - alpha) * self.state["stability"] + alpha * guna_stability
        self.state["step_count"] = step

        # Determine dominant Guna for logging
        gunas = self.state["gunas"]
        if gunas["s"] > gunas["r"] and gunas["s"] > gunas["t"]:
            dominant = "Lucidity"
        elif gunas["r"] > gunas["t"]:
            dominant = "Activity"
        else:
            dominant = "Stability"

        return {
            "gunas": self.state["gunas"].copy(),
            "dominant": dominant,
            "cognitive_state": self.state["cognitive_state"],
            "confidence": self.state["confidence"],
            "stability": self.state["stability"],
        }

    def get_guna_status(self) -> str:
        """Format Guna state for logging."""
        if "gunas" not in self.state:
            return "Gunas:N/A"

        g = self.state["gunas"]
        # Determine dominant and icon
        if g["s"] > g["r"] and g["s"] > g["t"]:
            icon = "\u2600\ufe0f"  # Lucidity - clarity
        elif g["r"] > g["t"]:
            icon = "\U0001f525"  # Activity - dynamism
        else:
            icon = "\U0001f319"  # Stability - inertia

        return f"S:{g['s']:.2f} R:{g['r']:.2f} T:{g['t']:.2f}{icon}"


# =============================================================================
# TRAINING GUNAS: Bridge Training Physics to Cognitive Philosophy
# =============================================================================

class GradNormEMA:
    """
    Exponential Moving Average tracker for gradient norms.

    Used to establish a baseline for Rajas (metabolic effort) computation.
    Handles first-step initialization safely to avoid division by zero.

    Usage:
        grad_ema = GradNormEMA(alpha=0.1)
        baseline = grad_ema.update(grad_norm)  # Returns EMA
        rajas = grad_norm / grad_ema.get_baseline()  # Safe division
    """

    def __init__(self, alpha: float = 0.1, min_baseline: float = 1e-8):
        """
        Initialize gradient norm EMA tracker.

        Args:
            alpha: EMA smoothing factor (higher = faster adaptation)
            min_baseline: Minimum baseline to prevent division by zero
        """
        self.alpha = alpha
        self.min_baseline = min_baseline
        self.ema: Optional[float] = None
        self.step_count = 0
        self.max_observed = 0.0

    def update(self, grad_norm: float) -> float:
        """
        Update EMA with new gradient norm observation.

        Args:
            grad_norm: Current gradient norm

        Returns:
            Updated EMA value
        """
        self.step_count += 1
        self.max_observed = max(self.max_observed, grad_norm)

        if self.ema is None:
            # First observation: initialize to observed value
            self.ema = grad_norm
        else:
            # Standard EMA update
            self.ema = (1 - self.alpha) * self.ema + self.alpha * grad_norm

        return self.ema

    def get_baseline(self) -> float:
        """
        Get safe baseline for Rajas computation.

        Never returns zero or very small values that would cause
        division issues.

        Returns:
            Baseline value >= min_baseline
        """
        if self.ema is None or self.ema < self.min_baseline:
            return 1.0  # Neutral baseline before enough data
        return self.ema

    def get_normalized(self, grad_norm: float) -> float:
        """
        Get normalized gradient activity (grad_norm / baseline).

        Clamped to [0, 2] to prevent extreme values.

        Args:
            grad_norm: Current gradient norm

        Returns:
            Normalized value in [0, 2] range
        """
        baseline = self.get_baseline()
        return min(2.0, grad_norm / baseline)


class TrainingGunas:
    """
    Training Gunas - Map training dynamics to Sattva/Rajas/Tamas.

    Bridges the gap between:
    - Training physics (gradients, loss, entropy)
    - Cognitive philosophy (Sattva=clarity, Rajas=action, Tamas=inertia)

    This enables semantic interpretation of training dynamics:
    - High Sattva: Model is learning well (lock in)
    - High Rajas: High gradient activity (may need braking)
    - High Tamas: Stagnation/plateau (may need boost)

    Usage:
        gunas = TrainingGunas()

        # Each training step:
        s, r, t = gunas.compute(
            coherence=0.8,
            entropy=0.3,
            grad_norm=5.0,
            loss=2.5,
            prev_loss=2.6
        )

        # Feed to TrainingStateTracker
        tracker.update_with_gunas(s, r, t, step)
    """

    def __init__(
        self,
        grad_ema_alpha: float = 0.1,
        loss_ema_alpha: float = 0.05,
    ):
        """
        Initialize Training Gunas computer.

        Args:
            grad_ema_alpha: EMA alpha for gradient norm baseline
            loss_ema_alpha: EMA alpha for loss velocity tracking
        """
        self.grad_ema = GradNormEMA(alpha=grad_ema_alpha)
        self.loss_ema: Optional[float] = None
        self.loss_ema_alpha = loss_ema_alpha
        self.prev_loss: Optional[float] = None

    def compute(
        self,
        coherence: float,
        entropy: float,
        grad_norm: float,
        loss: float,
        prev_loss: Optional[float] = None,
    ) -> Tuple[float, float, float]:
        """
        Compute Training Gunas from training metrics.

        Args:
            coherence: Model coherence [0, 1]
            entropy: Model entropy [0, 1]
            grad_norm: Current gradient norm
            loss: Current loss value
            prev_loss: Previous loss value (optional, uses tracked if None)

        Returns:
            (sattva, rajas, tamas) tuple, each in [0, 1], normalized to sum=1
        """
        # Update gradient baseline
        self.grad_ema.update(grad_norm)

        # Track loss for velocity
        if prev_loss is None:
            prev_loss = self.prev_loss if self.prev_loss is not None else loss
        self.prev_loss = loss

        # Compute raw Gunas
        s_raw = self._compute_sattva(coherence, entropy)
        r_raw = self._compute_rajas(grad_norm)
        t_raw = self._compute_tamas(loss, prev_loss, grad_norm)

        # Normalize to sum = 1.0
        total = s_raw + r_raw + t_raw
        if total > 0:
            s, r, t = s_raw / total, r_raw / total, t_raw / total
        else:
            s, r, t = 0.33, 0.33, 0.34

        return s, r, t

    def _compute_sattva(self, coherence: float, entropy: float) -> float:
        """
        Compute Sattva (clarity/quality of knowledge).

        Sattva = coherence × (1 - entropy)

        High coherence + low entropy = model is learning clearly.
        """
        # Clamp inputs
        coherence = max(0.0, min(1.0, float(coherence)))
        entropy = max(0.0, min(1.0, float(entropy)))

        return coherence * (1.0 - entropy)

    def _compute_rajas(self, grad_norm: float) -> float:
        """
        Compute Rajas (metabolic effort/action).

        Rajas = grad_norm / baseline_norm (clamped to [0, 1])

        High gradient activity relative to baseline = high action.
        """
        normalized = self.grad_ema.get_normalized(grad_norm)

        # Map [0, 2] to [0, 1] with 1.0 baseline at 0.5
        return min(1.0, normalized / 2.0)

    def _compute_tamas(
        self,
        loss: float,
        prev_loss: float,
        grad_norm: float,
    ) -> float:
        """
        Compute Tamas (inertia/stagnation) directly.

        NOT computed as residual (1 - s - r), but measured directly:
        - Low loss change = high inertia
        - Low gradient norm = high inertia

        Tamas = (1 - |loss_change|) × (1 - grad_activity)
        """
        # Loss velocity: how much is loss changing?
        loss_change = abs(loss - prev_loss)
        loss_velocity = min(1.0, loss_change / 0.5)  # Normalize, 0.5 = significant change

        # Gradient activity
        grad_activity = min(1.0, self.grad_ema.get_normalized(grad_norm) / 2.0)

        # Tamas: high when both loss and gradients are stable/flat
        tamas = (1.0 - loss_velocity) * (1.0 - grad_activity * 0.5)

        return max(0.0, min(1.0, tamas))

    def get_status(self, s: float, r: float, t: float) -> str:
        """Format Guna status for logging."""
        # Determine dominant
        if s > r and s > t:
            icon = "\u2600\ufe0f"  # Lucidity
            state = "Learning"
        elif r > t:
            icon = "\U0001f525"  # Activity
            state = "Active"
        else:
            icon = "\U0001f319"  # Stability
            state = "Plateau"

        return f"Gunas[{state}]: L:{s:.2f} A:{r:.2f} S:{t:.2f} {icon}"

    def get_action_recommendation(self, s: float, r: float, t: float) -> str:
        """
        Get action recommendation based on Guna state.

        Returns:
            Action recommendation string
        """
        if s > 0.5:
            return "CONSERVE"  # Learning well, lock in
        elif r > 0.5:
            return "BRAKE"     # High activity, may need to slow down
        elif t > 0.5:
            return "BOOST"     # Stagnant, may need to increase K_p
        else:
            return "CONTINUE"  # Balanced, keep going


# =============================================================================
# SATTVIC BRAKE: Lightweight Confidence via Phase Angle Variance
# =============================================================================

class SattvicBrake:
    """
    Sattvic Brake - Lightweight Confidence Estimation via Phase Angle Variance.

    Instead of full Bayesian inference, measure the "agreement" of Phase Attention
    heads in Authority layers (0-8). High agreement = high confidence.

    Now enhanced with R-Matrix Pramāṇa weighting:
    - Each layer's variance is weighted by its Pramāṇa (Truth) value from the R-Matrix
    - Intellect (layer 6) with Pramāṇa=0.9 contributes most to confidence
    - Dormant (layer 0) with Pramāṇa=0.1 contributes least

    Uses shared VarianceConfidence for braking logic and status formatting.

    Cost: ~0.1% compute (variance calculation), 0% extra memory

    Usage:
        brake = SattvicBrake(model, authority_layers=9)
        confidence = brake.compute_confidence()
        if confidence < 0.5:
            lr *= 0.8  # Apply brake
    """

    def __init__(
        self,
        model: nn.Module,
        authority_layers: int = 9,
        confidence_threshold: float = 0.5,
        lr_reduction: float = 0.8,
        window_size: int = 10,
        use_pramana_weighting: bool = True,  # Enable R-Matrix Pramāṇa weighting
    ):
        self.model = model
        self.authority_layers = authority_layers
        self.confidence_threshold = confidence_threshold
        self.lr_reduction = lr_reduction
        self.use_pramana_weighting = use_pramana_weighting

        # R-Matrix Pramāṇa weights for confidence weighting
        # Row 0 of R-Matrix = Pramāṇa (Truth) values per Aspect (layer)
        self._pramana_weights = get_pramana_weights()

        # Use shared VarianceConfidence for braking logic
        if VARIANCE_CONFIDENCE_AVAILABLE:
            self._variance_confidence = VarianceConfidence(
                window_size=window_size,
                confidence_threshold=confidence_threshold,
            )
        else:
            self._variance_confidence = None

        # Fallback history tracking (if shared class unavailable)
        self.confidence_history = []
        self.brake_applied_count = 0

    @torch.no_grad()
    def compute_phase_variance(self) -> Tuple[float, List[float]]:
        """
        Compute variance of phase angles across Authority layers.

        With Pramāṇa weighting enabled, each layer's variance is weighted by
        its Pramāṇa (Truth) value from the R-Matrix:
        - weighted_variance = sum(var_i * pramana_i) / sum(pramana_i)
        - Intellect (0.9) and Integration (0.9) dominate the score
        - Dormant (0.1) has minimal influence

        Returns:
            (average_variance, per_layer_variances)
        """
        variances = []

        # Get model layers
        layers = None
        if hasattr(self.model, 'layers'):
            layers = self.model.layers
        elif hasattr(self.model, 'transformer') and hasattr(self.model.transformer, 'layers'):
            layers = self.model.transformer.layers
        elif hasattr(self.model, 'blocks'):
            layers = self.model.blocks

        if layers is None:
            return 0.5, []  # Default if can't access layers

        # Check Authority layers (0 to authority_layers-1)
        for idx in range(min(self.authority_layers, len(layers))):
            layer = layers[idx]
            variance = self._get_layer_phase_variance(layer)
            if variance is not None:
                variances.append(variance)

        if not variances:
            return 0.5, []

        # Compute weighted or unweighted average
        if self.use_pramana_weighting and len(variances) > 0:
            # Pramāṇa-weighted variance: sum(var_i * pramana_i) / sum(pramana_i)
            weighted_sum = 0.0
            weight_sum = 0.0
            for idx, var in enumerate(variances):
                pramana = self._pramana_weights[min(idx, 11)].item()
                weighted_sum += var * pramana
                weight_sum += pramana
            avg_variance = weighted_sum / max(weight_sum, 1e-8)
        else:
            avg_variance = sum(variances) / len(variances)

        return avg_variance, variances

    def _get_layer_phase_variance(self, layer) -> Optional[float]:
        """Extract phase variance from a single layer."""
        # Try different attribute names for phase attention
        phase_attn = None
        for attr in ['phase_attention', 'attention', 'self_attn', 'attn']:
            if hasattr(layer, attr):
                phase_attn = getattr(layer, attr)
                break

        if phase_attn is None:
            return None

        # Try to get phase angles
        if hasattr(phase_attn, 'phase') and phase_attn.phase is not None:
            phase = phase_attn.phase
            if isinstance(phase, torch.Tensor):
                # Compute circular variance: 1 - |mean(e^{i*theta})|
                if phase.numel() > 1:
                    complex_phase = torch.exp(1j * phase.float())
                    mean_phase = torch.mean(complex_phase)
                    variance = 1.0 - torch.abs(mean_phase).item()
                    return variance

        # Fallback: use weight variance as proxy
        if hasattr(phase_attn, 'q_proj') and hasattr(phase_attn.q_proj, 'weight'):
            weight = phase_attn.q_proj.weight
            variance = weight.var().item()
            # Normalize to [0, 1] range (empirical scaling)
            return min(1.0, variance * 10)

        return None

    def compute_confidence(self) -> float:
        """
        Compute confidence score from phase variance.

        Confidence = 1 - variance (high variance = low confidence)
        """
        variance, layer_variances = self.compute_phase_variance()
        confidence = 1.0 - variance

        # Update shared variance confidence with layer variances
        if self._variance_confidence is not None and layer_variances:
            # Feed layer variances as observation tuple
            self._variance_confidence.update(tuple(layer_variances))

        # Track history
        self.confidence_history.append(confidence)
        if len(self.confidence_history) > 100:
            self.confidence_history = self.confidence_history[-100:]

        return max(0.0, min(1.0, confidence))

    def should_brake(self, confidence: float = None) -> Tuple[bool, float]:
        """
        Check if brake should be applied.

        Returns:
            (should_apply, lr_multiplier)
        """
        if confidence is None:
            confidence = self.compute_confidence()

        # Use shared VarianceConfidence if available
        if self._variance_confidence is not None:
            # Override the confidence in shared tracker
            self._variance_confidence._confidence = confidence
            should_apply, mult = self._variance_confidence.should_brake(confidence)
            if should_apply:
                self.brake_applied_count += 1
            return should_apply, mult

        # Fallback: inline braking logic
        if confidence < self.confidence_threshold:
            self.brake_applied_count += 1
            # Graduated braking: lower confidence = stronger brake
            if confidence < 0.3:
                lr_mult = 0.6
            elif confidence < 0.4:
                lr_mult = 0.7
            else:
                lr_mult = self.lr_reduction
            return True, lr_mult

        return False, 1.0

    def get_status_icon(self, confidence: float) -> str:
        """Get status icon for confidence level."""
        if self._variance_confidence is not None:
            return self._variance_confidence.get_status_icon(confidence)

        # Fallback
        if confidence >= 0.7:
            return "\U0001f7e2"
        elif confidence >= 0.5:
            return "\U0001f7e1"
        elif confidence >= 0.3:
            return "\U0001f7e0"
        else:
            return "\U0001f534"

    def format_status(self, confidence: float = None) -> str:
        """Format status for logging."""
        if confidence is None:
            confidence = self.compute_confidence()

        if self._variance_confidence is not None:
            self._variance_confidence._confidence = confidence
            return self._variance_confidence.format_status(confidence)

        # Fallback
        icon = self.get_status_icon(confidence)
        brake, lr_mult = self.should_brake(confidence)

        if brake:
            return f"Conf:{confidence:.2f}{icon} LR\u00d7{lr_mult:.2f} [BRAKE]"
        return f"Conf:{confidence:.2f}{icon}"
