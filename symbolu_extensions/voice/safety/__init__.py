"""
Voice Safety Package.

This package provides safety-aware voice response processing,
applying Sentinel's safety contracts to voice output.

Features:
- Verbal confirmation requests before risky actions
- Safety disclaimers and warnings
- Escalation to human operators when needed

Usage:
    from symbolu_extensions.voice.safety import SafetyVoiceGate

    gate = SafetyVoiceGate()
    gated_response = await gate.process(response)

    if gated_response.requires_confirmation:
        # Wait for user confirmation
        pass
"""

from .gate import (
    SafetyAction,
    SafetyEvaluation,
    SafetyGateConfig,
    SafetyVoiceGate,
)

__all__ = [
    "SafetyAction",
    "SafetyEvaluation",
    "SafetyGateConfig",
    "SafetyVoiceGate",
]
