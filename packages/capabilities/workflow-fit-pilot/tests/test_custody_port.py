"""Slice 3B-1: the verdict-custody port and its in-memory double.

Every fixture is synthetic. The double is test-only (revision 20 ruling 3) and is never
genuine custody evidence; no adapter, endpoint or credential is exercised here.
"""

from __future__ import annotations

import pytest

from ugence_workflow_fit_pilot.custody import (
    InMemoryVerdictCustody,
    VerdictCustodyRecord,
    write_and_verify,
)
from ugence_reasoning_method_governance.errors import ContractError
from ugence_workflow_fit_pilot.errors import PilotError, PilotErrorCode

REF = "memory://workflow-fit-test/verdicts/rep0"
A, B = "a" * 64, "b" * 64


def _record(**overrides) -> VerdictCustodyRecord:
    kwargs = dict(custody_ref=REF, manifest_digest="c" * 64, index_digest="d" * 64,
                  verdicts=((A, "correct"), (B, "incorrect")))
    kwargs.update(overrides)
    return VerdictCustodyRecord(**kwargs)


# --------------------------------------------------------------------------- the record


def test_the_record_digest_settles_from_its_own_content():
    r = _record()
    assert r.record_digest and VerdictCustodyRecord(**{**_record().__dict__, "record_digest": ""}).record_digest == r.record_digest


def test_a_supplied_record_digest_covering_other_content_is_refused():
    with pytest.raises(PilotError) as e:
        _record(record_digest="e" * 64)
    assert e.value.code is PilotErrorCode.RETENTION_VERIFY_FAILED


def test_changing_any_field_changes_the_record_digest():
    base = _record().record_digest
    assert _record(index_digest="f" * 64).record_digest != base
    assert _record(manifest_digest="f" * 64).record_digest != base
    assert _record(custody_ref=REF + "/other").record_digest != base
    assert _record(verdicts=((A, "correct"), (B, "correct"))).record_digest != base


# The refusing guard is named per case rather than assumed: the shared _canon helpers raise
# ContractError while this module's own invariants raise PilotError, and a test that accepted
# either would not show which guard did the work.
@pytest.mark.parametrize(
    ("verdicts", "exc", "message"),
    [
        ((), PilotError, "non-empty tuple"),
        (((B, "x"), (A, "y")), PilotError, "ascending case-digest order"),
        (((A, "x"), (A, "y")), PilotError, "appears twice"),
        (((A,),), PilotError, "pair of strings"),
        (((A, ""),), ContractError, "must be a non-blank string"),
        ((("short", "x"),), ContractError, "64 lowercase hex characters"),
    ],
)
def test_malformed_verdict_sets_are_refused(verdicts, exc, message):
    with pytest.raises(exc, match=message):
        _record(verdicts=verdicts)


# --------------------------------------------------------------------------- the double


def test_write_then_read_back_reproduces_the_record():
    port = InMemoryVerdictCustody()
    r = _record()
    assert port.write(r) == r.record_digest
    assert port.read_back(REF).record_digest == r.record_digest


def test_custody_is_append_only():
    port = InMemoryVerdictCustody()
    port.write(_record())
    with pytest.raises(PilotError) as e:
        port.write(_record(verdicts=((A, "incorrect"), (B, "correct"))))
    assert e.value.code is PilotErrorCode.RETENTION_WRITE_FAILED


def test_reading_an_unwritten_reference_is_a_verify_failure_not_a_write_failure():
    with pytest.raises(PilotError) as e:
        InMemoryVerdictCustody().read_back("memory://workflow-fit-test/absent")
    assert e.value.code is PilotErrorCode.RETENTION_VERIFY_FAILED


def test_the_double_is_deterministic_across_instances():
    p1, p2 = InMemoryVerdictCustody(), InMemoryVerdictCustody()
    assert p1.write(_record()) == p2.write(_record())
    assert p1.written_references() == p2.written_references() == (REF,)


# --------------------------------------------------------------------------- write_and_verify


def test_write_and_verify_returns_the_verified_digest():
    port = InMemoryVerdictCustody()
    r = _record()
    assert write_and_verify(port, r) == r.record_digest


def test_a_write_failure_is_classified_by_the_write_operation():
    """§2.3: classification is by the operation that failed, never by exception class."""

    class RefusingWriter:
        def write(self, record):
            raise PilotError(PilotErrorCode.RETENTION_WRITE_FAILED, "store unavailable")

        def read_back(self, custody_ref):  # pragma: no cover - never reached
            raise AssertionError("read_back must not run after a write failure")

    with pytest.raises(PilotError) as e:
        write_and_verify(RefusingWriter(), _record())
    assert e.value.code is PilotErrorCode.RETENTION_WRITE_FAILED


def test_a_read_back_that_differs_is_a_verify_failure():
    class LyingStore:
        def __init__(self):
            self._other = _record(verdicts=((A, "incorrect"), (B, "correct")))

        def write(self, record):
            return record.record_digest

        def read_back(self, custody_ref):
            return self._other

    with pytest.raises(PilotError) as e:
        write_and_verify(LyingStore(), _record())
    assert e.value.code is PilotErrorCode.RETENTION_VERIFY_FAILED


def test_a_writer_reporting_a_digest_for_other_content_is_a_write_failure():
    class MisreportingWriter:
        def write(self, record):
            return "f" * 64

        def read_back(self, custody_ref):  # pragma: no cover - never reached
            raise AssertionError("read_back must not run after a write failure")

    with pytest.raises(PilotError) as e:
        write_and_verify(MisreportingWriter(), _record())
    assert e.value.code is PilotErrorCode.RETENTION_WRITE_FAILED


def test_the_double_satisfies_the_port_structurally():
    from ugence_workflow_fit_pilot.custody import VerdictCustodyPort

    port: VerdictCustodyPort = InMemoryVerdictCustody()
    assert write_and_verify(port, _record())
