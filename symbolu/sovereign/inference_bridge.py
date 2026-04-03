"""
Sovereign → Inference Bridge — Explicit Projection from Training State to Inference State.

REPRESENTATION GAP:
    Training time (sovereign/observer.py):
        128-D State Vector:
            Guna[0:16]       — 16-D cognitive dynamics (Sattva 5D, Rajas 5D, Tamas 6D)
            S-Signal[16:48]  — 32-D referent class (semantic category)
            R-Signal[48:96]  — 48-D ontological state (12 Bhava × 4 dims each)
            C-Signal[96:128] — 32-D phonemic features (deterministic hash)

    Inference time (inference/sovereign_state_monitor.py):
        32-D State Vector:
            Bhava[0:12]      — 12-D ontological aspects (phase rotation)
            Kosha[12:17]     — 5-D consciousness sheaths (depth control)
            Vritti[17:22]    — 5-D mental modifications (reliability gating)
            Guna[22:28]      — 6-D energy dynamics (lucidity/activity/stability/vel/accel/stable)
            Reserved[28:32]  — 4-D toroidal feedback (JEPA only)

    These are NOT the same state.  The inference 32-D is a restructured,
    lower-dimensional control-plane extraction from the full 128-D.  This
    module makes the projection explicit, testable, and auditable.

PROJECTION STRATEGY:
    1. R-Signal (48-D) → Bhava (12-D):  Average-pool each Bhava's 4 dims into 1
    2. Guna (16-D) → Guna (6-D):        Pool Sattva 5→1, Rajas 5→1, Tamas 6→1,
                                          then add velocity/acceleration/stability
                                          from state delta if available
    3. S-Signal / C-Signal → NOT projected (these have no inference-side slot)
    4. Kosha → Derived from Bhava profile (depth estimation)
    5. Vritti → Derived from R-Signal dominant Bhava pattern
    6. Reserved → Zero (not available without JEPA)

    Dimensions lost: S-Signal (32-D) and C-Signal (32-D) = 64 dims have
    no representation in inference state.  These are explicitly tracked
    in ProjectionMetadata.

Phase 4: Sovereign ↔ inference reconciliation.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# =========================================================================
# Constants — Training-time 128-D layout
# =========================================================================
TRAIN_GUNA_SLICE = slice(0, 16)
TRAIN_S_SIGNAL_SLICE = slice(16, 48)
TRAIN_R_SIGNAL_SLICE = slice(48, 96)
TRAIN_C_SIGNAL_SLICE = slice(96, 128)
TRAIN_STATE_DIM = 128

# Sub-structure within 16-D Guna
TRAIN_SATTVA_SLICE = slice(0, 5)   # dims 0-4
TRAIN_RAJAS_SLICE = slice(5, 10)   # dims 5-9
TRAIN_TAMAS_SLICE = slice(10, 16)  # dims 10-15

# =========================================================================
# Constants — Inference-time 32-D layout
# =========================================================================
INF_BHAVA_SLICE = slice(0, 12)
INF_KOSHA_SLICE = slice(12, 17)
INF_VRITTI_SLICE = slice(17, 22)
INF_GUNA_SLICE = slice(22, 28)
INF_RESERVED_SLICE = slice(28, 32)
INF_STATE_DIM = 32

# Bhava-to-Vritti mapping (from sovereign/vritti.py and pid_governor.py)
# Which Bhava patterns suggest which cognitive mode
_BHAVA_TO_VRITTI_MAP = {
    # Logic-heavy Bhavas → Pramana (truth/verification)
    "RSN": 0,  # Reasoning → FACT
    "UNI": 0,  # Unity → FACT
    # Memory-heavy Bhavas → Smriti (recall)
    "STR": 4,  # Structure → MEMORY
    "COG": 4,  # Cognition → MEMORY
    # Balanced Bhavas → Pramana
    "AGY": 0,  # Agency → FACT
    "WIT": 0,  # Witness → FACT
    # Dormant/potential → Nidra
    "POT": 3,  # Potential → VOID
    "ABS": 3,  # Absolute → VOID
    # Active/intent → Imagination/creative
    "EXE": 2,  # Execution → IMAGINATION
    "INT": 2,  # Intent → IMAGINATION
    # Identity/purpose → Memory/recall
    "IDN": 4,  # Identity → MEMORY
    "PRP": 0,  # Purpose → FACT
}

# Bhava-to-Kosha depth mapping (which Bhavas contribute to which depth)
# Weights for deriving Kosha from Bhava activations
_BHAVA_KOSHA_WEIGHTS = [
    # MATERIAL: surface processing (POT, EXE)
    [0.3, 0.0, 0.3, 0.1, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.1, 0.0],
    # VITAL: energy/flow (EXE, AGY, INT)
    [0.1, 0.0, 0.2, 0.0, 0.0, 0.3, 0.0, 0.0, 0.0, 0.0, 0.3, 0.0],
    # MENTAL: semantics (COG, RSN, PRP)
    [0.0, 0.0, 0.0, 0.1, 0.3, 0.0, 0.3, 0.2, 0.0, 0.0, 0.0, 0.0],
    # INTELLECTUAL: patterns (RSN, UNI, WIT)
    [0.0, 0.0, 0.0, 0.1, 0.1, 0.0, 0.3, 0.0, 0.2, 0.3, 0.0, 0.0],
    # BLISSFUL: integration (UNI, ABS, WIT)
    [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.2, 0.3, 0.1, 0.4],
]

# Bhava names for logging
BHAVA_NAMES = [
    "POT", "IDN", "EXE", "STR", "COG", "AGY",
    "RSN", "PRP", "WIT", "UNI", "INT", "ABS",
]


# =========================================================================
# Projection result
# =========================================================================

@dataclass(frozen=True)
class ProjectionMetadata:
    """Metadata about the sovereign → inference projection.

    Tracks projection fidelity and documents what was lost.
    """
    source_dim: int = TRAIN_STATE_DIM
    target_dim: int = INF_STATE_DIM
    # Which components were available for projection
    had_guna: bool = False
    had_r_signal: bool = False
    had_s_signal: bool = False
    had_c_signal: bool = False
    had_state_delta: bool = False
    # Fidelity measures
    bhava_projection_norm: float = 0.0   # L2 norm of projected Bhava
    guna_projection_norm: float = 0.0    # L2 norm of projected Guna
    # Explicit losses
    s_signal_dropped: bool = True        # S-Signal has no inference slot
    c_signal_dropped: bool = True        # C-Signal has no inference slot
    reserved_zeroed: bool = True         # Reserved dims are zero (no JEPA)
    kosha_derived: bool = True           # Kosha was derived, not directly measured
    vritti_derived: bool = True          # Vritti was derived, not directly measured
    # Warnings
    projection_warnings: Tuple[str, ...] = ()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source_dim": self.source_dim,
            "target_dim": self.target_dim,
            "had_guna": self.had_guna,
            "had_r_signal": self.had_r_signal,
            "had_s_signal": self.had_s_signal,
            "had_c_signal": self.had_c_signal,
            "had_state_delta": self.had_state_delta,
            "bhava_projection_norm": self.bhava_projection_norm,
            "guna_projection_norm": self.guna_projection_norm,
            "s_signal_dropped": self.s_signal_dropped,
            "c_signal_dropped": self.c_signal_dropped,
            "reserved_zeroed": self.reserved_zeroed,
            "kosha_derived": self.kosha_derived,
            "vritti_derived": self.vritti_derived,
            "projection_warnings": list(self.projection_warnings),
        }


@dataclass(frozen=True)
class SovereignProjectionResult:
    """Result of projecting 128-D sovereign state to 32-D inference state.

    Attributes:
        inference_state: List of 32 floats in inference layout.
        metadata: Projection fidelity and loss information.
        bhava_activations: Dict mapping Bhava name to projected value.
        dominant_bhava: Name of the dominant Bhava.
        guna_summary: Dict with lucidity/activity/stability keys.
        kosha_profile: 5-element tuple (depth profile).
        vritti_profile: 5-element tuple (reliability profile).
    """
    inference_state: Tuple[float, ...]  # 32 floats
    metadata: ProjectionMetadata
    bhava_activations: Dict[str, float]
    dominant_bhava: str
    guna_summary: Dict[str, float]
    kosha_profile: Tuple[float, ...]    # 5 floats
    vritti_profile: Tuple[float, ...]   # 5 floats

    def to_dict(self) -> Dict[str, Any]:
        return {
            "inference_state": list(self.inference_state),
            "metadata": self.metadata.to_dict(),
            "bhava_activations": self.bhava_activations,
            "dominant_bhava": self.dominant_bhava,
            "guna_summary": self.guna_summary,
            "kosha_profile": list(self.kosha_profile),
            "vritti_profile": list(self.vritti_profile),
        }


# =========================================================================
# Projection logic
# =========================================================================

def project_sovereign_to_inference(
    sovereign_state_128d: Any,
    state_delta_128d: Any = None,
) -> SovereignProjectionResult:
    """Project 128-D training sovereign state to 32-D inference state.

    This is an explicit, lossy projection.  The 128-D training state has
    richer information than the 32-D inference state can represent.  This
    function makes the mapping principled and the loss visible.

    Args:
        sovereign_state_128d: 128-element sequence (list, tuple, or tensor).
            Expected layout: Guna[0:16], S[16:48], R[48:96], C[96:128].
        state_delta_128d: Optional 128-element state delta for velocity/accel.

    Returns:
        SovereignProjectionResult with 32-D inference state and metadata.

    Fail-closed: Returns a zero state with warnings if input is malformed.
    """
    warnings: List[str] = []

    # Extract as plain floats
    vals = _to_float_list(sovereign_state_128d)
    if vals is None or len(vals) < TRAIN_STATE_DIM:
        warnings.append(
            f"Invalid sovereign state: expected {TRAIN_STATE_DIM} dims, "
            f"got {len(vals) if vals else 'None'}"
        )
        return _empty_projection(warnings)

    delta_vals = None
    if state_delta_128d is not None:
        delta_vals = _to_float_list(state_delta_128d)
        if delta_vals is None or len(delta_vals) < TRAIN_STATE_DIM:
            warnings.append("State delta malformed or wrong size, ignoring")
            delta_vals = None

    # ---- Extract training-time components ----
    train_guna_16 = vals[TRAIN_GUNA_SLICE]
    train_s_signal = vals[TRAIN_S_SIGNAL_SLICE]
    train_r_signal = vals[TRAIN_R_SIGNAL_SLICE]
    train_c_signal = vals[TRAIN_C_SIGNAL_SLICE]

    had_guna = any(abs(x) > 1e-9 for x in train_guna_16)
    had_r = any(abs(x) > 1e-9 for x in train_r_signal)
    had_s = any(abs(x) > 1e-9 for x in train_s_signal)
    had_c = any(abs(x) > 1e-9 for x in train_c_signal)
    had_delta = delta_vals is not None

    # ---- Step 1: R-Signal (48-D) → Bhava (12-D) ----
    # Average-pool each Bhava's 4 dims
    bhava_12 = []
    for i in range(12):
        start = i * 4
        end = start + 4
        dims = train_r_signal[start:end]
        bhava_12.append(sum(dims) / 4.0)

    bhava_norm = math.sqrt(sum(x * x for x in bhava_12))

    bhava_activations = {
        BHAVA_NAMES[i]: bhava_12[i] for i in range(12)
    }
    dominant_idx = max(range(12), key=lambda i: bhava_12[i])
    dominant_bhava = BHAVA_NAMES[dominant_idx]

    # ---- Step 2: Guna (16-D) → Guna (6-D) ----
    sattva_5 = train_guna_16[TRAIN_SATTVA_SLICE]
    rajas_5 = train_guna_16[TRAIN_RAJAS_SLICE]
    tamas_6 = train_guna_16[TRAIN_TAMAS_SLICE]

    lucidity = sum(sattva_5) / max(len(sattva_5), 1)
    activity = sum(rajas_5) / max(len(rajas_5), 1)
    stability = sum(tamas_6) / max(len(tamas_6), 1)

    # Velocity and acceleration from state delta if available
    velocity = 0.0
    acceleration = 0.0
    stable_measure = max(0.0, min(1.0, 1.0 - abs(velocity)))

    if delta_vals is not None:
        delta_guna = delta_vals[TRAIN_GUNA_SLICE]
        velocity = math.sqrt(sum(x * x for x in delta_guna)) / max(len(delta_guna), 1)
        # Acceleration would need second-order delta; approximate as velocity magnitude
        acceleration = velocity * 0.5
        stable_measure = max(0.0, min(1.0, 1.0 - velocity))

    guna_6 = [lucidity, activity, stability, velocity, acceleration, stable_measure]
    guna_norm = math.sqrt(sum(x * x for x in guna_6))

    guna_summary = {
        "lucidity": lucidity,
        "activity": activity,
        "stability": stability,
        "velocity": velocity,
        "acceleration": acceleration,
        "stable": stable_measure,
    }

    # ---- Step 3: Derive Kosha (5-D) from Bhava profile ----
    kosha_5 = _derive_kosha_from_bhava(bhava_12)

    # ---- Step 4: Derive Vritti (5-D) from Bhava pattern ----
    vritti_5 = _derive_vritti_from_bhava(bhava_12)

    # ---- Step 5: Reserved (4-D) → zeros ----
    reserved_4 = [0.0, 0.0, 0.0, 0.0]

    # ---- Assemble 32-D inference state ----
    inference_state = bhava_12 + kosha_5 + vritti_5 + guna_6 + reserved_4
    assert len(inference_state) == INF_STATE_DIM

    # ---- Track what was dropped ----
    if had_s:
        warnings.append("S-Signal (32-D referent) dropped: no inference slot")
    if had_c:
        warnings.append("C-Signal (32-D phonemic) dropped: no inference slot")

    metadata = ProjectionMetadata(
        had_guna=had_guna,
        had_r_signal=had_r,
        had_s_signal=had_s,
        had_c_signal=had_c,
        had_state_delta=had_delta,
        bhava_projection_norm=bhava_norm,
        guna_projection_norm=guna_norm,
        s_signal_dropped=had_s,
        c_signal_dropped=had_c,
        reserved_zeroed=True,
        kosha_derived=True,
        vritti_derived=True,
        projection_warnings=tuple(warnings),
    )

    return SovereignProjectionResult(
        inference_state=tuple(inference_state),
        metadata=metadata,
        bhava_activations=bhava_activations,
        dominant_bhava=dominant_bhava,
        guna_summary=guna_summary,
        kosha_profile=tuple(kosha_5),
        vritti_profile=tuple(vritti_5),
    )


# =========================================================================
# Helpers
# =========================================================================

def _to_float_list(tensor_or_list: Any) -> Optional[List[float]]:
    """Convert tensor/list to plain Python floats."""
    if tensor_or_list is None:
        return None
    try:
        if hasattr(tensor_or_list, 'detach'):
            # torch.Tensor
            t = tensor_or_list.detach().cpu()
            if t.dim() == 2:
                t = t[0]  # take first batch element
            return [float(x) for x in t.tolist()]
        if isinstance(tensor_or_list, (list, tuple)):
            return [float(x) for x in tensor_or_list]
    except (TypeError, ValueError, RuntimeError) as e:
        logger.debug("Failed to convert sovereign state to floats: %s", e)
        return None
    return None


def _derive_kosha_from_bhava(bhava_12: List[float]) -> List[float]:
    """Derive 5-D Kosha profile from 12-D Bhava activations.

    Uses fixed weight matrix mapping Bhava activations to Kosha sheaths.
    """
    kosha = []
    for weights in _BHAVA_KOSHA_WEIGHTS:
        val = sum(w * b for w, b in zip(weights, bhava_12))
        kosha.append(val)
    return kosha


def _derive_vritti_from_bhava(bhava_12: List[float]) -> List[float]:
    """Derive 5-D Vritti profile from 12-D Bhava activations.

    Distributes Bhava activation mass into the 5 Vritti buckets
    according to the _BHAVA_TO_VRITTI_MAP.
    """
    vritti = [0.0] * 5  # FACT, ERROR, IMAGINATION, VOID, MEMORY
    for i, name in enumerate(BHAVA_NAMES):
        target_vritti = _BHAVA_TO_VRITTI_MAP.get(name, 0)
        vritti[target_vritti] += abs(bhava_12[i])

    # Normalize to sum to 1.0 (softmax-like)
    total = sum(vritti) + 1e-9
    vritti = [v / total for v in vritti]
    return vritti


def _empty_projection(warnings: List[str]) -> SovereignProjectionResult:
    """Return a zero projection result for malformed input."""
    zero_32 = tuple([0.0] * INF_STATE_DIM)
    return SovereignProjectionResult(
        inference_state=zero_32,
        metadata=ProjectionMetadata(
            projection_warnings=tuple(warnings),
        ),
        bhava_activations={name: 0.0 for name in BHAVA_NAMES},
        dominant_bhava="POT",
        guna_summary={
            "lucidity": 0.0, "activity": 0.0, "stability": 0.0,
            "velocity": 0.0, "acceleration": 0.0, "stable": 0.0,
        },
        kosha_profile=(0.0, 0.0, 0.0, 0.0, 0.0),
        vritti_profile=(0.2, 0.2, 0.2, 0.2, 0.2),
    )
