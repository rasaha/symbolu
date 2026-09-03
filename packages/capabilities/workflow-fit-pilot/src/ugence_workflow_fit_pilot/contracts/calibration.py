"""Calibration contracts for the revision-14/15 run-role architecture.

A calibration run measures one statistic and instantiates nothing by itself. It carries
the **same** governed plan, binding, roles and task-class identity a confirmatory run
does — because ``ReasoningMethodExecutionRecord`` and ``PilotObservation`` require them —
and differs in exactly two committed ways: its ``PilotRunRole`` and a governed threshold
that names a benchmark rather than a literal, so the comparison engine's ``tau`` is
``None`` by construction.

``CalibrationResult`` is deliberately reduced. It re-declares nothing that
``QualityEvaluationRecord`` and the attestation envelope already bind transitively;
it adds only what nothing else carries — the statistic, the sample-index digest, the
preregistration commitment pair, the verdict-custody reference and the formula identity.
Cross-artifact traversal (statistic against the reachable ``QualityResult``, literal
against the confirmatory threshold) belongs to the verifier slice, not to these value
objects.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from enum import Enum
from typing import Any

from ugence_reasoning_method_governance.api import ContractError, ContractErrorCode

from .._canon import digest_of, require_digest, require_nonblank, require_tzaware, settle_digest
from ..errors import PilotError, PilotErrorCode

CALIBRATION_RESULT_SCHEMA_VERSION = "workflow_fit_pilot.calibration_result.v1"
CALIBRATION_GOVERNED_UNIT = "score.unit"


class PilotRunRole(str, Enum):
    """The committed role of a manifest v2 run. There is no default: a missing or
    unknown role is refused, and a v1 manifest never acquires one by inference."""

    CALIBRATION = "CALIBRATION"
    CONFIRMATORY = "CONFIRMATORY"


def require_canonical_decimal(value: Any, name: str) -> Decimal:
    """A finite decimal carried as a string, the same discipline ``MetricClaim.value``
    and ``GovernedThreshold.literal_value`` follow. Bare numbers are refused: the
    canonicalizer admits none, and a float would not round-trip."""
    if not isinstance(value, str) or not value.strip():
        raise ContractError(ContractErrorCode.REF_BLANK_FIELD, f"{name} must be a non-blank decimal string")
    try:
        parsed = Decimal(value)
    except InvalidOperation:
        raise ContractError(ContractErrorCode.REF_BLANK_FIELD, f"{name} must be a decimal string") from None
    if not parsed.is_finite():
        raise ContractError(ContractErrorCode.REF_BLANK_FIELD, f"{name} must be finite")
    return parsed


def require_positive_count(value: Any, name: str) -> int:
    """The repository's typed-string numeric convention applies to the canonical payload;
    in the constructor the count is a positive Python integer, never a bool."""
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise PilotError(PilotErrorCode.COUNT_INVALID, f"{name} must be a positive integer")
    return value


@dataclass(frozen=True)
class CalibrationProvenance:
    """The confirmatory manifest's binding to the calibration that instantiated its
    threshold. Carried inside the manifest, so it participates in the manifest digest.

    This object proves *which* calibration a literal came from. Proving the literal
    *equals* that calibration's statistic and the task class's threshold is the
    verifier's job, deferred to the next slice."""

    calibration_result_digest: str
    calibration_manifest_digest: str
    calibration_commitment_identifier: str
    calibration_index_digest: str
    formula_id: str
    formula_version: str
    instantiated_literal: str

    def __post_init__(self) -> None:
        for name in ("calibration_result_digest", "calibration_manifest_digest", "calibration_index_digest"):
            require_digest(getattr(self, name), f"CalibrationProvenance.{name}")
        for name in ("calibration_commitment_identifier", "formula_id", "formula_version"):
            require_nonblank(getattr(self, name), f"CalibrationProvenance.{name}")
        require_canonical_decimal(self.instantiated_literal, "CalibrationProvenance.instantiated_literal")


@dataclass(frozen=True)
class CalibrationResult:
    """The only artifact permitted to instantiate a confirmatory threshold.

    Every field here is something no other artifact binds. The benchmark, method,
    evaluator, scorer and run identities are reachable through ``evaluation_digest`` and
    ``attestation_digest`` and are deliberately not repeated."""

    schema_version: str
    calibration_id: str
    manifest_digest: str
    evaluation_digest: str
    attestation_digest: str
    statistic_value: str
    governed_unit: str
    score_count: int
    sample_index_digest: str
    commitment_identifier: str
    index_digest: str
    verdict_custody_ref: str
    formula_id: str
    formula_version: str
    issued_by: str
    issued_at: datetime
    calibration_result_digest: str = ""

    def __post_init__(self) -> None:
        if self.schema_version != CALIBRATION_RESULT_SCHEMA_VERSION:
            raise PilotError(
                PilotErrorCode.SCHEMA_VERSION_UNSUPPORTED,
                f"CalibrationResult.schema_version must be {CALIBRATION_RESULT_SCHEMA_VERSION}",
            )
        require_nonblank(self.calibration_id, "CalibrationResult.calibration_id")
        for name in ("manifest_digest", "evaluation_digest", "attestation_digest", "sample_index_digest", "index_digest"):
            require_digest(getattr(self, name), f"CalibrationResult.{name}")
        require_canonical_decimal(self.statistic_value, "CalibrationResult.statistic_value")
        if self.governed_unit != CALIBRATION_GOVERNED_UNIT:
            raise PilotError(
                PilotErrorCode.CALIBRATION_STATISTIC_UNAVAILABLE,
                f"CalibrationResult.governed_unit is fixed at {CALIBRATION_GOVERNED_UNIT}",
            )
        require_positive_count(self.score_count, "CalibrationResult.score_count")
        for name in ("commitment_identifier", "verdict_custody_ref", "formula_id", "formula_version", "issued_by"):
            require_nonblank(getattr(self, name), f"CalibrationResult.{name}")
        require_tzaware(self.issued_at, "CalibrationResult.issued_at")
        settle_digest(self, "calibration_result_digest", digest_of(self, exclude=("calibration_result_digest",)))


__all__ = [
    "CALIBRATION_RESULT_SCHEMA_VERSION",
    "CALIBRATION_GOVERNED_UNIT",
    "PilotRunRole",
    "CalibrationProvenance",
    "CalibrationResult",
    "require_canonical_decimal",
    "require_positive_count",
]
