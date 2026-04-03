"""
Renderer Compliance Module

This module provides the complete framework for validating renderer
compliance with P13 Acoustic Safety Envelope constraints.

Contents:
- renderer_contract: Contract schemas (RendererInputContract, AcousticRenderIntent)
- mock_renderer: Mock renderers for testing (CompliantRenderer, unsafe renderers)
- renderer_compliance_checker: Compliance validation (RendererComplianceChecker)

CRITICAL ARCHITECTURAL INVARIANT:
    Any renderer violating this contract is UNSAFE BY DEFINITION.
    No renderer can violate P13 without being detected and blocked.

Usage:
    from symbolu_core.mechanical.pipeline.renderer_compliance import (
        RendererInputContract,
        AcousticRenderIntent,
        RendererComplianceChecker,
        CompliantRenderer,
        check_compliance,
    )

    # Create contract from P13 envelope
    contract = RendererInputContract(
        p10_acoustic=p10_frame,
        p13_envelope=p13_envelope,
    )

    # Render with compliant renderer
    renderer = CompliantRenderer()
    intent = renderer.render(contract)

    # Check compliance
    result = check_compliance(p13_envelope, intent)
    assert result.passed()
"""

from symbolu_core.mechanical.pipeline.renderer_compliance.renderer_contract import (
    # Version
    RENDERER_CONTRACT_VERSION,
    # Enums
    RenderIntentCategory,
    ComplianceVerdict,
    ViolationCategory,
    # Dataclasses
    AcousticRenderIntent,
    ComplianceViolation,
    ComplianceResult,
    RendererInputContract,
)

from symbolu_core.mechanical.pipeline.renderer_compliance.mock_renderer import (
    # Constants
    BOUNDARY_EPSILON_PITCH,
    BOUNDARY_EPSILON_ENERGY,
    BOUNDARY_EPSILON_VARIANCE,
    # Base class
    MockRenderer,
    # Implementations
    CompliantRenderer,
    AmplifyingRenderer,
    AuthorityRenderer,
    EmotiveRenderer,
    IgnoreSafetyRenderer,
    BoundaryPusherRenderer,
    ExactBoundaryRenderer,
    BlockedOverrideRenderer,
)

from symbolu_core.mechanical.pipeline.renderer_compliance.renderer_compliance_checker import (
    # Version
    COMPLIANCE_CHECKER_VERSION,
    # Classes
    RendererComplianceChecker,
    # Functions
    check_compliance,
    is_compliant,
)


__all__ = [
    # Versions
    "RENDERER_CONTRACT_VERSION",
    "COMPLIANCE_CHECKER_VERSION",
    # Constants
    "BOUNDARY_EPSILON_PITCH",
    "BOUNDARY_EPSILON_ENERGY",
    "BOUNDARY_EPSILON_VARIANCE",
    # Enums
    "RenderIntentCategory",
    "ComplianceVerdict",
    "ViolationCategory",
    # Contract dataclasses
    "AcousticRenderIntent",
    "ComplianceViolation",
    "ComplianceResult",
    "RendererInputContract",
    # Renderer classes
    "MockRenderer",
    "CompliantRenderer",
    "AmplifyingRenderer",
    "AuthorityRenderer",
    "EmotiveRenderer",
    "IgnoreSafetyRenderer",
    "BoundaryPusherRenderer",
    "ExactBoundaryRenderer",
    "BlockedOverrideRenderer",
    # Checker classes
    "RendererComplianceChecker",
    # Functions
    "check_compliance",
    "is_compliant",
]
