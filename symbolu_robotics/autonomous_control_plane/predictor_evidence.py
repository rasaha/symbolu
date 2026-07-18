"""PredictorEvidence envelope.

Deterministic per-predictor evidence — NOT a generic "trust probability." Each
field is a bounded, physical, deterministic quantity or a discrete state, exactly
as specified in ``ACP_PREDICTOR_RELIABILITY_V2.md``.

The BCVF dynamic-disagreement feature is modelled as an OPTIONAL advisory that is
``None`` (disabled) by default and carries NO authorization authority: no
admissibility or authorization code path reads it as a gate (enforced in
``action_selection.py`` / ``constraints.py`` and asserted by the test suite).

Standard-library only.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Tuple

from .errors import SchemaValidationError
from .identity import identity, normalize_float

_DOMAIN = "predictor_evidence"


class ReliabilityState(str, Enum):
    """Resulting deterministic reliability state (see PR-V2 state machine)."""
    TRUSTED = "TRUSTED"
    DEGRADED = "DEGRADED"
    SUSPECT = "SUSPECT"
    FAILED = "FAILED"
    RECOVERING = "RECOVERING"


class VarianceState(str, Enum):
    NOMINAL = "NOMINAL"
    ELEVATED = "ELEVATED"
    HIGH = "HIGH"


class DropoutState(str, Enum):
    PRESENT = "PRESENT"
    INTERMITTENT = "INTERMITTENT"
    MISSING = "MISSING"


class CalibrationState(str, Enum):
    CALIBRATED = "CALIBRATED"
    DRIFTING = "DRIFTING"
    UNCALIBRATED = "UNCALIBRATED"


@dataclass(frozen=True)
class BCVFAdvisory:
    """Optional BCVF 2nd-order disagreement feature. ADVISORY ONLY.

    May shorten detection latency where an evaluator chooses to use it; it MUST
    NOT move a predictor to TRUSTED, silence a SUSPECT/FAILED, or authorize any
    action. ``advisory`` is fixed True to make the contract explicit in data.
    """
    margin: float
    would_advance_detection_ticks: int = 0
    note: str = ""
    advisory: bool = True

    def __post_init__(self) -> None:
        normalize_float(self.margin, field="BCVFAdvisory.margin")
        if self.advisory is not True:
            raise SchemaValidationError("BCVFAdvisory.advisory must be True")
        if self.would_advance_detection_ticks < 0:
            raise SchemaValidationError("would_advance_detection_ticks must be >= 0")


@dataclass(frozen=True)
class PredictorEvidence:
    """Deterministic evidence for one predictor at one tick."""
    predictor_id: str
    freshness_s: float                 # age of the newest sample
    latency_s: float                   # inter-arrival latency
    residual: float                    # ||predictor - robust consensus||
    normalized_residual: float         # uncertainty-normalized (NIS-like)
    persistent_bias: bool              # sustained windowed-mean bias indicator
    variance_state: VarianceState
    dropout_state: DropoutState
    calibration_state: CalibrationState
    reliability_state: ReliabilityState
    reason_codes: Tuple[str, ...] = ()
    # OFF by default; carries no authorization authority.
    bcvf_advisory: Optional[BCVFAdvisory] = None

    def __post_init__(self) -> None:
        if not self.predictor_id:
            raise SchemaValidationError("predictor_id must be non-empty")
        for f in ("freshness_s", "latency_s", "residual", "normalized_residual"):
            v = getattr(self, f)
            normalize_float(v, field=f"PredictorEvidence.{f}")
        if self.freshness_s < 0 or self.latency_s < 0:
            raise SchemaValidationError("freshness_s / latency_s must be >= 0")
        for enum_field, typ in (("variance_state", VarianceState),
                                ("dropout_state", DropoutState),
                                ("calibration_state", CalibrationState),
                                ("reliability_state", ReliabilityState)):
            if not isinstance(getattr(self, enum_field), typ):
                raise SchemaValidationError(f"{enum_field} must be {typ.__name__}")
        if not isinstance(self.reason_codes, tuple):
            raise SchemaValidationError("reason_codes must be an immutable tuple")
        if self.bcvf_advisory is not None and not isinstance(
                self.bcvf_advisory, BCVFAdvisory):
            raise SchemaValidationError("bcvf_advisory must be BCVFAdvisory or None")

    @property
    def bcvf_enabled(self) -> bool:
        return self.bcvf_advisory is not None

    @property
    def identity(self) -> str:
        return identity(self, domain=_DOMAIN)
