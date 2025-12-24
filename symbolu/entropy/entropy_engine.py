"""
Cross-Domain Entropy Engine
============================

╔═══════════════════════════════════════════════════════════════════════════════╗
║                         CORE/SUBSTRATE LAYER                                   ║
║                                                                                ║
║  Unified Entropy Engine for cross-domain coherence measurement.                ║
║  Single entry point with tier-specific configurations.                         ║
╚═══════════════════════════════════════════════════════════════════════════════╝

This is NOT a safety system.
This is NOT an AGI system.
This is structural coherence regulation ONLY.

The Entropy Engine:
    - Computes structural entropy across guna, kosha, and cross-domain dimensions
    - Produces metrics only
    - Applies tier-specific behavior via configuration
    - Never breaks existing pipelines

Authority scales by tier:
    - Tier 1 (Enterprise Search): DIAGNOSTIC_ONLY - no behavioral impact
    - Tier 2 (Enterprise Chat): MODULATION_ONLY - advisory only
    - Tier 3 (Consumer): FULL_GATING - expression gate only

Key Guarantees:
    - Deterministic: same input → same output
    - Auditable: full explainability trace
    - Non-invasive: if removed, system still functions correctly

Version: 1.0
Date: 2025-12-21
"""

from typing import Optional, Dict, Any, Tuple, List
from dataclasses import dataclass

from symbolu.entropy.types import (
    EntropyResult,
    EntropyGate,
    EntropyMode,
    EntropyTraceEntry,
    TierConfig,
    GunaProfile,
    KoshaProfile,
    DomainProfile,
)
from symbolu.entropy.guna_entropy import compute_guna_entropy
from symbolu.entropy.kosha_entropy import compute_kosha_entropy
from symbolu.entropy.cross_domain_entropy import (
    compute_cross_domain_entropy,
    detect_incompatibility_pattern,
)


# =============================================================================
# Entropy Engine (Single Entry Point)
# =============================================================================

class EntropyEngine:
    """
    Unified Entropy Engine for cross-domain coherence measurement.

    The same code runs everywhere - only configuration differs by tier.
    This preserves: one mental model, one math, one truth.

    Usage:
        # Create engine with tier configuration
        config = TIER_1_CONFIG  # or TIER_2_CONFIG, TIER_3_CONFIG
        engine = EntropyEngine(config)

        # Evaluate entropy
        result = engine.evaluate(
            guna_profile=guna_profile,
            kosha_source=source_kosha,
            kosha_target=target_kosha,
            domain_source=source_domain,
            domain_target=target_domain,
        )

        # Check result
        print(result.combined_entropy)  # 0.0 - 1.0
        print(result.gate)  # ALLOW | ALLOW_WITH_MODULATION | BLOCK
        print(result.mode)  # DIAGNOSTIC_ONLY | MODULATION_ONLY | FULL_GATING

    Determinism:
        The engine is fully deterministic. Same inputs always produce same outputs.
        No randomness, no ML, no embeddings inside entropy math.
    """

    def __init__(self, config: TierConfig):
        """
        Initialize the Entropy Engine with tier configuration.

        Args:
            config: TierConfig specifying tier-specific behavior
        """
        self._config = config

    @property
    def config(self) -> TierConfig:
        """Get the current configuration."""
        return self._config

    @property
    def tier_name(self) -> str:
        """Get the tier name."""
        return self._config.tier_name

    @property
    def mode(self) -> EntropyMode:
        """Get the operating mode."""
        return self._config.mode

    def evaluate(
        self,
        *,
        guna_profile: Optional[GunaProfile] = None,
        kosha_source: Optional[KoshaProfile] = None,
        kosha_target: Optional[KoshaProfile] = None,
        domain_source: Optional[DomainProfile] = None,
        domain_target: Optional[DomainProfile] = None,
    ) -> EntropyResult:
        """
        Evaluate entropy across all dimensions.

        This is the main entry point for entropy computation.
        All parameters are keyword-only for clarity.

        Args:
            guna_profile: Guna distribution for internal balance check
            kosha_source: Source kosha profile (where input originates)
            kosha_target: Target kosha profile (what domain is invoked)
            domain_source: Source domain structural profile
            domain_target: Target domain structural profile

        Returns:
            EntropyResult with all metrics, gate classification, and trace

        Notes:
            - Missing profiles are handled gracefully (default to 0.0 entropy)
            - All entropy values are in [0.0, 1.0]
            - Gate is determined by tier configuration
        """
        trace_entries: List[EntropyTraceEntry] = []

        # 1. Compute Guna Entropy
        if guna_profile is not None:
            guna_entropy, guna_trace = compute_guna_entropy(guna_profile)
            trace_entries.append(guna_trace)
        else:
            guna_entropy = 0.0
            trace_entries.append(EntropyTraceEntry(
                metric_name="guna_entropy",
                value=0.0,
                reason="No guna profile provided",
                components=(),
            ))

        # 2. Compute Kosha Entropy
        if kosha_source is not None and kosha_target is not None:
            kosha_entropy, kosha_trace = compute_kosha_entropy(kosha_source, kosha_target)
            trace_entries.append(kosha_trace)
        else:
            kosha_entropy = 0.0
            trace_entries.append(EntropyTraceEntry(
                metric_name="kosha_entropy",
                value=0.0,
                reason="Incomplete kosha profiles (source or target missing)",
                components=(),
            ))

        # 3. Compute Cross-Domain Entropy
        if domain_source is not None and domain_target is not None:
            cross_entropy, cross_trace = compute_cross_domain_entropy(
                domain_source, domain_target
            )
            trace_entries.append(cross_trace)

            # Check for known incompatibility patterns
            pattern = detect_incompatibility_pattern(domain_source, domain_target)
            if pattern:
                trace_entries.append(EntropyTraceEntry(
                    metric_name="incompatibility_pattern",
                    value=1.0,
                    reason=pattern,
                    components=(),
                ))
        else:
            cross_entropy = 0.0
            trace_entries.append(EntropyTraceEntry(
                metric_name="cross_domain_entropy",
                value=0.0,
                reason="Incomplete domain profiles (source or target missing)",
                components=(),
            ))

        # 4. Compute Combined Entropy (weighted sum)
        combined_entropy = (
            self._config.guna_weight * guna_entropy +
            self._config.kosha_weight * kosha_entropy +
            self._config.cross_domain_weight * cross_entropy
        )

        # Clamp to [0.0, 1.0]
        combined_entropy = max(0.0, min(1.0, combined_entropy))

        # 5. Determine Gate based on configuration
        gate = self._determine_gate(combined_entropy)

        # 6. Build result
        return EntropyResult(
            guna_entropy=guna_entropy,
            kosha_entropy=kosha_entropy,
            cross_domain_entropy=cross_entropy,
            combined_entropy=combined_entropy,
            gate=gate,
            mode=self._config.mode,
            trace=tuple(trace_entries),
        )

    def _determine_gate(self, combined_entropy: float) -> EntropyGate:
        """
        Determine the gate classification based on entropy and configuration.

        The gate is determined by:
        1. The combined entropy value
        2. The tier configuration (mode)

        Rules:
        - DIAGNOSTIC_ONLY: Always ALLOW (no behavioral impact)
        - MODULATION_ONLY: ALLOW or ALLOW_WITH_MODULATION (no blocking)
        - FULL_GATING: ALLOW, ALLOW_WITH_MODULATION, or BLOCK
        """
        config = self._config

        # Tier 1: Diagnostic only - always ALLOW
        if config.mode == EntropyMode.DIAGNOSTIC_ONLY:
            return EntropyGate.ALLOW

        # Tier 2: Modulation only - no blocking
        if config.mode == EntropyMode.MODULATION_ONLY:
            if combined_entropy >= config.modulation_threshold:
                return EntropyGate.ALLOW_WITH_MODULATION
            return EntropyGate.ALLOW

        # Tier 3: Full gating
        if config.mode == EntropyMode.FULL_GATING:
            if combined_entropy >= config.block_threshold:
                return EntropyGate.BLOCK
            if combined_entropy >= config.modulation_threshold:
                return EntropyGate.ALLOW_WITH_MODULATION
            return EntropyGate.ALLOW

        # Fallback (should never reach here)
        return EntropyGate.ALLOW

    def evaluate_guna_only(self, guna_profile: GunaProfile) -> Tuple[float, EntropyTraceEntry]:
        """
        Evaluate only guna entropy.

        Convenience method for cases where only guna analysis is needed.

        Args:
            guna_profile: Guna distribution profile

        Returns:
            Tuple of (entropy_value, trace_entry)
        """
        return compute_guna_entropy(guna_profile)

    def evaluate_kosha_only(
        self,
        source: KoshaProfile,
        target: KoshaProfile,
    ) -> Tuple[float, EntropyTraceEntry]:
        """
        Evaluate only kosha entropy.

        Convenience method for cases where only kosha analysis is needed.

        Args:
            source: Source kosha profile
            target: Target kosha profile

        Returns:
            Tuple of (entropy_value, trace_entry)
        """
        return compute_kosha_entropy(source, target)

    def evaluate_cross_domain_only(
        self,
        source: DomainProfile,
        target: DomainProfile,
    ) -> Tuple[float, EntropyTraceEntry]:
        """
        Evaluate only cross-domain entropy.

        Convenience method for cases where only cross-domain analysis is needed.

        Args:
            source: Source domain profile
            target: Target domain profile

        Returns:
            Tuple of (entropy_value, trace_entry)
        """
        return compute_cross_domain_entropy(source, target)


# =============================================================================
# Factory Functions
# =============================================================================

def create_engine(config: TierConfig) -> EntropyEngine:
    """
    Create an EntropyEngine with the given configuration.

    Args:
        config: TierConfig specifying tier-specific behavior

    Returns:
        Configured EntropyEngine instance
    """
    return EntropyEngine(config)


def create_engine_for_tier(tier_name: str) -> EntropyEngine:
    """
    Create an EntropyEngine for a named tier.

    Args:
        tier_name: One of "enterprise_search", "enterprise_chat", "consumer"

    Returns:
        Configured EntropyEngine instance

    Raises:
        ValueError: If tier_name is unknown
    """
    from symbolu.entropy.config import get_tier_config
    config = get_tier_config(tier_name)
    return EntropyEngine(config)


# =============================================================================
# Diagnostic Helpers
# =============================================================================

def explain_entropy_result(result: EntropyResult) -> Dict[str, Any]:
    """
    Generate a human-readable explanation of an entropy result.

    Args:
        result: EntropyResult to explain

    Returns:
        Dictionary with explanation details
    """
    explanation = {
        "summary": _generate_summary(result),
        "metrics": {
            "guna_entropy": result.guna_entropy,
            "kosha_entropy": result.kosha_entropy,
            "cross_domain_entropy": result.cross_domain_entropy,
            "combined_entropy": result.combined_entropy,
        },
        "gate": result.gate.value,
        "mode": result.mode.value,
        "reasons": [entry.reason for entry in result.trace],
    }

    # Add action recommendation based on gate
    if result.gate == EntropyGate.ALLOW:
        explanation["action"] = "Proceed normally"
    elif result.gate == EntropyGate.ALLOW_WITH_MODULATION:
        explanation["action"] = "Proceed with tone/verbosity adjustment"
    elif result.gate == EntropyGate.BLOCK:
        explanation["action"] = "Expression blocked due to structural incoherence"

    return explanation


def _generate_summary(result: EntropyResult) -> str:
    """Generate a one-line summary of the entropy result."""
    level = "low" if result.combined_entropy < 0.3 else (
        "moderate" if result.combined_entropy < 0.6 else "high"
    )

    if result.mode == EntropyMode.DIAGNOSTIC_ONLY:
        return f"Diagnostic: {level} entropy ({result.combined_entropy:.2f})"

    if result.gate == EntropyGate.ALLOW:
        return f"Coherent: {level} entropy ({result.combined_entropy:.2f})"
    elif result.gate == EntropyGate.ALLOW_WITH_MODULATION:
        return f"Modulating: {level} entropy ({result.combined_entropy:.2f})"
    else:
        return f"Blocked: {level} entropy ({result.combined_entropy:.2f})"
