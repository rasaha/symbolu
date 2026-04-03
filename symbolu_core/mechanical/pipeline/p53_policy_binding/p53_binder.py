"""
Phase 53: External Policy Binding Layer - Core Binding Logic

This module contains the core binding logic for P53.
It binds external governance decisions without interpretation or enforcement.

P53 is a plug, not a judge.

What P53 Actually Does:
    1. Checks if a GovernanceResponse exists
    2. If absent: Emits GovernanceBindingEnvelope(bound=False, ...)
    3. If present:
        - Validates structure only
        - Stores response verbatim
        - Marks bound=True

That is all.
"""

from typing import Optional

from symbolu_core.mechanical.pipeline.p52_governance_adapter import (
    GovernanceResponse,
)

from .p53_schema import (
    GovernanceBindingEnvelope,
    VALID_GOVERNANCE_DECISIONS,
    create_unbound_envelope,
)


class GovernanceResponseValidationError(Exception):
    """Raised when GovernanceResponse structure is invalid."""

    pass


def validate_governance_response_structure(
    response: GovernanceResponse,
) -> None:
    """
    Validate the structure of a GovernanceResponse.

    This performs STRUCTURAL validation only:
        - decision is present and valid
        - rationale_codes is present and is tuple-like
        - audit_reference exists (can be None)

    This does NOT:
        - Interpret the meaning of decision
        - Evaluate rationale codes
        - Check authority correctness
        - Validate business logic

    Args:
        response: The GovernanceResponse to validate

    Raises:
        GovernanceResponseValidationError: If structure is invalid
    """
    # Validate decision field exists and is valid
    if not hasattr(response, "decision"):
        raise GovernanceResponseValidationError(
            "GovernanceResponse missing required field: decision"
        )
    if response.decision not in VALID_GOVERNANCE_DECISIONS:
        raise GovernanceResponseValidationError(
            f"Invalid decision value: {response.decision}. "
            f"Must be one of {sorted(VALID_GOVERNANCE_DECISIONS)}"
        )

    # Validate rationale_codes field exists
    if not hasattr(response, "rationale_codes"):
        raise GovernanceResponseValidationError(
            "GovernanceResponse missing required field: rationale_codes"
        )
    # rationale_codes must be iterable (tuple, list, etc.)
    try:
        tuple(response.rationale_codes)
    except TypeError:
        raise GovernanceResponseValidationError(
            "rationale_codes must be iterable"
        )

    # Validate audit_reference field exists (can be None)
    if not hasattr(response, "audit_reference"):
        raise GovernanceResponseValidationError(
            "GovernanceResponse missing required field: audit_reference"
        )


def bind_governance_response(
    response: Optional[GovernanceResponse],
    authority_id: Optional[str] = None,
) -> GovernanceBindingEnvelope:
    """
    Bind an external governance response to the pipeline.

    This is the core binding function. It:
        1. Checks if a response exists
        2. If absent: Returns unbound envelope
        3. If present: Validates structure and binds verbatim

    Args:
        response: The GovernanceResponse to bind (None if absent)
        authority_id: Opaque authority identifier (no parsing, no validation)

    Returns:
        GovernanceBindingEnvelope with binding status

    Raises:
        GovernanceResponseValidationError: If response structure is invalid
    """
    # Case 1: No governance response exists
    if response is None:
        return create_unbound_envelope()

    # Case 2: Governance response exists - validate structure
    validate_governance_response_structure(response)

    # Case 3: Structure valid - bind verbatim
    return GovernanceBindingEnvelope(
        bound=True,
        decision=response.decision,
        rationale_codes=tuple(response.rationale_codes),
        audit_reference=response.audit_reference,
        authority_id=authority_id,
    )


def run_p53_directly(
    response: Optional[GovernanceResponse],
    authority_id: Optional[str] = None,
) -> GovernanceBindingEnvelope:
    """
    Direct entry point for P53 binding.

    This function allows direct invocation of P53 logic without
    going through the pipeline context.

    Args:
        response: The GovernanceResponse to bind (None if absent)
        authority_id: Opaque authority identifier

    Returns:
        GovernanceBindingEnvelope with binding status

    Raises:
        GovernanceResponseValidationError: If response structure is invalid
    """
    return bind_governance_response(response, authority_id)


# Public exports
__all__ = [
    # Exceptions
    "GovernanceResponseValidationError",
    # Validation
    "validate_governance_response_structure",
    # Core binding
    "bind_governance_response",
    # Direct entry point
    "run_p53_directly",
]
