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

**F3 and F4 — recorded in revision 16, implemented in slice 3B-1** (revision 21):

- **F3, enforced.** ``run_phase_4c_pilot`` calls
  ``PilotStudyManifest.require_phase_4c_eligible()`` before delegating, so a v1 manifest
  is refused *by the entry point*, not only by callers that ask. ``run_pilot`` stays
  ungated by ruling, for historical mechanism-validation tests.
- **F4, enforced at the entry point; `[G]` not at replay.** ``run_role`` and
  ``calibration_provenance`` are excluded from the **v1** digest payload, so a v1 object
  whose role was set by circumventing the frozen dataclass keeps a digest that still
  verifies. ``PilotStudyManifest.revalidate_role()`` re-runs the role invariants through
  the constructor rather than trusting that digest, and ``run_phase_4c_pilot`` calls it.
  It is **not** applied by ``validate_lineage``, the replay verifier, nor by
  ``is_calibration_run``, which read ``run_role`` directly — carried forward in
  revision 23.
- Slice 3 compares ``statistic_value``, ``instantiated_literal`` and the confirmatory
  threshold literal by **exact code-point equality** over the canonical form below, and
  must check the canonical rendering of the reachable ``QualityResult.value`` against
  the calibration statistic.
"""

from __future__ import annotations

import re
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


# The revision-16 canonical decimal grammar. One decimal value has exactly one
# admissible spelling, so slice 3 can reconcile a calibration statistic, a provenance
# literal and a confirmatory threshold by **code-point equality** rather than by
# numeric parsing — and so a digest over any of them is a digest over the value.
#
# Optional "-", then an integer part with no leading zeros (a lone zero, or a non-zero
# leading digit followed by any digits), then optionally "." and a fractional part whose
# last digit is non-zero. Rejected by construction: a leading "+", exponent notation, a
# leading integer zero, a trailing fractional zero, and surrounding whitespace.
# A negative zero matches this pattern and is rejected separately: every zero is "0".
# The worked examples live in revision 16 of the commissioning note, not here: the A31
# gate forbids a numeric literal anywhere in this package's source.
_CANONICAL_DECIMAL = re.compile(r"^-?(?:0|[1-9][0-9]*)(?:\.[0-9]*[1-9])?$")
CANONICAL_DECIMAL_GRAMMAR = _CANONICAL_DECIMAL.pattern


def canonical_decimal_rendering(value: Any, name: str = "value") -> str:
    """Derive the canonical Phase 4C spelling of a decimal that some other contract produced.

    **This derives; it does not normalise.** ``require_canonical_decimal`` refuses a
    caller-supplied, digest-bound string in a non-canonical spelling, and that rule is
    unchanged — normalising such a value would move a digest behind the caller's back. This
    function serves the opposite case, the one revision 16 named as slice 3's obligation:
    establishing "that the canonical string **derived from** the reachable
    ``QualityResult.value`` equals the calibration statistic". The reachable value belongs to
    ``MetricClaim``/``QualityResult``, whose looser spelling revision 16 explicitly declines to
    constrain retroactively, so the 4C spelling has to be derived rather than demanded.

    Why not fix it at the source instead: ``runner._mean`` feeds ``MetricClaim.value`` and
    ``QualityResult``. Making it emit the canonical spelling would impose Phase 4C's rule on
    those contracts — the retroactive imposition revision 16 forbids — and would move
    ``quality_result_digest`` and ``observation_digest`` for existing v1 and 4B runs.

    Accepts a ``Decimal`` or a decimal string. A ``float`` is refused: it would not round-trip.
    The result always satisfies ``require_canonical_decimal``."""
    if isinstance(value, bool) or isinstance(value, float):
        raise ContractError(
            ContractErrorCode.DECIMAL_UNPARSEABLE,
            f"{name} must be a Decimal or a decimal string, not {type(value).__name__}; a float would not round-trip",
        )
    if isinstance(value, Decimal):
        parsed = value
    elif isinstance(value, str):
        try:
            parsed = Decimal(value.strip())
        except InvalidOperation:
            raise ContractError(ContractErrorCode.DECIMAL_UNPARSEABLE, f"{name} is not a decimal: {value!r}") from None
    else:
        raise ContractError(
            ContractErrorCode.DECIMAL_UNPARSEABLE,
            f"{name} must be a Decimal or a decimal string, not {type(value).__name__}",
        )
    if not parsed.is_finite():
        raise ContractError(ContractErrorCode.DECIMAL_UNPARSEABLE, f"{name} must be finite; got {value!r}")
    # ``f`` is fixed-point and never emits an exponent, which the grammar forbids.
    text = format(parsed, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    if text in ("", "-", "-0"):
        text = "0"
    # Fail-closed tripwire, not a pinned guard: with the grammar as ratified no input makes
    # the derivation above produce a non-canonical string, so no test can distinguish this
    # line from its absence. It exists so that a future change to the grammar or to the
    # derivation fails here rather than handing a caller a string the contracts then refuse.
    require_canonical_decimal(text, name)
    return text


def require_matching_canonical_rendering(statistic_value: str, quality_value: Any, name: str) -> str:
    """Slice 3's obligation, executable: the calibration statistic must equal the canonical
    rendering of the reachable ``QualityResult.value``, by exact code-point equality.

    Returns the agreed rendering so a caller cannot use this as a boolean and discard which
    string actually matched."""
    require_canonical_decimal(statistic_value, name)
    derived = canonical_decimal_rendering(quality_value, f"{name} source")
    if statistic_value != derived:
        raise ContractError(
            ContractErrorCode.DECIMAL_UNPARSEABLE,
            f"{name} is {statistic_value!r} but the canonical rendering of the reachable "
            f"quality value is {derived!r}; they must be equal code point for code point",
        )
    return derived


def require_canonical_decimal(value: Any, name: str) -> Decimal:
    """A finite decimal in the single canonical spelling ratified in revision 16.

    Stricter than the repository's older convention: ``MetricClaim.value`` and
    ``GovernedThreshold.literal_value`` are only required to be non-empty strings and
    are not parsed, so they admit several spellings of one value. Phase 4C cannot,
    because these fields are compared and digested as strings. An equivalent but
    non-canonical form is **refused, never silently normalised** — normalising would
    change a digest-bound value behind the caller's back.

    Bare numbers are refused outright: the canonicaliser admits none, and a float would
    not round-trip. This rule is Phase 4C's own and is not imposed retroactively on any
    other governance contract."""
    if not isinstance(value, str):
        raise ContractError(ContractErrorCode.DECIMAL_UNPARSEABLE, f"{name} must be a decimal string, not {type(value).__name__}")
    if not _CANONICAL_DECIMAL.match(value) or value == "-0":
        raise ContractError(
            ContractErrorCode.DECIMAL_UNPARSEABLE,
            f"{name} must be a canonical decimal string (no whitespace, leading '+', exponent, "
            f"leading integer zero, trailing fractional zero or signed zero); got {value!r}",
        )
    try:
        parsed = Decimal(value)
    except InvalidOperation:  # unreachable through the grammar; kept so a pattern change fails closed
        raise ContractError(ContractErrorCode.DECIMAL_UNPARSEABLE, f"{name} must be a decimal string") from None
    if not parsed.is_finite():  # likewise unreachable: the grammar admits no NaN or Infinity
        raise ContractError(ContractErrorCode.DECIMAL_UNPARSEABLE, f"{name} must be finite")
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
            # F5, revision 16 — limitation recorded, not repaired. The statistic is
            # present and only its unit is wrong, so CALIBRATION_STATISTIC_UNAVAILABLE is
            # a semantic stretch. No existing code fits exactly: the precise name,
            # UNIT_MISMATCH, belongs to ``RefusalCode``, the comparison engine's
            # *evaluation-time* vocabulary, which ``ContractError`` cannot carry and which
            # a constructor has no standing to raise. Adding a code was forbidden, so the
            # ratified code is retained and the imprecision is documented here.
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
    "CANONICAL_DECIMAL_GRAMMAR",
    "canonical_decimal_rendering",
    "require_matching_canonical_rendering",
    "PilotRunRole",
    "CalibrationProvenance",
    "CalibrationResult",
    "require_canonical_decimal",
    "require_positive_count",
]
