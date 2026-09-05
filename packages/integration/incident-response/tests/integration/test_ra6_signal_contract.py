"""The cross-package contract, checked by actually importing both sides.

This package builds an RA-6 reassessment payload and never imports RA-6. That is
the point of the seam — and it is also exactly what makes the claim unfalsifiable
from inside the package: a hand-written copy of RA-6's field names and enum
spellings keeps passing forever after RA-6 changes them.

So this test, and only this test, imports both. It performs the one adaptation a
composition root has to perform — wrapping the flat ``target_type``/``target_id``
in RA-6's ``SignalTarget`` and re-reading the change type as RA-6's enum — and
asserts the result is something RA-6 accepts: ``validation_errors() == ()``.

If RA-6 renames a field, adds a required one, or changes a spelling, this fails.
``tests/test_boundaries.py::test_the_authorities_this_package_signals_are_never_imported``
independently asserts the package's own source still imports nothing from
``risk_authority``, so the seam is not quietly widened by this test's existence.
"""

from __future__ import annotations

import dataclasses

import pytest

from ugence_incident_response import (
    ReassessmentSignalPayload,
    SignalChangeType,
    SignalTargetType,
    signal_for_containment,
)

from _fixtures import containment, incident

ra6 = pytest.importorskip(
    "risk_authority.domain.authority_signal",
    reason="RA-6 source tree is not on the path")


def _payload() -> ReassessmentSignalPayload:
    inc = incident()
    return signal_for_containment(
        inc, containment(inc), target_type=SignalTargetType.ENVELOPE,
        change_type=SignalChangeType.RUNTIME_RISK_ESCALATED,
        source_version="0.1.0", correlation_id="corr-1")


def _to_ra6(payload: ReassessmentSignalPayload):
    """The composition root's whole job, written out."""

    return ra6.AuthorityReassessmentSignal(
        target=ra6.SignalTarget(
            target_type=ra6.SignalTargetType(payload.target_type.value),
            target_id=payload.target_id),
        change_type=ra6.SignalChangeType(payload.change_type.value),
        **payload.as_signal_fields())


def test_a_payload_built_here_is_accepted_by_ra6():
    signal = _to_ra6(_payload())
    assert signal.validation_errors() == ()


def test_as_signal_fields_names_every_ra6_field_except_the_two_that_need_adapting():
    """No field is silently dropped, and none is invented.

    The two exceptions are named rather than glossed: RA-6 nests the target in its
    own type, and ``isinstance``-checks its own change-type enum, so neither can be
    supplied without importing RA-6.
    """

    theirs = {f.name for f in dataclasses.fields(ra6.AuthorityReassessmentSignal)}
    supplied = set(_payload().as_signal_fields())
    assert supplied | {"target", "change_type"} == theirs
    assert supplied.isdisjoint({"target", "change_type"})


def test_a_tenant_target_is_accepted_without_a_target_id():
    inc = incident()
    payload = signal_for_containment(
        inc, containment(inc), target_type=SignalTargetType.TENANT,
        change_type=SignalChangeType.EXECUTION_EFFECT_MISMATCH,
        source_version="0.1.0", correlation_id="corr-1")
    assert payload.target_id == ""
    assert _to_ra6(payload).validation_errors() == ()


def test_every_change_type_this_package_can_report_is_one_ra6_recognizes():
    for member in SignalChangeType:
        assert ra6.SignalChangeType(member.value).value == member.value
