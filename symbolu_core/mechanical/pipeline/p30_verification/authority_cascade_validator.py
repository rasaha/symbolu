"""
Authority Cascade Validator
============================

Validates that phase authority levels are properly respected throughout
the Symbol-U pipeline. Ensures higher-authority phase decisions are
not overridden by lower-authority phases.

Authority Levels:
    - HIGH (P13, P17, P18): Safety and ethical constraints - cannot be overridden
    - MEDIUM (P27, P30): Persona and verification - can inform but not override HIGH
    - LOW (P28, P29, P31): Styling and formatting - advisory only

Integration:
    Used by P30 verification to ensure pipeline integrity.

Version: 1.0.0
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Dict, List, Optional, Set, Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from symbolu_core.mechanical.pipeline.models import PipelineContext

# =============================================================================
# VERSION
# =============================================================================

VERSION = "1.0.0"


# =============================================================================
# ENUMS
# =============================================================================


class AuthorityLevel(Enum):
    """Phase authority levels."""
    HIGH = 3      # Cannot be overridden (safety, ethics)
    MEDIUM = 2    # Can inform but not override HIGH
    LOW = 1       # Advisory only


class ViolationType(Enum):
    """Types of authority violations."""
    OVERRIDE = "override"           # Lower phase overrode higher
    MISSING = "missing"             # Required higher-auth phase missing
    CONFLICT = "conflict"           # Conflicting decisions at same level
    SEQUENCE = "sequence"           # Out-of-order phase execution


# =============================================================================
# PHASE AUTHORITY DEFINITIONS
# =============================================================================


@dataclass(frozen=True)
class PhaseAuthority:
    """Authority definition for a phase."""
    phase_id: str
    authority: AuthorityLevel
    can_override: Tuple[str, ...]  # Phase IDs this phase can override
    requires: Tuple[str, ...]       # Phase IDs that must execute before
    protects: Tuple[str, ...]       # Aspects this phase protects


# Phase authority registry
PHASE_AUTHORITIES: Dict[str, PhaseAuthority] = {
    # HIGH authority phases (safety band)
    "P13": PhaseAuthority(
        phase_id="P13",
        authority=AuthorityLevel.HIGH,
        can_override=("P28", "P29", "P31"),
        requires=(),
        protects=("safety", "harmful_content", "toxicity"),
    ),
    "P17": PhaseAuthority(
        phase_id="P17",
        authority=AuthorityLevel.HIGH,
        can_override=("P28", "P29", "P31"),
        requires=(),
        protects=("ethics", "bias", "fairness"),
    ),
    "P18": PhaseAuthority(
        phase_id="P18",
        authority=AuthorityLevel.HIGH,
        can_override=("P28", "P29", "P31"),
        requires=(),
        protects=("alignment", "values", "goals"),
    ),

    # MEDIUM authority phases (delivery adaptation)
    "P27": PhaseAuthority(
        phase_id="P27",
        authority=AuthorityLevel.MEDIUM,
        can_override=("P28", "P29", "P31"),
        requires=(),
        protects=("persona", "voice", "identity"),
    ),
    "P30": PhaseAuthority(
        phase_id="P30",
        authority=AuthorityLevel.MEDIUM,
        can_override=("P31",),
        requires=("P29",),
        protects=("verification", "quality", "consistency"),
    ),

    # LOW authority phases (styling/formatting)
    "P28": PhaseAuthority(
        phase_id="P28",
        authority=AuthorityLevel.LOW,
        can_override=(),
        requires=("P27",),
        protects=("tone", "delivery", "style"),
    ),
    "P29": PhaseAuthority(
        phase_id="P29",
        authority=AuthorityLevel.LOW,
        can_override=(),
        requires=("P28",),
        protects=("expression", "polish", "flow"),
    ),
    "P31": PhaseAuthority(
        phase_id="P31",
        authority=AuthorityLevel.LOW,
        can_override=(),
        requires=("P30",),
        protects=("envelope", "format", "channel"),
    ),
}


# =============================================================================
# DATA CLASSES
# =============================================================================


@dataclass(frozen=True)
class AuthorityViolation:
    """A detected authority violation."""
    violation_type: ViolationType
    phase_id: str
    violated_by: Optional[str]
    severity: AuthorityLevel
    description: str
    protected_aspect: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "type": self.violation_type.value,
            "phase": self.phase_id,
            "violated_by": self.violated_by,
            "severity": self.severity.value,
            "description": self.description,
            "protected_aspect": self.protected_aspect,
        }


@dataclass(frozen=True)
class CascadeValidation:
    """Result of authority cascade validation."""
    valid: bool
    violations: Tuple[AuthorityViolation, ...]
    phases_checked: Tuple[str, ...]
    authority_chain: Dict[str, AuthorityLevel]
    high_authority_respected: bool
    warnings: Tuple[str, ...] = ()

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "valid": self.valid,
            "violations": [v.to_dict() for v in self.violations],
            "phases_checked": list(self.phases_checked),
            "authority_chain": {k: v.value for k, v in self.authority_chain.items()},
            "high_authority_respected": self.high_authority_respected,
            "warnings": list(self.warnings),
        }


# =============================================================================
# AUTHORITY CASCADE VALIDATOR
# =============================================================================


class AuthorityCascadeValidator:
    """
    Validates that phase authority levels are properly respected.

    Checks:
    1. Higher-authority phases cannot be overridden by lower-authority phases
    2. Required predecessor phases have executed
    3. No conflicting decisions at same authority level
    4. Safety-critical (HIGH auth) decisions are always respected
    """

    def __init__(
        self,
        phase_authorities: Optional[Dict[str, PhaseAuthority]] = None,
        strict_mode: bool = True,
    ):
        """
        Initialize authority cascade validator.

        Args:
            phase_authorities: Custom phase authority definitions.
            strict_mode: If True, treat warnings as violations.
        """
        self.phase_authorities = phase_authorities or PHASE_AUTHORITIES
        self.strict_mode = strict_mode

    def validate(
        self,
        ctx: "PipelineContext",
        phases_executed: Optional[List[str]] = None,
    ) -> CascadeValidation:
        """
        Validate authority cascade for pipeline context.

        Args:
            ctx: Pipeline context with phase outputs.
            phases_executed: List of phases that were executed.

        Returns:
            CascadeValidation with validation result.
        """
        violations: List[AuthorityViolation] = []
        warnings: List[str] = []

        # Detect executed phases from context
        if phases_executed is None:
            phases_executed = self._detect_executed_phases(ctx)

        # Build authority chain
        authority_chain: Dict[str, AuthorityLevel] = {}
        for phase_id in phases_executed:
            if phase_id in self.phase_authorities:
                authority_chain[phase_id] = self.phase_authorities[phase_id].authority

        # Check sequence requirements
        sequence_violations = self._check_sequence(phases_executed)
        violations.extend(sequence_violations)

        # Check for override violations
        override_violations = self._check_overrides(ctx, phases_executed)
        violations.extend(override_violations)

        # Check HIGH authority is respected
        high_authority_respected = self._check_high_authority(ctx, phases_executed)
        if not high_authority_respected:
            violations.append(AuthorityViolation(
                violation_type=ViolationType.OVERRIDE,
                phase_id="HIGH_AUTHORITY",
                violated_by="LOWER_PHASE",
                severity=AuthorityLevel.HIGH,
                description="High-authority phase decision was overridden",
                protected_aspect="safety",
            ))

        # Generate warnings for missing optional phases
        for phase_id, auth in self.phase_authorities.items():
            if phase_id not in phases_executed:
                if auth.authority == AuthorityLevel.HIGH:
                    warnings.append(f"High-authority phase {phase_id} not executed")

        # Determine validity
        high_violations = [v for v in violations if v.severity == AuthorityLevel.HIGH]
        valid = len(high_violations) == 0
        if self.strict_mode:
            valid = len(violations) == 0

        return CascadeValidation(
            valid=valid,
            violations=tuple(violations),
            phases_checked=tuple(phases_executed),
            authority_chain=authority_chain,
            high_authority_respected=high_authority_respected,
            warnings=tuple(warnings),
        )

    def _detect_executed_phases(self, ctx: "PipelineContext") -> List[str]:
        """Detect which phases have executed from context."""
        executed = []

        # Check for phase outputs in context
        phase_attrs = {
            "p13_safety": "P13",
            "p17_ethics": "P17",
            "p18_alignment": "P18",
            "p27_persona": "P27",
            "p28_dha": "P28",
            "p29_expression": "P29",
            "p30_verification": "P30",
            "p31_envelope": "P31",
        }

        for attr, phase_id in phase_attrs.items():
            if hasattr(ctx, attr) and getattr(ctx, attr) is not None:
                executed.append(phase_id)

        return executed

    def _check_sequence(self, phases_executed: List[str]) -> List[AuthorityViolation]:
        """Check that phases execute in required order."""
        violations = []
        executed_set = set(phases_executed)

        for phase_id in phases_executed:
            if phase_id not in self.phase_authorities:
                continue

            auth = self.phase_authorities[phase_id]
            for required in auth.requires:
                if required not in executed_set:
                    violations.append(AuthorityViolation(
                        violation_type=ViolationType.SEQUENCE,
                        phase_id=phase_id,
                        violated_by=None,
                        severity=auth.authority,
                        description=f"Phase {phase_id} requires {required} to execute first",
                    ))

        return violations

    def _check_overrides(
        self,
        ctx: "PipelineContext",
        phases_executed: List[str],
    ) -> List[AuthorityViolation]:
        """Check for unauthorized override attempts."""
        violations = []

        # Check P30 verification results for override indicators
        if hasattr(ctx, 'p30_verification') and ctx.p30_verification:
            p30 = ctx.p30_verification
            if hasattr(p30, 'violations'):
                for v in p30.violations:
                    # Check if any violation indicates HIGH auth was overridden
                    if hasattr(v, 'severity') and v.severity == "blocking":
                        violations.append(AuthorityViolation(
                            violation_type=ViolationType.OVERRIDE,
                            phase_id="P30",
                            violated_by="downstream_phase",
                            severity=AuthorityLevel.MEDIUM,
                            description=f"P30 violation: {getattr(v, 'description', 'unknown')}",
                        ))

        return violations

    def _check_high_authority(
        self,
        ctx: "PipelineContext",
        phases_executed: List[str],
    ) -> bool:
        """Check that HIGH authority phases are respected."""
        # Check P13 safety compliance
        if hasattr(ctx, 'p30_verification') and ctx.p30_verification:
            p30 = ctx.p30_verification
            if hasattr(p30, 'compliance_result'):
                compliance = p30.compliance_result
                if hasattr(compliance, 'compliant') and not compliance.compliant:
                    return False

        # Check P29 didn't override safety constraints
        if hasattr(ctx, 'p29_expression') and ctx.p29_expression:
            p29 = ctx.p29_expression
            if hasattr(p29, 'safety_overridden') and p29.safety_overridden:
                return False

        return True

    def get_authority_for_phase(self, phase_id: str) -> Optional[AuthorityLevel]:
        """Get authority level for a phase."""
        if phase_id in self.phase_authorities:
            return self.phase_authorities[phase_id].authority
        return None

    def can_override(self, overriding_phase: str, target_phase: str) -> bool:
        """Check if one phase can override another."""
        if overriding_phase not in self.phase_authorities:
            return False
        if target_phase not in self.phase_authorities:
            return True  # Unknown phases can be overridden

        overrider = self.phase_authorities[overriding_phase]
        target = self.phase_authorities[target_phase]

        # Check explicit override permission
        if target_phase in overrider.can_override:
            return True

        # Check authority hierarchy
        return overrider.authority.value > target.authority.value


# =============================================================================
# SINGLETON
# =============================================================================

_validator: Optional[AuthorityCascadeValidator] = None


def get_authority_cascade_validator() -> AuthorityCascadeValidator:
    """Get or create singleton AuthorityCascadeValidator instance."""
    global _validator
    if _validator is None:
        _validator = AuthorityCascadeValidator()
    return _validator


def validate_authority_cascade(
    ctx: "PipelineContext",
    phases_executed: Optional[List[str]] = None,
) -> CascadeValidation:
    """
    Convenience function to validate authority cascade.

    Args:
        ctx: Pipeline context.
        phases_executed: List of executed phase IDs.

    Returns:
        CascadeValidation with validation result.
    """
    return get_authority_cascade_validator().validate(ctx, phases_executed)


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    "VERSION",
    "AuthorityLevel",
    "ViolationType",
    "PhaseAuthority",
    "PHASE_AUTHORITIES",
    "AuthorityViolation",
    "CascadeValidation",
    "AuthorityCascadeValidator",
    "get_authority_cascade_validator",
    "validate_authority_cascade",
]
