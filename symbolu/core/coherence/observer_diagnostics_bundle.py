"""
Observer Diagnostics Bundle - Neutral Carrier for Observer Artifacts

This module defines the ObserverDiagnosticsBundle dataclass which serves as a
clean, explicit bridge for Phase 10 Coherence to optionally receive P20/P24
diagnostic artifacts WITHOUT any authority coupling.

CRITICAL ARCHITECTURAL CONSTRAINTS:
1. This type lives in coherence core (not in observer modules)
2. Observer modules (P20, P24) MAY import this type
3. Authoritative modules (coherence_engine) MUST NOT import observer modules
4. Bundle contains DIAGNOSTICS ONLY - no raw text, no policy fields

SAFETY INVARIANTS (NON-NEGOTIABLE):
- INV-CB1: Bundle can ONLY affect coherence_v3_quality downward (never upward)
           and only within existing bounds
- INV-CB2: Bundle MUST NOT affect: PO1–PO5, P6–P9 outputs, regime/discourse/
           semantic/lexical decisions
- INV-CB3: No imports from observer modules into authoritative modules

The bundle type must live in coherence core, and observers may import it,
but not the reverse.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional, Tuple, Any

# Forward reference imports for type hints only (no runtime import of observers)
if TYPE_CHECKING:
    from symbolu.core.coherence.acoustic_alignment_schema import AcousticAlignmentReport
    from symbolu.mechanical.pipeline.p24_projection.p24_projection_schema import P24ProjectionReport


@dataclass(frozen=True)
class ObserverDiagnosticsBundle:
    """
    Neutral, observer-only carrier for diagnostic artifacts from P20/P24.

    This bundle provides a clean, explicit mechanism for Phase 10 Coherence
    to optionally receive observer diagnostics WITHOUT any authority coupling.

    CRITICAL DESIGN PRINCIPLES:
    1. IMMUTABLE: Frozen dataclass ensures no mutation after creation
    2. OBSERVER-ONLY: Contains only diagnostic observations, no policy fields
    3. NO RAW TEXT: Never contains raw input text or tokens
    4. OPTIONAL: All diagnostic fields are Optional
    5. TRACEABLE: source_phase_ids identifies which phases contributed

    INVARIANTS:
    - INV-CB1: Can only affect coherence_v3_quality downward, within existing bounds
    - INV-CB2: Cannot affect PO1–PO5, P6–P9, regime, discourse, semantic, lexical
    - INV-CB3: No imports from observer modules in authoritative modules

    Attributes:
        acoustic_alignment: Optional acoustic alignment report from P22/P23/P24.
                           Provides alignment_score, pressure_band, mismatch_tags.
                           Used for optional quality reduction (max 5%).

        acoustic_ontology_projection: Optional P24 projection report.
                                     Contains projected ontology layers, risk bands,
                                     and mismatch types from acoustic-ontology comparison.
                                     Observer-only; no authority impact.

        source_phase_ids: Tuple of phase identifiers that contributed to this bundle.
                         Used for provenance tracking and debugging.
                         Example: ("P22", "P23", "P24")

    Usage:
        # In observer orchestration (P20 or similar):
        bundle = ObserverDiagnosticsBundle(
            acoustic_alignment=alignment_report,
            acoustic_ontology_projection=projection_report,
            source_phase_ids=("P22", "P23", "P24"),
        )

        # In coherence engine:
        engine.update_state(
            ...,
            observer_diagnostics=bundle,  # Optional
        )

    Example:
        >>> from symbolu.core.coherence.acoustic_alignment_schema import create_misaligned_report
        >>> alignment = create_misaligned_report(alignment_score=0.25)
        >>> bundle = ObserverDiagnosticsBundle(
        ...     acoustic_alignment=alignment,
        ...     acoustic_ontology_projection=None,
        ...     source_phase_ids=("P23",),
        ... )
        >>> bundle.has_acoustic_alignment()
        True
        >>> bundle.has_ontology_projection()
        False
    """

    # === Diagnostic Fields (all Optional) ===

    acoustic_alignment: Optional[Any] = None
    """
    Acoustic alignment report from P22/P23/P24.
    Type: Optional[AcousticAlignmentReport]

    When present, provides:
    - alignment_score: [0.0, 1.0] acoustic-semantic alignment
    - pressure_band: "low" | "moderate" | "high"
    - mismatch_tags: Diagnostic tags for misalignment

    Can ONLY reduce coherence_v3_quality (max 5%), NEVER increase.
    """

    acoustic_ontology_projection: Optional[Any] = None
    """
    P24 acoustic-ontology projection report.
    Type: Optional[P24ProjectionReport]

    When present, provides:
    - projected_layers: Ontology layers (max 3)
    - projection_risk_band: LOW | MODERATE | HIGH
    - mismatch_type: NONE | SOFT_MISMATCH | STRONG_MISMATCH
    - projection_tags: Diagnostic tags from allow-list
    - confidence: Evidence completeness [0.0, 1.0]

    Observer-only; no direct authority impact on coherence scoring.
    """

    source_phase_ids: Tuple[str, ...] = ()
    """
    Phase identifiers that contributed to this bundle.

    Used for:
    - Provenance tracking
    - Debugging and observability
    - Audit trails

    Example: ("P22", "P23", "P24") or ("P20",)
    """

    def __post_init__(self) -> None:
        """Validate ObserverDiagnosticsBundle invariants."""
        # Validate source_phase_ids is a tuple
        if not isinstance(self.source_phase_ids, tuple):
            raise ValueError(
                f"ObserverDiagnosticsBundle.source_phase_ids must be a tuple, "
                f"got {type(self.source_phase_ids).__name__}"
            )

        # Validate all phase IDs are strings
        for phase_id in self.source_phase_ids:
            if not isinstance(phase_id, str):
                raise ValueError(
                    f"ObserverDiagnosticsBundle.source_phase_ids must contain only strings, "
                    f"found {type(phase_id).__name__}"
                )

        # Validate acoustic_alignment if present (duck-typing check)
        if self.acoustic_alignment is not None:
            # Check required attributes exist (duck typing for AcousticAlignmentReport)
            required_attrs = ["alignment_score", "pressure_band", "mismatch_tags"]
            for attr in required_attrs:
                if not hasattr(self.acoustic_alignment, attr):
                    raise ValueError(
                        f"ObserverDiagnosticsBundle.acoustic_alignment must have '{attr}' attribute"
                    )

        # Validate acoustic_ontology_projection if present (duck-typing check)
        if self.acoustic_ontology_projection is not None:
            # Check required attributes exist (duck typing for P24ProjectionReport)
            required_attrs = ["projected_layers", "projection_risk_band", "confidence"]
            for attr in required_attrs:
                if not hasattr(self.acoustic_ontology_projection, attr):
                    raise ValueError(
                        f"ObserverDiagnosticsBundle.acoustic_ontology_projection must have '{attr}' attribute"
                    )

    # === Query Methods ===

    def has_acoustic_alignment(self) -> bool:
        """Check if acoustic alignment report is present."""
        return self.acoustic_alignment is not None

    def has_ontology_projection(self) -> bool:
        """Check if P24 ontology projection report is present."""
        return self.acoustic_ontology_projection is not None

    def is_empty(self) -> bool:
        """Check if bundle contains no diagnostic data."""
        return (
            self.acoustic_alignment is None
            and self.acoustic_ontology_projection is None
        )

    def has_any_diagnostics(self) -> bool:
        """Check if bundle contains any diagnostic data."""
        return not self.is_empty()

    def get_source_phases(self) -> Tuple[str, ...]:
        """Get the source phase IDs that contributed to this bundle."""
        return self.source_phase_ids

    # === Extraction Methods ===

    def extract_acoustic_alignment(self) -> Optional[Any]:
        """
        Extract acoustic alignment for use in coherence quality computation.

        Returns:
            The acoustic alignment report, or None if not present.

        Note:
            The returned report can ONLY be used to reduce coherence_v3_quality,
            never to increase it. Max reduction is 5%.
        """
        return self.acoustic_alignment

    def extract_ontology_projection(self) -> Optional[Any]:
        """
        Extract P24 ontology projection for observability purposes.

        Returns:
            The P24 projection report, or None if not present.

        Note:
            This is observer-only data with no authority impact on scoring.
        """
        return self.acoustic_ontology_projection

    # === Serialization ===

    def to_dict(self) -> dict:
        """
        Serialize to dictionary for logging/tracing.

        Returns:
            Dictionary representation of the bundle.
        """
        result = {
            "has_acoustic_alignment": self.has_acoustic_alignment(),
            "has_ontology_projection": self.has_ontology_projection(),
            "source_phase_ids": list(self.source_phase_ids),
            "is_empty": self.is_empty(),
        }

        if self.acoustic_alignment is not None and hasattr(self.acoustic_alignment, "to_dict"):
            result["acoustic_alignment"] = self.acoustic_alignment.to_dict()

        if self.acoustic_ontology_projection is not None and hasattr(self.acoustic_ontology_projection, "to_dict"):
            result["acoustic_ontology_projection"] = self.acoustic_ontology_projection.to_dict()

        return result


# === Factory Functions ===


def create_empty_bundle() -> ObserverDiagnosticsBundle:
    """
    Create an empty observer diagnostics bundle.

    Used when no observer diagnostics are available but a bundle
    is required by the API.

    Returns:
        ObserverDiagnosticsBundle with all fields set to None/empty
    """
    return ObserverDiagnosticsBundle(
        acoustic_alignment=None,
        acoustic_ontology_projection=None,
        source_phase_ids=(),
    )


def create_acoustic_only_bundle(
    acoustic_alignment: Any,
    source_phase_ids: Tuple[str, ...] = ("P23",),
) -> ObserverDiagnosticsBundle:
    """
    Create a bundle with only acoustic alignment data.

    Args:
        acoustic_alignment: AcousticAlignmentReport from P22/P23/P24
        source_phase_ids: Phase identifiers that contributed

    Returns:
        ObserverDiagnosticsBundle with acoustic_alignment only
    """
    return ObserverDiagnosticsBundle(
        acoustic_alignment=acoustic_alignment,
        acoustic_ontology_projection=None,
        source_phase_ids=source_phase_ids,
    )


def create_full_bundle(
    acoustic_alignment: Optional[Any],
    acoustic_ontology_projection: Optional[Any],
    source_phase_ids: Tuple[str, ...] = ("P22", "P23", "P24"),
) -> ObserverDiagnosticsBundle:
    """
    Create a bundle with both acoustic alignment and ontology projection.

    Args:
        acoustic_alignment: AcousticAlignmentReport from P22/P23/P24
        acoustic_ontology_projection: P24ProjectionReport
        source_phase_ids: Phase identifiers that contributed

    Returns:
        ObserverDiagnosticsBundle with all available diagnostics
    """
    return ObserverDiagnosticsBundle(
        acoustic_alignment=acoustic_alignment,
        acoustic_ontology_projection=acoustic_ontology_projection,
        source_phase_ids=source_phase_ids,
    )


# === Public Exports ===


__all__ = [
    # Main dataclass
    "ObserverDiagnosticsBundle",
    # Factory functions
    "create_empty_bundle",
    "create_acoustic_only_bundle",
    "create_full_bundle",
]
