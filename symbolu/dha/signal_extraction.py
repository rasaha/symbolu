"""
DHA Signal Extraction - Canonical Signal Mapping
=================================================

Maps existing SymbolU pipeline signals to DHA inputs.

EXPLICIT CONSTRAINTS:
    - NO new inference engines
    - NO psychology inference
    - NO invented semantics
    - Direct signal reuse + normalization only
    - Deterministic defaults for missing signals

Signal Sources (Priority Order):
    1. H_G (Guna Entropy): MLCR → Observables → compute from guna vector
    2. M (Motion): P18 → delta_sem → request metadata
    3. C_s (Coherence): coherence_state → P17 integrity → request metadata
    4. C_contr (Contradiction): MLCR → request metadata

Version: 1.0
Date: 2025-12-22
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from symbolu.mechanical.pipeline.models import PipelineContext

from symbolu.dha.types import DHAInputs, Tier
from symbolu.dha.config import DHAConfig


# =============================================================================
# Constants for Normalization
# =============================================================================

# Entropy normalization constants
LN_3: float = math.log(3)   # ~1.0986 - max guna entropy
LN_5: float = math.log(5)   # ~1.6094 - max kosha entropy
LN_10: float = math.log(10)  # ~2.3026 - max dimensional entropy

# Motion normalization
M_MAX: float = 1.0  # Maximum motion magnitude (already normalized in pipeline)

# Contradiction normalization
C_CONTR_MAX: float = 1.0  # Maximum contradiction (already normalized)

# Numerical stability
EPSILON: float = 1e-9


# =============================================================================
# Audit Record for Signal Extraction
# =============================================================================

@dataclass
class SignalExtractionAudit:
    """
    Audit trail for DHA signal extraction.

    Records which signals were found, which used defaults,
    and any normalization applied.
    """
    # Guna entropy
    guna_source: str = "none"  # "mlcr" | "computed" | "metadata" | "none"
    guna_raw: Optional[float] = None
    guna_normalized: bool = False
    missing_guna: bool = True

    # Motion
    motion_source: str = "none"  # "p18" | "delta_sem" | "metadata" | "none"
    motion_raw: Optional[float] = None
    motion_defaulted: bool = True

    # Coherence
    coherence_source: str = "none"  # "coherence_state" | "coherence_state_v2" | "p17" | "metadata" | "none"
    coherence_raw: Optional[float] = None
    coherence_assumed: bool = True

    # Contradiction
    contradiction_source: str = "none"  # "mlcr" | "metadata" | "none"
    contradiction_raw: Optional[float] = None
    no_contradiction_signal: bool = True

    # Guna distribution
    guna_distribution_source: str = "none"  # "mlcr" | "observables" | "metadata" | "none"
    guna_distribution_normalized: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "guna": {
                "source": self.guna_source,
                "raw": self.guna_raw,
                "normalized": self.guna_normalized,
                "missing": self.missing_guna,
            },
            "motion": {
                "source": self.motion_source,
                "raw": self.motion_raw,
                "defaulted": self.motion_defaulted,
            },
            "coherence": {
                "source": self.coherence_source,
                "raw": self.coherence_raw,
                "assumed": self.coherence_assumed,
            },
            "contradiction": {
                "source": self.contradiction_source,
                "raw": self.contradiction_raw,
                "no_signal": self.no_contradiction_signal,
            },
            "guna_distribution": {
                "source": self.guna_distribution_source,
                "normalized": self.guna_distribution_normalized,
            },
        }


# =============================================================================
# Guna Entropy Extraction (H_G)
# =============================================================================

def compute_guna_entropy_from_distribution(s: float, r: float, t: float) -> float:
    """
    Compute guna entropy from distribution vector.

    FORMULA:
        H_G = -Σ_{i∈{S,R,T}} g_i × ln(g_i + ε)

    Args:
        s: Sattva component [0, 1]
        r: Rajas component [0, 1]
        t: Tamas component [0, 1]

    Returns:
        Raw guna entropy [0, ln(3)]
    """
    def safe_log(x: float) -> float:
        return math.log(x + EPSILON)

    # Normalize distribution
    total = s + r + t
    if total < EPSILON:
        return 0.0

    s_norm = s / total
    r_norm = r / total
    t_norm = t / total

    # Compute Shannon entropy
    H_G = -(
        s_norm * safe_log(s_norm) +
        r_norm * safe_log(r_norm) +
        t_norm * safe_log(t_norm)
    )

    return max(0.0, min(LN_3, H_G))


def extract_guna_entropy(
    ctx: "PipelineContext",
    audit: SignalExtractionAudit,
) -> Optional[float]:
    """
    Extract H_G from pipeline context.

    Priority order:
        1. ctx.mlcr.explain_log['entropy']['H_G']
        2. Compute from guna distribution if available
        3. ctx.request.metadata['guna_entropy']
        4. None (missing signal)

    Args:
        ctx: PipelineContext
        audit: Audit record to update

    Returns:
        H_G value [0, ln(3)] or None if missing
    """
    # Try MLCR entropy first
    if hasattr(ctx, 'mlcr') and ctx.mlcr is not None:
        explain_log = ctx.mlcr.explain_log if hasattr(ctx.mlcr, 'explain_log') else {}
        entropy = explain_log.get('entropy', {})

        if 'H_G' in entropy and entropy['H_G'] is not None:
            H_G = entropy['H_G']
            audit.guna_source = "mlcr"
            audit.guna_raw = H_G
            audit.missing_guna = False
            return H_G

    # Try computing from guna distribution
    guna_dist = extract_guna_distribution_raw(ctx)
    if guna_dist is not None:
        s, r, t = guna_dist
        H_G = compute_guna_entropy_from_distribution(s, r, t)
        audit.guna_source = "computed"
        audit.guna_raw = H_G
        audit.missing_guna = False
        return H_G

    # Try request metadata
    if hasattr(ctx, 'request') and ctx.request and hasattr(ctx.request, 'metadata'):
        H_G = ctx.request.metadata.get('guna_entropy')
        if H_G is not None:
            audit.guna_source = "metadata"
            audit.guna_raw = H_G
            audit.missing_guna = False
            return H_G

    # No entropy available
    audit.guna_source = "none"
    audit.missing_guna = True
    return None


# =============================================================================
# Motion Extraction (M)
# =============================================================================

def extract_motion(
    ctx: "PipelineContext",
    audit: SignalExtractionAudit,
) -> float:
    """
    Extract M (motion/transformation magnitude) from pipeline context.

    Priority order:
        1. ctx.p18.delta_entropy (absolute value)
        2. ctx.request.metadata['delta_sem']
        3. ctx.request.metadata['motion_magnitude']
        4. 0.0 (default - no motion)

    FORMULA:
        M = clip(|delta_signal| / M_MAX, 0, 1)

    Args:
        ctx: PipelineContext
        audit: Audit record to update

    Returns:
        M value [0, 1]
    """
    # Try P18 temporal entropy delta
    if hasattr(ctx, 'p18') and ctx.p18 is not None:
        if hasattr(ctx.p18, 'delta_entropy') and ctx.p18.delta_entropy is not None:
            raw = abs(ctx.p18.delta_entropy)
            M = max(0.0, min(1.0, raw / M_MAX))
            audit.motion_source = "p18"
            audit.motion_raw = ctx.p18.delta_entropy
            audit.motion_defaulted = False
            return M

    # Try request metadata - delta_sem
    if hasattr(ctx, 'request') and ctx.request and hasattr(ctx.request, 'metadata'):
        delta_sem = ctx.request.metadata.get('delta_sem')
        if delta_sem is not None:
            M = max(0.0, min(1.0, abs(delta_sem)))
            audit.motion_source = "delta_sem"
            audit.motion_raw = delta_sem
            audit.motion_defaulted = False
            return M

        # Try motion_magnitude
        motion = ctx.request.metadata.get('motion_magnitude')
        if motion is not None:
            M = max(0.0, min(1.0, motion))
            audit.motion_source = "metadata"
            audit.motion_raw = motion
            audit.motion_defaulted = False
            return M

    # Default: no motion
    audit.motion_source = "none"
    audit.motion_defaulted = True
    return 0.0


# =============================================================================
# Structural Coherence Extraction (C_s)
# =============================================================================

def extract_coherence(
    ctx: "PipelineContext",
    audit: SignalExtractionAudit,
) -> float:
    """
    Extract C_s (structural coherence) from pipeline context.

    Priority order:
        1. ctx.coherence_state.coherence_score (v1 canonical)
        2. ctx.coherence_state.coherence_score_v2
        3. ctx.coherence_report['coherence_score']
        4. ctx.p17.integrity_score (inverse entropy proxy)
        5. ctx.request.metadata['coherence_score']
        6. 1.0 (default - assume coherent)

    FORMULA:
        C_s = clip(score, 0, 1)

    Args:
        ctx: PipelineContext
        audit: Audit record to update

    Returns:
        C_s value [0, 1]
    """
    # Try coherence_state (v1 canonical)
    if hasattr(ctx, 'coherence_state') and ctx.coherence_state is not None:
        if hasattr(ctx.coherence_state, 'coherence_score') and ctx.coherence_state.coherence_score is not None:
            raw = ctx.coherence_state.coherence_score
            C_s = max(0.0, min(1.0, raw))
            audit.coherence_source = "coherence_state"
            audit.coherence_raw = raw
            audit.coherence_assumed = False
            return C_s

        # Try v2 if v1 not available
        if hasattr(ctx.coherence_state, 'coherence_score_v2') and ctx.coherence_state.coherence_score_v2 is not None:
            raw = ctx.coherence_state.coherence_score_v2
            C_s = max(0.0, min(1.0, raw))
            audit.coherence_source = "coherence_state_v2"
            audit.coherence_raw = raw
            audit.coherence_assumed = False
            return C_s

    # Try coherence_report
    if hasattr(ctx, 'coherence_report') and ctx.coherence_report:
        raw = ctx.coherence_report.get('coherence_score')
        if raw is not None:
            C_s = max(0.0, min(1.0, raw))
            audit.coherence_source = "coherence_report"
            audit.coherence_raw = raw
            audit.coherence_assumed = False
            return C_s

    # Try P17 semantic integrity
    if hasattr(ctx, 'p17') and ctx.p17 is not None:
        if hasattr(ctx.p17, 'integrity_score') and ctx.p17.integrity_score is not None:
            raw = ctx.p17.integrity_score
            C_s = max(0.0, min(1.0, raw))
            audit.coherence_source = "p17"
            audit.coherence_raw = raw
            audit.coherence_assumed = False
            return C_s

    # Try request metadata
    if hasattr(ctx, 'request') and ctx.request and hasattr(ctx.request, 'metadata'):
        raw = ctx.request.metadata.get('coherence_score')
        if raw is not None:
            C_s = max(0.0, min(1.0, raw))
            audit.coherence_source = "metadata"
            audit.coherence_raw = raw
            audit.coherence_assumed = False
            return C_s

    # Default: assume coherent
    audit.coherence_source = "none"
    audit.coherence_assumed = True
    return 1.0


# =============================================================================
# Contradiction Extraction (C_contr)
# =============================================================================

def extract_contradiction(
    ctx: "PipelineContext",
    audit: SignalExtractionAudit,
) -> float:
    """
    Extract C_contr (contradiction metric) from pipeline context.

    Priority order:
        1. ctx.mlcr.explain_log['contradiction']
        2. ctx.request.metadata['C_contr']
        3. ctx.request.metadata['contradiction']
        4. 0.0 (default - no contradiction)

    FORMULA:
        C_contr = clip(raw / C_CONTR_MAX, 0, 1)

    Args:
        ctx: PipelineContext
        audit: Audit record to update

    Returns:
        C_contr value [0, 1]
    """
    # Try MLCR
    if hasattr(ctx, 'mlcr') and ctx.mlcr is not None:
        explain_log = ctx.mlcr.explain_log if hasattr(ctx.mlcr, 'explain_log') else {}
        raw = explain_log.get('contradiction')
        if raw is not None:
            C_contr = max(0.0, min(1.0, raw / C_CONTR_MAX))
            audit.contradiction_source = "mlcr"
            audit.contradiction_raw = raw
            audit.no_contradiction_signal = False
            return C_contr

    # Try request metadata
    if hasattr(ctx, 'request') and ctx.request and hasattr(ctx.request, 'metadata'):
        # Try C_contr first
        raw = ctx.request.metadata.get('C_contr')
        if raw is not None:
            C_contr = max(0.0, min(1.0, raw))
            audit.contradiction_source = "metadata"
            audit.contradiction_raw = raw
            audit.no_contradiction_signal = False
            return C_contr

        # Try contradiction
        raw = ctx.request.metadata.get('contradiction')
        if raw is not None:
            C_contr = max(0.0, min(1.0, raw))
            audit.contradiction_source = "metadata"
            audit.contradiction_raw = raw
            audit.no_contradiction_signal = False
            return C_contr

    # Default: no contradiction
    audit.contradiction_source = "none"
    audit.no_contradiction_signal = True
    return 0.0


# =============================================================================
# Guna Distribution Extraction (s, r, t)
# =============================================================================

def extract_guna_distribution_raw(ctx: "PipelineContext") -> Optional[Tuple[float, float, float]]:
    """
    Extract raw guna distribution from pipeline context.

    Does NOT normalize. Returns None if not available.

    Priority order:
        1. ctx.mlcr.explain_log['guna']
        2. ctx.request.metadata (sattva, rajas, tamas)

    Returns:
        (s, r, t) tuple or None
    """
    # Try MLCR guna
    if hasattr(ctx, 'mlcr') and ctx.mlcr is not None:
        explain_log = ctx.mlcr.explain_log if hasattr(ctx.mlcr, 'explain_log') else {}
        guna = explain_log.get('guna', {})

        s = guna.get('sattva') or guna.get('s')
        r = guna.get('rajas') or guna.get('r')
        t = guna.get('tamas') or guna.get('t')

        if s is not None and r is not None and t is not None:
            return (s, r, t)

    # Try request metadata
    if hasattr(ctx, 'request') and ctx.request and hasattr(ctx.request, 'metadata'):
        s = ctx.request.metadata.get('sattva')
        r = ctx.request.metadata.get('rajas')
        t = ctx.request.metadata.get('tamas')

        if s is not None and r is not None and t is not None:
            return (s, r, t)

    return None


def extract_guna_distribution(
    ctx: "PipelineContext",
    audit: SignalExtractionAudit,
) -> Tuple[float, float, float]:
    """
    Extract guna distribution (s, r, t) from pipeline context.

    Normalizes to sum = 1 if not already normalized.

    Priority order:
        1. ctx.mlcr.explain_log['guna']
        2. ctx.request.metadata (sattva, rajas, tamas)
        3. (0.333, 0.333, 0.334) - balanced default

    Args:
        ctx: PipelineContext
        audit: Audit record to update

    Returns:
        (s, r, t) normalized tuple
    """
    raw = extract_guna_distribution_raw(ctx)

    if raw is not None:
        s, r, t = raw
        total = s + r + t

        # Normalize if needed
        if abs(total - 1.0) > EPSILON:
            if total > EPSILON:
                s = s / total
                r = r / total
                t = t / total
                audit.guna_distribution_normalized = True
            else:
                # All zeros - use balanced
                s, r, t = 0.333333, 0.333333, 0.333334
                audit.guna_distribution_normalized = True

        # Determine source
        if hasattr(ctx, 'mlcr') and ctx.mlcr is not None:
            explain_log = ctx.mlcr.explain_log if hasattr(ctx.mlcr, 'explain_log') else {}
            if 'guna' in explain_log:
                audit.guna_distribution_source = "mlcr"
            else:
                audit.guna_distribution_source = "metadata"
        else:
            audit.guna_distribution_source = "metadata"

        return (s, r, t)

    # Default: balanced distribution
    audit.guna_distribution_source = "none"
    return (0.333333, 0.333333, 0.333334)


# =============================================================================
# Tier Extraction
# =============================================================================

def extract_tier(ctx: "PipelineContext") -> str:
    """
    Extract tier identifier from pipeline context.

    Priority:
        1. ctx.mlcr.explain_log['meta']['tier']
        2. ctx.request.metadata['tier']
        3. "consumer" (default)

    Returns:
        Tier string: "enterprise_tier_1" | "enterprise_tier_2" | "consumer"
    """
    # Try MLCR
    if hasattr(ctx, 'mlcr') and ctx.mlcr is not None:
        explain_log = ctx.mlcr.explain_log if hasattr(ctx.mlcr, 'explain_log') else {}
        meta = explain_log.get('meta', {})
        tier_str = meta.get('tier', '')

        if tier_str in ('UPPER', 'enterprise_tier_1'):
            return "enterprise_tier_1"
        elif tier_str in ('LOWER', 'enterprise_tier_2'):
            return "enterprise_tier_2"
        elif tier_str:
            return "consumer"

    # Try request metadata
    if hasattr(ctx, 'request') and ctx.request and hasattr(ctx.request, 'metadata'):
        tier = ctx.request.metadata.get('tier')
        if tier in ('enterprise_tier_1', 'enterprise_tier_2', 'consumer'):
            return tier

    return "consumer"


# =============================================================================
# Main Extraction Function
# =============================================================================

def extract_dha_inputs(
    ctx: "PipelineContext",
    config: Optional[DHAConfig] = None,
) -> Tuple[DHAInputs, SignalExtractionAudit]:
    """
    Extract DHA inputs from pipeline context.

    This is the canonical extraction function that maps existing
    pipeline signals to DHA inputs using deterministic formulas.

    EXPLICIT CONSTRAINTS:
        - No new inference engines
        - No psychology inference
        - No invented semantics
        - Direct signal reuse only
        - Deterministic defaults for missing signals

    Args:
        ctx: PipelineContext with upstream stage results
        config: Optional DHA configuration

    Returns:
        Tuple of (DHAInputs, SignalExtractionAudit)

    Signal Mapping Table:

    | DHA Input | Source Module | Field Name | Formula | Default |
    |-----------|---------------|------------|---------|---------|
    | H_G | MLCR/Observables | explain_log['entropy']['H_G'] | H = H_G / ln(3) | 0.0 |
    | M | P18/Metadata | delta_entropy | M = abs(delta) | 0.0 |
    | C_s | CoherenceState | coherence_score | C_s = clip(score, 0, 1) | 1.0 |
    | C_contr | MLCR | explain_log['contradiction'] | C_contr = clip(raw, 0, 1) | 0.0 |
    | s, r, t | MLCR/Observables | explain_log['guna'] | normalize(s+r+t=1) | balanced |
    """
    audit = SignalExtractionAudit()
    missing_signals = []

    # =========================================================================
    # Extract Guna Entropy (H_G)
    # =========================================================================
    H_G = extract_guna_entropy(ctx, audit)
    if H_G is None:
        H_G = 0.0
        missing_signals.append("H_G")

    # =========================================================================
    # Extract Motion (M)
    # =========================================================================
    M = extract_motion(ctx, audit)
    if audit.motion_defaulted:
        missing_signals.append("M")

    # =========================================================================
    # Extract Structural Coherence (C_s)
    # =========================================================================
    C_s = extract_coherence(ctx, audit)
    if audit.coherence_assumed:
        missing_signals.append("C_s")

    # =========================================================================
    # Extract Contradiction (C_contr)
    # =========================================================================
    C_contr = extract_contradiction(ctx, audit)
    if audit.no_contradiction_signal:
        missing_signals.append("C_contr")

    # =========================================================================
    # Extract Guna Distribution (s, r, t)
    # =========================================================================
    s, r, t = extract_guna_distribution(ctx, audit)
    if audit.guna_distribution_source == "none":
        missing_signals.append("guna_distribution")

    # =========================================================================
    # Extract Tier
    # =========================================================================
    tier_str = extract_tier(ctx)
    tier_map = {
        "enterprise_tier_1": Tier.ENTERPRISE_TIER_1,
        "enterprise_tier_2": Tier.ENTERPRISE_TIER_2,
        "consumer": Tier.CONSUMER,
    }
    tier = tier_map.get(tier_str, Tier.CONSUMER)

    # =========================================================================
    # Extract Base Text Reference
    # =========================================================================
    base_text_ref = None
    if hasattr(ctx, 'fusion') and ctx.fusion is not None:
        if hasattr(ctx.fusion, 'trace'):
            base_text_ref = str(ctx.fusion.trace.get('candidate_count', 'fusion'))

    # =========================================================================
    # Build DHAInputs
    # =========================================================================
    inputs = DHAInputs(
        C_s=C_s,
        M=M,
        H_G=H_G,
        H_D=None,  # Not extracted in this version
        H_K=None,  # Not extracted in this version
        C_contr=C_contr,
        s=s,
        r=r,
        t=t,
        tier=tier,
        base_text_ref=base_text_ref,
        missing_signals=tuple(missing_signals),
    )

    return inputs, audit


# =============================================================================
# Convenience Function for Integration Module
# =============================================================================

def extract_signals_from_context_v2(
    ctx: "PipelineContext",
    config: DHAConfig,
) -> DHAInputs:
    """
    Extract DHA signals from context (v2 - with proper signal wiring).

    This replaces the original extract_signals_from_context with
    canonical signal extraction formulas.

    Args:
        ctx: PipelineContext
        config: DHA configuration

    Returns:
        DHAInputs with extracted signals
    """
    inputs, audit = extract_dha_inputs(ctx, config)

    # Attach audit to request metadata for observability
    if hasattr(ctx, 'request') and ctx.request and hasattr(ctx.request, 'metadata'):
        ctx.request.metadata['dha_signal_extraction_audit'] = audit.to_dict()

    return inputs


# =============================================================================
# Public Exports
# =============================================================================

__all__ = [
    "extract_dha_inputs",
    "extract_signals_from_context_v2",
    "SignalExtractionAudit",
    "LN_3",
    "LN_5",
    "LN_10",
    "M_MAX",
    "C_CONTR_MAX",
]
