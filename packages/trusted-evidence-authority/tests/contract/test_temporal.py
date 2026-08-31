"""Half-open temporal boundaries and the typed temporal refusals (ADR §17.9)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from _builders import VALID_FROM, VALID_TO, identity
from ugence_trusted_evidence_authority.api import (
    TrustedEvidenceContractError,
    TrustedEvidenceRefusalReason,
)

UTC = timezone.utc
TICK = timedelta(microseconds=1)


def test_the_lower_bound_is_inclusive():
    assert identity().is_valid_at(VALID_FROM) is True
    assert identity().temporal_refusal_at(VALID_FROM) is None


def test_just_before_the_lower_bound_is_not_yet_valid():
    instant = VALID_FROM - TICK
    assert identity().is_valid_at(instant) is False
    assert (
        identity().temporal_refusal_at(instant)
        is TrustedEvidenceRefusalReason.TRUSTED_EVIDENCE_NOT_YET_VALID
    )


def test_the_upper_bound_is_exclusive():
    """``valid_to`` itself is already stale — the interval is ``[from, to)``."""

    assert identity().is_valid_at(VALID_TO) is False
    assert (
        identity().temporal_refusal_at(VALID_TO)
        is TrustedEvidenceRefusalReason.TRUSTED_EVIDENCE_STALE
    )


def test_just_before_the_upper_bound_is_within():
    instant = VALID_TO - TICK
    assert identity().is_valid_at(instant) is True
    assert identity().temporal_refusal_at(instant) is None


def test_past_the_upper_bound_is_stale():
    assert (
        identity().temporal_refusal_at(VALID_TO + timedelta(days=1))
        is TrustedEvidenceRefusalReason.TRUSTED_EVIDENCE_STALE
    )


def test_an_absent_bound_is_open_on_that_side():
    far_past = datetime(1990, 1, 1, tzinfo=UTC)
    far_future = datetime(2999, 1, 1, tzinfo=UTC)
    assert identity(valid_from=None).is_valid_at(far_past) is True
    assert identity(valid_from=None).is_valid_at(VALID_TO - TICK) is True
    assert identity(valid_to=None).is_valid_at(far_future) is True
    assert identity(valid_from=None, valid_to=None).is_valid_at(far_past) is True


def test_the_evaluation_instant_is_mandatory_and_never_defaulted():
    with pytest.raises(TypeError):
        identity().is_valid_at()
    with pytest.raises(TypeError):
        identity().temporal_refusal_at()


def test_a_naive_evaluation_instant_is_refused():
    for method in ("is_valid_at", "temporal_refusal_at"):
        with pytest.raises(TrustedEvidenceContractError) as excinfo:
            getattr(identity(), method)(datetime(2026, 6, 1))
        assert "timezone-aware" in str(excinfo.value)


def test_temporal_answers_are_offset_independent():
    boundary_utc = VALID_TO
    boundary_ist = VALID_TO.astimezone(timezone(timedelta(hours=5, minutes=30)))
    assert boundary_utc == boundary_ist
    assert identity().is_valid_at(boundary_utc) == identity().is_valid_at(boundary_ist)
    assert identity().temporal_refusal_at(boundary_utc) is identity().temporal_refusal_at(
        boundary_ist
    )


def test_a_temporal_refusal_of_none_is_documented_as_not_a_pass():
    """The docstring must not be readable as "verified"."""

    doc = " ".join((type(identity()).temporal_refusal_at.__doc__ or "").split())
    assert "not a pass" in doc
    assert "unestablished" in doc


def test_no_method_reads_a_clock_to_answer_a_temporal_question():
    """Two calls a moment apart with the same instant give the same answer."""

    ident = identity()
    first = ident.temporal_refusal_at(VALID_TO)
    second = ident.temporal_refusal_at(VALID_TO)
    assert first is second is TrustedEvidenceRefusalReason.TRUSTED_EVIDENCE_STALE
