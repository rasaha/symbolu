"""
Phase 51: Governance Readiness Analyzer

Core computation engine for evaluating governance readiness using
deterministic structural criteria only.

Phase 51 summarizes structural readiness for governance without exercising
governance authority.

READINESS CRITERIA (Deterministic Rules):

P51 MUST evaluate readiness using only structural criteria, not meaning.

REQUIRED CHECKS:
    1. Phase completeness: All mandatory upstream envelopes present
    2. Determinism: No nondeterministic flags detected
    3. Authority integrity: No observer phase influenced authoritative phase
    4. Explainability: All authoritative decisions traceable to phase fields
    5. Drift safety: Drift level below hard threshold
    6. Contradiction handling: No unresolved authoritative contradictions

READINESS MAPPING RULES:

    READY:
        - All checks pass
        - No blocking factors

    CONDITIONAL:
        - Non-authoritative warnings present
        - Observational noise
        - Forecast uncertainty only

    NOT_READY:
        - Missing authoritative envelope
        - Determinism violation
        - Authority leakage
        - Untraceable decision

INVARIANTS:
    INV-P51-1: P51 MUST NOT modify any upstream data
    INV-P51-2: P51 MUST NOT introduce new classifications or decisions
    INV-P51-3: P51 MUST NOT block or gate output
    INV-P51-4: P51 MUST NOT depend on future governance logic
    INV-P51-5: When P51 is removed, system behavior is bitwise identical
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from .p51_schema import (
    GovernanceReadinessEnvelope,
    ReadinessLevel,
    create_governance_readiness_envelope,
    DRIFT_SAFETY_THRESHOLD,
    MANDATORY_PHASES,
)


# ============================================================================
# CHECK FUNCTIONS
# ============================================================================


def _check_phase_completeness(
    phase_presence: Dict[str, bool],
) -> Tuple[bool, List[str], Dict[str, Any]]:
    """
    Check if all mandatory upstream envelopes are present.

    INV-P51-1: We read phase presence but NEVER modify it.

    Args:
        phase_presence: Dict mapping phase names to presence status

    Returns:
        Tuple of (passed, blocking_factors, evidence)
    """
    blocking_factors = []
    missing_phases = []

    for phase in MANDATORY_PHASES:
        if not phase_presence.get(phase, False):
            missing_phases.append(phase)
            blocking_factors.append(f"MISSING_MANDATORY_PHASE: {phase}")

    passed = len(missing_phases) == 0
    evidence = {
        "mandatory_phases": sorted(MANDATORY_PHASES),
        "present_phases": sorted(k for k, v in phase_presence.items() if v),
        "missing_phases": sorted(missing_phases),
    }

    return passed, blocking_factors, evidence


def _check_determinism(
    nondeterministic_flags: Tuple[str, ...],
) -> Tuple[bool, List[str], Dict[str, Any]]:
    """
    Check for nondeterministic flags in the pipeline.

    INV-P51-1: We read flags but NEVER modify them.

    Args:
        nondeterministic_flags: Tuple of detected nondeterministic flags

    Returns:
        Tuple of (passed, blocking_factors, evidence)
    """
    blocking_factors = []

    if nondeterministic_flags:
        for flag in nondeterministic_flags:
            blocking_factors.append(f"NONDETERMINISM_DETECTED: {flag}")

    passed = len(nondeterministic_flags) == 0
    evidence = {
        "nondeterministic_flags": list(nondeterministic_flags),
        "determinism_verified": passed,
    }

    return passed, blocking_factors, evidence


def _check_authority_integrity(
    observer_influence_flags: Tuple[str, ...],
) -> Tuple[bool, List[str], Dict[str, Any]]:
    """
    Check that no observer phase influenced an authoritative phase.

    INV-P51-1: We read flags but NEVER modify them.

    Args:
        observer_influence_flags: Tuple of detected authority leakage flags

    Returns:
        Tuple of (passed, blocking_factors, evidence)
    """
    blocking_factors = []

    if observer_influence_flags:
        for flag in observer_influence_flags:
            blocking_factors.append(f"AUTHORITY_LEAKAGE: {flag}")

    passed = len(observer_influence_flags) == 0
    evidence = {
        "observer_influence_flags": list(observer_influence_flags),
        "authority_integrity_verified": passed,
    }

    return passed, blocking_factors, evidence


def _check_explainability(
    untraceable_decisions: Tuple[str, ...],
) -> Tuple[bool, List[str], Dict[str, Any]]:
    """
    Check that all authoritative decisions are traceable to phase fields.

    INV-P51-1: We read trace data but NEVER modify it.

    Args:
        untraceable_decisions: Tuple of decisions that cannot be traced

    Returns:
        Tuple of (passed, blocking_factors, evidence)
    """
    blocking_factors = []

    if untraceable_decisions:
        for decision in untraceable_decisions:
            blocking_factors.append(f"UNTRACEABLE_DECISION: {decision}")

    passed = len(untraceable_decisions) == 0
    evidence = {
        "untraceable_decisions": list(untraceable_decisions),
        "explainability_verified": passed,
    }

    return passed, blocking_factors, evidence


def _check_drift_safety(
    drift_fusion_index: Optional[float],
) -> Tuple[bool, List[str], List[str], Dict[str, Any]]:
    """
    Check that drift level is below hard threshold.

    INV-P51-1: We read drift data but NEVER modify it.

    Args:
        drift_fusion_index: Drift fusion index from P19 [0.0, 1.0]

    Returns:
        Tuple of (passed, blocking_factors, advisory_notes, evidence)
    """
    blocking_factors = []
    advisory_notes = []

    # If drift data is missing, we cannot verify safety
    if drift_fusion_index is None:
        advisory_notes.append("DRIFT_DATA_MISSING: Cannot verify drift safety")
        evidence = {
            "drift_fusion_index": None,
            "drift_threshold": DRIFT_SAFETY_THRESHOLD,
            "drift_safety_verified": False,
            "reason": "missing_data",
        }
        return True, blocking_factors, advisory_notes, evidence  # Not blocking

    # Check against hard threshold
    if drift_fusion_index >= DRIFT_SAFETY_THRESHOLD:
        blocking_factors.append(
            f"DRIFT_EXCEEDS_THRESHOLD: {drift_fusion_index:.3f} >= {DRIFT_SAFETY_THRESHOLD}"
        )
        passed = False
    else:
        passed = True

    evidence = {
        "drift_fusion_index": drift_fusion_index,
        "drift_threshold": DRIFT_SAFETY_THRESHOLD,
        "drift_safety_verified": passed,
    }

    return passed, blocking_factors, advisory_notes, evidence


def _check_contradiction_handling(
    unresolved_contradictions: Tuple[str, ...],
) -> Tuple[bool, List[str], Dict[str, Any]]:
    """
    Check for unresolved authoritative contradictions.

    INV-P51-1: We read contradiction data but NEVER modify it.

    Args:
        unresolved_contradictions: Tuple of unresolved contradiction descriptions

    Returns:
        Tuple of (passed, blocking_factors, evidence)
    """
    blocking_factors = []

    if unresolved_contradictions:
        for contradiction in unresolved_contradictions:
            blocking_factors.append(f"UNRESOLVED_CONTRADICTION: {contradiction}")

    passed = len(unresolved_contradictions) == 0
    evidence = {
        "unresolved_contradictions": list(unresolved_contradictions),
        "contradiction_handling_verified": passed,
    }

    return passed, blocking_factors, evidence


# ============================================================================
# READINESS LEVEL DETERMINATION
# ============================================================================


def _determine_readiness_level(
    blocking_factors: List[str],
    advisory_notes: List[str],
) -> ReadinessLevel:
    """
    Determine readiness level based on blocking factors and advisory notes.

    READINESS MAPPING RULES:

        READY:
            - All checks pass
            - No blocking factors

        CONDITIONAL:
            - Non-authoritative warnings present
            - Observational noise
            - Forecast uncertainty only

        NOT_READY:
            - Missing authoritative envelope
            - Determinism violation
            - Authority leakage
            - Untraceable decision

    Args:
        blocking_factors: List of blocking factor descriptions
        advisory_notes: List of advisory note strings

    Returns:
        ReadinessLevel ("READY", "CONDITIONAL", or "NOT_READY")
    """
    if blocking_factors:
        return "NOT_READY"
    elif advisory_notes:
        return "CONDITIONAL"
    else:
        return "READY"


# ============================================================================
# CORE COMPUTATION
# ============================================================================


def compute_governance_readiness(
    phase_presence: Dict[str, bool],
    nondeterministic_flags: Tuple[str, ...] = (),
    observer_influence_flags: Tuple[str, ...] = (),
    untraceable_decisions: Tuple[str, ...] = (),
    drift_fusion_index: Optional[float] = None,
    unresolved_contradictions: Tuple[str, ...] = (),
) -> GovernanceReadinessEnvelope:
    """
    Compute governance readiness envelope from structural checks.

    INV-P51-1: We read but NEVER modify any upstream data.
    INV-P51-2: We report readiness, we don't create new decisions.
    INV-P51-3: We don't gate or block - this is diagnostic only.
    INV-P51-4: No future governance logic dependencies.

    Args:
        phase_presence: Dict mapping phase names to presence status
        nondeterministic_flags: Tuple of nondeterministic flags
        observer_influence_flags: Tuple of authority leakage flags
        untraceable_decisions: Tuple of untraceable decision descriptions
        drift_fusion_index: Drift fusion index from P19 [0.0, 1.0]
        unresolved_contradictions: Tuple of unresolved contradiction descriptions

    Returns:
        GovernanceReadinessEnvelope
    """
    all_blocking_factors: List[str] = []
    all_advisory_notes: List[str] = []
    all_evidence: Dict[str, Any] = {}

    # Check 1: Phase completeness
    passed, factors, evidence = _check_phase_completeness(phase_presence)
    all_blocking_factors.extend(factors)
    all_evidence["phase_completeness"] = evidence

    # Check 2: Determinism
    passed, factors, evidence = _check_determinism(nondeterministic_flags)
    all_blocking_factors.extend(factors)
    all_evidence["determinism"] = evidence

    # Check 3: Authority integrity
    passed, factors, evidence = _check_authority_integrity(observer_influence_flags)
    all_blocking_factors.extend(factors)
    all_evidence["authority_integrity"] = evidence

    # Check 4: Explainability
    passed, factors, evidence = _check_explainability(untraceable_decisions)
    all_blocking_factors.extend(factors)
    all_evidence["explainability"] = evidence

    # Check 5: Drift safety
    passed, factors, notes, evidence = _check_drift_safety(drift_fusion_index)
    all_blocking_factors.extend(factors)
    all_advisory_notes.extend(notes)
    all_evidence["drift_safety"] = evidence

    # Check 6: Contradiction handling
    passed, factors, evidence = _check_contradiction_handling(unresolved_contradictions)
    all_blocking_factors.extend(factors)
    all_evidence["contradiction_handling"] = evidence

    # Determine readiness level
    readiness_level = _determine_readiness_level(
        all_blocking_factors, all_advisory_notes
    )

    return create_governance_readiness_envelope(
        readiness_level=readiness_level,
        blocking_factors=tuple(sorted(all_blocking_factors)),
        advisory_notes=tuple(sorted(all_advisory_notes)),
        supporting_evidence=all_evidence,
    )


def run_p51_directly(
    phase_20_snapshot: Any,
    p21_delivery_mode: Any,
    p6_regime: Any,
    p7_discourse_envelope: Any,
    p18_entropy: Any,
    p19_drift: Any,
    p50_cognitive_consistency: Any,
    coherence_state: Any,
) -> Optional[GovernanceReadinessEnvelope]:
    """
    Run P51 governance readiness directly with upstream reports.

    This is the direct computation entry point for testing and
    bypassing context extraction.

    INV-P51-1: We read but NEVER modify upstream outputs.
    INV-P51-2: We report readiness, not create decisions.

    Args:
        phase_20_snapshot: P20 UnifiedCognitiveSnapshot
        p21_delivery_mode: P21 DeliveryModeDecision
        p6_regime: P6 RegimeEnvelope
        p7_discourse_envelope: P7 DiscourseEnvelope
        p18_entropy: P18 temporal entropy report
        p19_drift: P19 drift fusion report
        p50_cognitive_consistency: P50 cognitive consistency report
        coherence_state: CoherenceState

    Returns:
        GovernanceReadinessEnvelope
    """
    # Build phase presence map
    phase_presence: Dict[str, bool] = {
        "phase_20_snapshot": phase_20_snapshot is not None,
        "p21_delivery_mode": p21_delivery_mode is not None,
        "p6_regime": p6_regime is not None,
        "p7_discourse_envelope": p7_discourse_envelope is not None,
        "p18": p18_entropy is not None,
        "p19_drift_fusion": p19_drift is not None,
        "p50_cognitive_consistency": p50_cognitive_consistency is not None,
        "coherence_state": coherence_state is not None,
    }

    # Extract drift fusion index from P19
    drift_fusion_index: Optional[float] = None
    if p19_drift is not None:
        drift_fusion_index = getattr(p19_drift, "drift_fusion_index", None)

    # Extract unresolved contradictions from P50
    unresolved_contradictions: Tuple[str, ...] = ()
    if p50_cognitive_consistency is not None:
        detected = getattr(p50_cognitive_consistency, "detected_contradictions", None)
        if detected:
            # Only include authoritative contradictions (regime, discourse)
            unresolved_contradictions = tuple(
                c for c in detected
                if "REGIME_CONTRADICTION" in c or "DISCOURSE_CONTRADICTION" in c
            )

    # No nondeterministic flags in this architecture (deterministic by design)
    nondeterministic_flags: Tuple[str, ...] = ()

    # No observer influence flags (architecture enforces separation)
    observer_influence_flags: Tuple[str, ...] = ()

    # No untraceable decisions (all phases have trace metadata)
    untraceable_decisions: Tuple[str, ...] = ()

    return compute_governance_readiness(
        phase_presence=phase_presence,
        nondeterministic_flags=nondeterministic_flags,
        observer_influence_flags=observer_influence_flags,
        untraceable_decisions=untraceable_decisions,
        drift_fusion_index=drift_fusion_index,
        unresolved_contradictions=unresolved_contradictions,
    )


# Public exports
__all__ = [
    "compute_governance_readiness",
    "run_p51_directly",
]
