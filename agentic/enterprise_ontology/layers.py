"""
The twelve semantic layers and per-record status.

These are SPARSE semantic buckets, not mandatory sequential stages. A layer may
be present, partial, absent, or not applicable for a given (event, vertical).
No band assumption is baked in: any layer may hold supplied, observed,
deterministically-derived, or interpretively-inferred information — that
distinction is carried by record metadata (see records.py), not by the layer.
"""

from __future__ import annotations

from enum import Enum


class OntologyLayer(str, Enum):
    POTENTIAL = "potential"
    EXECUTION = "execution"
    IDENTITY = "identity"
    FORM = "form"
    COGNITION = "cognition"
    AGENCY = "agency"
    REASONING = "reasoning"
    PURPOSE = "purpose"
    OBSERVATION = "observation"
    CORE = "core"
    UNIVERSAL = "universal"
    INTEGRATION = "integration"


class LayerStatus(str, Enum):
    PRESENT = "present"
    PARTIAL = "partial"
    NOT_CAPTURED = "not_captured"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    NOT_APPLICABLE = "not_applicable"
    PENDING = "pending"


# Convenience: the informal "evidence-ish" vs "intelligence-ish" reading is kept
# only as documentation — the pilot does NOT rely on it for any invariant.
_INFORMAL_EVIDENCE_BAND = (
    OntologyLayer.POTENTIAL, OntologyLayer.EXECUTION, OntologyLayer.IDENTITY,
    OntologyLayer.FORM, OntologyLayer.COGNITION, OntologyLayer.AGENCY,
)
_INFORMAL_INTELLIGENCE_BAND = (
    OntologyLayer.REASONING, OntologyLayer.PURPOSE, OntologyLayer.OBSERVATION,
    OntologyLayer.CORE, OntologyLayer.UNIVERSAL, OntologyLayer.INTEGRATION,
)
