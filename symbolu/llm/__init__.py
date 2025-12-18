"""
Symbol-U LLM Interface Layer
============================

Defines the one-way authority boundary between Symbol-U Core
(deterministic authority) and LLM Layer (optional renderer).

Contract: docs/contracts/SYMBOLU_LLM_INTERFACE_CONTRACT.md

This module enforces:
- No hallucination of structure
- No override of constraints
- No upstream feedback
- All violations are CI-detectable
"""

from symbolu.llm.types import (
    RenderMode,
    ContractViolationType,
    Envelope,
    Constraints,
    TargetConstraints,
    Provenance,
    RenderHints,
    AuthoritativePayload,
    TrajectoryStep,
    Phase7Result,
    RenderRequest,
    OutputItem,
    Assertions,
    RenderResponse,
    ContractViolation,
    ValidationResult,
)

from symbolu.llm.validator import (
    validate_llm_response,
    validate_tokens,
    validate_layers,
    validate_forbidden_phrases,
    validate_provenance,
    validate_no_selection,
    validate_no_governance_override,
)

__all__ = [
    # Types
    "RenderMode",
    "ContractViolationType",
    "Envelope",
    "Constraints",
    "TargetConstraints",
    "Provenance",
    "RenderHints",
    "AuthoritativePayload",
    "TrajectoryStep",
    "Phase7Result",
    "RenderRequest",
    "OutputItem",
    "Assertions",
    "RenderResponse",
    "ContractViolation",
    "ValidationResult",
    # Validators
    "validate_llm_response",
    "validate_tokens",
    "validate_layers",
    "validate_forbidden_phrases",
    "validate_provenance",
    "validate_no_selection",
    "validate_no_governance_override",
]
