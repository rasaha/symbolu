"""
P17 - Semantic Integrity Monitor Resolver

Main resolver class that composes all rule checks and produces
the P17IntegrityReport. This is the entry point for P17 analysis.

Design Principles:
- Observation-Only: Never modifies upstream context
- Deterministic: Same inputs always produce same outputs
- Composable: Combines multiple rule checks into single report
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from symbolu.mechanical.pipeline.p17_semantic_integrity.p17_schema import (
    IntegrityIssue,
    IntegrityIssueType,
    P17IntegrityReport,
    Severity,
    create_report,
    P17_VERSION,
)
from symbolu.mechanical.pipeline.p17_semantic_integrity.p17_rules import (
    detect_uncertainty_collapse,
    detect_cause_leak,
    detect_authority_drift,
    detect_tone_escalation,
    detect_slot_contradictions,
    detect_missing_inputs,
)


# ============================================================================
# SCORE PENALTIES - Fixed constants for deterministic scoring
# ============================================================================

# Penalties by issue type
ISSUE_TYPE_PENALTIES: Dict[IntegrityIssueType, float] = {
    IntegrityIssueType.CONTRADICTION: 0.25,
    IntegrityIssueType.UNCERTAINTY_COLLAPSE: 0.20,
    IntegrityIssueType.CAUSE_LEAK: 0.15,
    IntegrityIssueType.AUTHORITY_DRIFT: 0.15,
    IntegrityIssueType.TONE_ESCALATION: 0.05,
    IntegrityIssueType.INSUFFICIENT_EVIDENCE: 0.05,
}

# Severity multipliers
SEVERITY_MULTIPLIERS: Dict[Severity, float] = {
    Severity.HIGH: 1.0,
    Severity.WARN: 0.5,
    Severity.INFO: 0.1,
}


# ============================================================================
# RESOLVER CLASS
# ============================================================================


class P17SemanticIntegrityMonitor:
    """
    P17 Semantic Integrity Monitor - Observation-only governance phase.

    Composes all rule checks and produces a P17IntegrityReport that
    describes any integrity issues between upstream semantic/lexical
    decisions. The monitor never modifies upstream state.

    Usage:
        monitor = P17SemanticIntegrityMonitor()
        report = monitor.run(ctx)

    The report contains:
        - issues: List of detected integrity issues
        - integrity_score: 0.0-1.0 score (1.0 = no issues)
        - is_clean: True if no HIGH severity issues
        - debug: Trace information
    """

    def __init__(self) -> None:
        """Initialize the P17 Semantic Integrity Monitor."""
        self._version = P17_VERSION

    @property
    def version(self) -> str:
        """Get the monitor version."""
        return self._version

    def run(self, ctx: Any) -> P17IntegrityReport:
        """
        Run all integrity checks on the pipeline context.

        This is the main entry point for P17 analysis. It:
        1. Extracts relevant artifacts from context
        2. Runs all rule checks
        3. Computes integrity score
        4. Produces the P17IntegrityReport

        Args:
            ctx: PipelineContext or compatible object

        Returns:
            P17IntegrityReport with all detected issues
        """
        # Extract artifacts from context (read-only)
        po1 = self._extract_po1(ctx)
        p6 = self._extract_p6(ctx)
        p7 = self._extract_p7(ctx)
        p8 = self._extract_p8(ctx)
        p9 = self._extract_p9(ctx)

        # Collect all issues from rule checks
        all_issues: List[IntegrityIssue] = []

        # 1. Check for missing inputs first
        all_issues.extend(detect_missing_inputs(po1, p6, p7, p8, p9))

        # 2. Run integrity checks
        all_issues.extend(detect_uncertainty_collapse(p8, p9))
        all_issues.extend(detect_cause_leak(p6, p7, p8, p9))
        all_issues.extend(detect_authority_drift(po1, p7, p9))
        all_issues.extend(detect_tone_escalation(p9))
        all_issues.extend(detect_slot_contradictions(p8, p9))

        # 3. Compute integrity score
        integrity_score = self._compute_score(all_issues)

        # 4. Build debug info
        debug = self._build_debug(po1, p6, p7, p8, p9, all_issues)

        # 5. Create and return report
        return create_report(
            issues=all_issues,
            integrity_score=integrity_score,
            debug=debug,
        )

    def _extract_po1(self, ctx: Any) -> Optional[Any]:
        """Extract PO1 (phase_minus_one) from context."""
        return getattr(ctx, "phase_minus_one", None)

    def _extract_p6(self, ctx: Any) -> Optional[Any]:
        """Extract P6 regime envelope from context."""
        return getattr(ctx, "p6_regime", None)

    def _extract_p7(self, ctx: Any) -> Optional[Any]:
        """Extract P7 discourse envelope from context."""
        return getattr(ctx, "p7_discourse_envelope", None)

    def _extract_p8(self, ctx: Any) -> Optional[Any]:
        """Extract P8 semantic frame from context."""
        return getattr(ctx, "semantic_frame", None)

    def _extract_p9(self, ctx: Any) -> Optional[Any]:
        """Extract P9 lexical frame from context."""
        return getattr(ctx, "lexical_frame", None)

    def _compute_score(self, issues: List[IntegrityIssue]) -> float:
        """
        Compute integrity score deterministically from issues.

        Starts at 1.0 and subtracts penalties based on issue type
        and severity. Score is clamped to [0.0, 1.0].

        Args:
            issues: List of detected integrity issues

        Returns:
            Integrity score in [0.0, 1.0]
        """
        score = 1.0

        for issue in issues:
            # Get base penalty for issue type
            base_penalty = ISSUE_TYPE_PENALTIES.get(
                issue.issue_type, 0.05
            )

            # Apply severity multiplier
            multiplier = SEVERITY_MULTIPLIERS.get(
                issue.severity, 0.5
            )

            # Subtract penalty
            score -= base_penalty * multiplier

        # Clamp to [0.0, 1.0]
        return max(0.0, min(1.0, score))

    def _build_debug(
        self,
        po1: Optional[Any],
        p6: Optional[Any],
        p7: Optional[Any],
        p8: Optional[Any],
        p9: Optional[Any],
        issues: List[IntegrityIssue],
    ) -> Dict[str, Any]:
        """
        Build debug/trace information for the report.

        Args:
            po1: PO1 envelope (may be None)
            p6: P6 envelope (may be None)
            p7: P7 envelope (may be None)
            p8: P8 frame (may be None)
            p9: P9 frame (may be None)
            issues: List of detected issues

        Returns:
            Debug dictionary
        """
        debug: Dict[str, Any] = {
            "version": self._version,
            "inputs_present": {
                "po1": po1 is not None,
                "p6": p6 is not None,
                "p7": p7 is not None,
                "p8": p8 is not None,
                "p9": p9 is not None,
            },
            "rule_counts": {
                "uncertainty_collapse": sum(
                    1 for i in issues
                    if i.issue_type == IntegrityIssueType.UNCERTAINTY_COLLAPSE
                ),
                "cause_leak": sum(
                    1 for i in issues
                    if i.issue_type == IntegrityIssueType.CAUSE_LEAK
                ),
                "authority_drift": sum(
                    1 for i in issues
                    if i.issue_type == IntegrityIssueType.AUTHORITY_DRIFT
                ),
                "tone_escalation": sum(
                    1 for i in issues
                    if i.issue_type == IntegrityIssueType.TONE_ESCALATION
                ),
                "contradiction": sum(
                    1 for i in issues
                    if i.issue_type == IntegrityIssueType.CONTRADICTION
                ),
                "insufficient_evidence": sum(
                    1 for i in issues
                    if i.issue_type == IntegrityIssueType.INSUFFICIENT_EVIDENCE
                ),
            },
            "severity_counts": {
                "high": sum(1 for i in issues if i.severity == Severity.HIGH),
                "warn": sum(1 for i in issues if i.severity == Severity.WARN),
                "info": sum(1 for i in issues if i.severity == Severity.INFO),
            },
        }

        # Add upstream context hints (non-sensitive)
        if p6 is not None:
            regime = getattr(p6, "regime", None)
            if regime is not None:
                debug["source_regime"] = getattr(regime, "value", str(regime))

        if p7 is not None:
            act = getattr(p7, "act", None)
            if act is not None:
                debug["source_discourse_act"] = getattr(act, "value", str(act))

        if po1 is not None:
            selected_primary = getattr(po1, "selected_primary", None)
            if selected_primary is not None:
                mode = getattr(selected_primary, "mode", None)
                if mode is not None:
                    debug["source_grounding_mode"] = getattr(mode, "value", str(mode))

        return debug


# Public exports
__all__ = [
    "P17SemanticIntegrityMonitor",
    "ISSUE_TYPE_PENALTIES",
    "SEVERITY_MULTIPLIERS",
]
