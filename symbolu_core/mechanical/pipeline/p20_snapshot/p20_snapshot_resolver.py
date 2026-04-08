"""
P20 - Unified Cognitive Snapshot Resolver

Main resolver class that assembles a unified cognitive snapshot from pipeline context.
This is a pure read-only aggregation layer with zero computation.

Design Principles:
    - Read-Only: Never modifies upstream context
    - Deterministic: Same inputs always produce same outputs
    - No Computation: Copies values verbatim (no formulas, no thresholds)
    - No Gating: Does not influence any pipeline behavior
    - Non-Invasive: Zero impact on routing, scoring, or rendering

CRITICAL CONSTRAINTS:
    Must NOT:
        - Infer or derive new values
        - Apply formulas or thresholds
        - Gate or block any behavior
        - Modify any upstream state
        - Trigger any side effects
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple

from symbolu_core.mechanical.pipeline.p20_snapshot.p20_unified_snapshot_schema import (
    P20_VERSION,
    UnifiedCognitiveSnapshot,
    create_snapshot,
)


# ============================================================================
# RESOLVER CLASS
# ============================================================================


class P20UnifiedSnapshotResolver:
    """
    P20 Unified Cognitive Snapshot Resolver - Read-only aggregation.

    Assembles a snapshot of cognitive state from pipeline context by reading
    existing fields. Performs no computation, gating, or behavior modification.

    Usage:
        resolver = P20UnifiedSnapshotResolver()
        snapshot = resolver.resolve(ctx)

    The snapshot contains:
        - Coherence metrics (v3, quality)
        - Entropy metrics (diff, volatility)
        - Drift metrics (index, band, tags)
        - Integrity/harmony metrics
        - Domain/activation info
        - Phase completion flags
    """

    def __init__(self) -> None:
        """Initialize the P20 Unified Snapshot resolver."""
        self._version = P20_VERSION

    @property
    def version(self) -> str:
        """Get the resolver version."""
        return self._version

    def resolve(self, ctx: Any) -> UnifiedCognitiveSnapshot:
        """
        Resolve a unified cognitive snapshot from pipeline context.

        This is the main entry point for P20 resolution. It:
        1. Reads existing fields from context (verbatim copy)
        2. Assembles the snapshot
        3. Attaches timestamp and run_id
        4. Returns the immutable snapshot

        This method NEVER writes back to context.

        Args:
            ctx: PipelineContext or compatible object

        Returns:
            UnifiedCognitiveSnapshot with collected metrics
        """
        # Generate timestamp and run_id
        timestamp = datetime.now(timezone.utc)
        run_id = self._generate_run_id(ctx)

        # Extract all values (read-only)
        coherence_v3 = self._extract_coherence_v3(ctx)
        coherence_quality = self._extract_coherence_quality(ctx)
        temporal_entropy_diff = self._extract_temporal_entropy_diff(ctx)
        temporal_entropy_volatility = self._extract_temporal_entropy_volatility(ctx)
        drift_fusion_index = self._extract_drift_fusion_index(ctx)
        drift_risk_band = self._extract_drift_risk_band(ctx)
        drift_pattern_tags = self._extract_drift_pattern_tags(ctx)
        semantic_integrity = self._extract_semantic_integrity(ctx)
        symbolic_harmony = self._extract_symbolic_harmony(ctx)
        active_domains = self._extract_active_domains(ctx)
        phase_completion_flags = self._build_phase_completion_flags(ctx)

        # Assemble and return snapshot
        return create_snapshot(
            timestamp=timestamp,
            run_id=run_id,
            coherence_v3=coherence_v3,
            coherence_quality=coherence_quality,
            temporal_entropy_diff=temporal_entropy_diff,
            temporal_entropy_volatility=temporal_entropy_volatility,
            drift_fusion_index=drift_fusion_index,
            drift_risk_band=drift_risk_band,
            drift_pattern_tags=drift_pattern_tags,
            semantic_integrity=semantic_integrity,
            symbolic_harmony=symbolic_harmony,
            active_domains=active_domains,
            phase_completion_flags=phase_completion_flags,
        )

    # -------------------------------------------------------------------------
    # Private extraction methods (read-only)
    # -------------------------------------------------------------------------

    def _generate_run_id(self, ctx: Any) -> str:
        """
        Generate a run ID for this snapshot.

        Prefers existing run_id from context if available.

        Args:
            ctx: Pipeline context

        Returns:
            Run ID string
        """
        # Try to get existing run_id from context
        existing_run_id = getattr(ctx, "run_id", None)
        if existing_run_id is not None and isinstance(existing_run_id, str):
            return existing_run_id

        # Try to get from request metadata
        request = getattr(ctx, "request", None)
        if request is not None:
            metadata = getattr(request, "metadata", None)
            if isinstance(metadata, dict):
                run_id = metadata.get("run_id")
                if run_id is not None and isinstance(run_id, str):
                    return run_id

        # Generate new UUID
        return str(uuid.uuid4())

    def _extract_coherence_v3(self, ctx: Any) -> Optional[float]:
        """
        Extract coherence v3 score from context.

        Checks:
        1. ctx.coherence_state.coherence_score_v3

        Args:
            ctx: Pipeline context

        Returns:
            Coherence v3 in [0, 1], or None if not available
        """
        coherence_state = getattr(ctx, "coherence_state", None)
        if coherence_state is None:
            return None

        score = getattr(coherence_state, "coherence_score_v3", None)
        if score is not None and isinstance(score, (int, float)):
            return float(score)

        return None

    def _extract_coherence_quality(self, ctx: Any) -> Optional[float]:
        """
        Extract coherence v3 quality metric from context.

        Checks:
        1. ctx.coherence_state.coherence_v3_quality

        Args:
            ctx: Pipeline context

        Returns:
            Coherence quality in [0, 1], or None if not available
        """
        coherence_state = getattr(ctx, "coherence_state", None)
        if coherence_state is None:
            return None

        quality = getattr(coherence_state, "coherence_v3_quality", None)
        if quality is not None and isinstance(quality, (int, float)):
            return float(quality)

        return None

    def _extract_temporal_entropy_diff(self, ctx: Any) -> Optional[float]:
        """
        Extract temporal entropy diff from context (Phase 18).

        Checks:
        1. ctx.p18.entropy_now
        2. ctx.coherence_state.temporal_entropy_diff

        Args:
            ctx: Pipeline context

        Returns:
            Entropy diff in [0, 1], or None if not available
        """
        # Try P18 report first
        p18 = getattr(ctx, "p18", None)
        if p18 is not None:
            entropy_now = getattr(p18, "entropy_now", None)
            if entropy_now is not None and isinstance(entropy_now, (int, float)):
                return float(entropy_now)

        # Fall back to coherence_state
        coherence_state = getattr(ctx, "coherence_state", None)
        if coherence_state is not None:
            diff = getattr(coherence_state, "temporal_entropy_diff", None)
            if diff is not None and isinstance(diff, (int, float)):
                return float(diff)

        return None

    def _extract_temporal_entropy_volatility(self, ctx: Any) -> Optional[float]:
        """
        Extract temporal entropy volatility from context (Phase 18).

        Checks:
        1. ctx.coherence_state.temporal_entropy_volatility

        Args:
            ctx: Pipeline context

        Returns:
            Volatility in [0, 1], or None if not available
        """
        coherence_state = getattr(ctx, "coherence_state", None)
        if coherence_state is not None:
            vol = getattr(coherence_state, "temporal_entropy_volatility", None)
            if vol is not None and isinstance(vol, (int, float)):
                return float(vol)

        return None

    def _extract_drift_fusion_index(self, ctx: Any) -> Optional[float]:
        """
        Extract drift fusion index from context (Phase 19).

        Checks:
        1. ctx.p19.drift_fusion_index
        2. ctx.coherence_state.drift_fusion_index

        Args:
            ctx: Pipeline context

        Returns:
            Drift index in [0, 1], or None if not available
        """
        # Try P19 report first
        p19 = getattr(ctx, "p19", None)
        if p19 is not None:
            index = getattr(p19, "drift_fusion_index", None)
            if index is not None and isinstance(index, (int, float)):
                return float(index)

        # Fall back to coherence_state
        coherence_state = getattr(ctx, "coherence_state", None)
        if coherence_state is not None:
            index = getattr(coherence_state, "drift_fusion_index", None)
            if index is not None and isinstance(index, (int, float)):
                return float(index)

        return None

    def _extract_drift_risk_band(self, ctx: Any) -> Optional[str]:
        """
        Extract drift risk band from context (Phase 19).

        Checks:
        1. ctx.p19.drift_risk_band
        2. ctx.coherence_state.drift_risk_band

        Args:
            ctx: Pipeline context

        Returns:
            Risk band string ("low"/"moderate"/"high"), or None if not available
        """
        # Try P19 report first
        p19 = getattr(ctx, "p19", None)
        if p19 is not None:
            band = getattr(p19, "drift_risk_band", None)
            if band is not None and isinstance(band, str):
                return band

        # Fall back to coherence_state
        coherence_state = getattr(ctx, "coherence_state", None)
        if coherence_state is not None:
            band = getattr(coherence_state, "drift_risk_band", None)
            if band is not None and isinstance(band, str):
                return band

        return None

    def _extract_drift_pattern_tags(self, ctx: Any) -> Tuple[str, ...]:
        """
        Extract drift pattern tags from context (Phase 19).

        Checks:
        1. ctx.p19.drift_pattern_tags
        2. ctx.coherence_state.drift_pattern_tags

        Args:
            ctx: Pipeline context

        Returns:
            Tuple of tag strings, or empty tuple if not available
        """
        # Try P19 report first
        p19 = getattr(ctx, "p19", None)
        if p19 is not None:
            tags = getattr(p19, "drift_pattern_tags", None)
            if tags is not None:
                if isinstance(tags, tuple):
                    return tags
                elif isinstance(tags, (list, set)):
                    return tuple(tags)

        # Fall back to coherence_state
        coherence_state = getattr(ctx, "coherence_state", None)
        if coherence_state is not None:
            tags = getattr(coherence_state, "drift_pattern_tags", None)
            if tags is not None:
                if isinstance(tags, tuple):
                    return tags
                elif isinstance(tags, (list, set)):
                    return tuple(tags)

        return ()

    def _extract_semantic_integrity(self, ctx: Any) -> Optional[float]:
        """
        Extract semantic integrity score from context (Phase 17).

        Checks:
        1. ctx.p17.integrity_score
        2. ctx.coherence_state.semantic_integrity_score

        Args:
            ctx: Pipeline context

        Returns:
            Semantic integrity in [0, 1], or None if not available
        """
        # Try P17 report first
        p17 = getattr(ctx, "p17", None)
        if p17 is not None:
            score = getattr(p17, "integrity_score", None)
            if score is not None and isinstance(score, (int, float)):
                return float(score)

        # Fall back to coherence_state
        coherence_state = getattr(ctx, "coherence_state", None)
        if coherence_state is not None:
            score = getattr(coherence_state, "semantic_integrity_score", None)
            if score is not None and isinstance(score, (int, float)):
                return float(score)

        return None

    def _extract_symbolic_harmony(self, ctx: Any) -> Optional[float]:
        """
        Extract symbolic harmony/harmonization index from context (Phase 27).

        Checks:
        1. ctx.coherence_state.current_symbolic_harmonization_index

        Args:
            ctx: Pipeline context

        Returns:
            Symbolic harmony in [0, 1], or None if not available
        """
        coherence_state = getattr(ctx, "coherence_state", None)
        if coherence_state is not None:
            harmony = getattr(coherence_state, "current_symbolic_harmonization_index", None)
            if harmony is not None and isinstance(harmony, (int, float)):
                return float(harmony)

        return None

    def _extract_active_domains(self, ctx: Any) -> Tuple[str, ...]:
        """
        Extract active domain names from context.

        Checks:
        1. ctx.coherence_state.domain_history (most recent)
        2. ctx.mlcr.activation_plan (domain field)

        Args:
            ctx: Pipeline context

        Returns:
            Tuple of domain names, or empty tuple if not available
        """
        domains = []

        # Try coherence_state domain_history
        coherence_state = getattr(ctx, "coherence_state", None)
        if coherence_state is not None:
            domain_history = getattr(coherence_state, "domain_history", None)
            if domain_history and isinstance(domain_history, list):
                # Get unique domains from history
                for d in domain_history:
                    if isinstance(d, str) and d not in domains:
                        domains.append(d)

        # Try MLCR activation plan
        mlcr = getattr(ctx, "mlcr", None)
        if mlcr is not None:
            activation_plan = getattr(mlcr, "activation_plan", None)
            if isinstance(activation_plan, dict):
                domain = activation_plan.get("domain")
                if isinstance(domain, str) and domain not in domains:
                    domains.append(domain)

        return tuple(domains)

    def _build_phase_completion_flags(self, ctx: Any) -> Dict[str, bool]:
        """
        Build phase completion flags from context.

        Checks for presence of phase-specific artifacts to determine completion.

        Args:
            ctx: Pipeline context

        Returns:
            Dict mapping phase names to completion status
        """
        flags: Dict[str, bool] = {}

        # Phase -1: Grounding
        flags["phase_minus_one"] = getattr(ctx, "phase_minus_one", None) is not None

        # Phase 0: Intent
        flags["phase_zero"] = getattr(ctx, "phase_zero", None) is not None

        # Phase 1: Action binding
        flags["phase_one"] = getattr(ctx, "allowed_actions", None) is not None

        # PO4: Planner proposal
        flags["po4"] = getattr(ctx, "po4_proposal", None) is not None

        # PO5: Execution eligibility
        flags["po5"] = getattr(ctx, "po5_execution_eligibility", None) is not None

        # P6: Regime selection
        flags["p6"] = getattr(ctx, "p6_regime", None) is not None

        # P7: Discourse act
        flags["p7"] = getattr(ctx, "p7_discourse_envelope", None) is not None

        # P8: Semantic frame
        flags["p8"] = getattr(ctx, "semantic_frame", None) is not None

        # P9: Lexical frame
        flags["p9"] = getattr(ctx, "lexical_frame", None) is not None

        # P10: Acoustic params
        flags["p10"] = getattr(ctx, "p10_acoustic", None) is not None

        # P11: Prosodic evidence
        flags["p11"] = getattr(ctx, "p11_prosodic_evidence", None) is not None

        # P12: Consistency
        flags["p12"] = getattr(ctx, "p12_consistency", None) is not None

        # P13: Acoustic safety
        flags["p13"] = getattr(ctx, "p13_safety_envelope", None) is not None

        # P14: Surface plan
        flags["p14"] = getattr(ctx, "p14_surface", None) is not None

        # P15: Interaction directive
        flags["p15"] = getattr(ctx, "interaction_directive", None) is not None

        # P16: Regression guard
        flags["p16"] = getattr(ctx, "p16_guard_result", None) is not None

        # P17: Semantic integrity
        flags["p17"] = getattr(ctx, "p17", None) is not None

        # P18: Temporal entropy
        flags["p18"] = getattr(ctx, "p18", None) is not None

        # P19: Drift fusion (check both context and coherence_state)
        p19_from_ctx = getattr(ctx, "p19", None) is not None
        coherence_state = getattr(ctx, "coherence_state", None)
        p19_from_coherence = (
            coherence_state is not None and
            getattr(coherence_state, "drift_fusion_index", None) is not None
        )
        flags["p19"] = p19_from_ctx or p19_from_coherence

        return flags


# Public exports
__all__ = [
    "P20UnifiedSnapshotResolver",
]
