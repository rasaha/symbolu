"""
SymbolU12 Axiomatic Trigger Detection
======================================

Detects violations of the three primary axioms in real-time:

1. Identity Breach (A ≠ A):
   - Triggered when τ < 0.3 while in Pramāṇa mode
   - Self-contradiction detected in R_internal

2. Causal Disconnect (Grounding Failure):
   - Triggered when Entropy spikes >50% in single step
   - Model generating effects without traceable causes

3. Boundary Collision (Category Error):
   - Triggered when Bhava shifts >45° toward Vikalpa
   - Model asked to perform action outside ontology

These triggers are the "circuit breakers" that illuminate
when the model's Axiomatic Shield activates.
"""

from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from enum import Enum
import time
import math

from .data_stream import (
    AlertLevel,
    AxiomType,
    AlertSnapshot,
    StateSnapshot,
    BhavaSnapshot,
    DynamicsSnapshot,
)


# =============================================================================
# TRIGGER THRESHOLDS
# =============================================================================

@dataclass
class TriggerThresholds:
    """Configurable thresholds for axiomatic triggers."""

    # Identity Breach
    identity_trace_critical: float = 0.30
    identity_requires_pramana: bool = True

    # Causal Disconnect
    entropy_spike_threshold: float = 0.50  # 50% increase
    entropy_absolute_max: float = 0.90

    # Boundary Collision
    vikalpa_angle_threshold: float = 45.0  # degrees
    vikalpa_index: int = 4  # Index of speculative Bhava

    # Phase-Lock
    phase_lock_threshold: float = 0.75
    phase_lock_warning: float = 0.60

    # Determinant drift
    determinant_drift_threshold: float = 0.05

    # Cognitive dissonance (high confidence + low trace)
    dissonance_confidence_min: float = 0.70
    dissonance_trace_max: float = 0.50


# =============================================================================
# TRIGGER RESULT
# =============================================================================

@dataclass
class TriggerResult:
    """Result of a trigger check."""
    triggered: bool = False
    axiom_type: AxiomType = AxiomType.NONE
    level: AlertLevel = AlertLevel.NORMAL
    message: str = ""
    details: Dict[str, Any] = field(default_factory=dict)

    def to_alert(self, trace: float) -> AlertSnapshot:
        """Convert to AlertSnapshot."""
        return AlertSnapshot(
            level=self.level,
            axiom_type=self.axiom_type,
            message=self.message,
            trace_at_trigger=trace,
            timestamp=time.time(),
        )


# =============================================================================
# TRIGGER DETECTORS
# =============================================================================

class IdentityBreachDetector:
    """
    Detects Identity Axiom violations (A ≠ A).

    Triggers when:
    - Trace (τ) falls below critical threshold (0.30)
    - Model is in Pramāṇa (factual) mode
    - Self-contradiction detected in internal state

    Visual: Cyan flash on Identity axis of radar chart.
    """

    def __init__(self, thresholds: TriggerThresholds):
        self.thresholds = thresholds
        self.consecutive_violations = 0

    def check(
        self,
        trace: float,
        vritti_mode: str,
        dominant_bhava: str,
    ) -> TriggerResult:
        """Check for Identity Breach."""
        result = TriggerResult()

        # Must be in Pramāṇa mode for Identity Breach
        in_pramana = vritti_mode == 'Pramāṇa' or dominant_bhava == 'factual'

        if not self.thresholds.identity_requires_pramana:
            in_pramana = True

        if trace < self.thresholds.identity_trace_critical and in_pramana:
            self.consecutive_violations += 1

            result.triggered = True
            result.axiom_type = AxiomType.IDENTITY
            result.level = AlertLevel.CRITICAL
            result.message = "AXIOM_VIOLATION: IDENTITY_LOOP - Self-contradiction detected"
            result.details = {
                'trace': trace,
                'vritti_mode': vritti_mode,
                'consecutive': self.consecutive_violations,
                'visual': 'CYAN_FLASH',
            }
        else:
            self.consecutive_violations = 0

        return result


class CausalDisconnectDetector:
    """
    Detects Causality Axiom violations (Grounding Failure).

    Triggers when:
    - Entropy (d[1]) increases >50% in single token step
    - Model generating effects without traceable causes
    - Smṛti (memory) cannot ground the claim

    Visual: Magenta warning on Entropy gauge.
    """

    def __init__(self, thresholds: TriggerThresholds):
        self.thresholds = thresholds
        self.last_entropy: Optional[float] = None

    def check(
        self,
        current_entropy: float,
        dynamics: DynamicsSnapshot,
    ) -> TriggerResult:
        """Check for Causal Disconnect."""
        result = TriggerResult()

        # Check entropy spike
        if self.last_entropy is not None:
            entropy_delta = current_entropy - self.last_entropy
            entropy_ratio = entropy_delta / max(self.last_entropy, 0.01)

            if entropy_ratio > self.thresholds.entropy_spike_threshold:
                result.triggered = True
                result.axiom_type = AxiomType.CAUSALITY
                result.level = AlertLevel.WARNING
                result.message = "AXIOM_VIOLATION: CAUSAL_VOID - Grounding failure detected"
                result.details = {
                    'entropy_before': self.last_entropy,
                    'entropy_after': current_entropy,
                    'spike_ratio': entropy_ratio,
                    'visual': 'MAGENTA_WARNING',
                }

        # Also check absolute entropy
        if current_entropy > self.thresholds.entropy_absolute_max:
            result.triggered = True
            result.axiom_type = AxiomType.CAUSALITY
            result.level = AlertLevel.CRITICAL
            result.message = "AXIOM_VIOLATION: ENTROPY_OVERFLOW - Cognitive chaos detected"
            result.details = {
                'entropy': current_entropy,
                'threshold': self.thresholds.entropy_absolute_max,
                'visual': 'MAGENTA_FLASH',
            }

        self.last_entropy = current_entropy
        return result

    def reset(self):
        """Reset state for new conversation."""
        self.last_entropy = None


class BoundaryCollisionDetector:
    """
    Detects Category Error violations (Boundary Collision).

    Triggers when:
    - Bhava vector shifts >45° toward Vikalpa axis in one step
    - Model asked to perform action outside its ontology
    - Category mixing detected (e.g., "color of number 5")

    Visual: Amber pulse across entire 124-dim manifold.
    """

    def __init__(self, thresholds: TriggerThresholds):
        self.thresholds = thresholds
        self.last_bhava: Optional[List[float]] = None

    def check(
        self,
        bhava: BhavaSnapshot,
    ) -> TriggerResult:
        """Check for Boundary Collision."""
        result = TriggerResult()
        current_bhava = bhava.to_list()

        if self.last_bhava is not None:
            # Compute angle shift toward Vikalpa
            angle_shift = self._compute_vikalpa_angle_shift(
                self.last_bhava, current_bhava
            )

            if angle_shift > self.thresholds.vikalpa_angle_threshold:
                result.triggered = True
                result.axiom_type = AxiomType.CATEGORY
                result.level = AlertLevel.WARNING
                result.message = "AXIOM_VIOLATION: CATEGORY_SHIFT - Boundary collision detected"
                result.details = {
                    'angle_shift': angle_shift,
                    'threshold': self.thresholds.vikalpa_angle_threshold,
                    'vikalpa_before': self.last_bhava[self.thresholds.vikalpa_index],
                    'vikalpa_after': current_bhava[self.thresholds.vikalpa_index],
                    'visual': 'AMBER_PULSE',
                }

        self.last_bhava = current_bhava
        return result

    def _compute_vikalpa_angle_shift(
        self,
        before: List[float],
        after: List[float],
    ) -> float:
        """Compute angle of shift toward Vikalpa axis."""
        vikalpa_idx = self.thresholds.vikalpa_index

        # Vector from old to new position
        delta = [after[i] - before[i] for i in range(len(before))]

        # Unit vector toward Vikalpa
        vikalpa_unit = [0.0] * len(before)
        vikalpa_unit[vikalpa_idx] = 1.0

        # Compute angle
        dot_product = sum(d * v for d, v in zip(delta, vikalpa_unit))
        delta_magnitude = math.sqrt(sum(d * d for d in delta))

        if delta_magnitude < 0.001:
            return 0.0

        cos_angle = dot_product / delta_magnitude
        cos_angle = max(-1.0, min(1.0, cos_angle))  # Clamp for acos

        angle_rad = math.acos(cos_angle)
        angle_deg = math.degrees(angle_rad)

        # We want shift TOWARD Vikalpa, so take complement
        return 90.0 - angle_deg if cos_angle > 0 else 0.0

    def reset(self):
        """Reset state for new conversation."""
        self.last_bhava = None


class PhaseLockDetector:
    """
    Detects Phase-Lock violations.

    Triggers when:
    - Trace falls below threshold (0.75)
    - R_internal and R_external are misaligned

    Visual: Phase-Lock trigger light flashes.
    """

    def __init__(self, thresholds: TriggerThresholds):
        self.thresholds = thresholds

    def check(
        self,
        trace: float,
        confidence: float,
    ) -> TriggerResult:
        """Check for Phase-Lock violation."""
        result = TriggerResult()

        if trace < self.thresholds.phase_lock_threshold:
            if trace < self.thresholds.identity_trace_critical:
                result.level = AlertLevel.EMERGENCY
                result.message = "PHASE_LOCK: CRITICAL - Epistemic death imminent"
            elif trace < self.thresholds.phase_lock_warning:
                result.level = AlertLevel.CRITICAL
                result.message = "PHASE_LOCK: BREACH - META transition triggered"
            else:
                result.level = AlertLevel.WARNING
                result.message = "PHASE_LOCK: WARNING - Alignment degrading"

            result.triggered = True
            result.axiom_type = AxiomType.PHASE_LOCK
            result.details = {
                'trace': trace,
                'threshold': self.thresholds.phase_lock_threshold,
                'confidence': confidence,
                'visual': 'PHASE_LOCK_FLASH',
            }

        return result


class CognitiveDissonanceDetector:
    """
    Detects Cognitive Dissonance (high confidence + low trace).

    This is the "Honesty Ratio" check - if the model is confident
    but its internal state is misaligned, something is wrong.

    Triggers when:
    - Confidence (d[2]) > 0.70
    - Trace (τ) < 0.50
    """

    def __init__(self, thresholds: TriggerThresholds):
        self.thresholds = thresholds

    def check(
        self,
        trace: float,
        confidence: float,
    ) -> TriggerResult:
        """Check for Cognitive Dissonance."""
        result = TriggerResult()

        high_confidence = confidence > self.thresholds.dissonance_confidence_min
        low_trace = trace < self.thresholds.dissonance_trace_max

        if high_confidence and low_trace:
            result.triggered = True
            result.axiom_type = AxiomType.PHASE_LOCK
            result.level = AlertLevel.CRITICAL
            result.message = "COGNITIVE_DISSONANCE: High confidence with low trace"
            result.details = {
                'confidence': confidence,
                'trace': trace,
                'honesty_ratio': trace / max(confidence, 0.01),
                'visual': 'DISSONANCE_FLASH',
            }

        return result


# =============================================================================
# UNIFIED TRIGGER SYSTEM
# =============================================================================

class AxiomaticTriggerSystem:
    """
    Unified system for detecting all axiomatic violations.

    Combines all detectors and provides a single interface
    for the dashboard to check for alerts.
    """

    def __init__(self, thresholds: Optional[TriggerThresholds] = None):
        self.thresholds = thresholds or TriggerThresholds()

        # Initialize detectors
        self.identity_detector = IdentityBreachDetector(self.thresholds)
        self.causal_detector = CausalDisconnectDetector(self.thresholds)
        self.boundary_detector = BoundaryCollisionDetector(self.thresholds)
        self.phase_lock_detector = PhaseLockDetector(self.thresholds)
        self.dissonance_detector = CognitiveDissonanceDetector(self.thresholds)

        # Alert history
        self.alert_history: List[AlertSnapshot] = []
        self.max_history = 1000

    def check_all(
        self,
        snapshot: StateSnapshot,
    ) -> AlertSnapshot:
        """
        Check all triggers against a state snapshot.

        Returns the highest-priority alert found.
        """
        alerts = []

        # Check Phase-Lock first (most critical)
        phase_result = self.phase_lock_detector.check(
            snapshot.trace,
            snapshot.dynamics.confidence,
        )
        if phase_result.triggered:
            alerts.append(phase_result)

        # Check Identity Breach
        identity_result = self.identity_detector.check(
            snapshot.trace,
            snapshot.vritti_mode,
            snapshot.dominant_bhava,
        )
        if identity_result.triggered:
            alerts.append(identity_result)

        # Check Causal Disconnect
        causal_result = self.causal_detector.check(
            snapshot.dynamics.entropy,
            snapshot.dynamics,
        )
        if causal_result.triggered:
            alerts.append(causal_result)

        # Check Boundary Collision
        boundary_result = self.boundary_detector.check(snapshot.bhava)
        if boundary_result.triggered:
            alerts.append(boundary_result)

        # Check Cognitive Dissonance
        dissonance_result = self.dissonance_detector.check(
            snapshot.trace,
            snapshot.dynamics.confidence,
        )
        if dissonance_result.triggered:
            alerts.append(dissonance_result)

        # Return highest priority alert
        if alerts:
            # Sort by severity
            level_priority = {
                AlertLevel.EMERGENCY: 0,
                AlertLevel.CRITICAL: 1,
                AlertLevel.WARNING: 2,
                AlertLevel.NORMAL: 3,
            }
            alerts.sort(key=lambda a: level_priority[a.level])
            highest = alerts[0]
            alert = highest.to_alert(snapshot.trace)

            # Store in history
            self.alert_history.append(alert)
            if len(self.alert_history) > self.max_history:
                self.alert_history.pop(0)

            return alert

        return AlertSnapshot()

    def reset(self):
        """Reset all detectors for new conversation."""
        self.causal_detector.reset()
        self.boundary_detector.reset()
        self.alert_history.clear()

    def get_alert_summary(self) -> Dict[str, int]:
        """Get summary of recent alerts by type."""
        summary = {t.value: 0 for t in AxiomType}
        for alert in self.alert_history:
            summary[alert.axiom_type.value] += 1
        return summary

    def get_recent_alerts(self, n: int = 10) -> List[AlertSnapshot]:
        """Get most recent alerts."""
        return self.alert_history[-n:]


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    'TriggerThresholds',
    'TriggerResult',
    'IdentityBreachDetector',
    'CausalDisconnectDetector',
    'BoundaryCollisionDetector',
    'PhaseLockDetector',
    'CognitiveDissonanceDetector',
    'AxiomaticTriggerSystem',
]
