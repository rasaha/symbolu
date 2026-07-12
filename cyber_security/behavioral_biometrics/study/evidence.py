"""Transport-neutral evidence-export object for later Action-Gate integration.

This is a STUB for serialization/validation only. It does NOT call, import, or modify
the Action Gateway, and it NEVER contains an authorization decision (no ALLOW/DENY) —
only a recommended evidence action. The Action Gate owns decisions.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional

from cyber_security.behavioral_biometrics.version import (
    ANALYSIS_VERSION,
    EXTRACTOR_VERSION,
    STUDY_VERSION,
)

EVIDENCE_SCHEMA_VERSION = "bbio-evidence/1.0.0"

_RECOMMENDED_ACTIONS = {"CONTINUE_PASSIVE", "OBSERVE_MORE", "REQUEST_PASSIVE_EVIDENCE",
                        "REQUEST_ACTIVE_EVIDENCE", "INSUFFICIENT_EVIDENCE"}
_FORBIDDEN = {"ALLOW", "DENY", "PERMIT", "BLOCK", "AUTHORIZE"}


@dataclass
class EvidenceExport:
    session_id: str
    evidence_timestamp: str
    identity_probability: float
    confidence: float
    uncertainty: float
    evidence_sufficiency: float
    recommended_evidence_action: str
    calibration_status: str
    modality_quality: Dict[str, float] = field(default_factory=dict)
    anomaly_state: Optional[Dict[str, Any]] = None       # CUSUM / innovation diagnostics
    coupling_diagnostics: Optional[Dict[str, Any]] = None
    bcvf_disagreement: Optional[Dict[str, Any]] = None
    calibration_version: str = ""
    model_version: str = STUDY_VERSION
    extractor_version: str = EXTRACTOR_VERSION
    analysis_version: str = ANALYSIS_VERSION
    data_origin: str = ""
    data_freshness_seconds: Optional[float] = None
    evidence_schema_version: str = EVIDENCE_SCHEMA_VERSION

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def validate(export: Dict[str, Any]) -> List[str]:
    """Return a list of validation problems. Empty == valid. Fails closed on an
    authorization decision leaking into the evidence object."""
    problems: List[str] = []
    required = ("session_id", "evidence_timestamp", "identity_probability", "confidence",
                "uncertainty", "evidence_sufficiency", "recommended_evidence_action",
                "calibration_status", "data_origin", "evidence_schema_version")
    for r in required:
        if export.get(r) in (None, ""):
            problems.append(f"missing:{r}")
    for p in ("identity_probability", "confidence", "uncertainty", "evidence_sufficiency"):
        v = export.get(p)
        if isinstance(v, (int, float)) and not (0.0 <= float(v) <= 1.0):
            problems.append(f"out_of_range:{p}")
    action = export.get("recommended_evidence_action")
    if action not in _RECOMMENDED_ACTIONS:
        problems.append(f"bad_recommended_action:{action}")
    # tripwire: no authorization decision may appear anywhere in the object
    flat = " ".join(str(v) for v in export.values()).upper()
    for bad in _FORBIDDEN:
        if re.search(rf"\b{bad}\b", flat):
            problems.append(f"forbidden_authorization_token:{bad}")
    return problems


def build(*, session_id: str, timestamp: str, confidence_output: Dict[str, Any],
          modality_quality: Optional[Dict[str, float]] = None,
          anomaly_state: Optional[Dict[str, Any]] = None,
          coupling_diagnostics: Optional[Dict[str, Any]] = None,
          bcvf_disagreement: Optional[Dict[str, Any]] = None,
          calibration_version: str = "", data_origin: str = "",
          data_freshness_seconds: Optional[float] = None) -> EvidenceExport:
    c = confidence_output
    return EvidenceExport(
        session_id=session_id, evidence_timestamp=timestamp,
        identity_probability=float(c["identity_probability"]),
        confidence=float(c["confidence"]), uncertainty=float(c["uncertainty"]),
        evidence_sufficiency=float(c["evidence_sufficiency"]),
        recommended_evidence_action=c["recommended_evidence_action"],
        calibration_status=c["calibration_status"],
        modality_quality=modality_quality or {}, anomaly_state=anomaly_state,
        coupling_diagnostics=coupling_diagnostics, bcvf_disagreement=bcvf_disagreement,
        calibration_version=calibration_version, data_origin=data_origin,
        data_freshness_seconds=data_freshness_seconds)
