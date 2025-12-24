"""
Cross-Domain Entropy Engine
============================

╔═══════════════════════════════════════════════════════════════════════════════╗
║                         STRUCTURAL COHERENCE REGULATION                        ║
║                                                                                ║
║  Measures coherence, not correctness.                                          ║
║  Never replaces routing or generation.                                         ║
║  One engine, three configurations.                                             ║
╚═══════════════════════════════════════════════════════════════════════════════╝

This is NOT a safety system.
This is NOT an AGI system.
This is structural coherence regulation ONLY.

This is Augmented General Intelligence:
    - No autonomy
    - No learning
    - No judgment
    - No policy enforcement
    - Only structural regulation

Usage:
    from symbolu.entropy import EntropyEngine, TIER_1_CONFIG, TIER_2_CONFIG, TIER_3_CONFIG

    # Create engine for a tier
    engine = EntropyEngine(TIER_1_CONFIG)

    # Or use factory function
    from symbolu.entropy import create_engine_for_tier
    engine = create_engine_for_tier("enterprise_search")

    # Evaluate entropy
    result = engine.evaluate(
        guna_profile=guna,
        kosha_source=source_kosha,
        kosha_target=target_kosha,
        domain_source=source_domain,
        domain_target=target_domain,
    )

    # Access results
    print(result.combined_entropy)  # 0.0 - 1.0
    print(result.gate)  # ALLOW | ALLOW_WITH_MODULATION | BLOCK
    print(result.mode)  # DIAGNOSTIC_ONLY | MODULATION_ONLY | FULL_GATING

Tier Authority:
    Tier 1 (Enterprise Search): DIAGNOSTIC_ONLY - no behavioral impact
    Tier 2 (Enterprise Chat):   MODULATION_ONLY - advisory only
    Tier 3 (Consumer):          FULL_GATING - expression gate only

Version: 1.0
Date: 2025-12-21
"""

# Types
from symbolu.entropy.types import (
    # Enums
    EntropyMode,
    EntropyGate,
    # Main result
    EntropyResult,
    EntropyTraceEntry,
    # Configuration
    TierConfig,
    # Input profiles
    GunaProfile,
    KoshaProfile,
    DomainProfile,
)

# Engine
from symbolu.entropy.entropy_engine import (
    EntropyEngine,
    create_engine,
    create_engine_for_tier,
    explain_entropy_result,
)

# Configurations
from symbolu.entropy.config import (
    TIER_1_CONFIG,
    TIER_2_CONFIG,
    TIER_3_CONFIG,
    get_tier_config,
    list_tiers,
    create_custom_config,
)

# Individual entropy computations (for advanced use)
from symbolu.entropy.guna_entropy import (
    compute_guna_entropy,
    compute_guna_entropy_from_dict,
)
from symbolu.entropy.kosha_entropy import (
    compute_kosha_entropy,
    compute_kosha_entropy_simple,
    KOSHA_ORDER,
)
from symbolu.entropy.cross_domain_entropy import (
    compute_cross_domain_entropy,
    compute_structural_distance,
    detect_incompatibility_pattern,
    DIMENSION_NAMES,
)


__all__ = [
    # Enums
    "EntropyMode",
    "EntropyGate",
    # Main types
    "EntropyResult",
    "EntropyTraceEntry",
    "TierConfig",
    # Input profiles
    "GunaProfile",
    "KoshaProfile",
    "DomainProfile",
    # Engine
    "EntropyEngine",
    "create_engine",
    "create_engine_for_tier",
    "explain_entropy_result",
    # Configurations
    "TIER_1_CONFIG",
    "TIER_2_CONFIG",
    "TIER_3_CONFIG",
    "get_tier_config",
    "list_tiers",
    "create_custom_config",
    # Individual computations
    "compute_guna_entropy",
    "compute_guna_entropy_from_dict",
    "compute_kosha_entropy",
    "compute_kosha_entropy_simple",
    "compute_cross_domain_entropy",
    "compute_structural_distance",
    "detect_incompatibility_pattern",
    # Constants
    "KOSHA_ORDER",
    "DIMENSION_NAMES",
]


# =============================================================================
# Quick Start Examples
# =============================================================================

def _example_usage():
    """
    Example usage of the Entropy Engine.

    This function demonstrates the key patterns for using the engine.
    It is not meant to be called in production.
    """
    # Create engine for Tier 1 (Enterprise Search)
    engine_t1 = EntropyEngine(TIER_1_CONFIG)

    # Create profiles
    guna = GunaProfile(sattva=0.4, rajas=0.3, tamas=0.3)
    source_kosha = KoshaProfile(
        annamaya=0.1, pranamaya=0.2, manomaya=0.6,
        vijnanamaya=0.1, anandamaya=0.0
    )
    target_kosha = KoshaProfile(
        annamaya=0.0, pranamaya=0.1, manomaya=0.3,
        vijnanamaya=0.6, anandamaya=0.0
    )

    # Evaluate
    result = engine_t1.evaluate(
        guna_profile=guna,
        kosha_source=source_kosha,
        kosha_target=target_kosha,
    )

    # In Tier 1, gate is always ALLOW (diagnostic only)
    assert result.gate == EntropyGate.ALLOW
    assert result.mode == EntropyMode.DIAGNOSTIC_ONLY

    # Create engine for Tier 3 (Consumer)
    engine_t3 = EntropyEngine(TIER_3_CONFIG)

    # Same evaluation, different tier behavior
    result_t3 = engine_t3.evaluate(
        guna_profile=guna,
        kosha_source=source_kosha,
        kosha_target=target_kosha,
    )

    # In Tier 3, gate depends on entropy level
    # Could be ALLOW, ALLOW_WITH_MODULATION, or BLOCK
    assert result_t3.mode == EntropyMode.FULL_GATING

    return result, result_t3
