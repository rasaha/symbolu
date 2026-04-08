"""Acoustic Governance Chain - Full Pipeline Orchestration.

This module provides the AcousticGovernanceChain class which orchestrates
the complete acoustic governance pipeline from Presentation Layer output
through P10/P11B/P12.

Pipeline Flow:
    PresentationDirective → P6-Lite → P7-Lite → P10 → P12
                            ↓          ↓         ↓      ↓
                        RegimeEnv  DiscourseEnv  Acoustic  Audit

Design Principles:
-----------------
1. Sound must obey meaning (meaning never obeys sound)
2. P12 is audit-only (never modifies data)
3. Fail-closed on any error (conservative defaults)
4. Deterministic (same input → identical output)

Usage:
    from symbolu_core.presentation import PresentationEngine, CONSUMER_CONFIG
    from symbolu_core.presentation.acoustic_chain import AcousticGovernanceChain

    # Create presentation directive
    engine = PresentationEngine(CONSUMER_CONFIG)
    directive = engine.compute(signal_bundle)

    # Run acoustic governance
    chain = AcousticGovernanceChain()
    result = chain.execute(directive)

    # Access outputs
    print(result.acoustic_frame.regime)
    print(result.audit_report.is_consistent)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from symbolu_core.presentation.types import PresentationDirective
from symbolu_core.presentation.p6_lite import P6LiteResolver
from symbolu_core.presentation.p7_lite import P7LiteResolver
from symbolu_core.mechanical.pipeline.phase_p6.p6_schema import RegimeEnvelope
from symbolu_core.mechanical.pipeline.p7_discourse.p7_discourse_schema import DiscourseEnvelope
from symbolu_core.mechanical.pipeline.p10_acoustic.p10_acoustic_resolver import P10AcousticResolver
from symbolu_core.mechanical.pipeline.p10_acoustic.p10_acoustic_schema import AcousticParameterFrame
from symbolu_core.mechanical.pipeline.p12_consistency.p12_consistency_schema import (
    P12ConsistencyReport,
    ViolationSeverity,
)
from symbolu_core.mechanical.pipeline.p12_consistency.p12_consistency_validator import (
    P12ConsistencyValidator,
)


# =============================================================================
# ACOUSTIC CONTEXT (Internal)
# =============================================================================


@dataclass
class AcousticContext:
    """Internal context object for P12 validation.

    This provides the interface that P12ConsistencyValidator expects,
    populated from our lite bridge outputs.

    Invariants:
    - Immutable after creation
    - All fields have safe defaults
    - Never exposed directly to external code
    """

    # Source directive (for tracing)
    directive: Optional[PresentationDirective] = None

    # P6 Regime Envelope (from P6-Lite)
    p6_regime: Optional[RegimeEnvelope] = None

    # P7 Discourse Envelope (from P7-Lite)
    p7_discourse_envelope: Optional[DiscourseEnvelope] = None

    # P10 Acoustic Parameters
    p10_acoustic: Optional[AcousticParameterFrame] = None

    # P12 Consistency Report (set after validation)
    p12_consistency: Optional[P12ConsistencyReport] = None

    # Phase tracking
    phase_zero: Optional[Any] = None  # For P12 compatibility (intent)
    phase_minus_one: Optional[Any] = None  # For P12 compatibility (grounding)
    semantic_frame: Optional[Any] = None  # For P12 compatibility (uncertainty slot)


# =============================================================================
# ACOUSTIC GOVERNANCE CHAIN RESULT
# =============================================================================


@dataclass(frozen=True)
class AcousticChainResult:
    """Result of acoustic governance chain execution.

    Contains all intermediate outputs and the final audit report.
    This is the public API for chain execution results.

    Attributes:
        directive: The input PresentationDirective
        regime_envelope: The derived RegimeEnvelope from P6-Lite
        discourse_envelope: The derived DiscourseEnvelope from P7-Lite
        acoustic_frame: The derived AcousticParameterFrame from P10
        audit_report: The P12ConsistencyReport (audit-only)
        is_consistent: True if no violations found
        has_critical_violation: True if any CRITICAL violation
        has_major_violation: True if any MAJOR violation
        debug: Additional debug information
    """

    # Input
    directive: PresentationDirective

    # Intermediate outputs
    regime_envelope: RegimeEnvelope
    discourse_envelope: DiscourseEnvelope
    acoustic_frame: AcousticParameterFrame

    # Audit report
    audit_report: P12ConsistencyReport

    # Convenience flags
    is_consistent: bool
    has_critical_violation: bool
    has_major_violation: bool

    # Debug info
    debug: Dict[str, Any] = field(default_factory=dict)

    @property
    def should_block(self) -> bool:
        """Check if output should be blocked (CRITICAL violations in GOVERNED mode)."""
        return self.has_critical_violation

    @property
    def violation_count(self) -> int:
        """Total number of violations."""
        return len(self.audit_report.violations)

    @property
    def warning_count(self) -> int:
        """Total number of warnings."""
        return len(self.audit_report.warnings)


# =============================================================================
# ACOUSTIC GOVERNANCE CHAIN
# =============================================================================


class AcousticGovernanceChain:
    """Orchestrates the complete acoustic governance pipeline.

    This class is the main entry point for running the full acoustic
    governance chain from Presentation Layer output to P12 audit.

    Pipeline Stages:
        1. P6-Lite: Derive RegimeEnvelope from PresentationDirective
        2. P7-Lite: Derive DiscourseEnvelope from PresentationDirective
        3. P10: Derive AcousticParameterFrame from envelopes
        4. P12: Audit consistency (audit-only, never modifies)

    Example:
        chain = AcousticGovernanceChain()
        result = chain.execute(directive)

        if result.should_block:
            # Handle critical violations (GOVERNED mode)
            pass

        # Use acoustic parameters
        frame = result.acoustic_frame
    """

    def __init__(self) -> None:
        """Initialize the acoustic governance chain.

        Creates instances of all required resolvers/validators.
        """
        self._p6_resolver = P6LiteResolver()
        self._p7_resolver = P7LiteResolver()
        self._p10_resolver = P10AcousticResolver()
        self._p12_validator = P12ConsistencyValidator()

    def execute(
        self,
        directive: PresentationDirective,
    ) -> AcousticChainResult:
        """Execute the full acoustic governance chain.

        Args:
            directive: The PresentationDirective from Presentation Engine

        Returns:
            AcousticChainResult with all outputs and audit report

        Raises:
            ValueError: If directive is None
        """
        if directive is None:
            raise ValueError("directive cannot be None")

        # Stage 1: P6-Lite - Derive regime
        regime_envelope = self._p6_resolver.resolve(directive)

        # Stage 2: P7-Lite - Derive discourse
        discourse_envelope = self._p7_resolver.resolve(directive)

        # Stage 3: P10 - Derive acoustic parameters
        acoustic_frame = self._p10_resolver.resolve(
            lexical_frame=None,  # No lexical frame in lite mode
            discourse_envelope=discourse_envelope,
            regime_envelope=regime_envelope,
        )

        # Stage 4: Build context for P12
        ctx = AcousticContext(
            directive=directive,
            p6_regime=regime_envelope,
            p7_discourse_envelope=discourse_envelope,
            p10_acoustic=acoustic_frame,
        )

        # Stage 5: P12 - Audit consistency
        audit_report = self._p12_validator.validate(ctx)

        # Handle None report (shouldn't happen, but fail-closed)
        if audit_report is None:
            audit_report = self._create_empty_report(directive)

        # Compute convenience flags
        is_consistent = audit_report.is_consistent
        has_critical = any(
            v.severity == ViolationSeverity.CRITICAL
            for v in audit_report.violations
        )
        has_major = any(
            v.severity == ViolationSeverity.MAJOR
            for v in audit_report.violations
        )

        # Build debug info
        debug = {
            "source": "acoustic_chain",
            "delivery_mode": directive.delivery_mode.value,
            "confidence": directive.confidence.value,
            "triggered_rule": directive.triggered_rule,
            "regime": regime_envelope.regime.value,
            "discourse_act": discourse_envelope.act.value,
            "acoustic_regime": acoustic_frame.regime.value,
            "violation_count": len(audit_report.violations),
            "warning_count": len(audit_report.warnings),
        }

        return AcousticChainResult(
            directive=directive,
            regime_envelope=regime_envelope,
            discourse_envelope=discourse_envelope,
            acoustic_frame=acoustic_frame,
            audit_report=audit_report,
            is_consistent=is_consistent,
            has_critical_violation=has_critical,
            has_major_violation=has_major,
            debug=debug,
        )

    def _create_empty_report(
        self,
        directive: PresentationDirective,
    ) -> P12ConsistencyReport:
        """Create an empty P12 report for error cases.

        This is a fallback for when validation fails unexpectedly.
        Returns a conservative (fail-closed) report.
        """
        return P12ConsistencyReport(
            is_consistent=False,
            violations=[],
            warnings=[],
            checked_invariants=[],
            audit_notes={"error": "validation_failed"},
            source_regime=directive.delivery_mode.value,
            source_discourse_act="UNKNOWN",
            source_intent=None,
        )


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================


def run_acoustic_chain(directive: PresentationDirective) -> AcousticChainResult:
    """Convenience function to run the acoustic governance chain.

    Args:
        directive: The PresentationDirective from Presentation Engine

    Returns:
        AcousticChainResult with all outputs and audit report

    Example:
        >>> from symbolu_core.presentation.acoustic_chain import run_acoustic_chain
        >>> result = run_acoustic_chain(directive)
        >>> print(result.acoustic_frame.speech_rate)
    """
    chain = AcousticGovernanceChain()
    return chain.execute(directive)


def is_acoustically_consistent(directive: PresentationDirective) -> bool:
    """Check if a directive produces consistent acoustic output.

    This is a quick check that returns True if no violations are found.

    Args:
        directive: The PresentationDirective to check

    Returns:
        True if acoustically consistent, False otherwise
    """
    result = run_acoustic_chain(directive)
    return result.is_consistent


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    # Main class
    "AcousticGovernanceChain",
    # Result type
    "AcousticChainResult",
    # Convenience functions
    "run_acoustic_chain",
    "is_acoustically_consistent",
]
