"""
Losses Module: Custom Loss Functions for Sovereign AI Training

This module provides specialized loss functions that implement
Vedic-inspired self-regulation mechanisms.

Available Loss Functions:
- KoshaGyroscopicLoss: Homeostatic balance loss with Vijnana Gate
- InvertedCurriculumController: Manages Instructor -> Self-Learning transition
"""

from symbolu_training.losses.kosha_gyroscope import (
    KoshaGyroscopicLoss,
    KoshaGyroscopeConfig,
    InvertedCurriculumController,
    VrittiResonanceLoss,
    VrittiResonanceConfig,
    # Inference-time guardrails (v2.4.0)
    KoshaPhaseCorrector,
    KoshaPhaseCorrectorConfig,
    InferenceGuardrail,
    # 32D State Regularization (v2.3.3)
    SovereignStateRegularizer,
    SovereignStateRegularizerConfig,
)

__all__ = [
    'KoshaGyroscopicLoss',
    'KoshaGyroscopeConfig',
    'InvertedCurriculumController',
    'VrittiResonanceLoss',
    'VrittiResonanceConfig',
    # Inference-time guardrails (v2.4.0)
    'KoshaPhaseCorrector',
    'KoshaPhaseCorrectorConfig',
    'InferenceGuardrail',
    # 32D State Regularization (v2.3.3)
    'SovereignStateRegularizer',
    'SovereignStateRegularizerConfig',
]
