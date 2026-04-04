"""
Bhava Transition Priors — Pure-Python Runtime-Safe Extraction.

Extracted from sovereign/observer.py (BhavaTransitionPrior) for governance
audit/replay consumption. This module has NO torch dependency.

The 12x12 transition matrix encodes valid transitions between Bhava states.
High values (0.8–0.9) indicate natural transitions; low values (0.1–0.2)
indicate "ontological teleportation" — abrupt, questionable state jumps.

This is exposed as audit-only metadata: governance does NOT block on
transition penalties. The information enriches audit/replay logs by
documenting whether the model's state transitions were structurally
expected or anomalous.

Phase S4: sovereign integration.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional, Tuple

# 12 Bhava state names (matches inference_bridge.py BHAVA_NAMES)
BHAVA_NAMES: Tuple[str, ...] = (
    "POT", "IDN", "EXE", "STR", "COG", "AGY",
    "RSN", "PRP", "WIT", "UNI", "INT", "ABS",
)

# Observer-side Bhava names (from observer.py's transition matrix comments)
# These map to the canonical 12 Bhava states by position
OBSERVER_BHAVA_NAMES: Tuple[str, ...] = (
    "FACTUAL", "ANALYTICAL", "EVALUATIVE", "NARRATIVE",
    "ARGUMENTATIVE", "INSTRUCTIVE", "CERTAIN", "SPECULATIVE",
    "QUESTIONING", "POSITIVE", "NEGATIVE", "NEUTRAL",
)

# 12x12 transition probability matrix (from observer.py BhavaTransitionPrior)
# Rows: FROM state, Columns: TO state
# Values: 0.0–1.0 where higher = more valid transition
BHAVA_TRANSITION_MATRIX: Tuple[Tuple[float, ...], ...] = (
    # FACTUAL → ...
    (0.8, 0.8, 0.5, 0.3, 0.6, 0.2, 0.9, 0.2, 0.3, 0.5, 0.5, 0.9),
    # ANALYTICAL → ...
    (0.5, 0.9, 0.7, 0.2, 0.8, 0.4, 0.8, 0.4, 0.2, 0.3, 0.3, 0.5),
    # EVALUATIVE → ...
    (0.2, 0.5, 0.8, 0.3, 0.6, 0.3, 0.5, 0.4, 0.2, 0.9, 0.9, 0.2),
    # NARRATIVE → ...
    (0.4, 0.2, 0.4, 0.9, 0.3, 0.2, 0.4, 0.5, 0.3, 0.6, 0.6, 0.4),
    # ARGUMENTATIVE → ...
    (0.5, 0.8, 0.7, 0.2, 0.9, 0.5, 0.7, 0.5, 0.4, 0.4, 0.4, 0.3),
    # INSTRUCTIVE → ...
    (0.6, 0.4, 0.3, 0.2, 0.4, 0.9, 0.8, 0.2, 0.1, 0.5, 0.3, 0.5),
    # CERTAIN → ...
    (0.8, 0.7, 0.5, 0.3, 0.6, 0.7, 0.9, 0.1, 0.1, 0.5, 0.4, 0.6),
    # SPECULATIVE → ...
    (0.3, 0.5, 0.5, 0.5, 0.5, 0.2, 0.1, 0.9, 0.7, 0.4, 0.4, 0.4),
    # QUESTIONING → ...
    (0.4, 0.6, 0.4, 0.3, 0.5, 0.1, 0.2, 0.6, 0.8, 0.3, 0.3, 0.5),
    # POSITIVE → ...
    (0.4, 0.3, 0.8, 0.5, 0.4, 0.4, 0.5, 0.4, 0.3, 0.8, 0.2, 0.4),
    # NEGATIVE → ...
    (0.4, 0.3, 0.8, 0.5, 0.5, 0.3, 0.4, 0.4, 0.3, 0.2, 0.8, 0.4),
    # NEUTRAL → ...
    (0.8, 0.5, 0.3, 0.4, 0.4, 0.5, 0.6, 0.4, 0.4, 0.4, 0.4, 0.9),
)

# Name-to-index lookup
_BHAVA_NAME_TO_IDX: Dict[str, int] = {
    name: idx for idx, name in enumerate(BHAVA_NAMES)
}

# Also support observer-side names
_OBSERVER_NAME_TO_IDX: Dict[str, int] = {
    name: idx for idx, name in enumerate(OBSERVER_BHAVA_NAMES)
}


def get_transition_probability(
    from_bhava: str,
    to_bhava: str,
) -> Optional[float]:
    """Look up the transition probability between two Bhava states.

    Accepts either canonical (POT, IDN, ...) or observer-side
    (FACTUAL, ANALYTICAL, ...) Bhava names (case-insensitive).

    Returns None if either name is unrecognized.
    """
    from_idx = _resolve_bhava_index(from_bhava)
    to_idx = _resolve_bhava_index(to_bhava)
    if from_idx is None or to_idx is None:
        return None
    return BHAVA_TRANSITION_MATRIX[from_idx][to_idx]


def get_transition_penalty(
    from_bhava: str,
    to_bhava: str,
) -> Optional[float]:
    """Compute the transition penalty (0.0 = legal, 1.0 = illegal).

    Returns 1.0 - transition_probability, or None if names unrecognized.
    """
    prob = get_transition_probability(from_bhava, to_bhava)
    if prob is None:
        return None
    return round(1.0 - prob, 2)


@dataclass(frozen=True)
class BhavaTransitionAudit:
    """Audit snapshot for a Bhava state transition.

    This is metadata-only — it does not influence governance decisions.
    It documents whether the model's ontological state transition was
    structurally expected or anomalous.
    """
    from_bhava: Optional[str] = None
    to_bhava: Optional[str] = None
    transition_probability: Optional[float] = None
    transition_penalty: Optional[float] = None
    is_unusual: bool = False  # penalty > 0.5
    available: bool = False

    def to_audit_dict(self) -> Dict[str, object]:
        """Serialize for governance audit."""
        return {
            "from_bhava": self.from_bhava,
            "to_bhava": self.to_bhava,
            "transition_probability": self.transition_probability,
            "transition_penalty": self.transition_penalty,
            "is_unusual": self.is_unusual,
            "available": self.available,
        }


def evaluate_bhava_transition(
    from_bhava: Optional[str],
    to_bhava: Optional[str],
) -> BhavaTransitionAudit:
    """Evaluate a Bhava transition for audit purposes.

    Returns a BhavaTransitionAudit with transition metrics.
    If either bhava is None or unrecognized, returns available=False.
    """
    if from_bhava is None or to_bhava is None:
        return BhavaTransitionAudit()

    prob = get_transition_probability(from_bhava, to_bhava)
    if prob is None:
        return BhavaTransitionAudit(
            from_bhava=from_bhava,
            to_bhava=to_bhava,
        )

    penalty = round(1.0 - prob, 2)
    return BhavaTransitionAudit(
        from_bhava=from_bhava,
        to_bhava=to_bhava,
        transition_probability=prob,
        transition_penalty=penalty,
        is_unusual=penalty > 0.5,
        available=True,
    )


def _resolve_bhava_index(name: str) -> Optional[int]:
    """Resolve a Bhava name to its index."""
    upper = name.upper()
    idx = _BHAVA_NAME_TO_IDX.get(upper)
    if idx is not None:
        return idx
    return _OBSERVER_NAME_TO_IDX.get(upper)
