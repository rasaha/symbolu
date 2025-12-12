"""
Phase −1 Pipeline Orchestrator

Coordinates all Phase −1 stages to produce a PhaseMinusOneEnvelope
that downstream stages must respect.

Pipeline Flow:
1. CSL (Conservative Clause Splitter) proposes split (if beneficial)
2. For each clause: OOG generates candidates, ARL resolves
3. Determine overall policy (SINGLE_CONTEXT/MULTI_CONTEXT/BLOCKED)
4. Select primary grounding (if safe to do so)
5. Populate debug/metrics fields

Authority Model:
- Phase −1 establishes grounding constraints
- Authority flows downward (constraints are binding)
- Information flows upward (violations are reported, not overridden)
"""

from __future__ import annotations

import uuid
from typing import List, Optional

from .phase_minus_one_schema import (
    ClauseGroundingResult,
    GroundingCandidate,
    GroundingStatus,
    LinkageHint,
    ObservationMode,
    OverallPolicy,
    PhaseMinusOneEnvelope,
    ResolutionPolicy,
)
from .phase_minus_one_grounding import ObserverObservedGrounding
from .phase_minus_one_ambiguity import AmbiguityResolver
from .phase_minus_one_clause_splitter import ConservativeClauseSplitter


class PhaseMinusOnePipeline:
    """
    Phase −1 Pipeline Orchestrator.

    Coordinates clause splitting, grounding analysis, and ambiguity resolution
    to produce a complete grounding envelope.

    Usage:
        pipeline = PhaseMinusOnePipeline()
        envelope = pipeline.run("I'm worried because she seems sad.")
        # envelope.overall_policy == MULTI_CONTEXT
        # envelope.clauses[0].selected.mode == REFLEXIVE
        # envelope.clauses[1].selected.mode == RELATIONAL
    """

    def __init__(
        self,
        grounding_engine: ObserverObservedGrounding | None = None,
        resolver: AmbiguityResolver | None = None,
        splitter: ConservativeClauseSplitter | None = None,
    ) -> None:
        """
        Initialize the Phase −1 pipeline.

        Args:
            grounding_engine: OOG engine instance.
            resolver: ARL resolver instance.
            splitter: CSL splitter instance.
        """
        self.grounding_engine = grounding_engine or ObserverObservedGrounding()
        self.resolver = resolver or AmbiguityResolver()
        self.splitter = splitter or ConservativeClauseSplitter(
            grounding_engine=self.grounding_engine,
            resolver=self.resolver,
        )

    def run(self, text: str) -> PhaseMinusOneEnvelope:
        """
        Execute the Phase −1 pipeline on input text.

        Args:
            text: The input text to analyze.

        Returns:
            PhaseMinusOneEnvelope with complete grounding analysis.
        """
        run_id = str(uuid.uuid4())[:8]

        # Handle empty input
        if not text or not text.strip():
            return PhaseMinusOneEnvelope(
                overall_policy=OverallPolicy.BLOCKED,
                clauses=[],
                selected_primary=None,
                original_text=text or "",
                was_split=False,
                debug={"reason": "empty_input"},
                run_id=run_id,
            )

        text = text.strip()

        # Step 1: Run clause splitter
        split_result = self.splitter.split(text)

        # Step 2: Analyze each clause
        clause_results: List[ClauseGroundingResult] = []

        for i, (clause_text, linkage) in enumerate(
            zip(split_result.clauses, split_result.linkage_hints)
        ):
            result = self._analyze_clause(clause_text, linkage, i)
            clause_results.append(result)

        # Step 3: Determine overall policy
        overall_policy = self._determine_overall_policy(clause_results)

        # Step 4: Select primary grounding
        selected_primary = self._select_primary(clause_results, overall_policy)

        # Step 5: Build debug info
        debug = self._build_debug_info(
            split_result, clause_results, overall_policy, selected_primary
        )

        return PhaseMinusOneEnvelope(
            overall_policy=overall_policy,
            clauses=clause_results,
            selected_primary=selected_primary,
            original_text=text,
            was_split=split_result.was_split,
            debug=debug,
            run_id=run_id,
        )

    def _analyze_clause(
        self,
        clause_text: str,
        linkage: LinkageHint,
        index: int,
    ) -> ClauseGroundingResult:
        """
        Analyze a single clause.

        Args:
            clause_text: The clause text.
            linkage: Linkage hint from splitter.
            index: Clause index (0-based).

        Returns:
            ClauseGroundingResult with grounding analysis.
        """
        # Generate candidates
        candidates = self.grounding_engine.analyze(clause_text)

        # Resolve ambiguity
        resolution = self.resolver.resolve(candidates)

        return ClauseGroundingResult(
            clause_text=clause_text,
            candidates=candidates,
            selected=resolution.selected,
            grounding_status=resolution.status,
            resolution_policy=resolution.policy,
            linkage_hint=linkage,
            clause_index=index,
        )

    def _determine_overall_policy(
        self, clauses: List[ClauseGroundingResult]
    ) -> OverallPolicy:
        """
        Determine overall pipeline policy from clause results.

        Rules:
        - If any clause has ASK_CLARIFY and selected is None → BLOCKED
        - If >1 clauses → MULTI_CONTEXT
        - Else → SINGLE_CONTEXT
        """
        if not clauses:
            return OverallPolicy.BLOCKED

        # Check for blocking conditions
        for clause in clauses:
            if (clause.resolution_policy == ResolutionPolicy.ASK_CLARIFY and
                    clause.selected is None):
                return OverallPolicy.BLOCKED

        # Check for multi-context
        if len(clauses) > 1:
            return OverallPolicy.MULTI_CONTEXT

        return OverallPolicy.SINGLE_CONTEXT

    def _select_primary(
        self,
        clauses: List[ClauseGroundingResult],
        overall_policy: OverallPolicy,
    ) -> Optional[GroundingCandidate]:
        """
        Select the primary grounding candidate.

        Rules:
        - If any ASK_CLARIFY exists → None (unsafe to select)
        - Else priority order: REFLEXIVE > RELATIONAL > DETACHED
        - Tie break by confidence
        """
        # Check for any ASK_CLARIFY
        for clause in clauses:
            if clause.resolution_policy == ResolutionPolicy.ASK_CLARIFY:
                return None

        # Collect all selected candidates
        candidates_with_priority: List[tuple] = []

        priority_map = {
            ObservationMode.REFLEXIVE: 0,
            ObservationMode.RELATIONAL: 1,
            ObservationMode.DETACHED: 2,
        }

        for clause in clauses:
            if clause.selected:
                priority = priority_map.get(clause.selected.mode, 99)
                candidates_with_priority.append(
                    (priority, -clause.selected.confidence, clause.selected)
                )

        if not candidates_with_priority:
            return None

        # Sort by priority (ascending), then by confidence (descending via negation)
        candidates_with_priority.sort(key=lambda x: (x[0], x[1]))

        return candidates_with_priority[0][2]

    def _build_debug_info(
        self,
        split_result,
        clauses: List[ClauseGroundingResult],
        overall_policy: OverallPolicy,
        selected_primary: Optional[GroundingCandidate],
    ) -> dict:
        """Build debug/metrics information."""
        # Mode distribution
        mode_dist = {}
        risk_dist = {}
        policies_used = []
        statuses = []

        for clause in clauses:
            if clause.selected:
                mode = clause.selected.mode.value
                risk = clause.selected.projection_risk.value
                mode_dist[mode] = mode_dist.get(mode, 0) + 1
                risk_dist[risk] = risk_dist.get(risk, 0) + 1
            policies_used.append(clause.resolution_policy.value)
            statuses.append(clause.grounding_status.value)

        # Confidence stats
        confidences = [
            c.selected.confidence for c in clauses if c.selected
        ]

        return {
            "split_reason": split_result.reason,
            "split_gain": split_result.gain,
            "clause_count": len(clauses),
            "mode_distribution": mode_dist,
            "risk_distribution": risk_dist,
            "policies_used": policies_used,
            "statuses": statuses,
            "blocked": overall_policy == OverallPolicy.BLOCKED,
            "confidence_stats": {
                "min": min(confidences) if confidences else 0.0,
                "max": max(confidences) if confidences else 0.0,
                "mean": sum(confidences) / len(confidences) if confidences else 0.0,
            },
            "analysis_blocked_count": sum(
                1 for c in clauses
                if c.selected and not c.selected.analysis_allowed
            ),
            "ambiguity_rate": sum(
                1 for c in clauses
                if c.grounding_status == GroundingStatus.AMBIGUOUS
            ) / len(clauses) if clauses else 0.0,
            "safe_default_rate": sum(
                1 for c in clauses
                if c.resolution_policy == ResolutionPolicy.SAFE_DEFAULT
            ) / len(clauses) if clauses else 0.0,
        }


# Public exports
__all__ = ["PhaseMinusOnePipeline"]
