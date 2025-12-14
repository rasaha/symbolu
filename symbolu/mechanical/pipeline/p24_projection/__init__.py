"""
P24 - Acoustic-Ontology Projection Observer

This phase is observer-only and non-authoritative.

P24 estimates outer human interpretation (10-layer ontology projection) from
already-resolved pipeline artifacts (regime, discourse act, semantic slots,
lexical frame, grammar evidence) and compares it against inner acoustic
witness (P22) + alignment/tension (P23).

P24 answers these questions:
    - What ontology layers might a human project onto the response?
    - What is the risk of over-projection or misinterpretation?
    - Is there mismatch between inner acoustic state and outer projection?

P24:
    - does not read raw input text
    - does not change any upstream decision
    - does not affect routing, gating, regime, discourse, semantics, lexical, renderer
    - does not call LLMs

It projects ontology layers and reports observation only.

CRITICAL ARCHITECTURAL INVARIANT:
    P24 is purely observational. It projects without authority.
    The projection report is immutable and has no downstream effect on routing.

Usage:
    from symbolu.mechanical.pipeline.p24_projection import maybe_run_p24

    # In pipeline after P23:
    ctx = maybe_run_p24(ctx)

    # Access report:
    if ctx.p24_projection_report is not None:
        print(ctx.p24_projection_report.projected_layers)
        print(ctx.p24_projection_report.projection_risk_band)
"""

from symbolu.mechanical.pipeline.p24_projection.p24_projection_schema import (
    # Version
    P24_VERSION,
    # Allow-list
    ALLOWED_PROJECTION_TAGS,
    # Enums
    OntologyLayer,
    ProjectionRiskBand,
    ProjectionMismatchType,
    # Dataclasses
    P24ProjectionReport,
    # Exceptions
    P24InvariantViolation,
    # Factory functions
    create_empty_report,
    create_blocked_report,
)

from symbolu.mechanical.pipeline.p24_projection.p24_projection_resolver import (
    P24ProjectionResolver,
    resolve_projection,
    access_forbidden_attribute,
    # Forbidden attribute sets
    FORBIDDEN_TEXT_ATTRS,
    FORBIDDEN_TOKEN_ATTRS,
    ALL_FORBIDDEN_ATTRS,
    # Discourse -> layers mapping
    DISCOURSE_ACT_LAYERS,
    # Certainty markers
    CERTAINTY_MARKERS,
    # Conservative regimes
    CONSERVATIVE_REGIMES,
)

from symbolu.mechanical.pipeline.p24_projection.p24_integration import (
    # Singleton
    get_p24_resolver,
    # Integration
    maybe_run_p24,
    run_p24,
    # Helpers
    is_p24_disabled,
    has_p24_report,
    get_p24_report,
    is_high_risk,
    has_strong_mismatch,
    get_projected_layers,
    get_projection_tags,
    get_risk_band,
    get_mismatch_type,
    get_confidence,
    get_p24_version,
)


__all__ = [
    # === Schema ===
    # Version
    "P24_VERSION",
    # Allow-list
    "ALLOWED_PROJECTION_TAGS",
    # Enums
    "OntologyLayer",
    "ProjectionRiskBand",
    "ProjectionMismatchType",
    # Dataclasses
    "P24ProjectionReport",
    # Exceptions
    "P24InvariantViolation",
    # Factory functions
    "create_empty_report",
    "create_blocked_report",
    # === Resolver ===
    "P24ProjectionResolver",
    "resolve_projection",
    "access_forbidden_attribute",
    # Forbidden attribute sets
    "FORBIDDEN_TEXT_ATTRS",
    "FORBIDDEN_TOKEN_ATTRS",
    "ALL_FORBIDDEN_ATTRS",
    # Discourse -> layers mapping
    "DISCOURSE_ACT_LAYERS",
    # Certainty markers
    "CERTAINTY_MARKERS",
    # Conservative regimes
    "CONSERVATIVE_REGIMES",
    # === Integration ===
    # Singleton
    "get_p24_resolver",
    # Integration
    "maybe_run_p24",
    "run_p24",
    # Helpers
    "is_p24_disabled",
    "has_p24_report",
    "get_p24_report",
    "is_high_risk",
    "has_strong_mismatch",
    "get_projected_layers",
    "get_projection_tags",
    "get_risk_band",
    "get_mismatch_type",
    "get_confidence",
    "get_p24_version",
]
