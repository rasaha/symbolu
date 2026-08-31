"""
Stitching-to-Fusion Handoff Contract
=====================================

This module defines the ONLY interface between Stitching and Fusion.
It enforces the boundary requirements from the specification.

NORMATIVE REQUIREMENTS (from spec Section 0.3):
- MUST use an explicit handoff object between Stitching and Fusion
- MUST NOT allow rejected candidate IDs or metadata to cross the boundary
- MUST treat Stitching -> Fusion as a one-way, non-feedback boundary

CRITICAL: Fusion code MUST import from this module, NOT from contracts.py.
This enforces that Fusion cannot access StitchingDecision internals.

Reference: Project_documentation/repository/docs/architecture/STITCHING_FUSION_SPECIFICATION.md
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, TYPE_CHECKING
import uuid

if TYPE_CHECKING:
    # Only for type hints - Fusion should not import these at runtime
    from agentic.core.stitching.contracts import StitchingDecision


@dataclass
class StitchingToFusionHandoff:
    """
    Contract for data passed from Stitching to Fusion.

    This object explicitly defines what crosses the boundary:
    - allowed_candidates: Candidate objects that passed Stitching
    - context: FusionContext for downstream processing

    This object explicitly EXCLUDES:
    - Stitching diagnostic scores
    - Rejection reasons
    - Penalty breakdowns
    - Rejected candidates
    - Any Stitching internal state

    USAGE:
        # In orchestrator:
        decision = stitching_engine.evaluate(candidates, query_context)
        handoff = StitchingToFusionHandoff.from_decision(
            decision, candidates, fusion_context
        )
        ranking = fusion_engine.rank(handoff)
    """

    # PASSED: Allowed candidates only
    # These are the actual Candidate objects, filtered to only allowed ones
    allowed_candidates: List[Any]

    # PASSED: Context for Fusion (tier, intent, domain, etc.)
    context: Any  # FusionContext

    # PASSED: Audit reference for traceability (ID only, no data)
    stitching_audit_id: Optional[str] = None

    # PASSED: Cross-domain metadata (informational only, not for scoring)
    cross_domain_info: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """Validate handoff constraints."""
        # Ensure we have a list (not generator or other iterable)
        if not isinstance(self.allowed_candidates, list):
            self.allowed_candidates = list(self.allowed_candidates)

        # Generate audit ID if not provided
        if self.stitching_audit_id is None:
            self.stitching_audit_id = str(uuid.uuid4())[:8]

    @classmethod
    def from_decision(
        cls,
        decision: "StitchingDecision",
        all_candidates: List[Any],
        context: Any,
    ) -> "StitchingToFusionHandoff":
        """
        Create handoff from Stitching output.

        This factory method:
        1. Filters to allowed candidates only
        2. Strips all diagnostic information
        3. Creates a clean handoff object

        IMPORTANT: This is the ONLY correct way to create a handoff.
        Do NOT manually construct handoff with rejected candidates.

        Args:
            decision: StitchingDecision from evaluate()
            all_candidates: Original candidate list
            context: FusionContext for downstream

        Returns:
            StitchingToFusionHandoff with only allowed candidates
        """
        # Build set of allowed IDs for fast lookup
        allowed_ids = set(decision.allowed_candidate_ids)

        # Filter to allowed candidates only
        # CRITICAL: Rejected candidates are NOT included
        allowed = [
            c for c in all_candidates
            if getattr(c, 'id', None) in allowed_ids
        ]

        # Extract minimal cross-domain info (no scores)
        cross_domain_info = {
            "cross_domain_count": decision.diagnostics.get("cross_domain_count", 0),
            "domains_involved": decision.diagnostics.get("domains_involved", []),
        }

        return cls(
            allowed_candidates=allowed,
            context=context,
            stitching_audit_id=decision.audit.get("audit_id"),
            cross_domain_info=cross_domain_info,
        )

    def get_candidate_ids(self) -> List[str]:
        """Get IDs of allowed candidates."""
        return [getattr(c, 'id', f'unknown_{i}') for i, c in enumerate(self.allowed_candidates)]

    def is_empty(self) -> bool:
        """Check if handoff has no candidates."""
        return len(self.allowed_candidates) == 0

    def __len__(self) -> int:
        """Number of allowed candidates."""
        return len(self.allowed_candidates)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize for logging (minimal info)."""
        return {
            "allowed_candidate_count": len(self.allowed_candidates),
            "allowed_candidate_ids": self.get_candidate_ids(),
            "stitching_audit_id": self.stitching_audit_id,
            "cross_domain_info": self.cross_domain_info,
        }


def create_handoff(
    decision: "StitchingDecision",
    all_candidates: List[Any],
    context: Any,
) -> StitchingToFusionHandoff:
    """
    Convenience function to create handoff.

    Equivalent to StitchingToFusionHandoff.from_decision().

    Args:
        decision: StitchingDecision from evaluate()
        all_candidates: Original candidate list
        context: FusionContext for downstream

    Returns:
        StitchingToFusionHandoff with only allowed candidates
    """
    return StitchingToFusionHandoff.from_decision(decision, all_candidates, context)


__all__ = [
    "StitchingToFusionHandoff",
    "create_handoff",
]
