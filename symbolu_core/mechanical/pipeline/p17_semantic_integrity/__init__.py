"""
P17 - Semantic Integrity Monitor

Deterministic, observation-only governance phase that detects:
- Contradictions between semantic intent and lexical choices
- Uncertainty collapse
- Mode/authority drift
- Causal inference leakage
- Tone escalation signals

P17 is observation-only: it cannot change upstream decisions.
It produces a P17IntegrityReport used by later phases to gate
insight depth or renderer posture.

Usage:
    from symbolu_core.mechanical.pipeline.p17_semantic_integrity import (
        maybe_run_p17,
        is_integrity_clean,
        get_integrity_score,
    )

    # Run P17 after P9:
    maybe_run_p17(ctx)

    # Check results:
    if is_integrity_clean(ctx):
        # Proceed with full insight
        pass
    else:
        # Gate insight depth based on integrity score
        score = get_integrity_score(ctx)
"""

from symbolu_core.mechanical.pipeline.p17_semantic_integrity.p17_schema import (
    # Version
    P17_VERSION,
    # Enums
    IntegrityIssueType,
    Severity,
    # Dataclasses
    IntegrityIssue,
    P17IntegrityReport,
    # Helpers
    create_issue,
    create_report,
)

from symbolu_core.mechanical.pipeline.p17_semantic_integrity.p17_rules import (
    # Word lists
    CERTAINTY_MARKERS,
    UNCERTAINTY_PRESERVERS,
    CAUSAL_CONNECTORS,
    AUTHORITY_MARKERS,
    DIAGNOSTIC_LABELS,
    TONE_ESCALATION_MARKERS,
    CAUSAL_RESTRICTIVE_REGIMES,
    CAUSAL_RESTRICTIVE_DISCOURSE_ACTS,
    # Rule functions
    detect_uncertainty_collapse,
    detect_cause_leak,
    detect_authority_drift,
    detect_tone_escalation,
    detect_slot_contradictions,
    detect_missing_inputs,
)

from symbolu_core.mechanical.pipeline.p17_semantic_integrity.p17_resolver import (
    P17SemanticIntegrityMonitor,
    ISSUE_TYPE_PENALTIES,
    SEVERITY_MULTIPLIERS,
)

from symbolu_core.mechanical.pipeline.p17_semantic_integrity.p17_integration import (
    # Singleton
    get_p17_monitor,
    # Integration
    maybe_run_p17,
    run_p17_directly,
    # Helpers
    is_p17_disabled,
    has_p17_report,
    get_p17_report,
    is_integrity_clean,
    get_integrity_score,
    get_p17_version,
)


__all__ = [
    # Version
    "P17_VERSION",
    # Enums
    "IntegrityIssueType",
    "Severity",
    # Dataclasses
    "IntegrityIssue",
    "P17IntegrityReport",
    # Schema helpers
    "create_issue",
    "create_report",
    # Word lists
    "CERTAINTY_MARKERS",
    "UNCERTAINTY_PRESERVERS",
    "CAUSAL_CONNECTORS",
    "AUTHORITY_MARKERS",
    "DIAGNOSTIC_LABELS",
    "TONE_ESCALATION_MARKERS",
    "CAUSAL_RESTRICTIVE_REGIMES",
    "CAUSAL_RESTRICTIVE_DISCOURSE_ACTS",
    # Rule functions
    "detect_uncertainty_collapse",
    "detect_cause_leak",
    "detect_authority_drift",
    "detect_tone_escalation",
    "detect_slot_contradictions",
    "detect_missing_inputs",
    # Resolver
    "P17SemanticIntegrityMonitor",
    "ISSUE_TYPE_PENALTIES",
    "SEVERITY_MULTIPLIERS",
    # Singleton
    "get_p17_monitor",
    # Integration
    "maybe_run_p17",
    "run_p17_directly",
    # Helpers
    "is_p17_disabled",
    "has_p17_report",
    "get_p17_report",
    "is_integrity_clean",
    "get_integrity_score",
    "get_p17_version",
]
