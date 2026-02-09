"""
Explanation Telemetry Schema
============================

Enterprise-grade data contracts for Phase Quad explainability.

Phase Quad is explainable because it separates computation into named paths
and exposes the gating and stability signals that drove the output.  It
produces a verifiable audit trail: what it relied on, how stable the reasoning
was, and why it chose to act or escalate.

Four explanation layers (primitives → enterprise surface):
  A) Path Attribution  — Local / Phase / Quad contribution ratios
  B) Attention Provenance — Which context blocks drove the answer
  C) Stability & Drift   — Phase health, gate volatility, reversal risk
  D) Policy & Confidence  — ConfidenceGate / Sentinel decision ledger

These dataclasses form the JSON-serializable "Explanation Contract" returned
alongside every response (or stored in enterprise audit logs).
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any, Dict, List, Optional
import json


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class ConfidenceBand(str, Enum):
    """Discretised confidence for enterprise dashboards."""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    VERY_LOW = "very_low"


class StabilityBadge(str, Enum):
    """Traffic-light stability for UI badges."""
    GREEN = "green"    # Stable, low drift, low reversal risk
    YELLOW = "yellow"  # Moderate drift or gate volatility
    RED = "red"        # High drift, collapse risk, or reversal


class EscalationLevel(str, Enum):
    """How far up the chain the system escalated."""
    NONE = "none"                # Proceeded autonomously
    VERIFY = "verify"            # Requested human confirmation
    BLOCK = "block"              # Refused to proceed
    SENTINEL_OVERRIDE = "sentinel_override"  # Sentinel blocked


class PolicyOutcome(str, Enum):
    """Final action decision from confidence + policy."""
    ALLOWED = "allowed"
    CONFIRM_REQUIRED = "confirm_required"
    BLOCKED = "blocked"


# ---------------------------------------------------------------------------
# A) Path Attribution
# ---------------------------------------------------------------------------

@dataclass
class PathAttribution:
    """
    Per-response (or per-token) computation-path attribution.

    Enterprise translation:
        "Was this answer based on the latest message (Local), or on earlier
        context / retrieved structure (Quad)?"

    Fields mirror the three-path architecture in BindingCacheBlock:
        - Local: O(n*w) window attention  → syntax / recency
        - Phase: O(n) cumsum/EMA state    → semantic memory (always active)
        - Quad:  O(nk) Top-K retrieval    → structured recall
    """
    local_ratio: float = 0.0      # Fraction of output from LocalWindowAttention
    phase_ratio: float = 0.0      # Fraction from Phase accumulator state
    quad_ratio: float = 0.0       # Fraction from Quad retrieval

    # Gate strengths (aggregated across layers)
    gate_attn_mean: float = 0.0   # Mean attention gate strength
    gate_attn_p95: float = 0.0    # 95th percentile (spike detection)
    gate_ffn_mean: float = 0.0    # Mean FFN gate strength
    gate_volatility: float = 0.0  # Std of gate values across decoding steps

    # Proposal mode metrics (V10.4)
    confidence_mean: float = 0.0  # Mean phase confidence → quad skip trigger
    quad_skip_rate: float = 0.0   # Fraction of positions that skipped quad

    # Per-layer breakdown (optional, for deep audit)
    per_layer_local_ratio: List[float] = field(default_factory=list)
    per_layer_quad_ratio: List[float] = field(default_factory=list)
    per_layer_confidence: List[float] = field(default_factory=list)
    per_layer_skip_rate: List[float] = field(default_factory=list)


# ---------------------------------------------------------------------------
# B) Attention Provenance
# ---------------------------------------------------------------------------

@dataclass
class ProvenanceBlock:
    """A single context block that contributed to the answer."""
    block_id: int                 # Position or chunk index
    weight: float                 # Contribution weight [0, 1]
    distance: int = 0            # How many positions back from current
    source_label: str = ""       # Optional human label (e.g. "user message #3")


@dataclass
class AttentionProvenance:
    """
    Which sections of context influenced the answer.

    Enterprise translation:
        "I'm using past ticket #123 + policy section 4.2"

    Derived from Quad's Top-K retrieval and Phase's accumulated state.
    """
    top_blocks: List[ProvenanceBlock] = field(default_factory=list)
    block_entropy: float = 0.0     # Diversity of attended blocks (high = broad)
    recency_mean: float = 0.0      # Mean distance of contributing blocks
    recency_p95: float = 0.0       # 95th percentile distance

    # Cache health (from BindingCacheQuadQuery instrumentation)
    cache_hit_rate: float = 0.0
    cache_key_cosine_mean: float = 0.0  # > 0.85 = redundancy building
    cache_key_cosine_max: float = 0.0   # > 0.95 = slot collision


# ---------------------------------------------------------------------------
# C) Stability & Drift
# ---------------------------------------------------------------------------

@dataclass
class StabilityMetrics:
    """
    Phase health, drift, and reversal risk signals.

    Enterprise translation:
        "How stable is the reasoning trajectory?"

    Derived from phase_transformer health diagnostics:
        - R_k: mean resultant length (collapse detection)
        - Phase drift: |Δφ(t)| temporal differences
        - Head redundancy: pairwise cosine similarity
        - Amp-phase correlation: amplitude compensating for collapse
    """
    # Phase health (from compute_phase_health_diagnostics)
    r_k_mean: float = 0.0           # 0=collapsed, 1=well-distributed
    r_k_std: float = 0.0
    r_q_mean: float = 0.0
    amp_phase_correlation: float = 0.0  # High = amplitude compensating (bad)
    head_redundancy: float = 0.0     # > 0.85 = heads converging (bad)

    # Phase drift (temporal stability)
    phase_drift_mean: float = 0.0    # Small but non-zero is healthy
    phase_drift_std: float = 0.0     # High std = unstable

    # Derived enterprise signals
    reversal_risk: float = 0.0       # 0=safe, 1=likely reversal
    stability_badge: StabilityBadge = StabilityBadge.GREEN

    # Alignment modulation (intent × content coherence)
    alignment_score_mean: float = 0.0   # cos(θ_JEPA - θ_SRK) mean
    alignment_authority: float = 0.1    # Configured modulation strength

    # Gate volatility across decoding steps
    gate_volatility: float = 0.0


# ---------------------------------------------------------------------------
# D) Policy & Confidence (ConfidenceGate / Sentinel)
# ---------------------------------------------------------------------------

@dataclass
class PolicyDecision:
    """
    Decision ledger: why the system acted, asked, or refused.

    Enterprise translation:
        "Why did the system refuse, ask confirmation, or proceed?"

    Maps to V11.0.0 Control Plane:
        - Koshas[5]  → processing depth / Sentinel / budget
        - Vrittis[5] → epistemic reliability / ConfidenceGate
        - Gunas[6]   → energy dynamics / runtime governor
    """
    confidence_band: ConfidenceBand = ConfidenceBand.MEDIUM
    confidence_score: float = 0.0          # Raw [0, 1]
    escalation_level: EscalationLevel = EscalationLevel.NONE
    policy_outcome: PolicyOutcome = PolicyOutcome.ALLOWED

    # Control plane state (from 32D Sovereign State)
    kosha_depth: float = 0.0       # How deep processing went [0, 1]
    vritti_reliability: float = 0.0  # Epistemic state [0, 1]
    guna_energy: float = 0.0        # Energy dynamics [0, 1]

    # Tool/action permissions
    tool_execution_allowed: bool = True
    tool_block_reason: str = ""

    # Verification state
    verification_needed: bool = False
    verification_reason: str = ""

    # Sentinel signals
    coherence_score: float = 0.0    # Aggregate coherence
    prompt_injection_detected: bool = False
    adversarial_drift_detected: bool = False


# ---------------------------------------------------------------------------
# Composite: Full Explanation Telemetry
# ---------------------------------------------------------------------------

@dataclass
class ExplanationTelemetry:
    """
    Complete explanation record returned alongside each response.

    This is the "Explanation Contract" for Phase Quad: a consistent,
    JSON-serializable schema that enterprises can audit, log, and act on.

    Schema:
        1. routing   — Path attribution (Local vs Phase vs Quad)
        2. provenance — Context footprint (what blocks, how far back)
        3. stability  — Phase health, drift, reversal risk
        4. policy     — Confidence band, escalation, tool permissions

    Usage:
        telemetry = ExplanationTelemetry(...)
        json_str = telemetry.to_json()
        log_dict = telemetry.to_dict()
    """
    routing: PathAttribution = field(default_factory=PathAttribution)
    provenance: AttentionProvenance = field(default_factory=AttentionProvenance)
    stability: StabilityMetrics = field(default_factory=StabilityMetrics)
    policy: PolicyDecision = field(default_factory=PolicyDecision)

    # Metadata
    response_id: str = ""
    timestamp_ms: int = 0
    model_version: str = "phase_quad_v11.0.0"
    layer_count: int = 0
    sequence_length: int = 0

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to nested dict (JSON-ready)."""
        return asdict(self)

    def to_json(self, indent: int = 2) -> str:
        """Serialize to JSON string."""
        return json.dumps(self.to_dict(), indent=indent, default=str)

    def to_flat_dict(self) -> Dict[str, Any]:
        """
        Flatten to dot-notation keys for logging backends.

        E.g. {"routing.local_ratio": 0.72, "stability.r_k_mean": 0.45, ...}
        """
        flat: Dict[str, Any] = {}
        nested = self.to_dict()
        _flatten(nested, "", flat)
        return flat

    def summary(self) -> str:
        """
        One-line enterprise summary.

        Example:
            "Local 72% | Quad 28% | Confidence HIGH | Stability GREEN |
             Drift 0.02 | Reversal LOW | Action ALLOWED"
        """
        r = self.routing
        s = self.stability
        p = self.policy
        return (
            f"Local {r.local_ratio:.0%} | "
            f"Phase {r.phase_ratio:.0%} | "
            f"Quad {r.quad_ratio:.0%} | "
            f"Confidence {p.confidence_band.value.upper()} ({p.confidence_score:.2f}) | "
            f"Stability {s.stability_badge.value.upper()} | "
            f"Drift {s.phase_drift_mean:.3f} | "
            f"Reversal {s.reversal_risk:.2f} | "
            f"Action {p.policy_outcome.value.upper()}"
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _flatten(d: Any, prefix: str, out: Dict[str, Any]) -> None:
    """Recursively flatten a nested dict with dot-notation keys."""
    if isinstance(d, dict):
        for k, v in d.items():
            _flatten(v, f"{prefix}{k}." if prefix else f"{k}.", out)
    elif isinstance(d, list):
        out[prefix.rstrip(".")] = d  # Keep lists as-is
    else:
        out[prefix.rstrip(".")] = d


def confidence_to_band(score: float) -> ConfidenceBand:
    """Map a [0, 1] confidence score to a discrete band."""
    if score >= 0.75:
        return ConfidenceBand.HIGH
    elif score >= 0.50:
        return ConfidenceBand.MEDIUM
    elif score >= 0.25:
        return ConfidenceBand.LOW
    else:
        return ConfidenceBand.VERY_LOW


def stability_to_badge(
    drift_mean: float,
    r_k_mean: float,
    head_redundancy: float,
    reversal_risk: float,
) -> StabilityBadge:
    """
    Map health signals to a traffic-light badge.

    Thresholds calibrated from phase_transformer health diagnostics:
        - R_k: 0.001 < R < 100 healthy range
        - Drift: small but non-zero is healthy
        - Head redundancy: > 0.85 is concerning
    """
    red_flags = 0

    # Phase collapse: R_k near 0 or extremely high
    if r_k_mean < 0.01 or r_k_mean > 10.0:
        red_flags += 2
    elif r_k_mean < 0.05 or r_k_mean > 5.0:
        red_flags += 1

    # Drift: frozen or unstable
    if drift_mean < 0.001:   # Frozen phases
        red_flags += 1
    elif drift_mean > 0.5:   # Unstable phases
        red_flags += 2

    # Head redundancy
    if head_redundancy > 0.85:
        red_flags += 1

    # Reversal risk
    if reversal_risk > 0.7:
        red_flags += 2
    elif reversal_risk > 0.4:
        red_flags += 1

    if red_flags >= 3:
        return StabilityBadge.RED
    elif red_flags >= 1:
        return StabilityBadge.YELLOW
    return StabilityBadge.GREEN


__all__ = [
    "ConfidenceBand",
    "StabilityBadge",
    "EscalationLevel",
    "PolicyOutcome",
    "PathAttribution",
    "ProvenanceBlock",
    "AttentionProvenance",
    "StabilityMetrics",
    "PolicyDecision",
    "ExplanationTelemetry",
    "confidence_to_band",
    "stability_to_badge",
]
