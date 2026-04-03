"""
Acoustic Safety — Governance facade for P13 acoustic safety envelope.

Re-exports the P13 acoustic safety resolver from symbolu_core.mechanical.
P13 is the "last safety lock before sound" — it enforces absolute bounds
on acoustic parameters and detects:

  - Emotion amplification
  - Certainty escalation
  - Authority signaling
  - Excessive variance
  - Prosodic manipulation

Any violation at CRITICAL level results in acoustic parameter clamping.
"""

from symbolu_core.mechanical.pipeline.p13_acoustic_safety.p13_acoustic_safety_schema import (
    AcousticSafetyEnvelope,
    AcousticRiskLevel,
    SafetyViolation,
)
from symbolu_core.mechanical.pipeline.p13_acoustic_safety.p13_acoustic_safety_resolver import (
    P13AcousticSafetyResolver,
    detect_emotion_amplification,
    detect_certainty_escalation,
    detect_authority_signaling,
    detect_excessive_variance,
    detect_prosodic_manipulation,
)

__all__ = [
    "AcousticSafetyEnvelope",
    "AcousticRiskLevel",
    "SafetyViolation",
    "P13AcousticSafetyResolver",
    "detect_emotion_amplification",
    "detect_certainty_escalation",
    "detect_authority_signaling",
    "detect_excessive_variance",
    "detect_prosodic_manipulation",
]
