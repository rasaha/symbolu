#!/usr/bin/env python3
"""
Sovereign State Monitor
========================

Real-time monitoring and analysis of the 32D Sovereign State during inference.

CRITICAL DESIGN INVARIANT:
    This monitor is PURELY OBSERVATIONAL. It must NEVER influence generation.
    - Observational: Reads state tensors (always detached from computation graph)
    - Diagnostic: Provides metrics and warnings for logging/display
    - Logged/Surfaced: Results are for human review and debugging only
    - NEVER fed back into the forward pass
    - NEVER used to modify logits, sampling, or token selection
    - NEVER used to abort generation (warnings are informational only)

The 32D Sovereign State structure (V11.0.0 Three-Plane Separation):
- [0:12]  - 12 Bhavas (Phase Plane → ΔBhava → IntentPhaseProjector → θ)
- [12:17] - 5 Koshas (Control Plane → Sovereign Bridge → depth control)
- [17:22] - 5 Vrittis (Control Plane → Sovereign Bridge → quality gating)
- [22:28] - 6 Gunas (Control Plane → Sovereign Bridge → stability signals)
- [28:32] - 4 Reserved (Learning Plane → JEPA only, NOT consumed at inference)

V11.0.0 Inference Filter Table:
  CSR:      YES — CSRInferenceGuard in InferenceManager
  Ontology: Validate only — THIS monitor (observe-only, never modifies generation)
  JEPA:     NO — Reserved[28:32] excluded from inference decisions
  Kosha:    YES — Active depth control in OntologicalBindingCacheInferenceEngine
  Vritti:   YES (CRITICAL) — Active hallucination gating via Sovereign Bridge

Training Reference: symbolu/phase_transformer.py (OntologicalBindingCacheTransformer)

Author: Sovereign-1 Training Initiative
Date: January 2026 (V11.0.0 update: February 2026)
"""

import torch
from typing import Dict, List, Optional, Tuple, Any, Union
from dataclasses import dataclass
from enum import Enum


# ============================================================================
# SOVEREIGN STATE CONSTANTS (from phase_transformer.py)
# ============================================================================

SOVEREIGN_STATE_DIM = 32

# Slice definitions for state components
BHAVA_SLICE = slice(0, 12)
KOSHA_SLICE = slice(12, 17)
VRITTI_SLICE = slice(17, 22)
GUNA_SLICE = slice(22, 28)
RESERVED_SLICE = slice(28, 32)

# Bhava names - 12 Ontological Aspects
BHAVA_NAMES = [
    'POT',   # 0: Potential - latent possibility
    'IDN',   # 1: Identity - self-recognition
    'EXE',   # 2: Execution - action/manifestation
    'STR',   # 3: Structure - form/organization
    'COG',   # 4: Cognition - knowing/understanding
    'AGY',   # 5: Agency - will/intention
    'RSN',   # 6: Reason - logic/analysis
    'PRP',   # 7: Purpose - meaning/direction
    'WIT',   # 8: Witness - observation/awareness
    'UNI',   # 9: Unity - integration/wholeness
    'INT',   # 10: Intent - focused will
    'ABS',   # 11: Absolute - transcendent ground
]

BHAVA_FULL_NAMES = [
    'Potential',
    'Identity',
    'Execution',
    'Structure',
    'Cognition',
    'Agency',
    'Reason',
    'Purpose',
    'Witness',
    'Unity',
    'Intent',
    'Absolute',
]

# Kosha names - 5 Consciousness Sheaths (depth mapping)
KOSHA_NAMES = [
    'MATERIAL',      # 12: Physicality/Syntax
    'VITAL',         # 13: Flow/Energy
    'MENTAL',        # 14: Semantics/Meaning
    'INTELLECTUAL',  # 15: Pattern/Wisdom
    'BLISSFUL',      # 16: Unity/Integration
]

# Vritti names - 5 Mental Modifications (reliability mapping)
VRITTI_NAMES = [
    'FACT',          # 17: Verified Truth (Pramāṇa)
    'ERROR',         # 18: Hallucination (Viparyaya)
    'IMAGINATION',   # 19: Conceptualization (Vikalpa)
    'VOID',          # 20: Null State (Nidrā)
    'MEMORY',        # 21: Recall/Weights (Smṛti)
]

# Guna names - 6 Energy States/Dynamics
GUNA_NAMES = [
    'LUCIDITY',   # 22: Clarity/Precision (Sattva-like)
    'ACTIVITY',   # 23: Dynamism/Turbulence (Rajas-like)
    'STABILITY',  # 24: Inertia/Fixedness (Tamas-like)
    'VELOCITY',   # 25: Rate of state change
    'ACCEL',      # 26: Acceleration of change
    'STABLE',     # 27: Stability measure
]

# Reserved names - Toroidal Feedback
RESERVED_NAMES = ['VOID_0', 'VOID_1', 'VOID_2', 'VOID_3']


class DepthLevel(Enum):
    """Consciousness depth levels based on Kosha."""
    MATERIAL = 0      # Surface syntax processing
    VITAL = 1         # Energy flow awareness
    MENTAL = 2        # Semantic understanding
    INTELLECTUAL = 3  # Pattern wisdom
    BLISSFUL = 4      # Unified integration


class ReliabilityLevel(Enum):
    """Output reliability based on Vritti."""
    FACT = 0          # Verified truth - high confidence
    ERROR = 1         # Hallucination risk - low confidence
    IMAGINATION = 2   # Creative conceptualization
    VOID = 3          # Null/undefined state
    MEMORY = 4        # Recall from weights


@dataclass
class SovereignStateMetrics:
    """
    Comprehensive metrics for a 32D Sovereign State.

    Provides human-readable analysis of:
    - Bhava activations (ontological aspects)
    - Kosha depth (consciousness level)
    - Vritti reliability (output trustworthiness)
    - Guna dynamics (energy state)
    """
    # Bhava analysis
    dominant_bhava: str
    bhava_activations: Dict[str, float]
    bhava_entropy: float

    # Kosha analysis
    depth_level: DepthLevel
    kosha_profile: Tuple[float, ...]
    depth_confidence: float

    # Vritti analysis (reliability)
    vritti_dominant: ReliabilityLevel
    fact_confidence: float
    error_risk: float
    imagination_level: float
    vritti_profile: Tuple[float, ...]

    # Guna dynamics
    lucidity: float
    turbulence: float
    stability: float
    velocity: float
    acceleration: float

    # Reserved (toroidal feedback)
    toroidal_feedback: Tuple[float, ...]

    # Aggregate scores
    coherence_estimate: float
    reliability_score: float

    def get_summary(self) -> str:
        """Get human-readable summary."""
        lines = [
            f"Sovereign State Analysis:",
            f"  Dominant Bhava: {self.dominant_bhava} (entropy: {self.bhava_entropy:.2f})",
            f"  Depth Level: {self.depth_level.name} (conf: {self.depth_confidence:.2f})",
            f"  Reliability: {self.vritti_dominant.name} (fact: {self.fact_confidence:.2f}, error: {self.error_risk:.2f})",
            f"  Dynamics: lucid={self.lucidity:.2f}, turbulent={self.turbulence:.2f}, stable={self.stability:.2f}",
            f"  Overall: coherence={self.coherence_estimate:.2f}, reliability={self.reliability_score:.2f}",
        ]
        return "\n".join(lines)

    def get_status_line(self) -> str:
        """Get compact status line."""
        return (
            f"Bhava:{self.dominant_bhava}|"
            f"Depth:{self.depth_level.name[:4]}|"
            f"Rel:{self.vritti_dominant.name[:4]}|"
            f"L:{self.lucidity:.1f}T:{self.turbulence:.1f}S:{self.stability:.1f}"
        )


class SovereignStateMonitor:
    """
    Monitor and analyze 32D Sovereign State during inference.

    ╔════════════════════════════════════════════════════════════════════════════╗
    ║  CRITICAL INVARIANT: This monitor must NEVER influence generation.         ║
    ║                                                                            ║
    ║  This component is:                                                        ║
    ║    ✓ Observational - reads state tensors, never modifies them              ║
    ║    ✓ Diagnostic - provides metrics and warnings for logging/display        ║
    ║    ✓ Logged/Surfaced - results are for human review and debugging          ║
    ║    ✗ NEVER fed back into the forward pass                                  ║
    ║    ✗ NEVER used to modify logits, sampling, or token selection             ║
    ║    ✗ NEVER used to abort generation (warnings are informational only)      ║
    ║                                                                            ║
    ║  All state analysis uses .detach().cpu() to ensure complete decoupling     ║
    ║  from the computation graph. If you need to influence generation based     ║
    ║  on state, use a separate component (e.g., CSRInferenceGuard).             ║
    ╚════════════════════════════════════════════════════════════════════════════╝

    Provides:
    - Real-time state analysis
    - Trajectory tracking
    - Reliability assessment
    - Depth estimation
    - Warning detection (informational only, does not influence generation)

    Example:
        monitor = SovereignStateMonitor()

        for state in generation_states:
            metrics = monitor.analyze_state(state)
            print(metrics.get_status_line())

            # Warnings are INFORMATIONAL ONLY - do not use to abort/modify generation
            if metrics.error_risk > 0.5:
                print("Warning: High hallucination risk!")

        trajectory = monitor.get_state_trajectory()
        print(f"Depth progression: {[s.depth_level.name for s in trajectory]}")
    """

    def __init__(self, warn_thresholds: Optional[Dict[str, float]] = None):
        """
        Initialize state monitor.

        Args:
            warn_thresholds: Optional warning thresholds
        """
        self.warn_thresholds = warn_thresholds or {
            'error_risk': 0.5,
            'turbulence': 0.8,
            'low_lucidity': 0.2,
            'bhava_entropy': 2.0,
        }

        self._state_history: List[torch.Tensor] = []
        self._metrics_history: List[SovereignStateMetrics] = []
        self._warnings: List[Dict[str, Any]] = []
        self._device = torch.device('cpu')

    def to(self, device: Union[str, torch.device]) -> 'SovereignStateMonitor':
        """Move to device."""
        if isinstance(device, str):
            device = torch.device(device)
        self._device = device
        return self

    def analyze_state(self, state: torch.Tensor) -> SovereignStateMetrics:
        """
        Analyze a 32D Sovereign State tensor.

        NOTE: This method is READ-ONLY and OBSERVATIONAL. The returned metrics
        must NEVER be used to influence generation (modify logits, abort, etc.).
        All tensor operations use .detach().cpu() to ensure complete decoupling
        from the computation graph.

        Args:
            state: [B, 32] or [32] Sovereign State tensor

        Returns:
            metrics: Comprehensive state metrics (for logging/display only)
        """
        # Ensure 2D
        if state.dim() == 1:
            state = state.unsqueeze(0)

        # Mean over batch
        state = state.mean(dim=0)  # [32]

        # Extract components
        bhava = state[BHAVA_SLICE].detach().cpu()       # [12]
        kosha = state[KOSHA_SLICE].detach().cpu()       # [5]
        vritti = state[VRITTI_SLICE].detach().cpu()     # [5]
        guna = state[GUNA_SLICE].detach().cpu()         # [6]
        reserved = state[RESERVED_SLICE].detach().cpu() # [4]

        # Bhava analysis
        bhava_softmax = torch.softmax(bhava, dim=0)
        dominant_bhava_idx = bhava_softmax.argmax().item()
        dominant_bhava = BHAVA_NAMES[dominant_bhava_idx]

        bhava_activations = {
            name: bhava_softmax[i].item()
            for i, name in enumerate(BHAVA_NAMES)
        }

        # Bhava entropy (lower = more focused)
        bhava_entropy = -(bhava_softmax * torch.log(bhava_softmax + 1e-8)).sum().item()

        # Kosha analysis (depth level)
        kosha_softmax = torch.softmax(kosha, dim=0)
        depth_idx = kosha_softmax.argmax().item()
        depth_level = DepthLevel(depth_idx)
        depth_confidence = kosha_softmax[depth_idx].item()
        kosha_profile = tuple(kosha_softmax.tolist())

        # Vritti analysis (reliability)
        vritti_softmax = torch.softmax(vritti, dim=0)
        vritti_dominant_idx = vritti_softmax.argmax().item()
        vritti_dominant = ReliabilityLevel(vritti_dominant_idx)

        fact_confidence = vritti_softmax[0].item()  # FACT
        error_risk = vritti_softmax[1].item()       # ERROR
        imagination_level = vritti_softmax[2].item()  # IMAGINATION
        vritti_profile = tuple(vritti_softmax.tolist())

        # Guna dynamics
        guna_vals = guna.tolist()
        lucidity = guna_vals[0] if len(guna_vals) > 0 else 0.0
        turbulence = guna_vals[1] if len(guna_vals) > 1 else 0.0
        stability_val = guna_vals[2] if len(guna_vals) > 2 else 0.0
        velocity = guna_vals[3] if len(guna_vals) > 3 else 0.0
        acceleration = guna_vals[4] if len(guna_vals) > 4 else 0.0

        # Normalize guna values to [0, 1] via sigmoid
        lucidity = torch.sigmoid(torch.tensor(lucidity)).item()
        turbulence = torch.sigmoid(torch.tensor(turbulence)).item()
        stability_val = torch.sigmoid(torch.tensor(stability_val)).item()

        # Reserved (toroidal feedback)
        toroidal_feedback = tuple(reserved.tolist())

        # Aggregate scores
        # Coherence: high lucidity, low turbulence, deep depth
        coherence_estimate = (
            0.4 * lucidity +
            0.3 * (1 - turbulence) +
            0.3 * (depth_idx / 4)  # Deeper = more coherent
        )

        # Reliability: high fact, low error
        reliability_score = (
            0.6 * fact_confidence +
            0.4 * (1 - error_risk)
        )

        metrics = SovereignStateMetrics(
            dominant_bhava=dominant_bhava,
            bhava_activations=bhava_activations,
            bhava_entropy=bhava_entropy,
            depth_level=depth_level,
            kosha_profile=kosha_profile,
            depth_confidence=depth_confidence,
            vritti_dominant=vritti_dominant,
            fact_confidence=fact_confidence,
            error_risk=error_risk,
            imagination_level=imagination_level,
            vritti_profile=vritti_profile,
            lucidity=lucidity,
            turbulence=turbulence,
            stability=stability_val,
            velocity=velocity,
            acceleration=acceleration,
            toroidal_feedback=toroidal_feedback,
            coherence_estimate=coherence_estimate,
            reliability_score=reliability_score,
        )

        # Store history
        self._state_history.append(state.clone())
        self._metrics_history.append(metrics)

        # Check warnings
        self._check_warnings(metrics)

        return metrics

    def _check_warnings(self, metrics: SovereignStateMetrics) -> None:
        """
        Check for warning conditions.

        IMPORTANT: These warnings are INFORMATIONAL ONLY for logging/display.
        They must NEVER be used to abort generation or modify the forward pass.
        Callers should use these warnings for human review, debugging, or
        post-generation analysis - never for real-time generation control.
        """
        warnings_triggered = []

        if metrics.error_risk > self.warn_thresholds['error_risk']:
            warnings_triggered.append({
                'type': 'high_error_risk',
                'value': metrics.error_risk,
                'threshold': self.warn_thresholds['error_risk'],
            })

        if metrics.turbulence > self.warn_thresholds['turbulence']:
            warnings_triggered.append({
                'type': 'high_turbulence',
                'value': metrics.turbulence,
                'threshold': self.warn_thresholds['turbulence'],
            })

        if metrics.lucidity < self.warn_thresholds['low_lucidity']:
            warnings_triggered.append({
                'type': 'low_lucidity',
                'value': metrics.lucidity,
                'threshold': self.warn_thresholds['low_lucidity'],
            })

        if metrics.bhava_entropy > self.warn_thresholds['bhava_entropy']:
            warnings_triggered.append({
                'type': 'high_bhava_entropy',
                'value': metrics.bhava_entropy,
                'threshold': self.warn_thresholds['bhava_entropy'],
            })

        self._warnings.extend(warnings_triggered)

    def get_state_trajectory(self) -> List[SovereignStateMetrics]:
        """Get history of analyzed states."""
        return self._metrics_history

    def get_state_tensors(self) -> List[torch.Tensor]:
        """Get raw state tensor history."""
        return self._state_history

    def get_warnings(self) -> List[Dict[str, Any]]:
        """
        Get triggered warnings.

        Returns:
            warnings: List of warning dicts (for logging/display ONLY,
                     must NEVER be used to influence generation)
        """
        return self._warnings

    def get_reliability_trend(self, window: int = 5) -> str:
        """
        Get reliability trend over recent states.

        Args:
            window: Number of recent states to consider

        Returns:
            trend: "improving", "stable", or "declining"
        """
        if len(self._metrics_history) < 2:
            return "stable"

        recent = self._metrics_history[-window:]
        scores = [m.reliability_score for m in recent]

        if len(scores) < 2:
            return "stable"

        # Simple linear regression
        diff = scores[-1] - scores[0]
        if diff > 0.1:
            return "improving"
        elif diff < -0.1:
            return "declining"
        return "stable"

    def get_depth_progression(self) -> List[str]:
        """Get sequence of depth levels."""
        return [m.depth_level.name for m in self._metrics_history]

    def get_bhava_sequence(self) -> List[str]:
        """Get sequence of dominant Bhavas."""
        return [m.dominant_bhava for m in self._metrics_history]

    def get_average_metrics(self) -> Dict[str, float]:
        """Get average metrics over all states."""
        if not self._metrics_history:
            return {}

        return {
            'avg_coherence': sum(m.coherence_estimate for m in self._metrics_history) / len(self._metrics_history),
            'avg_reliability': sum(m.reliability_score for m in self._metrics_history) / len(self._metrics_history),
            'avg_lucidity': sum(m.lucidity for m in self._metrics_history) / len(self._metrics_history),
            'avg_turbulence': sum(m.turbulence for m in self._metrics_history) / len(self._metrics_history),
            'avg_error_risk': sum(m.error_risk for m in self._metrics_history) / len(self._metrics_history),
            'avg_fact_confidence': sum(m.fact_confidence for m in self._metrics_history) / len(self._metrics_history),
        }

    def get_status_line(self) -> str:
        """Get current status line."""
        if not self._metrics_history:
            return "SovereignState: no data"

        latest = self._metrics_history[-1]
        trend = self.get_reliability_trend()
        trend_symbol = "📈" if trend == "improving" else "📉" if trend == "declining" else "➡️"

        return f"State:{latest.dominant_bhava}|{latest.depth_level.name[:4]}|rel={latest.reliability_score:.2f}{trend_symbol}"

    def clear(self) -> None:
        """Clear all history."""
        self._state_history = []
        self._metrics_history = []
        self._warnings = []

    def get_state(self) -> Dict[str, Any]:
        """Get serializable state."""
        return {
            'metrics_history': [
                {
                    'dominant_bhava': m.dominant_bhava,
                    'depth_level': m.depth_level.name,
                    'vritti_dominant': m.vritti_dominant.name,
                    'coherence_estimate': m.coherence_estimate,
                    'reliability_score': m.reliability_score,
                }
                for m in self._metrics_history
            ],
            'warnings': self._warnings,
        }

    def load_state(self, state: Dict[str, Any]) -> None:
        """Load state from dict (partial - metrics only)."""
        self._warnings = state.get('warnings', [])


def get_sovereign_state_summary(state: torch.Tensor) -> Dict[str, float]:
    """
    Get quick summary of a Sovereign State tensor.

    Args:
        state: [B, 32] or [32] state tensor

    Returns:
        summary: Dict with component means
    """
    if state.dim() == 1:
        state = state.unsqueeze(0)

    state = state.mean(dim=0)

    return {
        'bhava_mean': state[BHAVA_SLICE].mean().item(),
        'kosha_mean': state[KOSHA_SLICE].mean().item(),
        'vritti_mean': state[VRITTI_SLICE].mean().item(),
        'guna_mean': state[GUNA_SLICE].mean().item(),
        'reserved_mean': state[RESERVED_SLICE].mean().item(),
    }
