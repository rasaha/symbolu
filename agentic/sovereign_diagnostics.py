"""
Sovereign Reasoning Diagnostics — Bridge-Safe Summary (Phase S3).

Pure-Python, serializable diagnostic summary of reasoning-kernel state.
This module lives outside agentic/sovereign/ to avoid the torch import chain
(same pattern as sovereign_constants.py and sovereign_metrics_runtime.py).

These diagnostics are populated from reasoning-kernel intervene() output,
carried through inference_bridge → sovereign_bridge, and consumed by the
governance pipeline for audit/enrichment.

No PyTorch dependency. No tensor fields. Only compact, explainable summaries.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


# =========================================================================
# Reasoning Kernel Diagnostics (bridge-safe summary)
# =========================================================================

@dataclass(frozen=True)
class ReasoningDiagnostics:
    """Compact diagnostic summary from the Sovereign Reasoning Kernel.

    Populated from SovereignReasoningKernel.intervene() diagnostics dict
    and/or get_diagnostics() output. All fields are plain Python types.

    Attributes:
        mauna_active: Whether the Mauna (silence) protocol triggered.
            True = model is withholding output due to instability.
        active_intervention: Which layer intervention ran
            (None, 'dna_bridge', 'witness', 'synthesis').
        active_logic_template: Name of matched IMR logic template
            (e.g. 'DEDUCTION', 'INDUCTION'), or None if no match.
        dominant_bhava: Dominant ontological layer name (e.g. 'RSN').
        active_kosha: Active processing depth name (e.g. 'INTELLECTUAL').
        vritti_state: Current vritti mode name (e.g. 'FACT').
        vritti_rejection: Whether the VrittiGate rejected the current token.
        opb_active_locks: Number of OPB dimension locks active.
        opb_locked_dims: Names of locked dimensions.
        opb_newly_locked: Dimensions newly locked this step.
        opb_newly_unlocked: Dimensions newly unlocked this step.
        entropy_delta: Entropy change from previous state (positive = rising).
        source: Provenance marker ('reasoning_kernel', 'inference_bridge', etc).
    """
    # Mauna / silence
    mauna_active: bool = False

    # Intervention
    active_intervention: Optional[str] = None
    active_logic_template: Optional[str] = None

    # State summary
    dominant_bhava: Optional[str] = None
    active_kosha: Optional[str] = None
    vritti_state: Optional[str] = None
    vritti_rejection: bool = False

    # OPB dimension locking
    opb_active_locks: int = 0
    opb_locked_dims: Tuple[str, ...] = ()
    opb_newly_locked: Tuple[str, ...] = ()
    opb_newly_unlocked: Tuple[str, ...] = ()

    # Entropy
    entropy_delta: float = 0.0

    # Provenance
    source: str = "unknown"

    def to_audit_dict(self) -> Dict[str, Any]:
        """Serialize to plain dict for governance audit."""
        return {
            "mauna_active": self.mauna_active,
            "active_intervention": self.active_intervention,
            "active_logic_template": self.active_logic_template,
            "dominant_bhava": self.dominant_bhava,
            "active_kosha": self.active_kosha,
            "vritti_state": self.vritti_state,
            "vritti_rejection": self.vritti_rejection,
            "opb_active_locks": self.opb_active_locks,
            "opb_locked_dims": list(self.opb_locked_dims),
            "opb_newly_locked": list(self.opb_newly_locked),
            "opb_newly_unlocked": list(self.opb_newly_unlocked),
            "entropy_delta": round(self.entropy_delta, 6),
            "source": self.source,
        }

    @property
    def is_silenced(self) -> bool:
        """Whether the model is in a silence/withholding state."""
        return self.mauna_active

    @property
    def opb_is_locked(self) -> bool:
        """Whether any OPB dimension locks are active."""
        return self.opb_active_locks > 0

    @property
    def opb_is_unstable(self) -> bool:
        """Whether OPB had lock transitions this step (dimension churn)."""
        return len(self.opb_newly_locked) > 0 or len(self.opb_newly_unlocked) > 0


# =========================================================================
# Factory: build from reasoning-kernel diagnostics dict
# =========================================================================

def diagnostics_from_kernel_output(
    kernel_diagnostics: Optional[Dict[str, Any]] = None,
    kernel_state: Optional[Dict[str, Any]] = None,
) -> ReasoningDiagnostics:
    """Build ReasoningDiagnostics from kernel intervene() and/or get_diagnostics() output.

    Args:
        kernel_diagnostics: Dict from SovereignReasoningKernel.intervene()['diagnostics'].
            Contains: intervention, isomorphism, mauna_triggered, opb_*, vritti_*, entropy_delta.
        kernel_state: Dict from SovereignReasoningKernel.get_diagnostics().
            Contains: dominant_bhava, active_kosha, vritti_state, lucidity, etc.

    Returns:
        ReasoningDiagnostics with all available fields populated.
        Missing fields get safe defaults.
    """
    if kernel_diagnostics is None and kernel_state is None:
        return ReasoningDiagnostics(source="no_data")

    d = kernel_diagnostics or {}
    s = kernel_state or {}

    return ReasoningDiagnostics(
        mauna_active=bool(d.get("mauna_triggered", False)),
        active_intervention=d.get("intervention"),
        active_logic_template=d.get("isomorphism"),
        dominant_bhava=s.get("dominant_bhava", d.get("dominant_bhava")),
        active_kosha=s.get("active_kosha", d.get("observed_kosha")),
        vritti_state=s.get("vritti_state"),
        vritti_rejection=bool(d.get("vritti_rejection", False)),
        opb_active_locks=int(d.get("opb_active_locks", 0)),
        opb_locked_dims=tuple(d.get("opb_locked_dims", [])),
        opb_newly_locked=tuple(d.get("opb_newly_locked", [])),
        opb_newly_unlocked=tuple(d.get("opb_newly_unlocked", [])),
        entropy_delta=float(d.get("entropy_delta", 0.0)),
        source="reasoning_kernel",
    )


def diagnostics_from_bridge_metadata(
    metadata: Optional[Dict[str, Any]] = None,
) -> ReasoningDiagnostics:
    """Build ReasoningDiagnostics from inference bridge projection metadata.

    Used when full kernel diagnostics aren't available but the inference
    bridge has projection-level information.

    Args:
        metadata: Dict from SovereignProjectionResult.to_dict() or similar,
            potentially enriched with diagnostics fields.

    Returns:
        ReasoningDiagnostics with available fields. Missing = safe defaults.
    """
    if metadata is None:
        return ReasoningDiagnostics(source="no_data")

    # Check for embedded diagnostics sub-dict
    diag = metadata.get("reasoning_diagnostics", {})
    if diag:
        return ReasoningDiagnostics(
            mauna_active=bool(diag.get("mauna_active", False)),
            active_intervention=diag.get("active_intervention"),
            active_logic_template=diag.get("active_logic_template"),
            dominant_bhava=diag.get("dominant_bhava") or metadata.get("dominant_bhava"),
            active_kosha=diag.get("active_kosha"),
            vritti_state=diag.get("vritti_state"),
            vritti_rejection=bool(diag.get("vritti_rejection", False)),
            opb_active_locks=int(diag.get("opb_active_locks", 0)),
            opb_locked_dims=tuple(diag.get("opb_locked_dims", [])),
            opb_newly_locked=tuple(diag.get("opb_newly_locked", [])),
            opb_newly_unlocked=tuple(diag.get("opb_newly_unlocked", [])),
            entropy_delta=float(diag.get("entropy_delta", 0.0)),
            source="inference_bridge",
        )

    # Fallback: extract what's available from top-level metadata
    return ReasoningDiagnostics(
        dominant_bhava=metadata.get("dominant_bhava"),
        source="inference_bridge_partial",
    )
