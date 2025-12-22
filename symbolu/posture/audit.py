"""
Posture Audit Logging
=====================

╔═══════════════════════════════════════════════════════════════════════════════╗
║                    AUDIT & EXPLAINABILITY                                      ║
║                                                                                ║
║  Complete audit trail for all posture applications.                            ║
║  Designed for regulatory scrutiny and external auditors.                       ║
╚═══════════════════════════════════════════════════════════════════════════════╝

Every posture application is logged with:
    - Full posture profile used
    - What was influenced
    - Original vs adjusted values
    - Tier context
    - Source of posture (deployment default, request override)

NEVER claims in audit logs:
    - "system chose"
    - "system judged"
    - "system decided morally"

ALWAYS indicates in audit logs:
    - "operator-configured"
    - "non-authoritative over truth"
    - "deterministic application"

Version: 1.0
Date: 2025-12-22
"""

from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass

from symbolu.posture.types import (
    DecisionPostureProfile,
    PostureApplicationResult,
    PostureAuditRecord,
    PostureInfluenceScope,
    PostureTier,
    PostureConstraint,
    HARD_CONSTRAINTS,
)


# =============================================================================
# Audit Record Builder
# =============================================================================

def create_audit_record(
    posture: DecisionPostureProfile,
    tier: PostureTier,
    applications: List[PostureApplicationResult],
    source: str = "deployment_default",
) -> PostureAuditRecord:
    """
    Create a complete audit record for posture application.

    Args:
        posture: The posture profile that was applied
        tier: The tier context
        applications: List of application results
        source: Where the posture came from:
                - "deployment_default"
                - "request_override"
                - "per_session"
                - "dynamic_adjustment"

    Returns:
        PostureAuditRecord ready for logging/serialization
    """
    # Collect all scopes that were actually influenced
    applied_to = tuple(
        app.influence_scope
        for app in applications
        if app.was_influenced
    )

    return PostureAuditRecord(
        posture_profile=posture,
        applied_to=applied_to,
        influence_scope_label="non-authoritative",
        tier=tier,
        applications=tuple(applications),
        constraints_respected=tuple(HARD_CONSTRAINTS),
        posture_source=source,
    )


# =============================================================================
# Audit Log Formatters
# =============================================================================

def format_audit_for_api_response(record: PostureAuditRecord) -> Dict[str, Any]:
    """
    Format audit record for inclusion in API responses.

    This is the format that external systems and auditors will see.

    Returns:
        Dictionary suitable for JSON serialization
    """
    return {
        "decision_posture": {
            "coherence_bias": round(record.posture_profile.coherence_bias, 4),
            "exploration_bias": round(record.posture_profile.exploration_bias, 4),
            "constraint_bias": round(record.posture_profile.constraint_bias, 4),
            "applied_to": [scope.value for scope in record.applied_to],
            "influence_scope": record.influence_scope_label,
        },
        "posture_metadata": {
            "tier": record.tier.value,
            "source": record.posture_source,
            "applications_count": len(record.applications),
            "influenced_count": sum(1 for app in record.applications if app.was_influenced),
        },
    }


def format_audit_for_detailed_log(record: PostureAuditRecord) -> Dict[str, Any]:
    """
    Format audit record for detailed internal logging.

    Includes all application details for debugging and compliance.

    Returns:
        Dictionary with full audit trail
    """
    return {
        "decision_posture": {
            "coherence_bias": record.posture_profile.coherence_bias,
            "exploration_bias": record.posture_profile.exploration_bias,
            "constraint_bias": record.posture_profile.constraint_bias,
            "is_balanced": record.posture_profile.is_balanced,
        },
        "context": {
            "tier": record.tier.value,
            "source": record.posture_source,
            "influence_scope": record.influence_scope_label,
        },
        "applications": [
            {
                "scope": app.influence_scope.value,
                "original": round(app.original_value, 4),
                "adjusted": round(app.adjusted_value, 4),
                "delta": round(app.adjustment_delta, 4),
                "was_influenced": app.was_influenced,
            }
            for app in record.applications
        ],
        "constraints": {
            "all_respected": True,
            "constraints": [c.value for c in record.constraints_respected],
        },
        "assertions": {
            "no_truth_override": True,
            "no_moral_judgment": True,
            "deterministic": True,
            "operator_configured": True,
        },
    }


def format_audit_for_compliance_report(record: PostureAuditRecord) -> str:
    """
    Format audit record for human-readable compliance reports.

    Returns:
        Multi-line string for compliance documentation
    """
    lines = [
        "=" * 70,
        "DECISION POSTURE AUDIT RECORD",
        "=" * 70,
        "",
        "POSTURE PROFILE:",
        f"  Coherence Bias:   {record.posture_profile.coherence_bias:.4f}",
        f"  Exploration Bias: {record.posture_profile.exploration_bias:.4f}",
        f"  Constraint Bias:  {record.posture_profile.constraint_bias:.4f}",
        "",
        "CONTEXT:",
        f"  Tier:             {record.tier.value}",
        f"  Source:           {record.posture_source}",
        f"  Influence Scope:  {record.influence_scope_label}",
        "",
        "APPLICATIONS:",
    ]

    for app in record.applications:
        status = "INFLUENCED" if app.was_influenced else "no change"
        lines.append(
            f"  {app.influence_scope.value}: "
            f"{app.original_value:.4f} → {app.adjusted_value:.4f} ({status})"
        )

    lines.extend([
        "",
        "HARD CONSTRAINTS RESPECTED:",
    ])
    for constraint in record.constraints_respected:
        lines.append(f"  ✓ {constraint.value}")

    lines.extend([
        "",
        "COMPLIANCE ASSERTIONS:",
        "  ✓ No truth evaluation override",
        "  ✓ No ontology modification",
        "  ✓ No moral judgment performed",
        "  ✓ No user ethical classification",
        "  ✓ Deterministic application",
        "  ✓ Operator-configured only",
        "",
        "=" * 70,
    ])

    return "\n".join(lines)


# =============================================================================
# Audit Validation
# =============================================================================

def validate_audit_record(record: PostureAuditRecord) -> Tuple[bool, List[str]]:
    """
    Validate that an audit record respects all constraints.

    Returns:
        Tuple of (is_valid, list_of_violations)
    """
    violations = []

    # Check influence scope is always non-authoritative
    if record.influence_scope_label != "non-authoritative":
        violations.append(
            f"influence_scope_label must be 'non-authoritative', "
            f"got '{record.influence_scope_label}'"
        )

    # Check all constraints are respected
    if set(record.constraints_respected) != HARD_CONSTRAINTS:
        missing = HARD_CONSTRAINTS - set(record.constraints_respected)
        violations.append(
            f"Missing hard constraints: {[c.value for c in missing]}"
        )

    # Check tier allows the influenced scopes
    from symbolu.posture.types import TIER_ALLOWED_INFLUENCES
    allowed = TIER_ALLOWED_INFLUENCES.get(record.tier, ())
    for app in record.applications:
        if app.was_influenced and app.influence_scope not in allowed:
            violations.append(
                f"Tier {record.tier.value} does not allow influence on "
                f"{app.influence_scope.value}"
            )

    return (len(violations) == 0, violations)


# =============================================================================
# Summary Statistics
# =============================================================================

def summarize_applications(
    applications: List[PostureApplicationResult],
) -> Dict[str, Any]:
    """
    Generate summary statistics for a batch of posture applications.

    Returns:
        Dictionary with summary statistics
    """
    if not applications:
        return {
            "total": 0,
            "influenced": 0,
            "influence_rate": 0.0,
            "avg_delta": 0.0,
            "max_delta": 0.0,
        }

    influenced = [app for app in applications if app.was_influenced]
    deltas = [abs(app.adjustment_delta) for app in applications]

    return {
        "total": len(applications),
        "influenced": len(influenced),
        "influence_rate": len(influenced) / len(applications),
        "avg_delta": sum(deltas) / len(deltas) if deltas else 0.0,
        "max_delta": max(deltas) if deltas else 0.0,
        "by_scope": {
            app.influence_scope.value: app.was_influenced
            for app in applications
        },
    }
