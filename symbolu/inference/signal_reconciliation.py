"""
Signal Reconciliation — Vritti/Guna Consistency Validation Across Sources.

At inference time, multiple sources produce vritti and guna signals:

1. **Inference-time approximation** (guna_inference.py / InferenceGunas):
   Token-probability-based Sattva/Rajas/Tamas approximation.

2. **Sovereign state monitor** (sovereign_state_monitor.py):
   32-D state Guna slice [22:28] and Vritti slice [17:22].

3. **Canonical runtime authority** (guna_modulation/guna_derivation.py):
   Closed-form S/R/T from pipeline signals (C_s, M, H).

4. **Sovereign bridge** (sovereign_bridge.py):
   Guna → stability/trajectory signals for ConfidenceSignals.

This module does NOT force all sources through one code path.
Instead it:
- Validates consistency between sources
- Produces diagnostic metadata for divergence
- Warns when sources disagree beyond threshold
- Provides reconciled "best estimate" when multiple sources available

Phase 4: Sovereign ↔ inference reconciliation.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# =========================================================================
# Thresholds
# =========================================================================

# Maximum acceptable divergence between guna sources before warning
GUNA_DIVERGENCE_THRESHOLD = 0.3

# Maximum acceptable divergence between vritti dominant mode
VRITTI_MISMATCH_THRESHOLD = 0.4

# Reconciliation blend weights (inference, sovereign, canonical)
_INFERENCE_WEIGHT = 0.3
_SOVEREIGN_WEIGHT = 0.5
_CANONICAL_WEIGHT = 0.2


# =========================================================================
# Source representations
# =========================================================================

@dataclass(frozen=True)
class GunaSnapshot:
    """Normalized guna triple from any source."""
    sattva: float
    rajas: float
    tamas: float
    source: str  # "inference", "sovereign", "canonical"

    @property
    def dominant(self) -> str:
        if self.sattva >= self.rajas and self.sattva >= self.tamas:
            return "sattva"
        elif self.rajas >= self.tamas:
            return "rajas"
        return "tamas"

    def as_tuple(self) -> Tuple[float, float, float]:
        return (self.sattva, self.rajas, self.tamas)


@dataclass(frozen=True)
class VrittiSnapshot:
    """Vritti profile from any source."""
    profile: Tuple[float, ...]  # 5 elements: FACT, ERROR, IMAGINATION, VOID, MEMORY
    source: str

    @property
    def dominant_index(self) -> int:
        return max(range(len(self.profile)), key=lambda i: self.profile[i])

    @property
    def dominant_name(self) -> str:
        names = ["FACT", "ERROR", "IMAGINATION", "VOID", "MEMORY"]
        idx = self.dominant_index
        return names[idx] if idx < len(names) else "UNKNOWN"


# =========================================================================
# Reconciliation result
# =========================================================================

@dataclass(frozen=True)
class ReconciliationResult:
    """Result of multi-source signal reconciliation.

    Attributes:
        reconciled_guna: Best-estimate guna triple.
        reconciled_vritti_dominant: Best-estimate dominant vritti.
        guna_sources_count: Number of guna sources available.
        vritti_sources_count: Number of vritti sources available.
        guna_divergence: Maximum pairwise L1 distance between guna sources.
        vritti_agreement: Whether all vritti sources agree on dominant mode.
        divergence_warnings: List of divergence warning strings.
        source_detail: Human-readable provenance.
        diagnostics: Full diagnostic dict for audit.
    """
    reconciled_guna: GunaSnapshot
    reconciled_vritti_dominant: str
    guna_sources_count: int
    vritti_sources_count: int
    guna_divergence: float
    vritti_agreement: bool
    divergence_warnings: Tuple[str, ...]
    source_detail: str
    diagnostics: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "reconciled_guna": {
                "sattva": self.reconciled_guna.sattva,
                "rajas": self.reconciled_guna.rajas,
                "tamas": self.reconciled_guna.tamas,
                "dominant": self.reconciled_guna.dominant,
            },
            "reconciled_vritti_dominant": self.reconciled_vritti_dominant,
            "guna_sources_count": self.guna_sources_count,
            "vritti_sources_count": self.vritti_sources_count,
            "guna_divergence": self.guna_divergence,
            "vritti_agreement": self.vritti_agreement,
            "divergence_warnings": list(self.divergence_warnings),
            "source_detail": self.source_detail,
        }


# =========================================================================
# Reconciliation logic
# =========================================================================

def reconcile_signals(
    *,
    inference_guna: Optional[Tuple[float, float, float]] = None,
    sovereign_guna: Optional[Tuple[float, float, float]] = None,
    canonical_guna: Optional[Tuple[float, float, float]] = None,
    inference_vritti_dominant: Optional[str] = None,
    sovereign_vritti_profile: Optional[Tuple[float, ...]] = None,
) -> ReconciliationResult:
    """Reconcile vritti/guna signals from multiple sources.

    Args:
        inference_guna: (sattva, rajas, tamas) from InferenceGunas.
        sovereign_guna: (sattva, rajas, tamas) from sovereign state monitor.
            Corresponds to lucidity/activity/stability in the 32-D guna slice.
        canonical_guna: (sattva, rajas, tamas) from guna_derivation.
        inference_vritti_dominant: Dominant vritti name from inference monitoring.
        sovereign_vritti_profile: 5-element vritti profile from sovereign state.

    Returns:
        ReconciliationResult with reconciled signals and divergence metadata.
    """
    warnings: List[str] = []
    diagnostics: Dict[str, Any] = {}
    sources: List[str] = []

    # ---- Collect guna snapshots ----
    guna_snapshots: List[GunaSnapshot] = []

    if inference_guna is not None:
        try:
            snap = GunaSnapshot(
                sattva=float(inference_guna[0]),
                rajas=float(inference_guna[1]),
                tamas=float(inference_guna[2]),
                source="inference",
            )
            guna_snapshots.append(snap)
            sources.append("inference_guna")
            diagnostics["inference_guna"] = snap.as_tuple()
        except (IndexError, TypeError, ValueError):
            warnings.append("Malformed inference_guna, skipping")

    if sovereign_guna is not None:
        try:
            snap = GunaSnapshot(
                sattva=float(sovereign_guna[0]),
                rajas=float(sovereign_guna[1]),
                tamas=float(sovereign_guna[2]),
                source="sovereign",
            )
            guna_snapshots.append(snap)
            sources.append("sovereign_guna")
            diagnostics["sovereign_guna"] = snap.as_tuple()
        except (IndexError, TypeError, ValueError):
            warnings.append("Malformed sovereign_guna, skipping")

    if canonical_guna is not None:
        try:
            snap = GunaSnapshot(
                sattva=float(canonical_guna[0]),
                rajas=float(canonical_guna[1]),
                tamas=float(canonical_guna[2]),
                source="canonical",
            )
            guna_snapshots.append(snap)
            sources.append("canonical_guna")
            diagnostics["canonical_guna"] = snap.as_tuple()
        except (IndexError, TypeError, ValueError):
            warnings.append("Malformed canonical_guna, skipping")

    # ---- Reconcile guna ----
    guna_divergence = 0.0
    if len(guna_snapshots) >= 2:
        guna_divergence = _max_pairwise_l1(guna_snapshots)
        if guna_divergence > GUNA_DIVERGENCE_THRESHOLD:
            warnings.append(
                f"Guna divergence {guna_divergence:.3f} exceeds threshold "
                f"{GUNA_DIVERGENCE_THRESHOLD}"
            )
        diagnostics["guna_divergence"] = guna_divergence

    reconciled_guna = _blend_gunas(guna_snapshots)

    # ---- Collect vritti sources ----
    vritti_names: List[str] = []

    if inference_vritti_dominant is not None:
        vritti_names.append(str(inference_vritti_dominant).upper())
        sources.append("inference_vritti")

    sovereign_vritti_dom = None
    if sovereign_vritti_profile is not None:
        try:
            profile = [float(x) for x in sovereign_vritti_profile]
            if len(profile) >= 5:
                names_list = ["FACT", "ERROR", "IMAGINATION", "VOID", "MEMORY"]
                idx = max(range(5), key=lambda i: profile[i])
                sovereign_vritti_dom = names_list[idx]
                vritti_names.append(sovereign_vritti_dom)
                sources.append("sovereign_vritti")
                diagnostics["sovereign_vritti_profile"] = profile[:5]
        except (TypeError, ValueError):
            warnings.append("Malformed sovereign_vritti_profile, skipping")

    # ---- Reconcile vritti ----
    vritti_agreement = len(set(vritti_names)) <= 1
    if vritti_names and not vritti_agreement:
        warnings.append(
            f"Vritti mode disagreement: {', '.join(vritti_names)}"
        )

    # Best-estimate: prefer sovereign, then inference
    reconciled_vritti = "FACT"  # default
    if sovereign_vritti_dom is not None:
        reconciled_vritti = sovereign_vritti_dom
    elif vritti_names:
        reconciled_vritti = vritti_names[0]

    source_detail = f"reconciled from: {', '.join(sources) or 'no sources'}"

    return ReconciliationResult(
        reconciled_guna=reconciled_guna,
        reconciled_vritti_dominant=reconciled_vritti,
        guna_sources_count=len(guna_snapshots),
        vritti_sources_count=len(vritti_names),
        guna_divergence=guna_divergence,
        vritti_agreement=vritti_agreement,
        divergence_warnings=tuple(warnings),
        source_detail=source_detail,
        diagnostics=diagnostics,
    )


# =========================================================================
# Helpers
# =========================================================================

def _max_pairwise_l1(snapshots: List[GunaSnapshot]) -> float:
    """Maximum pairwise L1 distance between guna snapshots."""
    max_dist = 0.0
    for i in range(len(snapshots)):
        for j in range(i + 1, len(snapshots)):
            a = snapshots[i].as_tuple()
            b = snapshots[j].as_tuple()
            dist = sum(abs(x - y) for x, y in zip(a, b))
            max_dist = max(max_dist, dist)
    return max_dist


def _blend_gunas(snapshots: List[GunaSnapshot]) -> GunaSnapshot:
    """Weighted blend of guna snapshots.

    Weights: sovereign > inference > canonical.
    If only one source, use it directly.
    """
    if not snapshots:
        return GunaSnapshot(0.33, 0.33, 0.34, source="default")

    if len(snapshots) == 1:
        s = snapshots[0]
        return GunaSnapshot(s.sattva, s.rajas, s.tamas, source=s.source)

    # Weighted blend
    weight_map = {
        "sovereign": _SOVEREIGN_WEIGHT,
        "inference": _INFERENCE_WEIGHT,
        "canonical": _CANONICAL_WEIGHT,
    }

    total_w = 0.0
    s, r, t = 0.0, 0.0, 0.0
    for snap in snapshots:
        w = weight_map.get(snap.source, 0.2)
        s += snap.sattva * w
        r += snap.rajas * w
        t += snap.tamas * w
        total_w += w

    if total_w > 0:
        s /= total_w
        r /= total_w
        t /= total_w

    # Renormalize
    total = s + r + t
    if total > 1e-9:
        s /= total
        r /= total
        t /= total
    else:
        s, r, t = 0.33, 0.33, 0.34

    return GunaSnapshot(s, r, t, source="reconciled")
