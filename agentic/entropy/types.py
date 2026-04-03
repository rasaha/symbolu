"""
Cross-Domain Entropy Engine - Type Definitions
===============================================

╔═══════════════════════════════════════════════════════════════════════════════╗
║                         CORE/SUBSTRATE LAYER                                   ║
║                                                                                ║
║  This module is part of the Core/Substrate layer.                              ║
║  It provides structural coherence metrics ONLY.                                ║
║  It has NO authority over routing, generation, or policy.                      ║
╚═══════════════════════════════════════════════════════════════════════════════╝

All types are frozen (immutable) dataclasses for determinism.
All collections use immutable types (tuple, frozenset).

This is NOT a safety system.
This is NOT an AGI system.
This is structural coherence regulation ONLY.

Version: 1.0 (Cross-Domain Entropy)
Date: 2025-12-21
"""

from dataclasses import dataclass, field
from typing import Tuple, Dict, Any, Optional
from enum import Enum


# =============================================================================
# Operating Mode
# =============================================================================

class EntropyMode(Enum):
    """
    Entropy engine operating mode by tier.

    DIAGNOSTIC_ONLY: Tier 1 - Compute and log, no behavioral impact
    MODULATION_ONLY: Tier 2 - Can suggest tone/verbosity adjustment, no blocking
    FULL_GATING: Tier 3 - Full modulation + blocking for extreme incoherence

    Authority scales: DIAGNOSTIC → MODULATION → GATED
    But never becomes absolute or a decision-maker.
    """
    DIAGNOSTIC_ONLY = "DIAGNOSTIC_ONLY"
    MODULATION_ONLY = "MODULATION_ONLY"
    FULL_GATING = "FULL_GATING"


# =============================================================================
# Gate Classification
# =============================================================================

class EntropyGate(Enum):
    """
    Entropy gate classification.

    ALLOW: Entropy within acceptable bounds, proceed normally
    ALLOW_WITH_MODULATION: Entropy elevated, tone/verbosity adjustment applied
    BLOCK: Entropy exceeds hard ceiling (Consumer tier only, rare)

    Note: BLOCK is based on structural entropy, NOT policy or content rules.
    No ethical judgments. Only structural coherence regulation.
    """
    ALLOW = "ALLOW"
    ALLOW_WITH_MODULATION = "ALLOW_WITH_MODULATION"
    BLOCK = "BLOCK"


# =============================================================================
# Trace Entry (for explainability)
# =============================================================================

@dataclass(frozen=True)
class EntropyTraceEntry:
    """
    Single entry in the entropy trace for explainability.

    Every entropy score must explain WHY, numerically.
    """
    metric_name: str       # e.g., "guna_entropy"
    value: float           # 0.0 - 1.0
    reason: str            # Human-readable explanation
    components: Tuple[Tuple[str, float], ...] = field(default=())  # Breakdown

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "metric_name": self.metric_name,
            "value": self.value,
            "reason": self.reason,
            "components": dict(self.components),
        }


# =============================================================================
# Entropy Result (Main Output)
# =============================================================================

@dataclass(frozen=True)
class EntropyResult:
    """
    Complete result from entropy evaluation.

    All entropy values are in range [0.0, 1.0] where:
    - 0.0 = Perfect coherence (no entropy)
    - 1.0 = Maximum incoherence (maximum entropy)

    Attributes:
        guna_entropy: Internal imbalance across detected gunas [0.0, 1.0]
        kosha_entropy: Layer disagreement between source/target [0.0, 1.0]
        cross_domain_entropy: Structural incompatibility between domains [0.0, 1.0]
        combined_entropy: Weighted sum of all entropy values [0.0, 1.0]
        gate: Classification result (ALLOW | ALLOW_WITH_MODULATION | BLOCK)
        mode: Operating mode (DIAGNOSTIC_ONLY | MODULATION_ONLY | FULL_GATING)
        trace: Explainability trace with reasoning for each score

    Example output for Tier 1 (diagnostic only):
        {
            "entropy": {"guna": 0.42, "kosha": 0.38, "combined": 0.40},
            "gate": "ALLOW",
            "mode": "DIAGNOSTIC_ONLY"
        }
    """
    guna_entropy: float
    kosha_entropy: float
    cross_domain_entropy: float
    combined_entropy: float
    gate: EntropyGate
    mode: EntropyMode
    trace: Tuple[EntropyTraceEntry, ...]

    def __post_init__(self):
        """Validate and clamp all entropy values to [0.0, 1.0]."""
        for attr in ("guna_entropy", "kosha_entropy", "cross_domain_entropy", "combined_entropy"):
            val = getattr(self, attr)
            if val < 0.0 or val > 1.0:
                object.__setattr__(self, attr, max(0.0, min(1.0, val)))

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "guna_entropy": self.guna_entropy,
            "kosha_entropy": self.kosha_entropy,
            "cross_domain_entropy": self.cross_domain_entropy,
            "combined_entropy": self.combined_entropy,
            "gate": self.gate.value,
            "mode": self.mode.value,
            "trace": [entry.to_dict() for entry in self.trace],
        }

    @property
    def is_diagnostic_only(self) -> bool:
        """Check if this result is diagnostic only (no behavioral impact)."""
        return self.mode == EntropyMode.DIAGNOSTIC_ONLY

    @property
    def allows_modulation(self) -> bool:
        """Check if modulation is active for this result."""
        return self.gate == EntropyGate.ALLOW_WITH_MODULATION

    @property
    def is_blocked(self) -> bool:
        """Check if this result indicates blocking."""
        return self.gate == EntropyGate.BLOCK


# =============================================================================
# Tier Configuration
# =============================================================================

@dataclass(frozen=True)
class TierConfig:
    """
    Tier-specific entropy behavior configuration.

    The same Entropy Engine code runs everywhere - only configuration differs.
    This preserves: one mental model, one math, one truth.

    ┌─────────────────────────────────────────────────────────────────────────┐
    │ Tier 1 — Enterprise Search (Pure STL)                                   │
    │   mode: DIAGNOSTIC_ONLY                                                 │
    │   Authority: NONE                                                       │
    │   - Computes entropy metrics                                            │
    │   - Logs to EngineResult.metadata                                       │
    │   - No modulation, no gating                                            │
    │   - Telemetry only                                                      │
    ├─────────────────────────────────────────────────────────────────────────┤
    │ Tier 2 — Enterprise Chat (STL + 7B)                                     │
    │   mode: MODULATION_ONLY                                                 │
    │   Authority: LOW-MEDIUM (advisory)                                      │
    │   - Computes entropy metrics                                            │
    │   - Applies tone / verbosity modulation                                 │
    │   - Cannot block output                                                 │
    │   - Cannot change meaning                                               │
    ├─────────────────────────────────────────────────────────────────────────┤
    │ Tier 3 — Consumer (STL + 768D + Cascade)                                │
    │   mode: FULL_GATING                                                     │
    │   Authority: MEDIUM (expression gate only)                              │
    │   - Computes entropy metrics                                            │
    │   - Applies modulation                                                  │
    │   - Can gate expression when entropy is extreme                         │
    │   - BLOCK is rare, structural incoherence only                          │
    └─────────────────────────────────────────────────────────────────────────┘

    Attributes:
        tier_name: Identifier for the tier
        mode: Operating mode (DIAGNOSTIC_ONLY | MODULATION_ONLY | FULL_GATING)
        modulation_threshold: Entropy level to trigger modulation [0.0, 1.0]
        block_threshold: Entropy level to trigger block [0.0, 1.0]
        guna_weight: Weight for guna entropy in combined score
        kosha_weight: Weight for kosha entropy in combined score
        cross_domain_weight: Weight for cross-domain entropy in combined score
    """
    tier_name: str
    mode: EntropyMode
    modulation_threshold: float = 0.5
    block_threshold: float = 0.85
    guna_weight: float = 0.30
    kosha_weight: float = 0.30
    cross_domain_weight: float = 0.40

    def __post_init__(self):
        """Validate configuration."""
        # Ensure weights sum to 1.0
        total_weight = self.guna_weight + self.kosha_weight + self.cross_domain_weight
        if abs(total_weight - 1.0) > 0.001:
            raise ValueError(
                f"Entropy weights must sum to 1.0, got {total_weight:.3f}"
            )

        # Ensure thresholds are valid
        for attr in ("modulation_threshold", "block_threshold"):
            val = getattr(self, attr)
            if val < 0.0 or val > 1.0:
                raise ValueError(f"{attr} must be in [0.0, 1.0], got {val}")

    @property
    def allow_block(self) -> bool:
        """Check if blocking is allowed in this configuration."""
        return self.mode == EntropyMode.FULL_GATING

    @property
    def allow_modulation(self) -> bool:
        """Check if modulation is allowed in this configuration."""
        return self.mode in (EntropyMode.MODULATION_ONLY, EntropyMode.FULL_GATING)

    @property
    def is_diagnostic_only(self) -> bool:
        """Check if this is diagnostic-only mode."""
        return self.mode == EntropyMode.DIAGNOSTIC_ONLY


# =============================================================================
# Input Profiles (for entropy computation)
# =============================================================================

@dataclass(frozen=True)
class GunaProfile:
    """
    Guna distribution profile.

    Represents the three gunas (qualities) present in content/context.
    Values are probabilities that should sum to ~1.0.
    """
    sattva: float  # Clarity, harmony, balance
    rajas: float   # Activity, passion, restlessness
    tamas: float   # Inertia, darkness, obstruction

    def __post_init__(self):
        """Validate and normalize probabilities."""
        # Clamp values to [0.0, 1.0]
        for attr in ("sattva", "rajas", "tamas"):
            val = getattr(self, attr)
            if val < 0.0:
                object.__setattr__(self, attr, 0.0)
            elif val > 1.0:
                object.__setattr__(self, attr, 1.0)

    def to_dict(self) -> Dict[str, float]:
        """Convert to dictionary."""
        return {
            "sattva": self.sattva,
            "rajas": self.rajas,
            "tamas": self.tamas,
        }

    @property
    def normalized(self) -> "GunaProfile":
        """Return normalized profile where values sum to 1.0."""
        total = self.sattva + self.rajas + self.tamas
        if total == 0.0:
            return GunaProfile(sattva=1/3, rajas=1/3, tamas=1/3)
        return GunaProfile(
            sattva=self.sattva / total,
            rajas=self.rajas / total,
            tamas=self.tamas / total,
        )


@dataclass(frozen=True)
class KoshaProfile:
    """
    Kosha (sheath/layer) profile.

    Represents activation across the five koshas (consciousness layers).
    Values are in [0.0, 1.0] representing activation intensity.
    """
    annamaya: float      # Physical sheath (Layer 1)
    pranamaya: float     # Energy/vital sheath (Layer 2)
    manomaya: float      # Mental sheath (Layer 3)
    vijnanamaya: float   # Wisdom/intellect sheath (Layer 4)
    anandamaya: float    # Bliss sheath (Layer 5)

    # Canonical ordering for distance computation
    KOSHA_ORDER: Tuple[str, ...] = (
        "annamaya", "pranamaya", "manomaya", "vijnanamaya", "anandamaya"
    )

    def __post_init__(self):
        """Clamp values to [0.0, 1.0]."""
        for attr in self.KOSHA_ORDER:
            val = getattr(self, attr)
            if val < 0.0:
                object.__setattr__(self, attr, 0.0)
            elif val > 1.0:
                object.__setattr__(self, attr, 1.0)

    def to_dict(self) -> Dict[str, float]:
        """Convert to dictionary."""
        return {k: getattr(self, k) for k in self.KOSHA_ORDER}

    def get_dominant_kosha(self) -> str:
        """Return the kosha with highest activation."""
        max_val = -1.0
        dominant = self.KOSHA_ORDER[0]
        for kosha in self.KOSHA_ORDER:
            val = getattr(self, kosha)
            if val > max_val:
                max_val = val
                dominant = kosha
        return dominant

    def get_activation_vector(self) -> Tuple[float, ...]:
        """Return ordered activation vector."""
        return tuple(getattr(self, k) for k in self.KOSHA_ORDER)


@dataclass(frozen=True)
class DomainProfile:
    """
    Structural profile for a domain (12-dimensional).

    This is a simplified representation of the full StructuralProfile
    for entropy computation purposes.
    """
    dimensions: Tuple[Tuple[str, float], ...]  # (dimension_name, value)
    domain_name: Optional[str] = None

    def get_dimension(self, name: str) -> float:
        """Get value for a dimension."""
        for dim_name, val in self.dimensions:
            if dim_name == name:
                return val
        return 0.5  # Default to middle

    def to_dict(self) -> Dict[str, float]:
        """Convert to dictionary."""
        return dict(self.dimensions)
